"""
STARK MODE - Sistema de Activación por Sonido
==============================================

INSTALACIÓN DE DEPENDENCIAS:
-----------------------------
Ejecuta estos comandos en tu terminal antes de correr el script:

    pip install sounddevice numpy pygame

Si sounddevice falla al detectar el micrófono en macOS, también instala:
    pip install PyAudio
    (requiere: brew install portaudio)

ESTRUCTURA DE ARCHIVOS ESPERADA:
---------------------------------
tony-stark/
├── stark_mode.py       ← este script
└── jarvis.mp3          ← tu MP3 preferido (renómbralo así o cambia MUSIC_FILE)

AJUSTE DE SENSIBILIDAD:
------------------------
- THRESHOLD: Valor entre 0.01 y 1.0.
  * 0.01–0.03  → muy sensible (se activa con voz normal o ruido ambiente)
  * 0.05–0.10  → sensible (aplauso moderado o voz alta)
  * 0.15–0.30  → poco sensible (aplauso fuerte o golpe en la mesa)
  Empieza en 0.08 y ajusta según tu micrófono.

- CONFIRM_FRAMES: Cuántas muestras consecutivas deben superar el umbral
  antes de activar. Aumenta para evitar falsos positivos.
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
#  CONFIGURACIÓN — edita estos valores
# ─────────────────────────────────────────────

# Sensibilidad del micrófono (0.01 = muy sensible, 0.30 = poco sensible)
THRESHOLD = 0.08

# Cuántas muestras consecutivas por encima del umbral se necesitan
# para confirmar la activación (evita falsos positivos por ruido puntual)
CONFIRM_FRAMES = 3

# Tasa de muestreo del micrófono (Hz) — 44100 es estándar
SAMPLE_RATE = 44100

# Tamaño del bloque de audio que se analiza en cada ciclo
BLOCK_SIZE = 1024

# Archivo MP3 a reproducir (debe estar en la misma carpeta que este script)
MUSIC_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jarvis.mp3")

# URL que se abrirá en el navegador (tu correo o Claude)
BROWSER_URL = "https://claude.ai"

# Ruta de la carpeta que se abrirá en Finder/Explorer
TARGET_FOLDER = os.path.expanduser("~/Documents")

# Tiempo de espera (segundos) antes de volver a escuchar tras una activación
COOLDOWN = 10

# ─────────────────────────────────────────────
#  PALETA DE COLORES ANSI para la consola
# ─────────────────────────────────────────────

RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"


def banner():
    """Imprime el banner de inicio al estilo Stark Industries."""
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
{YELLOW}              Sistema de Activación por Sonido — Nivel de acceso: MÁXIMO{RESET}
""")


def print_config():
    """Muestra la configuración activa."""
    print(f"{CYAN}{'─'*60}{RESET}")
    print(f"{BOLD}  CONFIGURACIÓN ACTIVA:{RESET}")
    print(f"  Umbral de detección : {YELLOW}{THRESHOLD}{RESET}")
    print(f"  Frames de confirmación: {YELLOW}{CONFIRM_FRAMES}{RESET}")
    print(f"  URL navegador       : {YELLOW}{BROWSER_URL}{RESET}")
    print(f"  Carpeta objetivo    : {YELLOW}{TARGET_FOLDER}{RESET}")
    music_status = f"{GREEN}✓ encontrado{RESET}" if os.path.exists(MUSIC_FILE) else f"{RED}✗ no encontrado ({MUSIC_FILE}){RESET}"
    print(f"  Archivo de música   : {music_status}")
    print(f"{CYAN}{'─'*60}{RESET}\n")


def init_audio():
    """Inicializa pygame para reproducción de audio."""
    pygame.mixer.init()


def play_music():
    """Reproduce el MP3 si existe; muestra advertencia si no."""
    if not os.path.exists(MUSIC_FILE):
        print(f"  {YELLOW}⚠  Música no encontrada: {MUSIC_FILE}{RESET}")
        print(f"  {YELLOW}   Coloca un MP3 llamado 'jarvis.mp3' junto al script.{RESET}")
        return
    try:
        pygame.mixer.music.load(MUSIC_FILE)
        pygame.mixer.music.play()
        print(f"  {GREEN}♪  Reproduciendo: {os.path.basename(MUSIC_FILE)}{RESET}")
    except Exception as e:
        print(f"  {RED}Error al reproducir música: {e}{RESET}")


def open_browser():
    """Abre la URL configurada en el navegador por defecto."""
    try:
        webbrowser.open(BROWSER_URL)
        print(f"  {GREEN}✓  Navegador abierto → {BROWSER_URL}{RESET}")
    except Exception as e:
        print(f"  {RED}Error abriendo navegador: {e}{RESET}")


def open_terminal_or_calculator():
    """
    Abre la calculadora del sistema o el terminal según el OS.
    En macOS abre Calculator.app; en Linux, abre gnome-calculator o xterm.
    """
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-a", "Calculator"])
            print(f"  {GREEN}✓  Calculadora abierta (macOS){RESET}")
        elif sys.platform.startswith("linux"):
            # Intenta gnome-calculator; si falla, abre xterm
            try:
                subprocess.Popen(["gnome-calculator"])
            except FileNotFoundError:
                subprocess.Popen(["xterm"])
            print(f"  {GREEN}✓  Calculadora/Terminal abierto (Linux){RESET}")
        elif sys.platform == "win32":
            subprocess.Popen(["calc.exe"])
            print(f"  {GREEN}✓  Calculadora abierta (Windows){RESET}")
    except Exception as e:
        print(f"  {RED}Error abriendo calculadora: {e}{RESET}")


def open_folder():
    """Abre la carpeta configurada en el explorador de archivos del sistema."""
    try:
        if not os.path.exists(TARGET_FOLDER):
            print(f"  {YELLOW}⚠  Carpeta no encontrada: {TARGET_FOLDER}{RESET}")
            return

        if sys.platform == "darwin":
            subprocess.Popen(["open", TARGET_FOLDER])
        elif sys.platform.startswith("linux"):
            subprocess.Popen(["xdg-open", TARGET_FOLDER])
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", TARGET_FOLDER])

        print(f"  {GREEN}✓  Carpeta abierta → {TARGET_FOLDER}{RESET}")
    except Exception as e:
        print(f"  {RED}Error abriendo carpeta: {e}{RESET}")


def stark_mode():
    """
    Función principal que se ejecuta cuando se detecta el aplauso.
    Lanza todas las acciones en paralelo (el OS las gestiona de forma asíncrona).
    """
    print(f"\n{GREEN}{BOLD}{'═'*60}{RESET}")
    print(f"{GREEN}{BOLD}  ✦  ACCESO CONCEDIDO. BIENVENIDO, SEÑOR.{RESET}")
    print(f"{GREEN}{BOLD}{'═'*60}{RESET}\n")
    print(f"{CYAN}  Iniciando secuencia STARK MODE...{RESET}\n")

    play_music()
    open_browser()
    open_terminal_or_calculator()
    open_folder()

    print(f"\n{CYAN}  Secuencia completa. Entrando en modo reposo ({COOLDOWN}s)...{RESET}")


def monitor_microphone():
    """
    Bucle principal: escucha el micrófono en tiempo real con sounddevice.
    Cuando el RMS del bloque supera el THRESHOLD durante CONFIRM_FRAMES
    muestras consecutivas, dispara stark_mode().
    """
    print(f"{CYAN}  Iniciando monitorización de micrófono...{RESET}")
    print(f"\n{YELLOW}{'─'*60}{RESET}")
    print(f"{BOLD}  >> Esperando comando de voz...{RESET}")
    print(f"{YELLOW}  (Aplaude o da un golpe fuerte para activar){RESET}")
    print(f"{YELLOW}  (Presiona Ctrl+C para salir){RESET}")
    print(f"{YELLOW}{'─'*60}{RESET}\n")

    # Contador de frames consecutivos que superan el umbral
    trigger_count = 0
    # Tiempo de la última activación (para el cooldown)
    last_trigger = 0

    def audio_callback(indata, frames, time_info, status):
        """
        Callback invocado por sounddevice en cada bloque de audio capturado.
        Se ejecuta en un hilo separado — sólo modifica variables compartidas.
        """
        nonlocal trigger_count, last_trigger

        # Calcula el RMS (Root Mean Square) del bloque — medida de volumen
        rms = float(np.sqrt(np.mean(indata ** 2)))

        # Visualizador de nivel en tiempo real (barra proporcional al volumen)
        bar_len = int(rms * 300)
        bar = "█" * min(bar_len, 50)
        color = GREEN if rms < THRESHOLD else RED
        print(f"\r  Nivel: {color}{bar:<50}{RESET}  RMS: {rms:.4f}", end="", flush=True)

        now = time.time()

        # Ignora activaciones durante el período de cooldown
        if now - last_trigger < COOLDOWN:
            trigger_count = 0
            return

        if rms > THRESHOLD:
            trigger_count += 1
        else:
            trigger_count = 0  # Resetea si hay silencio entre muestras

        if trigger_count >= CONFIRM_FRAMES:
            trigger_count = 0
            last_trigger = now
            print()  # Salto de línea para separar el log del nivel
            stark_mode()
            # Reactiva el mensaje de espera
            print(f"\n{YELLOW}{'─'*60}{RESET}")
            print(f"{BOLD}  >> Esperando comando de voz...{RESET}")
            print(f"{YELLOW}{'─'*60}{RESET}\n")

    # Abre el stream del micrófono (mono, callback asíncrono)
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
            print(f"\n\n{RED}  Sistema STARK MODE desactivado. Hasta pronto, Señor.{RESET}\n")


# ─────────────────────────────────────────────
#  PUNTO DE ENTRADA
# ─────────────────────────────────────────────

if __name__ == "__main__":
    banner()
    print_config()
    init_audio()
    monitor_microphone()
