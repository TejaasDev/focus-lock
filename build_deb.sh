#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Focus Lock — .deb Package Builder
# Creates a proper Debian package for Ubuntu/Zorin/Debian-based systems
# ═══════════════════════════════════════════════════════════════════════════════

set -e

APP_NAME="focus-lock"
APP_VERSION="1.0.0"
ARCH="amd64"
MAINTAINER="Tejaas <tejaas@focuslock.app>"
DESCRIPTION="A lightweight desktop application that helps you stay focused by blocking distracting applications."

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BINARY="$SCRIPT_DIR/dist/$APP_NAME"
ICON="$SCRIPT_DIR/icon.png"
DESKTOP_FILE="$SCRIPT_DIR/focus-lock.desktop"

PKG_NAME="${APP_NAME}_${APP_VERSION}_${ARCH}"
PKG_DIR="$SCRIPT_DIR/pkg-build/$PKG_NAME"

echo ""
echo "══════════════════════════════════════════════════"
echo "  Focus Lock — Debian Package Builder"
echo "══════════════════════════════════════════════════"
echo ""

# ─── Verify binary exists ───────────────────────────────────────────────────
if [ ! -f "$BINARY" ]; then
    echo "  ✗ ERROR: Binary not found at $BINARY"
    echo "  Run ./build.sh first to create the binary."
    exit 1
fi

echo "[1/5] Verifying assets..."
echo "  ✓ Binary: $BINARY"
echo "  ✓ Icon:   $ICON"
echo "  ✓ Desktop: $DESKTOP_FILE"

# ─── Create package directory structure ──────────────────────────────────────
echo "[2/5] Creating package structure..."
rm -rf "$PKG_DIR"
mkdir -p "$PKG_DIR/DEBIAN"
mkdir -p "$PKG_DIR/usr/bin"
mkdir -p "$PKG_DIR/usr/share/applications"
mkdir -p "$PKG_DIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$PKG_DIR/usr/share/doc/$APP_NAME"
echo "  ✓ Directory structure created"

# ─── DEBIAN/control ─────────────────────────────────────────────────────────
echo "[3/5] Writing package metadata..."
cat > "$PKG_DIR/DEBIAN/control" << EOF
Package: $APP_NAME
Version: $APP_VERSION
Section: utils
Priority: optional
Architecture: $ARCH
Depends: libnotify-bin, libxcb-xinerama0
Recommends: libnotify-bin
Maintainer: $MAINTAINER
Description: $DESCRIPTION
 Focus Lock is a productivity tool that blocks distracting
 applications while you work. It monitors running processes
 and automatically closes blacklisted apps during focus sessions.
 .
 Features:
  - Focus Mode with automatic distraction blocking
  - Customizable blacklist of distracting applications
  - Allowed resources (YouTube channels, files, folders)
  - Daily focus time tracking
  - Dark mode UI
Homepage: https://github.com/TejaasDev/focus-lock
EOF

# ─── Post-install script ────────────────────────────────────────────────────
cat > "$PKG_DIR/DEBIAN/postinst" << 'EOF'
#!/bin/sh
set -e

# Update icon cache
if command -v gtk-update-icon-cache > /dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
fi

# Update desktop database
if command -v update-desktop-database > /dev/null 2>&1; then
    update-desktop-database /usr/share/applications 2>/dev/null || true
fi

echo ""
echo "═══════════════════════════════════════════════"
echo "  Focus Lock installed successfully!"
echo "  Launch from your application menu or run:"
echo "    focus-lock"
echo "═══════════════════════════════════════════════"
echo ""
EOF
chmod 0755 "$PKG_DIR/DEBIAN/postinst"

# ─── Post-remove script ─────────────────────────────────────────────────────
cat > "$PKG_DIR/DEBIAN/postrm" << 'EOF'
#!/bin/sh
set -e

# Update icon cache
if command -v gtk-update-icon-cache > /dev/null 2>&1; then
    gtk-update-icon-cache -f -t /usr/share/icons/hicolor 2>/dev/null || true
fi

# Update desktop database
if command -v update-desktop-database > /dev/null 2>&1; then
    update-desktop-database /usr/share/applications 2>/dev/null || true
fi

# Clean up user data on purge
if [ "$1" = "purge" ]; then
    echo "Note: User settings in ~/.local/share/focus-lock/ were not removed."
    echo "Delete manually if you want to remove all data."
fi
EOF
chmod 0755 "$PKG_DIR/DEBIAN/postrm"

echo "  ✓ Control files written"

# ─── Copy files into package ────────────────────────────────────────────────
echo "[4/5] Packaging files..."

# Binary
cp "$BINARY" "$PKG_DIR/usr/bin/$APP_NAME"
chmod 0755 "$PKG_DIR/usr/bin/$APP_NAME"
echo "  ✓ Binary installed to /usr/bin/$APP_NAME"

# Desktop file
cp "$DESKTOP_FILE" "$PKG_DIR/usr/share/applications/$APP_NAME.desktop"
chmod 0644 "$PKG_DIR/usr/share/applications/$APP_NAME.desktop"
echo "  ✓ Desktop launcher installed"

# Icon
cp "$ICON" "$PKG_DIR/usr/share/icons/hicolor/256x256/apps/$APP_NAME.png"
chmod 0644 "$PKG_DIR/usr/share/icons/hicolor/256x256/apps/$APP_NAME.png"
echo "  ✓ Icon installed"

# Copyright / doc
cat > "$PKG_DIR/usr/share/doc/$APP_NAME/copyright" << EOF
Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/
Upstream-Name: Focus Lock
Source: https://github.com/TejaasDev/focus-lock

Files: *
Copyright: 2026 Tejaas
License: MIT
EOF
chmod 0644 "$PKG_DIR/usr/share/doc/$APP_NAME/copyright"

# ─── Build .deb ─────────────────────────────────────────────────────────────
echo "[5/5] Building .deb package..."

# Set correct ownership (fakeroot handles this)
fakeroot dpkg-deb --build "$PKG_DIR" "$SCRIPT_DIR/dist/$PKG_NAME.deb"

echo ""
echo "══════════════════════════════════════════════════"
echo "  ✓ Package Built Successfully!"
echo "══════════════════════════════════════════════════"
echo ""
echo "  Package:  $SCRIPT_DIR/dist/$PKG_NAME.deb"
echo "  Size:     $(du -sh "$SCRIPT_DIR/dist/$PKG_NAME.deb" | cut -f1)"
echo ""
echo "  Install with:"
echo "    sudo dpkg -i dist/$PKG_NAME.deb"
echo ""
echo "  Or double-click the .deb file in your file manager."
echo ""
echo "  Uninstall with:"
echo "    sudo apt remove $APP_NAME"
echo ""
