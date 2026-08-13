#!/usr/bin/env python3
"""
MacWave 🌊
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
from pathlib import Path
from typing import Optional, Dict, Any, Union

# ==========================================
# 依赖库检查
# ==========================================

# 检查 requests 库（用于发送 HTTP 请求）
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

# 检查 packaging 库（用于安全地比较版本号大小）
try:
    from packaging.version import parse as parse_version
except ImportError:
    print("🌊 Error: 'packaging' library is not installed.")
    print("🌊 Please install it using: pip3 install packaging")
    sys.exit(1)

# 检查 rich 库（用于在终端显示漂亮的进度条）
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
    # 如果 rich 未安装，则退回到无进度条的模式，不影响实际功能
    pass


# ==========================================
# 全局常量定义
# ==========================================

VERSION = "1.0.0"                                   # 当前 MacWave 版本号
REPO_URL = "https://raw.githubusercontent.com/Sha0huaZhang/MacWave/main/repo/repo.json"  # 远程软件源地址
INSTALL_DIR = Path.home() / ".local" / "macwave" / "bin"    # 二进制文件默认安装目录
INSTALLED_DB = Path.home() / ".local" / "macwave" / "installed.json"  # 已安装包记录数据库
REPO_CACHE = Path.home() / ".local" / "macwave" / "repo_cache.json"   # 软件源本地缓存文件


# ==========================================
# 核心主类：MacWaveCLI
# ==========================================

class MacWaveCLI:
    def __init__(self):
        """初始化命令行界面，解析参数并设置日志系统"""
        self.parser = self._create_parser()
        self.verbose = False  # 是否开启详细调试模式

        # 初始化 fallback logger（避免在日志未配置时崩溃）
        self._logger = logging.getLogger("MacWave")
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(message)s'))
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)

    def _create_parser(self):
        """创建并配置命令行参数解析器，支持各种子命令和参数"""
        parser = argparse.ArgumentParser(
            prog="wave",
            description="MacWave 1.0.0 🌊\nA package manager for macOS/Linux jailbreak developers.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            usage="wave <command> [package] [flags]",
            epilog="For more details, visit: https://macwave.org"
        )
        
        # --- 全局 Flags ---
        parser.add_argument('-V', '--version', action='version', 
                          version=f'MacWave {VERSION} 🌊')
        parser.add_argument('-v', '--verbose', action='store_true',
                          help='Enable verbose output (显示详细的调试日志，包括异常堆栈)')
        parser.add_argument('-B', '--beta-version', action='store_true',
                          help='Install the latest beta version (如果可用，则安装最新测试版)')
        parser.add_argument('--proxy', type=str, metavar='string',
                          help='Specify an HTTP/HTTPS proxy (指定代理，如 http://127.0.0.1:8080)')
        parser.add_argument('--skip-ssl', action='store_true',
                          help='Skip SSL certificate verification (跳过SSL验证，不安全，需交互确认)')
        parser.add_argument('--limit-rate', type=str, metavar='string',
                          help='Limit download speed (限制下载速度，如 200K, 1M, 5M)')
        parser.add_argument('--dry-run', action='store_true',
                          help='Simulate the installation without making changes (模拟安装，不实际执行)')
        parser.add_argument('--json', action='store_true',
                          help='Output in JSON format (以 JSON 格式输出结果，方便脚本调用)')
        
        # --- 子命令 ---
        subparsers = parser.add_subparsers(dest="command", help="Commands")
        
        # 1. install 命令
        install_parser = subparsers.add_parser(
            "install", 
            help="Install a package (安装一个包)",
            usage="wave install <package_name> [flags]"
        )
        install_parser.add_argument("package_name", help="Name of the package to install (要安装的包名)")
        self._add_install_flags(install_parser)
        
        # 2. uninstall 命令
        uninstall_parser = subparsers.add_parser(
            "uninstall",
            help="Uninstall a package (卸载一个包)",
            usage="wave uninstall <package_name>"
        )
        uninstall_parser.add_argument("package_name", help="Name of the package to uninstall (要卸载的包名)")
        
        # 3. list 命令
        subparsers.add_parser("list", help="List installed packages (列出已安装的包)")
        
        # 4. search 命令
        search_parser = subparsers.add_parser(
            "search",
            help="Search for a package in the index (在软件源中搜索包)",
            usage="wave search <query> [flags]"
        )
        search_parser.add_argument("query", help="Search query (搜索关键词)")
        search_parser.add_argument('-f', '--fuzzy', action='store_true',
                                  help='Enable fuzzy search (启用模糊搜索，关键字可匹配任意位置)')
        
        # 5. info 命令
        info_parser = subparsers.add_parser(
            "info",
            help="Display detailed information about a package (显示包的详细信息)",
            usage="wave info <package_name>"
        )
        info_parser.add_argument("package_name", help="Name of the package (包名)")
        
        # 6. update 命令
        subparsers.add_parser("update", help="Update the package index (更新软件源索引)")
        
        # 7. upgrade 命令
        upgrade_parser = subparsers.add_parser(
            "upgrade",
            help="Upgrade an installed package to the latest version (升级已安装的包)",
            usage="wave upgrade <package_name>"
        )
        upgrade_parser.add_argument("package_name", help="Name of the package to upgrade (要升级的包名)")
        
        # 8. doctor 命令
        subparsers.add_parser("doctor", help="Check your system for missing dependencies (检查系统依赖)")
        
        return parser
    
    def _add_install_flags(self, parser):
        """为 install 命令添加特有的参数"""
        parser.add_argument('-D', '--dir', type=str, metavar='string',
                          help='Specify an output directory (指定下载输出的目录)')
        parser.add_argument('--ver', type=str, metavar='string',
                          help='Install a specific version of the package (安装指定版本的包)')
        parser.add_argument('-C', '--continue', dest='resume', action='store_true',
                          help='Resume interrupted downloads (恢复被中断的下载)')
    
    def _log(self, message: str, level: str = "info", force: bool = False):
        """
        统一的日志输出函数。
        如果 verbose 为 True 或者出现错误级别日志，则强制输出。
        """
        if self.verbose or force or level == "error":
            log_func = getattr(self._logger, level, self._logger.info)
            log_func(f"🌊 {message}")

    def log(self, message, force=False):
        """兼容旧代码的标准日志输出"""
        self._log(message, "info", force)

    def log_verbose(self, message):
        """仅在 verbose 模式启用的调试日志"""
        if self.verbose:
            self._log(message, "debug")

    def _confirm_skip_ssl(self, args) -> bool:
        """
        处理 --skip-ssl 参数。
        如果用户使用了该参数，必须弹出交互式询问确认，因为这是不安全的操作。
        """
        skip_ssl = getattr(args, 'skip_ssl', False)
        if not skip_ssl:
            return True  # 未启用，直接安全放行
        
        console = Console()
        console.print("--skip-ssl parameter will skip SSL certificate verification, it is insecure. Are you sure to continue?", style="bold red")
        response = input("[Y/n] ").strip().lower()
        
        if response in ['y', 'yes', '']:
            console.print("Install continue", style="bold red")
            return True
        else:
            console.print("Install stopped", style="bold green")
            return False

    def _confirm_missing_sha256(self) -> bool:
        """
        当软件源中没有提供 SHA256 校验值时，弹出交互式询问。
        因为缺少校验会存在安全隐患。
        """
        console = Console()
        console.print("Can't find SHA256 value, continuing installation will skip SHA256 verification, which may be insecure. Are you sure to continue?", style="bold red")
        response = input("[Y/n] ").strip().lower()
        
        if response in ['y', 'yes', '']:
            console.print("Install continue with SHA256 skipped", style="bold red")
            return True
        else:
            console.print("Install stopped", style="bold green")
            return False

    def _calculate_sha256(self, filepath: Path) -> str:
        """
        计算指定文件的 SHA256 哈希值。
        用于校验下载的文件是否完整、未被篡改。
        """
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            # 每次读取 4096 字节，避免一次性加载大文件导致内存溢出
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def fetch_repo_data(self, args=None):
        """
        拉取并解析远程软件源（repo.json）。
        采用智能缓存策略：
        - 缓存 5 分钟内：直接返回缓存（极速）。
        - 缓存 1 小时内：如果网络拉取失败，降级使用旧缓存（容错）。
        - 如果网络失败且无缓存：抛出异常。
        """
        REPO_CACHE.parent.mkdir(parents=True, exist_ok=True)

        # --- 尝试读取本地缓存 ---
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

        # 1. 缓存时间在 5 分钟以内，直接视为最新，直接返回（无需联网）
        if cache_data is not None and cache_age is not None and cache_age < 300:
            self.log_verbose("Using fresh cache")
            return cache_data

        # --- 准备联网拉取 ---
        session = requests.Session()
        session.headers.update({'User-Agent': 'MacWave/1.0.0'})
        
        # 设置网络重试策略：最多重试 3 次
        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        session.mount('https://', HTTPAdapter(max_retries=retries))

        request_kwargs = {'timeout': 10}  # 设置网络超时时间

        # 配置代理
        if args and getattr(args, 'proxy', None):
            proxy = args.proxy
            self.log_verbose(f"Using proxy: {proxy}")
            if proxy.startswith(('http://', 'https://')):
                request_kwargs['proxies'] = {'http': proxy, 'https': proxy}
            else:
                self._log(f"Proxy protocol '{proxy.split(':')[0]}' may not be supported. Use http:// or https://", "warning")

        # 配置 SSL 跳过验证
        if args and getattr(args, 'skip_ssl', False):
            self.log_verbose("SSL verification disabled")
            request_kwargs['verify'] = False
            urllib3.disable_warnings(InsecureRequestWarning)

        # --- 执行网络请求 ---
        try:
            self.log_verbose("Fetching fresh repo.json from network")
            response = session.get(REPO_URL, **request_kwargs)
            response.raise_for_status()
            data = response.json()

            # 请求成功，写入新缓存
            with open(REPO_CACHE, 'w') as f:
                json.dump(data, f, indent=2)
            self.log_verbose("Fetched and cached fresh repo.json")
            return data

        except requests.exceptions.RequestException as e:
            # 如果网络失败，但缓存是 1 小时内的，允许降级使用旧缓存
            if cache_data is not None and cache_age is not None and cache_age < 3600:
                self._log(f"Network failed, using stale cache (age: {cache_age:.1f}s): {e}", "warning")
                return cache_data
            # 否则，必须报错退出
            raise RuntimeError(f"Failed to fetch repository data after retries: {e}") from e
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON data received from repository: {e}") from e

    def find_package(self, repo_data, package_name, args=None):
        """
        在软件源数据中查找指定的包。
        支持指定版本 (--ver) 和测试版 (-B) 查找。
        返回匹配到的 release 信息（包含下载链接、版本号、SHA256 等）。
        """
        self.log_verbose(f"Searching for package: {package_name}")
        
        if "packages" in repo_data:
            for pkg in repo_data["packages"]:
                if pkg.get("name") == package_name:
                    self.log_verbose(f"Found package: {pkg.get('name')}")
                    releases = pkg.get("releases", [])
                    
                    # 1. 用户指定了具体版本号 (--ver)
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
                    
                    # 2. 用户请求安装测试版 (-B)
                    if args and getattr(args, 'beta_version', False):
                        self.log_verbose("User requested beta version.")
                        for release in releases:
                            if release.get("arch") == "beta":
                                self.log_verbose("Found beta release.")
                                return release
                        return None  # 没找到测试版，返回 None 让调用者处理
                    
                    # 3. 默认：查找与当前系统架构 (如 arm64, x86_64) 匹配的 release
                    current_arch = platform.machine().lower()
                    for release in releases:
                        if release.get("arch") == current_arch:
                            self.log_verbose(f"Found release matching architecture: {current_arch}")
                            return release
                    # 4. 如果找不到精确架构，寻找通用架构 (any)
                    for release in releases:
                        if release.get("arch") == "any":
                            self.log_verbose(f"Found fallback release with arch='any'")
                            return release
                    
                    # 如果都找不到，报错退出
                    print(f"🌊 Error: No release found for architecture '{current_arch}' or 'any' for package '{package_name}'")
                    sys.exit(1)
        
        print(f"🌊 Error: Package '{package_name}' not found in repository")
        sys.exit(1)
    
    def _parse_rate_limit(self, rate_str):
        """
        解析用户传入的限速字符串（如 "200K", "1M"）。
        将其转换为具体的每秒字节数（Bytes per second）。
        """
        rate_str = rate_str.upper().strip()
        multipliers = {'K': 1024, 'M': 1024**2, 'G': 1024**3}
        try:
            # 检查结尾是否有单位 K, M, G
            if rate_str[-1] in multipliers:
                return float(rate_str[:-1]) * multipliers[rate_str[-1]]
            # 如果没有单位，直接当做纯数字字节处理
            return float(rate_str)
        except ValueError:
            self.log(f"Invalid rate limit format '{rate_str}', ignoring limit.", force=True)
            return None

    def download_binary(self, url, package_name, args, install_dir=None, release=None):
        """
        核心下载函数。
        支持：断点续传 (-C)、进度条、SHA256 文件完整性校验、下载限速 (--limit-rate)。
        """
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
        
        final_path = install_dir / package_name          # 最终安装的二进制文件路径
        temp_path = install_dir / f"{package_name}.partial"  # 下载过程中的临时文件（断点续传依赖）
        
        install_dir.mkdir(parents=True, exist_ok=True)
        
        # --- 准备 HTTP 请求参数 ---
        request_kwargs = {
            'stream': True,  # 流式下载，不一次性加载到内存
            'timeout': 30
        }
        
        # 代理设置
        if args.proxy:
            request_kwargs['proxies'] = {'http': args.proxy, 'https': args.proxy}
            self.log_verbose(f"Using proxy: {args.proxy}")
        
        # SSL 跳过验证
        if args.skip_ssl:
            request_kwargs['verify'] = False
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            self.log_verbose("SSL verification disabled")
        
        # --- 断点续传处理逻辑 ---
        headers = {}
        resume_pos = 0
        should_resume = args.resume and temp_path.exists()  # 用户指定了 -C，且存在 .partial 文件
        
        if should_resume:
            try:
                resume_pos = temp_path.stat().st_size
                if resume_pos > 0:
                    # 组装 Range 请求头，告诉服务器从哪个字节开始给数据
                    headers['Range'] = f"bytes={resume_pos}-"
                    self.log_verbose(f"Resuming download from byte {resume_pos}")
                    print(f"🌊 Resuming from {resume_pos} bytes")
                else:
                    self.log_verbose("Partial file exists but is empty, starting from beginning")
                    temp_path.unlink()  # 如果文件是空的，删掉重新开始
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
            self.log_verbose(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
            content_length = response.headers.get('content-length')
            if content_length:
                self.log_verbose(f"Content-Length: {content_length} bytes")
            
            is_resume = False
            if should_resume and headers:
                if response.status_code == 206:
                    # 206 表示服务器支持断点续传，返回了部分内容
                    is_resume = True
                    self.log_verbose(f"Server supports resume, continuing from {resume_pos}")
                elif response.status_code == 200:
                    # 200 表示服务器不支持断点续传，返回了完整文件。
                    # 【关键修复】此时必须删掉之前损坏的 .partial 文件，重新从头下载！
                    self.log_verbose("Server does not support resume, restarting download from scratch")
                    
                    # 严格步骤 1：先 rm 删掉坏的文件
                    if temp_path.exists():
                        temp_path.unlink()
                        self.log_verbose(f"Removed corrupted partial file: {temp_path}")
                    
                    # 严格步骤 2：用红色字体给用户输出明确的警告
                    print("\033[91m🌊 Warning: The server does not support resuming downloads.\033[0m")
                    print("\033[91m🌊 To ensure file integrity, we are restarting the download completely from the beginning.\033[0m")
                    
                    # 重置状态，准备从头写入
                    resume_pos = 0
                    is_resume = False
                else:
                    self.log_verbose(f"Unexpected status code: {response.status_code}")
                    resume_pos = 0
            
            # 计算文件总大小（已下载的大小 + 剩余的大小）
            total_size = int(response.headers.get('content-length', 0)) + resume_pos
            if total_size == 0:
                total_size = None
                self.log_verbose("Total file size unknown (server did not send Content-Length)")
            else:
                self.log_verbose(f"Total file size: {total_size} bytes")
            
            # ================= 核心下载流程 =================
            if RICH_AVAILABLE:
                console = Console()
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
                
                # 【关键逻辑】使用 add_task 直接传入 total 大小和 completed 已完成的字节。
                # 这样进度条就能正确地从 44%（中断位置）开始走，一直走到 100%，而不是从 0 开始。
                with Progress(*progress_columns, console=console) as progress:
                    task_id = progress.add_task(
                        description=package_name,
                        total=total_size if total_size else None,
                        completed=resume_pos  # 告诉进度条，当前已经下载了多少字节
                    )
                    
                    if not total_size:
                        progress.update(task_id, description=f"{package_name} (unknown size)")
                    
                    mode = 'ab' if is_resume else 'wb'  # 续传用追加模式，新下载用覆盖模式
                    downloaded = resume_pos

                    # ================= 新增：限速逻辑所需变量 =================
                    limit_bps = None
                    if args.limit_rate:
                        limit_bps = self._parse_rate_limit(args.limit_rate)
                        if limit_bps is not None:
                            self.log_verbose(f"Download rate limit set to {limit_bps} bytes/sec")
                    
                    # 计算限速的时间窗口变量
                    rate_start_time = time.time()
                    rate_bytes_in_window = 0
                    # ================= 结束新增 =================
                    
                    with open(temp_path, mode) as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                chunk_size_bytes = len(chunk)
                                downloaded += chunk_size_bytes

                                # ================= 新增：实际限速执行 =================
                                if limit_bps:
                                    rate_bytes_in_window += chunk_size_bytes
                                    # 按照目标速度，当前窗口内理论上应该过去的时间 (秒)
                                    expected_time = rate_bytes_in_window / limit_bps
                                    actual_time = time.time() - rate_start_time
                                    
                                    # 如果当前实际花费的时间少于理论时间，说明下载太快了，需要休眠
                                    if actual_time < expected_time:
                                        time.sleep(expected_time - actual_time)
                                    
                                    # 当实际时间超过 1 秒时，重新开始计算下一段窗口
                                    if actual_time >= 1.0:
                                        rate_start_time = time.time()
                                        rate_bytes_in_window = 0
                                # ================= 结束新增 =================

                                # 更新进度条
                                progress.update(task_id, advance=chunk_size_bytes)
            else:
                # 如果没有安装 rich 库，使用最基础的打印点号作为备选方案
                self.log_verbose("rich library not available, using simple progress indicator")
                mode = 'ab' if is_resume else 'wb'
                downloaded = resume_pos
                
                # ================= 新增：备选方案的限速逻辑 =================
                limit_bps = None
                if args.limit_rate:
                    limit_bps = self._parse_rate_limit(args.limit_rate)
                
                rate_start_time = time.time()
                rate_bytes_in_window = 0
                # ================= 结束新增 =================
                
                with open(temp_path, mode) as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            chunk_size_bytes = len(chunk)
                            downloaded += len(chunk)

                            # ================= 新增：备选限速执行 =================
                            if limit_bps:
                                rate_bytes_in_window += chunk_size_bytes
                                expected_time = rate_bytes_in_window / limit_bps
                                actual_time = time.time() - rate_start_time
                                if actual_time < expected_time:
                                    time.sleep(expected_time - actual_time)
                                if actual_time >= 1.0:
                                    rate_start_time = time.time()
                                    rate_bytes_in_window = 0
                            # ================= 结束新增 =================

                            if self.verbose:
                                print(".", end="", flush=True)
                if self.verbose:
                    print(" 🌊")
            # ================= 核心下载流程结束 =================
            
            # --- SHA256 文件校验 ---
            if release and release.get("sha256"):
                expected_sha256 = release.get("sha256")
                self.log_verbose(f"Expected SHA256: {expected_sha256}")
                print("🌊 Verifying SHA256...")
                actual_sha256 = self._calculate_sha256(temp_path)
                self.log_verbose(f"Actual SHA256: {actual_sha256}")
                if actual_sha256 != expected_sha256:
                    # 校验失败，删掉损坏的文件，直接退出
                    temp_path.unlink()
                    print(f"🌊 SHA256 verification failed!")
                    print(f"🌊 Expected: {expected_sha256}")
                    print(f"🌊 Actual:   {actual_sha256}")
                    print(f"🌊 File may have been tampered with or corrupted.")
                    sys.exit(1)
                else:
                    self.log_verbose("SHA256 verification passed")
                    print(f"🌊 SHA256 verified successfully")
            else:
                # 如果元数据里没提供 SHA256，必须询问用户是否继续
                self.log_verbose("No SHA256 value found in release metadata")
                if not self._confirm_missing_sha256():
                    temp_path.unlink()
                    sys.exit(0)
            
            # --- 安装完成：重命名并赋予可执行权限 ---
            temp_path.rename(final_path)
            os.chmod(final_path, 0o755)  # rwxr-xr-x (所有用户可读可执行)
            self.log_verbose(f"Downloaded {final_path.stat().st_size} bytes to {final_path}")
            print(f"🌊 Download complete!")
            
        except KeyboardInterrupt:
            # 用户按 Ctrl+C 中断下载，保存当前进度并提示如何使用 -C 续传
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
        """完成安装的后置步骤：记录数据库，并提示用户设置 PATH 环境变量"""
        if install_dir is None:
            install_dir = INSTALL_DIR
        
        if args.dry_run:
            print(f"🌊 [DRY RUN] Would install {package_name} to {install_dir}")
            return
        
        binary_path = install_dir / package_name
        if not binary_path.exists():
            print(f"🌊 Error: Binary file not found after download.")
            sys.exit(1)
        
        self.log_verbose(f"Installing to: {binary_path}")
        self.log_verbose(f"File size: {binary_path.stat().st_size} bytes")
        
        try:
            print(f"🌊 Successfully installed {package_name} to {binary_path}")
            self._record_installation(package_name, version, install_dir)
            
            # 检查安装目录是否在系统的 PATH 环境变量中
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
        """
        将安装的包记录到本地 installed.json 文件中。
        使用 fcntl 文件锁保证多进程并发安装时的数据安全性。
        """
        if install_dir is None:
            install_dir = INSTALL_DIR
        
        try:
            INSTALLED_DB.parent.mkdir(parents=True, exist_ok=True)
            
            with open(INSTALLED_DB, 'a+') as f:
                # 获取互斥锁，确保同一时间只有一个进程能写入数据库
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                
                f.seek(0)
                try:
                    content = f.read()
                    installed = json.loads(content) if content else {}
                except json.JSONDecodeError:
                    installed = {}
                
                # 记录包名、版本号和安装路径
                installed[package_name] = {
                    "version": release_version,
                    "binary_path": str(install_dir / package_name)
                }
                
                f.seek(0)
                f.truncate()
                json.dump(installed, f, indent=2)
                
                # 释放锁
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                
        except Exception as e:
            self.log(f"Warning: Could not record installation: {e}", force=True)
    
    def handle_install(self, args):
        """处理 install 安装命令的主逻辑"""
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
        
        # 如果指定了特定版本（--ver）
        if args.ver:
            release = self.find_package(repo_data, safe_name, args)
            if release:
                self.download_binary(release["binary_url"], safe_name, args, install_dir, release)
                self.install_package(safe_name, args, release.get("version"), install_dir)
            return
        
        # 如果指定了测试版（-B）
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
        
        # 默认：安装最新稳定版
        release = self.find_package(repo_data, safe_name, args)
        self.download_binary(release["binary_url"], safe_name, args, install_dir, release)
        self.install_package(safe_name, args, release.get("version"), install_dir)
    
    def handle_uninstall(self, args):
        """处理 uninstall 卸载命令"""
        safe_name = args.package_name.lower()
        if not INSTALLED_DB.exists():
            print(f"🌊 No packages installed. Nothing to uninstall.")
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
            if binary_path.exists():
                binary_path.unlink()
                print(f"🌊 Removed binary: {binary_path}")
            else:
                print(f"🌊 Warning: Binary file not found, but removing from database.")
            
            # 从数据库中移除记录
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
        """处理 list 列出所有已安装包的命令"""
        if not INSTALLED_DB.exists():
            print("🌊 No packages installed yet.")
            return
        try:
            with open(INSTALLED_DB, 'r') as f:
                installed = json.load(f)
            print("🌊 Installed packages:")
            for pkg_name, info in installed.items():
                version = info.get('version', 'unknown')
                print(f"  - {pkg_name} (v{version})")
        except Exception as e:
            print(f"🌊 Error: Could not read installed packages: {e}")
    
    def handle_search(self, args):
        """处理 search 搜索命令"""
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
                    # 模糊匹配：只要包含关键词即可
                    if query in name or query in desc:
                        matches.append(pkg)
                else:
                    # 精确匹配：必须以关键词开头
                    if name.startswith(query) or desc.startswith(query):
                        matches.append(pkg)
        if not matches:
            print(f"🌊 No packages found matching '{args.query}'")
            return
        print(f"🌊 Found {len(matches)} package(s) matching '{args.query}':")
        for pkg in matches:
            name = pkg.get("name", "Unknown")
            desc = pkg.get("description", "No description")
            print(f"  - {name}: {desc}")
    
    def handle_info(self, args):
        """处理 info 查看包详细信息的命令"""
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
        """处理 update 强制更新软件源的命令"""
        print("🌊 Forcing update: fetching fresh package index...")
        try:
            if REPO_CACHE.exists():
                REPO_CACHE.unlink()  # 删除旧缓存，强制重新拉取
            repo_data = self.fetch_repo_data(args)
            print(f"🌊 Package index updated successfully. Found {len(repo_data.get('packages', []))} packages.")
        except RuntimeError as e:
            print(f"🌊 {e}")
            sys.exit(1)
        except Exception as e:
            print(f"🌊 Error: Failed to update package index: {e}")
    
    def handle_upgrade(self, args):
        """处理 upgrade 升级指定包的命令"""
        safe_name = args.package_name.lower()
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
            
            # 比较本地和远程的版本号
            try:
                local_v = parse_version(local_version)
                remote_v = parse_version(remote_version)
                if local_v >= remote_v:
                    print(f"🌊 Package '{safe_name}' is already up to date (v{local_version}).")
                    return
            except Exception:
                # 如果版本号格式无法解析，采用简单的字符串比较
                if local_version >= remote_version:
                    print(f"🌊 Package '{safe_name}' is already up to date (v{local_version}).")
                    return
            
            print(f"🌊 Upgrading '{safe_name}' from v{local_version} to v{remote_version}...")
            binary_path = INSTALL_DIR / safe_name
            if binary_path.exists():
                binary_path.unlink()
            del installed[safe_name]
            with open(INSTALLED_DB, 'w') as f:
                json.dump(installed, f, indent=2)
            self.download_binary(release["binary_url"], safe_name, args, release=release)
            self.install_package(safe_name, args, release.get("version"))
        except Exception as e:
            print(f"🌊 Error: Failed to upgrade package: {e}")
    
    def handle_doctor(self, args):
        """处理 doctor 检查系统命令（预留）"""
        print(f"🌊 Command 'doctor' is not implemented yet.")
    
    def run(self):
        """程序的主要运行入口，调度各个子命令"""
        # 使用 parse_known_args 来容忍未知参数
        args, unknown = self.parser.parse_known_args()
        
        # 因为 parse_known_args 可能将 --skip-ssl 漏掉，手动做一层兜底检测
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
        
        # 交互式确认 --skip-ssl 参数
        if not self._confirm_skip_ssl(args):
            sys.exit(0)
        
        if not args.command:
            self.parser.print_help()
            return
        
        # 子命令分发器
        command_handlers = {
            "install": self.handle_install,
            "uninstall": self.handle_uninstall,
            "list": self.handle_list,
            "search": self.handle_search,
            "info": self.handle_info,
            "update": self.handle_update,
            "upgrade": self.handle_upgrade,
            "doctor": self.handle_doctor,
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
