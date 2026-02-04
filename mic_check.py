import speech_recognition as sr
import time
from rich.console import Console

console = Console()

def test_mic(index):
    r = sr.Recognizer()
    r.energy_threshold = 300  # Low threshold
    
    try:
        with sr.Microphone(device_index=index) as source:
            console.print(f"\n[bold yellow]Testing Mic Index {index}...[/bold yellow]")
            console.print("[dim]Speak now! You should see energy levels changing.[/dim]")
            r.adjust_for_ambient_noise(source, duration=1)
            
            start = time.time()
            # Listen for 5 seconds
            while time.time() - start < 5:
                # Read a chunk of audio
                buffer = source.stream.read(source.CHUNK)
                # Calculate simple energy (volume)
                energy = sum(abs(x) for x in buffer) / len(buffer)
                
                # Draw a bar
                bar_len = int(energy / 5) 
                bar = "█" * min(bar_len, 50)
                print(f"\rVolume: {bar:<50}", end="")
                
            print("\n[green]Done.[/green]")
            return True
    except Exception as e:
        console.print(f"[red]Failed to access Index {index}: {e}[/red]")
        return False

# --- TEST CANDIDATES ---
# Based on your previous logs, these are the likely ones:
candidates = [5, 11, 10] # 5 (Analog), 11 (Default), 10 (Pulse)

for idx in candidates:
    print("-" * 30)
    test_mic(idx)xx