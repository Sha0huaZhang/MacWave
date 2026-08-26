#!/bin/bash

# MacWave 🌊 Official Installer
# This script downloads wave.py, installs dependencies, and configures PATH.
# Usage: bash -c "$(curl -fsSL https://raw.githubusercontent.com/Sha0huaZhang/MacWave/2.0.0-beta/install.sh)"

set -e

BRANCH="2.0.0-beta"
BASE_URL="https://raw.githubusercontent.com/Sha0huaZhang/MacWave/$BRANCH"

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

echo "🌊 Welcome to MacWave 2.0!"
echo "🌊 Installing from branch: $BRANCH"
echo ""
echo -e "\033[33mWhere do you want to install MacWave? (Enter the number)\033[0m"
echo "1. ~/.local/macwave"
echo "2. /opt/macwave"
echo "3. other (enter custom directory)"
echo ""
echo -e "\033[33mEnter your choice:\033[0m"

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
        echo -e "\033[33mPlease enter the installation directory:\033[0m"
        read -r custom_dir < /dev/tty
        # 展开 ~ 如果用户输入了 ~
        BASE_DIR="${custom_dir/#\~/$HOME}"
        ;;
    *)
        echo "🌊 Invalid choice. Using default: ~/.local/macwave"
        BASE_DIR="$HOME/.local/macwave"
        ;;
esac

# 用于显示的用户友好路径
DISPLAY_DIR=$(home_to_tilde "$BASE_DIR")

# ==========================================
# 判断是否需要 sudo
# ==========================================

if [[ "$BASE_DIR" == "$HOME"* ]]; then
    USE_SUDO=""
else
    echo "🌊 Installing to $DISPLAY_DIR requires administrator privileges."
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
# 文件 URL
# ==========================================

WAVE_URL="$BASE_URL/wave.py"
PARSER_URL="$BASE_URL/repo/parser.rb"
PKGINFO_URL="$BASE_URL/repo/pkginfo_arm64.txt"

# ==========================================
# 检查 Ruby 版本（要求 >= 2.6.10）
# ==========================================

echo "🌊 Checking Ruby version..."
if ! command -v ruby &> /dev/null; then
    echo "🌊 Error: Ruby is not installed. Please install Ruby 2.6.10 or higher."
    exit 1
fi

RUBY_VERSION=$(ruby -e 'puts RUBY_VERSION')

# 用 Ruby 自身比较版本
if ! ruby -e "exit Gem::Version.new('$RUBY_VERSION') >= Gem::Version.new('2.6.10')" 2>/dev/null; then
    echo "🌊 Error: Ruby version $RUBY_VERSION is too old. Please upgrade to 2.6.10 or higher."
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

echo "🌊 Downloading pkginfo_arm64.txt..."
$USE_SUDO curl -fsSL -o "$REPO_DIR/pkginfo_arm64.txt" "$PKGINFO_URL"

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
        echo "🌊 Warning: 'rich' installation failed. Progress bar will not be available."
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
echo ""
echo "🌊 To use 'wave' immediately in this terminal, run:"
echo -e "\033[33m    source $RC_FILE\033[0m"
echo "🌊 Or simply open a new terminal window."
echo ""
echo "🌊 Try it now:"
echo "    wave install test_001"

# ==========================================
# 许可协议确认
# ==========================================

echo ""
echo -e "\033[33mPlease read the agreement before use (see bottom of https://macwave.org).\033[0m"
echo -e "\033[33mHave you read and agreed to the agreement? [Y/n]\033[0m"
read -r agreement < /dev/tty
if [[ $agreement =~ ^[Yy]$ ]]; then
    echo -e "\033[32mYou have agreed to the agreement. Installation continues.\033[0m"
else
    echo -e "\033[31mYou do not agree to the agreement. Installation stopped.\033[0m"
    exit 1
fi
