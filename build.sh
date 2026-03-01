#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Focus Lock — Build Script
# Builds the standalone binary using PyInstaller
# ═══════════════════════════════════════════════════════════════════════════════

set -e

APP_NAME="focus-lock"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo ""
echo "══════════════════════════════════════════════════"
echo "  Focus Lock — Build System"
echo "══════════════════════════════════════════════════"
echo ""

# ─── Step 1: Create / activate virtual environment ───────────────────────────
echo "[1/4] Setting up virtual environment..."

if [ ! -d "$SCRIPT_DIR/venv" ]; then
    python3 -m venv "$SCRIPT_DIR/venv"
    echo "  ✓ Virtual environment created"
else
    echo "  ✓ Virtual environment exists"
fi

source "$SCRIPT_DIR/venv/bin/activate"

# ─── Step 2: Install dependencies ───────────────────────────────────────────
echo "[2/4] Installing dependencies..."
pip install --upgrade pip -q
pip install -r "$SCRIPT_DIR/requirements.txt" -q
echo "  ✓ Dependencies installed"

# ─── Step 3: Clean previous builds ──────────────────────────────────────────
echo "[3/4] Cleaning previous builds..."
rm -rf "$SCRIPT_DIR/build" "$SCRIPT_DIR/dist"
echo "  ✓ Clean build directory"

# ─── Step 4: Build with PyInstaller ─────────────────────────────────────────
echo "[4/4] Building standalone binary with PyInstaller..."
echo "  This may take a few minutes..."

cd "$SCRIPT_DIR"
pyinstaller focus_lock.spec --clean --noconfirm

echo ""
echo "══════════════════════════════════════════════════"
echo "  ✓ Build Complete!"
echo "══════════════════════════════════════════════════"
echo ""
echo "  Binary location: $SCRIPT_DIR/dist/$APP_NAME"
echo "  Size: $(du -sh "$SCRIPT_DIR/dist/$APP_NAME" 2>/dev/null | cut -f1)"
echo ""

# Quick sanity check
if [ -f "$SCRIPT_DIR/dist/$APP_NAME" ]; then
    echo "  Testing binary..."
    chmod +x "$SCRIPT_DIR/dist/$APP_NAME"
    file "$SCRIPT_DIR/dist/$APP_NAME"
    echo ""
    echo "  ✓ Binary is ready!"
else
    echo "  ✗ ERROR: Binary not found. Check build logs above."
    exit 1
fi
