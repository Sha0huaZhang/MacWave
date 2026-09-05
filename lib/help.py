#!/usr/bin/env python3
"""
MacWave Help Module
负责展示命令行帮助信息（简版和详细版）。
"""

import json
from pathlib import Path

# 颜色定义
RED = '\033[31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
CYAN = '\033[36m'
RESET = '\033[0m'
BOLD = '\033[1m'
PURPLE = '\033[35m'
ORANGE = '\033[38;5;197m'

VERSION_FILE = Path("/opt/macwave_config/VERSION.json")

def get_project_version():
    """从 VERSION.json 获取主程序版本号"""
    if VERSION_FILE.exists():
        try:
            with open(VERSION_FILE, 'r') as f:
                data = json.load(f)
                return data.get("version", "unknown")
        except Exception:
            pass
    return "unknown"


def print_custom_help():
    """简版帮助"""
    version = get_project_version()
    print(f"{PURPLE}usage: {ORANGE}wave <command> [package] [flags]{RESET}")
    print()
    print(f"MacWave {version} 🌊")
    print("A package manager for macOS jailbreak developers.")
    print()
    print(f"{PURPLE}positional arguments:{RESET}")
    print(f"  {GREEN}{{install, uninstall, list, search, info, update, upgrade, doctor, clean, listdeps, depsinstall, depsquery, pkgquery, allquery, depsuninstall, changedeppath, delpathrecord}}{RESET}")
    print("                          Commands")
    print(f"    {GREEN}install{RESET}               Install a package")
    print(f"    {GREEN}uninstall{RESET}             Uninstall a package")
    print(f"    {GREEN}list{RESET}                  List installed packages")
    print(f"    {GREEN}search{RESET}                Search for a package in the index")
    print(f"    {GREEN}info{RESET}                  Display detailed information about a package")
    print(f"    {GREEN}update{RESET}                Update the package index")
    print(f"    {GREEN}upgrade{RESET}               Upgrade an installed package to the latest version")
    print(f"    {GREEN}doctor{RESET}                Check your system for missing dependencies")
    print(f"    {GREEN}clean{RESET}                 Clean up temporary download files")
    print(f"    {GREEN}listdeps{RESET}              List dependencies")
    print(f"    {GREEN}depsinstall{RESET}           Install dependencies")
    print(f"    {GREEN}depsquery{RESET}             Query dependencies")
    print(f"    {GREEN}pkgquery{RESET}              Query packages that depend on a target")
    print(f"    {GREEN}allquery{RESET}              Query all dependencies and packages")
    print(f"    {GREEN}depsuninstall{RESET}         Uninstall dependencies")
    print(f"    {GREEN}changedeppath{RESET}         Change dependency path")
    print(f"    {GREEN}delpathrecord{RESET}         Delete path record")
    print()
    print(f"{PURPLE}parameters:{RESET}")
    print(f"  {GREEN}-h, --help{RESET}              show this help message and exit")
    print(f"  {GREEN}-V, --version{RESET}           show program's version number and exit")
    print(f"  {GREEN}-v, --verbose{RESET}           Enable verbose output")
    print(f"  {GREEN}-B, --beta-version{RESET}      Install the latest beta version")
    print(f"  {CYAN}--proxy{RESET} {YELLOW}string{RESET}          Specify an HTTP/HTTPS proxy")
    print(f"  {CYAN}--skip-ssl{RESET}              Skip SSL certificate verification")
    print(f"  {CYAN}--limit-rate{RESET} {YELLOW}string{RESET}     Limit download speed")
    print(f"  {CYAN}--dry-run{RESET}               Simulate the installation")
    print(f"  {CYAN}--json{RESET}                  Output in JSON format")
    print()
    print("Global Flags:")
    print(f"  {GREEN}-B, --beta-version{RESET}      Install the latest beta version")
    print(f"  {GREEN}-D, --dir{RESET} {YELLOW}string{RESET}        Specify an output directory")
    print(f"  {GREEN}-C, --continue{RESET}          Resume interrupted downloads")
    print(f"  {CYAN}--proxy{RESET} {YELLOW}string{RESET}          Specify an HTTP/HTTPS proxy")
    print(f"  {CYAN}--skip-ssl{RESET}              Skip SSL certificate verification")
    print(f"  {CYAN}--limit-rate{RESET} {YELLOW}string{RESET}     Limit download speed")
    print(f"  {CYAN}--dry-run{RESET}               Simulate the installation")
    print(f"  {CYAN}--json{RESET}                  Output in JSON format")
    print(f"  {CYAN}--ver{RESET} {YELLOW}string{RESET}            Install a specific version")
    print()
    print("For more details, visit: https://macwave.org")


def print_detailed_help():
    """详细版帮助"""
    version = get_project_version()
    print(f"{PURPLE}usage: {ORANGE}wave <command> [package] [flags]{RESET}")
    print()
    print(f"MacWave {version} 🌊")
    print("A package manager for macOS jailbreak developers.")
    print()
    print("Detailed Help (All Commands):")
    print("========================================")
    print()

    print(f"{BOLD}{PURPLE}[INSTALL]{RESET}")
    print("Usage: wave install <package_name> [flags]")
    print("Description: Install a package.")
    print("Flags:")
    print(f"  {GREEN}-D{RESET}, --dir <path>       Specify an output directory.")
    print(f"  {CYAN}--ver{RESET} <version>        Install a specific version.")
    print(f"  {GREEN}-C{RESET}, --continue         Resume interrupted downloads.")
    print("Example: wave install ldid --ver 2.1.5-procursus7")
    print()

    print(f"{BOLD}{PURPLE}[UNINSTALL]{RESET}")
    print("Usage: wave uninstall <package_name> [package_name@version]")
    print("Description: Uninstall a package.")
    print("Flags: (none)")
    print("Example: wave uninstall ldid@2.1.5-procursus7")
    print()

    print(f"{BOLD}{PURPLE}[LIST]{RESET}")
    print("Usage: wave list")
    print("Description: List installed packages.")
    print("Flags: (none)")
    print("Example: wave list")
    print()

    print(f"{BOLD}{PURPLE}[SEARCH]{RESET}")
    print("Usage: wave search <query> [flags]")
    print("Flags:")
    print(f"  {GREEN}-f{RESET}, --fuzzy            Enable fuzzy search.")
    print("Example: wave search ldid -f")
    print()

    print(f"{BOLD}{PURPLE}[INFO]{RESET}")
    print("Usage: wave info <package_name>")
    print("Description: Display detailed information about a package.")
    print("Flags: (none)")
    print("Example: wave info ldid")
    print()

    print(f"{BOLD}{PURPLE}[UPDATE]{RESET}")
    print("Usage: wave update")
    print("Description: Update the package index.")
    print("Flags: (none)")
    print("Example: wave update")
    print()

    print(f"{BOLD}{PURPLE}[UPGRADE]{RESET}")
    print("Usage: wave upgrade <package_name>")
    print("Description: Upgrade an installed package to the latest version.")
    print("Flags: (none)")
    print("Example: wave upgrade ldid")
    print()

    print(f"{BOLD}{PURPLE}[DOCTOR]{RESET}")
    print("Usage: wave doctor")
    print("Description: Check your system for missing dependencies.")
    print("Flags: (none)")
    print("Example: wave doctor")
    print()

    print(f"{BOLD}{PURPLE}[CLEAN]{RESET}")
    print("Usage: wave clean")
    print("Description: Clean up temporary download files.")
    print("Flags: (none)")
    print("Example: wave clean")
    print()

    print(f"{BOLD}{PURPLE}[LISTDEPS]{RESET}")
    print("Usage: wave listdeps [flags]")
    print("Flags:")
    print(f"  {GREEN}-d{RESET}, --detailed         Show detailed dependency info.")
    print("Example: wave listdeps -d")
    print()

    print(f"{BOLD}{PURPLE}[DEPSINSTALL]{RESET}")
    print("Usage: wave depsinstall <target> [flags]")
    print("Flags:")
    print(f"  {GREEN}-m{RESET}, --missing          Install missing dependencies.")
    print(f"  {GREEN}-ma{RESET}, --missing-all     Install all missing dependencies.")
    print("Example: wave depsinstall openssl@1.0")
    print()

    print(f"{BOLD}{PURPLE}[DEPSQUERY]{RESET}")
    print("Usage: wave depsquery <target> [flags]")
    print("Flags:")
    print(f"  {GREEN}-d{RESET}, --detailed         Show detailed dependency info.")
    print("Example: wave depsquery openssl@1.0 -d")
    print()

    print(f"{BOLD}{PURPLE}[PKGQUERY]{RESET}")
    print("Usage: wave pkgquery <target>")
    print("Description: Query packages that depend on a target.")
    print("Flags: (none)")
    print("Example: wave pkgquery openssl@1.0")
    print()

    print(f"{BOLD}{PURPLE}[ALLQUERY]{RESET}")
    print("Usage: wave allquery <target>")
    print("Description: Query all dependencies and packages (bidirectional).")
    print("Flags: (none)")
    print("Example: wave allquery openssl@1.0")
    print()

    print(f"{BOLD}{PURPLE}[DEPSUNINSTALL]{RESET}")
    print("Usage: wave depsuninstall <target> [flags]")
    print("Flags:")
    print(f"  {GREEN}-u{RESET}, --unnecessary      Remove unnecessary dependencies.")
    print("Example: wave depsuninstall openssl@1.0 -u")
    print()

    print(f"{BOLD}{PURPLE}[CHANGEDEPPATH]{RESET}")
    print("Usage: wave changedeppath <package>@<version> @<dependency>@<version> <absolute_path>")
    print("Description: Change a specific dependency's path.")
    print("Flags: (none)")
    print("Example: wave changedeppath pkg1@1.0 @openssl@1.0 /opt/homebrew/opt/openssl")
    print()

    print(f"{BOLD}{PURPLE}[DELPATHRECORD]{RESET}")
    print("Usage: wave delpathrecord <target>")
    print("Flags:")
    print(f"  {GREEN}--force{RESET}                Force delete default path.")
    print("Example: wave delpathrecord pkg1@1.0 --force")
    print()

    print("For more details, visit: https://macwave.org")


def main():
    """直接运行 python3 help.py 时，预览帮助信息"""
    print_custom_help()


if __name__ == "__main__":
    main()
