#!/usr/bin/env python3

# querier.py
# 查询依赖是否已安装。
# 依赖目录结构：BASE_DIR/deps/{依赖引用名}/{依赖引用名}@{版本号}/

import json
import sys
from pathlib import Path

# -------------------- 颜色定义 --------------------

RED_BOLD = '\033[1;31m'
RESET = '\033[0m'

# -------------------- 配置加载 --------------------

CONFIG_FILE = Path("/opt/macwave_config/config.json")


def load_config():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                base_dir = config.get("base_dir")
                if base_dir:
                    return Path(base_dir)
        except Exception:
            pass
    print(f"{RED_BOLD}🌊 Error: Configuration file not found or invalid.{RESET}")
    print(f"{RED_BOLD}🌊 Please run the install script again to reinstall MacWave.{RESET}")
    sys.exit(1)


BASE_DIR = load_config()
DEPS_DIR = BASE_DIR / "deps"


# -------------------- 查询 --------------------

def dep_owner_dir(dep_name):

    # 依赖名目录，同一依赖的所有版本都放在这里。

    return DEPS_DIR / dep_name


def dep_dir(dep_name, dep_version):

    # 依赖具体版本的安装目录。

    return dep_owner_dir(dep_name) / f"{dep_name}@{dep_version}"


def is_installed(dep_name, dep_version):

    # 安装目录存在、且已写入 _DEPS 才算安装完成。
    # _DEPS 是安装流程的最后一步，用它判断可避免中途失败留下的空目录被误判为已安装。

    target_dir = dep_dir(dep_name, dep_version)
    if not target_dir.is_dir():
        return False
    return (target_dir / "_DEPS").is_file()


def installed_versions(dep_name):

    # 列出某个依赖在本地的所有已安装版本目录名，如 ["openssl@3.0.15"]。

    owner_dir = dep_owner_dir(dep_name)
    if not owner_dir.is_dir():
        return []
    return sorted([entry.name for entry in owner_dir.iterdir() if entry.is_dir()])
