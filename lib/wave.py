#!/usr/bin/env python3

# wave.py

import sys
from pathlib import Path


# -------------------- 配置与模块路径 --------------------

CONFIG_FILE = Path("/opt/macwave_config/config.json")
VERSION_FILE = Path("/opt/macwave_config/VERSION.json")


def load_config():
    import json
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                base_dir = config.get("base_dir")
                if base_dir:
                    return Path(base_dir)
        except Exception:
            pass
    print("🌊 Error: Configuration file not found or invalid.")
    sys.exit(1)


BASE_DIR = load_config()
LIB_DIR = BASE_DIR / "lib"
PKG_DIR = BASE_DIR / "pkg"
SURFBOARD_DIR = BASE_DIR / "surfboard"

sys.path.insert(0, str(LIB_DIR))
sys.path.insert(0, str(PKG_DIR))
sys.path.insert(0, str(SURFBOARD_DIR))


# -------------------- 字典定义 --------------------

COMMANDS = {
    "install":   "pkginstaller",
    "uninstall": "uninstaller",
    "list":      "pkginfohelper",
    "search":    "pkginfohelper",
    "info":      "pkginfohelper",
    "version":   "help",
}

ARGUMENTS = {
    "-h":        "help",
    "--help":    "help",
    "-V":        "help",
    "--version": "help",
}


# -------------------- 主调度逻辑 --------------------

def main():
    words = sys.argv[1:]

    # 1. 无任何输入
    if not words:
        from help import print_custom_help
        print_custom_help()
        sys.exit(0)

    FirstWord = words[0]

    # 2. 参数优先
    if FirstWord in ARGUMENTS:
        if FirstWord in ("-h", "--help"):
            from help import print_custom_help
            print_custom_help()
        elif FirstWord in ("-V", "--version"):
            from help import print_version
            print_version()
        sys.exit(0)

    # 3. 命令分发
    if FirstWord in COMMANDS:
        module_name = COMMANDS[FirstWord]
        full_input = " ".join(words)

        if module_name == "pkginstaller":
            from pkginstaller import handle_install
            handle_install(full_input)

        elif module_name == "uninstaller":
            from uninstaller import handle_uninstall
            handle_uninstall(full_input)

        elif module_name == "pkginfohelper":
            from pkginfohelper import handle_info_command
            handle_info_command(full_input)

        elif module_name == "help":
            from help import print_version
            print_version()

        # 预留：query
        
        sys.exit(0)

    # 4. 未知输入
    from help import print_error_help
    print_error_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
