#!/usr/bin/env python3
import threading
import time
from pynput import keyboard
from rich.console import Console

console = Console()

def on_press(key):
    console.print(f"[green]Key pressed: {key}[/green]")

def on_release(key):
    console.print(f"[red]Key released: {key}[/red]")
    if key == keyboard.Key.esc:
        console.print("[yellow]Exiting...[/yellow]")
        return False

console.print("[cyan]Testing keyboard listener. Press any key. Press ESC to exit.[/cyan]")

try:
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        console.print("[green]Listener started[/green]")
        listener.join()
except Exception as e:
    console.print(f"[red]Error: {e}[/red]")
    console.print("[yellow]Try: export DISPLAY=:0 or run in GUI terminal[/yellow]")