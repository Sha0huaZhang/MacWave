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
from pathlib import Path

# Check for requests library
try:
    import requests
except ImportError:
    print("🌊 Error: 'requests' library is not installed.")
    print("🌊 Please install it using: pip3 install requests")
    sys.exit(1)

VERSION = "1.0.0"
REPO_URL = "https://raw.githubusercontent.com/Sha0huaZhang/MacWave/main/repo/repo.json"
INSTALL_DIR = Path.home() / ".local" / "macwave" / "bin"
INSTALLED_DB = Path.home() / ".local" / "macwave" / "installed.json"


class MacWaveCLI:
    def __init__(self):
        self.parser = self._create_parser()
        self.verbose = False
        
    def _create_parser(self):
        """Create the main argument parser with all commands and flags."""
        parser = argparse.ArgumentParser(
            prog="wave",
            description="MacWave 1.0.0 🌊\nA package manager for macOS/Linux jailbreak developers.",
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
        parser.add_argument('-C', '--continue', dest='resume', action='store_true',
                          help='Resume interrupted downloads (like curl -C -)')
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
    
    def log(self, message, force=False):
        """Print log messages. Only prints if verbose mode is enabled or forced."""
        if self.verbose or force:
            print(f"🌊 {message}")
    
    def log_verbose(self, message):
        """Print verbose-only messages."""
        if self.verbose:
            print(f"🌊 Verbose: {message}")
    
    def fetch_repo_data(self, args=None):
        """Fetch and parse the remote package index (repo.json)."""
        self.log_verbose("Fetching repo from URL: " + REPO_URL)
        try:
            request_kwargs = {
                'timeout': 10
            }
            
            # Handle proxy
            if args and args.proxy:
                self.log_verbose(f"Using proxy: {args.proxy}")
                request_kwargs['proxies'] = {
                    'http': args.proxy,
                    'https': args.proxy
                }
            
            # Handle SSL
            if args and args.skip_ssl:
                self.log_verbose("SSL verification disabled")
                request_kwargs['verify'] = False
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            
            response = requests.get(REPO_URL, **request_kwargs)
            response.raise_for_status()
            self.log_verbose("Successfully fetched and parsed repo.json")
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"🌊 Error: Failed to fetch repository data: {e}")
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
    
    def download_binary(self, url, package_name, args):
        """Download the binary file from the given URL with progress indicator."""
        if args.dry_run:
            print(f"🌊 [DRY RUN] Would download {package_name} from {url}")
            return b"dry-run-content"
        
        self.log_verbose(f"Downloading from: {url}")
        print(f"🌊 Downloading {package_name}...")
        
        request_kwargs = {
            'stream': True,
            'timeout': 30
        }
        
        if args.proxy:
            self.log_verbose(f"Using proxy: {args.proxy}")
            request_kwargs['proxies'] = {
                'http': args.proxy,
                'https': args.proxy
            }
        
        if args.skip_ssl:
            self.log_verbose("SSL verification disabled")
            request_kwargs['verify'] = False
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        headers = {}
        if args.resume:
            temp_file = INSTALL_DIR / f"{package_name}.partial"
            if temp_file.exists():
                self.log_verbose(f"Resuming download from byte {temp_file.stat().st_size}")
                headers['Range'] = f"bytes={temp_file.stat().st_size}-"
        
        if headers:
            request_kwargs['headers'] = headers
        
        try:
            response = requests.get(url, **request_kwargs)
            response.raise_for_status()
            
            rate_limit = None
            if args.limit_rate:
                rate_limit = self._parse_rate_limit(args.limit_rate)
                self.log_verbose(f"Rate limit set to: {args.limit_rate}")
            
            content = b""
            if args.resume and temp_file.exists():
                with open(temp_file, 'rb') as f:
                    content = f.read()
                self.log_verbose(f"Resumed with {len(content)} existing bytes")
            
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    content += chunk
                    print(".", end="", flush=True)
                    
                    if args.resume:
                        temp_file = INSTALL_DIR / f"{package_name}.partial"
                        with open(temp_file, 'ab') as f:
                            f.write(chunk)
                    
                    if rate_limit:
                        import time
                        time.sleep(len(chunk) / rate_limit)
            
            if args.resume and temp_file.exists():
                temp_file.unlink()
            
            print(" 🌊")
            self.log_verbose(f"Downloaded {len(content)} bytes")
            return content
            
        except requests.exceptions.RequestException as e:
            print(f"\n🌊 Error: Failed to download binary: {e}")
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
    
    def install_package(self, content, package_name, args):
        """Install the downloaded binary to the local MacWave directory."""
        if args.dry_run:
            print(f"🌊 [DRY RUN] Would install {package_name} to {INSTALL_DIR}")
            return
        
        INSTALL_DIR.mkdir(parents=True, exist_ok=True)
        binary_path = INSTALL_DIR / package_name
        
        try:
            with open(binary_path, "wb") as f:
                f.write(content)
            os.chmod(binary_path, 0o755)
            print(f"🌊 Successfully installed {package_name} to {binary_path}")
            
            self._record_installation(package_name, release_version=None)
            
            path_dirs = os.environ.get("PATH", "").split(":")
            if str(INSTALL_DIR) not in path_dirs:
                print(f"🌊 Tip: Add {INSTALL_DIR} to your PATH to use '{package_name}' directly:")
                print(f"🌊   export PATH=\"{INSTALL_DIR}:$PATH\"")
            else:
                print(f"🌊 Ready to ride! You can now run: {package_name}")
                
        except OSError as e:
            print(f"🌊 Error: Failed to install package: {e}")
            sys.exit(1)
    
    def _record_installation(self, package_name, release_version=None):
        """Record installed package in the local database."""
        try:
            installed = {}
            if INSTALLED_DB.exists():
                with open(INSTALLED_DB, 'r') as f:
                    installed = json.load(f)
            
            installed[package_name] = {
                "version": release_version,
                "binary_path": str(INSTALL_DIR / package_name)
            }
            
            INSTALLED_DB.parent.mkdir(parents=True, exist_ok=True)
            with open(INSTALLED_DB, 'w') as f:
                json.dump(installed, f, indent=2)
                
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
        
        # 1. If user specified a version via --ver
        if args.ver:
            release = self.find_package(repo_data, safe_name, args)
            if release:
                binary_content = self.download_binary(release["binary_url"], safe_name, args)
                self.install_package(binary_content, safe_name, args)
            return
        
        # 2. If user requested beta version
        if args.beta_version:
            beta_release = self.find_package(repo_data, safe_name, args)
            if beta_release:
                binary_content = self.download_binary(beta_release["binary_url"], safe_name, args)
                self.install_package(binary_content, safe_name, args)
                return
            else:
                print(f"🌊 No beta version found for '{safe_name}'.")
                response = input(f"🌊 Do you want to install the latest stable version instead? [Y/n] ")
                if response.lower() not in ['y', 'yes', '']:
                    print("🌊 Installation cancelled.")
                    return
        
        # 3. Regular stable release
        release = self.find_package(repo_data, safe_name, args)
        binary_content = self.download_binary(release["binary_url"], safe_name, args)
        self.install_package(binary_content, safe_name, args)
    
    def handle_uninstall(self, args):
        """Handle the uninstall command."""
        safe_name = args.package_name.lower()
        if not INSTALLED_DB.exists():
            print(f"🌊 No packages installed. Nothing to uninstall.")
            return
        try:
            with open(INSTALLED_DB, 'r') as f:
                installed = json.load(f)
            if safe_name not in installed:
                print(f"🌊 Error: Package '{safe_name}' is not installed.")
                return
            binary_path = INSTALL_DIR / safe_name
            if binary_path.exists():
                binary_path.unlink()
                print(f"🌊 Removed binary: {binary_path}")
            else:
                print(f"🌊 Warning: Binary file not found, but removing from database.")
            del installed[safe_name]
            with open(INSTALLED_DB, 'w') as f:
                json.dump(installed, f, indent=2)
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
        repo_data = self.fetch_repo_data(self.parser.parse_args([]))
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
        """Handle the update command."""
        print("🌊 Updating package index...")
        try:
            repo_data = self.fetch_repo_data(self.parser.parse_args([]))
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
            binary_content = self.download_binary(release["binary_url"], safe_name, args)
            self.install_package(binary_content, safe_name, args)
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
