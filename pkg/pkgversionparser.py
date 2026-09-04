#!/usr/bin/env python3
"""
MacWave / LinuxWave pkgversionparser.py
负责所有软件包（Software Package）版本号的解析、比较和排序逻辑。
"""

import re
import logging
from packaging.version import parse as parse_version, InvalidVersion


def safe_parse_pkg_version(v):
    v = str(v)
    try:
        return parse_version(v)
    except InvalidVersion:
        pass

    base_match = re.search(r'(\d+\.\d+\.\d+)', v)
    if base_match:
        base_version = base_match.group(1)
        proc_match = re.search(r'procursus(\d+)', v)
        suffix_num = int(proc_match.group(1)) if proc_match else 0
        try:
            return parse_version(f"{base_version}.{suffix_num}")
        except InvalidVersion:
            pass

    macwave_match = re.search(r'(\d+\.\d+)-macwaveteam(\d+)', v)
    if macwave_match:
        base_version = macwave_match.group(1)
        team_num = int(macwave_match.group(2))
        return parse_version(f"{base_version}.{team_num}")

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
    test_versions = ["2.1.5-procursus7", "2.1.5-procursus6", "1.0-macwaveteam2", "1.0.0"]
    print("原始版本列表:", test_versions)
    sorted_versions = sort_pkg_versions(test_versions)
    print("排序后的版本:", sorted_versions)
    print("最高版本:", get_max_pkg_version(test_versions))


if __name__ == "__main__":
    main()
