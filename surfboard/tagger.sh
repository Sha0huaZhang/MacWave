#!/bin/bash

# tagger.sh - 负责为依赖目录生成引用标记文件
# 用法: bash tagger.sh <依赖名> <依赖版本> <引用者包名> <引用者版本>

set -e

RED_BOLD='\033[1;31m'
GREEN='\033[32m'
RESET='\033[0m'

DEP_NAME="$1"
DEP_VERSION="$2"
REF_PKG_NAME="$3"
REF_PKG_VERSION="$4"

CONFIG_FILE="/opt/macwave_config/config.json"
if [[ -f "$CONFIG_FILE" ]]; then
    BASE_DIR=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE')).get('base_dir', ''))" 2>/dev/null)
fi

if [[ -z "$BASE_DIR" ]]; then
    echo -e "${RED_BOLD}🌊 Error: Configuration not found.${RESET}"
    exit 1
fi

DEP_DIR="$BASE_DIR/deps/${DEP_NAME}@${DEP_VERSION}"
MARKER="$DEP_DIR/.dep_${REF_PKG_NAME}@${REF_PKG_VERSION}"

if [[ ! -d "$DEP_DIR" ]]; then
    echo -e "${RED_BOLD}🌊 Error: Dependency directory $DEP_DIR not found.${RESET}"
    exit 1
fi

touch "$MARKER"
echo -e "${GREEN}🌊 Generated reference marker: $MARKER${RESET}"
exit 0
