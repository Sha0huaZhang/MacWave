#!/usr/bin/env python3
"""pkginstaller.py"""

import os
import sys
import json
import hashlib
import shutil
import fcntl
import time
import logging
import argparse
import platform
import subprocess
import traceback
from pathlib import Path

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

CONFIG_FILE = Path("/opt/macwave_config/config.json")
VERSION_FILE = Path("/opt/macwave_config/VERSION.json")

def get_version():
    if VERSION_FILE.exists():
        try:
            with open(VERSION_FILE, 'r') as f:
                data = json.load(f)
                return data.get("version", "unknown")
        except Exception:
            pass
    return "unknown"

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
DOWNLOAD_TMP = BASE_DIR / "downloads" / "tmp"

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
# 核心辅助函数
# ==========================================

def _parse_rate_limit(rate_str):
    rate_str = rate_str.upper().strip()
    multipliers = {'K': 1024, 'M': 1024**2, 'G': 1024**3}
    try:
        if rate_str[-1] in multipliers:
            return float(rate_str[:-1]) * multipliers[rate_str[-1]]
        return float(rate_str)
    except ValueError:
        return None


def _check_disk_space(path: Path, required_bytes: int = 10 * 1024 * 1024) -> bool:
    total, used, free = shutil.disk_usage(path)
    if free < required_bytes:
        print(f"{RED_BOLD}🌊 Error: Insufficient disk space in {path}.{RESET}")
        sys.exit(1)
    return True


# ==========================================
# 获取最高版本（通过 GitHub API）
# ==========================================

def fetch_max_version(package_name):
    """
    遍历 infosource 分支，通过 GitHub API 获取文件名并提取版本号。
    调用 pkgversionparser.py 进行排序，获取最终的最高版本。
    """
    api_url = f"https://api.github.com/repos/Sha0huaZhang/MacWave/contents/pkg/pkginfo_{ARCH}/{package_name}"
    try:
        response = requests.get(api_url, timeout=30)
        if response.status_code != 200:
            print(f"{RED_BOLD}🌊 Error: Cannot fetch package list.{RESET}")
            sys.exit(1)

        file_list = response.json()
        versions = []
        for item in file_list:
            fname = item["name"]
            if fname.endswith("@common"):
                continue
            if "@" in fname:
                versions.append(fname.split("@")[1])

        # 调用 pkgversionparser.py 进行排序
        from pkgversionparser import get_max_version
        return get_max_version(versions)
    except Exception as e:
        print(f"{RED_BOLD}🌊 Error: Failed to fetch version list: {e}{RESET}")
        sys.exit(1)


# ==========================================
# 核心安装流程
# ==========================================

def handle_install(input_string):
    # 1. 解析包名
    parts = input_string.split()
    if len(parts) >= 2:
        raw_pkg = parts[1]
    else:
        print(f"{RED_BOLD}🌊 Error: Invalid package name{RESET}")
        sys.exit(1)

    if "@" in raw_pkg:
        ParsePkgName = raw_pkg.split("@")[0]
    else:
        ParsePkgName = raw_pkg

    # 2. 获取架构
    global ARCH
    machine = platform.machine().lower()
    if machine in ["arm64", "aarch64"]:
        ARCH = "arm64"
    elif machine in ["x86_64", "amd64"]:
        ARCH = "amd64"
    else:
        print(f"{RED_BOLD}🌊 Error: Unknown Arch!{RESET}")
        sys.exit(1)


    # 3. 解析版本号
    ParsePkgVersion = None
    if "@" in input_string:
        if "--ver" in input_string:
            print(f"{RED_BOLD}🌊 Error: Repeated Version Number{RESET}")
            sys.exit(1)
        else:
            ParsePkgVersion = input_string.split("@")[1].split(" ")[0].strip()
    elif "--ver" in input_string:
        ParsePkgVersion = input_string.split("--ver")[1].strip().split(" ")[0]
    else:
        # 通过 GitHub API 获取最高版本
        print("🌊 Fetching version info...")
        ParsePkgVersion = fetch_max_version(ParsePkgName)
        print("🌊 Version info fetched successfully.")

    # 4. 获取远程 URL 和 SHA256
    pkg_version_url = f"https://raw.githubusercontent.com/Sha0huaZhang/MacWave/infosource/pkg/pkginfo_{ARCH}/{ParsePkgName}/{ParsePkgName}@{ParsePkgVersion}"
    try:
        resp = requests.get(pkg_version_url)
        if resp.status_code != 200:
            if "-v" in input_string or "--verbose" in input_string:
                print(resp.text)
            elif resp.status_code == 404:
                print(f"{RED_BOLD}🌊 Error: Can't find parse pacakge version.\n🌊 If you certain this version is existent, Please contact the administrator.{RESET}")
                sys.exit(1)
            else:
                print(f"{RED_BOLD}🌊 Error: Service unavailable, Please contact the administrator.{RESET}")
                sys.exit(1)
    except Exception as e:
        print(f"{RED_BOLD}🌊 Error: {e}{RESET}")
        sys.exit(1)

    # 提取 URL 和 SHA256
    import re
    url_match = re.search(r'url:\s*"([^"]+)"', resp.text)
    sha_match = re.search(r'sha256:\s*"([^"]+)"', resp.text)

    if url_match:
        ParsePkgURL = url_match.group(1)
    else:
        print(f"{RED_BOLD}🌊 Error: URL field not found.{RESET}")
        sys.exit(1)

    if sha_match:
        ParsePkgSHA256 = sha_match.group(1)
    else:
        ParsePkgSHA256 = None

    # 5. URL 检查
    if not ParsePkgURL.startswith("https://"):
        if ParsePkgURL.startswith("http://"):
            print(f"{RED_BOLD}🌊 ParsePkgURL using HTTP！That's insecure, Please contact the administrator.{RESET}")
            sys.exit(1)
        else:
            print(f"{RED_BOLD}🌊 ParsePkgURL Invalid, Please contact the administrator.{RESET}")
            sys.exit(1)

    # 6. 下载前准备
    original_filename = ParsePkgURL.split("/")[-1]
    CONFIG = DOWNLOAD_TMP
    CONFIG.mkdir(parents=True, exist_ok=True)
    temp_path = CONFIG / f"{original_filename}.partial"
    if temp_path.exists():
        temp_path.unlink()

    # 7. 下载（包含 2.0 RC 的重试逻辑和 Rich 进度条）
    download_success = False
    attempt = 0
    while not download_success:
        attempt += 1
        try:
            response = requests.get(ParsePkgURL, stream=True)

            if response.status_code == 404:
                print(f"{RED_BOLD}🌊 Error: ErrorCode 404 - The URL or file does not exist.{RESET}")
                print(f"{RED_BOLD}🌊 URL: {ParsePkgURL}{RESET}")
                sys.exit(404)
            elif response.status_code != 200:
                print(f"{RED_BOLD}🌊 Error: ErrorCode {response.status_code}{RESET}")
                print(f"{RED_BOLD}🌊 URL: {ParsePkgURL}{RESET}")
                sys.exit(response.status_code)

            total_size = int(response.headers.get('content-length', 0))
            limit_bps = None
            if '--limit-rate' in input_string:
                limit_rate_str = input_string.split('--limit-rate')[1].strip().split(' ')[0]
                limit_bps = _parse_rate_limit(limit_rate_str)
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
                    task_id = progress.add_task(description=f"🌊 {ParsePkgName}", total=total_size or None, speed="0 B/s")

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
                            if '-v' in input_string or '--verbose' in input_string:
                                print(".", end="", flush=True)
                if '-v' in input_string or '--verbose' in input_string:
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
            print(f"{RED_BOLD}🌊 Error: {e}{RESET}")
            sys.exit(1)

    # 8. 删掉 .partial 后缀，恢复原文件名
    final_download_path = CONFIG / original_filename
    temp_path.rename(final_download_path)

    # 9. 拼接长字符串并传给 pkginstaller.sh
    # ParseDir 固定为 BASE_DIR/bin/软件包名@版本号
    parse_dir_value = f"{BASE_DIR}/bin/{ParsePkgName}@{ParsePkgVersion}"
    pkg_info_string = (
        f"{ParsePkgName}\n{ParsePkgVersion}\n{ParsePkgSHA256}\n{parse_dir_value}"
    )

    # 调用 pkginstaller.sh
    try:
        script_path = os.path.join(os.path.dirname(__file__), 'pkginstaller.sh')
        result = subprocess.run(
            ['bash', script_path, pkg_info_string],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(result.stderr)
            sys.exit(result.returncode)
        print(result.stdout.strip())
    except Exception as e:
        print(f"{RED_BOLD}🌊 Error: Failed to invoke shell script: {e}{RESET}")
        sys.exit(1)