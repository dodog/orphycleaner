# OrphyCleaner GUI

## Overview

OrphyCleaner is a tool that scans your Linux system for orphaned or unused application folders and helps you decide whether to keep or remove them to keep your system tidy. It provides descriptions of applications using multiple sources (Pacman, AUR, Flatpak) to make it easier to identify what a folder belongs to. 

This app is intended for Manjaro and other Arch-based Linux distributions. Feel free to modify it for your Linux distribution. 

Do you find OrphyCleaner useful? Buy me a [coffee ☕](https://ko-fi.com/dodog)

## 🚀 Features

- Simple GUI built with Tkinter (no terminal commands required for usage).
- Scans common config locations: `~/.config`, `~/.local/share`, and other hidden folders under your home.
- Matches folders against installed packages (`pacman`), Flatpak apps, `.desktop` applications, AppImages, and executables in your PATH.
- Categorizes folders as Installed, Maybe Installed, or Orphaned and shows summary count.
- Option to mark orphaned folder as important (KEEP)
- Includes default ignored folders like cache, trash, and other system-related directories.
- Customizable alias mappings for special folder names.
- Lightweight and fast — no unnecessary dependencies.
- Runs on Manjaro and other Arch-based distributions.

## 🛠️ Usage
1. Download the script 
2. Run it from your home directory:
   ```bash
   python orphycleaner.py
   ```

> [!WARNING]
> This script cannot guarantee that orphaned folders are truly unused. Please backup and verify before deleting to avoid losing important data.

## 📋 Requirements for the Python version

**Python version:**
- **Python**: 3.9+  
- **Tkinter** (GUI library)  

### Installation of Tkinter
Depending on your Linux distribution, install `tkinter` with:

[Manjaro](https://manjaro.org)/[Arch Linux](https://archlinux.org)
  ```bash
  sudo pacman -S tk
   ```

## Screenshots
<img width="1500" height="868" alt="orphycleaner-v1 1 0_screnshot" src="https://github.com/user-attachments/assets/0a8a3307-87c9-44a9-835e-76a3772a34ae" />


## Help
For help visit wiki [OrphyCleaner – Help & Documentation](https://github.com/dodog/orphycleaner/wiki)

## Customization
Update the ignored_folders array in the script to exclude additional folders.

Add folder-to-app name aliases in the alias_map section.



