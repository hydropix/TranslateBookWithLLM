#!/bin/bash
# ============================================
# TranslateBook - Build macOS Executable
# ============================================

echo ""
echo "============================================"
echo "TranslateBook - Building macOS Executable"
echo "============================================"
echo ""

# Check if virtual environment exists
if [ ! -d "../../venv" ]; then
    echo "[ERROR] Virtual environment not found"
    echo "Please create one first:"
    echo "  python3 -m venv venv"
    echo "  source venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
echo "[1/4] Activating virtual environment..."
source ../../venv/bin/activate

# Install PyInstaller if not already installed
echo "[2/4] Checking PyInstaller installation..."
if ! pip show pyinstaller > /dev/null 2>&1; then
    echo "[INFO] Installing PyInstaller..."
    pip install pyinstaller
fi
echo "[OK] PyInstaller ready"

# Clean previous builds
echo "[3/4] Cleaning previous builds..."
rm -rf ../../dist ../dist ../TranslateBookWithLLM
echo "[OK] Cleaned"

# Build executable
echo "[4/4] Building TranslateBook..."
echo "This may take 5-10 minutes..."
echo ""
pyinstaller --clean TranslateBook-macOS.spec

if [ $? -ne 0 ]; then
    echo ""
    echo "[ERROR] Build failed"
    exit 1
fi

echo ""
echo "============================================"
echo "Build Complete!"
echo "============================================"
echo ""
echo "Executable location: ../../dist/TranslateBook"

# Get file size
if [ -f "../../dist/TranslateBook" ]; then
    SIZE=$(ls -lh ../../dist/TranslateBook | awk '{print $5}')
    echo "File size: $SIZE"
fi

echo ""
echo "You can now distribute this executable"
echo "Users need to have Ollama installed separately"
echo ""
echo "To make it executable on another Mac:"
echo "  chmod +x TranslateBook"
echo ""
