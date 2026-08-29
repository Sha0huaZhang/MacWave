#!/bin/bash

# MacWave Troubleshooting Script
# Usage: ./troubleshoot.sh

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

echo "=== MacWave System Diagnostics ==="
echo ""

# 1. Check if wave is installed
echo "[1/7] Checking wave executable..."
if command -v wave &> /dev/null; then
    echo -e "${GREEN}wave found at: $(which wave)${NC}"
else
    echo -e "${RED}wave not found in PATH.${NC}"
    echo -e "${YELLOW}Try: source ~/.zshrc${NC}"
fi
echo ""

# 2. Check Python 3
echo "[2/7] Checking Python 3..."
if command -v python3 &> /dev/null; then
    echo -e "${GREEN}Python 3 found: $(python3 --version)${NC}"
else
    echo -e "${RED}Python 3 not found. Install Python 3.${NC}"
fi
echo ""

# 3. Check Python dependencies
echo "[3/7] Checking Python dependencies (requests, packaging, rich)..."
python3 -c "import requests; print('requests OK')" 2>/dev/null && echo -e "${GREEN}requests installed.${NC}" || echo -e "${RED}requests missing. Run: pip3 install requests${NC}"
python3 -c "from packaging.version import parse; print('packaging OK')" 2>/dev/null && echo -e "${GREEN}packaging installed.${NC}" || echo -e "${RED}packaging missing. Run: pip3 install packaging${NC}"
python3 -c "import rich; print('rich OK')" 2>/dev/null && echo -e "${GREEN}rich installed.${NC}" || echo -e "${RED}rich missing. Run: pip3 install rich${NC}"
echo ""

# 4. Check Ruby
echo "[4/7] Checking Ruby..."
if command -v ruby &> /dev/null; then
    RUBY_VERSION=$(ruby -e 'puts RUBY_VERSION')
    echo -e "${GREEN}Ruby found, version: $RUBY_VERSION${NC}"
else
    echo -e "${RED}Ruby not found. Install Ruby 2.6.10+.${NC}"
fi
echo ""

# 5. Check config file
echo "[5/7] Checking configuration (/opt/macwave_config)..."
if [ -f "/opt/macwave_config/config.json" ]; then
    echo -e "${GREEN}config.json exists.${NC}"
else
    echo -e "${RED}config.json missing. Run install script again.${NC}"
fi
echo ""

# 6. Check PKG directory structure
echo "[6/7] Checking package directory (~/.local/macwave/pkg)..."
PKG_DIR="$HOME/.local/macwave/pkg"
if [ -d "$PKG_DIR" ]; then
    echo -e "${GREEN}pkg directory exists.${NC}"
    if [ -f "$PKG_DIR/pkgparser.rb" ]; then
        echo -e "${GREEN}pkgparser.rb found.${NC}"
    else
        echo -e "${RED}pkgparser.rb missing.${NC}"
    fi
    if [ -f "$PKG_DIR/pkginfo_arm64.txt" ]; then
        echo -e "${GREEN}pkginfo_arm64.txt found.${NC}"
    else
        echo -e "${RED}pkginfo_arm64.txt missing.${NC}"
    fi
else
    echo -e "${RED}pkg directory missing. Reinstall MacWave.${NC}"
fi
echo ""

# 7. Check URL validity (Testing ldid package)
echo "[7/7] Checking download URL validity..."
URL="https://github.com/ProcursusTeam/ldid/releases/download/v2.1.5-procursus7/ldid_macosx_arm64"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" -I "$URL")
if [ "$HTTP_CODE" == "302" ] || [ "$HTTP_CODE" == "200" ]; then
    echo -e "${GREEN}URL is valid (HTTP $HTTP_CODE).${NC}"
else
    echo -e "${RED}URL is invalid (HTTP $HTTP_CODE). Check URL or version.${NC}"
fi
echo ""

echo "=== Diagnostics Complete ==="
