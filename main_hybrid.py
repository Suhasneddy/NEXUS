import threading
import queue
import time
import sys
import os
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

# --- CONFIGURATION ---
AI_MODEL = "llama3.2:latest"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
WHISPER_MODEL = "small.en"
SAMPLE_RATE = 16000

# Available female voices (from sweetest to most professional):
# af_sarah - Warm, friendly, conversational (RECOMMENDED)
# af_nicole - Clear, pleasant, professional
# af_sky - Youthful, energetic
# bf_emma - British accent, elegant
# bf_isabella - British accent, sophisticated
VOICE = "af_sarah"  # Change this to try different voices
SPEECH_SPEED = 1.0  # 0.8 = slower, 1.2 = faster

# --- INIT ---
console = Console()

# Load models once
console.print("[cyan]Loading models...[/cyan]")
stt_model = whisper.load_model(WHISPER_MODEL, device=DEVICE)
tts_pipeline = KPipeline(lang_code='a', device=DEVICE)
console.print(f"[green]✓ Models loaded (Voice: {VOICE})[/green]")

# Audio recording variables
is_recording = False
audio_buffer = []
stream = None

# --- STATES ---
class State(Enum):
    IDLE = 1
    LISTENING = 2
    THINKING = 3
    SPEAKING = 4

current_state = State.IDLE
audio_queue = queue.Queue()

# --- AUDIO CALLBACK ---
def audio_callback(indata, frames, time_info, status):
    """Callback for audio recording"""
    if is_recording:
        audio_buffer.append(indata.copy())

# --- RECORDING CONTROL ---
def start_recording():
    global is_recording, stream, audio_buffer
    
    if not is_recording:
        is_recording = True
        audio_buffer = []
        console.print("[yellow]🎤 RECORDING... Press ENTER when done speaking[/yellow]")
        
        try:
            stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype='float32',
                callback=audio_callback
            )
            stream.start()
        except Exception as e:
            console.print(f"[red]Recording error: {e}[/red]")
            is_recording = False

def stop_recording():
    global is_recording, stream, audio_buffer
    
    if is_recording:
        is_recording = False
        console.print("[cyan]⏹️  Processing...[/cyan]")
        
        try:
            if stream:
                stream.stop()
                stream.close()
            
            if len(audio_buffer) > 0:
                full_audio = np.concatenate(audio_buffer, axis=0).flatten()
                max_amplitude = np.max(np.abs(full_audio))
                
                console.print(f"[dim]Audio: {len(full_audio)} samples ({len(full_audio)/SAMPLE_RATE:.2f}s), amplitude: {max_amplitude:.4f}[/dim]")
                
                if max_amplitude > 0.01 and len(full_audio) > SAMPLE_RATE * 0.3:
                    audio_queue.put(full_audio)
                else:
                    console.print("[red]Audio too quiet or too short, try again[/red]")
                    console.print("[green]● Press ENTER to record...[/green]")
            else:
                console.print("[red]No audio data recorded[/red]")
                console.print("[green]● Press ENTER to record...[/green]")
                
        except Exception as e:
            console.print(f"[red]Error processing recording: {e}[/red]")
            console.print("[green]● Press ENTER to record...[/green]")

# --- INPUT THREAD ---
def input_thread():
    """Thread to handle user input"""
    while True:
        try:
            user_input = input()
            
            if user_input.lower() in ['quit', 'exit', 'q']:
                console.print("[yellow]Exiting...[/yellow]")
                os._exit(0)
            
            if not is_recording:
                start_recording()
            else:
                stop_recording()
                
        except EOFError:
            break
        except Exception as e:
            console.print(f"[red]Input error: {e}[/red]")

# --- THE EARS (Whisper STT) ---
def transcribe_audio(audio_data):
    """Transcribe audio using Whisper"""
    try:
        if len(audio_data) == 0:
            return ""
            
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

# --- THE MOUTH (Kokoro TTS) ---
async def speak(text):
    """Convert text to speech using Kokoro TTS"""
    global current_state
    current_state = State.SPEAKING
    
    speech_text = text
    if "{" in text and "}" in text:
        speech_text = "Command executed."

    console.print(Panel(f"[magenta]🗣️ {speech_text}[/magenta]", title="Nexus Speaking"))

    try:
        # Generate speech with selected voice
        generator = tts_pipeline(speech_text, voice=VOICE, speed=SPEECH_SPEED)
        
        # Collect ALL audio chunks (this was the bug - it was breaking after first chunk)
        all_audio = []
        for i, (gs, ps, audio) in enumerate(generator):
            all_audio.append(audio)
            console.print(f"[dim]Generating speech chunk {i+1}...[/dim]")
        
        # Concatenate and play all audio at once
        if all_audio:
            console.print(f"[dim]Playing {len(all_audio)} audio chunks...[/dim]")
            full_audio = np.concatenate(all_audio)
            sd.play(full_audio, 24000)
            sd.wait()  # Wait for playback to complete
            
    except Exception as e:
        console.print(f"[red]Speech error: {e}[/red]")
    
    current_state = State.LISTENING
    console.print("[green]● Press ENTER to record...[/green]")

# --- THE BRAIN (Ollama) ---
def process_command(user_text):
    """Process user command through AI"""
    global current_state
    current_state = State.THINKING
    
    system_prompt = """You are Nexus, a helpful and friendly AI assistant with a warm personality. 
Keep your responses conversational, clear, and concise. When giving lists or multiple points, 
structure them naturally but don't make responses too long."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text}
    ]

    console.print("[yellow]🧠 Thinking...[/yellow]")
    
    try:
        response = ollama.chat(
            model=AI_MODEL, 
            messages=messages,
            options={
                "temperature": 0.7,
                "top_p": 0.9,
                "num_predict": 300,  # Increased for longer responses
                "num_ctx": 2048
            }
        )
        return response['message']['content']
        
    except Exception as e:
        console.print(f"[red]AI error: {e}[/red]")
        return "I'm having trouble processing that request."

# --- MAIN LOOP ---
async def main():
    global current_state
    
    console.print(Panel(
        "[bold green]🤖 Nexus V2 Hybrid (Whisper + Kokoro + Ollama)[/bold green]\n"
        f"[cyan]Voice: {VOICE} | Speed: {SPEECH_SPEED}x[/cyan]\n\n"
        "Commands:\n"
        "• Press [ENTER] to start recording\n"
        "• Press [ENTER] again to stop and process\n"
        "• Type 'quit' or 'q' to exit",
        title="System"
    ))
    
    current_state = State.LISTENING
    console.print("[green]● Press ENTER to start recording...[/green]")
    
    # Start input thread
    input_thread_obj = threading.Thread(target=input_thread, daemon=True)
    input_thread_obj.start()
    
    try:
        while True:
            try:
                # Check for audio data
                audio_data = audio_queue.get(timeout=0.1)
                
                # Transcribe with Whisper
                console.print("[cyan]🎯 Transcribing...[/cyan]")
                text = transcribe_audio(audio_data)
                
                if text and len(text) > 1:
                    console.print(f"[cyan]👤 You said:[/cyan] {text}")
                    
                    # Process with Ollama
                    response = process_command(text)
                    
                    # Speak response with Kokoro
                    await speak(response)
                else:
                    console.print("[yellow]No speech detected, try again[/yellow]")
                    console.print("[green]● Press ENTER to record...[/green]")

            except queue.Empty:
                await asyncio.sleep(0.1)
            except KeyboardInterrupt:
                break
                
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
    finally:
        if stream:
            stream.close()
        console.print("[yellow]Shutting down...[/yellow]")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        console.print("\n[yellow]Goodbye![/yellow]")