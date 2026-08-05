# 🌊 MacWave 
A package manager for macOS/Linux jailbreak developers.
# 🌊 What is MacWave? 

MacWave is a **package manager** that runs on **macOS/Linux**, specifically designed to host **iOS/iPadOS jailbreak-related software packages** for jailbreak developers and researchers. These packages are **typically not included in mainstream package managers**. Previously, jailbreak projects required downloading from various scattered sources. Now, you only need a single terminal command.
# 🌊 Install MacWave    
In the terminal, run the following command:        
```
curl -fsSL https://raw.githubusercontent.com/Sha0huaZhang/MacWave/main/install.sh | bash
```    
# 🌊 Download Directory 
Installed binaries are stored in:    
```
~/.local/macwave/bin
```

# 🌊 Command Reference

```MacWave 1.0.0 🌊
Usage:
  wave <command> [package] [flags]

Commands:
  install     Install a package (binary preferred)
  uninstall   Uninstall a package
  list        List installed packages
  search      Search for a package in the index
  info        Display detailed information about a package
  update      Update the package index
  upgrade     Upgrade an installed package to the latest version
  doctor      Check your system for missing dependencies

Flags:
  -h, --help              Show help for any command
  -V, --version           Print version information
  -v, --verbose           Enable verbose output (show detailed logs)

Global Flags (can be used with any command):
  -D, --dir string        Specify an output directory (e.g., ~/Desktop) for downloads
  -C, --continue          Resume interrupted downloads (like curl -C -)
      --proxy string      Specify an HTTP/HTTPS proxy (e.g., http://127.0.0.1:8080)
      --skipssl           Skip SSL certificate verification (insecure)
      --limit-rate string Limit download speed (e.g., 200K, 1M, 5M)
      --dry-run           Simulate the installation without making changes
      --json              Output in JSON format (for scripting)

Examples:
  wave install machox
  wave search choma
  wave info trollresigner

For more details, visit: https://macwave.org
```

# 🌊 Supported Packages
(Listed in alphabetical order)
```
machox          
test_001
```

# 🌊 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

# 🌊 Contact Us


