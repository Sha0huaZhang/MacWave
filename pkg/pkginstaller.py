#!/usr/bin/env python3
"""
MacWave Package Installer
负责下载、校验、安装、卸载和 installed.json 管理。
作为独立模块由 wave.py 调用。
"""

import os
import sys
import json
import hashlib
import shutil
import fcntl
import time
import platform
import traceback
import logging
import argparse
from pathlib import Path
from typing import Optional

# ==========================================
# 颜色定义
# ==========================================

RED_BOLD = '\033[1;31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
RESET = '\033[0m'

# ==========================================
# 配置加载（无死循环：固定读取 /opt/macwave_config）
# ==========================================

CONFIG_FILE = Path("/opt/macwave_config/config.json")
VERSION_FILE = Path("/opt/macwave_config/VERSION.json")

def load_config():
    """强制加载 /opt/macwave_config/config.json"""
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

BASE_DIR = load_config()
INSTALL_DIR = BASE_DIR / "bin"
DOWNLOAD_TMP = BASE_DIR / "downloads" / "tmp"
INSTALLED_DB = BASE_DIR / "pkg" / "installed.json"  # 移到 pkg/ 下
PROTECTED_PACKAGES = ["wave"]

# ==========================================
# 版本号获取（统一从 VERSION.json 读取）
# ==========================================

def get_version():
    """从 /opt/macwave_config/VERSION.json 获取主程序版本号"""
    if VERSION_FILE.exists():
        try:
            with open(VERSION_FILE, 'r') as f:
                data = json.load(f)
                return data.get("version", "unknown")
        except Exception:
            pass
    return "unknown"

VERSION = get_version()

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
    from rich.progress import (
        Progress, BarColumn, DownloadColumn, TextColumn,
        TransferSpeedColumn, TimeRemainingColumn,
    )
    from rich.console import Console
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False


# ==========================================
# 核心安装器
# ==========================================

class PackageInstaller:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self._logger = logging.getLogger("PackageInstaller")
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(message)s'))
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)

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

    def _safe_delete_binary(self, binary_path: Path) -> bool:
        if self._is_protected(binary_path.name):
            print(f"{RED_BOLD}🌊 ERROR: Cannot delete '{binary_path.name}' - it's protected!{RESET}")
            return False
        try:
            if binary_path.exists():
                binary_path.unlink()
                return True
            return False
        except Exception as e:
            print(f"{RED_BOLD}🌊 Error deleting {binary_path}: {e}{RESET}")
            return False

    def _confirm_missing_sha256(self) -> bool:
        console = Console()
        console.print(f"{RED_BOLD}🌊 Can't find SHA256 value, continuing installation will skip SHA256 verification. Are you sure to continue?{RESET}", style="bold red")
        response = input(f"🌊 Are you sure to continue? [Y/n] ").strip()
        return response == 'Y' or response == 'y'

    def _calculate_sha256(self, filepath: Path) -> str:
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

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

    def download_binary(self, url, package_name, args, install_dir=None, release=None, final_path=None):
        if install_dir is None:
            install_dir = INSTALL_DIR
        if final_path is None:
            final_path = install_dir / package_name

        self.log_verbose(f"Download URL: {url}")
        print(f"🌊 Downloading {package_name}...")

        DOWNLOAD_TMP.mkdir(parents=True, exist_ok=True)
        temp_path = DOWNLOAD_TMP / f"{package_name}.partial"

        if temp_path.exists():
            temp_path.unlink()

        request_kwargs = {'stream': True, 'timeout': 30}

        if args.get('proxy'):
            proxy = args['proxy']
            safe_proxy = proxy.replace(proxy.split('@')[-1], '******') if '@' in proxy else proxy
            self.log_verbose(f"Using proxy: {safe_proxy}")
            request_kwargs['proxies'] = {'http': args['proxy'], 'https': args['proxy']}

        if args.get('skip_ssl'):
            request_kwargs['verify'] = False
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        headers = {}
        resume_pos = 0
        should_resume = args.get('resume', False) and temp_path.exists()

        if should_resume:
            try:
                resume_pos = temp_path.stat().st_size
                if resume_pos > 0:
                    headers['Range'] = f"bytes={resume_pos}-"
                    print(f"🌊 Resuming from {resume_pos} bytes")
                else:
                    temp_path.unlink()
                    should_resume = False
            except (FileNotFoundError, OSError):
                should_resume = False

        if headers:
            request_kwargs['headers'] = headers

        try:
            response = requests.get(url, **request_kwargs)
            response.raise_for_status()

            is_resume = False
            if should_resume and headers:
                if response.status_code == 206:
                    is_resume = True
                elif response.status_code == 200:
                    if temp_path.exists():
                        temp_path.unlink()
                    print("🌊 \033[31mWarning: The server does not support resuming downloads.\033[0m")
                    print("🌊 \033[31mRestarting download completely from the beginning.\033[0m")
                    resume_pos = 0
                    is_resume = False

            total_size = int(response.headers.get('content-length', 0)) + resume_pos
            if total_size == 0:
                total_size = None

            limit_bps = None
            if args.get('limit_rate'):
                limit_bps = self._parse_rate_limit(args['limit_rate'])
                if limit_bps is not None:
                    limit_bps = int(limit_bps * 0.8)
                    self.log_verbose(f"Download rate limit set to {limit_bps} bytes/sec (80% of user requested)")

            try:
                if RICH_AVAILABLE:
                    from rich.console import Console
                    progress_columns = [
                        TextColumn("[progress.description]{task.description}"),
                        BarColumn(bar_width=None),
                        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                        DownloadColumn(),
                        TextColumn("•"),
                        TextColumn("{task.fields[speed]}"),
                        TextColumn("•"),
                        TimeRemainingColumn(),
                    ]
                    console = Console()
                    with Progress(*progress_columns, console=console) as progress:
                        task_id = progress.add_task(
                            description=f"🌊 {package_name}",
                            total=total_size if total_size else None,
                            completed=resume_pos,
                            speed="0 B/s"
                        )
                        if not total_size:
                            progress.update(task_id, description=f"🌊 {package_name} (unknown size)")

                        mode = 'ab' if is_resume else 'wb'
                        sha256_hash = hashlib.sha256()

                        token_bucket = 0.0
                        last_time = time.monotonic()
                        speed_last_time = time.monotonic()
                        speed_last_bytes = resume_pos

                        with open(temp_path, mode) as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    if limit_bps:
                                        now = time.monotonic()
                                        delta = now - last_time
                                        token_bucket += delta * limit_bps
                                        last_time = now
                                        if token_bucket > 8192:
                                            token_bucket = 8192
                                        if token_bucket < len(chunk):
                                            time.sleep((len(chunk) - token_bucket) / limit_bps)
                                            now = time.monotonic()
                                            delta = now - last_time
                                            token_bucket += delta * limit_bps
                                            last_time = now
                                        token_bucket -= len(chunk)

                                    f.write(chunk)
                                    chunk_size_bytes = len(chunk)
                                    sha256_hash.update(chunk)

                                    current_bytes = progress.tasks[task_id].completed + chunk_size_bytes
                                    now = time.monotonic()

                                    if now - speed_last_time >= 0.5:
                                        real_speed = (current_bytes - speed_last_bytes) / (now - speed_last_time)
                                        speed_last_bytes = current_bytes
                                        speed_last_time = now

                                        if limit_bps:
                                            if real_speed > limit_bps:
                                                display_speed = limit_bps
                                            else:
                                                display_speed = real_speed
                                        else:
                                            display_speed = real_speed

                                        if display_speed >= 1024 * 1024:
                                            speed_str = f"{display_speed / (1024 * 1024):.1f} MB/s"
                                        elif display_speed >= 1024:
                                            speed_str = f"{display_speed / 1024:.1f} kB/s"
                                        else:
                                            speed_str = f"{display_speed:.0f} B/s"

                                        progress.update(task_id, speed=speed_str)

                                    progress.update(task_id, advance=chunk_size_bytes)

                        if total_size:
                            current_completed = progress.tasks[task_id].completed
                            if current_completed < total_size:
                                progress.update(task_id, advance=total_size - current_completed)
                        progress.update(task_id, speed="0 B/s")

                else:
                    mode = 'ab' if is_resume else 'wb'
                    sha256_hash = hashlib.sha256()

                    token_bucket = 0.0
                    last_time = time.monotonic()

                    with open(temp_path, mode) as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                if limit_bps:
                                    now = time.monotonic()
                                    delta = now - last_time
                                    token_bucket += delta * limit_bps
                                    last_time = now
                                    if token_bucket > 8192:
                                        token_bucket = 8192
                                    if token_bucket < len(chunk):
                                        time.sleep((len(chunk) - token_bucket) / limit_bps)
                                        now = time.monotonic()
                                        delta = now - last_time
                                        token_bucket += delta * limit_bps
                                        last_time = now
                                    token_bucket -= len(chunk)

                                f.write(chunk)
                                sha256_hash.update(chunk)
                                if self.verbose:
                                    print(".", end="", flush=True)
                    if self.verbose:
                        print(" ")

                if release and release.get("sha256"):
                    expected_sha256 = release.get("sha256")
                    print("🌊 Verifying SHA256...")
                    actual_sha256 = sha256_hash.hexdigest()
                    if actual_sha256 != expected_sha256:
                        print(f"{RED_BOLD}🌊 SHA256 verification failed!{RESET}")
                        print(f"🌊 \033[32mExpected: {expected_sha256}\033[0m")
                        print(f"{RED_BOLD}🌊 Actual:   {actual_sha256}{RESET}")
                        raise Exception("SHA256 verification failed")
                else:
                    if not self._confirm_missing_sha256():
                        raise Exception("Installation cancelled by user")

                install_dir.mkdir(parents=True, exist_ok=True)

                if final_path.exists():
                    if self._is_protected(final_path.name):
                        print(f"{RED_BOLD}🌊 ERROR: Cannot overwrite protected package: {final_path.name}{RESET}")
                        raise Exception("Protected package overwrite attempt")

                    backup_path = final_path.with_suffix(final_path.suffix + ".bak")
                    final_path.rename(backup_path)

                shutil.move(str(temp_path), str(final_path))
                os.chmod(final_path, 0o755)
                self.log_verbose(f"Moved to {final_path} ({final_path.stat().st_size} bytes)")
                print("🌊 Download complete!")

            except Exception as e:
                if not final_path.exists() and temp_path.exists():
                    temp_path.unlink()
                raise e

        except KeyboardInterrupt:
            print("\n🌊 Download interrupted by user.")
            if temp_path.exists() and temp_path.stat().st_size > 0:
                print(f"🌊 Partial file saved at: {temp_path}")
                print(f"🌊 Use 'wave install {package_name} -C' to resume later")
            else:
                temp_path.unlink()
            sys.exit(130)

        except requests.exceptions.RequestException as e:
            if self.verbose:
                traceback.print_exc()
            print(f"{RED_BOLD}\n🌊 Error: Failed to download binary: {e}{RESET}")
            if temp_path.exists() and temp_path.stat().st_size > 0:
                print(f"🌊 Partial file saved at: {temp_path}")
            sys.exit(1)
        except Exception as e:
            if self.verbose:
                traceback.print_exc()
            print(f"{RED_BOLD}\n🌊 Error: {e}{RESET}")
            if temp_path.exists() and temp_path.stat().st_size > 0:
                print(f"🌊 Partial file saved at: {temp_path}")
            sys.exit(1)

    def install_package(self, package_name, args, version=None, install_dir=None, final_path=None, skip_db_update=False):
        if install_dir is None:
            install_dir = INSTALL_DIR
        if final_path is None:
            final_path = install_dir / package_name

        if not final_path.exists():
            print(f"{RED_BOLD}🌊 Error: Binary file not found after download.{RESET}")
            sys.exit(1)

        try:
            print(f"🌊 Successfully installed {package_name} to {final_path}")
            if not skip_db_update:
                self._record_installation(package_name, version, install_dir, final_path=final_path)
            else:
                self.log_verbose("Skipping DB update (--skip-db-update specified)")

            path_dirs = os.environ.get("PATH", "").split(":")
            if str(install_dir) not in path_dirs:
                print(f"🌊 Tip: Add {install_dir} to your PATH to use '{package_name}' directly:")
                print(f"🌊   export PATH=\"{install_dir}:$PATH\"")
            else:
                print(f"🌊 Ready to ride! You can now run: {package_name}")

        except OSError as e:
            print(f"{RED_BOLD}🌊 Error: Failed to install package: {e}{RESET}")
            sys.exit(1)

    def _record_installation(self, package_name, release_version=None, install_dir=None, final_path=None):
        if install_dir is None:
            install_dir = INSTALL_DIR
        if final_path is None:
            final_path = install_dir / package_name

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
                installed[package_name] = {"version": release_version, "binary_path": str(final_path)}
                f.seek(0)
                f.truncate()
                json.dump(installed, f, indent=2)
        except Exception as e:
            self.log(f"Warning: Could not record installation: {e}", force=True)

    def uninstall_package(self, package_spec):
        safe_name = package_spec.lower()

        if self._is_protected(safe_name):
            print(f"{RED_BOLD}🌊 ERROR: Cannot uninstall protected package: {safe_name}{RESET}")
            return

        INSTALLED_DB.parent.mkdir(parents=True, exist_ok=True)
        install_dir = INSTALL_DIR

        # ========== 解析卸载目标 ==========
        if package_spec.endswith('@*'):
            base_name = safe_name.rstrip('@*')
            to_remove = []
            for f in install_dir.glob(f"{base_name}@*"):
                if f.name.endswith('.bak'):
                    continue
                ver = f.name.split('@', 1)[1]
                to_remove.append((f, ver))
            if not to_remove:
                print(f"🌊 No versions of '{base_name}' found to uninstall.")
                return
            print(f"🌊 Found {len(to_remove)} version(s) of '{base_name}':")
            for _, ver in to_remove:
                print(f"🌊   - {base_name}@{ver}")
            if not self._confirm_action(f"Uninstall all versions of '{base_name}'?"):
                print("🌊 Uninstall cancelled.")
                return
        elif '@' in package_spec:
            parts = package_spec.split('@')
            base_name = parts[0].lower()
            versions_to_remove = parts[1:]
            to_remove = []
            for ver in versions_to_remove:
                target = install_dir / f"{base_name}@{ver}"
                if target.exists() and not target.name.endswith('.bak'):
                    to_remove.append((target, ver))
                else:
                    print(f"🌊 \033[93mWarning: {base_name}@{ver} not found, skipping.\033[0m")
            if not to_remove:
                print(f"🌊 No specified versions of '{base_name}' found to uninstall.")
                return
            print(f"🌊 Found {len(to_remove)} specified version(s) of '{base_name}':")
            for _, ver in to_remove:
                print(f"🌊   - {base_name}@{ver}")
            if not self._confirm_action(f"Uninstall these versions of '{base_name}'?"):
                print("🌊 Uninstall cancelled.")
                return
        else:
            base_name = safe_name
            if not INSTALLED_DB.exists():
                print("🌊 No packages installed. Nothing to uninstall.")
                return
            try:
                with open(INSTALLED_DB, 'r') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                    installed = json.load(f)
                if base_name not in installed:
                    print(f"{RED_BOLD}🌊 Error: Package '{base_name}' is not installed.{RESET}")
                    return
                binary_path = Path(installed[base_name].get('binary_path', str(install_dir / base_name)))
                if not self._safe_delete_binary(binary_path):
                    return
                bak_path = binary_path.with_suffix(binary_path.suffix + ".bak")
                if bak_path.exists():
                    try:
                        bak_path.unlink()
                        print(f"🌊 Removed backup {base_name}.bak")
                    except Exception as e:
                        print(f"{RED_BOLD}🌊 Warning: Could not remove backup {base_name}.bak: {e}{RESET}")
                with open(INSTALLED_DB, 'w') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    del installed[base_name]
                    f.seek(0)
                    f.truncate()
                    json.dump(installed, f, indent=2)
                print(f"🌊 Successfully uninstalled '{base_name}'.")
                return
            except Exception as e:
                print(f"{RED_BOLD}🌊 Error: Failed to uninstall package: {e}{RESET}")
                return

        deleted_count = 0
        for file_path, ver in to_remove:
            try:
                if self._safe_delete_binary(file_path):
                    deleted_count += 1
                    print(f"🌊 Removed {base_name}@{ver}")
                    bak_path = file_path.with_suffix(file_path.suffix + ".bak")
                    if bak_path.exists():
                        try:
                            bak_path.unlink()
                            print(f"🌊 Removed backup {base_name}@{ver}.bak")
                        except Exception as e:
                            print(f"{RED_BOLD}🌊 Warning: Could not remove backup {base_name}@{ver}.bak: {e}{RESET}")
                else:
                    print(f"{RED_BOLD}🌊 Failed to remove {base_name}@{ver}{RESET}")
            except Exception as e:
                print(f"{RED_BOLD}🌊 Error removing {base_name}@{ver}: {e}{RESET}")

        try:
            if INSTALLED_DB.exists():
                with open(INSTALLED_DB, 'r+') as f:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    installed = json.load(f)
                    if base_name in installed:
                        del installed[base_name]
                        f.seek(0)
                        f.truncate()
                        json.dump(installed, f, indent=2)
                        print(f"🌊 Removed '{base_name}' from installation database.")
        except Exception as e:
            print(f"{RED_BOLD}🌊 Warning: Could not update installation database: {e}{RESET}")

        if deleted_count > 0:
            print(f"🌊 Successfully uninstalled {deleted_count} version(s) of '{base_name}'.")
        else:
            print(f"🌊 No versions of '{base_name}' were uninstalled.")

    def _confirm_action(self, message: str) -> bool:
        response = input(f"🌊 {message} [Y/n] ").strip()
        return response == 'Y' or response == 'y'

    def _confirm_skip_ssl(self, args) -> bool:
        skip_ssl = args.get('skip_ssl', False)
        if not skip_ssl:
            return True

        console = Console()
        console.print(f"{RED_BOLD}🌊 --skip-ssl parameter will skip SSL certificate verification, it is insecure. Are you sure to continue?{RESET}", style="bold red")
        if self._confirm_action(""):
            console.print(f"{GREEN}🌊 Install continue{RESET}", style="bold green")
            return True
        else:
            console.print(f"{RED_BOLD}🌊 Install stopped{RESET}", style="bold red")
            return False


def main():
    parser = argparse.ArgumentParser(description="MacWave Package Installer")
    parser.add_argument('--version', action='version', version=f'MacWave Package Installer {VERSION}')
    parser.add_argument('--command', required=True, choices=['install', 'uninstall'], help='Command to execute')
    parser.add_argument('--package', required=True, help='Package name')
    parser.add_argument('--ver', help='Package version')
    parser.add_argument('--url', help='Binary URL (for install)')
    parser.add_argument('--sha256', help='SHA256 checksum (for install)')
    parser.add_argument('--dir', help='Install directory')
    parser.add_argument('--final-path', help='Final binary path')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    parser.add_argument('--proxy', help='HTTP/HTTPS proxy')
    parser.add_argument('--skip-ssl', action='store_true', help='Skip SSL verification')
    parser.add_argument('--limit-rate', help='Limit download speed')
    parser.add_argument('--resume', action='store_true', help='Resume interrupted download')
    parser.add_argument('--dry-run', action='store_true', help='Dry run')
    parser.add_argument('--skip-db-update', action='store_true', help='Skip updating installed.json (used by wave upgrade)')

    args = parser.parse_args()
    installer = PackageInstaller(verbose=args.verbose)

    if args.command == 'install':
        installer.download_binary(
            url=args.url,
            package_name=args.package,
            args=vars(args),
            install_dir=Path(args.dir) if args.dir else None,
            release={'sha256': args.sha256} if args.sha256 else None,
            final_path=Path(args.final_path) if args.final_path else None
        )
        installer.install_package(
            package_name=args.package,
            args=vars(args),
            version=args.ver,
            install_dir=Path(args.dir) if args.dir else None,
            final_path=Path(args.final_path) if args.final_path else None,
            skip_db_update=args.skip_db_update
        )
    elif args.command == 'uninstall':
        installer.uninstall_package(args.package)


if __name__ == "__main__":
    main()
