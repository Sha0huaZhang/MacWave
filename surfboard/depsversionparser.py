#!/usr/bin/env python3
"""
MacWave depsversionparser.py
负责所有依赖版本号的解析、比较和排序逻辑。
支持 alpha/beta/rc 预发布版本，遇到无数字后缀自动补 0。
特殊版本（procursus, macwaveteam）由 specialversionparser.py 处理。
"""

import re
import logging
import sys
from pathlib import Path

# 确保能找到 pkg/ 目录下的 specialversionparser.py
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pkg"))

from packaging.version import parse as parse_version, InvalidVersion
from specialversionparser import is_special_version, safe_parse_special_version


def handle_pre_release(v: str) -> str:
    """处理 alpha/beta/rc 后缀，无数字时按 0 处理"""
    v = str(v)
    v = re.sub(r'-(alpha|beta|rc)$', r'-\1 0', v)
    v = v.replace(' 0', '0')
    return v


def safe_parse_deps_version(v):
    v = str(v)
    if is_special_version(v):
        return safe_parse_special_version(v)

    v = handle_pre_release(v)
    try:
        return parse_version(v)
    except InvalidVersion:
        pass

    base_match = re.search(r'(\d+\.\d+\.\d+|\d+\.\d+)', v)
    if base_match:
        base_version = base_match.group(1)
        if base_version.count('.') == 1:
            base_version += '.0'
        try:
            return parse_version(base_version)
        except InvalidVersion:
            pass

    logging.warning(f"Invalid dependency version string '{v}', falling back to 0.0.0")
    return parse_version("0.0.0")


def sort_deps_versions(versions, reverse=True):
    return sorted(versions, key=lambda v: safe_parse_deps_version(v), reverse=reverse)


def get_max_deps_version(versions):
    if not versions:
        return None
    sorted_versions = sort_deps_versions(versions)
    return sorted_versions[0]


def main():
    test_versions = ["1.0.0-rc", "1.0.0", "1.0.0-alpha", "1.0.0-beta", "2.0.0", "0.9.0"]
    print("原始依赖版本列表:", test_versions)
    sorted_versions = sort_deps_versions(test_versions)
    print("排序后的依赖版本:", sorted_versions)
    print("最高依赖版本:", get_max_deps_version(test_versions))


if __name__ == "__main__":
    main()
