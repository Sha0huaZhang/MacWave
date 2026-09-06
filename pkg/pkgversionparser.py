#!/usr/bin/env python3
"""
MacWave pkgversionparser.py
负责所有软件包（Software Package）常规版本号的解析、比较和排序逻辑。
支持 alpha/beta/rc 预发布版本，遇到无数字后缀自动补 0（例如 rc -> rc0）。
特殊版本（procursus, macwaveteam）由 specialversionparser.py 处理。
"""

import re
import logging
from packaging.version import parse as parse_version, InvalidVersion
from specialversionparser import is_special_version, safe_parse_special_version


def handle_pre_release(v: str) -> str:
    """处理 alpha/beta/rc 后缀，无数字时按 0 处理"""
    v = str(v)
    # 在字母和数字之间插入 0（例如 rc -> rc0, beta -> beta0, alpha -> alpha0）
    # 如果 rc 后面已经是数字（如 rc1），则保持原样
    v = re.sub(r'-(alpha|beta|rc)$', r'-\1 0', v)
    # 去掉可能引入的额外空格，标准格式化为 -alpha0, -beta0, -rc0
    v = v.replace(' 0', '0')
    return v


def safe_parse_pkg_version(v):
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

    logging.warning(f"Invalid package version string '{v}', falling back to 0.0.0")
    return parse_version("0.0.0")


def sort_pkg_versions(versions, reverse=True):
    return sorted(versions, key=lambda v: safe_parse_pkg_version(v), reverse=reverse)


def get_max_pkg_version(versions):
    if not versions:
        return None
    sorted_versions = sort_pkg_versions(versions)
    return sorted_versions[0]


def main():
    test_versions = ["1.0.0-rc", "1.0.0", "2.1.5-procursus7", "1.0-Xteam1", "1.0.0-alpha", "1.0.0-beta", "1.0.0-rc1"]
    print("原始版本列表:", test_versions)
    sorted_versions = sort_pkg_versions(test_versions)
    print("排序后的版本:", sorted_versions)
    print("最高版本:", get_max_pkg_version(test_versions))


if __name__ == "__main__":
    main()
