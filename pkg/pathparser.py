#!/usr/bin/env python3
"""
MacWave Path Parser (2.1)
负责解析 _path 文件：既能输出给人看（Human Readable），也能输出给程序用（JSON结构）。
格式: openssl@2.0: /path/to/openssl
"""

import json
import re
from pathlib import Path


def parse_raw_line(line: str) -> dict:
    """解析单行格式: openssl@2.0: /path/to/openssl"""
    if not line or not line.strip():
        return None
    line = line.strip()
    
    # 处理格式: dep@version: path
    if ':' in line:
        parts = line.split(':', 1)
        dep_key = parts[0].strip()
        path = parts[1].strip()
        # 避免路径里带冒号导致截断
        if dep_key and path:
            return {"dep": dep_key, "path": path}
    
    # 其他格式（无冒号，直接是路径），当作默认路径
    return {"dep": None, "path": line.strip()}


def path_to_json(content: str) -> dict:
    """将 _path 文件内容解析为 JSON 结构"""
    if not content:
        return {}
    
    result = {}
    for line in content.splitlines():
        parsed = parse_raw_line(line)
        if parsed and parsed.get('dep'):
            result[parsed['dep']] = parsed['path']
    return result


def json_to_path(json_data: dict) -> str:
    """将 JSON 结构解析为给人看的 _path 文本格式"""
    if not json_data:
        return ""
    
    lines = []
    for dep, path in json_data.items():
        lines.append(f"{dep}: {path}")
    return "\n".join(lines)


def read_path_file(file_path: Path) -> dict:
    """直接读取 _path 文件并返回 JSON 结构"""
    if not file_path.exists():
        return {}
    with open(file_path, 'r') as f:
        return path_to_json(f.read())


def write_path_file(file_path: Path, json_data: dict) -> None:
    """将 JSON 结构写入 _path 文件（人类可读格式）"""
    if not json_data:
        return
    with open(file_path, 'w') as f:
        f.write(json_to_path(json_data))


def read_deps_file(file_path: Path) -> list:
    """直接读取 _deps 文件，返回依赖列表"""
    if not file_path.exists():
        return []
    with open(file_path, 'r') as f:
        return [line.strip() for line in f if line.strip()]


def write_deps_file(file_path: Path, deps: list) -> None:
    """将依赖列表写入 _deps 文件（人类可读格式）"""
    if not deps:
        return
    with open(file_path, 'w') as f:
        f.write("\n".join(deps))


def main():
    """简单自测"""
    sample_content = "openssl@2.0: /Users/you/.local/macwave/deps/openssl@2.0/openssl\nlibcurl@1.0: /Users/you/.local/macwave/deps/libcurl@1.0/libcurl"
    print("原始 _path 内容:")
    print(sample_content)
    print()
    
    json_data = path_to_json(sample_content)
    print("解析为 JSON:")
    print(json.dumps(json_data, indent=2))
    print()
    
    back_to_text = json_to_path(json_data)
    print("JSON 转回文本:")
    print(back_to_text)


if __name__ == "__main__":
    main()
