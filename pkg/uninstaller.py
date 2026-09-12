#!/usr/bin/env python3

# uninstaller.py

import os
import sys
import json
import shutil
from pathlib import Path


# -------------------- 颜色定义 --------------------

RED_BOLD = '\033[1;31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
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
BIN_DIR = BASE_DIR / "bin"
INSTALLED_DB = BASE_DIR / "pkg" / "installed.json"


# -------------------- 依赖库检查 --------------------

try:
    from pkgversionparser import sort_versions
except ImportError:
    print(f"{RED_BOLD}🌊 Error: 'pkgversionparser' module is not available.{RESET}")
    sys.exit(1)


# -------------------- 辅助函数 --------------------

def to_tilde(path):
    # 把 $HOME 前缀显示成 ~
    home = os.path.expanduser("~")
    path = str(path)
    if path.startswith(home):
        return "~" + path[len(home):]
    return path


def load_installed():
    if INSTALLED_DB.exists():
        try:
            with open(INSTALLED_DB, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_installed(installed):
    INSTALLED_DB.parent.mkdir(parents=True, exist_ok=True)
    with open(INSTALLED_DB, 'w') as f:
        json.dump(installed, f, indent=2)


def find_installed_versions(pkg_name):
    # 扫描 bin 目录，返回该包所有已安装版本（降序，排除 .bak 备份）
    if not BIN_DIR.exists():
        return []
    prefix = f"{pkg_name}@"
    versions = []
    for entry in BIN_DIR.iterdir():
        name = entry.name
        if not name.startswith(prefix):
            continue
        version = name[len(prefix):]
        if not version or version.endswith(".bak"):
            continue
        versions.append(version)
    return sort_versions(versions)


# -------------------- 删除动作 --------------------

def remove_one(pkg_name, version, installed):
    # 删除单个 <包名>@<版本号>（含 .bak），并同步 installed.json
    target = BIN_DIR / f"{pkg_name}@{version}"
    backup = BIN_DIR / f"{pkg_name}@{version}.bak"

    record = installed.get(pkg_name)
    if record and record.get("version") == version and record.get("binary_path"):
        display_path = record["binary_path"]
    else:
        display_path = target

    print(f"🌊 Deleting {to_tilde(display_path)}...")

    if target.is_dir():
        shutil.rmtree(target)
    elif target.exists():
        target.unlink()

    if backup.is_dir():
        shutil.rmtree(backup)
    elif backup.exists():
        backup.unlink()

    # 只有记录版本与删除版本一致时才移除记录，避免误删其他版本
    if record and record.get("version") == version:
        del installed[pkg_name]
        return True
    return False


def uninstall_versions(pkg_name, versions):
    installed = load_installed()
    changed = False
    for version in versions:
        changed = remove_one(pkg_name, version, installed) or changed
    if changed:
        save_installed(installed)
    for version in versions:
        print(f"{GREEN}🌊 Successfully uninstalled {pkg_name}@{version}.{RESET}")


# -------------------- 交互式选择 --------------------

def select_versions(pkg_name, versions):
    print(f"🌊 Multiple versions found for '{pkg_name}':")
    for index, version in enumerate(versions, start=1):
        print(f"🌊 - {index}. {version}")
    print("🌊 Enter the number(s) to uninstall (separate by @ or space):")

    try:
        choice = input().strip()
    except (EOFError, KeyboardInterrupt):
        print("🌊 Operation cancelled by user.")
        sys.exit(130)

    selected = []
    for token in choice.replace('@', ' ').split():
        if not token.isdigit() or not (1 <= int(token) <= len(versions)):
            print(f"{RED_BOLD}🌊 Error: Invalid selection '{token}'.{RESET}")
            sys.exit(1)
        selected.append(versions[int(token) - 1])

    if not selected:
        print("🌊 Nothing selected.")
        sys.exit(0)

    return selected


# -------------------- 命令入口 --------------------

def handle_uninstall(input_string):
    parts = input_string.split()
    if len(parts) < 3:
        print(f"{RED_BOLD}🌊 Error: Missing package name.{RESET}")
        sys.exit(1)

    raw_pkg = parts[2]

    # 1. 不带 @：列出所有版本让用户选择
    if '@' not in raw_pkg:
        pkg_name = raw_pkg
        versions = find_installed_versions(pkg_name)
        if not versions:
            print(f"{RED_BOLD}🌊 Error: Package '{pkg_name}' is not installed.{RESET}")
            sys.exit(1)
        uninstall_versions(pkg_name, select_versions(pkg_name, versions))
        return

    # 2. 带 @：拆分包名与版本号
    pkg_name, *raw_versions = raw_pkg.split('@')
    raw_versions = [v for v in raw_versions if v]

    if not raw_versions:
        print(f"{RED_BOLD}🌊 Error: Missing version number.{RESET}")
        sys.exit(1)

    # 2.1 通配符 *：卸载所有版本
    if raw_versions == ['*']:
        versions = find_installed_versions(pkg_name)
        if not versions:
            print(f"{RED_BOLD}🌊 Error: Package '{pkg_name}' is not installed.{RESET}")
            sys.exit(1)
        uninstall_versions(pkg_name, versions)
        return

    # 2.2 指定一个或多个版本：批量删除
    installed_versions = find_installed_versions(pkg_name)
    targets = [v for v in raw_versions if v in installed_versions]
    missing = [v for v in raw_versions if v not in installed_versions]

    if not targets:
        print(f"{RED_BOLD}🌊 Error: Package '{pkg_name}' is not installed.{RESET}")
        sys.exit(1)

    for version in missing:
        print(f"{YELLOW}🌊 Warning: {pkg_name}@{version} is not installed, skipping.{RESET}")

    uninstall_versions(pkg_name, targets)


if __name__ == "__main__":
    try:
        input_string = " ".join(sys.argv[1:])
        handle_uninstall(input_string)
    except KeyboardInterrupt:
        print("🌊 Operation cancelled by user.")
        sys.exit(130)
