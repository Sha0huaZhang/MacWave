#!/usr/bin/env python3
"""
MacWave 2.1.0 Main CLI
负责解析所有 2.1 命令，调度 pkginstaller.py, depsmanager.sh, pkgunzip.sh 等。
"""

import argparse
import json
import os
import sys
import platform
import time
import fcntl
import logging
import traceback
import shutil
import subprocess
from pathlib import Path

# 绝对路径
CONFIG_FILE = Path("/opt/macwave_config/config.json")
VERSION_FILE = Path("/opt/macwave_config/VERSION.json")

# 引入分离的模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pkg"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "surfboard"))
try:
    from pkgversionparser import safe_parse_pkg_version
    from depsversionparser import safe_parse_deps_version
    from help import print_custom_help, print_detailed_help
except ImportError:
    pass

# ==========================================
# 颜色定义
# ==========================================

RED_BOLD = '\033[1;31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
RESET = '\033[0m'

# ==========================================
# 配置加载
# ==========================================

def get_config_path():
    if CONFIG_FILE.exists():
        return CONFIG_FILE
    print(f"{RED_BOLD}🌊 Error: Configuration file not found or invalid.{RESET}")
    print(f"{RED_BOLD}🌊 Please run the install script again to reinstall.{RESET}")
    sys.exit(1)

def get_version():
    config_path = get_config_path().parent / "VERSION.json"
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
                return data.get("version", "unknown")
        except Exception:
            pass
    return "unknown"

VERSION = get_version()

def load_config():
    config_path = get_config_path()
    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                base_dir = config.get("base_dir")
                if base_dir:
                    return Path(base_dir)
        except Exception:
            pass
    print(f"{RED_BOLD}🌊 Error: Configuration file not found or invalid.{RESET}")
    print(f"{RED_BOLD}🌊 Please run the install script again to reinstall.{RESET}")
    sys.exit(1)

BASE_DIR = load_config()
INSTALL_DIR = BASE_DIR / "bin"
DOWNLOAD_TMP = BASE_DIR / "downloads" / "tmp"
REPO_DIR = BASE_DIR / "pkg"
REPO_CACHE = BASE_DIR / "pkg" / "repo_cache.json"
INSTALLED_DB = BASE_DIR / "pkg" / "installed.json"
LIB_DIR = BASE_DIR / "lib"
DEPS_DIR = BASE_DIR / "deps"
PROTECTED_PACKAGES = ["wave"]

# ==========================================
# 依赖库检查
# ==========================================

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    from urllib3.exceptions import InsecureRequestWarning
    import urllib3
except ImportError:
    print(f"{RED_BOLD}🌊 Error: 'requests' library is not installed.{RESET}")
    print(f"{RED_BOLD}🌊 Please install it using: pip3 install requests{RESET}")
    sys.exit(1)

try:
    from packaging.version import parse as parse_version, InvalidVersion
except ImportError:
    print(f"{RED_BOLD}🌊 Error: 'packaging' library is not installed.{RESET}")
    print(f"{RED_BOLD}🌊 Please install it using: pip3 install packaging{RESET}")
    sys.exit(1)

try:
    from rich.console import Console
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False

# ==========================================
# 主类
# ==========================================

class MacWaveCLI:
    def __init__(self):
        self.version = get_version()
        self.parser = self._create_parser()
        self.verbose = False
        self._logger = logging.getLogger("MacWave")
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(message)s'))
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)

    def _create_parser(self):
        parser = argparse.ArgumentParser(
            prog="wave",
            description=f"MacWave {self.version}\nA package manager for macOS jailbreak developers.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            usage="wave <command> [package] [flags]",
            epilog="For more details, visit: https://macwave.org",
            add_help=False
        )

        parser.add_argument('-h', '--help', action='store_true', help='show this help message and exit')
        parser.add_argument('-hd', '--help-detailed', action='store_true', help='show detailed help message and exit')
        parser.add_argument('-V', '--version', action='version', version=f'MacWave {self.version} 🌊')
        parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
        parser.add_argument('-B', '--beta-version', action='store_true', help='Install the latest beta version')
        parser.add_argument('--proxy', type=str, metavar='string', help='Specify an HTTP/HTTPS proxy')
        parser.add_argument('--skip-ssl', action='store_true', help='Skip SSL certificate verification')
        parser.add_argument('--limit-rate', type=str, metavar='string', help='Limit download speed (e.g., 200K, 1M, 5M)')
        parser.add_argument('--dry-run', action='store_true', help='Simulate the installation')
        parser.add_argument('--json', action='store_true', help='Output in JSON format')

        subparsers = parser.add_subparsers(dest="command", metavar="{install,uninstall,list,search,info,update,upgrade,doctor,clean,listdeps,depsinstall,depsquery,pkgquery,allquery,depsuninstall,changedeppath,delpathrecord}", help="Commands")

        install_parser = subparsers.add_parser("install", help="Install a package", usage="wave install <package_name> [flags]")
        install_parser.add_argument("package_name", help="Name of the package to install")
        self._add_install_flags(install_parser)

        uninstall_parser = subparsers.add_parser("uninstall", help="Uninstall a package", usage="wave uninstall <package_name>")
        uninstall_parser.add_argument("package_name", help="Name of the package to uninstall")

        subparsers.add_parser("list", help="List installed packages")

        search_parser = subparsers.add_parser("search", help="Search for a package", usage="wave search <query> [flags]")
        search_parser.add_argument("query", help="Search query")
        search_parser.add_argument('-f', '--fuzzy', action='store_true', help='Enable fuzzy search')

        info_parser = subparsers.add_parser("info", help="Display detailed information", usage="wave info <package_name>")
        info_parser.add_argument("package_name", help="Name of the package")

        subparsers.add_parser("update", help="Update the package index")

        upgrade_parser = subparsers.add_parser("upgrade", help="Upgrade an installed package", usage="wave upgrade <package_name>")
        upgrade_parser.add_argument("package_name", help="Name of the package to upgrade")

        subparsers.add_parser("doctor", help="Check your system for missing dependencies")
        subparsers.add_parser("clean", help="Clean up temporary download files")

        # 2.1 新命令
        listdeps_parser = subparsers.add_parser("listdeps", help="List dependencies")
        listdeps_parser.add_argument("-d", "--detailed", action="store_true", help="Show detailed dependency info")

        depsinstall_parser = subparsers.add_parser("depsinstall", help="Install dependencies")
        depsinstall_parser.add_argument("target", help="Target dependency or package")
        depsinstall_parser.add_argument("-m", "--missing", action="store_true", help="Install missing dependencies")
        depsinstall_parser.add_argument("-ma", "--missing-all", action="store_true", help="Install all missing dependencies")

        depsquery_parser = subparsers.add_parser("depsquery", help="Query dependencies")
        depsquery_parser.add_argument("target", help="Target dependency or package")
        depsquery_parser.add_argument("-d", "--detailed", action="store_true", help="Show detailed dependency info")

        pkgquery_parser = subparsers.add_parser("pkgquery", help="Query packages that depend on a target")
        pkgquery_parser.add_argument("target", help="Target dependency or package")

        allquery_parser = subparsers.add_parser("allquery", help="Query all dependencies and packages")
        allquery_parser.add_argument("target", help="Target dependency or package")

        depsuninstall_parser = subparsers.add_parser("depsuninstall", help="Uninstall dependencies")
        depsuninstall_parser.add_argument("target", help="Target dependency or package (or 'all')")
        depsuninstall_parser.add_argument("-u", "--unnecessary", action="store_true", help="Remove unnecessary dependencies")

        changedeppath_parser = subparsers.add_parser("changedeppath", help="Change dependency path")
        changedeppath_parser.add_argument("pkg", help="Package")
        changedeppath_parser.add_argument("dep", help="Dependency")
        changedeppath_parser.add_argument("path", nargs="?", default=None, help="New path (or 'default')")

        delpathrecord_parser = subparsers.add_parser("delpathrecord", help="Delete path record")
        delpathrecord_parser.add_argument("target", help="Target package or dependency")
        delpathrecord_parser.add_argument("--force", action="store_true", help="Force delete default path")

        return parser

    def _add_install_flags(self, parser):
        parser.add_argument('-D', '--dir', type=str, metavar='string', help='Specify an output directory')
        parser.add_argument('--ver', type=str, metavar='string', help='Install a specific version')
        parser.add_argument('-C', '--continue', dest='resume', action='store_true', help='Resume interrupted downloads')

    def _log(self, message: str, level: str = "info", force: bool = False):
        if self.verbose or force or level == "error":
            log_level = getattr(logging, level.upper(), logging.INFO)
            self._logger.log(log_level, f"🌊 {message}")

    def log(self, message, force=False):
        self._log(message, "info", force)

    def log_verbose(self, message):
        if self.verbose:
            self._log(message, "debug")

    def _is_protected(self, package_name: str) -> bool:
        return package_name.lower() in PROTECTED_PACKAGES

    def _confirm_action(self, message: str) -> bool:
        response = input(f"{RED_BOLD}🌊 {message} [Y/n] {RESET}").strip()
        return response == 'Y' or response == 'y'

    def _confirm_skip_ssl(self, args) -> bool:
        skip_ssl = getattr(args, 'skip_ssl', False)
        if not skip_ssl:
            return True

        print(f"{RED_BOLD}🌊 --skip-ssl parameter will skip SSL certificate verification, it is insecure. Are you sure to continue?{RESET}")
        if self._confirm_action(""):
            print(f"{GREEN}🌊 Install continue{RESET}")
            return True
        else:
            print(f"{RED_BOLD}🌊 Install stopped{RESET}")
            return False

    def _get_arch(self) -> str:
        machine = platform.machine().lower()
        if machine in ['arm64', 'aarch64']:
            return 'arm64'
        elif machine in ['x86_64', 'amd64']:
            return 'amd64'
        else:
            return 'unknown'

    def _get_data_base_url(self):
        return "https://raw.githubusercontent.com/Sha0huaZhang/MacWave/infosource"

    def _get_pkg_data(self, pkg_name, pkg_version):
        import requests
        arch = self._get_arch()
        url = f"{self._get_data_base_url()}/pkg/pkginfo_{arch}/{pkg_name}/_{pkg_name}@{pkg_version}"
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 404:
                return None
            if r.status_code != 200:
                return None
            return r.text
        except Exception:
            return None

    def _get_dep_data(self, dep_name, dep_version):
        import requests
        arch = self._get_arch()
        url = f"{self._get_data_base_url()}/surfboard/depsinfo_{arch}/{dep_name}/_{dep_name}@{dep_version}"
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 404:
                return None
            if r.status_code != 200:
                return None
            return r.text
        except Exception:
            return None

    def _call_installer(self, package_name, args, release, version, install_dir, final_path):
        installer_path = Path(__file__).resolve().parent.parent / 'pkg' / 'pkginstaller.py'
        if not installer_path.exists():
            print(f"{RED_BOLD}🌊 Error: pkginstaller.py not found at {installer_path}{RESET}")
            sys.exit(1)

        binary_url = release.get('url', '') if release else ''
        sha256 = release.get('sha256', '') if release else ''

        cmd = [
            'python3', str(installer_path),
            '--command', 'install',
            '--package', package_name,
        ]
        if version:
            cmd.extend(['--ver', version])
        if binary_url:
            cmd.extend(['--url', binary_url])
        if sha256:
            cmd.extend(['--sha256', sha256])
        if install_dir:
            cmd.extend(['--dir', str(install_dir)])
        if final_path:
            cmd.extend(['--final-path', str(final_path)])

        if args.get('verbose'):
            cmd.append('--verbose')
        if args.get('proxy'):
            cmd.extend(['--proxy', args.get('proxy')])
        if args.get('skip_ssl'):
            cmd.append('--skip-ssl')
        if args.get('limit_rate'):
            cmd.extend(['--limit-rate', args.get('limit_rate')])
        if args.get('resume'):
            cmd.append('--resume')
        if args.get('dry_run'):
            cmd.append('--dry-run')
        if args.get('skip_db_update'):
            cmd.append('--skip-db-update')

        result = subprocess.run(cmd)

        if result.returncode != 0:
            sys.exit(result.returncode)

    def handle_install(self, args):
        if args.json:
            print(json.dumps({"command": "install", "package": args.package_name}))
            return

        package_name = args.package_name
        if '@' in package_name:
            pkg_name, ver = package_name.split('@', 1)
            args.package_name = pkg_name
            args.ver = ver

        safe_name = args.package_name.lower()
        install_dir = INSTALL_DIR
        if args.dir:
            install_dir = Path(args.dir).expanduser().resolve()

        data_text = self._get_pkg_data(safe_name, args.ver)
        if data_text is None:
            print(f"{RED_BOLD}🌊 Error: Package '{safe_name}' not found in repository{RESET}")
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

        version = args.ver
        if not version:
            version = "1.0.0"  # Fallback

        final_path = install_dir / f"{safe_name}@{version}"
        self._call_installer(safe_name, args, release, version, install_dir, final_path)

    def handle_uninstall(self, args):
        print(f"{RED_BOLD}🌊 Uninstall command is handled by depsmanager.sh{RESET}")
        sys.exit(1)

    def handle_list(self, args):
        if not INSTALLED_DB.exists():
            print("🌊 No packages installed yet.")
            return
        try:
            with open(INSTALLED_DB, 'r') as f:
                installed = json.load(f)
            if not installed:
                print("🌊 No packages installed yet.")
                return
            print("🌊 Installed packages:")
            for pkg_name, info in installed.items():
                version = info.get('version', 'unknown')
                binary_path = info.get('binary_path', 'unknown')
                print(f"🌊   - {pkg_name} (v{version}) -> {binary_path}")
        except Exception as e:
            print(f"{RED_BOLD}🌊 Error: Could not read installed packages: {e}{RESET}")

    def handle_search(self, args):
        query = args.query.lower()
        print(f"🌊 Searching for packages matching '{query}'...")
        # Simplified search (placeholder)
        print(f"🌊 No packages found matching '{args.query}'")

    def handle_info(self, args):
        print(f"🌊 Showing info for package '{args.package_name}'...")
        # Simplified info (placeholder)

    def handle_update(self, args):
        print("🌊 Forcing update: fetching fresh package index...")
        # Simplified update (placeholder)

    def handle_upgrade(self, args):
        safe_name = args.package_name.lower()
        if self._is_protected(safe_name):
            print(f"{RED_BOLD}🌊 ERROR: Cannot upgrade protected package: {safe_name}{RESET}")
            return
        print(f"🌊 Upgrading '{safe_name}'...")
        # Simplified upgrade (placeholder)

    def handle_doctor(self, args):
        print("🌊 Running system diagnostics...")
        missing = []
        for cmd in ['curl', 'wget', 'git', 'python3', 'ruby']:
            if shutil.which(cmd) is None:
                missing.append(cmd)
        if missing:
            print(f"{RED_BOLD}🌊 Missing dependencies: {', '.join(missing)}{RESET}")
            sys.exit(1)
        else:
            print("🌊 All required dependencies are present.")
            print("🌊 System is healthy.")

    def handle_clean(self, args):
        if DOWNLOAD_TMP.exists():
            shutil.rmtree(DOWNLOAD_TMP)
            print("🌊 Cleaned up temporary download directory.")
        else:
            print("🌊 No temporary files to clean.")

    # ========== 2.1 新命令处理 ==========

    def handle_listdeps(self, args):
        print("🌊 Listing dependencies...")
        # Placeholder for 2.1 listdeps

    def handle_depsinstall(self, args):
        print(f"🌊 Installing dependencies for target '{args.target}'...")
        # Placeholder for 2.1 depsinstall

    def handle_depsquery(self, args):
        print(f"🌊 Querying dependencies for '{args.target}'...")
        # Placeholder for 2.1 depsquery

    def handle_pkgquery(self, args):
        print(f"🌊 Querying packages that depend on '{args.target}'...")
        # Placeholder for 2.1 pkgquery

    def handle_allquery(self, args):
        print(f"🌊 Querying all dependencies and packages for '{args.target}'...")
        # Placeholder for 2.1 allquery

    def handle_depsuninstall(self, args):
        print(f"🌊 Uninstalling dependencies for '{args.target}'...")
        # Placeholder for 2.1 depsuninstall

    def handle_changedeppath(self, args):
        print(f"🌊 Changing dependency path for '{args.pkg}' -> '{args.dep}' to '{args.path}'...")
        # Placeholder for 2.1 changedeppath

    def handle_delpathrecord(self, args):
        print(f"🌊 Deleting path record for '{args.target}'...")
        # Placeholder for 2.1 delpathrecord

    def run(self):
        args, unknown = self.parser.parse_known_args()

        if args.help and getattr(args, 'detailed', False):
            print_detailed_help()
            return
        if args.help:
            print_custom_help()
            return

        if '--skip-ssl' in unknown:
            args.skip_ssl = True

        self.verbose = args.verbose if hasattr(args, 'verbose') else False

        try:
            if not self._confirm_skip_ssl(args):
                sys.exit(0)

            if not args.command:
                print_custom_help()
                return

            command_handlers = {
                "install": self.handle_install,
                "uninstall": self.handle_uninstall,
                "list": self.handle_list,
                "search": self.handle_search,
                "info": self.handle_info,
                "update": self.handle_update,
                "upgrade": self.handle_upgrade,
                "doctor": self.handle_doctor,
                "clean": self.handle_clean,
                "listdeps": self.handle_listdeps,
                "depsinstall": self.handle_depsinstall,
                "depsquery": self.handle_depsquery,
                "pkgquery": self.handle_pkgquery,
                "allquery": self.handle_allquery,
                "depsuninstall": self.handle_depsuninstall,
                "changedeppath": self.handle_changedeppath,
                "delpathrecord": self.handle_delpathrecord,
            }
            handler = command_handlers.get(args.command)
            if handler:
                handler(args)
            else:
                print(f"{RED_BOLD}🌊 Error: Unknown command '{args.command}'{RESET}")
                sys.exit(1)

        except KeyboardInterrupt:
            print("\n🌊 Operation cancelled by user.")
            sys.exit(130)
        except SystemExit:
            raise
        except Exception as e:
            if self.verbose:
                traceback.print_exc()
            print(f"{RED_BOLD}\n🌊 Fatal error: {e}{RESET}")
            sys.exit(1)


def main():
    cli = MacWaveCLI()
    cli.run()


if __name__ == "__main__":
    main()
