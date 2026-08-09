#!/usr/bin/env python3
"""
MacWave 🌊
A package manager for macOS/Linux jailbreak developers.
Version: 1.0.1
"""

import argparse
import json
import os
import sys
import platform
import time
import fcntl
from pathlib import Path

# Check for requests library
try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    print("🌊 Error: 'requests' library is not installed.")
    print("🌊 Please install it using: pip3 install requests")
    sys.exit(1)

# Check for packaging library (used for safe version comparison)
try:
    from packaging.version import parse as parse_version
except ImportError:
    print("🌊 Error: 'packaging' library is not installed.")
    print("🌊 Please install it using: pip3 install packaging")
    sys.exit(1)

VERSION = "1.0.1"
REPO_URL = "https://raw.githubusercontent.com/Sha0huaZhang/MacWave/main/repo/repo.json"
INSTALL_DIR = Path.home() / ".local" / "macwave" / "bin"
INSTALLED_DB = Path.home() / ".local" / "macwave" / "installed.json"
REPO_CACHE = Path.home() / ".local" / "macwave" / "repo_cache.json"


class MacWaveCLI:
    def __init__(self):
        self.parser = self._create_parser()
        self.verbose = False
        
    def _create_parser(self):
        """Create the main argument parser with all commands and flags."""
        parser = argparse.ArgumentParser(
            prog="wave",
            description="MacWave 1.0.1 🌊\nA package manager for macOS/Linux jailbreak developers.",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            usage="wave <command> [package] [flags]",
            epilog="For more details, visit: https://macwave.org"
        )
        
        # Global flags
        parser.add_argument('-V', '--version', action='version', 
                          version=f'MacWave {VERSION} 🌊')
        parser.add_argument('-v', '--verbose', action='store_true',
                          help='Enable verbose output (show detailed logs)')
        parser.add_argument('-B', '--beta-version', action='store_true',
                          help='Install the latest beta version (if available)')
        # -C 已移到 install 子命令中
        parser.add_argument('--proxy', type=str, metavar='string',
                          help='Specify an HTTP/HTTPS proxy (e.g., http://127.0.0.1:8080)')
        parser.add_argument('--skip-ssl', action='store_true',
                          help='Skip SSL certificate verification (insecure)')
        parser.add_argument('--limit-rate', type=str, metavar='string',
                          help='Limit download speed (e.g., 200K, 1M, 5M)')
        parser.add_argument('--dry-run', action='store_true',
                          help='Simulate the installation without making changes')
        parser.add_argument('--json', action='store_true',
                          help='Output in JSON format (for scripting)')
        
        # Create subparsers for commands
        subparsers = parser.add_subparsers(dest="command", help="Commands")
        
        # install command
        install_parser = subparsers.add_parser(
            "install", 
            help="Install a package",
            usage="wave install <package_name> [flags]"
        )
        install_parser.add_argument("package_name", help="Name of the package to install")
        self._add_install_flags(install_parser)
        
        # uninstall command
        uninstall_parser = subparsers.add_parser(
            "uninstall",
            help="Uninstall a package",
            usage="wave uninstall <package_name>"
        )
        uninstall_parser.add_argument("package_name", help="Name of the package to uninstall")
        
        # list command
        subparsers.add_parser("list", help="List installed packages")
        
        # search command
        search_parser = subparsers.add_parser(
            "search",
            help="Search for a package in the index",
            usage="wave search <query> [flags]"
        )
        search_parser.add_argument("query", help="Search query")
        search_parser.add_argument('-f', '--fuzzy', action='store_true',
                                  help='Enable fuzzy search (matches anywhere in name/description)')
        
        # info command
        info_parser = subparsers.add_parser(
            "info",
            help="Display detailed information about a package",
            usage="wave info <package_name>"
        )
        info_parser.add_argument("package_name", help="Name of the package")
        
        # update command
        subparsers.add_parser("update", help="Update the package index")
        
        # upgrade command
        upgrade_parser = subparsers.add_parser(
            "upgrade",
            help="Upgrade an installed package to the latest version",
            usage="wave upgrade <package_name>"
        )
        upgrade_parser.add_argument("package_name", help="Name of the package to upgrade")
        
        # doctor command
        subparsers.add_parser("doctor", help="Check your system for missing dependencies")
        
        return parser
    
    def _add_install_flags(self, parser):
        """Add flags specific to the install command."""
        parser.add_argument('-D', '--dir', type=str, metavar='string',
                          help='Specify an output directory (e.g., ~/Desktop) for downloads')
        parser.add_argument('--ver', type=str, metavar='string',
                          help='Install a specific version of the package (e.g., --ver 1.0.0)')
        # 修复：-C 参数现在属于 install 子命令
        parser.add_argument('-C', '--continue', dest='resume', action='store_true',
                          help='Resume interrupted downloads (use with install command)')
    
    def log(self, message, force=False):
        """Print log messages. Only prints if verbose mode is enabled or forced."""
        if self.verbose or force:
            print(f"🌊 {message}")
    
    def log_verbose(self, message):
        """Print verbose-only messages."""
        if self.verbose:
            print(f"🌊 Verbose: {message}")
    
    def fetch_repo_data(self, args=None):
        """Fetch and parse the remote package index (repo.json) with local caching."""
        # Ensure cache directory exists
        REPO_CACHE.parent.mkdir(parents=True, exist_ok=True)
        
        # Check if cache is valid (5 minutes)
        cache_valid = False
        if REPO_CACHE.exists():
            mtime = REPO_CACHE.stat().st_mtime
            if (time.time() - mtime) < 300:
                cache_valid = True
        
        # If cache is valid, use it
        if cache_valid:
            self.log_verbose("Using cached repo.json")
            try:
                with open(REPO_CACHE, 'r') as f:
                    return json.load(f)
            except Exception:
                self.log_verbose("Cache corrupted, falling back to network")
                pass
        
        self.log_verbose("Fetching fresh repo.json from network")
        session = requests.Session()
        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET"]
        )
        session.mount('https://', HTTPAdapter(max_retries=retries))
        
        try:
            request_kwargs = {
                'timeout': 10
            }
            
            if args and args.proxy:
                self.log_verbose(f"Using proxy: {args.proxy}")
                request_kwargs['proxies'] = {
                    'http': args.proxy,
                    'https': args.proxy
                }
            
            if args and args.skip_ssl:
                self.log_verbose("SSL verification disabled")
                request_kwargs['verify'] = False
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            response = session.get(REPO_URL, **request_kwargs)
            response.raise_for_status()
            data = response.json()
            
            # Write to cache
            with open(REPO_CACHE, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.log_verbose("Fetched and cached fresh repo.json")
            return data
            
        except requests.exceptions.RequestException as e:
            print(f"🌊 Error: Failed to fetch repository data after 3 retries: {e}")
            sys.exit(1)
        except json.JSONDecodeError:
            print("🌊 Error: Invalid JSON data received from repository")
            sys.exit(1)
    
    def find_package(self, repo_data, package_name, args=None):
        """Find a package. Respects --ver and -B flags."""
        self.log_verbose(f"Searching for package: {package_name}")
        
        if "packages" in repo_data:
            for pkg in repo_data["packages"]:
                if pkg.get("name") == package_name:
                    self.log_verbose(f"Found package: {pkg.get('name')}")
                    releases = pkg.get("releases", [])
                    
                    # 1. If user specified a version via --ver
                    if args and args.ver:
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
                    
                    # 2. If user requested beta version
                    if args and args.beta_version:
                        self.log_verbose("User requested beta version.")
                        for release in releases:
                            if release.get("arch") == "beta":
                                self.log_verbose("Found beta release.")
                                return release
                        return None
                    
                    # 3. Regular stable release (match architecture)
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
    
    def download_binary(self, url, package_name, args, install_dir=None):
        """Download binary to disk directly with streaming. Handles Ctrl+C gracefully."""
        if install_dir is None:
            install_dir = INSTALL_DIR
        
        if args.dry_run:
            print(f"🌊 [DRY RUN] Would download {package_name} from {url}")
            return
        
        self.log_verbose(f"Downloading from: {url}")
        print(f"🌊 Downloading {package_name}...")
        
        # Target and temporary paths
        final_path = install_dir / package_name
        temp_path = install_dir / f"{package_name}.partial"
        
        # Ensure directory exists
        install_dir.mkdir(parents=True, exist_ok=True)
        
        # Prepare request parameters
        request_kwargs = {
            'stream': True,
            'timeout': 30
        }
        
        if args.proxy:
            request_kwargs['proxies'] = {'http': args.proxy, 'https': args.proxy}
        
        if args.skip_ssl:
            request_kwargs['verify'] = False
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Handle resume - 修复：安全检查
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
                    # 文件存在但大小为0，从头开始
                    self.log_verbose("Partial file exists but is empty, starting from beginning")
                    temp_path.unlink()  # 删除空文件
                    should_resume = False
            except (FileNotFoundError, OSError) as e:
                self.log_verbose(f"Cannot read partial file: {e}, starting from beginning")
                should_resume = False
        
        if headers:
            request_kwargs['headers'] = headers
        
        try:
            response = requests.get(url, **request_kwargs)
            response.raise_for_status()
            
            # 修复：检查正确的状态码
            is_resume = False
            if should_resume and headers:
                if response.status_code == 206:  # Partial Content
                    is_resume = True
                    self.log_verbose(f"Server supports resume, continuing from {resume_pos}")
                elif response.status_code == 200:
                    # 服务器不支持续传，从头开始
                    self.log_verbose("Server does not support resume, starting from beginning")
                    resume_pos = 0
                    # 覆盖临时文件
                    if temp_path.exists():
                        temp_path.unlink()
                    # 移除Range头，重新请求
                    if 'Range' in request_kwargs.get('headers', {}):
                        del request_kwargs['headers']['Range']
                    response = requests.get(url, **request_kwargs)
                    response.raise_for_status()
                else:
                    self.log_verbose(f"Unexpected status code: {response.status_code}")
                    resume_pos = 0
            
            # Write to disk directly
            mode = 'ab' if is_resume else 'wb'
            downloaded = 0
            
            with open(temp_path, mode) as f:
                try:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if self.verbose:
                                print(".", end="", flush=True)
                except KeyboardInterrupt:
                    print("\n🌊 Download interrupted.")
                    if temp_path.exists() and temp_path.stat().st_size > 0:
                        print(f"🌊 Partial file saved at: {temp_path}")
                        print(f"🌊 Use 'wave install {package_name} -C' to resume later")
                    else:
                        if temp_path.exists():
                            temp_path.unlink()
                    return
            
            # Rename to final file
            temp_path.rename(final_path)
            os.chmod(final_path, 0o755)
            if self.verbose:
                print(" 🌊")
            self.log_verbose(f"Downloaded {final_path.stat().st_size} bytes")
            print(f"🌊 Download complete!")
            
        except requests.exceptions.RequestException as e:
            print(f"\n🌊 Error: Failed to download binary: {e}")
            # 保留临时文件以便续传
            if temp_path.exists() and temp_path.stat().st_size > 0:
                print(f"🌊 Partial file saved at: {temp_path}")
            sys.exit(1)
    
    def _parse_rate_limit(self, rate_str):
        """Parse rate limit string to bytes per second."""
        rate_str = rate_str.upper()
        multipliers = {'K': 1024, 'M': 1024**2, 'G': 1024**3}
        try:
            if rate_str[-1] in multipliers:
                return float(rate_str[:-1]) * multipliers[rate_str[-1]]
            return float(rate_str)
        except ValueError:
            self.log("Invalid rate limit format, ignoring", force=True)
            return None
    
    def install_package(self, package_name, args, version=None, install_dir=None):
        """Finalize installation (check PATH and record)."""
        if install_dir is None:
            install_dir = INSTALL_DIR
        
        if args.dry_run:
            print(f"🌊 [DRY RUN] Would install {package_name} to {install_dir}")
            return
        
        binary_path = install_dir / package_name
        if not binary_path.exists():
            print(f"🌊 Error: Binary file not found after download.")
            sys.exit(1)
        
        try:
            print(f"🌊 Successfully installed {package_name} to {binary_path}")
            self._record_installation(package_name, version, install_dir)
            
            path_dirs = os.environ.get("PATH", "").split(":")
            if str(install_dir) not in path_dirs:
                print(f"🌊 Tip: Add {install_dir} to your PATH to use '{package_name}' directly:")
                print(f"🌊   export PATH=\"{install_dir}:$PATH\"")
            else:
                print(f"🌊 Ready to ride! You can now run: {package_name}")
                
        except OSError as e:
            print(f"🌊 Error: Failed to install package: {e}")
            sys.exit(1)
    
    def _record_installation(self, package_name, release_version=None, install_dir=None):
        """Record installed package in the local database with file lock."""
        if install_dir is None:
            install_dir = INSTALL_DIR
        
        try:
            INSTALLED_DB.parent.mkdir(parents=True, exist_ok=True)
            
            # Open file with exclusive lock
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
        """Handle the install command."""
        if args.json:
            print(json.dumps({"command": "install", "package": args.package_name}))
            return
        
        self.log_verbose(f"Install command for package: {args.package_name}")
        repo_data = self.fetch_repo_data(args)
        safe_name = args.package_name.lower()
        
        # 处理 --dir 标志
        install_dir = INSTALL_DIR
        if args.dir:
            install_dir = Path(args.dir).expanduser().resolve()
            self.log_verbose(f"Using custom install directory: {install_dir}")
        
        # 1. If user specified a version via --ver
        if args.ver:
            release = self.find_package(repo_data, safe_name, args)
            if release:
                self.download_binary(release["binary_url"], safe_name, args, install_dir)
                self.install_package(safe_name, args, release.get("version"), install_dir)
            return
        
        # 2. If user requested beta version
        if args.beta_version:
            beta_release = self.find_package(repo_data, safe_name, args)
            if beta_release:
                self.download_binary(beta_release["binary_url"], safe_name, args, install_dir)
                self.install_package(safe_name, args, beta_release.get("version"), install_dir)
                return
            else:
                print(f"🌊 No beta version found for '{safe_name}'.")
                response = input(f"🌊 Do you want to install the latest stable version instead? [Y/n] ")
                if response.lower() not in ['y', 'yes', '']:
                    print("🌊 Installation cancelled.")
                    return
        
        # 3. Regular stable release
        release = self.find_package(repo_data, safe_name, args)
        self.download_binary(release["binary_url"], safe_name, args, install_dir)
        self.install_package(safe_name, args, release.get("version"), install_dir)
    
    def handle_uninstall(self, args):
        """Handle the uninstall command."""
        safe_name = args.package_name.lower()
        if not INSTALLED_DB.exists():
            print(f"🌊 No packages installed. Nothing to uninstall.")
            return
        try:
            # Read with shared lock
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
            
            # Write with exclusive lock
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
        """Handle the list command."""
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
        """Handle the search command."""
        query = args.query.lower()
        # 修复：传递实际的 args 而不是空列表
        repo_data = self.fetch_repo_data(args)
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
        """Handle the info command."""
        self.log_verbose(f"Info command for package: {args.package_name}")
        repo_data = self.fetch_repo_data(args)
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
        """Handle the update command (force refresh the cache)."""
        print("🌊 Forcing update: fetching fresh package index...")
        try:
            if REPO_CACHE.exists():
                REPO_CACHE.unlink()
            # 修复：传递实际的 args
            repo_data = self.fetch_repo_data(args)
            print(f"🌊 Package index updated successfully. Found {len(repo_data.get('packages', []))} packages.")
        except Exception as e:
            print(f"🌊 Error: Failed to update package index: {e}")
    
    def handle_upgrade(self, args):
        """Handle the upgrade command."""
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
            repo_data = self.fetch_repo_data(args)
            release = self.find_package(repo_data, safe_name)
            remote_version = release.get("version", "unknown")
            
            # Safe semantic version comparison
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
            self.download_binary(release["binary_url"], safe_name, args)
            self.install_package(safe_name, args, release.get("version"))
        except Exception as e:
            print(f"🌊 Error: Failed to upgrade package: {e}")
    
    def handle_doctor(self, args):
        """Handle the doctor command."""
        print(f"🌊 Command 'doctor' is not implemented yet.")
    
    def run(self):
        """Main entry point of the CLI."""
        args = self.parser.parse_args()
        self.verbose = args.verbose if hasattr(args, 'verbose') else False
        if not args.command:
            self.parser.print_help()
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
        }
        handler = command_handlers.get(args.command)
        if handler:
            handler(args)
        else:
            print(f"🌊 Error: Unknown command '{args.command}'")
            sys.exit(1)


def main():
    """Main entry point of the script."""
    cli = MacWaveCLI()
    cli.run()


if __name__ == "__main__":
    main()
