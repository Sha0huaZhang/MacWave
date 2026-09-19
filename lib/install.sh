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

    if [[ -z "$dir" ]]; then
        echo -e "${RED_BOLD}🌊 Error: Empty path is not allowed.${RESET}" >&2
        return 1
    fi

    if [[ "$dir" == *".."* ]]; then
        echo -e "${RED_BOLD}🌊 Error: Path traversal ('..') is not allowed.${RESET}" >&2
        return 1
    fi

    if [[ "$dir" == *$'\n'* ]] || [[ "$dir" == *$'\r'* ]] || [[ "$dir" == *$'\t'* ]]; then
        echo -e "${RED_BOLD}🌊 Error: Invalid control characters in path.${RESET}" >&2
        return 1
    fi

    if LC_ALL=C grep -q '[^a-zA-Z0-9/_.~ -]' <<< "$dir"; then
        echo -e "${RED_BOLD}🌊 Error: Path contains non-ASCII or invalid characters.${RESET}" >&2
        echo -e "${RED_BOLD}🌊 Only ASCII letters, digits, '/', '-', '_', '.', '~', and spaces are allowed.${RESET}" >&2
        return 1
    fi

    local expanded="${dir/#\~/$HOME}"

    if [[ "$expanded" != /* ]]; then
        echo -e "${RED_BOLD}🌊 Error: Please use an absolute path (starting with / or ~).${RESET}" >&2
        return 1
    fi

    if [[ "$expanded" == *"//"* ]]; then
        echo -e "${RED_BOLD}🌊 Error: Path contains consecutive slashes.${RESET}" >&2
        return 1
    fi

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

CURRENT_USER=$(whoami)

if [[ "$BASE_DIR" == "$HOME"* ]]; then
    NEED_SUDO=false
else
    NEED_SUDO=true
fi

run_cmd() {
    if [[ "$NEED_SUDO" == "true" ]]; then
        sudo "$@"
    else
        "$@"
    fi
}

if [[ "$NEED_SUDO" == "true" ]]; then
    echo -e "${YELLOW}🌊 Granting temporary administrator access for installation...${RESET}"
    sudo -v
fi

# ==========================================
# 创建目录
# ==========================================

INSTALL_DIR="$BASE_DIR/bin"
LINKS_DIR="$BASE_DIR/links"
REPO_DIR="$BASE_DIR/pkg"
SURFBOARD_DIR="$BASE_DIR/surfboard"
LIB_DIR="$BASE_DIR/lib"
DOWNLOAD_DIR="$BASE_DIR/downloads/tmp"
CONFIG_DIR="/opt/macwave_config"
CONFIG_FILE="$CONFIG_DIR/config.json"
VERSION_FILE="$CONFIG_DIR/VERSION.json"

run_cmd mkdir -p "$INSTALL_DIR"
run_cmd mkdir -p "$LINKS_DIR"
run_cmd mkdir -p "$REPO_DIR"
run_cmd mkdir -p "$SURFBOARD_DIR"
run_cmd mkdir -p "$LIB_DIR"
run_cmd mkdir -p "$DOWNLOAD_DIR"
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
  "version": "2.2.0",
  "components": {
    "installer": "2.2.0",
    "parser": "2.2.0"
  }
}
EOF

# ==========================================
# 把所有权交还给当前真实用户
# ==========================================

if [[ "$NEED_SUDO" == "true" ]]; then
    sudo chown -R "$CURRENT_USER": "$BASE_DIR"
fi

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
    run_cmd rm -f "$OLD_JSON"
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

# 依赖处理相关文件全部从 2.2.0 分支拉取
DEPSINSTALLER_URL="$BASE_URL/surfboard/depsinstaller.py"
DEPSINSTALLER_SH_URL="$BASE_URL/surfboard/depsinstaller.sh"
DEPSMANAGER_SH_URL="$BASE_URL/surfboard/depsmanager.sh"
DEPSVERSIONPARSER_URL="$BASE_URL/surfboard/depsversionparser.py"
QUERIER_URL="$BASE_URL/surfboard/querier.py"
TAGGER_SH_URL="$BASE_URL/surfboard/tagger.sh"

# 纯数据从 infosource 拉取（下载时动态生成）
DATA_PREFIX="$DATA_BASE_URL/pkg/pkginfo_${ARCH}"

# ==========================================
# 下载文件
# ==========================================

echo "🌊 Downloading wave..."
run_cmd curl -fsSL -o "$LIB_DIR/wave" "$WAVE_URL"
run_cmd chmod +x "$LIB_DIR/wave"

echo "🌊 Downloading help.py..."
run_cmd curl -fsSL -o "$LIB_DIR/help.py" "$HELP_URL"

echo "🌊 Downloading configerror.py..."
run_cmd curl -fsSL -o "$LIB_DIR/configerror.py" "$CONFIGERROR_URL"

echo "🌊 Downloading pkginstaller.py..."
run_cmd curl -fsSL -o "$REPO_DIR/pkginstaller.py" "$PKGINSTALLER_URL"

echo "🌊 Downloading pkginstaller.sh..."
run_cmd curl -fsSL -o "$REPO_DIR/pkginstaller.sh" "$PKGINSTALLER_SH_URL"
run_cmd chmod +x "$REPO_DIR/pkginstaller.sh"

echo "🌊 Downloading pkginfohelper.py..."
run_cmd curl -fsSL -o "$REPO_DIR/pkginfohelper.py" "$PKGINFOHELPER_URL"

echo "🌊 Downloading uninstaller.py..."
run_cmd curl -fsSL -o "$REPO_DIR/uninstaller.py" "$UNINSTALLER_URL"

echo "🌊 Downloading pkgversionparser.py..."
run_cmd curl -fsSL -o "$REPO_DIR/pkgversionparser.py" "$PKGVERSIONPARSER_URL"

echo "🌊 Downloading pkgunzip.sh..."
run_cmd curl -fsSL -o "$REPO_DIR/pkgunzip.sh" "$PKGUNZIP_URL"
run_cmd chmod +x "$REPO_DIR/pkgunzip.sh"

echo "🌊 Downloading surfboard/depsinstaller.py..."
run_cmd curl -fsSL -o "$SURFBOARD_DIR/depsinstaller.py" "$DEPSINSTALLER_URL"

echo "🌊 Downloading surfboard/depsinstaller.sh..."
run_cmd curl -fsSL -o "$SURFBOARD_DIR/depsinstaller.sh" "$DEPSINSTALLER_SH_URL"
run_cmd chmod +x "$SURFBOARD_DIR/depsinstaller.sh"

echo "🌊 Downloading surfboard/depsmanager.sh..."
run_cmd curl -fsSL -o "$SURFBOARD_DIR/depsmanager.sh" "$DEPSMANAGER_SH_URL"
run_cmd chmod +x "$SURFBOARD_DIR/depsmanager.sh"

echo "🌊 Downloading surfboard/depsversionparser.py..."
run_cmd curl -fsSL -o "$SURFBOARD_DIR/depsversionparser.py" "$DEPSVERSIONPARSER_URL"

echo "🌊 Downloading surfboard/querier.py..."
run_cmd curl -fsSL -o "$SURFBOARD_DIR/querier.py" "$QUERIER_URL"

echo "🌊 Downloading surfboard/tagger.sh..."
run_cmd curl -fsSL -o "$SURFBOARD_DIR/tagger.sh" "$TAGGER_SH_URL"
run_cmd chmod +x "$SURFBOARD_DIR/tagger.sh"

# ==========================================
# 把所有权交还给用户（下载后再次确保）
# ==========================================

if [[ "$NEED_SUDO" == "true" ]]; then
    sudo chown -R "$CURRENT_USER": "$BASE_DIR"
fi

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
    run_cmd rm -rf "$BASE_DIR"
    sudo rm -rf "$CONFIG_DIR"
    echo -e "${RED_BOLD}🌊 All files have been deleted.${RESET}"
    exit 1
fi