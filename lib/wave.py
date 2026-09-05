#!/usr/bin/env python3
"""
MacWave 2.1.0 Main CLI
负责解析所有 2.1 命令，调用 pkginstaller.py, depsmanager.sh, pkgunzip.sh 等。
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

CONFIG_FILE = Path("/opt/macwave_config/config.json")
VERSION_FILE = Path("/opt/macwave_config/VERSION.json")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pkg"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "surfboard"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "deps"))
try:
    from pkgversionparser import safe_parse_pkg_version
    from depsversionparser import safe_parse_deps_version
    from help import print_custom_help, print_detailed_help
except ImportError:
    pass

RED_BOLD = '\033[1;31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
RESET = '\033[0m'

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

try:
    import requests
    from requests.exceptions import RequestException, HTTPError, ConnectionError, Timeout
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

class MacWaveCLI:
    def __init__(self):
        self.version = get_version()
        self.parser = self._create_parser()
        self.verbose = False
        self._logger = logging.getLogger("MacWave")

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
        parser.add_argument('--proxy', type=str, metavar='string', help='Specify an HTTP/HTTPS proxy')
        parser.add_argument('--skip-ssl', action='store_true', help='Skip SSL certificate verification')
        parser.add_argument('--limit-rate', type=str, metavar='string', help='Limit download speed')
        parser.add_argument('--dry-run', action='store_true', help='Simulate the installation')
        parser.add_argument('--json', action='store_true', help='Output in JSON format')

        subparsers = parser.add_subparsers(dest="command")

        install_parser = subparsers.add_parser("install", help="Install a package")
        install_parser.add_argument("package_name", help="Name of the package to install")
        self._add_install_flags(install_parser)

        subparsers.add_parser("uninstall", help="Uninstall a package")
        subparsers.add_parser("list", help="List installed packages")

        search_parser = subparsers.add_parser("search", help="Search for a package")
        search_parser.add_argument("query", help="Search query")
        search_parser.add_argument('-f', '--fuzzy', action='store_true', help='Enable fuzzy search')

        subparsers.add_parser("info", help="Display detailed information")

        listdeps_parser = subparsers.add_parser("listdeps", help="List dependencies")
        listdeps_parser.add_argument("-d", "--detailed", action="store_true", help="Show detailed dependency info")

        depsquery_parser = subparsers.add_parser("depsquery", help="Query dependencies")
        depsquery_parser.add_argument("target", help="Target package")
        depsquery_parser.add_argument("-d", "--detailed", action="store_true", help="Show detailed dependency info")

        pkgquery_parser = subparsers.add_parser("pkgquery", help="Query packages that depend on a target")
        pkgquery_parser.add_argument("target", help="Target dependency")

        changedeppath_parser = subparsers.add_parser("changedeppath", help="Change dependency path")
        changedeppath_parser.add_argument("pkg", help="Package")
        changedeppath_parser.add_argument("dep", help="Dependency")
        changedeppath_parser.add_argument("path", nargs="?", default=None, help="New path (or 'default')")

        delpathrecord_parser = subparsers.add_parser("delpathrecord", help="Delete path record")
        delpathrecord_parser.add_argument("target", help="Target package")
        delpathrecord_parser.add_argument("--force", action="store_true", help="Force delete default path")

        depsuninstall_parser = subparsers.add_parser("depsuninstall", help="Uninstall dependencies")
        depsuninstall_parser.add_argument("target", help="Target dependency or package (or 'all')")
        depsuninstall_parser.add_argument("-u", "--unnecessary", action="store_true", help="Remove unnecessary dependencies")

        depsinstall_parser = subparsers.add_parser("depsinstall", help="Install dependencies")
        depsinstall_parser.add_argument("target", help="Target dependency or package")
        depsinstall_parser.add_argument("-m", "--missing", action="store_true", help="Install missing dependencies")
        depsinstall_parser.add_argument("-ma", "--missing-all", action="store_true", help="Install all missing dependencies")

        return parser

    def _add_install_flags(self, parser):
        parser.add_argument('-D', '--dir', type=str, metavar='string', help='Specify an output directory')
        parser.add_argument('--ver', type=str, metavar='string', help='Install a specific version')
        parser.add_argument('-C', '--continue', dest='resume', action='store_true', help='Resume interrupted downloads')

    def _get_arch(self):
        machine = platform.machine().lower()
        if machine in ['arm64', 'aarch64']:
            return 'arm64'
        elif machine in ['x86_64', 'amd64']:
            return 'amd64'
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
        result = subprocess.run(cmd)
        if result.returncode != 0:
            sys.exit(result.returncode)

    def handle_install(self, args):
        package_name = args.package_name
        if '@' in package_name:
            pkg_name, ver = package_name.split('@', 1)
            args.package_name = pkg_name
            args.ver = ver

        safe_name = args.package_name.lower()
        install_dir = INSTALL_DIR
        if args.dir:
            install_dir = Path(args.dir).expanduser().resolve()

        # 如果没有指定版本，尝试获取所有版本并选最新
        data_text = None
        if args.ver:
            data_text = self._get_pkg_data(safe_name, args.ver)
        else:
            all_versions = self._get_all_pkg_versions(safe_name)
            if all_versions:
                from pkgversionparser import sort_pkg_versions
                sorted_versions = sort_pkg_versions(all_versions)
                latest_version = sorted_versions[0]
                args.ver = latest_version
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
        final_path = install_dir / f"{safe_name}@{version}"
        self._call_installer(safe_name, args, release, version, install_dir, final_path)

        # 自动下载全部缺失依赖，并生成 _deps、_path 和 .dep 标记
        if release.get('deps'):
            import querier
            querier.auto_install_deps(safe_name, version, release.get('deps', []))

    def _get_all_pkg_versions(self, pkg_name):
        """获取某个包的所有版本号（通过拉取 infosource 上的目录列表）"""
        import requests
        arch = self._get_arch()
        api_url = f"https://api.github.com/repos/Sha0huaZhang/MacWave/contents/pkg/pkginfo_{arch}/{pkg_name}?ref=infosource"
        try:
            r = requests.get(api_url, timeout=30)
            if r.status_code == 200:
                files = r.json()
                versions = []
                for f in files:
                    name = f['name']
                    if name.startswith(f"_{pkg_name}@") and "@common" not in name:
                        ver = name.split("@", 1)[1]
                        versions.append(ver)
                return versions
            return None
        except Exception:
            return None

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

    def handle_listdeps(self, args):
        if args.detailed:
            querier.list_deps(detailed=True)
        else:
            querier.list_deps()

    def handle_depsquery(self, args):
        querier.query_deps(args.target, detailed=args.detailed)

    def handle_pkgquery(self, args):
        querier.query_pkg_reverse(args.target)

    def handle_changedeppath(self, args):
        if args.pkg == "all":
            print(f"{YELLOW}🌊 Global path change not fully implemented yet.{RESET}")
        else:
            if '@' in args.pkg:
                pkg, ver = args.pkg.split('@', 1)
            else:
                pkg = args.pkg
                ver = None
            querier.change_dep_path(pkg, ver, args.dep, args.path)

    def handle_delpathrecord(self, args):
        if '@' in args.target:
            pkg, ver = args.target.split('@', 1)
        else:
            pkg = args.target
            ver = None
        querier.delete_path_record(pkg, ver, args.force)

    def handle_depsuninstall(self, args):
        if args.target == "all":
            if args.unnecessary:
                querier.uninstall_deps(unnecessary=True)
            else:
                print("🌊 To uninstall all dependencies, use 'wave depsuninstall all -u'.")
        else:
            querier.uninstall_deps(args.target, unnecessary=args.unnecessary)

    def handle_depsinstall(self, args):
        querier.install_deps(args.target, args.missing, args.missing_all)

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
            if not args.command:
                print_custom_help()
                return
            command_handlers = {
                "install": self.handle_install,
                "listdeps": self.handle_listdeps,
                "depsquery": self.handle_depsquery,
                "pkgquery": self.handle_pkgquery,
                "changedeppath": self.handle_changedeppath,
                "delpathrecord": self.handle_delpathrecord,
                "depsuninstall": self.handle_depsuninstall,
                "depsinstall": self.handle_depsinstall,
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
