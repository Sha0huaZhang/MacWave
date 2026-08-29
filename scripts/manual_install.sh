#!/bin/bash

# MacWave Manual Installation Simulation Script
# Usage: ./manual_install.sh

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Package Info (Change these if testing other packages)
PACKAGE_NAME="ldid"
VERSION="2.1.5-procursus7"
BINARY_NAME="ldid_macosx_arm64"
URL="https://github.com/ProcursusTeam/ldid/releases/download/v2.1.5-procursus7/ldid_macosx_arm64"
SHA256="5dff8e6b8d9dc3ff7226276c81e09930865f15381f54cb55b98b196a94c5ca50"

# Paths
BASE_DIR="$HOME/.local/macwave"
BIN_DIR="$BASE_DIR/bin"
TMP_DIR="$BASE_DIR/downloads/tmp"
FINAL_PATH="$BIN_DIR/${PACKAGE_NAME}@${VERSION}"
INSTALLED_DB="$BASE_DIR/pkg/installed.json"

echo "=== MacWave Manual Installation Simulation ==="
echo "Package: $PACKAGE_NAME"
echo "Version: $VERSION"
echo "Target: $FINAL_PATH"
echo ""

# Step 1: Create directories
echo "[1/5] Creating directories..."
mkdir -p "$BIN_DIR" "$TMP_DIR" "$BASE_DIR/pkg"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Directories created successfully.${NC}"
else
    echo -e "${RED}Failed to create directories. Check permissions.${NC}"
    exit 1
fi

# Step 2: Download file
echo "[2/5] Downloading $BINARY_NAME..."
cd "$TMP_DIR"
curl -L -o "$BINARY_NAME" "$URL"
if [ $? -eq 0 ] && [ -f "$BINARY_NAME" ]; then
    echo -e "${GREEN}Download successful (File Size: $(du -h "$BINARY_NAME" | cut -f1)).${NC}"
else
    echo -e "${RED}Download failed. Check network or URL.${NC}"
    exit 1
fi

# Step 3: Verify SHA256
echo "[3/5] Verifying SHA256..."
ACTUAL_SHA256=$(shasum -a 256 "$BINARY_NAME" | awk '{print $1}')
if [ "$ACTUAL_SHA256" == "$SHA256" ]; then
    echo -e "${GREEN}SHA256 verification passed.${NC}"
else
    echo -e "${RED}SHA256 verification FAILED.${NC}"
    echo -e "${RED}Expected: $SHA256${NC}"
    echo -e "${RED}Actual:   $ACTUAL_SHA256${NC}"
    exit 1
fi

# Step 4: Move and set permissions
echo "[4/5] Installing to $FINAL_PATH..."
mv "$BINARY_NAME" "$FINAL_PATH"
chmod +x "$FINAL_PATH"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}File installed and made executable.${NC}"
else
    echo -e "${RED}Failed to move file.${NC}"
    exit 1
fi

# Step 5: Update installed.json
echo "[5/5] Updating installation database..."
python3 -c "
import json, time, os
db_path = os.path.expanduser('$INSTALLED_DB')
with open(db_path, 'a+') as f:
    try:
        f.seek(0)
        installed = json.load(f)
    except:
        installed = {}
    installed['$PACKAGE_NAME'] = {
        'version': '$VERSION',
        'binary_path': os.path.expanduser('$FINAL_PATH'),
        'installed_at': time.time()
    }
    f.seek(0)
    f.truncate()
    json.dump(installed, f, indent=2)
"
if [ $? -eq 0 ]; then
    echo -e "${GREEN}Installation database updated.${NC}"
else
    echo -e "${RED}Failed to update installation database.${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}=== INSTALLATION COMPLETE ==="
echo -e "${GREEN}Run 'wave list' to confirm.${NC}"
