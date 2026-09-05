#!/usr/bin/env python3
"""
MacWave Querier Module
负责所有依赖查询、路径重定向、路径记录清理等高级功能。
同时包含自动下载依赖并生成标记和路径文件的逻辑。
由 wave.py 调用。
"""

import os
import json
import shutil
import time
import subprocess
import sys
from pathlib import Path

# 颜色定义
RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
BOLD = '\033[1m'
RESET = '\033[0m'

CONFIG_FILE = Path("/opt/macwave_config/config.json")

def to_tilde(path):
    """将绝对路径转换为 ~ 形式"""
    import os
    home = os.path.expanduser("~")
    if str(path).startswith(home):
        return "~" + str(path)[len(home):]
    return str(path)

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


def _fetch_data(dep_name, dep_version):
    """从 infosource 拉取依赖数据"""
    import requests
    arch = _get_arch()
    url = f"{_get_data_base_url()}/surfboard/depsinfo_{arch}/{dep_name}/_{dep_name}@{dep_version}"
    try:
        r = requests.get(url, timeout=30)
        if r.status_code == 404:
            return None
        if r.status_code != 200:
            return None
        return r.text
    except Exception:
        return None


def _download_and_install_dep(dep_name, dep_version):
    """下载并安装依赖到 deps 目录"""
    # 1. 检查 MacWave 默认位置是否有同名同版本依赖
    dep_dir = DEPS_DIR / f"{dep_name}@{dep_version}"
    if dep_dir.exists() and (dep_dir / dep_name).exists():
        print(f"{GREEN}🌊 Dependency {dep_name}@{dep_version} already exists. Skipping download.{RESET}")
        return dep_dir

    # 2. 从 infosource 拉取依赖数据
    data_text = _fetch_data(dep_name, dep_version)
    if data_text is None:
        print(f"{RED}🌊 Error: Dependency '{dep_name}@{dep_version}' not found in repository.{RESET}")
        sys.exit(1)

    release = {"url": None, "sha256": None, "deps": []}
    for line in data_text.strip().splitlines():
        line = line.strip()
        if line.startswith("url:"):
            release["url"] = line.split(":", 1)[1].strip().strip('"')
        elif line.startswith("sha256:"):
            release["sha256"] = line.split(":", 1)[1].strip().strip('"')
        elif line.startswith("deps:"):
            deps_str = line.split(":", 1)[1].strip().strip('"')
            if deps_str:
                release["deps"].append(deps_str)
        elif line.startswith('"') and release["deps"]:
            dep = line.strip().strip('"')
            if dep:
                release["deps"].append(dep)

    # 3. 调用 pkginstaller.py 下载并安装（install_dir 指向 deps/）
    installer_path = Path(__file__).resolve().parent.parent / 'pkg' / 'pkginstaller.py'
    dep_final_path = dep_dir / dep_name

    cmd = [
        'python3', str(installer_path),
        '--command', 'install',
        '--package', dep_name,
        '--ver', dep_version,
        '--url', release.get('url', ''),
        '--sha256', release.get('sha256', ''),
        '--dir', str(DEPS_DIR),
        '--final-path', str(dep_final_path)
    ]

    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"{RED}🌊 Error: Failed to install dependency {dep_name}@{dep_version}.{RESET}")
        sys.exit(1)

    print(f"{GREEN}🌊 Dependency {dep_name}@{dep_version} installed successfully.{RESET}")
    return dep_dir


def _generate_deps_and_path(package, version, deps_list):
    """生成 _deps 和 _path 文件"""
    pkg_dir = INSTALL_DIR / f"{package}@{version}"

    # 1. 生成 _deps 文件
    if deps_list:
        with open(pkg_dir / "_deps", 'w') as f:
            for dep in deps_list:
                f.write(dep + "\n")
        print(f"🌊 Generated _deps for {package}@{version}")

    # 2. 生成 _path 文件（指向依赖的实际位置）
    if deps_list:
        paths = []
        for dep in deps_list:
            if '@' in dep:
                dep_name, dep_ver = dep.split('@', 1)
                dep_dir = DEPS_DIR / f"{dep_name}@{dep_ver}"
                if (dep_dir / dep_name).exists():
                    paths.append(f"{dep_dir / dep_name}")
        if paths:
            with open(pkg_dir / "_path", 'w') as f:
                f.write("\n".join(paths))
            print(f"🌊 Generated _path for {package}@{version}")


def _generate_dep_references(package, version, deps_list):
    """为每个依赖生成 .dep_<包名>@<版本> 标记文件"""
    pkg_version = version
    for dep in deps_list:
        if '@' in dep:
            dep_name, dep_ver = dep.split('@', 1)
            dep_dir = DEPS_DIR / f"{dep_name}@{dep_ver}"
            if not dep_dir.exists():
                print(f"{RED}🌊 Error: Dependency directory {dep_dir} not found.{RESET}")
                continue
            marker = dep_dir / f".dep_{package}@{pkg_version}"
            if not marker.exists():
                marker.touch()
                print(f"🌊 Generated reference marker: {to_tilde(marker)}")


def auto_install_deps(package, version, deps_list):
    """自动安装全部依赖，并生成 _deps、_path 和 .dep 标记"""
    if not deps_list:
        return

    print(f"{YELLOW}🌊 Checking and installing dependencies for {package}@{version}...{RESET}")

    # 1. 检查每个依赖是否已安装
    for dep in deps_list:
        if '@' in dep:
            dep_name, dep_ver = dep.split('@', 1)
            existing_dep = DEPS_DIR / f"{dep_name}@{dep_ver}"
            if existing_dep.exists() and (existing_dep / dep_name).exists():
                print(f"🌊 Dependency {dep_name}@{dep_ver} already exists. Skipping download.")
            else:
                # 如果还有下一层依赖，自动递归
                _download_and_install_dep(dep_name, dep_ver)

    # 2. 生成 _deps 和 _path
    _generate_deps_and_path(package, version, deps_list)

    # 3. 生成 .dep 引用标记
    _generate_dep_references(package, version, deps_list)

    print(f"🌊 All dependencies for {package}@{version} are ready!")


def list_deps(detailed=False):
    """列出所有已安装的依赖（或详细版本）"""
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
    """查询某个包的依赖（支持版本，可选是否安装红绿显示）"""
    if version:
        pkg_dir = INSTALL_DIR / f"{package}@{version}"
    else:
        pkg_dirs = list(INSTALL_DIR.glob(f"{package}@*"))
        if not pkg_dirs:
            print(f"🌊 Package '{package}' not found.")
            return
        pkg_dir = pkg_dirs[0]

    deps_file = pkg_dir / "_deps"
    if not deps_file.exists():
        print(f"🌊 Package '{package}' has no dependencies.")
        return

    with open(deps_file, 'r') as f:
        deps = [line.strip() for line in f if line.strip()]

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
            deps_file = pkg_dir / "_deps"
            if deps_file.exists():
                with open(deps_file, 'r') as f:
                    deps = [line.strip() for line in f if line.strip()]
                if dep_key in deps:
                    print(f"🌊 - {pkg_name}@{info.get('version', '')}")
    else:
        for pkg_name, info in installed.items():
            pkg_dir = INSTALL_DIR / f"{pkg_name}@{info.get('version', '')}"
            deps_file = pkg_dir / "_deps"
            if deps_file.exists():
                with open(deps_file, 'r') as f:
                    deps = [line.strip() for line in f if line.strip()]
                for dep in deps:
                    if dep.startswith(f"{dep_name}@"):
                        dep_ver = dep.split('@', 1)[1]
                        print(f"🌊 @{dep_ver}")
                        print(f"    - {pkg_name}@{info.get('version', '')}")


def change_dep_path(package, version, dep, new_path):
    """修改依赖路径（含备份）"""
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
    """恢复默认路径"""
    pkg_dir = INSTALL_DIR / f"{package}@{version}"
    path_file = pkg_dir / "_path"
    default_bak = pkg_dir / "_path.bak_default"

    if not default_bak.exists():
        print(f"{RED}🌊 Error: No default backup found.{RESET}")
        return

    i = 1
    while (pkg_dir / f"_path.bak_{i}").exists():
        i += 1
    shutil.copy2(path_file, pkg_dir / f"_path.bak_{i}")

    shutil.copy2(default_bak, path_file)
    print(f"{GREEN}🌊 Default path restored.{RESET}")


def delete_path_record(package, version=None, force=False):
    """删除路径备份记录"""
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
    """卸载依赖（普通卸载 或 清理不必要依赖）"""
    if unnecessary:
        if not DEPS_DIR.exists():
            print("🌊 No dependencies installed.")
            return

        unnecessary_deps = []
        for dep_dir in DEPS_DIR.iterdir():
            if dep_dir.is_dir():
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


def install_deps(target=None, missing=False, missing_all=False):
    """安装依赖（特定依赖、缺失依赖、全部缺失）"""
    if missing_all:
        print(f"{GREEN}🌊 Checking all packages for missing dependencies...{RESET}")
        installed = _load_installed()
        all_deps = []
        for pkg_name, info in installed.items():
            pkg_dir = INSTALL_DIR / f"{pkg_name}@{info.get('version', '')}"
            deps_file = pkg_dir / "_deps"
            if deps_file.exists():
                with open(deps_file, 'r') as f:
                    deps = [line.strip() for line in f if line.strip()]
                all_deps.extend(deps)
        auto_install_deps("", "", all_deps)
        return

    if missing:
        if not target:
            print(f"{RED}🌊 Error: Missing package name.{RESET}")
            return
        if '@' in target:
            pkg, ver = target.split('@', 1)
        else:
            pkg = target
            ver = None
        pkg_dirs = list(INSTALL_DIR.glob(f"{pkg}@*"))
        if not pkg_dirs:
            print(f"{RED}🌊 Package '{pkg}' not found.{RESET}")
            return
        pkg_dir = pkg_dirs[0]
        deps_file = pkg_dir / "_deps"
        if not deps_file.exists():
            print(f"🌊 Package '{pkg}' has no dependencies.")
            return
        with open(deps_file, 'r') as f:
            deps = [line.strip() for line in f if line.strip()]
        auto_install_deps(pkg, pkg_dir.name.split('@')[-1], deps)
        return

    if target:
        if '@' in target:
            dep_name, dep_ver = target.split('@', 1)
            _download_and_install_dep(dep_name, dep_ver)
        else:
            print(f"{RED}🌊 Error: Please specify dependency version (e.g., openssl@1.0).{RESET}")
        return


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
    elif command == "install_deps":
        target = args[0] if args else None
        missing = '-m' in args or '--missing' in args
        missing_all = '-ma' in args or '--missing-all' in args
        install_deps(target, missing, missing_all)
    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
