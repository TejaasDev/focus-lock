"""
Focus Lock — Configuration Module
Centralizes all app constants, version info, and path resolution.
"""

import os
import sys

# ─── App Metadata ────────────────────────────────────────────────────────────
APP_NAME = "Focus Lock"
APP_ID = "com.focuslock.app"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "A lightweight desktop application that helps you stay focused by blocking distracting applications."
APP_AUTHOR = "Tejaas"
APP_WEBSITE = "https://github.com/TejaasDev/focus-lock"

# ─── Path Resolution (works for both dev and PyInstaller frozen builds) ──────
def get_base_path():
    """Return the base path for the application.
    When running as a PyInstaller bundle, sys._MEIPASS points to the temp folder.
    Otherwise, use the directory containing this file.
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def get_data_dir():
    """Return the user data directory for storing settings.
    Uses XDG_DATA_HOME (~/.local/share/focus-lock) on Linux.
    Falls back to the app directory in development mode.
    """
    if getattr(sys, 'frozen', False):
        # Production: use XDG standard paths
        xdg_data = os.environ.get('XDG_DATA_HOME', os.path.expanduser('~/.local/share'))
        data_dir = os.path.join(xdg_data, 'focus-lock')
        os.makedirs(data_dir, exist_ok=True)
        return data_dir
    else:
        # Development: use the project directory
        return get_base_path()


BASE_PATH = get_base_path()
DATA_DIR = get_data_dir()

# ─── File Paths ──────────────────────────────────────────────────────────────
SETTINGS_FILE = os.path.join(DATA_DIR, 'focus_lock_settings.json')
ICON_PATH = os.path.join(BASE_PATH, 'icon.png')

# ─── Default Settings ────────────────────────────────────────────────────────
DEFAULT_BLACKLIST = [
    "chrome", "firefox", "brave", "opera", "vivaldi", "chromium",
    "edge", "instagram", "twitter", "telegram", "discord", "whatsapp",
    "slack", "spotify"
]

# ─── UI Constants ────────────────────────────────────────────────────────────
WINDOW_MIN_WIDTH = 600
WINDOW_MIN_HEIGHT = 700
MONITOR_INTERVAL_SEC = 3

# ─── Logging ─────────────────────────────────────────────────────────────────
import logging

LOG_LEVEL = logging.WARNING  # Production: only warnings and errors
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

def setup_logging():
    """Configure application-wide logging."""
    logging.basicConfig(
        level=LOG_LEVEL,
        format=LOG_FORMAT,
    )
    return logging.getLogger(APP_NAME)

logger = setup_logging()
