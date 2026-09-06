#!/usr/bin/env python3
"""
MacWave specialversionparser.py
专门处理 MacWave 特有的特殊版本号（procursus、macwaveteam 等）。
这些版本号带有自定义后缀（例如 1.0-Xteam1, 2.1.5-procursus7）。
它们被视为正式版（大于 alpha/beta/rc），内部按整数递增排序。
"""

import re
import logging
from packaging.version import parse as parse_version, InvalidVersion


def is_special_version(v: str) -> bool:
    """判断版本号是否包含特殊后缀标记"""
    v = str(v)
    return bool(re.search(r'(procursus|macwaveteam|team|Xteam)', v, re.IGNORECASE))


def extract_special_info(v: str):
    """从特殊版本号中提取基础数字和后缀编号"""
    v = str(v)
    info = {"base": None, "suffix_type": None, "suffix_num": 0}

    # 处理 procursus 类型：1.0-procursus7 或 2.1.5-procursus7
    proc_match = re.search(r'(\d+\.\d+(?:\.\d+)?)[-_]?procursus(\d+)', v, re.IGNORECASE)
    if proc_match:
        base = proc_match.group(1)
        if base.count('.') == 1:
            base += '.0'
        info["base"] = base
        info["suffix_type"] = "procursus"
        info["suffix_num"] = int(proc_match.group(2))
        return info

    # 处理 macwaveteam 类型：1.0-macwaveteam2 或 1.0-Xteam2
    macwave_match = re.search(r'(\d+\.\d+(?:\.\d+)?)[-_]?(?:macwaveteam|Xteam)(\d+)', v, re.IGNORECASE)
    if macwave_match:
        base = macwave_match.group(1)
        if base.count('.') == 1:
            base += '.0'
        info["base"] = base
        info["suffix_type"] = "macwaveteam"
        info["suffix_num"] = int(macwave_match.group(2))
        return info

    # 兜底处理：匹配任意数字 + 数字后缀
    base_match = re.search(r'(\d+\.\d+(?:\.\d+)?)', v)
    if base_match:
        base = base_match.group(1)
        if base.count('.') == 1:
            base += '.0'
        info["base"] = base
        info["suffix_type"] = "unknown"
        info["suffix_num"] = 0
        return info

    return None


def safe_parse_special_version(v: str):
    """安全解析特殊版本号，返回 packaging.version 对象。特殊版本视为正式版。"""
    v = str(v)
    info = extract_special_info(v)
    if not info:
        logging.warning(f"Invalid special version string '{v}', falling back to 0.0.0")
        return parse_version("0.0.0")

    # 组装为 X.Y.Z.N 格式（N 为后缀编号）
    base = info["base"]
    suffix_num = info["suffix_num"]
    return parse_version(f"{base}.{suffix_num}")


def sort_special_versions(versions, reverse=True):
    """对特殊版本列表进行排序"""
    return sorted(versions, key=lambda v: safe_parse_special_version(v), reverse=reverse)


def get_max_special_version(versions):
    """获取特殊版本列表中的最高版本号"""
    if not versions:
        return None
    sorted_versions = sort_special_versions(versions)
    return sorted_versions[0]


def main():
    """自测：验证特殊版本排序"""
    test_versions = ["1.0-Xteam1", "1.0-Xteam2", "1.0-Xteam3", "2.1.5-procursus7", "2.1.5-procursus6"]
    print("原始特殊版本列表:", test_versions)
    sorted_versions = sort_special_versions(test_versions)
    print("排序后的特殊版本:", sorted_versions)
    print("最高特殊版本:", get_max_special_version(test_versions))


if __name__ == "__main__":
    main()
