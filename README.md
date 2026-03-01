<p align="center">
  <img src="icon.png" alt="Focus Lock Logo" width="150" />
</p>

<h1 align="center">Focus Lock</h1>

<p align="center">
  <strong>A lightweight Linux desktop app that blocks distracting applications to help you stay focused.</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-blue?style=flat-square" alt="Version" />
  <img src="https://img.shields.io/badge/platform-Linux-green?style=flat-square" alt="Platform" />
  <img src="https://img.shields.io/badge/license-MIT-yellow?style=flat-square" alt="License" />
</p>

---

## ✨ Features

- **🔒 Focus Mode** — Automatically closes distracting apps (Chrome, Discord, Spotify, etc.)
- **📋 Custom Blacklist** — Define which apps count as distractions
- **✅ Allowed Resources** — Whitelist YouTube channels, files, folders, and apps
- **⏱ Focus Timer** — Tracks your total focus time each day
- **🔔 Notifications** — Desktop alerts when distractions are blocked
- **🌙 Dark Mode** — Clean, minimal dark-themed interface
- **📦 Standalone** — Runs without Python — no dependencies needed

---

## 📥 Installation

### Option A: Install from `.deb` package (Recommended)

Download the latest `.deb` from the [Releases](https://github.com/TejaasDev/focus-lock/releases) page.

```bash
# Install
sudo dpkg -i focus-lock_1.0.0_amd64.deb

# Fix any missing dependencies (if needed)
sudo apt-get install -f
```

After installation, **Focus Lock** appears in your application menu. You can also launch it from the terminal:

```bash
focus-lock
```

### Option B: Run the standalone binary

Download the `focus-lock` binary from Releases and run it directly:

```bash
chmod +x focus-lock
./focus-lock
```

### Option C: Run from source (Development)

```bash
# Clone the repository
git clone https://github.com/TejaasDev/focus-lock.git
cd focus-lock

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run
python3 focus_lock.py
```

---

## 🔨 Building from Source

### Build the standalone binary

```bash
chmod +x build.sh
./build.sh
```

The binary will be at `dist/focus-lock`.

### Build the `.deb` package

```bash
# First, build the binary
./build.sh

# Then, package it
chmod +x build_deb.sh
./build_deb.sh
```

The `.deb` package will be at `dist/focus-lock_1.0.0_amd64.deb`.

---

## 🗂️ Uninstallation

```bash
sudo apt remove focus-lock
```

User settings are stored at `~/.local/share/focus-lock/` and are preserved on uninstall. Delete manually if desired.

---

## 📁 Project Structure

```
focus-lock/
├── focus_lock.py          # Main application
├── config.py              # Configuration & constants
├── icon.png               # App icon (256×256)
├── focus-lock.desktop      # Linux desktop launcher
├── focus_lock.spec         # PyInstaller build spec
├── requirements.txt        # Python dependencies
├── build.sh               # Binary build script
├── build_deb.sh           # Debian package build script
├── CHANGELOG.md           # Version history
├── README.md              # This file
└── dist/                  # Build output (generated)
    ├── focus-lock         # Standalone binary
    └── focus-lock_1.0.0_amd64.deb
```

---

## 🖥️ System Requirements

- **OS:** Ubuntu 20.04+, Zorin OS, Linux Mint, Debian 11+, or any Debian-based distro
- **Architecture:** x86_64 (amd64)
- **Dependencies:** `libnotify-bin` (for desktop notifications, installed automatically with `.deb`)

---

## 🪟 Windows Compatibility (Planned)

A Windows version is planned for a future release. The build process will require:

1. Running PyInstaller on a Windows system
2. Generating a `.exe` with `--onefile --windowed --icon=icon.ico`
3. The core Python code is already cross-platform compatible

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>Built with ❤️ by Tejaas</strong>
</p>
