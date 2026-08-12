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


class AlignedHelpFormatter(argparse.RawDescriptionHelpFormatter):
    """
    自定义帮助信息格式化器。
    当选项没有短参数（如 --proxy）时，用空格填充短参数位置，使长参数对齐。
    """
    
    def _format_action_invocation(self, action):
        """重写父类方法，控制选项在帮助中的显示格式。"""
        if not action.option_strings:
            return super()._format_action_invocation(action)
        
        options = action.option_strings
        
        # 判断是否有短参数（如 -v, -B），有则显示 "-s, --long"
        if len(options) >= 2 and options[0].startswith('-') and len(options[0]) <= 2:
            return ', '.join(options)
        else:
            # 没有短参数，用 5 个空格填充，与有短参数的行对齐
            return '     ' + options[0]


# =============================================================================
# 第三方库导入与检查
# =============================================================================

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

try:
    from packaging.version import parse as parse_version
except ImportError:
    print("🌊 Error: 'packaging' library is not installed.")
    print("🌊 Please install it using: pip3 install packaging")
    sys.exit(1)

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


# =============================================================================
# 常量配置
# =============================================================================

VERSION = "1.0.0"
REPO_URL = "https://raw.githubusercontent.com/Sha0huaZhang/MacWave/main/repo/repo.json"
INSTALL_DIR = Path.home() / ".local" / "macwave" / "bin"
INSTALLED_DB = Path.home() / ".local" / "macwave" / "installed.json"
REPO_CACHE = Path.home() / ".local" / "macwave" / "repo_cache.json"


# =============================================================================
# 主类
# =============================================================================

class MacWaveCLI:
    """MacWave 命令行工具的主类，管理所有命令和参数。"""

    def __init__(self):
        self.parser = self._create_parser()
        self.verbose = False
        self._logger = logging.getLogger("MacWave")
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(message)s'))
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)

    # -------------------------------------------------------------------------
    # 命令行参数解析
    # -------------------------------------------------------------------------

    def _create_parser(self):
        """
        创建并配置 argparse 解析器。
        定义所有全局参数和子命令（install, uninstall, list 等）。
        """
        parser = argparse.ArgumentParser(
            prog="wave",
            description="MacWave 1.0.0 🌊\nA package manager for macOS/Linux jailbreak developers.",
            formatter_class=AlignedHelpFormatter,
            usage="wave <command> [package] [flags]",
            epilog="For more details, visit: https://macwave.org"
        )
        
        # ---------- 全局参数 ----------
        parser.add_argument('-V', '--version', action='version', 
                          version=f'MacWave {VERSION} 🌊')
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
        
        # ---------- 子命令 ----------
        subparsers = parser.add_subparsers(dest="command", help="Commands")
        
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
        
        return parser
    
    def _add_install_flags(self, parser):
        """为 install 子命令添加专属参数。"""
        parser.add_argument('-D', '--dir', type=str,
                          help='Specify an output directory (e.g., ~/Desktop) for downloads')
        parser.add_argument('--ver', type=str,
                          help='Install a specific version of the package (e.g., --ver 1.0.0)')
        parser.add_argument('-C', '--continue', dest='resume', action='store_true',
                          help='Resume interrupted downloads (use with install command)')
    
    # -------------------------------------------------------------------------
    # 日志与输出
    # -------------------------------------------------------------------------

    def _log(self, message: str, level: str = "info", force: bool = False):
        """内部日志方法，支持等级控制。"""
        if self.verbose or force or level == "error":
            log_func = getattr(self._logger, level, self._logger.info)
            log_func(f"🌊 {message}")

    def log(self, message, force=False):
        """公开日志方法，默认 info 级别。"""
        self._log(message, "info", force)

    def log_verbose(self, message):
        """仅在 verbose 模式开启时输出。"""
        if self.verbose:
            self._log(message, "debug")

    # -------------------------------------------------------------------------
    # 交互确认
    # -------------------------------------------------------------------------

    def _confirm_skip_ssl(self, args) -> bool:
        """
        处理 --skip-ssl 的交互确认。
        用户必须输入 y 或直接回车才能继续，输入 n 则终止安装。
        """
        skip_ssl = getattr(args, 'skip_ssl', False)
        if not skip_ssl:
            return True
        
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
        当包索引中缺少 SHA256 值时，询问用户是否继续。
        跳过验证存在安全风险，需用户明确确认。
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

    # -------------------------------------------------------------------------
    # SHA256 工具
    # -------------------------------------------------------------------------

    def _calculate_sha256(self, filepath: Path) -> str:
        """计算文件的 SHA256 哈希值，分块读取以支持大文件。"""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    # -------------------------------------------------------------------------
    # 包索引获取（含缓存机制）
    # -------------------------------------------------------------------------

    def fetch_repo_data(self, args=None):
        """
        获取远程包索引 repo.json，支持缓存策略：
        - 缓存 5 分钟内：直接返回
        - 缓存 1 小时内：网络失败时使用缓存
        - 超过 1 小时或网络失败：尝试重新获取
        """
        REPO_CACHE.parent.mkdir(parents=True, exist_ok=True)

        cache_data: Optional[Dict[str, Any]] = None
        cache_age: Optional[float] = None

        # 加载缓存
        if REPO_CACHE.exists():
            try:
                with open(REPO_CACHE, 'r') as f:
                    cache_data = json.load(f)
                cache_age = time.time() - REPO_CACHE.stat().st_mtime
                self.log_verbose(f"Cache exists, age: {cache_age:.1f}s")
            except (json.JSONDecodeError, OSError) as e:
                self._log(f"Cache corrupted: {e}", "warning")
                cache_data = None

        # 新鲜缓存（5 分钟内）直接使用
        if cache_data is not None and cache_age is not None and cache_age < 300:
            self.log_verbose("Using fresh cache")
            return cache_data

        # 准备网络请求
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

        # 代理配置
        if args and getattr(args, 'proxy', None):
            proxy = args.proxy
            self.log_verbose(f"Using proxy: {proxy}")
            if proxy.startswith(('http://', 'https://')):
                request_kwargs['proxies'] = {'http': proxy, 'https': proxy}
            else:
                self._log(f"Proxy protocol '{proxy.split(':')[0]}' may not be supported. Use http:// or https://", "warning")

        # SSL 跳过（不安全）
        if args and getattr(args, 'skip_ssl', False):
            self.log_verbose("SSL verification disabled")
            request_kwargs['verify'] = False
            urllib3.disable_warnings(InsecureRequestWarning)

        # 执行网络请求
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
            # 网络失败时，如果缓存还在 1 小时内，使用缓存
            if cache_data is not None and cache_age is not None and cache_age < 3600:
                self._log(f"Network failed, using stale cache (age: {cache_age:.1f}s): {e}", "warning")
                return cache_data
            raise RuntimeError(f"Failed to fetch repository data after retries: {e}") from e
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Invalid JSON data received from repository: {e}") from e

    # -------------------------------------------------------------------------
    # 包查找
    # -------------------------------------------------------------------------

    def find_package(self, repo_data, package_name, args=None):
        """
        在索引中查找指定包，并返回匹配的 release。
        支持 --ver 指定版本、-B 选择 beta 版本，以及自动匹配当前架构。
        """
        self.log_verbose(f"Searching for package: {package_name}")
        
        if "packages" in repo_data:
            for pkg in repo_data["packages"]:
                if pkg.get("name") == package_name:
                    self.log_verbose(f"Found package: {pkg.get('name')}")
                    releases = pkg.get("releases", [])
                    
                    # 优先匹配 --ver 指定的版本
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
                    
                    # 匹配 beta 版本
                    if args and getattr(args, 'beta_version', False):
                        self.log_verbose("User requested beta version.")
                        for release in releases:
                            if release.get("arch") == "beta":
                                self.log_verbose("Found beta release.")
                                return release
                        return None
                    
                    # 匹配当前系统架构
                    current_arch = platform.machine().lower()
                    for release in releases:
                        if release.get("arch") == current_arch:
                            self.log_verbose(f"Found release matching architecture: {current_arch}")
                            return release
                    # 回退到 "any" 架构
                    for release in releases:
                        if release.get("arch") == "any":
                            self.log_verbose(f"Found fallback release with arch='any'")
                            return release
                    
                    print(f"🌊 Error: No release found for architecture '{current_arch}' or 'any' for package '{package_name}'")
                    sys.exit(1)
        
        print(f"🌊 Error: Package '{package_name}' not found in repository")
        sys.exit(1)
    
    # -------------------------------------------------------------------------
    # 下载与验证
    # -------------------------------------------------------------------------

    def download_binary(self, url, package_name, args, install_dir=None, release=None):
        """
        下载二进制文件，支持：
        - curl 风格进度条（依赖 rich）
        - 断点续传（-C）
        - SHA256 强制验证
        - Ctrl+C 干净退出
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
        
        final_path = install_dir / package_name
        temp_path = install_dir / f"{package_name}.partial"  # 临时文件，用于断点续传
        
        install_dir.mkdir(parents=True, exist_ok=True)
        
        # 准备请求参数
        request_kwargs = {
            'stream': True,   # 流式下载，避免一次加载到内存
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
        
        # 断点续传：检查是否有 .partial 文件
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
        
        # 主下载逻辑
        try:
            self.log_verbose(f"Sending GET request to {url}")
            response = requests.get(url, **request_kwargs)
            response.raise_for_status()
            
            self.log_verbose(f"Response status: {response.status_code}")
            self.log_verbose(f"Content-Type: {response.headers.get('content-type', 'unknown')}")
            content_length = response.headers.get('content-length')
            if content_length:
                self.log_verbose(f"Content-Length: {content_length} bytes")
            
            # 断点续传：判断服务器是否支持
            is_resume = False
            if should_resume and headers:
                if response.status_code == 206:  # Partial Content
                    is_resume = True
                    self.log_verbose(f"Server supports resume, continuing from {resume_pos}")
                elif response.status_code == 200:
                    self.log_verbose("Server does not support resume, starting from beginning")
                    resume_pos = 0
                    if temp_path.exists():
                        temp_path.unlink()
                    if 'Range' in request_kwargs.get('headers', {}):
                        del request_kwargs['headers']['Range']
                    response = requests.get(url, **request_kwargs)
                    response.raise_for_status()
                else:
                    self.log_verbose(f"Unexpected status code: {response.status_code}")
                    resume_pos = 0
            
            total_size = int(response.headers.get('content-length', 0)) + resume_pos
            if total_size == 0:
                total_size = None
                self.log_verbose("Total file size unknown (server did not send Content-Length)")
            else:
                self.log_verbose(f"Total file size: {total_size} bytes")
            
            # ---------- 进度条（rich） ----------
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
                
                with Progress(*progress_columns, console=console, transient=False) as progress:
                    task_id = progress.add_task(
                        description=package_name,
                        total=total_size if total_size else None,
                        start=False
                    )
                    if total_size:
                        progress.update(task_id, description=f"{package_name}", total=total_size)
                    else:
                        progress.update(task_id, description=f"{package_name} (unknown size)", total=None)
                    
                    progress.start_task(task_id)
                    
                    mode = 'ab' if is_resume else 'wb'
                    downloaded = resume_pos
                    
                    with open(temp_path, mode) as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                chunk_size_bytes = len(chunk)
                                downloaded += chunk_size_bytes
                                progress.update(task_id, advance=chunk_size_bytes)
            else:
                # 降级方案：无 rich 时使用简单点状进度
                self.log_verbose("rich library not available, using simple progress indicator")
                mode = 'ab' if is_resume else 'wb'
                downloaded = resume_pos
                with open(temp_path, mode) as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if self.verbose:
                                print(".", end="", flush=True)
                if self.verbose:
                    print(" 🌊")
            
            # ---------- SHA256 验证 ----------
            if release and release.get("sha256"):
                expected_sha256 = release.get("sha256")
                self.log_verbose(f"Expected SHA256: {expected_sha256}")
                print("🌊 Verifying SHA256...")
                actual_sha256 = self._calculate_sha256(temp_path)
                self.log_verbose(f"Actual SHA256: {actual_sha256}")
                if actual_sha256 != expected_sha256:
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
                # 缺少 SHA256：询问用户是否继续
                self.log_verbose("No SHA256 value found in release metadata")
                if not self._confirm_missing_sha256():
                    temp_path.unlink()
                    sys.exit(0)
            
            # ---------- 安装完成 ----------
            temp_path.rename(final_path)
            os.chmod(final_path, 0o755)
            self.log_verbose(f"Downloaded {final_path.stat().st_size} bytes to {final_path}")
            print(f"🌊 Download complete!")
            
        except KeyboardInterrupt:
            # Ctrl+C 干净退出
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
    
    # -------------------------------------------------------------------------
    # 安装管理
    # -------------------------------------------------------------------------

    def install_package(self, package_name, args, version=None, install_dir=None):
        """完成安装：检查文件存在性、记录安装信息、提示 PATH 配置。"""
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
            
            # 检查安装目录是否在 PATH 中
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
        """将已安装的包记录到 installed.json，使用文件锁防止并发写入。"""
        if install_dir is None:
            install_dir = INSTALL_DIR
        
        try:
            INSTALLED_DB.parent.mkdir(parents=True, exist_ok=True)
            
            with open(INSTALLED_DB, 'a+') as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # 独占锁
                
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
                
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)  # 释放锁
                
        except Exception as e:
            self.log(f"Warning: Could not record installation: {e}", force=True)
    
    # -------------------------------------------------------------------------
    # 命令处理器
    # -------------------------------------------------------------------------

    def handle_install(self, args):
        """处理 install 命令。"""
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
        
        # 用户指定了版本
        if args.ver:
            release = self.find_package(repo_data, safe_name, args)
            if release:
                self.download_binary(release["binary_url"], safe_name, args, install_dir, release)
                self.install_package(safe_name, args, release.get("version"), install_dir)
            return
        
        # 用户请求 beta 版本
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
        """处理 uninstall 命令：删除二进制文件和数据库记录。"""
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
        """处理 list 命令：显示已安装的包列表。"""
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
        """处理 search 命令：在索引中搜索包。"""
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
            print(f"  - {name}: {desc}")
    
    def handle_info(self, args):
        """处理 info 命令：显示包的详细信息。"""
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
        """处理 update 命令：强制刷新包索引缓存。"""
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
        """处理 upgrade 命令：升级已安装的包到最新版本。"""
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
            
            # 版本比较（支持语义化版本）
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
                binary_path.unlink()
            del installed[safe_name]
            with open(INSTALLED_DB, 'w') as f:
                json.dump(installed, f, indent=2)
            self.download_binary(release["binary_url"], safe_name, args, release=release)
            self.install_package(safe_name, args, release.get("version"))
        except Exception as e:
            print(f"🌊 Error: Failed to upgrade package: {e}")
    
    def handle_doctor(self, args):
        """处理 doctor 命令：检查系统环境（待实现）。"""
        print(f"🌊 Command 'doctor' is not implemented yet.")
    
    # -------------------------------------------------------------------------
    # 入口
    # -------------------------------------------------------------------------

    def run(self):
        """
        程序主入口。
        解析命令行参数，处理 --skip-ssl 确认，然后分发到对应的命令处理器。
        """
        args, unknown = self.parser.parse_known_args()
        
        # 处理 --skip-ssl 被放入 unknown 的情况（argparse 的全局参数行为）
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
        
        # 处理 --skip-ssl 的交互确认
        if not self._confirm_skip_ssl(args):
            sys.exit(0)
        
        if not args.command:
            self.parser.print_help()
            return
        
        # 命令分发表
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
    """程序启动入口。"""
    cli = MacWaveCLI()
    cli.run()


if __name__ == "__main__":
    main()
