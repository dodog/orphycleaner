#!/usr/bin/env python3
__version__ = "1.1.3"
##
#     Project: OrphyCleaner GUI- Orphaned Config Folder Cleaner
# Description: Scans your home directory for orphaned config folders
#      Author: Jozef Gaal (dodog)
#     License: AGPL-3+
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
import os
import subprocess
import shutil
import json
import re
import time
import webbrowser
import threading
import tkinter as tk
from tkinter import ttk, messagebox, font

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

# =========================================================
# CONFIGURATION
# =========================================================
HOME = os.path.expanduser("~")

# Cache and kept file locations 
CACHE_FILE = os.path.join(HOME, ".cache", "orphycleaner", "orphycleaner_pkg_cache.json")
KEPT_FILE  = os.path.join(HOME, ".local", "share", "orphycleaner", "kept_folders.txt")

# Folders that should never be scanned/marked as orphaned
IGNORED_FOLDERS = [
    f"{HOME}/.local/share/applications", 
    f"{HOME}/.local/share/backgrounds",
    f"{HOME}/.local/share/keyrings",
    f"{HOME}/.local/share/sounds",
    f"{HOME}/.local/share/Trash",
    f"{HOME}/.local/share/orphycleaner",
    f"{HOME}/.local/share/gvfs-metadata",
    f"{HOME}/.local/share/mime",
    f"{HOME}/.local/share/fonts",
    f"{HOME}/.cache",
    f"{HOME}/.mozilla/cache",
    f"{HOME}/.thumbnails",
    f"{HOME}/.npm",
    f"{HOME}/.themes",
    f"{HOME}/.var/app",
    f"{HOME}/.pki",
    f"{HOME}/.fonts",
    f"{HOME}/.Templates",
    f"{HOME}/.Public",
    f"{HOME}/.config/pulse",
    f"{HOME}/.config/gtk-4.0",
    f"{HOME}/.config/gtk-3.0",
    f"{HOME}/.config/gtk-2.0",
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

# Get list of .desktop app names from /usr/share/applications.
def get_desktop_apps():
    apps = set()
    desktop_dir = "/usr/share/applications"
    if os.path.isdir(desktop_dir):
        for f in os.listdir(desktop_dir):
            if f.endswith(".desktop"):
                apps.add(normalize(os.path.splitext(f)[0]))
    return apps

# If you have an AUR helper like yay or paru
def get_aur_packages():
    try:
        result = subprocess.run(["yay", "-Qq"], stdout=subprocess.PIPE, text=True, check=True)
        return {normalize(pkg) for pkg in result.stdout.splitlines()}
    except (FileNotFoundError, subprocess.CalledProcessError):
        return set()

# =========================================================
# MAIN APPLICATION CLASS
# =========================================================
class AppGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"OrphyCleaner v{__version__}")
        self.geometry("1500x830")

        # Only set icon if installed system-wide (AUR)
        system_icon_path = "/usr/share/pixmaps/orphycleaner.png"
        if os.path.exists(system_icon_path):
            try:
                # self.iconphoto sets the icon for the window decorations
                self.iconphoto(True, tk.PhotoImage(file=system_icon_path))
            except Exception as e:
                print(f"Warning: could not set taskbar icon: {e}")
        else:
            # Running directly from source - no icon 
            pass
       
        # Ensure directories exist
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        os.makedirs(os.path.dirname(KEPT_FILE), exist_ok=True)

        # -----------------------------
        # Thread/cache-related attributes
        # -----------------------------
        # Package description cache file
        self.cache_file = CACHE_FILE
        try:
            if os.path.exists(self.cache_file) and os.path.getsize(self.cache_file) > 0:
                with open(self.cache_file, "r") as f:
                    self.pkg_descriptions = json.load(f)
            else:
                self.pkg_descriptions = {}
        except Exception:
            # corrupted/empty file fallback
            self.pkg_descriptions = {}

        # AUR backoff helpers
        self.aur_last_query = {}        # pkg_name -> last query timestamp
        self.aur_backoff_base = 10      # base backoff in seconds
        self.aur_backoff_max = 300      # max backoff (5 min)

        # -----------------------------
        # Scanning state
        # -----------------------------
        self.results = {cat: [] for cat in CATEGORY_COLORS.keys()}
        self.current_category = None
        self.scanning_index = 0
        self.kept_file = KEPT_FILE

        # -----------------------------
        # Treeview style (font + row height)
        # -----------------------------
        self.style = ttk.Style(self)
        # Use a theme that respects rowheight (clam)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        
        # Change the font you like
        self.tree_font = font.Font(family="Helvetica", size=12)
        row_h = self.tree_font.metrics("linespace") + 8
        
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

        # -----------------------------
        # Build UI
        # -----------------------------
        self.create_progress_area()
        self.create_warning_label()
        self.create_main_layout()

        # -----------------------------
        # Prepare data for scanning
        # -----------------------------
        self.folders_to_scan = self.prepare_folders()
        self.installed_pkgs = get_installed_packages()  # Pacman
        self.installed_aur = get_aur_packages()         # AUR
        self.installed_flatpaks = get_flatpaks()        # Flatpak
        self.installed_cmds = get_installed_commands()
        self.desktop_apps = get_desktop_apps()
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

        # Right column
        self.right_frame = ttk.Frame(main_frame)
        self.right_frame.pack(side="right", fill="y", padx=5, pady=5)

        # Right column: Action buttons
        self.create_action_buttons(main_frame)
    
    #Right column buttons for keeping, opening, deleting folders.
    def create_action_buttons(self, parent):
        self.right_frame = ttk.Frame(parent, width=250)
        self.right_frame.pack(side="right", fill="y", padx=5)
        self.right_frame.pack_propagate(False)
        self.right_frame.grid_propagate(False)   # Prevent grid from resizing

        # Configure column to stretch buttons full width
        self.right_frame.columnconfigure(0, weight=1)

        # KEEP / UNKEEP buttons share the same grid position
        self.keep_button = tk.Button(self.right_frame, text="KEEP", bg="#4CAF50", fg="white", command=self.keep_folder)
        self.unkeep_button = tk.Button(self.right_frame, text="UNKEEP", bg="#2196F3", fg="white", command=self.unkeep_folder)

        self.keep_button.grid(row=0, column=0, sticky="ew", pady=2)
        self.unkeep_button.grid(row=0, column=0, sticky="ew", pady=2)

        # Initially show KEEP
        self.keep_button.lift()

        # Load descriptions button
        self.load_desc_button = tk.Button(self.right_frame, text="LOAD DESCRIPTION", command=self.load_description, bg="#7616DF", fg="white")
        self.load_desc_button.grid(row=1, column=0, sticky="ew", pady=5)

        # Open folder
        self.open_button = tk.Button(self.right_frame, text="OPEN FOLDER", bg="#FF9800", fg="white", command=self.open_folder)
        self.open_button.grid(row=2, column=0, sticky="ew", pady=5)

        # Delete folder    
        self.delete_button = tk.Button(self.right_frame, text="DELETE", bg="#F44336", fg="white", command=self.delete_folder)
        self.delete_button.grid(row=3, column=0, sticky="ew", pady=5)
        # start disabled until a category is shown
        self.delete_button.config(state="disabled", bg="#cccccc", fg="#666666")

        # Help button
        self.help_button = tk.Button(self.right_frame, text="HELP", command=self.open_help)
        self.help_button.grid(row=4, column=0, sticky="ew", pady=5)

        # Quit button
        tk.Button(self.right_frame, text="QUIT", command=self.destroy).grid(row=5, column=0, sticky="ew", pady=5)
        
        # Description displayed under the buttons
        self.desc_label = tk.Label(self.right_frame, text="", wraplength=250, justify="left", fg="#333")
        self.desc_label.grid(row=6, column=0, sticky="w", pady=5)

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
    # DESCRIPTION HANDLER
    # =========================================================
    #Run a command and return stdout text or None. Suppress stderr.
    def _run_cmd(self, cmd, timeout=5):
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=timeout
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            return ""
        except Exception:
            return ""
    
    #Parse Description from pacman/yay/paru -Qi/-Si (handles locales like 'Description' or 'Popis')."""
    def _parse_desc_from_qi_or_si(self, text):
        if not text:
            return None
        for line in text.splitlines():
            if ":" in line:
                label, val = line.split(":", 1)
                lab = label.strip().lower()
                if "description" in lab or "popis" in lab:  # add more locales if needed
                    return val.strip()
        return None

    # Parse description from *-Ss output (pacman/yay/paru). 
    # Looks for header lines containing '/<wanted_name>' and returns the following indented description line.
    def _parse_desc_from_ss(self, text, wanted_name):
        if not text:
            return None

        lines = text.splitlines()
        wanted_name = wanted_name.strip().lower()

        for i, line in enumerate(lines):
            line = line.strip("\n")
            # skip noise lines
            if not line or line.startswith("==>") or "matches found" in line.lower():
                continue

            # detect header lines like 'aur/gnokii 0.6.31-15 ...'
            if re.search(r"/" + re.escape(wanted_name) + r"\b", line.lower()):
                # next indented line should be description
                if i + 1 < len(lines):
                    nxt = lines[i + 1]
                    if nxt.startswith("    ") or nxt.startswith("\t"):
                        return nxt.strip()

        # fallback: first indented non-noise line
        for line in lines:
            if line.startswith("    ") or line.startswith("\t"):
                val = line.strip()
                if val and "matches found" not in val.lower():
                    return val

        return None

    # -----------------------------
    # PACMAN SEARCH
    # -----------------------------
    def _search_pacman(self, name):
        """Try pacman for installed (-Qi), repo (-Si), then search (-Ss)."""
        # 1) Installed (fast, local)
        out = self._run_cmd(["pacman", "-Qi", name], timeout=2)
        desc = self._parse_desc_from_qi_or_si(out)
        if desc:
            return desc

        # 2) Repo info (might be slower)
        out = self._run_cmd(["pacman", "-Si", name], timeout=8)
        desc = self._parse_desc_from_qi_or_si(out)
        if desc:
            return desc

        # 3) Search databases
        out = self._run_cmd(["pacman", "-Ss", f"^{name}$"], timeout=8)
        desc = self._parse_desc_from_ss(out, name)
        if desc:
            return desc

        return None

    # -----------------------------
    # AUR SEARCH (via yay/paru) with negative caching & backoff
    # -----------------------------
    def _search_aur(self, pkg_name):
        cache_key = f"aur:{pkg_name}"
        # check negative cache
        if cache_key in self.pkg_descriptions:
            if self.pkg_descriptions[cache_key] == "<not found>":
                return None
            return self.pkg_descriptions[cache_key]

        # pick the first available helper
        if shutil.which("yay"):
            helper = "yay"
        elif shutil.which("paru"):
            helper = "paru"
        else:
            self.pkg_descriptions[cache_key] = "<not found>"
            return None

        # backoff parameters
        retries = 2
        delay = 1

        attempt = 0
        while attempt < retries:
            attempt += 1
            try:
                result = subprocess.run(
                    [helper, "-Si", pkg_name],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=6
                )
                if result.returncode == 0 and result.stdout.strip():
                    desc = self._parse_desc_from_qi_or_si(result.stdout)
                    if desc:
                        self.pkg_descriptions[cache_key] = desc
                        return desc
                    break  # found nothing, no need to retry
                else:
                    # network or other error, backoff
                    time.sleep(delay)
                    delay *= 2
            except subprocess.TimeoutExpired:
                time.sleep(delay)
                delay *= 2
            except Exception:
                break

        # negative cache
        self.pkg_descriptions[cache_key] = "<not found>"
        return None

    # -----------------------------
    # FLATPAK SEARCH
    # -----------------------------
    def _flatpak_installed_ids(self):
        """Return set of installed flatpak app IDs (raw)."""
        out = self._run_cmd(["flatpak", "list", "--app", "--columns=application"])
        if not out:
            return set()
        return {x.strip() for x in out.splitlines() if x.strip()}

    # -----------------------------
    # FLATPAK SEARCH with negative caching
    # -----------------------------
    def _search_flatpak(self, name):
        cache_key = f"flatpak:{name}"
        if cache_key in self.pkg_descriptions:
            if self.pkg_descriptions[cache_key] == "<not found>":
                return None
            return self.pkg_descriptions[cache_key]

        if not shutil.which("flatpak"):
            self.pkg_descriptions[cache_key] = "<not found>"
            return None

        target = name.lower()
        installed_ids = self._flatpak_installed_ids()
        for appid in installed_ids:
            appid_l = appid.lower()
            last = appid_l.split(".")[-1]
            if appid_l == target or last == target:
                out = self._run_cmd(["flatpak", "info", appid], timeout=3)
                desc = self._parse_desc_from_qi_or_si(out)
                if desc:
                    self.pkg_descriptions[cache_key] = desc
                    return desc
                break

        out = self._run_cmd(["flatpak", "search", "--columns=name,application,description", name], timeout=5)
        if out:
            for line in out.splitlines():
                line = line.strip()
                if not line or ("Name" in line and "Application ID" in line):
                    continue
                cols = [c.strip() for c in line.split("\t")]
                if len(cols) < 2:
                    continue
                nm, appid = cols[0], cols[1]
                desc = cols[2] if len(cols) > 2 else ""
                nm_l = nm.lower()
                app_last = appid.lower().split(".")[-1] if appid else ""
                if nm_l == target or app_last == target or (appid and appid.lower() == target):
                    self.pkg_descriptions[cache_key] = desc or nm
                    return desc or nm
            # fallback substring match
            for line in out.splitlines():
                cols = [c.strip() for c in line.split("\t")]
                if len(cols) >= 2:
                    nm, appid = cols[0].lower(), cols[1].lower()
                    if target in nm or target in appid:
                        self.pkg_descriptions[cache_key] = cols[2] if len(cols) > 2 else cols[0]
                        return self.pkg_descriptions[cache_key]

        # negative cache
        self.pkg_descriptions[cache_key] = "<not found>"
        return None

    # -----------------------------
    # Build a small, sane set of candidates from a folder path:
    # - basename
    # - child after .config or .local/share
    # - strip leading dot
    # - alias map (raw basename)
    # - normalize: lowercase + spaces → dashes  (underscores kept!)
    # -----------------------------
    def _derive_name_candidates(self, folder_path):

        rel = os.path.relpath(folder_path, HOME) if folder_path.startswith(HOME) else folder_path
        parts = [p for p in rel.split(os.sep) if p]

        base = os.path.basename(folder_path)
        cand = set()

        # child after .config or .local/share
        for i, p in enumerate(parts):
            if p == ".config" and i + 1 < len(parts):
                cand.add(parts[i+1])
            if p == ".local" and i + 2 < len(parts) and parts[i+1] == "share":
                cand.add(parts[i+2])

        # always include basename
        cand.add(base)

        # strip leading dot
        if base.startswith("."):
            cand.add(base.lstrip("."))

        # alias mapping (raw basename key)
        if base in ALIAS_MAP:
            cand.add(ALIAS_MAP[base])

        # normalize: lowercase + spaces→dashes (keep underscores!)
        norm = set()
        for c in cand:
            n = c.strip().lower().replace(" ", "-")
            if len(n) >= 2:
                norm.add(n)

        # stable order (shorter first tends to be more “package-like”)
        return sorted(norm, key=len)

    # -----------------------------
    # Load description for selected folder
    # -----------------------------
    def load_description(self):
        """Kick off background description lookup for the selected folder."""
        threading.Thread(target=self._load_description_thread, daemon=True).start()

    def _update_label(self, text):
        """Thread-safe label update."""
        self.desc_label.after(0, lambda: self.desc_label.config(text=text))

    def _load_description_thread(self):
        # get selection
        sel = self.folder_tree.selection()
        if not sel:
            self._update_label("Select a folder first")
            return

        item = self.folder_tree.item(sel[0])
        folder_path = item.get("text") or (item.get("values")[0] if item.get("values") else "")
        if not folder_path:
            self._update_label("Could not read selected folder")
            return

        self._update_label("Loading description...")

        # candidates (conservative)
        candidates = self._derive_name_candidates(folder_path)

        best_desc = None
        best_name = None
        best_source = "any"

        for cand in candidates:
            # Try each source in order: pacman → AUR → flatpak
            for source, search_func in [
                ("pacman", self._search_pacman),
                ("aur", self._search_aur),
                ("flatpak", self._search_flatpak)
            ]:
                cache_key = f"{source}:{cand}"
                cached = self.pkg_descriptions.get(cache_key)

                if cached and cached != "<not found>":
                    best_desc, best_name, best_source = cached, cand, source
                    break  # got a positive cached result

                # Not cached or cached miss → search
                self._update_label(f"Searching {source.upper()} for {cand}...")
                desc = search_func(cand)

                if desc:
                    best_desc, best_name, best_source = desc, cand, source
                    self.pkg_descriptions[cache_key] = desc  # cache positive result
                    break
                else:
                    # cache negative result for backoff purposes
                    self.pkg_descriptions[cache_key] = "<not found>"

            if best_desc:
                break  # stop after first positive result

        if not best_desc:
            best_name = candidates[0] if candidates else "(unknown)"
            best_desc = "Description not found"
            best_source = "any"
            # Cache negative results for "any" key
            cache_key = f"{best_source}:{best_name}"
            self.pkg_descriptions[cache_key] = best_desc

        # save cache to disk
        try:
            with open(self.cache_file, "w") as f:
                json.dump(self.pkg_descriptions, f, indent=2)
        except Exception:
            pass

        self._update_label(f"{best_name}: {best_desc}")

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

    # Move selected folder from and to category.
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
    
    # Write kept folders to file.
    def save_kept_folders(self):
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
