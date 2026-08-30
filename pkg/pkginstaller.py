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
import logging
import argparse
from pathlib import Path

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
    # 如果配置文件缺失或损坏，直接报错退出，绝不写死 ~/.local
    print(f"{RED_BOLD}🌊 Error: Configuration file not found or invalid.{RESET}")
    print(f"{RED_BOLD}🌊 Please run the install script again to reinstall MacWave.{RESET}")
    sys.exit(1)

BASE_DIR = load_config()
INSTALL_DIR = BASE_DIR / "bin"
DOWNLOAD_TMP = BASE_DIR / "downloads" / "tmp"
INSTALLED_DB = BASE_DIR / "pkg" / "installed.json"
PROTECTED_PACKAGES = ["wave"]

# ==========================================
# 依赖库检查
# ==========================================

try:
    import requests
    from requests.exceptions import RequestException, HTTPError, ConnectionError, Timeout
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
        print(f"{RED_BOLD}🌊 WARNING: This package has NO SHA256 checksum provided.{RESET}")
        print(f"{RED_BOLD}🌊 Skipping SHA256 verification is INSECURE and may expose you to tampered files.{RESET}")
        response = input(f"{RED_BOLD}🌊 Are you sure to continue? [Y]: {RESET}").strip()
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

    def _check_disk_space(self, path: Path, required_bytes: int = 10 * 1024 * 1024) -> bool:
        total, used, free = shutil.disk_usage(path)
        if free < required_bytes:
            print(f"{RED_BOLD}🌊 Error: Insufficient disk space in {path}.{RESET}")
            sys.exit(1)
        return True

    def _delete_directory_with_sudo(self, target_path: Path) -> bool:
        """尝试使用 sudo 删除目录/文件"""
        try:
            import subprocess as sp
            print(f"{RED_BOLD}🌊 Permission denied. Attempting to delete with sudo...{RESET}")
            result = sp.run(['sudo', 'rm', '-rf', str(target_path)], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"{RED_BOLD}🌊 Deleted with sudo (sudo rm -rf).{RESET}")
                return True
            else:
                print(f"{RED_BOLD}🌊 WARNING: Unable to delete with sudo. Please delete manually.{RESET}")
                return False
        except Exception:
            print(f"{RED_BOLD}🌊 WARNING: Unable to delete with sudo. Please delete manually.{RESET}")
            return False

    def download_binary(self, url, package_name, args, install_dir=None, release=None, final_path=None):
        if install_dir is None:
            install_dir = INSTALL_DIR
        if final_path is None:
            final_path = install_dir / package_name

        # ========== B方案流程图逻辑开始 ==========

        # 1. URL exists?
        if not url:
            print(f"{RED_BOLD}🌊 Error: URLNone{RESET}")
            sys.exit(1)

        # 2. 预先判断 SHA256 缺失（下载前强制询问，绝不默认跳过）
        if release and not release.get("sha256"):
            print(f"{RED_BOLD}🌊 WARNING: This package has NO SHA256 checksum provided.{RESET}")
            print(f"{RED_BOLD}🌊 Skipping SHA256 verification is INSECURE and may expose you to tampered files.{RESET}")
            if not self._confirm_missing_sha256():
                print(f"{RED_BOLD}🌊 Installation cancelled by user.{RESET}")
                sys.exit(1)
            sha256_skip = True
            print(f"{RED_BOLD}🌊 SHA256 verification will be skipped (user confirmed).{RESET}")
        else:
            sha256_skip = False

        # 3. 预处理（开始下载）
        self.log_verbose(f"Download URL: {url}")
        print(f"🌊 Downloading {package_name}...")

        # 磁盘空间检查 (Disk space full?)
        DOWNLOAD_TMP.mkdir(parents=True, exist_ok=True)
        self._check_disk_space(DOWNLOAD_TMP)

        # 下载前准备
        temp_path = DOWNLOAD_TMP / f"{package_name}.partial"
        if temp_path.exists():
            temp_path.unlink()

        request_kwargs = {'stream': True, 'timeout': (30, 30)}

        if args.get('proxy'):
            proxy = args['proxy']
            safe_proxy = proxy.replace(proxy.split('@')[-1], '******') if '@' in proxy else proxy
            self.log_verbose(f"Using proxy: {safe_proxy}")
            request_kwargs['proxies'] = {'http': args['proxy'], 'https': args['proxy']}

        if args.get('skip_ssl'):
            print(f"{RED_BOLD}🌊 WARNING: SSL verification is DISABLED. This may expose you to man-in-the-middle attacks.{RESET}")
            request_kwargs['verify'] = False
            urllib3.disable_warnings(InsecureRequestWarning)

        # 4. 下载并重试
        download_success = False
        attempt = 0
        while not download_success:
            attempt += 1
            try:
                response = requests.get(url, **request_kwargs)

                if response.status_code == 404:
                    print(f"{RED_BOLD}🌊 Error: ErrorCode 404 - The URL or file does not exist.{RESET}")
                    print(f"{RED_BOLD}🌊 URL: {url}{RESET}")
                    sys.exit(404)
                elif response.status_code != 200:
                    print(f"{RED_BOLD}🌊 Error: ErrorCode {response.status_code}{RESET}")
                    print(f"{RED_BOLD}🌊 URL: {url}{RESET}")
                    sys.exit(response.status_code)

                total_size = int(response.headers.get('content-length', 0))
                limit_bps = None
                if args.get('limit_rate'):
                    limit_bps = self._parse_rate_limit(args['limit_rate'])
                    if limit_bps is not None:
                        limit_bps = int(limit_bps * 0.8)

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
                        task_id = progress.add_task(description=f"🌊 {package_name}", total=total_size or None, speed="0 B/s")

                        sha256_hash = hashlib.sha256()
                        token_bucket = 0.0
                        last_time = time.monotonic()
                        speed_last_time = time.monotonic()
                        speed_last_bytes = 0

                        with open(temp_path, 'wb') as f:
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

                                    current_bytes = progress.tasks[task_id].completed + len(chunk)
                                    now = time.monotonic()

                                    if now - speed_last_time >= 0.5:
                                        real_speed = (current_bytes - speed_last_bytes) / (now - speed_last_time)
                                        speed_last_bytes = current_bytes
                                        speed_last_time = now
                                        display_speed = min(real_speed, limit_bps) if limit_bps else real_speed
                                        if display_speed >= 1024 * 1024:
                                            speed_str = f"{display_speed / (1024 * 1024):.1f} MB/s"
                                        elif display_speed >= 1024:
                                            speed_str = f"{display_speed / 1024:.1f} kB/s"
                                        else:
                                            speed_str = f"{display_speed:.0f} B/s"

                                        progress.update(task_id, speed=speed_str)

                                    progress.update(task_id, advance=len(chunk))

                        if total_size:
                            current_completed = progress.tasks[task_id].completed
                            if current_completed < total_size:
                                progress.update(task_id, advance=total_size - current_completed)
                        progress.update(task_id, speed="0 B/s")

                else:
                    sha256_hash = hashlib.sha256()
                    with open(temp_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                sha256_hash.update(chunk)
                                if self.verbose:
                                    print(".", end="", flush=True)
                    if self.verbose:
                        print(" ")

                download_success = True
                break

            except (ConnectionError, Timeout) as e:
                if attempt < 2:
                    print(f"{RED_BOLD}🌊 Download failed: {e}{RESET}")
                    print(f"{RED_BOLD}🌊 Do you want to retry? [y/N]: {RESET}")
                    retry = input().strip().lower()
                    if retry == 'y':
                        continue
                    else:
                        print(f"{RED_BOLD}🌊 Error: Failed to download package{RESET}")
                        sys.exit(1)
                else:
                    print(f"{RED_BOLD}🌊 Error: Failed to download package{RESET}")
                    sys.exit(1)

            except HTTPError as e:
                status_code = e.response.status_code if e.response is not None else 1
                print(f"{RED_BOLD}🌊 Error: ErrorCode {status_code}{RESET}")
                sys.exit(status_code)

            except Exception as e:
                if self.verbose:
                    traceback.print_exc()
                print(f"{RED_BOLD}🌊 Error: {e}{RESET}")
                sys.exit(1)

        # 5. 校验 SHA256（仅在存在且未跳过时执行）
        if release and release.get("sha256") and not sha256_skip:
            expected_sha256 = release.get("sha256")
            print("🌊 Verifying SHA256...")
            actual_sha256 = sha256_hash.hexdigest()
            if actual_sha256 != expected_sha256:
                print(f"{RED_BOLD}🌊 Error: SHA256 verification failed (Error code 007).{RESET}")
                print(f"{RED_BOLD}🌊 Actual:   {actual_sha256}{RESET}")
                print(f"{GREEN}🌊 Expected: {expected_sha256}{RESET}")
                # 删除损坏文件
                if temp_path.exists():
                    try:
                        temp_path.unlink()
                        print(f"{RED_BOLD}🌊 The corrupted file has been deleted (rm -rf).{RESET}")
                    except PermissionError:
                        print(f"{RED_BOLD}🌊 Permission denied. Attempting to delete with sudo...{RESET}")
                        import subprocess as sp
                        try:
                            result = sp.run(['sudo', 'rm', '-rf', str(temp_path)], capture_output=True, text=True)
                            if result.returncode == 0:
                                print(f"{RED_BOLD}🌊 The corrupted file has been deleted (sudo rm -rf).{RESET}")
                            else:
                                print(f"{RED_BOLD}🌊 WARNING: Unable to delete {temp_path}. Please delete it manually.{RESET}")
                        except Exception:
                            print(f"{RED_BOLD}🌊 WARNING: Unable to delete {temp_path}. Please delete it manually.{RESET}")
                sys.exit(7)

        # 6. 移动到 /bin
        install_dir.mkdir(parents=True, exist_ok=True)

        if final_path.exists():
            if self._is_protected(final_path.name):
                print(f"{RED_BOLD}🌊 ERROR: Cannot overwrite protected package: {final_path.name}{RESET}")
                raise Exception("Protected package overwrite attempt")
            backup_path = final_path.with_suffix(final_path.suffix + ".bak")
            final_path.rename(backup_path)

        shutil.move(str(temp_path), str(final_path))

        # 7. 权限检查
        try:
            os.chmod(final_path, 0o755)
        except PermissionError:
            print(f"{RED_BOLD}🌊 Error: Permission wrong{RESET}")
            sys.exit(1)

        self.log_verbose(f"Moved to {final_path} ({final_path.stat().st_size} bytes)")
        print("🌊 Download complete!")

        # 8. 输出成功
        return final_path

    def install_package(self, package_name, args, version=None, install_dir=None, final_path=None, skip_db_update=False):
        if install_dir is None:
            install_dir = INSTALL_DIR
        if final_path is None:
            final_path = install_dir / package_name

        if not final_path.exists():
            print(f"{RED_BOLD}🌊 Error: Binary file not found after download.{RESET}")
            sys.exit(1)

        try:
            # 将绝对路径转换为 ~ 形式
            home = Path.home()
            display_path = final_path
            if str(final_path).startswith(str(home)):
                display_path = Path("~") / final_path.relative_to(home)

            print(f"🌊 Successfully installed {package_name} to {display_path}")
            if not skip_db_update:
                self._record_installation(package_name, version, install_dir, final_path=final_path)
            else:
                self.log_verbose("Skipping DB update (--skip-db-update specified)")

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

        # 1. 检查是否受保护
        if self._is_protected(safe_name):
            print(f"{RED_BOLD}🌊 ERROR: Cannot uninstall protected package: {safe_name}{RESET}")
            return

        # 2. 获取版本号
        version = None
        if '@' in package_spec:
            parts = package_spec.split('@')
            safe_name = parts[0].lower()
            if len(parts) > 1:
                version = parts[1]

        # 如果未指定版本，询问用户
        if not version:
            print(f"{RED_BOLD}🌊 Please enter the version number for '{safe_name}':{RESET}")
            version = input().strip()
            if not version:
                print(f"{RED_BOLD}🌊 ERROR: No version entered. Uninstall skipped.{RESET}")
                return

        # 3. 查询 installed.json 是否记录了该版本
        INSTALLED_DB.parent.mkdir(parents=True, exist_ok=True)
        install_dir = INSTALL_DIR

        if not INSTALLED_DB.exists():
            print(f"{RED_BOLD}🌊 ERROR: No download, uninstall skipped.{RESET}")
            return

        try:
            with open(INSTALLED_DB, 'r') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)
                installed = json.load(f)

            if safe_name not in installed:
                print(f"{RED_BOLD}🌊 ERROR: No download, uninstall skipped.{RESET}")
                return

            current_version = installed[safe_name].get('version', '0.0.0')
            if current_version != version:
                print(f"{RED_BOLD}🌊 ERROR: No download, uninstall skipped.{RESET}")
                return

            binary_path = Path(installed[safe_name].get('binary_path', str(install_dir / f"{safe_name}@{version}")))

        except Exception as e:
            print(f"{RED_BOLD}🌊 ERROR: No download, uninstall skipped.{RESET}")
            return

        # 4. 删除文件本身
        print(f"🌊 Deleting {binary_path}...")
        deleted = False
        if binary_path.exists():
            try:
                binary_path.unlink()
                deleted = True
            except PermissionError:
                deleted = self._delete_directory_with_sudo(binary_path)

        if not deleted:
            print(f"{RED_BOLD}🌊 WARNING: Failed to delete {binary_path}. Please delete manually.{RESET}")
            return

        # 5. 删除对应的 .bak 文件
        bak_path = binary_path.with_suffix(binary_path.suffix + ".bak")
        if bak_path.exists():
            print(f"🌊 Deleting backup file: {bak_path}...")
            bak_deleted = False
            try:
                bak_path.unlink()
                bak_deleted = True
            except PermissionError:
                bak_deleted = self._delete_directory_with_sudo(bak_path)

            if not bak_deleted:
                print(f"{RED_BOLD}🌊 WARNING: Failed to delete backup {bak_path}. Please delete manually.{RESET}")

        # 6. 备份 installed.json
        print("🌊 Backing up installed.json...")
        backup_path = INSTALLED_DB.with_name(f"installed.bak_{int(time.time())}.json")
        try:
            shutil.copy2(INSTALLED_DB, backup_path)
            print(f"🌊 Backup created: {backup_path}")
        except Exception as e:
            print(f"{RED_BOLD}🌊 WARNING: Backup failed. You may need to manually edit installed.json.{RESET}")

        # 7. 从 installed.json 删除该记录
        try:
            with open(INSTALLED_DB, 'r+') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                installed = json.load(f)
                if safe_name in installed:
                    del installed[safe_name]
                    f.seek(0)
                    f.truncate()
                    json.dump(installed, f, indent=2)
                    print(f"🌊 Removed '{safe_name}' from installation database.")
        except Exception as e:
            print(f"{RED_BOLD}🌊 WARNING: Failed to remove record from installed.json.{RESET}")
            print(f"{RED_BOLD}🌊 Error: {e}{RESET}")
            print(f"{RED_BOLD}🌊 Backup file available at: {backup_path}{RESET}")
            return

        # 8. 删除备份文件
        try:
            if backup_path.exists():
                backup_path.unlink()
                print(f"🌊 Backup file deleted.")
        except Exception:
            # 这里不再报错，因为数据库已经更新成功，备份残留无害
            pass

        # 9. 成功
        print(f"🌊 Successfully uninstalled {safe_name}@{version}.")

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
