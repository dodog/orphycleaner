#!/usr/bin/env python3
##
#     Project: OrphyCleaner GUI- Orphaned Config Folder Cleaner
# Description: Scans your home directory for orphaned config folders
#      Author: Jozef Gaal (dodog) 
#     License: GPL-3+
#         Web: https://github.com/dodog/orphycleaner
#
# Scans your home directory for config folders that may belong to uninstalled or unused applications.
# Matches against installed packages (pacman), Flatpak apps, desktop files, AppImages, and executables.
# Categorizes folders as Installed, Maybe Installed, or Orphaned.
#
# WARNING: Not 100% guaranteed — backup and verify before deleting folders.
#
# Usage:
#   python orphycleaner.py
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.
##
import sys
import platform

# -------------------------------
# Basic environment checks
# -------------------------------

# Check Python version
if sys.version_info < (3, 9):
    print("Error: OrphyCleaner requires Python 3.9 or newer.")
    sys.exit(1)

# Check OS (intended for Arch/Manjaro)
if "Linux" not in platform.system():
    print("Warning: This application was designed for Linux (Manjaro/Arch).")
    print("It may not work correctly on your system.\n")

# Check if tkinter is available
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, font
except (ModuleNotFoundError, ImportError):
    print("Error: The Tkinter library is not installed or configured on your system.")
    print("On Manjaro/Arch, install it with:")
    print("    sudo pacman -S tk")
    sys.exit(1)

import os
import subprocess
import shutil
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, font

# =========================================================
# CONFIGURATION
# =========================================================
HOME = os.path.expanduser("~")

# Folders that should never be scanned/marked as orphaned
IGNORED_FOLDERS = [
    f"{HOME}/.local/share/applications", 
    f"{HOME}/.local/share/backgrounds",
    f"{HOME}/.local/share/keyrings",
    f"{HOME}/.local/share/sounds",
    f"{HOME}/.local/share/Trash",
    f"{HOME}/.cache",
    f"{HOME}/.mozilla/cache",
    f"{HOME}/.thumbnails",
    f"{HOME}/.npm",
    f"{HOME}/.config/pulse",
    f"{HOME}/.config/gtk-4.0",
    f"{HOME}/.config/gtk-3.0",
    f"{HOME}/.local/share/flatpak/runtime",
    f"{HOME}/.config/autostart"
]

# Maps folder names to more recognizable app names
ALIAS_MAP = {
    ".audacity-data": "audacity",
    ".SynologyDrive": "synology-drive",
    "Code - OSS": "code-oss",
    ".eID_klient": "eidklient",
    ".mozilla": "mozilla"
}

# Category labels with their display colors
CATEGORY_COLORS = {
    "Installed (package match)": "#4CAF50",      # green
    "Installed (executable found)": "#4CAF50",   # green
    "Installed (Flatpak)": "#4CAF50",            # green
    "Installed (desktop file match)": "#4CAF50", # green
    "Installed (AppImage)": "#4CAF50",           # green
    "Maybe Installed (partial package match)": "#FF9800", # orange
    "Orphaned": "#F44336",                       # red
    "Kept": "#2196F3"                            # blue
}

# =========================================================
# HELPER FUNCTIONS
# =========================================================
def normalize(name):
    # Normalize a name by making lowercase and replacing spaces/punctuation with dashes.
    return name.lower().replace(' ', '-').replace('_', '-').replace('.', '-')

def is_ignored(folder):
    # Check if the folder is in the ignore list or inside an ignored path
    return any(folder == ignored or folder.startswith(ignored + "/") for ignored in IGNORED_FOLDERS)

def get_installed_packages():
    # Get list of installed system packages (Pacman)
    try:
        result = subprocess.run(["pacman", "-Qq"], stdout=subprocess.PIPE, text=True, check=True)
        return {normalize(pkg) for pkg in result.stdout.splitlines()}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return set()

def get_flatpaks():
    # Get list of installed Flatpak apps
    try:
        result = subprocess.run(["flatpak", "list", "--app", "--columns=application"], stdout=subprocess.PIPE, text=True, check=True)
        return {normalize(app) for app in result.stdout.splitlines()}
    except (FileNotFoundError, subprocess.CalledProcessError):
        return set()

def get_appimages():
    # Get list of AppImage files in ~/Applications
    appimage_dir = os.path.join(HOME, "Applications")
    apps = set()
    if os.path.isdir(appimage_dir):
        for f in os.listdir(appimage_dir):
            if f.lower().endswith(".appimage"):
                apps.add(normalize(os.path.splitext(f)[0]))
    return apps

def get_installed_commands():
    # Get list of all executable commands in PATH
    cmds = set()
    for path in os.environ.get("PATH", "").split(os.pathsep):
        if os.path.isdir(path):
            cmds.update(os.listdir(path))
    return cmds

def get_desktop_apps():
    # Get list of .desktop app names from /usr/share/applications.
    apps = set()
    desktop_dir = "/usr/share/applications"
    if os.path.isdir(desktop_dir):
        for f in os.listdir(desktop_dir):
            if f.endswith(".desktop"):
                apps.add(normalize(os.path.splitext(f)[0]))
    return apps

# =========================================================
# MAIN APPLICATION CLASS
# =========================================================
class AppGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OrphyCleaner v1.0")
        self.geometry("1100x650")

        # Scanning state
        self.results = {cat: [] for cat in CATEGORY_COLORS.keys()}
        self.current_category = None
        self.scanning_index = 0
        self.kept_file = os.path.join(HOME, ".config", "kept_folders.txt")

        #Treeview style (font + row height)
        self.style = ttk.Style(self)
        # Use a theme that respects rowheight (clam is widely available on Linux)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass

        # Change the font you like
        self.tree_font = font.Font(family="Helvetica", size=12)  # tweak size to taste
        row_h = self.tree_font.metrics("linespace") + 8          # extra pixels for descenders

        # Two styles: one for the main folder tree, one for the progress tree
        self.style.configure("Folders.Treeview",  font=self.tree_font, rowheight=row_h)
        self.style.configure("Progress.Treeview", font=self.tree_font, rowheight=row_h - 2)

        # Selection colors
        self.style.map("Folders.Treeview",
                    background=[("selected", "#FFEB3B")],
                    foreground=[("selected", "black")])
        self.style.map("Progress.Treeview",
                    background=[("selected", "#FFC107")],
                    foreground=[("selected", "black")])

        # Build UI
        self.create_progress_area()
        self.create_warning_label()
        self.create_main_layout()

        # Prepare data for scanning
        self.folders_to_scan = self.prepare_folders()
        self.installed_pkgs = get_installed_packages()
        self.installed_cmds = get_installed_commands()
        self.desktop_apps = get_desktop_apps()
        self.installed_flatpaks = get_flatpaks()
        self.appimages = get_appimages()

        # Load kept folders from file
        self.load_kept_folders()

        # Start scanning loop
        self.after(100, self.scan_next_folder)

    # =========================================================
    # UI CREATION METHODS
    # =========================================================
    def create_progress_area(self):
        # Create top section showing scan progress using Treeview
        frame = ttk.Frame(self)
        frame.pack(side="top", fill="x", padx=5, pady=5)

        self.progress_label = ttk.Label(frame, text="Scanning folders...")
        self.progress_label.pack(anchor="w")

        # Treeview
        self.progress_tree = ttk.Treeview(frame, show="tree", selectmode="browse", height=8, style="Progress.Treeview")
        self.progress_tree.pack(side="left", fill="both", expand=True)

        # Vertical scrollbar
        scrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.progress_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.progress_tree.configure(yscrollcommand=scrollbar.set)

    def create_warning_label(self):
        # Add a cautionary message about deleting folders.
        warning_frame = ttk.Frame(self)
        warning_frame.pack(side="top", fill="x", padx=5)
        tk.Label(warning_frame,
                 text="⚠ Be careful deleting folders. This script is not 100% accurate.",
                 fg="red", font=("Helvetica", 10, "italic")).pack(anchor="w")

    def create_main_layout(self):
        #Create main three-column layout: categories, folder list, action buttons.
        main_frame = ttk.Frame(self)
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # Left column: Category buttons
        self.left_frame = ttk.Frame(main_frame, width=450)
        self.left_frame.pack(side="left", fill="y", padx=5)
        self.left_frame.pack_propagate(False)

        # Middle column: Folder list using Treeview
        self.middle_frame = ttk.Frame(main_frame)
        self.middle_frame.pack(side="left", fill="both", expand=True, padx=5)
        self.folder_tree = ttk.Treeview(self.middle_frame, show="tree", selectmode="browse", style="Folders.Treeview")
        self.folder_tree.pack(side="left", fill="both", expand=True)

        # Vertical scrollbar
        scrollbar = ttk.Scrollbar(self.middle_frame, orient="vertical", command=self.folder_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.folder_tree.configure(yscrollcommand=scrollbar.set)

        # Right column: Action buttons
        self.create_action_buttons(main_frame)

    def create_action_buttons(self, parent):
        #Right column buttons for keeping, opening, deleting folders.
        right_frame = ttk.Frame(parent, width=150)
        right_frame.pack(side="right", fill="y", padx=5)
        right_frame.pack_propagate(False)

        # Configure column to stretch buttons full width
        right_frame.columnconfigure(0, weight=1)

        # KEEP / UNKEEP buttons share the same grid position
        self.keep_button = tk.Button(right_frame, text="KEEP", bg="#4CAF50", fg="white", command=self.keep_folder)
        self.unkeep_button = tk.Button(right_frame, text="UNKEEP", bg="#2196F3", fg="white", command=self.unkeep_folder)

        self.keep_button.grid(row=0, column=0, sticky="ew", pady=2)
        self.unkeep_button.grid(row=0, column=0, sticky="ew", pady=2)

        # Initially show KEEP
        self.keep_button.lift()

        # Open folder
        self.open_button = tk.Button(right_frame, text="OPEN FOLDER", bg="#FF9800", fg="white", command=self.open_folder)
        self.open_button.grid(row=1, column=0, sticky="ew", pady=5)

        # Delete folder    
        self.delete_button = tk.Button(right_frame, text="DELETE", bg="#F44336", fg="white", command=self.delete_folder)
        self.delete_button.grid(row=2, column=0, sticky="ew", pady=5)
        # start disabled until a category is shown
        self.delete_button.config(state="disabled", bg="#cccccc", fg="#666666")

        # Help button
        self.help_button = tk.Button(right_frame, text="HELP", command=self.open_help)
        self.help_button.grid(row=3, column=0, sticky="ew", pady=5)

        # Quit button
        tk.Button(right_frame, text="QUIT", command=self.destroy).grid(row=4, column=0, sticky="ew", pady=5)

    # =========================================================
    # SCANNING LOGIC
    # =========================================================
    def prepare_folders(self):
        # Collect candidate folders to check from ~/.config, ~/.local/share, and hidden folders in ~.
        folders = []

        # From ~/.config
        config_path = os.path.join(HOME, ".config")
        if os.path.isdir(config_path):
            folders.extend(os.path.join(config_path, f) for f in os.listdir(config_path))

        # From ~/.local/share
        local_share = os.path.join(HOME, ".local", "share")
        if os.path.isdir(local_share):
            folders.extend(os.path.join(local_share, f) for f in os.listdir(local_share))

        # Hidden folders in home, excluding .config/.local
        for f in os.listdir(HOME):
            full_path = os.path.join(HOME, f)
            if f.startswith('.') and os.path.isdir(full_path) and f not in ['.config', '.local']:
                folders.append(full_path)

        # Remove ignored folders
        return [f for f in folders if os.path.isdir(f) and not is_ignored(f)]

    def scan_next_folder(self):
        # Process one folder at a time and classify it using Treeview.
        if self.scanning_index >= len(self.folders_to_scan):
            self.progress_tree.insert("", "end", text="Scanning complete.")
            self.progress_label.config(text="Scanning complete")
            self.create_category_buttons()
            return

        folder = self.folders_to_scan[self.scanning_index]
        idx = len(self.progress_tree.get_children())
        
        # Insert folder into Treeview
        item_id = self.progress_tree.insert("", "end", text=folder)
        
        # Alternate row colors
        bg_color = "#f9f9f9" if idx % 2 == 0 else "#ffffff"
        self.progress_tree.tag_configure(f"row{idx}", background=bg_color)
        self.progress_tree.item(item_id, tags=(f"row{idx}",))

        # Scroll to last item
        self.progress_tree.see(item_id)

        # Classification rules
        base = os.path.basename(folder)
        name = ALIAS_MAP.get(base, normalize(base.lstrip('.')))

        if name in self.installed_pkgs:
            self.results["Installed (package match)"].append(folder)
        elif name in self.installed_cmds:
            self.results["Installed (executable found)"].append(folder)
        elif any(name in pkg for pkg in self.installed_pkgs):
            self.results["Maybe Installed (partial package match)"].append(folder)
        elif any(name in app for app in self.installed_flatpaks):
            self.results["Installed (Flatpak)"].append(folder)
        elif any(name in app for app in self.desktop_apps):
            self.results["Installed (desktop file match)"].append(folder)
        elif any(name in app for app in self.appimages):
            self.results["Installed (AppImage)"].append(folder)
        elif folder not in self.results["Kept"]:
            self.results["Orphaned"].append(folder)

        self.scanning_index += 1
        self.after(1, self.scan_next_folder)

    # =========================================================
    # CATEGORY HANDLING
    # =========================================================
    def create_category_buttons(self):
        # Create/update category buttons with counts.
        # Remove old category buttons 
        if hasattr(self, "categories_frame"):
            for widget in self.categories_frame.winfo_children():
                widget.destroy()
        else:
            self.categories_frame = tk.Frame(self.left_frame)
            self.categories_frame.pack(side="top", fill="x")

        # Create category buttons
        for cat, color in CATEGORY_COLORS.items():
            btn = tk.Button(
                self.categories_frame,
                text=f"{cat} ({len(self.results.get(cat, []))})",
                bg=color,
                fg="white",
                relief="raised",
                command=lambda c=cat: self.show_category(c)
            )
            btn.pack(fill="x", pady=2)

        if not self.current_category:
            self.show_category("Orphaned")

        # Create infobox
        if hasattr(self, "infobox_frame"):
            for widget in self.infobox_frame.winfo_children():
                widget.destroy()
        else:
            self.infobox_frame = tk.Frame(self.left_frame)
            self.infobox_frame.pack(side="top", fill="x", pady=(10,0))

        from tkinter import font
        bold_font = font.Font(family="Helvetica", size=10, weight="bold")
        normal_font = font.Font(family="Helvetica", size=10)

        tk.Label(self.infobox_frame, text="HOW TO USE:", font=bold_font, justify="left", anchor="nw").pack(fill="x")
        tk.Label(
            self.infobox_frame,
            text=(
                "1. Select a category to see folders.\n"
                "2. Only 'Orphaned' folders can be deleted.\n"
                "3. Use KEEP/UNKEEP to mark important folders."
            ),
            font=normal_font,
            justify="left",
            anchor="nw"
        ).pack(fill="x", pady=(0,5))
        tk.Label(self.infobox_frame, text="⚠ WARNING:", font=bold_font, fg="red", justify="left", anchor="nw").pack(fill="x")
        tk.Label(
            self.infobox_frame,
            text=(
                "- Deleting folders is permanent if Trash is unavailable.\n"
                "- Double-check and backup before deleting anything.\n"
                "- This script is not 100% accurate."
            ),
            font=normal_font,
            justify="left",
            anchor="nw"
        ).pack(fill="x")

        # Make infobox text wrap dynamically
        def update_wrap(event):
            for lbl in self.infobox_frame.winfo_children():
                lbl.config(wraplength=event.width)      
        self.left_frame.bind("<Configure>", update_wrap)

    def show_category(self, category):
        # Show all folders in the selected category using Treeview.
        self.current_category = category
        self.folder_tree.heading("#0", text="Folders", anchor="w")

        # Clear old folder list
        for item in self.folder_tree.get_children():
            self.folder_tree.delete(item)

        # Add folders for this category with alternating row colors
        for idx, folder in enumerate(self.results.get(category, [])):
            item_id = self.folder_tree.insert("", "end", text=folder)
            bg_color = "#f9f9f9" if idx % 2 == 0 else "#ffffff"
            self.folder_tree.tag_configure(f"row{idx}", background=bg_color)
            self.folder_tree.item(item_id, tags=(f"row{idx}",))

        # Highlight the selected category button
        for btn in self.categories_frame.winfo_children():
            text = btn.cget("text")
            if text.startswith(category):
                btn.config(relief="sunken", text=f"▶ {category} ({len(self.results.get(category, []))})")
            else:
                btn.config(relief="raised", text=text.lstrip("▶ "))

        # Show correct KEEP/UNKEEP without moving it
        if category == "Orphaned":
            self.keep_button.config(state="normal")
            self.unkeep_button.config(state="disabled")
            self.keep_button.lift()
        elif category == "Kept":
            self.keep_button.config(state="disabled")
            self.unkeep_button.config(state="normal")
            self.unkeep_button.lift()
        else:
            self.keep_button.config(state="disabled")
            self.unkeep_button.config(state="disabled")
            self.keep_button.lift()
        
        # Enable/disable and recolor buttons based on category
        if category == "Orphaned":
            self.keep_button.config(state="normal", bg="#4CAF50", fg="white")
            self.unkeep_button.config(state="disabled", bg="#cccccc", fg="#666666")
            self.delete_button.config(state="normal", bg="#F44336", fg="white")
            self.keep_button.lift()
        elif category == "Kept":
            self.keep_button.config(state="disabled", bg="#cccccc", fg="#666666")
            self.unkeep_button.config(state="normal", bg="#2196F3", fg="white")
            self.delete_button.config(state="disabled", bg="#cccccc", fg="#666666")
            self.unkeep_button.lift()
        else:
            self.keep_button.config(state="disabled", bg="#cccccc", fg="#666666")
            self.unkeep_button.config(state="disabled", bg="#cccccc", fg="#666666")
            self.delete_button.config(state="disabled", bg="#cccccc", fg="#666666")
            self.keep_button.lift()

    def maintain_selection(self, prev_index: int):
        # After changing the Treeview contents, keep selection on the next sensible row.
        items = self.folder_tree.get_children()
        if not items:
            return

        target_index = prev_index if prev_index < len(items) else len(items) - 1
        target_item = items[target_index]

        # Clear old selection and select the target item
        self.folder_tree.selection_remove(self.folder_tree.selection())
        self.folder_tree.selection_add(target_item)
        self.folder_tree.see(target_item)
      
    # =========================================================
    # ACTION HANDLERS
    # =========================================================
    def load_kept_folders(self):
        # Load kept folders from file.
        if os.path.exists(self.kept_file):
            with open(self.kept_file, "r") as f:
                for line in f:
                    path = line.strip()
                    if os.path.isdir(path):
                        self.results["Kept"].append(path)

    # Move selected folder from and  to category.
    def move_folder_between_categories(self, src_category, dst_category):
        # Move selected folder from src_category to dst_category and keep selection.
        if self.current_category != src_category:
            return

        selected_items = self.folder_tree.selection()
        if not selected_items:
            return
        item_id = selected_items[0]
        folder = self.folder_tree.item(item_id, "text")

        if folder not in self.results.get(src_category, []):
            return  # Safety check

        # Move folder between categories
        self.results[src_category].remove(folder)
        self.results.setdefault(dst_category, []).append(folder)

        # Refresh the source category list
        prev_index = list(self.folder_tree.get_children()).index(item_id)
        self.show_category(src_category)

        # Keep selection
        self.maintain_selection(prev_index)

    def keep_folder(self):
        self.move_folder_between_categories("Orphaned", "Kept")
        self.save_kept_folders()
        self.create_category_buttons()

    def unkeep_folder(self):
        self.move_folder_between_categories("Kept", "Orphaned")
        self.save_kept_folders()
        self.create_category_buttons()

    def save_kept_folders(self):
        # Write kept folders to file.
        with open(self.kept_file, "w") as f:
            for fpath in self.results["Kept"]:
                f.write(fpath + "\n")

    def open_folder(self):
        # Open the selected folder in file manager.
        selected_items = self.folder_tree.selection()
        if not selected_items:
            return
        folder = self.folder_tree.item(selected_items[0], "text")
        subprocess.Popen(["xdg-open", folder])

    def open_help(self):
        # Open the help URL in the default web browser.
        webbrowser.open("https://github.com/dodog/orphycleaner") 

    def delete_folder(self):
        # Delete selected orphaned folder and keep selection on next row.
        selected_items = self.folder_tree.selection()
        if not selected_items:
            return
        item_id = selected_items[0]
        folder = self.folder_tree.item(item_id, "text")

        if self.current_category != "Orphaned":
            messagebox.showwarning("Delete", "Only Orphaned folders can be deleted.")
            return

        # Confirm deletion
        if shutil.which("gio"):
            confirm = messagebox.askyesno(
                "Confirm Delete",
                f"Are you sure you want to move this folder to Trash?\n\n{folder}"
            )
            if not confirm:
                return
            subprocess.run(["gio", "trash", folder])
        else:
            confirm = messagebox.askyesno(
                "Confirm Permanent Delete",
                f"Trash is not available.\n\n"
                f"Are you sure you want to permanently delete this folder?\n\n{folder}"
            )
            if not confirm:
                return
            subprocess.run(["rm", "-rf", folder])

        # Update UI and data
        prev_index = list(self.folder_tree.get_children()).index(item_id)
        self.folder_tree.delete(item_id)
        if folder in self.results[self.current_category]:
            self.results[self.current_category].remove(folder)

        self.create_category_buttons()

        # Keep selection on the next appropriate row
        self.maintain_selection(prev_index)

# =========================================================
# ENTRY POINT
# =========================================================
if __name__ == "__main__":
    app = AppGUI()
    app.mainloop()
