#!/bin/bash
# MacWave Uninstaller
# 卸载 MacWave 及清理环境配置

CONFIG_DIR="/opt/macwave_config"
ARCH=$(uname -m)

# 默认尝试删除的路径列表
BASE_DIRS=()

# 1. 如果配置文件存在，优先读取
if [ -f "$CONFIG_DIR/config.json" ]; then
    READ_DIR=$(python3 -c "import json; print(json.load(open('$CONFIG_DIR/config.json')).get('base_dir', ''))" 2>/dev/null)
    if [ -n "$READ_DIR" ]; then
        BASE_DIRS+=("$READ_DIR")
    fi
fi

# 2. 如果读取失败（或文件不存在），把所有可能的路径都加入列表
if [ ${#BASE_DIRS[@]} -eq 0 ]; then
    BASE_DIRS+=("$HOME/.local/macwave")
    BASE_DIRS+=("/opt/macwave")
    # Intel Mac 才有 /usr/local/macwave
    if [[ "$ARCH" == "x86_64" ]] || [[ "$ARCH" == "amd64" ]]; then
        BASE_DIRS+=("/usr/local/macwave")
    fi
fi

echo -e "\033[1;31mYou are deleting MacWave, are you sure? [Y/n]\033[0m"
read -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "🌊 Uninstall cancelled."
    exit 0
fi

# 逐个尝试删除所有可能的路径
for DIR in "${BASE_DIRS[@]}"; do
    if [ -d "$DIR" ]; then
        # 如果是系统级目录，需要 sudo
        if [[ "$DIR" == "$HOME"* ]]; then
            echo "🌊 Removing $DIR..."
            rm -rf "$DIR"
        else
            echo "🌊 Removing $DIR (with sudo)..."
            sudo rm -rf "$DIR"
        fi
    fi
done

# 删除配置目录
if [ -d "$CONFIG_DIR" ]; then
    echo "🌊 Removing $CONFIG_DIR..."
    sudo rm -rf "$CONFIG_DIR"
fi

# 清理 PATH 配置
for RC_FILE in "$HOME/.zshrc" "$HOME/.bashrc"; do
    if [ -f "$RC_FILE" ]; then
        sed -i '' '/# MacWave/d' "$RC_FILE" 2>/dev/null || true
        sed -i '' '/export PATH=".*macwave\/bin/d' "$RC_FILE" 2>/dev/null || true
        echo "🌊 Removed MacWave PATH entries from $RC_FILE"
    fi
done

echo ""
echo "🌊 MacWave has been uninstalled."
echo "🌊 Please restart your terminal to apply changes."

# ========== 删除自身脚本 ==========
rm -f "$0"
exit 0
