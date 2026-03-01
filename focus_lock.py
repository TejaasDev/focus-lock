#!/usr/bin/env python3
"""
Focus Lock — Desktop Productivity Application
Blocks distracting applications to help you stay focused.

Version: See config.APP_VERSION
"""

import sys
import os
import json
import time
import subprocess
import threading
import signal
import psutil
from datetime import datetime, timedelta

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QPushButton, QLineEdit, QListWidget,
                             QFileDialog, QMessageBox, QTabWidget, QTextEdit,
                             QSizePolicy, QInputDialog, QListWidgetItem, QAbstractItemView)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer, QSize
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon

from config import (
    APP_NAME, APP_VERSION, APP_ID,
    SETTINGS_FILE, ICON_PATH, BASE_PATH, DATA_DIR,
    DEFAULT_BLACKLIST, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    MONITOR_INTERVAL_SEC, logger
)


# ═══════════════════════════════════════════════════════════════════════════════
# Focus Manager — Core Logic
# ═══════════════════════════════════════════════════════════════════════════════

class FocusManager(QObject):
    """Manages focus mode: monitoring, killing blacklisted apps, and tracking time."""

    update_timer_signal = pyqtSignal(str)
    block_notification_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active = False
        self.lock_thread = None
        self.start_time = None
        self.settings = self._load_settings()
        self.allowed_processes = []

    # ── Settings I/O ─────────────────────────────────────────────────────────

    def _load_settings(self):
        """Load settings from disk, resetting daily counters if needed."""
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    data = json.load(f)

                # Reset daily timer on new day
                current_date = datetime.now().strftime("%Y-%m-%d")
                if data.get("last_date", "") != current_date:
                    data["time_focused_today_sec"] = 0
                    data["last_date"] = current_date
                    self._save_settings(data)

                return data
            except (json.JSONDecodeError, IOError, OSError) as e:
                logger.error("Failed to load settings: %s", e)

        # Return defaults if file missing or corrupt
        default_settings = {
            "youtube_url": "",
            "allowed_items": [],
            "blacklist": list(DEFAULT_BLACKLIST),
            "time_focused_today_sec": 0,
            "last_date": datetime.now().strftime("%Y-%m-%d")
        }
        self._save_settings(default_settings)
        return default_settings

    def _save_settings(self, data=None):
        """Persist settings to disk."""
        if data is None:
            data = self.settings
        try:
            os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(data, f, indent=4)
        except (IOError, OSError) as e:
            logger.error("Failed to save settings: %s", e)

    def save_settings(self):
        """Public API for saving current settings."""
        self._save_settings()

    # ── Browser & Resource Launching ─────────────────────────────────────────

    def launch_isolated_browser(self, url):
        """Launch a URL in an isolated browser profile (won't be killed)."""
        logger.info("Launching allowed browser for: %s", url)

        chrome_paths = [
            'google-chrome', 'chromium-browser', 'chromium',
            'brave-browser', 'microsoft-edge'
        ]

        for browser in chrome_paths:
            try:
                if subprocess.call(
                    ['which', browser],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                ) == 0:
                    profile_dir = '/tmp/focus_lock_chrome_profile'
                    os.makedirs(profile_dir, exist_ok=True)
                    proc = subprocess.Popen(
                        [browser, f'--app={url}', f'--user-data-dir={profile_dir}'],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    self.allowed_processes.append(proc)
                    return True
            except OSError:
                continue

        # Try Firefox
        try:
            if subprocess.call(
                ['which', 'firefox'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            ) == 0:
                profile_dir = '/tmp/focus_lock_ff_profile'
                os.makedirs(profile_dir, exist_ok=True)
                proc = subprocess.Popen(
                    ['firefox', '--no-remote', '--profile', profile_dir, url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
                self.allowed_processes.append(proc)
                return True
        except OSError:
            pass

        # Fallback to xdg-open
        try:
            proc = subprocess.Popen(
                ['xdg-open', url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self.allowed_processes.append(proc)
            return True
        except OSError as e:
            logger.error("Failed to open URL %s: %s", url, e)
            return False

    def launch_item(self, path):
        """Launch an allowed app, file, or folder."""
        if not os.path.exists(path):
            logger.warning("Path not found: %s", path)
            return False

        try:
            if os.path.isdir(path) or (os.path.isfile(path) and not os.access(path, os.X_OK)):
                proc = subprocess.Popen(
                    ['xdg-open', path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            else:
                proc = subprocess.Popen(
                    [path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            self.allowed_processes.append(proc)
            return True
        except OSError as e:
            logger.error("Failed to launch %s: %s", path, e)
            return False

    # ── Focus Mode Control ───────────────────────────────────────────────────

    def start_focus_mode(self):
        """Activate focus mode: begin monitoring and killing blacklisted apps."""
        self.active = True
        self.start_time = time.time()
        self.allowed_processes = []

        # Initial kill pass
        self._kill_blacklisted()

        self.lock_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.lock_thread.start()

    def stop_focus_mode(self):
        """Deactivate focus mode and save session time."""
        self.active = False
        if self.lock_thread:
            self.lock_thread.join(timeout=2.0)

        # Accumulate session time
        if self.start_time:
            session_duration = int(time.time() - self.start_time)
            self.settings["time_focused_today_sec"] = (
                self.settings.get("time_focused_today_sec", 0) + session_duration
            )
            self._save_settings()
            self.start_time = None

    def _monitor_loop(self):
        """Background thread: periodically update timer and kill distractions."""
        while self.active:
            try:
                session_duration = int(time.time() - self.start_time)
                total_sec = self.settings.get("time_focused_today_sec", 0) + session_duration
                formatted_time = str(timedelta(seconds=total_sec))
                self.update_timer_signal.emit(formatted_time)
                self._kill_blacklisted()
            except Exception as e:
                logger.error("Monitor loop error: %s", e)

            time.sleep(MONITOR_INTERVAL_SEC)

    def _kill_blacklisted(self):
        """Scan running processes and kill any that match the blacklist."""
        blacklist = [b.lower() for b in self.settings.get("blacklist", [])]

        # Build set of exempt PIDs from allowed processes
        exempt_pids = set()
        active_procs = []
        for proc in self.allowed_processes:
            if proc.poll() is None:  # Still running
                active_procs.append(proc)
                try:
                    exempt_pids.add(proc.pid)
                    parent = psutil.Process(proc.pid)
                    for child in parent.children(recursive=True):
                        exempt_pids.add(child.pid)
                except psutil.NoSuchProcess:
                    pass
        self.allowed_processes = active_procs

        # Scan all processes
        try:
            for p in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if p.info['pid'] in exempt_pids:
                        continue

                    p_name = (p.info.get('name') or '').lower()
                    cmdline = p.info.get('cmdline') or []
                    cmd_str = " ".join(cmdline).lower() if cmdline else ""

                    should_kill = False
                    for b in blacklist:
                        if b in p_name:
                            should_kill = True
                            break
                        if b in cmd_str and any(
                            exe in cmd_str for exe in ['/opt/', '/usr/bin/', '/snap/']
                        ):
                            should_kill = True
                            break

                    if should_kill:
                        os.kill(p.info['pid'], signal.SIGKILL)
                        logger.info("Distraction blocked: %s (PID: %d)", p_name, p.info['pid'])
                        self.block_notification_signal.emit(p_name)

                except (psutil.NoSuchProcess, psutil.AccessDenied,
                        ProcessLookupError, PermissionError):
                    continue
        except Exception as e:
            logger.error("Process scan error: %s", e)


# ═══════════════════════════════════════════════════════════════════════════════
# Main Window — UI
# ═══════════════════════════════════════════════════════════════════════════════

class MainWindow(QMainWindow):
    """Primary application window for Focus Lock."""

    def __init__(self):
        super().__init__()
        self.manager = FocusManager()
        self.manager.update_timer_signal.connect(self._update_timer_ui)
        self.manager.block_notification_signal.connect(self._show_notification)

        self._init_ui()
        self._apply_dark_theme()

    # ── UI Setup ─────────────────────────────────────────────────────────────

    def _init_ui(self):
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)

        # Set window icon
        if os.path.exists(ICON_PATH):
            self.setWindowIcon(QIcon(ICON_PATH))

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)

        # Title
        title = QLabel(APP_NAME)
        title.setFont(QFont("Arial", 28, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(title)

        # Version subtitle
        version_label = QLabel(f"v{APP_VERSION}")
        version_label.setFont(QFont("Arial", 10))
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("color: #888888;")
        self.main_layout.addWidget(version_label)

        # Today's focus time
        self.time_label = QLabel("Time Focused Today: 00:00:00")
        self.time_label.setFont(QFont("Arial", 14))
        self.time_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.time_label)

        # Tab Widget
        self.tabs = QTabWidget()
        self.tabs.setFont(QFont("Arial", 12))

        self._setup_allowed_tab()
        self._setup_blacklist_tab()

        self.main_layout.addWidget(self.tabs)

        # Focus Mode Button
        self.focus_btn = QPushButton("Start Focus Mode")
        self.focus_btn.setFont(QFont("Arial", 16, QFont.Bold))
        self.focus_btn.setMinimumHeight(60)
        self.focus_btn.setStyleSheet("""
            QPushButton {
                background-color: #2e7d32;
                color: white;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #1b5e20;
            }
        """)
        self.focus_btn.clicked.connect(self._toggle_focus_mode)
        self.main_layout.addWidget(self.focus_btn)

        # Initialize timer display
        self._update_timer_ui("0:00:00")

    def _setup_allowed_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # YouTube Section
        yt_label = QLabel("Add YouTube Channel:")
        yt_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(yt_label)

        yt_layout = QHBoxLayout()
        self.yt_input = QLineEdit()
        self.yt_input.setPlaceholderText("https://www.youtube.com/@Channel")
        yt_layout.addWidget(self.yt_input)

        self.yt_add_btn = QPushButton("Add Channel")
        self.yt_add_btn.clicked.connect(self._add_youtube_channel)
        yt_layout.addWidget(self.yt_add_btn)
        layout.addLayout(yt_layout)

        # Resources Section
        res_label = QLabel("Allowed Applications & Files:")
        res_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(res_label)

        btn_layout = QHBoxLayout()
        btn_app = QPushButton("Add Application")
        btn_app.clicked.connect(self._add_app)
        btn_file = QPushButton("Add File / Book")
        btn_file.clicked.connect(self._add_file)
        btn_folder = QPushButton("Add Folder")
        btn_folder.clicked.connect(self._add_folder)

        btn_layout.addWidget(btn_app)
        btn_layout.addWidget(btn_file)
        btn_layout.addWidget(btn_folder)
        layout.addLayout(btn_layout)

        self.res_list = QListWidget()
        self.res_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.res_list.doubleClicked.connect(self._open_selected_resource)
        self._refresh_resources_list()
        layout.addWidget(self.res_list)

        # Action buttons
        action_layout = QHBoxLayout()
        btn_remove = QPushButton("Remove Selected")
        btn_remove.clicked.connect(self._remove_resource)
        btn_open = QPushButton("Open Selected")
        btn_open.clicked.connect(self._open_selected_resource)

        action_layout.addWidget(btn_open)
        action_layout.addWidget(btn_remove)
        layout.addLayout(action_layout)

        self.tabs.addTab(tab, "Allowed Resources")

    def _setup_blacklist_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        lbl = QLabel("Distracting Apps (Blacklist):")
        lbl.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(lbl)

        self.edit_blacklist = QTextEdit()
        bl = self.manager.settings.get("blacklist", [])
        self.edit_blacklist.setText("\n".join(bl))
        layout.addWidget(self.edit_blacklist)

        btn_save = QPushButton("Save Blacklist")
        btn_save.clicked.connect(self._save_blacklist)
        layout.addWidget(btn_save)

        lbl_info = QLabel(
            "Add one application name per line (e.g., chrome, firefox, instagram)."
        )
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet("color: #aaaaaa;")
        layout.addWidget(lbl_info)

        self.tabs.addTab(tab, "Blacklist")

    # ── Resource Management ──────────────────────────────────────────────────

    def _add_youtube_channel(self):
        url = self.yt_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a YouTube URL.")
            return
        name = url.split('/')[-1] if '/' in url else url
        self._add_resource("yt", url, name)
        self.yt_input.clear()

    def _add_app(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Application Executable", "/usr/bin"
        )
        if path:
            self._add_resource("app", path, os.path.basename(path))

    def _add_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select File / Book", os.path.expanduser("~")
        )
        if path:
            self._add_resource("file", path, os.path.basename(path))

    def _add_folder(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Folder", os.path.expanduser("~")
        )
        if path:
            self._add_resource("folder", path, os.path.basename(path))

    def _add_resource(self, rtype, path, name):
        items = self.manager.settings.get("allowed_items", [])
        if any(item['path'] == path for item in items):
            return
        items.append({"type": rtype, "path": path, "name": name})
        self.manager.settings["allowed_items"] = items
        self.manager.save_settings()
        self._refresh_resources_list()

    def _remove_resource(self):
        selected = self.res_list.currentRow()
        if selected < 0:
            return
        items = self.manager.settings.get("allowed_items", [])
        if 0 <= selected < len(items):
            del items[selected]
            self.manager.settings["allowed_items"] = items
            self.manager.save_settings()
            self._refresh_resources_list()

    def _open_selected_resource(self):
        selected = self.res_list.currentRow()
        if selected < 0:
            return
        items = self.manager.settings.get("allowed_items", [])
        if 0 <= selected < len(items):
            item = items[selected]
            if item.get("type") == "yt":
                self.manager.launch_isolated_browser(item["path"])
            else:
                if not self.manager.launch_item(item["path"]):
                    QMessageBox.warning(
                        self, "Not Found",
                        f"Could not open: {item['path']}"
                    )

    def _refresh_resources_list(self):
        self.res_list.clear()
        items = self.manager.settings.get("allowed_items", [])
        for item in items:
            t = item.get('type', 'Unknown').upper()
            n = item.get('name', 'Unknown')
            p = item.get('path', '')
            self.res_list.addItem(f"[{t}] {n}  ({p})")

    def _save_blacklist(self):
        text = self.edit_blacklist.toPlainText()
        bl = [line.strip() for line in text.split('\n') if line.strip()]
        self.manager.settings["blacklist"] = bl
        self.manager.save_settings()
        QMessageBox.information(self, "Saved", "Blacklist updated successfully.")

    # ── Focus Mode Toggle ────────────────────────────────────────────────────

    def _toggle_focus_mode(self):
        if not self.manager.active:
            # Start Focus Mode
            self.manager.start_focus_mode()
            self.focus_btn.setText("Exit Focus Mode")
            self.focus_btn.setStyleSheet("""
                QPushButton {
                    background-color: #d32f2f;
                    color: white;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #b71c1c;
                }
            """)
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
            self.setWindowFlag(Qt.WindowCloseButtonHint, False)
            self.show()
            QMessageBox.information(
                self, "Focus Mode Started",
                "Distracting applications will be continuously closed!"
            )
        else:
            # Exit Focus Mode
            reply = QMessageBox.question(
                self, 'Confirm Exit',
                'Are you sure you want to exit Focus Lock?',
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                self.manager.stop_focus_mode()
                self.focus_btn.setText("Start Focus Mode")
                self.focus_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #2e7d32;
                        color: white;
                        border-radius: 8px;
                    }
                    QPushButton:hover {
                        background-color: #1b5e20;
                    }
                """)
                self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
                self.setWindowFlag(Qt.WindowCloseButtonHint, True)
                self.show()

    # ── Timer & Notifications ────────────────────────────────────────────────

    def _update_timer_ui(self, time_str):
        if time_str == "0:00:00":
            total_sec = self.manager.settings.get("time_focused_today_sec", 0)
            time_str = str(timedelta(seconds=total_sec))
        self.time_label.setText(f"Time Focused Today: {time_str}")

    def _show_notification(self, app_name):
        """Send a desktop notification when a distraction is blocked."""
        try:
            subprocess.call(
                ['notify-send', '-u', 'low', '-i', ICON_PATH,
                 APP_NAME, f'Distraction Blocked: {app_name}'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except (OSError, FileNotFoundError):
            pass  # notify-send may not be installed

    # ── Theme ────────────────────────────────────────────────────────────────

    def _apply_dark_theme(self):
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(30, 30, 30))
        palette.setColor(QPalette.WindowText, Qt.white)
        palette.setColor(QPalette.Base, QColor(45, 45, 45))
        palette.setColor(QPalette.AlternateBase, QColor(30, 30, 30))
        palette.setColor(QPalette.ToolTipBase, Qt.white)
        palette.setColor(QPalette.ToolTipText, Qt.white)
        palette.setColor(QPalette.Text, Qt.white)
        palette.setColor(QPalette.Button, QColor(45, 45, 45))
        palette.setColor(QPalette.ButtonText, Qt.white)
        palette.setColor(QPalette.BrightText, Qt.red)
        palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
        palette.setColor(QPalette.HighlightedText, Qt.black)

        QApplication.instance().setPalette(palette)

        self.setStyleSheet("""
            QLineEdit, QListWidget, QTextEdit {
                border: 1px solid #555;
                padding: 5px;
                border-radius: 4px;
            }
            QPushButton {
                padding: 8px 15px;
                border-radius: 4px;
                background-color: #444;
                border: 1px solid #555;
            }
            QPushButton:hover {
                background-color: #555;
            }
            QTabWidget::pane {
                border: 1px solid #555;
                border-radius: 4px;
            }
            QTabBar::tab {
                background: #333;
                padding: 8px 15px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #444;
            }
        """)

    # ── Window Events ────────────────────────────────────────────────────────

    def closeEvent(self, event):
        if self.manager.active:
            QMessageBox.warning(
                self, "Focus Mode Active",
                "Please exit Focus Mode before closing the app."
            )
            event.ignore()
        else:
            self.manager.save_settings()
            event.accept()


# ═══════════════════════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    """Application entry point."""
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setDesktopFileName(APP_ID)
    app.setStyle("Fusion")

    # Set application icon
    if os.path.exists(ICON_PATH):
        app.setWindowIcon(QIcon(ICON_PATH))

    window = MainWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
