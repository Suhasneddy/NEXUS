# Hybrid Voice Assistant

A voice assistant combining Whisper STT, Kokoro TTS, and Ollama AI with mouse-based push-to-talk functionality.

## Features
- **Speech-to-Text**: Whisper (small.en model)
- **Text-to-Speech**: Kokoro TTS with natural voice
- **AI Processing**: Ollama (llama3.2:latest)
- **Push-to-Talk**: Left mouse button control

## Setup
1. Create virtual environment: `python -m venv venv_omen`
2. Activate: `source venv_omen/bin/activate`
3. Install dependencies: `pip install -r requirements.txt`
4. Run: `python main_hybrid.py`

## Usage
- Hold **Left Mouse Button** to record
- Release to process and get AI response
- Press **Ctrl+C** to exit

## Files
- `main_hybrid.py` - Main voice assistant with mouse PTT
- `requirements.txt` - Python dependencies
- `mic_test.py` - Microphone diagnostic tool