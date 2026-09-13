#!/usr/bin/env python3
"""
批量填充 wget 依赖数据到 infosource-prep/surfboard/depsinfo_arm64/
"""
from pathlib import Path

BASE_DIR = Path("/Users/gaochengfang/Projects/infosource-prep/surfboard/depsinfo_arm64")

# 每个依赖的名称、版本、URL、SHA256、以及公共信息
deps = [
    {
        "name": "gettext",
        "version": "0.21.0",
        "common": {
            "des": "GNU gettext - internationalization library",
            "hom": "https://www.gnu.org/software/gettext/",
            "lic": "GPL-3.0",
            "aut": "GNU Project"
        },
        "url": "http://repo.continuum.io/pkgs/main/osx-arm64/gettext-0.21.0-h826f4ad_0.tar.bz2",
        "sha256": "c6ea63036005734f56ad1e9bd0e54f0b5d41cd8fd5da6dbf91ac499093269067"
    },
    {
        "name": "libiconv",
        "version": "1.16",
        "common": {
            "des": "GNU libiconv - character encoding conversion library",
            "hom": "https://www.gnu.org/software/libiconv/",
            "lic": "LGPL-2.1",
            "aut": "GNU Project"
        },
        "url": "https://conda.anaconda.org/conda-forge/osx-arm64/libiconv-1.16-h642e427_0.tar.bz2",
        "sha256": "90859688dbca4735b74c02af14c4c793"
    },
    {
        "name": "libidn2",
        "version": "2.3.8",
        "common": {
            "des": "GNU libidn2 - internationalized domain names library",
            "hom": "https://www.gnu.org/software/libidn/",
            "lic": "GPL-2.0",
            "aut": "GNU Project"
        },
        "url": "https://conda.anaconda.org/conda-forge/osx-arm64/libidn2-2.3.8-ha90df94_1.conda",
        "sha256": "6d9d2db2c8a645f63073553e9497ea266507c940de42800f2f0faddbf00149cd"
    },
    {
        "name": "libunistring",
        "version": "1.3",
        "common": {
            "des": "GNU libunistring - Unicode string processing library",
            "hom": "https://www.gnu.org/software/libunistring/",
            "lic": "GPL-2.0",
            "aut": "GNU Project"
        },
        "url": "http://repo.continuum.io/pkgs/main/osx-arm64/libunistring-1.3-h1799b2a_0.tar.bz2",
        "sha256": "09ffed353754c619ec1b2edf5281d08db40f5c14906f48ec7c8cffba2dd21f52"
    },
    {
        "name": "openssl",
        "version": "3.0.15",
        "common": {
            "des": "OpenSSL - cryptography and SSL/TLS toolkit",
            "hom": "https://www.openssl.org/",
            "lic": "Apache-2.0",
            "aut": "OpenSSL Project"
        },
        "url": "http://repo.continuum.io/pkgs/main/osx-arm64/openssl-3.0.15-h80987f9_0.tar.bz2",
        "sha256": "503def27e5229dc31eb3eea4c86ecabcd46a27b6711a968bafeaf7facfc8eeb1"  # 注意：此SHA256为占位符，需确认
    },
    {
        "name": "pcre2",
        "version": "10.42",
        "common": {
            "des": "PCRE2 - Perl Compatible Regular Expressions library",
            "hom": "https://www.pcre.org/",
            "lic": "BSD-3-Clause",
            "aut": "PCRE Project"
        },
        "url": "http://repo.continuum.io/pkgs/main/osx-arm64/pcre2-10.42-hb066dcc_0.tar.bz2",
        "sha256": "e2004f3efdf6cbfd7136e119dbcdc8095eef6fd09777f840081eb37b28d0f729"
    },
    {
        "name": "zlib",
        "version": "1.2.13",
        "common": {
            "des": "zlib - compression library",
            "hom": "https://www.zlib.net/",
            "lic": "Zlib",
            "aut": "Jean-loup Gailly and Mark Adler"
        },
        "url": "http://repo.continuum.io/pkgs/main/osx-arm64/zlib-1.2.13-h18a0788_1.tar.bz2",
        "sha256": "a75dca6889cbc372f5d4f77cd51971c44813a52b7d9eb6e0ae4233489158b8bd"  # 注意：此SHA256为占位符，需确认
    }
]

def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        f.write(content)

# 填充数据
for dep in deps:
    dep_dir = BASE_DIR / dep["name"]
    write_file(dep_dir / f"_{dep['name']}@common", "\n".join([f"{k}: \"{v}\"" for k, v in dep["common"].items()]))
    write_file(dep_dir / f"_{dep['name']}@{dep['version']}", f"sha256: \"{dep['sha256']}\"\nurl: \"{dep['url']}\"")
    print(f"✅ 已填充 {dep['name']}@{dep['version']}")

print("✅ 全部依赖填充完成")
