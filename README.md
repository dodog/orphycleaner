# OrphyCleaner - Orphaned Config Folder Cleaner

## Overview

This script scans your home directory for configuration folders that may be "orphaned" — meaning they belong to applications that are no longer installed or in use. It helps you identify and clean up these leftover folders to keep your system tidy.

Do you find OrphyCleaner useful? Buy me a [coffee ☕](https://ko-fi.com/dodog)

## Features

- Scans common config locations: `~/.config`, `~/.local/share`, and other hidden folders under your home.
- Matches folders against installed packages (`pacman`), Flatpak apps, `.desktop` applications, AppImages, and executables in your PATH.
- Categorizes folders as Installed, Maybe Installed, or Orphaned.
- Shows a summary count of folders in each category.
- Provides an interactive cleanup interface for orphaned folders with options to Keep, Delete, Skip, or Quit.
- Includes default ignored folders like cache, trash, and other system-related directories.
- Customizable alias mappings for special folder names.

## Usage
1. Download the script to your home directory
2. Make the script executable:
   ```bash
   chmod +x orphycleaner-gui.py
   ```
3. Run it from your home directory:
   ```bash
   ./orphycleaner-gui.py
   ```

> [!WARNING]
> This script cannot guarantee that orphaned folders are truly unused. Please backup and verify before deleting to avoid losing important data.

## Customization
Update the ignored_folders array in the script to exclude additional folders.

Add folder-to-app name aliases in the alias_map section.

## Requirements
[Manjaro](https://manjaro.org) or [Arch Linux](https://archlinux.org) with pacman (or adapt package check for your distro).

Optional: Flatpak and AppImage support if you use those package formats.

