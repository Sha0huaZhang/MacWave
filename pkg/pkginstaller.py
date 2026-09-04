#!/usr/bin/env python3
"""
LinuxWave / MacWave Package Installer (2.1)
负责下载、调用 shasum256.sh 校验、调用 pkgunzip.sh 解压、生成 _path / _deps。
依赖的复杂管理、路径重定向、备份由 depsmanager.sh 处理。
"""

import os
import sys
import json
import shutil
import fcntl
import time
import logging
import argparse
import subprocess
from pathlib import Path

# ==========================================
# 颜色定义
# ==========================================

RED_BOLD = '\033[1;31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
RESET = '\033[0m'

# ==========================================
# 配置加载（自动识别 MacWave / LinuxWave）
# ==========================================

CONFIG_FILE = Path("/opt/macwave_config/config.json")
VERSION_FILE = Path("/opt/macwave_config/VERSION.json")

def get_config_path():
    if CONFIG_FILE.exists():
        return CONFIG_FILE
    alt = Path("/opt/linuxwave_config/config.json")
    if alt.exists():
        return alt
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
INSTALLED_DB = BASE_DIR / "pkg" / "installed.json"
DEPS_DIR = BASE_DIR / "deps"
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

    def _confirm_missing_sha256(self) -> bool:
        print(f"{RED_BOLD}🌊 WARNING: This package has NO SHA256 checksum provided.{RESET}")
        print(f"{RED_BOLD}🌊 Skipping SHA256 verification is INSECURE and may expose you to tampered files.{RESET}")
        response = input(f"{RED_BOLD}🌊 Are you sure to continue? [Y]: {RESET}").strip()
        return response == 'Y' or response == 'y'

    def _confirm_action(self, message: str) -> bool:
        response = input(f"{RED_BOLD}🌊 {message} [Y/n] {RESET}").strip()
        return response == 'Y' or response == 'y'

    def _check_disk_space(self, path: Path, required_bytes: int = 10 * 1024 * 1024) -> bool:
        total, used, free = shutil.disk_usage(path)
        if free < required_bytes:
            print(f"{RED_BOLD}🌊 Error: Insufficient disk space in {path}.{RESET}")
            sys.exit(1)
        return True

    def _verify_sha256(self, file_path: Path, expected_sha256: str):
        import subprocess
        shasum_path = Path(__file__).resolve().parent / "shasum256.sh"
        result = subprocess.run(
            ['bash', str(shasum_path), str(file_path), expected_sha256],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            sys.exit(result.returncode)

    def _process_downloaded_file(self, temp_path: Path, package_name: str, final_path: Path):
        archive_suffix = ['.zip', '.tar.gz', '.tgz', '.tar.bz2', '.tar.xz', '.gz', '.bz2']
        is_archive = any(temp_path.name.endswith(s) for s in archive_suffix)

        if is_archive:
            print(f"🌊 Extracting archive...")
            extract_dir = DOWNLOAD_TMP / f"{package_name}_extract"
            if extract_dir.exists():
                shutil.rmtree(extract_dir, ignore_errors=True)
            extract_dir.mkdir(parents=True, exist_ok=True)

            import subprocess
            pkgunzip_path = Path(__file__).resolve().parent / "pkgunzip.sh"
            result = subprocess.run(
                ['bash', str(pkgunzip_path), str(temp_path), str(extract_dir)],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                print(f"{RED_BOLD}🌊 Error: Failed to extract archive: {result.stderr}{RESET}")
                if temp_path.exists():
                    temp_path.unlink()
                sys.exit(1)

            main_binary = None
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    if file == package_name:
                        main_binary = Path(root) / file
                        break
                if main_binary:
                    break

            if not main_binary:
                for root, dirs, files in os.walk(extract_dir):
                    for file in files:
                        if '.' not in file:
                            main_binary = Path(root) / file
                            break
                    if main_binary:
                        break

            if not main_binary:
                print(f"{RED_BOLD}🌊 Error: Could not find main binary in extracted archive.{RESET}")
                sys.exit(1)

            final_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(main_binary), str(final_path))
            shutil.rmtree(extract_dir, ignore_errors=True)

        else:
            final_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(temp_path), str(final_path))

        os.chmod(final_path, 0o755)
        self.log_verbose(f"Installed to {final_path} ({final_path.stat().st_size} bytes)")

    def download_binary(self, url, package_name, args, install_dir=None, release=None, final_path=None):
        if install_dir is None:
            install_dir = INSTALL_DIR
        if final_path is None:
            final_path = install_dir / package_name

        if not url:
            print(f"{RED_BOLD}🌊 Error: URLNone{RESET}")
            sys.exit(1)

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

        self.log_verbose(f"Download URL: {url}")
        print(f"🌊 Downloading {package_name}...")

        DOWNLOAD_TMP.mkdir(parents=True, exist_ok=True)
        self._check_disk_space(DOWNLOAD_TMP)

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

                with open(temp_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

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

        print("🌊 Verifying SHA256...")
        self._verify_sha256(temp_path, release.get("sha256"))
        self._process_downloaded_file(temp_path, package_name, final_path)
        print("🌊 Download complete!")

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
            print(f"🌊 Successfully installed {package_name} to {final_path}")
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


def main():
    parser = argparse.ArgumentParser(description="MacWave / LinuxWave Package Installer")
    parser.add_argument('--version', action='version', version=f'Package Installer {VERSION}')
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
        print(f"{RED_BOLD}🌊 Error: Uninstall command is handled by depsmanager.sh{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🌊 Download interrupted by user.")
        print("🌊 Operation cancelled by user.")
        print("🌊 Tip: You can resume the download next time using: wave install <package_name> -C")
        sys.exit(130)
