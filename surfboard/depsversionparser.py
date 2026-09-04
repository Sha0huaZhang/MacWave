#!/usr/bin/env python3
"""
LinuxWave / MacWave depsversionparser.py
负责所有依赖版本号的解析、比较和排序逻辑。
"""

import re
import logging
from packaging.version import parse as parse_version, InvalidVersion


def safe_parse_deps_version(v):
    """
    安全解析依赖版本号。
    依赖版本通常比较标准，但兼容类似 1.0.0-alpha, 2.0.0-beta1 等格式。
    """
    v = str(v)
    try:
        return parse_version(v)
    except InvalidVersion:
        pass

    # 提取基础数字版本（如 1.0.0）
    base_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', v)
    if base_match:
        base_version = base_match.group(1)
        try:
            return parse_version(base_version)
        except InvalidVersion:
            pass

    logging.warning(f"Invalid dependency version string '{v}', falling back to 0.0.0")
    return parse_version("0.0.0")


def sort_deps_versions(versions, reverse=True):
    """
    对依赖版本列表进行安全排序。
    """
    return sorted(versions, key=lambda v: safe_parse_deps_version(v), reverse=reverse)


def get_max_deps_version(versions):
    """
    获取依赖版本列表中的最高版本号。
    """
    if not versions:
        return None
    sorted_versions = sort_deps_versions(versions)
    return sorted_versions[0]


def main():
    """简单的自测逻辑，验证依赖版本解析功能是否正常"""
    test_versions = ["1.0.0", "2.0.0", "1.0.0-beta1", "0.9.0"]
    print("原始版本列表:", test_versions)
    sorted_versions = sort_deps_versions(test_versions)
    print("排序后的版本:", sorted_versions)
    print("最高版本:", get_max_deps_version(test_versions))


if __name__ == "__main__":
    main()
