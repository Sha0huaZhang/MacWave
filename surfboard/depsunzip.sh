#!/bin/bash

# depsunzip.sh - 负责解压依赖包并自动移动到 deps 目录
# 用法: bash depsunzip.sh <依赖名> <版本号> <下载文件路径>

set -e

RED_BOLD='\033[1;31m'
GREEN='\033[32m'
RESET='\033[0m'

DEP_NAME="$1"
DEP_VERSION="$2"
ARCHIVE_PATH="$3"

# ==========================================
# 参数检查
# ==========================================

if [[ -z "$DEP_NAME" || -z "$DEP_VERSION" || -z "$ARCHIVE_PATH" ]]; then
    echo -e "${RED_BOLD}🌊 Error: Missing dependency name, version, or archive path.${RESET}"
    exit 1
fi

if [[ ! -f "$ARCHIVE_PATH" ]]; then
    echo -e "${RED_BOLD}🌊 Error: Archive file not found: $ARCHIVE_PATH${RESET}"
    exit 1
fi

# ==========================================
# 读取配置
# ==========================================

CONFIG_DIR="/opt/macwave_config"
CONFIG_FILE="$CONFIG_DIR/config.json"

if [[ -f "$CONFIG_FILE" ]]; then
    BASE_DIR=$(python3 -c "import json; print(json.load(open('$CONFIG_FILE')).get('base_dir', ''))" 2>/dev/null)
fi

if [[ -z "$BASE_DIR" ]]; then
    echo -e "${RED_BOLD}🌊 Error: Configuration not found.${RESET}"
    exit 1
fi

DEPS_DIR="$BASE_DIR/deps"
TARGET_DIR="$DEPS_DIR/${DEP_NAME}@${DEP_VERSION}"

# ==========================================
# 解压并移动
# ==========================================

echo -e "${GREEN}🌊 Extracting dependency: ${DEP_NAME}@${DEP_VERSION}${RESET}"

# 创建目标目录
mkdir -p "$TARGET_DIR"

# 临时解压目录
TEMP_EXTRACT_DIR="$TARGET_DIR/_extract_tmp"
rm -rf "$TEMP_EXTRACT_DIR"
mkdir -p "$TEMP_EXTRACT_DIR"

# 根据文件后缀解压
case "$ARCHIVE_PATH" in
    *.zip)
        unzip -q "$ARCHIVE_PATH" -d "$TEMP_EXTRACT_DIR"
        ;;
    *.tar.gz|*.tgz)
        tar -xzf "$ARCHIVE_PATH" -C "$TEMP_EXTRACT_DIR"
        ;;
    *.tar.bz2|*.tbz2)
        tar -xjf "$ARCHIVE_PATH" -C "$TEMP_EXTRACT_DIR"
        ;;
    *.tar.xz|*.txz)
        tar -xJf "$ARCHIVE_PATH" -C "$TEMP_EXTRACT_DIR"
        ;;
    *.tar)
        tar -xf "$ARCHIVE_PATH" -C "$TEMP_EXTRACT_DIR"
        ;;
    *.gz)
        gzip -dk "$ARCHIVE_PATH" -c > "$TEMP_EXTRACT_DIR/${DEP_NAME}"
        ;;
    *.bz2)
        bzip2 -dk "$ARCHIVE_PATH" -c > "$TEMP_EXTRACT_DIR/${DEP_NAME}"
        ;;
    *)
        echo -e "${RED_BOLD}🌊 Error: Unsupported archive format: $ARCHIVE_PATH${RESET}"
        exit 1
        ;;
esac

# 在解压结果里找到主二进制
MAIN_BINARY=""
MAIN_BINARY=$(find "$TEMP_EXTRACT_DIR" -type f -name "$DEP_NAME" | head -1)

if [[ -z "$MAIN_BINARY" ]]; then
    # 如果找不到同名文件，则找第一个无后缀文件
    MAIN_BINARY=$(find "$TEMP_EXTRACT_DIR" -type f ! -name "*.*" | head -1)
fi

if [[ -z "$MAIN_BINARY" ]]; then
    echo -e "${RED_BOLD}🌊 Error: Could not find main binary for dependency '${DEP_NAME}'.${RESET}"
    exit 1
fi

# 将主二进制移动到目标目录
mv "$MAIN_BINARY" "$TARGET_DIR/${DEP_NAME}"

# 清理临时解压目录
rm -rf "$TEMP_EXTRACT_DIR"

# 设置执行权限
chmod +x "$TARGET_DIR/${DEP_NAME}"

echo -e "${GREEN}🌊 Dependency ${DEP_NAME}@${DEP_VERSION} installed successfully at: $TARGET_DIR/${DEP_NAME}${RESET}"
exit 0
