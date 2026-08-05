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
        
        # Create subparsers for commands
        subparsers = parser.add_subparsers(dest="command", help="Commands")
        
        # install command
        install_parser = subparsers.add_parser(
            "install", 
            help="Install a package (binary preferred)",
            usage="wave install <package_name> [flags]"
        )
        install_parser.add_argument("package_name", help="Name of the package to install")
        self._add_global_flags(install_parser)
        
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
            usage="wave search <query>"
        )
        search_parser.add_argument("query", help="Search query")
        
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
    
    def _add_global_flags(self, parser):
        """Add global flags to a command parser."""
        parser.add_argument('-D', '--dir', type=str, metavar='string',
                          help='Specify an output directory (e.g., ~/Desktop) for downloads')
        parser.add_argument('-C', '--continue', dest='resume', action='store_true',
                          help='Resume interrupted downloads (like curl -C -)')
        parser.add_argument('--proxy', type=str, metavar='string',
                          help='Specify an HTTP/HTTPS proxy (e.g., http://127.0.0.1:8080)')
        parser.add_argument('--skipssl', action='store_true',
                          help='Skip SSL certificate verification (insecure)')
        parser.add_argument('--limit-rate', type=str, metavar='string',
                          help='Limit download speed (e.g., 200K, 1M, 5M)')
        parser.add_argument('--dry-run', action='store_true',
                          help='Simulate the installation without making changes')
        parser.add_argument('--json', action='store_true',
                          help='Output in JSON format (for scripting)')
    
    def log(self, message, force=False):
        """Print log messages. Only prints if verbose mode is enabled or forced."""
        if self.verbose or force:
            print(f"🌊 {message}")
    
    def log_verbose(self, message):
        """Print verbose-only messages."""
        if self.verbose:
            print(f"🌊 Verbose: {message}")
    
    def fetch_repo_data(self):
        """Fetch and parse the remote package index (repo.json)."""
        self.log_verbose("Fetching repo from URL: " + REPO_URL)
        try:
            response = requests.get(REPO_URL, timeout=10)
            response.raise_for_status()
            self.log_verbose("Successfully fetched and parsed repo.json")
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"🌊 Error: Failed to fetch repository data: {e}")
            sys.exit(1)
        except json.JSONDecodeError:
            print("🌊 Error: Invalid JSON data received from repository")
            sys.exit(1)
    
    def find_package(self, repo_data, package_name):
        """Find a package in the repository data by its name."""
        self.log_verbose(f"Searching for package: {package_name}")
        
        # Support current array format: {"packages": [...]}
        if "packages" in repo_data:
            for pkg in repo_data["packages"]:
                if pkg.get("name") == package_name:
                    self.log_verbose(f"Found package: {pkg.get('name')}")
                    releases = pkg.get("releases", [])
                    for release in releases:
                        if release.get("arch") == "any":
                            self.log_verbose(f"Found release with arch='any'")
                            return release
                    print(f"🌊 Error: No 'any' architecture release found for package '{package_name}'")
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
        
        # Prepare request parameters
        request_kwargs = {
            'stream': True,
            'timeout': 30
        }
        
        # Handle proxy
        if args.proxy:
            self.log_verbose(f"Using proxy: {args.proxy}")
            request_kwargs['proxies'] = {
                'http': args.proxy,
                'https': args.proxy
            }
        
        # Handle SSL verification
        if args.skipssl:
            self.log_verbose("SSL verification disabled")
            request_kwargs['verify'] = False
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # Handle resume
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
            
            # Handle rate limiting
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
                    
                    # Save progress for resume
                    if args.resume:
                        temp_file = INSTALL_DIR / f"{package_name}.partial"
                        with open(temp_file, 'ab') as f:
                            f.write(chunk)
                    
                    # Simple rate limiting
                    if rate_limit:
                        import time
                        time.sleep(len(chunk) / rate_limit)
            
            # Clean up partial file
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
        
        # Binary installation
        INSTALL_DIR.mkdir(parents=True, exist_ok=True)
        binary_path = INSTALL_DIR / package_name
        
        try:
            with open(binary_path, "wb") as f:
                f.write(content)
            os.chmod(binary_path, 0o755)
            print(f"🌊 Successfully installed {package_name} to {binary_path}")
            
            # Record installation
            self._record_installation(package_name)
            
            # Check PATH
            path_dirs = os.environ.get("PATH", "").split(":")
            if str(INSTALL_DIR) not in path_dirs:
                print(f"🌊 Tip: Add {INSTALL_DIR} to your PATH to use '{package_name}' directly:")
                print(f"🌊   export PATH=\"{INSTALL_DIR}:$PATH\"")
            else:
                print(f"🌊 Ready to ride! You can now run: {package_name}")
                
        except OSError as e:
            print(f"🌊 Error: Failed to install package: {e}")
            sys.exit(1)
    
    def _record_installation(self, package_name):
        """Record installed package in the local database."""
        try:
            installed = {}
            if INSTALLED_DB.exists():
                with open(INSTALLED_DB, 'r') as f:
                    installed = json.load(f)
            
            installed[package_name] = {
                "installed_at": str(Path.home()),
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
        repo_data = self.fetch_repo_data()
        
        # Convert package name to lowercase for case-insensitive matching
        safe_name = args.package_name.lower()
        
        release = self.find_package(repo_data, safe_name)
        binary_content = self.download_binary(release["binary_url"], safe_name, args)
        self.install_package(binary_content, safe_name, args)
    
    def handle_uninstall(self, args):
        """Handle the uninstall command."""
        print(f"🌊 Command 'uninstall' is not implemented yet.")
    
    def handle_list(self, args):
        """Handle the list command."""
        print(f"🌊 Command 'list' is not implemented yet.")
    
    def handle_search(self, args):
        """Handle the search command."""
        print(f"🌊 Command 'search' is not implemented yet.")
    
    def handle_info(self, args):
        """Handle the info command."""
        print(f"🌊 Command 'info' is not implemented yet.")
    
    def handle_update(self, args):
        """Handle the update command."""
        print(f"🌊 Command 'update' is not implemented yet.")
    
    def handle_upgrade(self, args):
        """Handle the upgrade command."""
        print(f"🌊 Command 'upgrade' is not implemented yet.")
    
    def handle_doctor(self, args):
        """Handle the doctor command."""
        print(f"🌊 Command 'doctor' is not implemented yet.")
    
    def run(self):
        """Main entry point of the CLI."""
        args = self.parser.parse_args()
        
        # Set verbose mode
        self.verbose = args.verbose if hasattr(args, 'verbose') else False
        
        # Handle commands
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
