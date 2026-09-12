#!/bin/bash

# format_test.sh
# 对 8 种格式的测试包逐个跑：install → 执行 → uninstall

set -e

RED_BOLD='\033[1;31m'
GREEN='\033[32m'
YELLOW='\033[33m'
RESET='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
WAVE_BIN="$REPO_DIR/lib/wave.py"

if [[ ! -f "$WAVE_BIN" ]]; then
    echo -e "${RED_BOLD}🌊 Error: wave.py not found at $WAVE_BIN${RESET}"
    exit 1
fi

CONFIG_FILE="/opt/macwave_config/config.json"
if [[ ! -f "$CONFIG_FILE" ]]; then
    echo -e "${RED_BOLD}🌊 Error: MacWave not installed (config not found).${RESET}"
    exit 1
fi

BASE_DIR=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE'))['base_dir'])")
BIN_DIR="$BASE_DIR/bin"

PKGS=(
    "test_bin_no_ext|no-extension"
    "test_bin_zip|.zip"
    "test_bin_targz|.tar.gz"
    "test_bin_tarbz2|.tar.bz2"
    "test_bin_tarxz|.tar.xz"
    "test_bin_tar|.tar"
    "test_bin_gz|.gz"
    "test_bin_bz2|.bz2"
)

FAILED=0
PASSED=0

for entry in "${PKGS[@]}"; do
    IFS='|' read -r pkg fmt <<< "$entry"
    echo ""
    echo "========== $pkg ($fmt) =========="

    if ! python3 "$WAVE_BIN" install "${pkg}@1.0"; then
        echo -e "${RED_BOLD}🌊 FAIL: install ${pkg}@1.0${RESET}"
        FAILED=$((FAILED + 1))
        continue
    fi

    if [[ ! -x "$BIN_DIR/${pkg}@1.0" ]]; then
        echo -e "${RED_BOLD}🌊 FAIL: ${pkg}@1.0 not executable${RESET}"
        FAILED=$((FAILED + 1))
        python3 "$WAVE_BIN" uninstall "${pkg}@1.0" || true
        continue
    fi

    OUTPUT=$("$BIN_DIR/${pkg}@1.0")
    if [[ "$OUTPUT" != *"Test Successful! ($fmt)"* ]]; then
        echo -e "${RED_BOLD}🌊 FAIL: unexpected output: $OUTPUT${RESET}"
        FAILED=$((FAILED + 1))
    else
        echo -e "${GREEN}🌊 PASS: $pkg${RESET}"
        PASSED=$((PASSED + 1))
    fi

    python3 "$WAVE_BIN" uninstall "${pkg}@1.0" || true
done

echo ""
echo "=========================================="
echo "🌊 Passed: $PASSED / ${#PKGS[@]}"
echo "🌊 Failed: $FAILED / ${#PKGS[@]}"
echo "=========================================="

if [[ "$FAILED" -gt 0 ]]; then
    exit 1
fi

exit 0
