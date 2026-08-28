#!/usr/bin/env python3
"""
MacWave Version Parser
负责所有软件包的版本号解析、比较和排序逻辑。
"""

import re
import logging
from packaging.version import parse as parse_version, InvalidVersion


def safe_parse_version(v):
    """
    安全解析版本号，兼容 procursus 等非标准格式。
    如果解析失败，降级处理。
    """
    v = str(v)
    try:
        return parse_version(v)
    except InvalidVersion:
        pass

    # 尝试提取基础版本号 如 2.0.0
    base_match = re.search(r'(\d+\.\d+\.\d+)', v)
    if base_match:
        base_version = base_match.group(1)
        # 兼容类似 2.0.0procursus1 的格式，将后缀数字作为附加版本段
        proc_match = re.search(r'procursus(\d+)', v)
        suffix_num = int(proc_match.group(1)) if proc_match else 0
        try:
            return parse_version(f"{base_version}.{suffix_num}")
        except InvalidVersion:
            pass

    logging.warning(f"Invalid version string '{v}', falling back to 0.0.0")
    return parse_version("0.0.0")


def sort_versions(versions, reverse=True):
    """
    对版本号列表进行安全排序。
    """
    return sorted(versions, key=lambda v: safe_parse_version(v), reverse=reverse)


def get_max_version(versions):
    """
    获取列表中的最高版本号。
    """
    if not versions:
        return None
    sorted_versions = sort_versions(versions)
    return sorted_versions[0]


def main():
    """简单的自测逻辑，验证版本解析功能是否正常"""
    test_versions = ["2.0.0", "1.0.0", "2.0.0procursus1", "0.9.0"]
    print("原始版本列表:", test_versions)
    sorted_versions = sort_versions(test_versions)
    print("排序后的版本:", sorted_versions)
    print("最高版本:", get_max_version(test_versions))


if __name__ == "__main__":
    main()
