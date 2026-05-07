"""
STARK MODE - Sound Activation System (terminal version)
========================================================

INSTALLING DEPENDENCIES:
-------------------------
Run these commands in your terminal before running the script:

    pip install sounddevice numpy pygame

If sounddevice fails to detect the microphone on macOS, also install:
    pip install PyAudio
    (requires: brew install portaudio)

EXPECTED FILE STRUCTURE:
-------------------------
JARVIS/
├── stark_mode.py       ← this script
└── jarvis.mp3          ← your preferred MP3 (rename it or change MUSIC_FILE)

SENSITIVITY ADJUSTMENT:
------------------------
- THRESHOLD: Value between 0.01 and 1.0.
  * 0.01–0.03  → very sensitive (triggers with normal voice or ambient noise)
  * 0.05–0.10  → sensitive (moderate clap or loud voice)
  * 0.15–0.30  → low sensitivity (hard clap or desk knock)
  Start at 0.08 and adjust to your microphone.

- CONFIRM_FRAMES: How many consecutive samples must exceed the threshold
  before triggering. Increase to avoid false positives.
"""

import sounddevice as sd
import numpy as np
import pygame
import subprocess
import webbrowser
import os
import sys
import time

# ─────────────────────────────────────────────
#  CONFIGURATION — edit these values
# ─────────────────────────────────────────────

# Microphone sensitivity (0.01 = very sensitive, 0.30 = low sensitivity)
THRESHOLD = 0.08

# How many consecutive frames above the threshold are needed
# to confirm activation (avoids false positives from brief noise)
CONFIRM_FRAMES = 3

# Microphone sample rate (Hz) — 44100 is standard
SAMPLE_RATE = 44100

# Size of the audio block analysed each cycle
BLOCK_SIZE = 1024

# MP3 file to play (must be in the same folder as this script)
MUSIC_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis.mp3")

# URL to open in the browser
BROWSER_URL = "https://claude.ai"

# Path of the folder to open in Finder / Explorer
TARGET_FOLDER = os.path.expanduser("~/Documents")

# Cooldown (seconds) before the system listens again after activation
COOLDOWN = 10

# ─────────────────────────────────────────────
#  ANSI COLOURS for the terminal
# ─────────────────────────────────────────────

RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def banner():
    print(f"""
{CYAN}{BOLD}
 ███████╗████████╗ █████╗ ██████╗ ██╗  ██╗    ███╗   ███╗ ██████╗ ██████╗ ███████╗
 ██╔════╝╚══██╔══╝██╔══██╗██╔══██╗██║ ██╔╝    ████╗ ████║██╔═══██╗██╔══██╗██╔════╝
 ███████╗   ██║   ███████║██████╔╝█████╔╝     ██╔████╔██║██║   ██║██║  ██║█████╗
 ╚════██║   ██║   ██╔══██║██╔══██╗██╔═██╗     ██║╚██╔╝██║██║   ██║██║  ██║██╔══╝
 ███████║   ██║   ██║  ██║██║  ██║██║  ██╗    ██║ ╚═╝ ██║╚██████╔╝██████╔╝███████╗
 ╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝     ╚═╝ ╚═════╝ ╚═════╝ ╚══════╝
{RESET}
{YELLOW}                         [ STARK INDUSTRIES — J.A.R.V.I.S. v1.0 ]{RESET}
{YELLOW}                  Sound Activation System — Access level: MAXIMUM{RESET}
""")


def print_config():
    print(f"{CYAN}{'─'*60}{RESET}")
    print(f"{BOLD}  ACTIVE CONFIGURATION:{RESET}")
    print(f"  Detection threshold : {YELLOW}{THRESHOLD}{RESET}")
    print(f"  Confirm frames      : {YELLOW}{CONFIRM_FRAMES}{RESET}")
    print(f"  Browser URL         : {YELLOW}{BROWSER_URL}{RESET}")
    print(f"  Target folder       : {YELLOW}{TARGET_FOLDER}{RESET}")
    music_status = f"{GREEN}✓ found{RESET}" if os.path.exists(MUSIC_FILE) else f"{RED}✗ not found ({MUSIC_FILE}){RESET}"
    print(f"  Music file          : {music_status}")
    print(f"{CYAN}{'─'*60}{RESET}\n")


def init_audio():
    pygame.mixer.init()


def play_music():
    if not os.path.exists(MUSIC_FILE):
        print(f"  {YELLOW}⚠  Music file not found: {MUSIC_FILE}{RESET}")
        print(f"  {YELLOW}   Place an MP3 named 'jarvis.mp3' next to the script.{RESET}")
        return
    try:
        pygame.mixer.music.load(MUSIC_FILE)
        pygame.mixer.music.play()
        print(f"  {GREEN}♪  Playing: {os.path.basename(MUSIC_FILE)}{RESET}")
    except Exception as e:
        print(f"  {RED}Error playing music: {e}{RESET}")


def open_browser():
    try:
        webbrowser.open(BROWSER_URL)
        print(f"  {GREEN}✓  Browser opened → {BROWSER_URL}{RESET}")
    except Exception as e:
        print(f"  {RED}Error opening browser: {e}{RESET}")


def open_calculator():
    """Opens the system calculator or terminal depending on the OS."""
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-a", "Calculator"])
            print(f"  {GREEN}✓  Calculator opened (macOS){RESET}")
        elif sys.platform.startswith("linux"):
            # Try gnome-calculator; fall back to xterm
            try:
                subprocess.Popen(["gnome-calculator"])
            except FileNotFoundError:
                subprocess.Popen(["xterm"])
            print(f"  {GREEN}✓  Calculator / Terminal opened (Linux){RESET}")
        elif sys.platform == "win32":
            subprocess.Popen(["calc.exe"])
            print(f"  {GREEN}✓  Calculator opened (Windows){RESET}")
    except Exception as e:
        print(f"  {RED}Error opening calculator: {e}{RESET}")


def open_folder():
    try:
        if not os.path.exists(TARGET_FOLDER):
            print(f"  {YELLOW}⚠  Folder not found: {TARGET_FOLDER}{RESET}")
            return

        if sys.platform == "darwin":
            subprocess.Popen(["open", TARGET_FOLDER])
        elif sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", TARGET_FOLDER])
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", TARGET_FOLDER])

        print(f"  {GREEN}✓  Folder opened → {TARGET_FOLDER}{RESET}")
    except Exception as e:
        print(f"  {RED}Error opening folder: {e}{RESET}")


def stark_mode():
    print(f"\n{GREEN}{BOLD}{'═'*60}{RESET}")
    print(f"{GREEN}{BOLD}  ✦  ACCESS GRANTED. WELCOME, SIR.{RESET}")
    print(f"{GREEN}{BOLD}{'═'*60}{RESET}\n")
    print(f"{CYAN}  Launching STARK MODE sequence...{RESET}\n")

    play_music()
    open_browser()
    open_calculator()
    open_folder()

    print(f"\n{CYAN}  Sequence complete. Entering standby ({COOLDOWN}s)...{RESET}")


def monitor_microphone():
    """
    Main loop: listens to the microphone in real time using sounddevice.
    When the block RMS exceeds THRESHOLD for CONFIRM_FRAMES consecutive
    samples, stark_mode() is triggered.
    """
    print(f"{CYAN}  Starting microphone monitoring...{RESET}")
    print(f"\n{YELLOW}{'─'*60}{RESET}")
    print(f"{BOLD}  >> Waiting for voice command...{RESET}")
    print(f"{YELLOW}  (Clap or knock hard to activate){RESET}")
    print(f"{YELLOW}  (Press Ctrl+C to exit){RESET}")
    print(f"{YELLOW}{'─'*60}{RESET}\n")

    trigger_count = 0
    last_trigger  = 0

    def audio_callback(indata, frames, time_info, status):
        """
        Invoked by sounddevice for each captured audio block.
        Runs in a separate thread — only performs atomic variable writes.
        """
        nonlocal trigger_count, last_trigger

        # RMS (Root Mean Square) of the block — a measure of volume
        rms = float(np.sqrt(np.mean(indata ** 2)))

        # Real-time level bar proportional to volume
        bar_len = int(rms * 300)
        bar     = "█" * min(bar_len, 50)
        color   = GREEN if rms < THRESHOLD else RED
        print(f"\r  Level: {color}{bar:<50}{RESET}  RMS: {rms:.4f}", end="", flush=True)

        now = time.time()

        # Ignore activations during the cooldown period
        if now - last_trigger < COOLDOWN:
            trigger_count = 0
            return

        if rms > THRESHOLD:
            trigger_count += 1
        else:
            trigger_count = 0  # reset on silence between samples

        if trigger_count >= CONFIRM_FRAMES:
            trigger_count = 0
            last_trigger  = now
            print()
            stark_mode()
            print(f"\n{YELLOW}{'─'*60}{RESET}")
            print(f"{BOLD}  >> Waiting for voice command...{RESET}")
            print(f"{YELLOW}{'─'*60}{RESET}\n")

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        blocksize=BLOCK_SIZE,
        channels=1,
        dtype="float32",
        callback=audio_callback,
    ):
        try:
            while True:
                time.sleep(0.1)
        except KeyboardInterrupt:
            print(f"\n\n{RED}  STARK MODE deactivated. Goodbye, Sir.{RESET}\n")


# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────

if __name__ == "__main__":
    banner()
    print_config()
    init_audio()
    monitor_microphone()
