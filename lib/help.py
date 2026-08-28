#!/usr/bin/env python3
"""
MacWave Help Module
负责展示命令行帮助信息。
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

# 版本文件绝对路径
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
    """展示主程序的帮助信息"""
    version = get_project_version()
    print(f"{PURPLE}usage: {ORANGE}wave <command> [package] [flags]{RESET}")
    print()
    print(f"MacWave {version} 🌊")
    print("A package manager for macOS/Linux jailbreak developers.")
    print()
    print(f"{PURPLE}positional arguments:{RESET}")
    print(f"  {GREEN}{{install, uninstall, list, search, info, update, upgrade, doctor, clean}}{RESET}")
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


def main():
    """直接运行 python help.py 时，预览帮助信息"""
    print_custom_help()


if __name__ == "__main__":
    main()
