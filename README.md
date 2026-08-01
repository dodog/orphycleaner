# OrphyCleaner GUI

## Overview
<img width="64" height="64" alt="64x64" src="https://github.com/user-attachments/assets/ab88f709-2ab5-446d-8219-2f50f1920540" align="left" style="margin-right:15px"/>

OrphyCleaner is a lightweight GUI tool for Arch-based Linux that scans your home directory for orphaned or unused application folders and helps you decide whether to keep or remove them. Feel free to modify it for your Linux distribution. <br /> <br />

Do you find OrphyCleaner useful? Buy me a [coffee ☕](https://ko-fi.com/dodog)

## 🚀 Features

- Native GTK4 / libadwaita GUI that follows your system's light/dark theme automatically.
- Scans common config locations: `~/.config`, `~/.local/share`, and other hidden folders under your home.
- Matches folders against installed packages (`pacman`), Flatpak apps, `.desktop` applications, AppImages, and executables in your PATH.
- Categorizes folders as Installed, Maybe Installed, or Orphaned and folder count.
- Option to mark orphaned folders as important (Keep / Unkeep).
- Right-click context menu and keyboard shortcuts (<kbd>Ctrl</kbd>+<kbd>F</kbd> to search, <kbd>Return</kbd> to open, <kbd>Delete</kbd> to remove).
- Search/filter box to quickly narrow down folders within a category.
- Package/AUR/Flatpak description lookup for any folder, so you can see what a match actually is before deciding.
- Export the Orphaned list to a text file.
- Includes default ignored folders like cache, trash, and other system-related directories.
- Customizable alias mappings for special folder names.
- Lightweight and fast — no unnecessary dependencies.
- Runs on Manjaro and other Arch-based distributions.

## 🛠️ Installation
From AUR (Recommended for Manjaro/Arch)
   ```bash
   yay -S orphycleaner
   ```

From Github
   ```bash
   git clone https://github.com/dodog/orphycleaner.git
   cd orphycleaner
   python3 orphycleaner.py
   ```


> [!WARNING]
> This script cannot guarantee that orphaned folders are truly unused. Please backup and verify before deleting to avoid losing important data.

## 📋 Requirements

   **Python version:**
   - **Python**: 3.9+
   - **PyGObject**, **GTK4**, and **libadwaita** (GUI libraries)

   ### Installation of GTK4 / libadwaita

   Depending on your Linux distribution, install the dependencies with:

   [Manjaro](https://manjaro.org)/[Arch Linux](https://archlinux.org)
     ```bash
     sudo pacman -S python-gobject gtk4 libadwaita
      ```

## Screenshots
<img width="1500" height="868" alt="orphycleaner-v1 1 0_screnshot" src="https://github.com/user-attachments/assets/0a8a3307-87c9-44a9-835e-76a3772a34ae" />

![orphycleaner](https://github.com/user-attachments/assets/fc5ab883-8252-4486-80bd-9a4e730df632)




## Help
For help visit wiki [OrphyCleaner – Help & Documentation](https://github.com/dodog/orphycleaner/wiki)

## Customization
Update the `IGNORED_FOLDERS` list in the script to exclude additional folders.

Add folder-to-app name aliases in the `ALIAS_MAP` section.


