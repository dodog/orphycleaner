# OrphyCleaner GUI - Orphaned Config Folder Cleaner

## Overview

OrphyCleaner GUI is a small desktop utility that scans your home directory for configuration folders that may be "orphaned" — meaning they belong to applications that are no longer installed or in use. It helps you identify and clean up these leftover folders to keep your system tidy. 

This app is intended for Manjaro and other Arch-based Linux distributions. Feel free to modify it for your Linux distribution. 

Do you find OrphyCleaner useful? Buy me a [coffee ☕](https://ko-fi.com/dodog)

## Features

- Simple GUI built with Tkinter (no terminal commands required for usage).
- Scans common config locations: `~/.config`, `~/.local/share`, and other hidden folders under your home.
- Matches folders against installed packages (`pacman`), Flatpak apps, `.desktop` applications, AppImages, and executables in your PATH.
- Categorizes folders as Installed, Maybe Installed, or Orphaned and shows summary count.
- Option to mark orphaned folder as important (KEEP)
- Includes default ignored folders like cache, trash, and other system-related directories.
- Customizable alias mappings for special folder names.
- Lightweight and fast — no unnecessary dependencies.
- Runs on Manjaro and other Arch-based distributions.

## Usage
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
<img width="1000" height="618" alt="orphycleaner_screenshot" src="https://github.com/user-attachments/assets/4304a7ff-3eb7-464a-88b9-7f2230970727" />


## Customization
Update the ignored_folders array in the script to exclude additional folders.

Add folder-to-app name aliases in the alias_map section.



