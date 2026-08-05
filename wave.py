#!/usr/bin/env python3
"""
MacWave 🌊
A lightweight package manager CLI for jailbreak developers.
Usage: wave install <package_name>
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

REPO_URL = "https://raw.githubusercontent.com/Sha0huaZhang/MacWave/main/repo/repo.json"
INSTALL_DIR = Path.home() / ".local" / "macwave" / "bin"

def parse_arguments():
    parser = argparse.ArgumentParser(
        prog="wave",
        description="MacWave 🌊 - A lightweight package manager for jailbreak developers"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    install_parser = subparsers.add_parser("install", help="Install a package")
    install_parser.add_argument("package_name", help="Name of the package to install")
    return parser.parse_args()

def fetch_repo_data():
    try:
        response = requests.get(REPO_URL, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"🌊 Error: Failed to fetch repository data: {e}")
        sys.exit(1)
    except json.JSONDecodeError:
        print("🌊 Error: Invalid JSON data received from repository")
        sys.exit(1)

def find_package(repo_data, package_name):
    if package_name not in repo_data:
        print(f"🌊 Error: Package '{package_name}' not found in repository")
        sys.exit(1)
    package = repo_data[package_name]
    releases = package.get("releases", [])
    if not releases:
        print(f"🌊 Error: No releases found for package '{package_name}'")
        sys.exit(1)
    for release in releases:
        if release.get("arch") == "any":
            return release
    print(f"🌊 Error: No 'any' architecture release found for package '{package_name}'")
    sys.exit(1)

def download_binary(url, package_name):
    print(f"🌊 Downloading {package_name}...")
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        content = b""
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                content += chunk
                print(".", end="", flush=True)
        print(" 🌊")  # Add 🌊 after download
        return content
    except requests.exceptions.RequestException as e:
        print(f"\n🌊 Error: Failed to download binary: {e}")
        sys.exit(1)

def install_package(content, package_name):
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    binary_path = INSTALL_DIR / package_name
    try:
        with open(binary_path, "wb") as f:
            f.write(content)
        os.chmod(binary_path, 0o755)
        print(f"🌊 Successfully installed {package_name} to {binary_path}")
        
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

def main():
    args = parse_arguments()
    if args.command == "install":
        repo_data = fetch_repo_data()
        release = find_package(repo_data, args.package_name)
        binary_content = download_binary(release["binary_url"], args.package_name)
        install_package(binary_content, args.package_name)

if __name__ == "__main__":
    main()
