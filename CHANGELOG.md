# Changelog

All notable changes to Focus Lock will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] — 2026-03-01

### 🎉 Initial Production Release

#### Added
- **Focus Mode** — Automatically kills blacklisted processes during focus sessions
- **Allowed Resources** — Whitelist YouTube channels, applications, files, and folders
- **Blacklist Management** — Customizable list of distracting app names
- **Daily Focus Timer** — Tracks total focus time per day with automatic daily reset
- **Desktop Notifications** — System notifications when distractions are blocked
- **Dark Mode UI** — Clean, minimal dark theme built with PyQt5
- **Isolated Browser** — Opens allowed URLs in a sandboxed browser profile
- **Desktop Integration** — `.desktop` launcher for system application menu
- **Debian Package** — `.deb` installer for Ubuntu/Zorin/Debian-based systems
- **Standalone Binary** — No Python installation required on target machine
- **XDG-Compliant Settings** — Settings stored in `~/.local/share/focus-lock/`

#### Technical
- Separated configuration into `config.py`
- Proper logging (no debug prints)
- PyInstaller-compatible path resolution
- Graceful error handling throughout
- Signal-safe process termination
