#!/usr/bin/env python3

# depsinstaller.py
# 依赖安装入口：解析 depsinfo 数据、下载依赖、调用 depsinstaller.sh 安装，
# 并递归处理依赖自身的 deps。

import os
import re
import json
import subprocess
import sys
from pathlib import Path


# -------------------- 颜色定义 --------------------

RED_BOLD = '\033[1;31m'
GREEN = '\033[32m'
YELLOW = '\033[33m'
RESET = '\033[0m'


# -------------------- 配置加载 --------------------

CONFIG_FILE = Path("/opt/macwave_config/config.json")


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

DEPSINFO_BASE = "https://raw.githubusercontent.com/Sha0huaZhang/MacWave/infosource/surfboard"
TAGGER_SCRIPT = Path(__file__).resolve().parent / "tagger.sh"
TRANSFER_SCRIPT = Path(__file__).resolve().parent / "transfer.sh"


# -------------------- 依赖库检查 --------------------

try:
    import requests
except ImportError:
    print(f"{RED_BOLD}🌊 Error: 'requests' library is not installed.{RESET}")
    print(f"{RED_BOLD}🌊 Please install it using: pip3 install requests{RESET}")
    sys.exit(1)

try:
    from depsversionparser import parse_dep_ref
    from querier import dep_dir, is_installed
except ImportError as error:
    print(f"{RED_BOLD}🌊 Error: 'surfboard' module is not available ({error}).{RESET}")
    sys.exit(1)


# -------------------- 数据解析 --------------------

def parse_common_fields(text):

    # 解析 infosource 的 @common / 版本文件（同一套简易 DSL）：
    # 1. 行内第一个引号前有声明（如 deps:），该行属于该字段。
    # 2. 行内第一个引号前无声明，则向上回溯到最近的字段声明。
    # 3. 同字段多行内容合并为列表。

    fields = {}
    current_key = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        head = line.split('"', 1)[0]

        if ':' in head:
            current_key = head.split(':', 1)[0].strip()
            fields.setdefault(current_key, [])
            value_text = line[len(head):]
        else:
            if current_key is None:
                continue
            value_text = line

        for value in re.findall(r'"([^"]*)"', value_text):
            fields[current_key].append(value)

    return fields


def get_field(fields, key, default=None):

    # 取单值字段的第一个值。

    values = fields.get(key)
    if not values:
        return default
    return values[0]


def get_deps(fields):

    # 取 deps 字段（可能多行），缺失视为无依赖。

    return [value for value in fields.get("deps", []) if str(value).strip()]


# -------------------- 远程数据 --------------------

def fetch_text(url):

    # 返回 (状态码, 文本)，网络异常记状态码 0。

    try:
        response = requests.get(url, timeout=30)
        return response.status_code, response.text
    except Exception:
        return 0, ""


def dep_common_url(dep_name, arch):

    return f"{DEPSINFO_BASE}/depsinfo_{arch}/{dep_name}/_{dep_name}@common"


def dep_version_url(dep_name, dep_version, arch):

    return f"{DEPSINFO_BASE}/depsinfo_{arch}/{dep_name}/_{dep_name}@{dep_version}"


# -------------------- 错误输出 --------------------

def report_not_found(dep_ref):

    print(f"{RED_BOLD}🌊 Error: Dependency '{dep_ref}' not found in depsinfo.{RESET}")
    print(f"{RED_BOLD}🌊 Please contact the administrator.{RESET}")
    sys.exit(1)


def report_service_unavailable():

    print(f"{RED_BOLD}🌊 Error: Service unavailable, Please contact the administrator.{RESET}")
    sys.exit(1)


def check_dep_url(dep_url):

    # 与软件包一致：依赖地址同样强制 https

    if dep_url.startswith("https://"):
        return

    if dep_url.startswith("http://"):
        print(f"{RED_BOLD}🌊 ParsePkgURL using HTTP! That's insecure, Please contact the administrator.{RESET}")
    else:
        print(f"{RED_BOLD}🌊 ParsePkgURL Invalid, Please contact the administrator.{RESET}")
    sys.exit(1)


# -------------------- 标记与下载 --------------------

def add_depender_tag(dep_path, depender):

    # 已安装的依赖被新对象依赖时，补一个标记文件。

    depender_kind, depender_name, depender_version = depender
    if not depender_kind or not depender_name or not depender_version:
        return

    action = "create-pkg" if depender_kind == "pkg" else "create-dep"
    result = subprocess.run(
        ['bash', str(TAGGER_SCRIPT), action, str(dep_path), depender_name, depender_version],
        capture_output=True, text=True
    )

    if result.returncode != 0:
        if result.stdout.strip():
            print(result.stdout.strip())
        if result.stderr.strip():
            print(result.stderr.strip())
        sys.exit(result.returncode)


def download_dependency(dep_url, dep_display_name, config, input_string):

    # 复用软件包的下载函数，进度条格式保持一致。

    from pkginstaller import download_file

    DOWNLOAD_TMP.mkdir(parents=True, exist_ok=True)
    original_filename = dep_url.split("/")[-1]
    temp_path = DOWNLOAD_TMP / f"{original_filename}.partial"

    download_file(dep_url, temp_path, config, input_string, dep_display_name)

    final_path = DOWNLOAD_TMP / original_filename
    temp_path.rename(final_path)

    return original_filename


def transfer_paths(target_dir):

    # 路径替换（Homebrew 式）：交给 surfboard/transfer.sh，
    # 把产物里 Mach-O 的动态库引用与 install name 改成 BASE_DIR 下的实际位置。

    result = subprocess.run(
        ['bash', str(TRANSFER_SCRIPT), str(target_dir), str(BASE_DIR)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )

    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0:
        sys.exit(result.returncode)


def install_dependency_shell(dep_name, dep_version, dep_sha256, dep_display_name,
                             target_dir, dep_refs, depender, original_filename):

    # 依赖与软件包共用同一套安装逻辑，只是目标目录与脚本不同。

    depender_line = ""
    if depender and depender[0] and depender[1] and depender[2]:
        depender_line = f"{depender[0]}:{depender[1]}@{depender[2]}"

    info_string = "\n".join([
        dep_name,
        dep_version,
        dep_sha256 or "",
        str(target_dir),
        str(BASE_DIR),
        dep_display_name,
        depender_line,
        original_filename,
    ])
    deps_string = "\n".join(dep_refs)

    script_path = os.path.join(os.path.dirname(__file__), 'depsinstaller.sh')
    result = subprocess.run(
        ['bash', script_path, info_string, deps_string],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )

    if result.stdout.strip():
        print(result.stdout.strip())
    if result.returncode != 0:
        sys.exit(result.returncode)


# -------------------- 依赖安装 --------------------

def ensure_dependency(dep_ref, arch, config, input_string, depender):

    # 安装单个依赖（已安装则直接补标记），并递归处理它自己的依赖。

    dep_name, dep_version = parse_dep_ref(dep_ref)
    target_dir = dep_dir(dep_name, dep_version)

    # 1. 已安装：跳过下载，只补上“谁依赖了我”的标记
    if is_installed(dep_name, dep_version):
        print(f"🌊 Dependency {dep_name}@{dep_version} is already installed, skipping.")
        add_depender_tag(target_dir, depender)
        return

    # 2. 拉取 @common，拿依赖的真实名字（dep_name）
    status, common_text = fetch_text(dep_common_url(dep_name, arch))
    if status == 404:
        report_not_found(dep_ref)
    elif status != 200:
        report_service_unavailable()

    fields = parse_common_fields(common_text)
    dep_display_name = get_field(fields, "dep_name", dep_name)

    # 3. 拉取版本文件，拿下载地址、校验值，以及它自己的 deps
    status, version_text = fetch_text(dep_version_url(dep_name, dep_version, arch))
    if status == 404:
        report_not_found(dep_ref)
    elif status != 200:
        report_service_unavailable()

    version_fields = parse_common_fields(version_text)
    dep_url = get_field(version_fields, "url")
    dep_sha256 = get_field(version_fields, "sha256")
    dep_refs = get_deps(version_fields)

    if not dep_url:
        print(f"{RED_BOLD}🌊 Error: URL field not found.{RESET}")
        sys.exit(1)

    check_dep_url(dep_url)

    # 4. 先递归安装它自己的依赖：路径替换时这些库必须已经在磁盘上
    if dep_refs:
        install_dependencies(dep_refs, arch, config, input_string,
                             ("dep", dep_name, dep_version))

    # 5. 下载 + 安装自己（安装脚本会写入 _DEPS 与依赖者标记）
    original_filename = download_dependency(dep_url, dep_display_name, config, input_string)
    install_dependency_shell(dep_name, dep_version, dep_sha256, dep_display_name,
                             target_dir, dep_refs, depender, original_filename)

    # 6. 路径替换：把自己的动态库引用指向刚装好的依赖
    transfer_paths(target_dir)


def install_dependencies(dep_refs, arch, config, input_string, depender):

    # 依次安装 deps 列表里的所有依赖。

    for dep_ref in dep_refs:
        if not str(dep_ref).strip():
            continue
        ensure_dependency(dep_ref, arch, config, input_string, depender)
