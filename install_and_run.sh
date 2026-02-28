#!/bin/bash
# Focus Lock - Installer & Runner

echo "Installing required dependencies for Focus Lock..."

# Update and install python and pyqt5 if necessary
sudo apt-get update
sudo apt-get install -y python3 python3-pyqt5 python3-pip python3-venv libnotify-bin

# Set up python venv in current directory
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
else
    echo "Virtual environment exists."
fi

# Install psutil in venv
echo "Installing psutil..."
./venv/bin/pip install psutil

echo ""
echo "======================================"
echo "    Installation Complete!"
echo "======================================"
echo ""
echo "Starting Focus Lock..."
./venv/bin/python focus_lock.py
