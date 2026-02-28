#!/usr/bin/env python3
import sys
import os
import json
import time
import subprocess
import threading
import psutil
from datetime import datetime, timedelta

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QPushButton, QLineEdit, QListWidget,
                             QFileDialog, QMessageBox, QTabWidget, QTextEdit,
                             QSizePolicy, QInputDialog, QListWidgetItem, QAbstractItemView)
from PyQt5.QtCore import Qt, pyqtSignal, QObject, QTimer, QSize
from PyQt5.QtGui import QFont, QColor, QPalette, QIcon

SETTINGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'focus_lock_settings.json')

DEFAULT_BLACKLIST = [
    "chrome", "firefox", "brave", "opera", "vivaldi", "chromium",
    "edge", "instagram", "twitter", "telegram", "discord", "whatsapp",
    "slack", "spotify"
]

class FocusManager(QObject):
    update_timer_signal = pyqtSignal(str)
    block_notification_signal = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active = False
        self.lock_thread = None
        self.start_time = None
        
        # Load settings
        self.settings = self.load_settings()
        self.allowed_processes = []  # List to track PIDs of allowed launched apps

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            try:
                with open(SETTINGS_FILE, 'r') as f:
                    data = json.load(f)
                    
                    # Reset daily timer if it's a new day
                    last_date = data.get("last_date", "")
                    current_date = datetime.now().strftime("%Y-%m-%d")
                    if last_date != current_date:
                        data["time_focused_today_sec"] = 0
                        data["last_date"] = current_date
                        self.save_settings(data)
                        
                    return data
            except Exception as e:
                print("Error loading settings:", e)
        
        default_settings = {
            "youtube_url": "",
            "allowed_items": [], # list of dicts: {"name": "", "path": "", "type": ""}
            "blacklist": DEFAULT_BLACKLIST,
            "time_focused_today_sec": 0,
            "last_date": datetime.now().strftime("%Y-%m-%d")
        }
        self.save_settings(default_settings)
        return default_settings

    def save_settings(self, data=None):
        if data is None:
            data = self.settings
        try:
            with open(SETTINGS_FILE, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print("Error saving settings:", e)

    def launch_isolated_browser(self, url):
        """Launch the allowed YouTube URL in an isolated profile to avoid being killed."""
        print("Launching allowed browser for:", url)
        # Try finding chromium-based browsers
        chrome_paths = ['google-chrome', 'chromium-browser', 'chromium', 'brave-browser', 'microsoft-edge']
        for b in chrome_paths:
            if subprocess.call(['which', b], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
                profile_dir = '/tmp/focus_lock_chrome_profile'
                os.makedirs(profile_dir, exist_ok=True)
                proc = subprocess.Popen([b, f'--app={url}', f'--user-data-dir={profile_dir}'])
                self.allowed_processes.append(proc)
                return True
                
        # Try firefox
        if subprocess.call(['which', 'firefox'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
            profile_dir = '/tmp/focus_lock_ff_profile'
            os.makedirs(profile_dir, exist_ok=True)
            proc = subprocess.Popen(['firefox', '--no-remote', '--profile', profile_dir, url])
            self.allowed_processes.append(proc)
            return True
            
        # Fallback to xdg-open (might get killed if it's a blacklisted default browser)
        proc = subprocess.Popen(['xdg-open', url])
        self.allowed_processes.append(proc)
        return True

    def launch_item(self, path):
        """Launch allowed app, file, or folder."""
        if not os.path.exists(path):
            QMessageBox.warning(None, "Not Found", f"Path not found: {path}")
            return
            
        print("Launching allowed resource:", path)
        if os.path.isdir(path) or os.path.isfile(path) and not os.access(path, os.X_OK):
            # It's a directory or a non-executable file, strictly open with default app
            proc = subprocess.Popen(['xdg-open', path])
            self.allowed_processes.append(proc)
        else:
            # Executable
            proc = subprocess.Popen([path])
            self.allowed_processes.append(proc)

    def start_focus_mode(self):
        self.active = True
        self.start_time = time.time()
        self.allowed_processes = []
        
        # Kill initially
        self.kill_blacklisted()
        
        self.lock_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.lock_thread.start()

    def stop_focus_mode(self):
        self.active = True  # Stop the loop
        if self.lock_thread:
            self.active = False
            self.lock_thread.join(timeout=1.0)
            
        # Add session time to total
        if self.start_time:
            session_duration = int(time.time() - self.start_time)
            self.settings["time_focused_today_sec"] += session_duration
            self.save_settings()

    def _monitor_loop(self):
        while self.active:
            # Update timer UI
            session_duration = int(time.time() - self.start_time)
            total_sec = self.settings.get("time_focused_today_sec", 0) + session_duration
            formatted_time = str(timedelta(seconds=total_sec))
            self.update_timer_signal.emit(formatted_time)

            self.kill_blacklisted()
            time.sleep(3)

    def kill_blacklisted(self):
        blacklist = [b.lower() for b in self.settings.get("blacklist", [])]
        
        # Determine exempt PIDs from launched apps
        exempt_pids = set()
        active_procs = []
        for proc in self.allowed_processes:
            if proc.poll() is None:  # Still running
                active_procs.append(proc)
                try:
                    exempt_pids.add(proc.pid)
                    # Get children recursively
                    parent = psutil.Process(proc.pid)
                    for child in parent.children(recursive=True):
                        exempt_pids.add(child.pid)
                except psutil.NoSuchProcess:
                    pass
        self.allowed_processes = active_procs

        # Iterate all processes
        try:
            for p in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if p.info['pid'] in exempt_pids:
                        continue
                        
                    p_name = p.info['name'].lower()
                    # Also check cmdline for the process name in case it's a python script etc.
                    cmdline = p.info['cmdline']
                    cmd_str = " ".join(cmdline).lower() if cmdline else ""
                    
                    should_kill = False
                    for b in blacklist:
                        if b in p_name:
                            should_kill = True
                            break
                        # Certain electron apps or browsers launch via command paths
                        if b in cmd_str and any(exe in cmd_str for exe in ['/opt/', '/usr/bin/', '/snap/']):
                            # Match if the binary name exactly ends with the blacklist or contains it as a word
                            if b in cmd_str:
                                should_kill = True
                                break
                                
                    if should_kill:
                        os.kill(p.info['pid'], 9)
                        print(f"Distraction Blocked: {p_name} (PID: {p.info['pid']})")
                        self.block_notification_signal.emit(p_name)
                except (psutil.NoSuchProcess, psutil.AccessDenied, ProcessLookupError):
                    continue
        except Exception as e:
            print("Monitor error:", e)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.manager = FocusManager()
        self.manager.update_timer_signal.connect(self.update_timer_ui)
        self.manager.block_notification_signal.connect(self.show_notification)
        
        self.init_ui()
        self.apply_dark_theme()
        
    def init_ui(self):
        self.setWindowTitle("Focus Lock")
        self.setMinimumSize(600, 700)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)
        
        # Title
        title = QLabel("Focus Lock")
        title.setFont(QFont("Arial", 28, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(title)
        
        # Today's focus time
        self.time_label = QLabel("Time Focused Today: 00:00:00")
        self.time_label.setFont(QFont("Arial", 14))
        self.time_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.time_label)
        
        # Tab Widget for sections
        self.tabs = QTabWidget()
        self.tabs.setFont(QFont("Arial", 12))
        
        self.setup_allowed_tab()
        self.setup_blacklist_tab()
        
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
        self.focus_btn.clicked.connect(self.toggle_focus_mode)
        self.main_layout.addWidget(self.focus_btn)
        
        self.update_timer_ui("0:00:00") # Init with settings
        
    def setup_allowed_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # YouTube Section
        yt_label = QLabel("Allowed YouTube Channel:")
        yt_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(yt_label)
        
        yt_layout = QHBoxLayout()
        self.yt_input = QLineEdit()
        self.yt_input.setPlaceholderText("https://www.youtube.com/@Channel")
        self.yt_input.setText(self.manager.settings.get("youtube_url", ""))
        self.yt_input.textChanged.connect(self.save_yt_url)
        yt_layout.addWidget(self.yt_input)
        
        self.yt_open_btn = QPushButton("Open")
        self.yt_open_btn.clicked.connect(self.open_youtube)
        yt_layout.addWidget(self.yt_open_btn)
        layout.addLayout(yt_layout)
        
        # Resources Section
        res_label = QLabel("Allowed Applications & Files:")
        res_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(res_label)
        
        btn_layout = QHBoxLayout()
        btn_app = QPushButton("Add Application")
        btn_app.clicked.connect(self.add_app)
        btn_file = QPushButton("Add File / Book")
        btn_file.clicked.connect(self.add_file)
        btn_folder = QPushButton("Add Folder")
        btn_folder.clicked.connect(self.add_folder)
        
        btn_layout.addWidget(btn_app)
        btn_layout.addWidget(btn_file)
        btn_layout.addWidget(btn_folder)
        layout.addLayout(btn_layout)
        
        self.res_list = QListWidget()
        self.res_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.res_list.doubleClicked.connect(self.open_selected_resource)
        self.refresh_resources_list()
        layout.addWidget(self.res_list)
        
        # Remove and Open buttons
        action_layout = QHBoxLayout()
        btn_remove = QPushButton("Remove Selected")
        btn_remove.clicked.connect(self.remove_resource)
        btn_open = QPushButton("Open Selected")
        btn_open.clicked.connect(self.open_selected_resource)
        
        action_layout.addWidget(btn_open)
        action_layout.addWidget(btn_remove)
        layout.addLayout(action_layout)
        
        self.tabs.addTab(tab, "Allowed Resources")

    def setup_blacklist_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        lbl = QLabel("Distracting Apps (Blacklist):")
        lbl.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(lbl)
        
        self.edit_blacklist = QTextEdit()
        # Join blacklist into text box
        bl = self.manager.settings.get("blacklist", [])
        self.edit_blacklist.setText("\n".join(bl))
        layout.addWidget(self.edit_blacklist)
        
        btn_save = QPushButton("Save Blacklist")
        btn_save.clicked.connect(self.save_blacklist)
        layout.addWidget(btn_save)
        
        lbl_info = QLabel("Add one application name per line (e.g., chrome, firefox, instagram).")
        lbl_info.setWordWrap(True)
        lbl_info.setStyleSheet("color: #aaaaaa;")
        layout.addWidget(lbl_info)
        
        self.tabs.addTab(tab, "Blacklist")

    def save_yt_url(self):
        self.manager.settings["youtube_url"] = self.yt_input.text()
        self.manager.save_settings()

    def open_youtube(self):
        url = self.yt_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Error", "Please enter a YouTube URL.")
            return
        self.manager.launch_isolated_browser(url)
        
    def add_app(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select Application Executable", "/usr/bin")
        if path:
            self.add_resource("app", path, os.path.basename(path))

    def add_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select File / Book", os.path.expanduser("~"))
        if path:
            self.add_resource("file", path, os.path.basename(path))

    def add_folder(self):
        path = QFileDialog.getExistingDirectory(self, "Select Folder", os.path.expanduser("~"))
        if path:
            self.add_resource("folder", path, os.path.basename(path))

    def add_resource(self, rtype, path, name):
        items = self.manager.settings.get("allowed_items", [])
        # Prevent duplicates
        if any(item['path'] == path for item in items):
            return
            
        items.append({"type": rtype, "path": path, "name": name})
        self.manager.settings["allowed_items"] = items
        self.manager.save_settings()
        self.refresh_resources_list()

    def remove_resource(self):
        selected = self.res_list.currentRow()
        if selected < 0: return
        
        items = self.manager.settings.get("allowed_items", [])
        if 0 <= selected < len(items):
            del items[selected]
            self.manager.settings["allowed_items"] = items
            self.manager.save_settings()
            self.refresh_resources_list()

    def open_selected_resource(self):
        selected = self.res_list.currentRow()
        if selected < 0: return
        
        items = self.manager.settings.get("allowed_items", [])
        if 0 <= selected < len(items):
            path = items[selected]["path"]
            self.manager.launch_item(path)

    def refresh_resources_list(self):
        self.res_list.clear()
        items = self.manager.settings.get("allowed_items", [])
        for item in items:
            t = item.get('type', 'Unknown').upper()
            n = item.get('name', 'Unknown')
            p = item.get('path', '')
            self.res_list.addItem(f"[{t}] {n}  ({p})")

    def save_blacklist(self):
        text = self.edit_blacklist.toPlainText()
        bl = [line.strip() for line in text.split('\n') if line.strip()]
        self.manager.settings["blacklist"] = bl
        self.manager.save_settings()
        QMessageBox.information(self, "Saved", "Blacklist updated successfully.")

    def toggle_focus_mode(self):
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
            # Disable close button by overriding it
            self.setWindowFlag(Qt.WindowCloseButtonHint, False)
            self.show()
            QMessageBox.information(self, "Focus Mode Started", "Distracting applications will be continuously closed!")
        else:
            # Exit Focus Mode
            reply = QMessageBox.question(self, 'Confirm Exit', 
                                     'Are you sure you want to exit Focus Lock?',
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
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

    def update_timer_ui(self, time_str):
        # Initial load fallback
        if time_str == "0:00:00":
            total_sec = self.manager.settings.get("time_focused_today_sec", 0)
            time_str = str(timedelta(seconds=total_sec))
        self.time_label.setText(f"Time Focused Today: {time_str}")

    def show_notification(self, app_name):
        try:
            # Requires libnotify-bin on Ubuntu/Zorin
            subprocess.call(['notify-send', '-u', 'low', 'Focus Lock', f'Distraction Blocked: {app_name}'])
        except:
            pass

    def apply_dark_theme(self):
        # A beautiful clean dark theme
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
        
        # Style adjustments for widgets
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

    def closeEvent(self, event):
        if self.manager.active:
            QMessageBox.warning(self, "Focus Mode Active", "Please exit Focus Mode before closing the app.")
            event.ignore()
        else:
            self.manager.save_settings()
            event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec_())
