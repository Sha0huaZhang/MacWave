#!/bin/bash

# shasum256.sh - 负责校验 SHA256
# 用法: bash shasum256.sh <文件路径> <期望SHA256>

RED_BOLD='\033[1;31m'
GREEN='\033[32m'
RESET='\033[0m'

FILE_PATH="$1"
EXPECTED_SHA256="$2"

if [[ -z "$FILE_PATH" || -z "$EXPECTED_SHA256" ]]; then
    echo -e "${RED_BOLD}🌊 Error: Missing file path or expected SHA256.${RESET}"
    exit 1
fi

if [[ ! -f "$FILE_PATH" ]]; then
    echo -e "${RED_BOLD}🌊 Error: File not found: $FILE_PATH${RESET}"
    exit 1
fi

ACTUAL_SHA256=$(shasum -a 256 "$FILE_PATH" | awk '{print $1}')

if [[ "$ACTUAL_SHA256" == "$EXPECTED_SHA256" ]]; then
    echo -e "${GREEN}🌊 SHA256 verification passed!${RESET}"
    exit 0
else
    echo -e "${RED_BOLD}🌊 Error: SHA256 verification failed.${RESET}"
    echo -e "${RED_BOLD}🌊 Actual:   $ACTUAL_SHA256${RESET}"
    echo -e "${GREEN}🌊 Expected: $EXPECTED_SHA256${RESET}"
    exit 1
fi
