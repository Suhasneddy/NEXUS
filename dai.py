#!/usr/bin/env python3
"""
Diagnose mouse and keyboard listener issues
"""
from pynput import mouse, keyboard
from rich.console import Console
import time

console = Console()

console.print("[bold cyan]═══ Mouse & Keyboard Diagnostic Tool ═══[/bold cyan]\n")

# Test 1: Keyboard listener
console.print("[yellow]TEST 1: Keyboard Listener[/yellow]")
console.print("Press any key (or wait 5 seconds)...")

keyboard_works = False
def on_key_press(key):
    global keyboard_works
    keyboard_works = True
    console.print(f"[green]✓ Key detected: {key}[/green]")
    return False  # Stop listener

try:
    with keyboard.Listener(on_press=on_key_press) as listener:
        listener.join(timeout=5)
    
    if keyboard_works:
        console.print("[green]✓ Keyboard listener WORKS[/green]\n")
    else:
        console.print("[yellow]⚠ No keyboard input detected (timeout)[/yellow]\n")
except Exception as e:
    console.print(f"[red]✗ Keyboard listener FAILED: {e}[/red]\n")

# Test 2: Mouse listener
console.print("[yellow]TEST 2: Mouse Listener[/yellow]")
console.print("Click anywhere (or wait 5 seconds)...")

mouse_works = False
def on_mouse_click(x, y, button, pressed):
    global mouse_works
    if pressed:
        mouse_works = True
        console.print(f"[green]✓ Click detected: {button} at ({x}, {y})[/green]")
        return False  # Stop listener

try:
    with mouse.Listener(on_click=on_mouse_click) as listener:
        listener.join(timeout=5)
    
    if mouse_works:
        console.print("[green]✓ Mouse listener WORKS[/green]\n")
    else:
        console.print("[red]✗ Mouse listener FAILED (timeout - no clicks detected)[/red]")
        console.print("[yellow]This is common on Linux. Try one of these solutions:[/yellow]")
        console.print("  1. Run with sudo: sudo python3 main_hybrid.py")
        console.print("  2. Add user to input group: sudo usermod -a -G input $USER")
        console.print("  3. Use keyboard version instead (SPACEBAR to talk)\n")
except Exception as e:
    console.print(f"[red]✗ Mouse listener FAILED: {e}[/red]")
    console.print("[yellow]This is common on Linux. Try keyboard version instead.[/yellow]\n")

# Test 3: Check permissions
console.print("[yellow]TEST 3: Permission Check[/yellow]")
import os
import grp

try:
    username = os.getenv('USER')
    groups = [grp.getgrgid(g).gr_name for g in os.getgroups()]
    
    console.print(f"Current user: {username}")
    console.print(f"Member of groups: {', '.join(groups)}")
    
    if 'input' in groups:
        console.print("[green]✓ User is in 'input' group[/green]")
    else:
        console.print("[yellow]⚠ User NOT in 'input' group (may cause mouse issues)[/yellow]")
        console.print("[dim]   Fix: sudo usermod -a -G input $USER && reboot[/dim]")
        
except Exception as e:
    console.print(f"[yellow]Could not check groups: {e}[/yellow]")

console.print("\n[bold cyan]═══ Summary ═══[/bold cyan]")
if keyboard_works:
    console.print("[green]✓ Use keyboard version (SPACEBAR)[/green]")
if mouse_works:
    console.print("[green]✓ Mouse version should work[/green]")
if not mouse_works and not keyboard_works:
    console.print("[red]⚠ Both failed - may need to run with sudo[/red]")