#!/bin/bash

# MacWave 🌊 Uninstaller
# This script completely removes MacWave from your system.

set -e

INSTALL_DIR="$HOME/.local/macwave"

# Display warning in red
echo -e "\033[31mYou are deleting MacWave, are you sure? [Y/n]\033[0m"
read -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "🌊 Uninstall cancelled."
    exit 0
fi

# 1. Remove the installation directory
if [ -d "$INSTALL_DIR" ]; then
    echo "🌊 Removing $INSTALL_DIR..."
    rm -rf "$INSTALL_DIR"
else
    echo "🌊 MacWave installation directory not found. Skipping."
fi

# 2. Remove PATH entries from .zshrc / .bashrc
remove_path_from_rc() {
    local RC_FILE="$1"
    if [ -f "$RC_FILE" ]; then
        # Remove MacWave PATH entries using sed
        sed -i '' '/# MacWave/d' "$RC_FILE" 2>/dev/null || true
        sed -i '' '/export PATH=".*macwave\/bin/d' "$RC_FILE" 2>/dev/null || true
        echo "🌊 Removed MacWave PATH entries from $RC_FILE"
    fi
}

remove_path_from_rc "$HOME/.zshrc"
remove_path_from_rc "$HOME/.bashrc"

# 3. Final message
echo ""
echo "🌊 MacWave has been uninstalled."
echo "🌊 Please restart your terminal to apply changes."
