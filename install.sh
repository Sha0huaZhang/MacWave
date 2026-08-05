#!/bin/bash

# MacWave 🌊 Official Installer
# This script downloads wave.py, installs dependencies, and configures PATH.

set -e

INSTALL_DIR="$HOME/.local/macwave/bin"
WAVE_URL="https://raw.githubusercontent.com/Sha0huaZhang/MacWave/main/wave.py"

echo "🌊 Welcome to MacWave!"
echo "🌊 Installing to $INSTALL_DIR..."

# 1. Create installation directory
mkdir -p "$INSTALL_DIR"

# 2. Download wave.py as 'wave'
echo "🌊 Downloading wave.py..."
curl -fsSL -o "$INSTALL_DIR/wave" "$WAVE_URL"

# 3. Make it executable
chmod +x "$INSTALL_DIR/wave"

# 4. Install Python dependency: requests
echo "🌊 Checking Python dependencies..."
if ! python3 -c "import requests" 2>/dev/null; then
    echo "🌊 Installing 'requests' library..."
    pip3 install requests --quiet
else
    echo "🌊 'requests' library is already installed."
fi

# 5. Add to PATH in .zshrc / .bashrc
if [[ "$SHELL" == *"zsh"* ]]; then
    RC_FILE="$HOME/.zshrc"
elif [[ "$SHELL" == *"bash"* ]]; then
    RC_FILE="$HOME/.bashrc"
else
    RC_FILE="$HOME/.profile"
fi

if ! grep -q "$INSTALL_DIR" "$RC_FILE" 2>/dev/null; then
    echo "🌊 Adding MacWave to PATH in $RC_FILE..."
    echo "" >> "$RC_FILE"
    echo "# MacWave" >> "$RC_FILE"
    echo "export PATH=\"$INSTALL_DIR:\$PATH\"" >> "$RC_FILE"
else
    echo "🌊 MacWave is already in your PATH."
fi

# 6. Final success message
echo ""
echo "🌊 Installation complete!"
echo "🌊 Try it now: wave install test_001"
echo "🌊 To apply PATH changes, run: source $RC_FILE"
