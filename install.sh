#!/bin/bash

# MacWave 🌊 Official Installer
# This script downloads wave.py, installs dependencies, and configures PATH.
# Usage: bash -c "$(curl -fsSL https://raw.githubusercontent.com/Sha0huaZhang/MacWave/2.0.0-beta/install.sh)"

set -e

BRANCH="2.0.0-beta"
BASE_URL="https://raw.githubusercontent.com/Sha0huaZhang/MacWave/$BRANCH"

# ==========================================
# 颜色定义
# ==========================================

RED_BOLD='\033[1;31m'
GREEN='\033[32m'
YELLOW='\033[33m'
RESET='\033[0m'

# ==========================================
# 辅助函数：将路径中的 $HOME 替换为 ~
# ==========================================

home_to_tilde() {
    local path="$1"
    if [[ "$path" == "$HOME"* ]]; then
        echo "~${path#$HOME}"
    else
        echo "$path"
    fi
}

# ==========================================
# 交互式目录选择（从 /dev/tty 读取）
# ==========================================

echo "🌊 Welcome to MacWave 2.0.0-beta1(237B1401)!"
echo "🌊 Installing from branch: $BRANCH"
echo ""
echo -e "${YELLOW}Where do you want to install MacWave? (Enter the number)${RESET}"
echo "1. ~/.local/macwave"
echo "2. /opt/macwave"
echo "3. other (enter custom directory)"
echo ""
echo -e "${YELLOW}Enter your choice:${RESET}"

# 从 /dev/tty 读取用户输入
read -r choice < /dev/tty

case "$choice" in
    1)
        BASE_DIR="$HOME/.local/macwave"
        ;;
    2)
        BASE_DIR="/opt/macwave"
        ;;
    3)
        echo -e "${YELLOW}Please enter the installation directory:${RESET}"
        read -r custom_dir < /dev/tty
        BASE_DIR="${custom_dir/#\~/$HOME}"
        ;;
    *)
        echo -e "${RED_BOLD}🌊 Invalid choice. Using default: ~/.local/macwave${RESET}"
        BASE_DIR="$HOME/.local/macwave"
        ;;
esac

DISPLAY_DIR=$(home_to_tilde "$BASE_DIR")

# ==========================================
# 判断是否需要 sudo
# ==========================================

if [[ "$BASE_DIR" == "$HOME"* ]]; then
    USE_SUDO=""
else
    echo -e "${YELLOW}🌊 Installing to $DISPLAY_DIR requires administrator privileges.${RESET}"
    sudo -v
    USE_SUDO="sudo"
fi

# ==========================================
# 创建目录
# ==========================================

INSTALL_DIR="$BASE_DIR/bin"
REPO_DIR="$BASE_DIR/repo"
CONFIG_DIR="$HOME/.config/macwave"
CONFIG_FILE="$CONFIG_DIR/config.json"

$USE_SUDO mkdir -p "$INSTALL_DIR"
$USE_SUDO mkdir -p "$REPO_DIR"
mkdir -p "$CONFIG_DIR"

# ==========================================
# 写入配置文件
# ==========================================

cat > "$CONFIG_FILE" << EOF
{
  "base_dir": "$BASE_DIR"
}
EOF

CONFIG_DISPLAY=$(home_to_tilde "$CONFIG_FILE")
echo "🌊 Configuration saved to $CONFIG_DISPLAY"

# ==========================================
# 删除旧版 repo.json（如果存在）
# ==========================================

OLD_JSON="$REPO_DIR/repo.json"
if [ -f "$OLD_JSON" ]; then
    echo "🌊 Removing old repo.json (legacy format)..."
    $USE_SUDO rm -f "$OLD_JSON"
fi

# ==========================================
# 检测系统架构
# ==========================================

ARCH=$(uname -m)
echo "🌊 Detected architecture: $ARCH"
case "$ARCH" in
    arm64|aarch64)
        PKGINFO="pkginfo_arm64.txt"
        ;;
    x86_64|amd64)
        PKGINFO="pkginfo_amd64.txt"
        ;;
    *)
        echo -e "${RED_BOLD}🌊 Warning: Unsupported architecture '$ARCH'. Defaulting to arm64.${RESET}"
        PKGINFO="pkginfo_arm64.txt"
        ;;
esac

# ==========================================
# 文件 URL
# ==========================================

WAVE_URL="$BASE_URL/wave.py"
PARSER_URL="$BASE_URL/repo/parser.rb"
PKGINFO_URL="$BASE_URL/repo/$PKGINFO"

# ==========================================
# 检查 Ruby 版本（要求 >= 2.6.10）
# ==========================================

echo "🌊 Checking Ruby version..."
if ! command -v ruby &> /dev/null; then
    echo -e "${RED_BOLD}🌊 Error: Ruby is not installed. Please install Ruby 2.6.10 or higher.${RESET}"
    exit 1
fi

RUBY_VERSION=$(ruby -e 'puts RUBY_VERSION')

if ! ruby -e "exit Gem::Version.new('$RUBY_VERSION') >= Gem::Version.new('2.6.10')" 2>/dev/null; then
    echo -e "${RED_BOLD}🌊 Error: Ruby version $RUBY_VERSION is too old. Please upgrade to 2.6.10 or higher.${RESET}"
    exit 1
fi
echo "🌊 Ruby version $RUBY_VERSION is OK."

# ==========================================
# 下载文件
# ==========================================

echo "🌊 Downloading wave.py..."
$USE_SUDO curl -fsSL -o "$INSTALL_DIR/wave" "$WAVE_URL"
$USE_SUDO chmod +x "$INSTALL_DIR/wave"

echo "🌊 Downloading parser.rb..."
$USE_SUDO curl -fsSL -o "$REPO_DIR/parser.rb" "$PARSER_URL"
$USE_SUDO chmod +x "$REPO_DIR/parser.rb"

echo "🌊 Downloading $PKGINFO..."
$USE_SUDO curl -fsSL -o "$REPO_DIR/$PKGINFO" "$PKGINFO_URL"

# ==========================================
# 安装 Python 依赖
# ==========================================

echo "🌊 Checking Python dependencies..."
if ! python3 -c "import requests" 2>/dev/null; then
    echo "🌊 Installing 'requests' library..."
    pip3 install requests --quiet
else
    echo "🌊 'requests' library is already installed."
fi

if ! python3 -c "from packaging.version import parse" 2>/dev/null; then
    echo "🌊 Installing 'packaging' library..."
    pip3 install packaging --quiet
else
    echo "🌊 'packaging' library is already installed."
fi

if ! python3 -c "import rich" 2>/dev/null; then
    echo "🌊 Installing 'rich' library for progress bar..."
    if pip3 install rich --quiet; then
        echo "🌊 'rich' installed successfully."
    else
        echo -e "${RED_BOLD}🌊 Warning: 'rich' installation failed. Progress bar will not be available.${RESET}"
        echo "🌊 You can install it manually later: pip3 install rich"
    fi
else
    echo "🌊 'rich' library is already installed."
fi

# ==========================================
# 添加到 PATH
# ==========================================

if [[ "$SHELL" == *"zsh"* ]]; then
    RC_FILE="$HOME/.zshrc"
elif [[ "$SHELL" == *"bash"* ]]; then
    RC_FILE="$HOME/.bashrc"
else
    RC_FILE="$HOME/.profile"
fi

if ! grep -q "$INSTALL_DIR" "$RC_FILE" 2>/dev/null; then
    echo "🌊 Adding MacWave to PATH in $RC_FILE..."
    echo "" >> "$RC_FILE"
    echo "# MacWave" >> "$RC_FILE"
    echo "export PATH=\"$INSTALL_DIR:\$PATH\"" >> "$RC_FILE"
else
    echo "🌊 MacWave is already in your PATH."
fi

# ==========================================
# 完成信息
# ==========================================

echo ""
echo "🌊 Installation complete!"
echo "🌊 MacWave installed to: $DISPLAY_DIR"
echo "🌊 Architecture: $ARCH"
echo ""
echo "🌊 To use 'wave' immediately in this terminal, run:"
echo -e "${YELLOW}    source $RC_FILE${RESET}"
echo "🌊 Or simply open a new terminal window."
echo ""
echo "🌊 Try it now:"
echo "    wave install test_001"

# ==========================================
# 许可协议确认
# ==========================================

echo ""
echo -e "${YELLOW}Please read the agreement before use (see bottom of https://macwave.org).${RESET}"
echo -e "${YELLOW}Have you read and agreed to the agreement? [Y/n]${RESET}"
read -r agreement < /dev/tty
if [[ $agreement =~ ^[Yy]$ ]]; then
    echo -e "${GREEN}You have agreed to the agreement. Installation continues.${RESET}"
else
    echo -e "${RED_BOLD}You do not agree to the agreement. Installation stopped.${RESET}"
    exit 1
fi
