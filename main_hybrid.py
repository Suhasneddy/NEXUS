import threading
import queue
import asyncio
import whisper
import torch
import numpy as np
import sounddevice as sd
import ollama
from kokoro import KPipeline
from rich.console import Console
from rich.panel import Panel
from enum import Enum
from scipy.signal import resample_poly
from math import gcd

# --- CONFIGURATION ---
AI_MODEL = "llama3.2:latest"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
WHISPER_MODEL = "small.en"
SAMPLE_RATE = 16000
INPUT_DEVICE = 7     # acp6x Digital Microphone (hw:3,0) - built-in laptop mic
RECORD_RATE = 48000  # Device native rate; resampled to SAMPLE_RATE for Whisper
VOICE = "af_sarah"
SPEECH_SPEED = 1.0

# --- INIT ---
console = Console()
console.print("[cyan]Loading models...[/cyan]")
stt_model = whisper.load_model(WHISPER_MODEL, device=DEVICE)
tts_pipeline = KPipeline(lang_code='a', device=DEVICE)
console.print(f"[green]✓ Models loaded (Voice: {VOICE})[/green]")

class State(Enum):
    IDLE = 1
    LISTENING = 2
    THINKING = 3
    SPEAKING = 4

current_state = State.IDLE
audio_queue = queue.Queue()
is_recording = False
_audio_chunks = []
_stream = None

# --- INPUT HANDLER ---
def input_handler():
    global is_recording, _audio_chunks, _stream

    while True:
        try:
            input()  # Wait for Enter

            if not is_recording:
                is_recording = True
                _audio_chunks = []
                console.print("[yellow]🎤 RECORDING... Press ENTER to stop[/yellow]")

                def callback(indata, frames, time_info, status):
                    if is_recording:
                        _audio_chunks.append(indata.copy())

                try:
                    _stream = sd.InputStream(
                        samplerate=RECORD_RATE,
                        channels=2,
                        dtype='float32',
                        device=INPUT_DEVICE,
                        callback=callback
                    )
                    _stream.start()
                except Exception as e:
                    console.print(f"[red]Recording error: {e}[/red]")
                    is_recording = False
            else:
                is_recording = False
                console.print("[cyan]⏹️  Processing...[/cyan]")

                if _stream is not None:
                    try:
                        _stream.stop()
                        _stream.close()
                    except Exception:
                        pass
                    _stream = None

                if _audio_chunks:
                    full_audio = np.concatenate(_audio_chunks)
                    # Mix stereo to mono
                    if full_audio.ndim == 2:
                        full_audio = full_audio.mean(axis=1)
                    full_audio = full_audio.flatten()
                    max_amplitude = np.max(np.abs(full_audio))

                    g = gcd(SAMPLE_RATE, RECORD_RATE)
                    full_audio = resample_poly(full_audio, SAMPLE_RATE // g, RECORD_RATE // g).astype(np.float32)

                    console.print(f"[dim]Audio: {len(full_audio)} samples ({len(full_audio)/SAMPLE_RATE:.2f}s), amplitude: {max_amplitude:.4f}[/dim]")

                    if max_amplitude > 0.01:
                        audio_queue.put(full_audio)
                    else:
                        console.print("[red]Audio too quiet - check mic volume[/red]")
                        console.print("[green]● Press ENTER to record...[/green]")
                else:
                    console.print("[red]No audio captured[/red]")
                    console.print("[green]● Press ENTER to record...[/green]")
        except:
            break

# --- STT ---
def transcribe_audio(audio_data):
    try:
        audio_data = audio_data.astype(np.float32)
        max_val = np.max(np.abs(audio_data))
        if max_val > 0:
            audio_data = audio_data / max_val

        result = stt_model.transcribe(
            audio_data,
            fp16=False,
            language="en",
            task="transcribe",
            temperature=0.0,
            no_speech_threshold=0.6
        )
        return result['text'].strip()
    except Exception as e:
        console.print(f"[red]❌ Transcription error: {e}[/red]")
        return ""

# --- TTS ---
async def speak(text):
    global current_state
    current_state = State.SPEAKING

    speech_text = "Command executed." if "{" in text and "}" in text else text
    console.print(Panel(f"[magenta]🗣️ {speech_text}[/magenta]", title="Nexus Speaking"))

    try:
        all_audio = []
        for _, _, audio in tts_pipeline(speech_text, voice=VOICE, speed=SPEECH_SPEED):
            all_audio.append(audio)

        if all_audio:
            sd.play(np.concatenate(all_audio), 24000)
            sd.wait()
    except Exception as e:
        console.print(f"[red]Speech error: {e}[/red]")

    current_state = State.LISTENING
    console.print("[green]● Press ENTER to record...[/green]")

# --- AI ---
def process_command(user_text):
    global current_state
    current_state = State.THINKING
    console.print("[yellow]🧠 Thinking...[/yellow]")

    try:
        response = ollama.chat(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": "You are Nexus, a helpful and friendly AI assistant. Keep responses conversational and concise."},
                {"role": "user", "content": user_text}
            ],
            options={"temperature": 0.7, "top_p": 0.9, "num_predict": 300, "num_ctx": 2048}
        )
        return response['message']['content']
    except Exception as e:
        console.print(f"[red]AI error: {e}[/red]")
        return "I'm having trouble processing that request."

# --- MAIN ---
async def main():
    global current_state

    console.print(Panel(
        "[bold green]🤖 Nexus V2 Hybrid (Whisper + Kokoro + Ollama)[/bold green]\n"
        f"[cyan]Voice: {VOICE} | Speed: {SPEECH_SPEED}x[/cyan]\n\n"
        "• Press [ENTER] to start recording\n"
        "• Press [ENTER] again to stop\n"
        "• Press Ctrl+C to exit",
        title="System"
    ))

    current_state = State.LISTENING
    console.print("[green]● Press ENTER to record...[/green]")

    threading.Thread(target=input_handler, daemon=True).start()

    try:
        while True:
            try:
                audio_data = audio_queue.get(timeout=0.1)

                console.print("[cyan]🎯 Transcribing...[/cyan]")
                text = transcribe_audio(audio_data)

                if text and len(text) > 1:
                    console.print(f"[cyan]👤 You said:[/cyan] {text}")
                    response = process_command(text)
                    await speak(response)
                else:
                    console.print("[yellow]No speech detected[/yellow]")
                    console.print("[green]● Press ENTER to record...[/green]")


            except queue.Empty:
                await asyncio.sleep(0.1)
            except KeyboardInterrupt:
                break
    finally:
        console.print("[yellow]Shutting down...[/yellow]")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")
