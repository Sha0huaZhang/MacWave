## 🌊 MacWave

A package manager for macOS software developers.

## 🌊 Official Website

[macwave.org](https://macwave.org)

## 🌊 Supported macOS Version
macOS Sonoma14 and above
## 🌊 Latest Version

2.1.0, Release on 2026-09-13

## 🌊 What is MacWave?

MacWave is a **package manager** that runs on **macOS/Linux**, designed to host common software packages for macOS software developers.

## 🌊 Why MacWave

1. **One command, install common packages.** No more scattered download links.
2. **Mandatory `@version`.** Every binary is stored as `package@version`, so multiple versions can coexist without conflicting with system tools.
3. **No cache, always up to date.** Package metadata is fetched live from the `infosource` branch.
4. **8 archive formats, CI-verified.** Supports no-extension binaries, `.zip`, `.tar.gz`, `.tar.bz2`, `.tar.xz`, `.tar`, `.gz`, `.bz2`.
5. **Verify first, extract later.** SHA256 is checked before extraction.
6. **Resumable downloads.** Interrupted? Resume with `-C`.
7. **Lightweight and transparent.** Pure Python + Shell. No heavy runtime, no hidden behavior.

## 🌊 Install MacWave

In the terminal, run:

```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Sha0huaZhang/MacWave/2.1.0/lib/install.sh)"
```
```
source ~/.zshrc
```

(If you are using bash instead of zsh, run ```source ~/.bashrc```)
## 🌊 Download Directory 
Installed binaries are stored in:    
```
1. ~/.local/macwave
2. /opt/macwave
3. /usr/local/macwave (Only Intel Mac)
4. Custom
```
Config file is stored in:
```
/opt/macwave_config
```
## Uninstall MacWave

To completely remove MacWave from your system, run the following command in your terminal:

```
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Sha0huaZhang/MacWave/2.1.0/lib/uninstall.sh)"
```
## 🌊 Command Reference

```
Usage:
  wave <command> [package] [flags]

Commands:
  install     Install a package
  uninstall   Uninstall a package
  list        List installed packages
  search      Search for a package in the index
  info        Display detailed information about a package
  

Flags:
  -h, --help              Show help for any command
  -V, --version           Print version information
  -v, --verbose           Enable verbose output (show detailed logs)

Global Flags (can be used with any command):
  -C, --continue          Resume interrupted downloads (like curl -C -)
      --proxy string      Specify an HTTP/HTTPS proxy (e.g., http://127.0.0.1:8080)
      --skip-ssl          Skip SSL certificate verification (insecure)
      --limit-rate string Limit download speed (e.g., 200K, 1M, 5M)
      --ver string        Install a specific version of the package

Special Flags:
wave install <pkgname>@<version>   Download certain version(s) of a package

```

## 🌊 Supported Packages
(Listed in alphabetical order)

```
choma         by opa334
jq            by Stephen Dolan, Nicolas Williams, et al.
ldid          by Jay Freeman (saurik) / Procursus Team
trollrestore  by JJTech (@JJTech0130)
wget          by GNU Project
```
## 🌊 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

## 🌊 Contact Us

Email：[hi@macwave.org](mailto:hi@macwave.org)


