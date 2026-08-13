#!/usr/bin/env python3
"""
MacWave
A package manager for macOS/Linux jailbreak developers.
Version: 1.0.0
"""

import argparse
import json
import os
import sys
import platform
import time
import fcntl
import logging
import hashlib
import traceback
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, Union

# ==========================================
# 依赖库检查
# ==========================================

# 检查 requests 库
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    from urllib3.exceptions import InsecureRequestWarning
    import urllib3
except ImportError:
    print("🌊 Error: 'requests' library is not installed.")
    print("🌊 Please install it using: pip3 install requests")
    sys.exit(1)

# 检查 packaging 库
try:
    from packaging.version import parse as parse_version
except ImportError:
    print("🌊 Error: 'packaging' library is not installed.")
    print("🌊 Please install it using: pip3 install packaging")
    sys.exit(1)

# 检查 rich 库
try:
    from rich.progress import (
        Progress,
        BarColumn,
        DownloadColumn,
        TextColumn,
        TransferSpeedColumn,
        TimeRemainingColumn,
    )
    from rich.console import Console
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    pass


# ==========================================
# 全局常量定义
# ==========================================

VERSION = "1.0.0"
REPO_URL = "https://raw.githubusercontent.com/Sha0huaZhang/MacWave/main/repo/repo.json"
INSTALL_DIR = Path.home() / ".local" / "macwave" / "bin"
DOWNLOAD_TMP = Path.home() / ".local" / "macwave" / "downloads" / "tmp"
INSTALLED_DB = Path.home() / ".local" / "macwave" / "installed.json"
REPO_CACHE = Path.home() / ".local" / "macwave" / "repo_cache.json"

PROTECTED_PACKAGES = ["wave"]


# ==========================================
# 核心主类
# ==========================================

class MacWaveCLI:
    def __init__(self):
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
            description="MacWave 1.0.0\nA package manager for macOS/Linux jailbreak developers.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            usage="wave <command> [package] [flags]",
            epilog="For more details, visit: https://macwave.org",
            add_help=False
        )

        parser.add_argument('-h', '--help', action='store_true',
                          help='show this help message and exit')
        parser.add_argument('-V', '--version', action='version',
                          version=f'MacWave {VERSION}')
        parser.add_argument('-v', '--verbose', action='store_true',
                          help='Enable verbose output (show detailed debug logs, including exception stack traces)')
        parser.add_argument('-B', '--beta-version', action='store_true',
                          help='Install the latest beta version (if available)')
        parser.add_argument('--proxy', type=str, metavar='string',
                          help='Specify an HTTP/HTTPS proxy (e.g., http://127.0.0.1:8080)')
        parser.add_argument('--skip-ssl', action='store_true',
                          help='Skip SSL certificate verification (insecure, with interactive confirmation)')
        parser.add_argument('--limit-rate', type=str, metavar='string',
                          help='Limit download speed (e.g., 200K, 1M, 5M)')
        parser.add_argument('--dry-run', action='store_true',
                          help='Simulate the installation without making changes')
        parser.add_argument('--json', action='store_true',
                          help='Output in JSON format (for scripting)')

        subparsers = parser.add_subparsers(dest="command", metavar="{install,uninstall,list,search,info,update,upgrade,doctor,clean}", help="Commands")

        install_parser = subparsers.add_parser(
            "install",
            help="Install a package",
            usage="wave install <package_name> [flags]"
        )
        install_parser.add_argument("package_name", help="Name of the package to install")
        self._add_install_flags(install_parser)

        uninstall_parser = subparsers.add_parser(
            "uninstall",
            help="Uninstall a package",
            usage="wave uninstall <package_name>"
        )
        uninstall_parser.add_argument("package_name", help="Name of the package to uninstall")

        subparsers.add_parser("list", help="List installed packages")

        search_parser = subparsers.add_parser(
            "search",
            help="Search for a package in the index",
            usage="wave search <query> [flags]"
        )
        search_parser.add_argument("query", help="Search query")
        search_parser.add_argument('-f', '--fuzzy', action='store_true',
                                  help='Enable fuzzy search (matches anywhere in name/description)')

        info_parser = subparsers.add_parser(
            "info",
            help="Display detailed information about a package",
            usage="wave info <package_name>"
        )
        info_parser.add_argument("package_name", help="Name of the package")

        subparsers.add_parser("update", help="Update the package index")

        upgrade_parser = subparsers.add_parser(
            "upgrade",
            help="Upgrade an installed package to the latest version",
            usage="wave upgrade <package_name>"
        )
        upgrade_parser.add_argument("package_name", help="Name of the package to upgrade")

        subparsers.add_parser("doctor", help="Check your system for missing dependencies")

        subparsers.add_parser("clean", help="Clean up temporary download files")

        return parser

    def _add_install_flags(self, parser):
        parser.add_argument('-D', '--dir', type=str, metavar='string',
                          help='Specify an output directory (e.g., ~/Desktop) for downloads')
        parser.add_argument('--ver', type=str, metavar='string',
                          help='Install a specific version of the package')
        parser.add_argument('-C', '--continue', dest='resume', action='store_true',
                          help='Resume interrupted downloads')

    def _print_custom_help(self):
        print("🌊 \033[35musage: \033[38;5;197mwave <command> [package] [flags]\033[0m")
        print()
        print("🌊 MacWave 1.0.0 🌊")
        print("🌊 A package manager for macOS/Linux jailbreak developers.")
        print()
        print("🌊 \033[35mpositional arguments:\033[0m")
        print("🌊   \033[32m{install, uninstall, list, search, info, update, upgrade, doctor, clean}\033[0m")
        print("🌊                           \033[0mCommands\033[0m")
        print("🌊     \033[32minstall\033[0m               Install a package")
        print("🌊     \033[32muninstall\033[0m             Uninstall a package")
        print("🌊     \033[32mlist\033[0m                  List installed packages")
        print("🌊     \033[32msearch\033[0m                Search for a package in the index")
        print("🌊     \033[32minfo\033[0m                  Display detailed information about a package")
        print("🌊     \033[32mupdate\033[0m                Update the package index")
        print("🌊     \033[32mupgrade\033[0m               Upgrade an installed package to the latest version")
        print("🌊     \033[32mdoctor\033[0m                Check your system for missing dependencies")
        print("🌊     \033[32mclean\033[0m                 Clean up temporary download files")
        print()
        print("🌊 \033[35mparameters:\033[0m")
        print("🌊   \033[32m-h, --help\033[0m              show this help message and exit")
        print("🌊   \033[32m-V, --version\033[0m           show program's version number and exit")
        print("🌊   \033[32m-v, --verbose\033[0m           Enable verbose output (show detailed debug logs, including exception stack traces)")
        print("🌊   \033[32m-B, --beta-version\033[0m      Install the latest beta version (if available)")
        print("🌊   \033[36m--proxy\033[0m \033[33mstring\033[0m          Specify an HTTP/HTTPS proxy (e.g., http://127.0.0.1:8080)")
        print("🌊   \033[36m--skip-ssl\033[0m              Skip SSL certificate verification (insecure, with interactive confirmation)")
        print("🌊   \033[36m--limit-rate\033[0m \033[33mstring\033[0m     Limit download speed (e.g., 200K, 1M, 5M)")
        print("🌊   \033[36m--dry-run\033[0m               Simulate the installation without making changes")
        print("🌊   \033[36m--json\033[0m                  Output in JSON format (for scripting)")
        print()
        print("🌊 Global Flags (can be used with any command):")
        print("🌊   \033[32m-B, --beta-version\033[0m      Install the latest beta version (if available)")
        print("🌊   \033[32m-D, --dir\033[0m \033[33mstring\033[0m        Specify an output directory (e.g., ~/Desktop) for downloads")
        print("🌊   \033[32m-C, --continue\033[0m          Resume interrupted downloads")
        print("🌊   \033[36m--proxy\033[0m \033[33mstring\033[0m          Specify an HTTP/HTTPS proxy (e.g., http://127.0.0.1:8080)")
        print("🌊   \033[36m--skip-ssl\033[0m              Skip SSL certificate verification (insecure, with interactive confirmation)")
        print("🌊   \033[36m--limit-rate\033[0m \033[33mstring\033[0m     Limit download speed (e.g., 200K, 1M, 5M)")
        print("🌊   \033[36m--dry-run\033[0m               Simulate the installation without making changes")
        print("🌊   \033[36m--json\033[0m                  Output in JSON format (for scripting)")
        print("🌊   \033[36m--ver\033[0m \033[33mstring\033[0m            Install a specific version of the package")
        print()
        print("🌊 For more details, visit: https://macwave.org")

    def _log(self, message: str, level: str = "info", force: bool = False):
        if self.verbose or force or level == "error":
            log_func = getattr(self._logger, level, self._logger.info)
            log_func(f"🌊 {message}")

    def log(self, message, force=False):
        self._log(message, "info", force)

    def log_verbose(self, message):
        if self.verbose:
            self._log(message, "debug")

    def _is_protected(self, package_name: str) -> bool:
        return package_name.lower() in PROTECTED_PACKAGES

    def _safe_delete_binary(self, binary_path: Path) -> bool:
        if self._is_protected(binary_path.name):
            print(f"🌊 \033[31mERROR: Cannot delete '{binary_path.name}' - it's protected!\033[0m")
            print(f"🌊 \033[31mThis package is required for MacWave to function.\033[0m")
            return False

        try:
            if binary_path.exists():
                binary_path.unlink()
                self.log_verbose(f"Deleted: {binary_path}")
                return True
            return False
        except Exception as e:
            print(f"🌊 \033[31mError deleting {binary_path}: {e}\033[0m")
            return False

    def _confirm_skip_ssl(self, args) -> bool:
        skip_ssl = getattr(args, 'skip_ssl', False)
        if not skip_ssl:
            return True

        console = Console()
        console.print("🌊 --skip-ssl parameter will skip SSL certificate verification, it is insecure. Are you sure to continue?", style="bold red")
        response = input("🌊 [Y/n] ").strip().lower()

        if response in ['y', 'yes', '']:
            console.print("🌊 Install continue", style="bold red")
            return True
        else:
            console.print("🌊 Install stopped", style="bold green")
            return False

    def _confirm_missing_sha256(self) -> bool:
        console = Console()
        console.print("🌊 Can't find SHA256 value, continuing installation will skip SHA256 verification, which may be insecure. Are you sure to continue?", style="bold red")
        response = input("🌊 [Y/n] ").strip().lower()

        if response in ['y', 'yes', '']:
            console.print("🌊 Install continue with SHA256 skipped", style="bold red")
            return True
        else:
            console.print("🌊 Install stopped", style="bold green")
            return False

    def _calculate_sha256(self, filepath: Path) -> str:
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def fetch_repo_data(self, args=None):
        REPO_CACHE.parent.mkdir(parents=True, exist_ok=True)

        cache_data: Optional[Dict[str, Any]] = None
        cache_age: Optional[float] = None

        if REPO_CACHE.exists():
            try:
                with open(REPO_CACHE, 'r') as f:
                    cache_data = json.load(f)
                cache_age = time.time() - REPO_CACHE.stat().st_mtime
                self.log_verbose(f"Cache exists, age: {cache_age:.1f}s")
            except (json.JSONDecodeError, OSError) as e:
                self._log(f"Cache corrupted: {e}", "warning")
                cache_data = None

        if cache_data is not None and cache_age is not None and cache_age < 300:
            self.log_verbose("Using fresh cache")
            return cache_data

        session = requests.Session()
        session.headers.update({'User-Agent': 'MacWave/1.0.0'})
        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        session.mount('https://', HTTPAdapter(max_retries=retries))

        request_kwargs = {'timeout': 10}

        if args and getattr(args, 'proxy', None):
            proxy = args.proxy
            self.log_verbose(f"Using proxy: {proxy}")
            if proxy.startswith(('http://', 'https://')):
                request_kwargs['proxies'] = {'http': proxy, 'https': proxy}
            else:
                self._log(f"Proxy protocol '{proxy.split(':')[0]}' may not be supported. Use http:// or https://", "warning")

        if args and getattr(args, 'skip_ssl', False):
            self.log_verbose("SSL verification disabled")
            request_kwargs['verify'] = False
            urllib3.disable_warnings(InsecureRequestWarning)

        try:
            self.log_verbose("Fetching fresh repo.json from network")
            response = session.get(REPO_URL, **request_kwargs)
            response.raise_for_status()
            data = response.json()

            with open(REPO_CACHE, 'w') as f:
                json.dump(data, f, indent=2)
            self.log_verbose("Fetched and cached fresh repo.json")
            return data

        except requests.exceptions.RequestException as e:
            if cache_data is not None and cache_age is not None and cache_age < 3600:
                self._log(f"Network failed, using stale cache (age: {cache_age:.1f}s): {e}", "warning")
                return cache_data
            raise RuntimeError(f"Failed to fetch repository data after retries: {e}") from e
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON data received from repository: {e}") from e

    def find_package(self, repo_data, package_name, args=None):
        self.log_verbose(f"Searching for package: {package_name}")

        if "packages" in repo_data:
            for pkg in repo_data["packages"]:
                if pkg.get("name") == package_name:
                    self.log_verbose(f"Found package: {pkg.get('name')}")
                    releases = pkg.get("releases", [])

                    if args and getattr(args, 'ver', None):
                        requested_version = args.ver
                        self.log_verbose(f"User requested version: {requested_version}")
                        for release in releases:
                            if release.get("version") == requested_version:
                                arch = platform.machine().lower()
                                if release.get("arch") == arch or release.get("arch") == "any":
                                    self.log_verbose(f"Found matching release for version {requested_version}")
                                    return release
                        print(f"🌊 Error: Could not find version '{requested_version}' for package '{package_name}'.")
                        sys.exit(1)

                    if args and getattr(args, 'beta_version', False):
                        self.log_verbose("User requested beta version.")
                        for release in releases:
                            if release.get("arch") == "beta":
                                self.log_verbose("Found beta release.")
                                return release
                        return None

                    current_arch = platform.machine().lower()
                    for release in releases:
                        if release.get("arch") == current_arch:
                            self.log_verbose(f"Found release matching architecture: {current_arch}")
                            return release
                    for release in releases:
                        if release.get("arch") == "any":
                            self.log_verbose(f"Found fallback release with arch='any'")
                            return release

                    print(f"🌊 Error: No release found for architecture '{current_arch}' or 'any' for package '{package_name}'")
                    sys.exit(1)

        print(f"🌊 Error: Package '{package_name}' not found in repository")
        sys.exit(1)

    def _parse_rate_limit(self, rate_str):
        rate_str = rate_str.upper().strip()
        multipliers = {'K': 1024, 'M': 1024**2, 'G': 1024**3}
        try:
            if rate_str[-1] in multipliers:
                return float(rate_str[:-1]) * multipliers[rate_str[-1]]
            return float(rate_str)
        except ValueError:
            self.log(f"Invalid rate limit format '{rate_str}', ignoring limit.", force=True)
            return None

    def download_binary(self, url, package_name, args, install_dir=None, release=None):
        if install_dir is None:
            install_dir = INSTALL_DIR

        if args.dry_run:
            print(f"🌊 [DRY RUN] Would download {package_name} from {url}")
            return

        self.log_verbose(f"Download URL: {url}")
        self.log_verbose(f"Target directory: {install_dir}")
        self.log_verbose(f"Target file: {package_name}")
        if release:
            self.log_verbose(f"Release info: version={release.get('version', 'unknown')}, arch={release.get('arch', 'unknown')}")

        print(f"🌊 Downloading {package_name}...")

        DOWNLOAD_TMP.mkdir(parents=True, exist_ok=True)
        temp_path = DOWNLOAD_TMP / f"{package_name}.partial"
        final_path = install_dir / package_name

        if temp_path.exists():
            temp_path.unlink()
            self.log_verbose(f"Cleaned up old partial file: {temp_path}")

        request_kwargs = {
            'stream': True,
            'timeout': 30
        }

        if args.proxy:
            request_kwargs['proxies'] = {'http': args.proxy, 'https': args.proxy}
            self.log_verbose(f"Using proxy: {args.proxy}")

        if args.skip_ssl:
            request_kwargs['verify'] = False
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            self.log_verbose("SSL verification disabled")

        headers = {}
        resume_pos = 0
        should_resume = args.resume and temp_path.exists()

        if should_resume:
            try:
                resume_pos = temp_path.stat().st_size
                if resume_pos > 0:
                    headers['Range'] = f"bytes={resume_pos}-"
                    self.log_verbose(f"Resuming download from byte {resume_pos}")
                    print(f"🌊 Resuming from {resume_pos} bytes")
                else:
                    self.log_verbose("Partial file exists but is empty, starting from beginning")
                    temp_path.unlink()
                    should_resume = False
            except (FileNotFoundError, OSError) as e:
                self.log_verbose(f"Cannot read partial file: {e}, starting from beginning")
                should_resume = False

        if headers:
            request_kwargs['headers'] = headers

        try:
            self.log_verbose(f"Sending GET request to {url}")
            response = requests.get(url, **request_kwargs)
            response.raise_for_status()

            self.log_verbose(f"Response status: {response.status_code}")
            content_length = response.headers.get('content-length')
            if content_length:
                self.log_verbose(f"Content-Length: {content_length} bytes")

            is_resume = False
            if should_resume and headers:
                if response.status_code == 206:
                    is_resume = True
                    self.log_verbose(f"Server supports resume, continuing from {resume_pos}")
                elif response.status_code == 200:
                    self.log_verbose("Server does not support resume, restarting download from scratch")
                    if temp_path.exists():
                        temp_path.unlink()
                        self.log_verbose(f"Removed corrupted partial file: {temp_path}")
                    print("🌊 \033[31mWarning: The server does not support resuming downloads.\033[0m")
                    print("🌊 \033[31mTo ensure file integrity, we are restarting the download completely from the beginning.\033[0m")
                    resume_pos = 0
                    is_resume = False
                else:
                    self.log_verbose(f"Unexpected status code: {response.status_code}")
                    resume_pos = 0

            total_size = int(response.headers.get('content-length', 0)) + resume_pos
            if total_size == 0:
                total_size = None
                self.log_verbose("Total file size unknown (server did not send Content-Length)")
            else:
                self.log_verbose(f"Total file size: {total_size} bytes")

            limit_bps = None
            if args.limit_rate:
                limit_bps = self._parse_rate_limit(args.limit_rate)
                if limit_bps is not None:
                    self.log_verbose(f"Download rate limit set to {limit_bps} bytes/sec")

            rate_start_time = time.time()
            rate_bytes_in_window = 0
            SLIDING_WINDOW = 0.5

            if RICH_AVAILABLE:
                from rich.console import Console
                progress_columns = [
                    TextColumn("[progress.description]{task.description}"),
                    BarColumn(bar_width=None),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                    DownloadColumn(),
                    TextColumn("•"),
                    TransferSpeedColumn(),
                    TextColumn("•"),
                    TimeRemainingColumn(),
                ]

                console = Console()
                with Progress(*progress_columns, console=console) as progress:
                    task_id = progress.add_task(
                        description=f"🌊 {package_name}",
                        total=total_size if total_size else None,
                        completed=resume_pos
                    )
                    if not total_size:
                        progress.update(task_id, description=f"🌊 {package_name} (unknown size)")

                    mode = 'ab' if is_resume else 'wb'
                    downloaded = resume_pos

                    sha256_hash = hashlib.sha256()

                    with open(temp_path, mode) as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                chunk_size_bytes = len(chunk)
                                downloaded += chunk_size_bytes

                                sha256_hash.update(chunk)

                                if limit_bps:
                                    rate_bytes_in_window += chunk_size_bytes
                                    expected_bytes_in_window = limit_bps * SLIDING_WINDOW
                                    if rate_bytes_in_window > expected_bytes_in_window:
                                        over_bytes = rate_bytes_in_window - expected_bytes_in_window
                                        sleep_time = over_bytes / limit_bps
                                        time.sleep(sleep_time)
                                        rate_start_time = time.time()
                                        rate_bytes_in_window = 0

                                progress.update(task_id, advance=chunk_size_bytes)

                    # 强制刷新进度条到100%
                    if total_size:
                        current_completed = progress.tasks[task_id].completed
                        if current_completed < total_size:
                            progress.update(task_id, advance=total_size - current_completed)
                    else:
                        progress.update(task_id, description=f"🌊 {package_name} (complete)")
            else:
                self.log_verbose("rich library not available, using simple progress indicator")
                mode = 'ab' if is_resume else 'wb'
                downloaded = resume_pos

                rate_start_time_fb = time.time()
                rate_bytes_in_window_fb = 0

                sha256_hash = hashlib.sha256()

                with open(temp_path, mode) as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            chunk_size_bytes = len(chunk)
                            downloaded += len(chunk)

                            sha256_hash.update(chunk)

                            if limit_bps:
                                rate_bytes_in_window_fb += chunk_size_bytes
                                expected_bytes_in_window_fb = limit_bps * SLIDING_WINDOW
                                if rate_bytes_in_window_fb > expected_bytes_in_window_fb:
                                    over_bytes_fb = rate_bytes_in_window_fb - expected_bytes_in_window_fb
                                    sleep_time_fb = over_bytes_fb / limit_bps
                                    time.sleep(sleep_time_fb)
                                    rate_start_time_fb = time.time()
                                    rate_bytes_in_window_fb = 0

                            if self.verbose:
                                print(".", end="", flush=True)
                if self.verbose:
                    print(" ")

            # 校验 SHA256（此时文件已完整下载）
            if release and release.get("sha256"):
                expected_sha256 = release.get("sha256")
                self.log_verbose(f"Expected SHA256: {expected_sha256}")
                print("🌊 Verifying SHA256...")

                actual_sha256 = sha256_hash.hexdigest()
                self.log_verbose(f"Actual SHA256: {actual_sha256}")

                if actual_sha256 != expected_sha256:
                    if temp_path.exists():
                        temp_path.unlink()
                        self.log_verbose(f"Deleted malicious/corrupted file: {temp_path}")

                    print(f"🌊 \033[31mSHA256 verification failed!\033[0m")
                    print(f"🌊 \033[31mExpected: {expected_sha256}\033[0m")
                    print(f"🌊 \033[32mActual:   {actual_sha256}\033[0m")
                    print(f"🌊 \033[31mFile may have been tampered with or corrupted.\033[0m")
                    print(f"🌊 \033[31mMalicious file has been permanently deleted.\033[0m")
                    sys.exit(1)
                else:
                    self.log_verbose("SHA256 verification passed")
                    print("🌊 SHA256 verified successfully")
            else:
                self.log_verbose("No SHA256 value found in release metadata")
                if not self._confirm_missing_sha256():
                    if temp_path.exists():
                        temp_path.unlink()
                        self.log_verbose(f"Deleted file: {temp_path}")
                    print("🌊 Installation cancelled.")
                    sys.exit(0)

            install_dir.mkdir(parents=True, exist_ok=True)

            if final_path.exists():
                if self._is_protected(final_path.name):
                    print(f"🌊 \033[31mERROR: Cannot overwrite protected package: {final_path.name}\033[0m")
                    print(f"🌊 \033[31mThis would break your package manager!\033[0m")
                    if temp_path.exists():
                        temp_path.unlink()
                    sys.exit(1)

                backup_path = final_path.with_suffix(final_path.suffix + ".bak")
                self.log_verbose(f"Target exists, backing up to {backup_path}")
                final_path.rename(backup_path)

            temp_path.rename(final_path)
            os.chmod(final_path, 0o755)
            self.log_verbose(f"Moved to {final_path} ({final_path.stat().st_size} bytes)")
            print("🌊 Download complete!")

        except KeyboardInterrupt:
            print("\n🌊 Download interrupted by user.")
            if temp_path.exists():
                if temp_path.stat().st_size > 0:
                    print(f"🌊 Partial file saved at: {temp_path}")
                    print(f"🌊 Use 'wave install {package_name} -C' to resume later")
                else:
                    temp_path.unlink()
            sys.exit(130)

        except requests.exceptions.RequestException as e:
            if self.verbose:
                print("\n🌊 [VERBOSE] Full exception traceback:")
                traceback.print_exc()
            print(f"\n🌊 Error: Failed to download binary: {e}")
            if temp_path.exists() and temp_path.stat().st_size > 0:
                print(f"🌊 Partial file saved at: {temp_path}")
            sys.exit(1)
        except Exception as e:
            if self.verbose:
                print("\n🌊 [VERBOSE] Full exception traceback:")
                traceback.print_exc()
            print(f"\n🌊 Error: Unexpected error: {e}")
            if temp_path.exists() and temp_path.stat().st_size > 0:
                print(f"🌊 Partial file saved at: {temp_path}")
            sys.exit(1)

    def install_package(self, package_name, args, version=None, install_dir=None):
        if install_dir is None:
            install_dir = INSTALL_DIR

        if args.dry_run:
            print(f"🌊 [DRY RUN] Would install {package_name} to {install_dir}")
            return

        binary_path = install_dir / package_name
        if not binary_path.exists():
            print("🌊 Error: Binary file not found after download.")
            sys.exit(1)

        self.log_verbose(f"Installing to: {binary_path}")
        self.log_verbose(f"File size: {binary_path.stat().st_size} bytes")

        try:
            print(f"🌊 Successfully installed {package_name} to {binary_path}")
            self._record_installation(package_name, version, install_dir)

            path_dirs = os.environ.get("PATH", "").split(":")
            if str(install_dir) not in path_dirs:
                self.log_verbose(f"{install_dir} not in PATH")
                print(f"🌊 Tip: Add {install_dir} to your PATH to use '{package_name}' directly:")
                print(f"🌊   export PATH=\"{install_dir}:$PATH\"")
            else:
                self.log_verbose(f"{install_dir} is in PATH")
                print(f"🌊 Ready to ride! You can now run: {package_name}")

        except OSError as e:
            print(f"🌊 Error: Failed to install package: {e}")
            sys.exit(1)

    def _record_installation(self, package_name, release_version=None, install_dir=None):
        if install_dir is None:
            install_dir = INSTALL_DIR

        try:
            INSTALLED_DB.parent.mkdir(parents=True, exist_ok=True)

            with open(INSTALLED_DB, 'a+') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)

                f.seek(0)
                try:
                    content = f.read()
                    installed = json.loads(content) if content else {}
                except json.JSONDecodeError:
                    installed = {}

                installed[package_name] = {
                    "version": release_version,
                    "binary_path": str(install_dir / package_name)
                }

                f.seek(0)
                f.truncate()
                json.dump(installed, f, indent=2)

                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

        except Exception as e:
            self.log(f"Warning: Could not record installation: {e}", force=True)

    def handle_install(self, args):
        if args.json:
            print(json.dumps({"command": "install", "package": args.package_name}))
            return

        self.log_verbose(f"Install command for package: {args.package_name}")
        try:
            repo_data = self.fetch_repo_data(args)
        except RuntimeError as e:
            print(f"🌊 {e}")
            sys.exit(1)

        safe_name = args.package_name.lower()

        install_dir = INSTALL_DIR
        if args.dir:
            install_dir = Path(args.dir).expanduser().resolve()
            self.log_verbose(f"Using custom install directory: {install_dir}")

        if args.ver:
            release = self.find_package(repo_data, safe_name, args)
            if release:
                self.download_binary(release["binary_url"], safe_name, args, install_dir, release)
                self.install_package(safe_name, args, release.get("version"), install_dir)
            return

        if args.beta_version:
            beta_release = self.find_package(repo_data, safe_name, args)
            if beta_release:
                self.download_binary(beta_release["binary_url"], safe_name, args, install_dir, beta_release)
                self.install_package(safe_name, args, beta_release.get("version"), install_dir)
                return
            else:
                print(f"🌊 No beta version found for '{safe_name}'.")
                response = input(f"🌊 Do you want to install the latest stable version instead? [Y/n] ")
                if response.lower() not in ['y', 'yes', '']:
                    print("🌊 Installation cancelled.")
                    return

        release = self.find_package(repo_data, safe_name, args)
        self.download_binary(release["binary_url"], safe_name, args, install_dir, release)
        self.install_package(safe_name, args, release.get("version"), install_dir)

    def handle_uninstall(self, args):
        safe_name = args.package_name.lower()

        if self._is_protected(safe_name):
            print(f"🌊 \033[31mERROR: Cannot uninstall protected package: {safe_name}\033[0m")
            print(f"🌊 \033[31mThis package is required for MacWave to function.\033[0m")
            return

        INSTALLED_DB.parent.mkdir(parents=True, exist_ok=True)

        if not INSTALLED_DB.exists():
            print("🌊 No packages installed. Nothing to uninstall.")
            return
        try:
            with open(INSTALLED_DB, 'r') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                installed = json.load(f)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            if safe_name not in installed:
                print(f"🌊 Error: Package '{safe_name}' is not installed.")
                return

            binary_path = INSTALL_DIR / safe_name
            if not self._safe_delete_binary(binary_path):
                return

            with open(INSTALLED_DB, 'w') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                del installed[safe_name]
                f.seek(0)
                f.truncate()
                json.dump(installed, f, indent=2)
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

            print(f"🌊 Successfully uninstalled '{safe_name}'.")

        except Exception as e:
            print(f"🌊 Error: Failed to uninstall package: {e}")

    def handle_list(self, args):
        INSTALLED_DB.parent.mkdir(parents=True, exist_ok=True)

        if not INSTALLED_DB.exists():
            print("🌊 No packages installed yet.")
            return
        try:
            with open(INSTALLED_DB, 'r') as f:
                installed = json.load(f)
            print("🌊 Installed packages:")
            for pkg_name, info in installed.items():
                version = info.get('version', 'unknown')
                print(f"🌊   - {pkg_name} (v{version})")
        except Exception as e:
            print(f"🌊 Error: Could not read installed packages: {e}")

    def handle_search(self, args):
        query = args.query.lower()
        try:
            repo_data = self.fetch_repo_data(args)
        except RuntimeError as e:
            print(f"🌊 {e}")
            sys.exit(1)

        matches = []
        if "packages" in repo_data:
            for pkg in repo_data["packages"]:
                name = pkg.get("name", "").lower()
                desc = pkg.get("description", "").lower()
                if args.fuzzy:
                    if query in name or query in desc:
                        matches.append(pkg)
                else:
                    if name.startswith(query) or desc.startswith(query):
                        matches.append(pkg)
        if not matches:
            print(f"🌊 No packages found matching '{args.query}'")
            return
        print(f"🌊 Found {len(matches)} package(s) matching '{args.query}':")
        for pkg in matches:
            name = pkg.get("name", "Unknown")
            desc = pkg.get("description", "No description")
            print(f"🌊   - {name}: {desc}")

    def handle_info(self, args):
        self.log_verbose(f"Info command for package: {args.package_name}")
        try:
            repo_data = self.fetch_repo_data(args)
        except RuntimeError as e:
            print(f"🌊 {e}")
            sys.exit(1)

        safe_name = args.package_name.lower()
        package_info = None
        if "packages" in repo_data:
            for pkg in repo_data["packages"]:
                if pkg.get("name") == safe_name:
                    package_info = pkg
                    break
        if not package_info:
            print(f"🌊 Error: Package '{safe_name}' not found in repository")
            sys.exit(1)
        print(f"🌊 Name:        {package_info.get('name', 'Unknown')}")
        print(f"🌊 Version:     {package_info.get('version', 'Unknown')}")
        print(f"🌊 Author:      {package_info.get('author', 'Unknown')}")
        print(f"🌊 Description: {package_info.get('description', 'No description')}")
        if "homepage" in package_info:
            print(f"🌊 Homepage:    {package_info.get('homepage')}")

    def handle_update(self, args):
        print("🌊 Forcing update: fetching fresh package index...")
        try:
            if REPO_CACHE.exists():
                REPO_CACHE.unlink()
            repo_data = self.fetch_repo_data(args)
            print(f"🌊 Package index updated successfully. Found {len(repo_data.get('packages', []))} packages.")
        except RuntimeError as e:
            print(f"🌊 {e}")
            sys.exit(1)
        except Exception as e:
            print(f"🌊 Error: Failed to update package index: {e}")

    def handle_upgrade(self, args):
        safe_name = args.package_name.lower()

        if self._is_protected(safe_name):
            print(f"🌊 \033[31mERROR: Cannot upgrade protected package: {safe_name}\033[0m")
            print(f"🌊 \033[31mThis package is required for MacWave to function.\033[0m")
            print(f"🌊 \033[93mTo update MacWave, download the new version manually:\033[0m")
            print(f"🌊 \033[93m  curl -fsSL -o ~/.local/macwave/bin/wave https://raw.githubusercontent.com/Sha0huaZhang/MacWave/main/wave.py\033[0m")
            return

        INSTALLED_DB.parent.mkdir(parents=True, exist_ok=True)

        if not INSTALLED_DB.exists():
            print(f"🌊 Package '{safe_name}' is not installed. Nothing to upgrade.")
            return
        try:
            with open(INSTALLED_DB, 'r') as f:
                installed = json.load(f)
            if safe_name not in installed:
                print(f"🌊 Package '{safe_name}' is not installed. Nothing to upgrade.")
                return
            local_version = installed[safe_name].get('version', '0.0.0')
            if local_version is None:
                local_version = '0.0.0'

            try:
                repo_data = self.fetch_repo_data(args)
            except RuntimeError as e:
                print(f"🌊 {e}")
                sys.exit(1)

            release = self.find_package(repo_data, safe_name)
            remote_version = release.get("version", "unknown")

            try:
                local_v = parse_version(local_version)
                remote_v = parse_version(remote_version)
                if local_v >= remote_v:
                    print(f"🌊 Package '{safe_name}' is already up to date (v{local_version}).")
                    return
            except Exception:
                if local_version >= remote_version:
                    print(f"🌊 Package '{safe_name}' is already up to date (v{local_version}).")
                    return

            print(f"🌊 Upgrading '{safe_name}' from v{local_version} to v{remote_version}...")
            binary_path = INSTALL_DIR / safe_name

            if binary_path.exists():
                if not self._safe_delete_binary(binary_path):
                    return

            del installed[safe_name]
            with open(INSTALLED_DB, 'w') as f:
                json.dump(installed, f, indent=2)
            self.download_binary(release["binary_url"], safe_name, args, release=release)
            self.install_package(safe_name, args, release.get("version"))
        except Exception as e:
            print(f"🌊 Error: Failed to upgrade package: {e}")

    def handle_doctor(self, args):
        print("🌊 Command 'doctor' is not implemented yet.")

    def handle_clean(self, args):
        if DOWNLOAD_TMP.exists():
            shutil.rmtree(DOWNLOAD_TMP)
            print("🌊 Cleaned up temporary download directory.")
        else:
            print("🌊 No temporary files to clean.")

    def run(self):
        args, unknown = self.parser.parse_known_args()

        if args.help:
            self._print_custom_help()
            return

        if '--skip-ssl' in unknown:
            args.skip_ssl = True

        self.verbose = args.verbose if hasattr(args, 'verbose') else False

        if self.verbose:
            self.log_verbose(f"Parsed arguments: command={args.command}, verbose={self.verbose}")
            if hasattr(args, 'package_name'):
                self.log_verbose(f"Package name: {args.package_name}")
            if hasattr(args, 'skip_ssl'):
                self.log_verbose(f"skip_ssl: {args.skip_ssl}")
            if hasattr(args, 'proxy') and args.proxy:
                self.log_verbose(f"proxy: {args.proxy}")

        if not self._confirm_skip_ssl(args):
            sys.exit(0)

        if not args.command:
            self._print_custom_help()
            return

        if args.command in {"install", "upgrade"} and hasattr(args, 'package_name'):
            safe_name = args.package_name.lower()

            if self._is_protected(safe_name):
                print(f"🌊 \033[31mERROR: Cannot install/upgrade protected package: {safe_name}\033[0m")
                print(f"🌊 \033[31mThis would break your package manager!\033[0m")
                print(f"🌊 \033[93mTo update MacWave, download the new version manually:\033[0m")
                print(f"🌊 \033[93m  curl -fsSL -o ~/.local/macwave/bin/wave https://raw.githubusercontent.com/Sha0huaZhang/MacWave/main/wave.py\033[0m")
                sys.exit(1)

            binary_path = INSTALL_DIR / safe_name

            if binary_path.exists():
                print(f"🌊 \033[93mWarning: Package '{safe_name}' is already installed.\033[0m")
                print(f"🌊 \033[93mDo you want to overwrite it? This will replace the existing binary.\033[0m")
                response = input("🌊 [Y/n] ").strip().lower()
                if response not in ['y', 'yes', '']:
                    print(f"🌊 \033[32mInstallation cancelled. Existing '{safe_name}' preserved.\033[0m")
                    sys.exit(0)
                if not self._safe_delete_binary(binary_path):
                    sys.exit(1)
                print(f"🌊 \033[31mRemoved old version of {safe_name}\033[0m")

        DOWNLOAD_TMP.mkdir(parents=True, exist_ok=True)
        INSTALLED_DB.parent.mkdir(parents=True, exist_ok=True)
        REPO_CACHE.parent.mkdir(parents=True, exist_ok=True)

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
        }
        handler = command_handlers.get(args.command)
        if handler:
            handler(args)
        else:
            print(f"🌊 Error: Unknown command '{args.command}'")
            sys.exit(1)


def main():
    cli = MacWaveCLI()
    cli.run()


if __name__ == "__main__":
    main()
