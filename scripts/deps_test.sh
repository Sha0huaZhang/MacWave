#!/bin/bash

# deps_test.sh
# 端到端依赖回归：装一个带依赖链的包 → 运行二进制 → 确认没有未解析的库引用
# → 检查引用计数标记 → 卸载 → 确认依赖目录与软链接都被级联清理

set -e

RED_BOLD='\033[1;31m'
GREEN='\033[32m'
YELLOW='\033[33m'
RESET='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"
WAVE_BIN="$REPO_DIR/lib/wave.py"
PKG="${1:-wget@1.25.0}"

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
LINKS_DIR="$BASE_DIR/links"
DEPS_DIR="$BASE_DIR/deps"
LOG_FILE="$(mktemp)"

FAILED=0

# ==========================================
# 1. 安装（会把整条依赖链拉下来）
# ==========================================

echo "========== install $PKG =========="
INSTALL_RC=0
python3 "$WAVE_BIN" install "$PKG" > "$LOG_FILE" 2>&1 || INSTALL_RC=$?
cat "$LOG_FILE"

if [[ "$INSTALL_RC" -ne 0 ]]; then
    echo -e "${RED_BOLD}🌊 FAIL: install $PKG${RESET}"
    rm -f "$LOG_FILE"
    exit 1
fi

# ==========================================
# 2. 二进制要能真正跑起来（relink 漏改会在这里以 dyld 报错暴露）
# ==========================================

echo "========== run $PKG =========="
if "$LINKS_DIR/$PKG" --version > /dev/null 2>&1; then
    echo -e "${GREEN}🌊 OK: $PKG --version${RESET}"
else
    echo -e "${RED_BOLD}🌊 FAIL: $PKG --version${RESET}"
    FAILED=$((FAILED + 1))
fi

# ==========================================
# 3. 依赖里的动态库引用不能有未解析项
# ==========================================

if grep -qE 'could not be linked|not provided by any installed dependency' "$LOG_FILE"; then
    echo -e "${RED_BOLD}🌊 FAIL: unresolved library references${RESET}"
    grep -E 'could not be linked|not provided by any installed dependency' "$LOG_FILE"
    FAILED=$((FAILED + 1))
fi

# ==========================================
# 4. 引用计数标记必须写出来
# ==========================================

MARKERS=$(find "$DEPS_DIR" -name '.depped_*' 2>/dev/null | wc -l | tr -d ' ')
if [[ "$MARKERS" -eq 0 ]]; then
    echo -e "${RED_BOLD}🌊 FAIL: no .depped_* marker was written${RESET}"
    FAILED=$((FAILED + 1))
else
    echo "🌊 Found $MARKERS marker(s)"
fi

# ==========================================
# 5. 卸载，整条依赖链应被级联清理
# ==========================================

echo "========== uninstall $PKG =========="
python3 "$WAVE_BIN" uninstall "$PKG" > /dev/null 2>&1 || true

if [[ -e "$BIN_DIR/$PKG" || -e "$LINKS_DIR/$PKG" ]]; then
    echo -e "${RED_BOLD}🌊 FAIL: $PKG was left behind${RESET}"
    FAILED=$((FAILED + 1))
fi

REMAINING=$(find "$DEPS_DIR" -mindepth 2 -maxdepth 2 -type d 2>/dev/null | wc -l | tr -d ' ')
if [[ "$REMAINING" -ne 0 ]]; then
    echo -e "${RED_BOLD}🌊 FAIL: $REMAINING dependency dir(s) left behind${RESET}"
    find "$DEPS_DIR" -mindepth 2 -maxdepth 2 -type d
    FAILED=$((FAILED + 1))
fi

rm -f "$LOG_FILE"

# ==========================================
# 结果
# ==========================================

echo ""
if [[ "$FAILED" -gt 0 ]]; then
    echo -e "${RED_BOLD}🌊 Dependency test failed ($FAILED check(s))${RESET}"
    exit 1
fi

echo -e "${GREEN}🌊 Dependency test passed${RESET}"
