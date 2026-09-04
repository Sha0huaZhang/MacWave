#!/bin/bash

# depsmanager.sh - 2.1 依赖管理器
# 负责依赖计数、路径重定向、备份、以及依赖的反向查询

RED_BOLD='\033[1;31m'
GREEN='\033[32m'
YELLOW='\033[33m'
RESET='\033[0m'

# ==========================================
# 检查参数
# ==========================================

if [[ $# -lt 1 ]]; then
    echo -e "${RED_BOLD}🌊 Error: Missing arguments.${RESET}"
    exit 1
fi

ACTION="$1"

# ==========================================
# 工具函数
# ==========================================

# 获取依赖的路径（基于 config.json 里的 base_dir）
get_base_dir() {
    local config_path="/opt/macwave_config/config.json"
    if [[ -f "$config_path" ]]; then
        python3 -c "import json; print(json.load(open('$config_path')).get('base_dir', ''))" 2>/dev/null
    fi
}

# 计算目标绝对路径（替换 {config} 占位符）
resolve_path() {
    local template="$1"
    local base_dir="$2"
    echo "${template//\{config\}/$base_dir}"
}

# ==========================================
# 动作 1: 确认依赖是否被引用
# ==========================================

if [[ "$ACTION" == "check" ]]; then
    DEP_NAME="$2"
    DEP_VERSION="$3"
    BASE_DIR=$(get_base_dir)

    if [[ -z "$BASE_DIR" ]]; then
        echo -e "${RED_BOLD}🌊 Error: Configuration not found.${RESET}"
        exit 1
    fi

    DEP_DIR="$BASE_DIR/deps/${DEP_NAME}@${DEP_VERSION}"
    if [[ -d "$DEP_DIR" ]]; then
        echo -e "${GREEN}🌊 Dependency exists at: $DEP_DIR${RESET}"
        exit 0
    else
        echo -e "${RED_BOLD}🌊 Error: Dependency not found.${RESET}"
        exit 1
    fi
fi

# ==========================================
# 动作 2: 创建引用标记（计数 +1）
# ==========================================

if [[ "$ACTION" == "addref" ]]; then
    DEP_NAME="$2"
    DEP_VERSION="$3"
    REF_NAME="$4"
    REF_VERSION="$5"
    BASE_DIR=$(get_base_dir)

    if [[ -z "$BASE_DIR" ]]; then
        echo -e "${RED_BOLD}🌊 Error: Configuration not found.${RESET}"
        exit 1
    fi

    DEP_DIR="$BASE_DIR/deps/${DEP_NAME}@${DEP_VERSION}"
    mkdir -p "$DEP_DIR"

    # 创建或更新标记文件
    MARKER="$DEP_DIR/.dep_${REF_NAME}@${REF_VERSION}"
    if [[ -f "$MARKER" ]]; then
        echo -e "${YELLOW}🌊 Reference already exists.${RESET}"
    else
        touch "$MARKER"
        echo -e "${GREEN}🌊 Reference added.${RESET}"
    fi
    exit 0
fi

# ==========================================
# 动作 3: 删除引用标记（计数 -1）
# ==========================================

if [[ "$ACTION" == "delref" ]]; then
    DEP_NAME="$2"
    DEP_VERSION="$3"
    REF_NAME="$4"
    REF_VERSION="$5"
    BASE_DIR=$(get_base_dir)

    if [[ -z "$BASE_DIR" ]]; then
        echo -e "${RED_BOLD}🌊 Error: Configuration not found.${RESET}"
        exit 1
    fi

    DEP_DIR="$BASE_DIR/deps/${DEP_NAME}@${DEP_VERSION}"
    MARKER="$DEP_DIR/.dep_${REF_NAME}@${REF_VERSION}"

    if [[ -f "$MARKER" ]]; then
        rm -f "$MARKER"
        echo -e "${GREEN}🌊 Reference removed.${RESET}"
    else
        echo -e "${YELLOW}🌊 No reference found.${RESET}"
    fi
    exit 0
fi

# ==========================================
# 动作 4: 判断是否还有引用
# ==========================================

if [[ "$ACTION" == "hasrefs" ]]; then
    DEP_NAME="$2"
    DEP_VERSION="$3"
    BASE_DIR=$(get_base_dir)

    if [[ -z "$BASE_DIR" ]]; then
        echo -e "${RED_BOLD}🌊 Error: Configuration not found.${RESET}"
        exit 1
    fi

    DEP_DIR="$BASE_DIR/deps/${DEP_NAME}@${DEP_VERSION}"
    if [[ -d "$DEP_DIR" ]]; then
        count=$(find "$DEP_DIR" -maxdepth 1 -name ".dep_*" | wc -l)
        if [[ $count -gt 0 ]]; then
            echo -e "${GREEN}🌊 Has $count reference(s).${RESET}"
            exit 0
        else
            echo -e "${RED_BOLD}🌊 No references.${RESET}"
            exit 1
        fi
    fi
    exit 1
fi

# ==========================================
# 动作 5: 修改依赖路径
# ==========================================

if [[ "$ACTION" == "changepath" ]]; then
    PKG_NAME="$2"
    PKG_VERSION="$3"
    DEP_NAME="$4"
    DEP_VERSION="$5"
    NEW_PATH="$6"

    if [[ "$NEW_PATH" == *".."* ]]; then
        echo -e "${RED_BOLD}🌊 Error: Relative paths are not allowed.${RESET}"
        exit 1
    fi

    BASE_DIR=$(get_base_dir)
    if [[ -z "$BASE_DIR" ]]; then
        echo -e "${RED_BOLD}🌊 Error: Configuration not found.${RESET}"
        exit 1
    fi

    # 找到包目录下的 _path 文件
    PKG_DIR="$BASE_DIR/bin/${PKG_NAME}@${PKG_VERSION}"
    PATH_FILE="$PKG_DIR/_path"

    if [[ ! -f "$PATH_FILE" ]]; then
        echo -e "${RED_BOLD}🌊 Error: Path file not found.${RESET}"
        exit 1
    fi

    # 备份默认路径
    if [[ ! -f "$PATH_FILE.bak_default" ]]; then
        cp "$PATH_FILE" "$PATH_FILE.bak_default"
        echo -e "${GREEN}🌊 Default path backed up.${RESET}"
    fi

    # 替换为新路径（假设一行只有一个依赖）
    NEW_CONTENT="$NEW_PATH"
    sed -i '' "s|^.*$|$NEW_CONTENT|" "$PATH_FILE"

    echo -e "${GREEN}🌊 Path updated successfully.${RESET}"
    exit 0
fi

# ==========================================
# 动作 6: 恢复默认路径
# ==========================================

if [[ "$ACTION" == "restorepath" ]]; then
    PKG_NAME="$2"
    PKG_VERSION="$3"
    DEP_NAME="$4"
    DEP_VERSION="$5"
    BASE_DIR=$(get_base_dir)

    if [[ -z "$BASE_DIR" ]]; then
        echo -e "${RED_BOLD}🌊 Error: Configuration not found.${RESET}"
        exit 1
    fi

    PKG_DIR="$BASE_DIR/bin/${PKG_NAME}@${PKG_VERSION}"
    PATH_FILE="$PKG_DIR/_path"

    if [[ ! -f "$PATH_FILE.bak_default" ]]; then
        echo -e "${RED_BOLD}🌊 Error: No default backup found.${RESET}"
        exit 1
    fi

    # 备份当前为 bak_1, bak_2 等
    i=1
    while [[ -f "$PATH_FILE.bak_$i" ]]; do
        i=$((i+1))
    done
    cp "$PATH_FILE" "$PATH_FILE.bak_$i"

    # 恢复默认
    cp "$PATH_FILE.bak_default" "$PATH_FILE"
    echo -e "${GREEN}🌊 Default path restored.${RESET}"
    exit 0
fi

# ==========================================
# 默认行为
# ==========================================

echo -e "${RED_BOLD}🌊 Error: Unknown action '$ACTION'.${RESET}"
exit 1
