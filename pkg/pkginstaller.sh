#!/bin/bash

# pkginstaller.sh
# 接收 pkginstaller.py 传来的 4 行长字符串，执行校验、解压、安装、写库。

set -e

# -------------------- 颜色定义 --------------------

RED_BOLD='\033[1;31m'
GREEN='\033[32m'
YELLOW='\033[33m'
RESET='\033[0m'

# -------------------- 拆解长字符串 --------------------

INPUT_STR="$1"

if [[ -z "$INPUT_STR" ]]; then
    echo -e "${RED_BOLD}🌊 Error: No input received.${RESET}"
    exit 1
fi

lines=()
while IFS= read -r line; do
    lines+=("$line")
done <<< "$INPUT_STR"

ParsePkgName="${lines[0]}"
ParsePkgVersion="${lines[1]}"
ParsePkgSHA256="${lines[2]}"
ParseDir="${lines[3]}"

if [[ -z "$ParsePkgName" || -z "$ParsePkgVersion" || -z "$ParseDir" ]]; then
    echo -e "${RED_BOLD}🌊 Error: Incomplete package info.${RESET}"
    exit 1
fi

# -------------------- 定位脚本与目录 --------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UNZIP_SCRIPT="$SCRIPT_DIR/pkgunzip.sh"

if [[ ! -f "$UNZIP_SCRIPT" ]]; then
    echo -e "${RED_BOLD}🌊 Error: pkgunzip.sh not found.${RESET}"
    exit 1
fi

# -------------------- 定位下载好的原文件 --------------------

# Python 传过来的 ParseDir 是最终目标路径，
# 原文件在 BASE_DIR/downloads/tmp 下。
# 通过 ParseDir 反推 BASE_DIR。
BASE_DIR="$(dirname "$(dirname "$ParseDir")")"
DOWNLOAD_TMP="$BASE_DIR/downloads/tmp"

# 在下载临时目录里找最新生成的、带原始扩展名的文件
# 通过通配符匹配，排除 .partial 文件
ORIGINAL_FILE=""
for f in "$DOWNLOAD_TMP"/*; do
    if [[ -f "$f" && "$f" != *.partial ]]; then
        ORIGINAL_FILE="$f"
        break
    fi
done

if [[ -z "$ORIGINAL_FILE" || ! -f "$ORIGINAL_FILE" ]]; then
    echo -e "${RED_BOLD}🌊 Error: Download file not found in $DOWNLOAD_TMP.${RESET}"
    exit 1
fi

# -------------------- SHA256 校验 --------------------

if [[ -n "$ParsePkgSHA256" ]]; then
    echo "🌊 Verifying SHA256..."
    ACTUAL_SHA256=$(shasum -a 256 "$ORIGINAL_FILE" | awk '{print $1}')
    if [[ "$ACTUAL_SHA256" != "$ParsePkgSHA256" ]]; then
        echo -e "${RED_BOLD}🌊 Error: SHA256 verification failed. Removing corrupted file.${RESET}"
        echo -e "${RED_BOLD}🌊 Actual:   $ACTUAL_SHA256${RESET}"
        echo -e "${GREEN}🌊 Expected: $ParsePkgSHA256${RESET}"
        rm -f "$ORIGINAL_FILE"
        exit 1
    fi
    echo -e "${GREEN}🌊 SHA256 verification passed!${RESET}"
else
    echo -e "${YELLOW}🌊 Warning: No SHA256 provided, skipping verification.${RESET}"
fi

# -------------------- 解压 --------------------

echo "🌊 Extracting package..."
EXTRACT_DIR="$DOWNLOAD_TMP/extract_$$"

# 非压缩包（尤其是裸二进制）不交给 pkgunzip.sh，直接作为最终文件安装
case "$ORIGINAL_FILE" in
    *.zip|*.tar.gz|*.tgz|*.tar.bz2|*.tbz2|*.tar.xz|*.txz|*.tar|*.gz|*.bz2)
        mkdir -p "$EXTRACT_DIR"

        if ! bash "$UNZIP_SCRIPT" "$ORIGINAL_FILE" "$EXTRACT_DIR"; then
            echo -e "${RED_BOLD}🌊 Error: Extraction failed.${RESET}"
            rm -rf "$EXTRACT_DIR"
            exit 1
        fi

        # -------------------- 找出解压出的唯一二进制文件 --------------------

        BIN_COUNT=$(find "$EXTRACT_DIR" -type f | wc -l | tr -d ' ')
        if [[ "$BIN_COUNT" -eq 0 ]]; then
            echo -e "${RED_BOLD}🌊 Error: No binary found after extraction.${RESET}"
            rm -rf "$EXTRACT_DIR"
            exit 1
        elif [[ "$BIN_COUNT" -gt 1 ]]; then
            echo -e "${YELLOW}🌊 Warning: Multiple files found, using the first one.${RESET}"
        fi

        BIN_FILE=$(find "$EXTRACT_DIR" -type f | head -n 1)
        ;;
    *)
        # 裸二进制，直接使用下载到的原文件
        BIN_FILE="$ORIGINAL_FILE"
        ;;
esac

# -------------------- 移动到目标位置 --------------------

TARGET_DIR="$(dirname "$ParseDir")"
mkdir -p "$TARGET_DIR"

mv "$BIN_FILE" "$ParseDir"
chmod 755 "$ParseDir"

# -------------------- 清理临时文件 --------------------

rm -rf "$EXTRACT_DIR"
rm -f "$ORIGINAL_FILE"

# -------------------- 写入 installed.json --------------------

INSTALLED_DB="$BASE_DIR/pkg/installed.json"
mkdir -p "$(dirname "$INSTALLED_DB")"

python3 - "$INSTALLED_DB" "$ParsePkgName" "$ParsePkgVersion" "$ParseDir" << 'PYEOF'
import sys
import json
import fcntl
import time
from pathlib import Path

db_path = Path(sys.argv[1])
pkg_name = sys.argv[2]
pkg_version = sys.argv[3]
binary_path = sys.argv[4]

db_path.parent.mkdir(parents=True, exist_ok=True)

with open(db_path, 'a+') as f:
    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
    f.seek(0)
    try:
        content = f.read()
        installed = json.loads(content) if content else {}
    except json.JSONDecodeError:
        installed = {}
    installed[pkg_name] = {
        "version": pkg_version,
        "binary_path": binary_path,
        "installed_at": time.time()
    }
    f.seek(0)
    f.truncate()
    json.dump(installed, f, indent=2)
PYEOF

# -------------------- 输出成功 --------------------

echo -e "${GREEN}🌊 Successfully installed ${ParsePkgName}@${ParsePkgVersion}${RESET}"
DISPLAY_PATH="${ParseDir/$HOME/~}"
echo "🌊 Binary installed to: $DISPLAY_PATH"
exit 0
