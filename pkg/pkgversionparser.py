#!/usr/bin/env python3
"""
MacWave pkgversionparser.py
负责所有软件包（Software Package）常规版本号的解析、比较和排序逻辑。
支持 alpha/beta/rc 预发布版本，遇到无数字后缀自动补 0（例如 rc -> rc0）。
特殊版本（procursus, macwaveteam 等）在本文件内处理。
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


def sort_versions(versions, reverse=True):
    return sorted(versions, key=lambda v: safe_parse_pkg_version(v), reverse=reverse)


def get_max_version(versions):
    if not versions:
        return None
    sorted_versions = sort_versions(versions)
    return sorted_versions[0]


def main():
    test_versions = ["1.0.0-rc", "1.0.0", "2.1.5-procursus7", "1.0-Xteam1", "1.0.0-alpha", "1.0.0-beta", "1.0.0-rc1"]
    print("原始版本列表:", test_versions)
    sorted_versions = sort_versions(test_versions)
    print("排序后的版本:", sorted_versions)
    print("最高版本:", get_max_version(test_versions))


if __name__ == "__main__":
    main()
