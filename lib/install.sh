#!/bin/bash

# MacWave 🌊 Official Installer (2.2.0)
# This script downloads wave.py, installs dependencies, and configures PATH.
# Usage: /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Sha0huaZhang/MacWave/2.1.0/lib/install.sh)"

set -e

BRANCH="2.2.0"
BASE_URL="https://raw.githubusercontent.com/Sha0huaZhang/MacWave/$BRANCH"
DATA_BASE_URL="https://raw.githubusercontent.com/Sha0huaZhang/MacWave/infosource"

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
# 辅助函数：校验自定义目录，防止路径穿越
# ==========================================

validate_custom_dir() {
    local dir="$1"

    # 1. 空输入
    if [[ -z "$dir" ]]; then
        echo -e "${RED_BOLD}🌊 Error: Empty path is not allowed.${RESET}" >&2
        return 1
    fi

    # 2. 拒绝包含 ".." 的路径（路径穿越）
    if [[ "$dir" == *".."* ]]; then
        echo -e "${RED_BOLD}🌊 Error: Path traversal ('..') is not allowed.${RESET}" >&2
        return 1
    fi

    # 3. 拒绝控制字符（\0、换行、回车、制表等）
    if [[ "$dir" == *$'\n'* ]] || [[ "$dir" == *$'\r'* ]] || [[ "$dir" == *$'\t'* ]]; then
        echo -e "${RED_BOLD}🌊 Error: Invalid control characters in path.${RESET}" >&2
        return 1
    fi

    # 4. 拒绝非 ASCII 字符（防止宽字节 / Unicode 变体 / 同形字绕过）
    if LC_ALL=C grep -q '[^a-zA-Z0-9/_.~ -]' <<< "$dir"; then
        echo -e "${RED_BOLD}🌊 Error: Path contains non-ASCII or invalid characters.${RESET}" >&2
        echo -e "${RED_BOLD}🌊 Only ASCII letters, digits, '/', '-', '_', '.', '~', and spaces are allowed.${RESET}" >&2
        return 1
    fi

    # 5. 展开 ~
    local expanded="${dir/#\~/$HOME}"

    # 6. 拒绝相对路径
    if [[ "$expanded" != /* ]]; then
        echo -e "${RED_BOLD}🌊 Error: Please use an absolute path (starting with / or ~).${RESET}" >&2
        return 1
    fi

    # 7. 拒绝连续斜杠
    if [[ "$expanded" == *"//"* ]]; then
        echo -e "${RED_BOLD}🌊 Error: Path contains consecutive slashes.${RESET}" >&2
        return 1
    fi

    # 8. 拒绝根目录
    if [[ "$expanded" == "/" ]]; then
        echo -e "${RED_BOLD}🌊 Error: Cannot install to root directory.${RESET}" >&2
        return 1
    fi

    echo "$expanded"
    return 0
}

# ==========================================
# 显示欢迎信息
# ==========================================

echo "🌊 Welcome to MacWave $BRANCH!"
echo "🌊 Installing from branch: $BRANCH"
echo ""

# ==========================================
# 检测系统架构
# ==========================================

ARCH=$(uname -m)
echo "🌊 Detected architecture: $ARCH"

# ==========================================
# 交互式目录选择
# ==========================================

if [[ "$ARCH" == "x86_64" ]] || [[ "$ARCH" == "amd64" ]]; then
    echo -e "${YELLOW}Where do you want to install MacWave? (Enter the number)${RESET}"
    echo "1. ~/.local/macwave"
    echo "2. /opt/macwave"
    echo "3. /usr/local/macwave"
    echo "4. other (enter custom directory)"
    echo ""
    echo -e "${YELLOW}Enter your choice:${RESET}"

    read -r choice < /dev/tty

    case "$choice" in
        1)
            BASE_DIR="$HOME/.local/macwave"
            ;;
        2)
            BASE_DIR="/opt/macwave"
            ;;
        3)
            BASE_DIR="/usr/local/macwave"
            ;;
        4)
            echo -e "${YELLOW}Please enter the installation directory:${RESET}"
            read -r custom_dir < /dev/tty
            validated=$(validate_custom_dir "$custom_dir") || exit 1
            BASE_DIR="$validated"
            ;;
        *)
            echo -e "${RED_BOLD}🌊 Invalid choice. Using default: ~/.local/macwave${RESET}"
            BASE_DIR="$HOME/.local/macwave"
            ;;
    esac
else
    echo -e "${YELLOW}Where do you want to install MacWave? (Enter the number)${RESET}"
    echo "1. ~/.local/macwave"
    echo "2. /opt/macwave"
    echo "3. other (enter custom directory)"
    echo ""
    echo -e "${YELLOW}Enter your choice:${RESET}"

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
            validated=$(validate_custom_dir "$custom_dir") || exit 1
            BASE_DIR="$validated"
            ;;
        *)
            echo -e "${RED_BOLD}🌊 Invalid choice. Using default: ~/.local/macwave${RESET}"
            BASE_DIR="$HOME/.local/macwave"
            ;;
    esac
fi

DISPLAY_DIR=$(home_to_tilde "$BASE_DIR")

# ==========================================
# 判断是否需要 sudo
# ==========================================

echo -e "${YELLOW}🌊 Granting temporary administrator access for installation...${RESET}"
sudo -v
USE_SUDO="sudo"

# ==========================================
# 创建目录（全用 sudo 创建）
# ==========================================

INSTALL_DIR="$BASE_DIR/bin"
LINKS_DIR="$BASE_DIR/links"
REPO_DIR="$BASE_DIR/pkg"
LIB_DIR="$BASE_DIR/lib"
DOWNLOAD_DIR="$BASE_DIR/downloads/tmp"
CONFIG_DIR="/opt/macwave_config"
CONFIG_FILE="$CONFIG_DIR/config.json"
VERSION_FILE="$CONFIG_DIR/VERSION.json"

sudo mkdir -p "$INSTALL_DIR"
sudo mkdir -p "$LINKS_DIR"
sudo mkdir -p "$REPO_DIR"
sudo mkdir -p "$LIB_DIR"
sudo mkdir -p "$DOWNLOAD_DIR"
sudo mkdir -p "$CONFIG_DIR"
sudo chmod 755 "$CONFIG_DIR"

# ==========================================
# 写入配置文件
# ==========================================

sudo tee "$CONFIG_FILE" > /dev/null << EOF
{
  "base_dir": "$BASE_DIR"
}
EOF

sudo tee "$VERSION_FILE" > /dev/null << EOF
{
  "version": "2.1.0",
  "components": {
    "installer": "2.1.0",
    "parser": "2.1.0"
  }
}
EOF

# ==========================================
# 把所有权交还给当前真实用户
# ==========================================

CURRENT_USER=$(whoami)

sudo chown -R "$CURRENT_USER": "$BASE_DIR"
sudo chown -R "$CURRENT_USER": "$CONFIG_DIR"
sudo chmod 755 "$CONFIG_DIR"
sudo chmod 644 "$CONFIG_FILE"
sudo chmod 644 "$VERSION_FILE"

echo "🌊 Configuration saved to /opt/macwave_config/config.json"
echo "🌊 Version saved to /opt/macwave_config/VERSION.json"

# ==========================================
# 删除旧版 repo.json
# ==========================================

OLD_JSON="$REPO_DIR/repo.json"
if [ -f "$OLD_JSON" ]; then
    echo "🌊 Removing old repo.json (legacy format)..."
    sudo rm -f "$OLD_JSON"
fi

# ==========================================
# 文件 URL
# ==========================================

WAVE_URL="$BASE_URL/lib/wave.py"
HELP_URL="$BASE_URL/lib/help.py"
CONFIGERROR_URL="$BASE_URL/lib/configerror.py"
PKGINSTALLER_URL="$BASE_URL/pkg/pkginstaller.py"
PKGINSTALLER_SH_URL="$BASE_URL/pkg/pkginstaller.sh"
PKGINFOHELPER_URL="$BASE_URL/pkg/pkginfohelper.py"
UNINSTALLER_URL="$BASE_URL/pkg/uninstaller.py"
PKGVERSIONPARSER_URL="$BASE_URL/pkg/pkgversionparser.py"
PKGUNZIP_URL="$BASE_URL/pkg/pkgunzip.sh"

DATA_PREFIX="$DATA_BASE_URL/pkg/pkginfo_${ARCH}"

# ==========================================
# 下载文件
# ==========================================

echo "🌊 Downloading wave..."
sudo curl -fsSL -o "$LIB_DIR/wave" "$WAVE_URL"
sudo chmod +x "$LIB_DIR/wave"

echo "🌊 Downloading help.py..."
sudo curl -fsSL -o "$LIB_DIR/help.py" "$HELP_URL"

echo "🌊 Downloading configerror.py..."
sudo curl -fsSL -o "$LIB_DIR/configerror.py" "$CONFIGERROR_URL"

echo "🌊 Downloading pkginstaller.py..."
sudo curl -fsSL -o "$REPO_DIR/pkginstaller.py" "$PKGINSTALLER_URL"

echo "🌊 Downloading pkginstaller.sh..."
sudo curl -fsSL -o "$REPO_DIR/pkginstaller.sh" "$PKGINSTALLER_SH_URL"
sudo chmod +x "$REPO_DIR/pkginstaller.sh"

echo "🌊 Downloading pkginfohelper.py..."
sudo curl -fsSL -o "$REPO_DIR/pkginfohelper.py" "$PKGINFOHELPER_URL"

echo "🌊 Downloading uninstaller.py..."
sudo curl -fsSL -o "$REPO_DIR/uninstaller.py" "$UNINSTALLER_URL"

echo "🌊 Downloading pkgversionparser.py..."
sudo curl -fsSL -o "$REPO_DIR/pkgversionparser.py" "$PKGVERSIONPARSER_URL"

echo "🌊 Downloading pkgunzip.sh..."
sudo curl -fsSL -o "$REPO_DIR/pkgunzip.sh" "$PKGUNZIP_URL"
sudo chmod +x "$REPO_DIR/pkgunzip.sh"

# ==========================================
# 把所有权交还给用户
# ==========================================

sudo chown -R "$CURRENT_USER": "$BASE_DIR"

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
    echo "export PATH=\"$INSTALL_DIR:$LINKS_DIR:$LIB_DIR:\$PATH\"" >> "$RC_FILE"
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
RC_DISPLAY=$(home_to_tilde "$RC_FILE")
echo "🌊 To use 'wave' immediately in this terminal, run:"
echo -e "${YELLOW}    source $RC_DISPLAY${RESET}"
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
    echo -e "${RED_BOLD}🌊 Cleaning up downloaded files...${RESET}"
    sudo rm -rf "$BASE_DIR"
    sudo rm -rf "$CONFIG_DIR"
    echo -e "${RED_BOLD}🌊 All files have been deleted.${RESET}"
    exit 1
fi