"""
STARK MODE — macOS Menu Bar App
================================
Run: python3 stark_menubar.py

The menu bar icon shows a live VU-meter.
Click it to see the dropdown with threshold slider, feature toggles and settings.

Dependencies:
    pip install -r requirements.txt

Settings are persisted automatically in stark_config.json (same folder as this script).
"""

import rumps
import sounddevice as sd
import numpy as np
import pygame
import threading
import subprocess
import webbrowser
import json
import os
import sys
import time

# ─────────────────────────────────────────────
#  PATHS
# ─────────────────────────────────────────────

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SCRIPT_DIR, "stark_config.json")

# ─────────────────────────────────────────────
#  DEFAULTS  (used when no saved config exists)
# ─────────────────────────────────────────────

DEFAULTS = {
    "browser_url":    "https://claude.ai",
    "system_app":     "Calculator",        # macOS app name as seen in /Applications
    "folder_path":    os.path.expanduser("~/Documents"),
    "music_file":     os.path.join(SCRIPT_DIR, "jarvis.mp3"),
    "threshold":      0.08,
    "enable_browser": True,
    "enable_app":     True,
    "enable_folder":  True,
    "enable_music":   True,
}

# ─────────────────────────────────────────────
#  CONSTANTS
# ─────────────────────────────────────────────

THRESHOLD_MIN  = 0.01   # most sensitive
THRESHOLD_MAX  = 0.50   # least sensitive
CONFIRM_FRAMES = 3      # consecutive frames above threshold required to trigger
SAMPLE_RATE    = 44100
BLOCK_SIZE     = 1024
COOLDOWN       = 10     # seconds before the system can be triggered again

VU_CHARS = " ▁▂▃▄▅▆▇█"   # 9 levels for the live icon in the menu bar


# ─────────────────────────────────────────────
#  CONFIG HELPERS
# ─────────────────────────────────────────────

def load_config() -> dict:
    """Load config from JSON; fill missing keys with defaults."""
    config = dict(DEFAULTS)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                config.update(json.load(f))
        except (json.JSONDecodeError, OSError):
            pass
    return config


def save_config(config: dict) -> None:
    """Persist current config to JSON."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except OSError:
        pass


# ─────────────────────────────────────────────
#  MAIN APP
# ─────────────────────────────────────────────

class StarkApp(rumps.App):

    def __init__(self):
        super().__init__("⚡", quit_button=None)

        self.cfg           = load_config()
        self.muted         = False
        self.threshold     = float(self.cfg["threshold"])
        self.trigger_count = 0
        self.last_trigger  = 0.0
        self.current_rms   = 0.0
        self._triggered    = False
        self._stop_event   = threading.Event()

        self._build_menu()

        pygame.mixer.init()
        threading.Thread(target=self._audio_loop, daemon=True).start()
        rumps.Timer(self._refresh_ui, 0.1).start()

    # ────────────────────────────────────────────────────────────────────
    #  MENU
    # ────────────────────────────────────────────────────────────────────

    def _build_menu(self):
        self.item_header = rumps.MenuItem("STARK MODE  —  J.A.R.V.I.S.")
        self.item_header.set_callback(None)

        self.item_status = rumps.MenuItem("● Listening...")
        self.item_status.set_callback(None)

        # Stop button — hidden until STARK MODE fires
        self.item_stop = rumps.MenuItem("⏹  Stop STARK MODE", callback=self._stop_stark)
        self.item_stop.hidden = True

        self.item_level = rumps.MenuItem("  Level  ░░░░░░░░░░░░░░░░░░░░  0.0000")
        self.item_level.set_callback(None)

        # Threshold slider
        self.item_threshold_label = rumps.MenuItem(self._threshold_text())
        self.item_threshold_label.set_callback(None)

        self.item_slider = rumps.SliderMenuItem(
            value=self.threshold,
            min_value=THRESHOLD_MIN,
            max_value=THRESHOLD_MAX,
            callback=self._on_threshold_slide,
            dimensions=(200, 18),
        )
        self.item_slider._slider.setContinuous_(True)

        # Feature toggles
        self.item_tog_browser = rumps.MenuItem("🌐  Open browser",   callback=self._toggle_browser)
        self.item_tog_app     = rumps.MenuItem("🖥  Open app",       callback=self._toggle_app)
        self.item_tog_folder  = rumps.MenuItem("📁  Open folder",    callback=self._toggle_folder)
        self.item_tog_music   = rumps.MenuItem("♪   Play music",     callback=self._toggle_music)
        self._sync_toggle_states()

        # Settings submenu
        cfg_menu = rumps.MenuItem("⚙  Settings")
        cfg_menu.add(rumps.MenuItem("  — Edit settings —"))
        cfg_menu["  — Edit settings —"].set_callback(None)
        cfg_menu.add(rumps.MenuItem("🌐  Browser URL",          callback=self._cfg_browser))
        cfg_menu.add(rumps.MenuItem("🖥  System app",           callback=self._cfg_app))
        cfg_menu.add(rumps.MenuItem("📁  Folder to open",       callback=self._cfg_folder))
        cfg_menu.add(rumps.MenuItem("♪   Music file",           callback=self._cfg_music))
        cfg_menu.add(None)
        cfg_menu.add(rumps.MenuItem("  — Enable / Disable —"))
        cfg_menu["  — Enable / Disable —"].set_callback(None)
        cfg_menu.add(self.item_tog_browser)
        cfg_menu.add(self.item_tog_app)
        cfg_menu.add(self.item_tog_folder)
        cfg_menu.add(self.item_tog_music)
        cfg_menu.add(None)
        cfg_menu.add(rumps.MenuItem("↩  Reset to defaults",    callback=self._cfg_reset))

        self.item_apps_summary = rumps.MenuItem(self._apps_summary())
        self.item_apps_summary.set_callback(None)

        self.item_mute = rumps.MenuItem("🔇  Mute",  callback=self.toggle_mute)
        self.item_quit = rumps.MenuItem("⏻  Quit",   callback=self.quit_app)

        self.menu = [
            self.item_header,
            None,
            self.item_status,
            self.item_stop,
            self.item_level,
            None,
            self.item_threshold_label,
            self.item_slider,
            None,
            cfg_menu,
            self.item_apps_summary,
            None,
            self.item_mute,
            None,
            self.item_quit,
        ]

    # ────────────────────────────────────────────────────────────────────
    #  TEXT HELPERS
    # ────────────────────────────────────────────────────────────────────

    def _threshold_text(self) -> str:
        return f"  Threshold  ────────────────  {self.threshold:.2f}"

    def _apps_summary(self) -> str:
        url    = self.cfg["browser_url"]
        app    = self.cfg["system_app"]
        folder = os.path.basename(self.cfg["folder_path"]) or self.cfg["folder_path"]
        flags  = "".join([
            "🌐" if self.cfg["enable_browser"] else "✕",
            " 🖥" if self.cfg["enable_app"]    else " ✕",
            " 📁" if self.cfg["enable_folder"] else " ✕",
            " ♪"  if self.cfg["enable_music"]  else " ✕",
        ])
        return f"     {flags}  enabled\n     {url[:28]}{'…' if len(url) > 28 else ''}  ·  {app}  ·  {folder}"

    def _sync_toggle_states(self):
        """Sync checkmarks with current config values."""
        self.item_tog_browser.state = int(self.cfg["enable_browser"])
        self.item_tog_app.state     = int(self.cfg["enable_app"])
        self.item_tog_folder.state  = int(self.cfg["enable_folder"])
        self.item_tog_music.state   = int(self.cfg["enable_music"])

    # ────────────────────────────────────────────────────────────────────
    #  TIMER UI  — live VU-meter at 10 fps
    # ────────────────────────────────────────────────────────────────────

    def _refresh_ui(self, _):
        if self.muted:
            return

        rms      = self.current_rms
        ratio    = min(rms / (self.threshold * 2), 1.0)
        vu_index = int(ratio * (len(VU_CHARS) - 1))

        if not self._triggered:
            self.title = f"⚡{VU_CHARS[vu_index]}"

        filled = int(ratio * 20)
        bar    = "▓" * filled + "░" * (20 - filled)
        dot    = "🔴" if rms >= self.threshold else "🟢"
        self.item_level.title = f"  Level  {bar}  {rms:.4f} {dot}"

    # ────────────────────────────────────────────────────────────────────
    #  THRESHOLD SLIDER
    # ────────────────────────────────────────────────────────────────────

    def _on_threshold_slide(self, sender):
        self.threshold = round(float(sender.value), 2)
        self.item_threshold_label.title = self._threshold_text()
        self.cfg["threshold"] = self.threshold
        save_config(self.cfg)

    # ────────────────────────────────────────────────────────────────────
    #  FEATURE TOGGLES
    # ────────────────────────────────────────────────────────────────────

    def _toggle_browser(self, sender):
        self.cfg["enable_browser"] = not self.cfg["enable_browser"]
        sender.state = int(self.cfg["enable_browser"])
        self._save_and_refresh()

    def _toggle_app(self, sender):
        self.cfg["enable_app"] = not self.cfg["enable_app"]
        sender.state = int(self.cfg["enable_app"])
        self._save_and_refresh()

    def _toggle_folder(self, sender):
        self.cfg["enable_folder"] = not self.cfg["enable_folder"]
        sender.state = int(self.cfg["enable_folder"])
        self._save_and_refresh()

    def _toggle_music(self, sender):
        self.cfg["enable_music"] = not self.cfg["enable_music"]
        sender.state = int(self.cfg["enable_music"])
        self._save_and_refresh()

    # ────────────────────────────────────────────────────────────────────
    #  SETTINGS DIALOGS
    # ────────────────────────────────────────────────────────────────────

    def _cfg_browser(self, _):
        r = rumps.Window(
            message="URL to open in the browser:",
            title="🌐  Browser URL",
            default_text=self.cfg["browser_url"],
            ok="Save", cancel="Cancel", dimensions=(400, 24),
        ).run()
        if r.clicked and r.text.strip():
            self.cfg["browser_url"] = r.text.strip()
            self._save_and_refresh()

    def _cfg_app(self, _):
        r = rumps.Window(
            message="App name as it appears in /Applications:\nExamples: Terminal  Safari  Spotify  Notes  iTerm",
            title="🖥  System app",
            default_text=self.cfg["system_app"],
            ok="Save", cancel="Cancel", dimensions=(400, 24),
        ).run()
        if r.clicked and r.text.strip():
            self.cfg["system_app"] = r.text.strip()
            self._save_and_refresh()

    def _cfg_folder(self, _):
        r = rumps.Window(
            message="Full path to the folder to open (~ is supported):",
            title="📁  Folder to open",
            default_text=self.cfg["folder_path"],
            ok="Save", cancel="Cancel", dimensions=(400, 24),
        ).run()
        if r.clicked and r.text.strip():
            self.cfg["folder_path"] = os.path.expanduser(r.text.strip())
            self._save_and_refresh()

    def _cfg_music(self, _):
        r = rumps.Window(
            message="Full path to the MP3 file.\nIf it is in the same folder as the script, just the filename is enough.",
            title="♪  Music file",
            default_text=self.cfg["music_file"],
            ok="Save", cancel="Cancel", dimensions=(400, 24),
        ).run()
        if r.clicked and r.text.strip():
            path = r.text.strip()
            if not os.path.isabs(path):
                path = os.path.join(SCRIPT_DIR, path)
            self.cfg["music_file"] = path
            self._save_and_refresh()

    def _cfg_reset(self, _):
        r = rumps.Window(
            message="Reset all settings to their default values?",
            title="↩  Reset to defaults",
            ok="Yes, reset", cancel="Cancel", dimensions=(1, 1),
        ).run()
        if r.clicked:
            self.cfg       = dict(DEFAULTS)
            self.threshold = float(self.cfg["threshold"])
            self.item_threshold_label.title = self._threshold_text()
            self.item_slider.value = self.threshold
            self._sync_toggle_states()
            self._save_and_refresh()

    def _save_and_refresh(self):
        save_config(self.cfg)
        self.item_apps_summary.title = self._apps_summary()

    # ────────────────────────────────────────────────────────────────────
    #  STOP STARK MODE
    # ────────────────────────────────────────────────────────────────────

    def _stop_stark(self, _):
        pygame.mixer.music.stop()
        self._stop_event.set()   # unblocks the sleep inside _stark_mode
        self.last_trigger = 0    # allow immediate re-trigger

    # ────────────────────────────────────────────────────────────────────
    #  MUTE / QUIT
    # ────────────────────────────────────────────────────────────────────

    def toggle_mute(self, sender):
        self.muted = not self.muted
        if self.muted:
            self.title             = "🔇"
            sender.title           = "🎙  Unmute"
            self.item_status.title = "○ Muted"
            self.item_level.title  = "  Level  ────────────────────────  —"
        else:
            sender.title           = "🔇  Mute"
            self.item_status.title = "● Listening..."

    def quit_app(self, _):
        rumps.quit_application()

    # ────────────────────────────────────────────────────────────────────
    #  AUDIO LOOP
    # ────────────────────────────────────────────────────────────────────

    def _audio_loop(self):
        def callback(indata, frames, time_info, status):
            if self.muted:
                self.current_rms = 0.0
                return

            rms = float(np.sqrt(np.mean(indata ** 2)))
            self.current_rms = rms

            now = time.time()
            if now - self.last_trigger < COOLDOWN:
                self.trigger_count = 0
                return

            self.trigger_count = self.trigger_count + 1 if rms > self.threshold else 0

            if self.trigger_count >= CONFIRM_FRAMES:
                self.trigger_count = 0
                self.last_trigger  = now
                threading.Thread(target=self._stark_mode, daemon=True).start()

        with sd.InputStream(
            samplerate=SAMPLE_RATE, blocksize=BLOCK_SIZE,
            channels=1, dtype="float32", callback=callback,
        ):
            while True:
                time.sleep(0.1)

    # ────────────────────────────────────────────────────────────────────
    #  STARK MODE
    # ────────────────────────────────────────────────────────────────────

    def _stark_mode(self):
        self._triggered = True
        self._stop_event.clear()

        self.title             = "✦"
        self.item_status.title = "✦  ACCESS GRANTED — Welcome, Sir."
        self.item_stop.hidden  = False

        if self.cfg["enable_music"]:   self._play_music()
        if self.cfg["enable_browser"]: webbrowser.open(self.cfg["browser_url"])
        if self.cfg["enable_app"]:     self._open_system_app()
        if self.cfg["enable_folder"]:  self._open_folder()

        # Wait 3 s or until the user clicks Stop
        self._stop_event.wait(timeout=3)

        self.item_stop.hidden  = True
        self._triggered        = False
        if not self.muted:
            self.item_status.title = "● Listening..."

    # ────────────────────────────────────────────────────────────────────
    #  ACTIONS
    # ────────────────────────────────────────────────────────────────────

    def _play_music(self):
        path = self.cfg["music_file"]
        if not os.path.exists(path):
            return
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
        except Exception:
            pass

    def _open_system_app(self):
        app = self.cfg["system_app"]
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", "-a", app])
            elif sys.platform.startswith("linux"):
                subprocess.Popen([app.lower()])
            elif sys.platform == "win32":
                subprocess.Popen([app])
        except Exception:
            pass

    def _open_folder(self):
        path = self.cfg["folder_path"]
        if not os.path.exists(path):
            return
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", path])
            elif sys.platform.startswith("linux"):
                subprocess.Popen(["xdg-open", path])
            elif sys.platform == "win32":
                subprocess.Popen(["explorer", path])
        except Exception:
            pass


if __name__ == "__main__":
    StarkApp().run()
