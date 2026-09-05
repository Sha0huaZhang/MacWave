#!/usr/bin/env python3
"""
MacWave Querier Module
负责依赖查询、路径管理、卸载判断等高级功能。
检索和下载阶段不使用 _deps, _path, .dep，仅查询和运行阶段使用。
"""

import os
import json
import shutil
import time
import subprocess
import sys
from pathlib import Path

CONFIG_FILE = Path("/opt/macwave_config/config.json")

RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
BOLD = '\033[1m'
RESET = '\033[0m'

def load_base_dir():
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                base_dir = config.get("base_dir")
                if base_dir:
                    return Path(base_dir)
        except Exception:
            pass
    return Path.home() / ".local" / "macwave"

BASE_DIR = load_base_dir()
INSTALL_DIR = BASE_DIR / "bin"
DEPS_DIR = BASE_DIR / "deps"
INSTALLED_DB = BASE_DIR / "pkg" / "installed.json"


def _load_installed():
    if INSTALLED_DB.exists():
        with open(INSTALLED_DB, 'r') as f:
            return json.load(f)
    return {}


def _get_arch():
    import platform
    machine = platform.machine().lower()
    if machine in ['arm64', 'aarch64']:
        return 'arm64'
    elif machine in ['x86_64', 'amd64']:
        return 'amd64'
    return 'unknown'


def _get_data_base_url():
    return "https://raw.githubusercontent.com/Sha0huaZhang/MacWave/infosource"


def to_tilde(path):
    """将绝对路径转换为 ~ 形式"""
    home = os.path.expanduser("~")
    if str(path).startswith(home):
        return "~" + str(path)[len(home):]
    return str(path)


def _read_deps(pkg_dir):
    """读取包目录下的 _deps 文件"""
    deps_file = pkg_dir / "_deps"
    if not deps_file.exists():
        return []
    with open(deps_file, 'r') as f:
        return [line.strip() for line in f if line.strip()]


def _read_path(pkg_dir):
    """读取包目录下的 _path 文件"""
    path_file = pkg_dir / "_path"
    if not path_file.exists():
        return []
    with open(path_file, 'r') as f:
        return [line.strip() for line in f if line.strip()]


def _has_marker(dep_dir, pkg_name, pkg_version):
    """检查依赖目录下是否有 .dep_包@版本 标记"""
    marker = dep_dir / f".dep_{pkg_name}@{pkg_version}"
    return marker.exists()


def list_deps(detailed=False):
    """列出所有已安装的依赖（通过 .dep 标记判断）"""
    if not DEPS_DIR.exists():
        print("🌊 No dependencies installed yet.")
        return

    deps = {}
    for dep_dir in DEPS_DIR.iterdir():
        if dep_dir.is_dir():
            parts = dep_dir.name.split('@')
            if len(parts) == 2:
                name, version = parts
                if name not in deps:
                    deps[name] = []
                deps[name].append(version)

    for name in sorted(deps.keys()):
        versions = deps[name]
        if detailed:
            print(f"🌊 - {name}@{versions[0]}")
            for v in versions[1:]:
                padding = len(f"🌊 - {name}")
                print(f"{' ' * padding}@{v}")
        else:
            print(f"🌊 - {name}")


def query_deps(package, version=None, detailed=False):
    """查询某个包的依赖，通过 _deps 读取，_path 判断是否已安装"""
    if version:
        pkg_dir = INSTALL_DIR / f"{package}@{version}"
    else:
        pkg_dirs = list(INSTALL_DIR.glob(f"{package}@*"))
        if not pkg_dirs:
            print(f"🌊 Package '{package}' not found.")
            return
        pkg_dir = pkg_dirs[0]

    deps = _read_deps(pkg_dir)
    paths = _read_path(pkg_dir)

    if not deps:
        print(f"🌊 Package '{package}' has no dependencies.")
        return

    # 检查每个依赖是否安装
    for dep in deps:
        if '@' in dep:
            name, ver = dep.split('@', 1)
            dep_dir = DEPS_DIR / f"{name}@{ver}"
            if detailed:
                if dep_dir.exists():
                    print(f"{GREEN}🌊 - {name}@{ver}{RESET}")
                else:
                    print(f"{RED}🌊 - {name}@{ver}  # 缺失{RESET}")
            else:
                print(f"🌊 - {name}@{ver}")


def query_pkg_reverse(dep_name, dep_version=None):
    """反向查询：哪个包依赖了某个库"""
    installed = _load_installed()

    if dep_version:
        dep_key = f"{dep_name}@{dep_version}"
        for pkg_name, info in installed.items():
            pkg_dir = INSTALL_DIR / f"{pkg_name}@{info.get('version', '')}"
            deps = _read_deps(pkg_dir)
            if dep_key in deps:
                print(f"🌊 - {pkg_name}@{info.get('version', '')}")
    else:
        for pkg_name, info in installed.items():
            pkg_dir = INSTALL_DIR / f"{pkg_name}@{info.get('version', '')}"
            deps = _read_deps(pkg_dir)
            for dep in deps:
                if dep.startswith(f"{dep_name}@"):
                    dep_ver = dep.split('@', 1)[1]
                    print(f"🌊 @{dep_ver}")
                    print(f"    - {pkg_name}@{info.get('version', '')}")


def change_dep_path(package, version, dep, new_path):
    """修改依赖路径（通过修改 _path 文件）"""
    if not new_path:
        print(f"{RED}🌊 Error: Missing new path.{RESET}")
        return

    if '..' in new_path:
        print(f"{RED}🌊 Error: Relative paths are not allowed. Please use an absolute path.{RESET}")
        return

    pkg_dir = INSTALL_DIR / f"{package}@{version}"
    path_file = pkg_dir / "_path"

    if not path_file.exists():
        print(f"{RED}🌊 Error: Path file not found.{RESET}")
        return

    # 备份默认路径
    if not (pkg_dir / "_path.bak_default").exists():
        shutil.copy2(path_file, pkg_dir / "_path.bak_default")

    # 写入新路径
    with open(path_file, 'w') as f:
        f.write(new_path)

    print(f"{GREEN}🌊 Path updated for {package}@{version}.{RESET}")


def restore_default_path(package, version, dep):
    """恢复默认路径（通过读取 _path.bak_default）"""
    pkg_dir = INSTALL_DIR / f"{package}@{version}"
    path_file = pkg_dir / "_path"
    default_bak = pkg_dir / "_path.bak_default"

    if not default_bak.exists():
        print(f"{RED}🌊 Error: No default backup found.{RESET}")
        return

    # 备份当前为 bak_1, bak_2...
    i = 1
    while (pkg_dir / f"_path.bak_{i}").exists():
        i += 1
    shutil.copy2(path_file, pkg_dir / f"_path.bak_{i}")

    # 恢复默认
    shutil.copy2(default_bak, path_file)
    print(f"{GREEN}🌊 Default path restored.{RESET}")


def delete_path_record(package, version=None, force=False):
    """删除路径备份记录（通过 _path.bak 文件）"""
    if version:
        pkg_dir = INSTALL_DIR / f"{package}@{version}"
    else:
        pkg_dirs = list(INSTALL_DIR.glob(f"{package}@*"))
        if not pkg_dirs:
            print(f"{RED}🌊 Package '{package}' not found.{RESET}")
            return
        pkg_dir = pkg_dirs[0]

    backups = sorted(pkg_dir.glob("_path.bak_*"))
    if force:
        backups = sorted(pkg_dir.glob("_path.bak_*"))
    else:
        backups = [b for b in backups if not b.name.endswith("default")]

    if not backups:
        print("🌊 No backup records to delete.")
        return

    print("🌊 Found the following backup records:")
    for b in backups:
        print(f"  - {b.name}")

    response = input(f"🌊 Delete these records? [Y/n]: ").strip()
    if response.lower() == 'y':
        for b in backups:
            b.unlink()
            print(f"🌊 Deleted: {b.name}")
        print(f"{GREEN}🌊 Path records deleted.{RESET}")
    else:
        print("🌊 Operation cancelled.")


def uninstall_deps(dep_name=None, dep_version=None, unnecessary=False):
    """卸载依赖（通过 .dep 标记判断引用计数）"""
    if unnecessary:
        if not DEPS_DIR.exists():
            print("🌊 No dependencies installed.")
            return

        unnecessary_deps = []
        for dep_dir in DEPS_DIR.iterdir():
            if dep_dir.is_dir():
                # 检查是否有任何 .dep 标记
                markers = list(dep_dir.glob(".dep_*"))
                if not markers:
                    unnecessary_deps.append(dep_dir)

        if not unnecessary_deps:
            print("🌊 No unnecessary dependencies found.")
            return

        print("🌊 The following dependencies are unused:")
        for d in unnecessary_deps:
            print(f"  - {d.name}")

        response = input(f"🌊 Delete all unused dependencies? [Y/n]: ").strip()
        if response.lower() == 'y':
            for d in unnecessary_deps:
                shutil.rmtree(d)
                print(f"🌊 Deleted: {d.name}")
            print(f"{GREEN}🌊 Unnecessary dependencies removed.{RESET}")
        else:
            print("🌊 Operation cancelled.")
        return

    if not dep_name:
        print(f"{RED}🌊 Error: Missing dependency name.{RESET}")
        return

    if dep_version:
        dep_dir = DEPS_DIR / f"{dep_name}@{dep_version}"
        if dep_dir.exists():
            response = input(f"🌊 Are you sure you want to uninstall {dep_name}@{dep_version}? [Y/n]: ").strip()
            if response.lower() == 'y':
                shutil.rmtree(dep_dir)
                print(f"{GREEN}🌊 Dependency {dep_name}@{dep_version} uninstalled.{RESET}")
            else:
                print("🌊 Operation cancelled.")
        else:
            print(f"{RED}🌊 Dependency {dep_name}@{dep_version} not found.{RESET}")
    else:
        dep_dirs = list(DEPS_DIR.glob(f"{dep_name}@*"))
        if not dep_dirs:
            print(f"{RED}🌊 Dependency '{dep_name}' not found.{RESET}")
            return
        print("🌊 Found the following versions:")
        for d in dep_dirs:
            print(f"  - {d.name}")
        response = input(f"🌊 Are you sure you want to delete all versions of '{dep_name}'? [Y/n]: ").strip()
        if response.lower() == 'y':
            for d in dep_dirs:
                shutil.rmtree(d)
                print(f"🌊 Deleted: {d.name}")
            print(f"{GREEN}🌊 Dependency '{dep_name}' uninstalled.{RESET}")
        else:
            print("🌊 Operation cancelled.")


def main():
    import sys
    if len(sys.argv) < 2:
        print("Usage: python3 querier.py <command> [args]")
        return

    command = sys.argv[1]
    args = sys.argv[2:]

    if command == "list_deps":
        detailed = False
        if '-d' in args or '--detailed' in args:
            detailed = True
        list_deps(detailed)
    elif command == "query_deps":
        pkg = args[0] if args else ""
        ver = None
        detailed = False
        if '-d' in args or '--detailed' in args:
            detailed = True
        if '@' in pkg:
            pkg, ver = pkg.split('@', 1)
        query_deps(pkg, ver, detailed)
    elif command == "query_pkg_reverse":
        dep = args[0] if args else ""
        dep_ver = None
        if '@' in dep:
            dep, dep_ver = dep.split('@', 1)
        query_pkg_reverse(dep, dep_ver)
    elif command == "change_dep_path":
        if len(args) >= 3:
            change_dep_path(args[0], args[1], args[2], args[3] if len(args) > 3 else None)
        else:
            print("Usage: change_dep_path <pkg> <version> <dep> <path>")
    elif command == "restore_default_path":
        restore_default_path(args[0], args[1], args[2])
    elif command == "delete_path_record":
        force = '--force' in args
        args = [a for a in args if a != '--force']
        if args:
            pkg = args[0]
            ver = args[1] if len(args) > 1 else None
            delete_path_record(pkg, ver, force)
    elif command == "uninstall_deps":
        dep_name = args[0] if args else None
        dep_ver = None
        unnecessary = False
        if '-u' in args or '--unnecessary' in args:
            unnecessary = True
        if dep_name and '@' in dep_name:
            dep_name, dep_ver = dep_name.split('@', 1)
        uninstall_deps(dep_name, dep_ver, unnecessary)
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
