#!/usr/bin/env python3
__version__ = "2.0.0"
##
#     Project: OrphyCleaner GUI - Orphaned Config Folder Cleaner
# Description: Scans your home directory for orphaned config folders
#      Author: Jozef Gaal (dodog)
#     License: AGPL-3+
#         Web: https://github.com/dodog/orphycleaner
#
# Scans your home directory for config folders that may belong to uninstalled or unused applications.
# Matches against installed packages (pacman), Flatpak apps, desktop files, AppImages, and executables.
# Categorizes folders as Installed, Maybe Installed, or Orphaned.
#
# WARNING: Not 100% guaranteed - backup and verify before deleting folders.
#
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
import threading

# -------------------------------
# Basic environment checks
# -------------------------------

if sys.version_info < (3, 9):
    print("Error: OrphyCleaner requires Python 3.9 or newer.")
    sys.exit(1)

if "Linux" not in platform.system():
    print("Warning: This application was designed for Linux (Manjaro/Arch).")
    print("It may not work correctly on your system.\n")

try:
    import gi
    gi.require_version("Gtk", "4.0")
    gi.require_version("Adw", "1")
    from gi.repository import Gtk, Adw, GLib, Gio, GObject, Gdk
except (ModuleNotFoundError, ImportError, ValueError):
    print("Error: GTK4 / libadwaita (PyGObject) is not installed or configured on your system.")
    print("On Manjaro/Arch, install it with:")
    print("    sudo pacman -S python-gobject gtk4 libadwaita")
    sys.exit(1)

# =========================================================
# CONFIGURATION
# =========================================================
HOME = os.path.expanduser("~")
APP_ID = "sk.mayday.OrphyCleaner"

CACHE_FILE    = os.path.join(HOME, ".cache", "orphycleaner", "orphycleaner_pkg_cache.json")
KEPT_FILE     = os.path.join(HOME, ".local", "share", "orphycleaner", "kept_folders.txt")
SETTINGS_FILE = os.path.join(HOME, ".local", "share", "orphycleaner", "settings.json")

SUBPROCESS_ENV = os.environ.copy()
SUBPROCESS_ENV["LANG"] = "C"
SUBPROCESS_ENV["LC_ALL"] = "C"

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
    f"{HOME}/.config/autostart",
]

ALIAS_MAP = {
    ".audacity-data": "audacity",
    ".SynologyDrive": "synology-drive",
    "Code - OSS": "code-oss",
    ".eID_klient": "eidklient",
    ".mozilla": "mozilla",
}

# Category labels mapped to GTK4/libadwaita's built-in semantic CSS
# classes instead of hardcoded hex colors. These automatically switch
# with the system light/dark theme (Adwaita / Adwaita-dark).
CATEGORY_STYLES = {
    "Installed (package match)": "success",
    "Installed (executable found)": "success",
    "Installed (Flatpak)": "success",
    "Installed (desktop file match)": "success",
    "Installed (AppImage)": "success",
    "Maybe Installed (partial package match)": "warning",
    "Orphaned": "error",
    "Kept": "accent",
}
CATEGORY_ICONS = {
    "Installed (package match)": "package-x-generic-symbolic",
    "Installed (executable found)": "system-run-symbolic",
    "Installed (Flatpak)": "application-x-addon-symbolic",
    "Installed (desktop file match)": "application-x-executable-symbolic",
    "Installed (AppImage)": "drive-removable-media-symbolic",
    "Maybe Installed (partial package match)": "dialog-question-symbolic",
    "Orphaned": "user-trash-symbolic",
    "Kept": "starred-symbolic",
}
CATEGORY_ORDER = list(CATEGORY_STYLES.keys())


# =========================================================
# HELPER FUNCTIONS (unchanged from the Tkinter version - pure logic,
# no GUI toolkit dependency)
# =========================================================
def normalize(name):
    return name.lower().replace(' ', '-').replace('_', '-').replace('.', '-')


def is_ignored(folder):
    return any(folder == ignored or folder.startswith(ignored + "/") for ignored in IGNORED_FOLDERS)


def get_installed_packages():
    try:
        result = subprocess.run(["pacman", "-Qq"], stdout=subprocess.PIPE, text=True, check=True, env=SUBPROCESS_ENV)
        return {normalize(pkg) for pkg in result.stdout.splitlines()}
    except (subprocess.CalledProcessError, FileNotFoundError):
        return set()


_flatpak_raw_cache = None


def get_flatpak_ids_raw():
    global _flatpak_raw_cache
    if _flatpak_raw_cache is not None:
        return _flatpak_raw_cache
    try:
        result = subprocess.run(
            ["flatpak", "list", "--app", "--columns=application"],
            stdout=subprocess.PIPE, text=True, check=True, env=SUBPROCESS_ENV
        )
        _flatpak_raw_cache = {x.strip() for x in result.stdout.splitlines() if x.strip()}
    except (FileNotFoundError, subprocess.CalledProcessError):
        _flatpak_raw_cache = set()
    return _flatpak_raw_cache


def get_flatpaks():
    return {normalize(app) for app in get_flatpak_ids_raw()}


def get_folder_size(path):
    total = 0
    for dirpath, dirnames, filenames in os.walk(path, onerror=lambda e: None):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            try:
                if not os.path.islink(fp):
                    total += os.path.getsize(fp)
            except OSError:
                pass
    return total


def format_size(num_bytes):
    size = float(num_bytes)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def get_appimages():
    appimage_dir = os.path.join(HOME, "Applications")
    apps = set()
    if os.path.isdir(appimage_dir):
        for f in os.listdir(appimage_dir):
            if f.lower().endswith(".appimage"):
                apps.add(normalize(os.path.splitext(f)[0]))
    return apps


def get_installed_commands():
    cmds = set()
    for path in os.environ.get("PATH", "").split(os.pathsep):
        if os.path.isdir(path):
            cmds.update(os.listdir(path))
    return cmds


def get_desktop_apps():
    apps = set()
    desktop_dir = "/usr/share/applications"
    if os.path.isdir(desktop_dir):
        for f in os.listdir(desktop_dir):
            if f.endswith(".desktop"):
                apps.add(normalize(os.path.splitext(f)[0]))
    return apps


def get_aur_packages():
    try:
        result = subprocess.run(["yay", "-Qq"], stdout=subprocess.PIPE, text=True, check=True, env=SUBPROCESS_ENV)
        return {normalize(pkg) for pkg in result.stdout.splitlines()}
    except (FileNotFoundError, subprocess.CalledProcessError):
        return set()


def prepare_folders():
    folders = []
    config_path = os.path.join(HOME, ".config")
    if os.path.isdir(config_path):
        folders.extend(os.path.join(config_path, f) for f in os.listdir(config_path))

    local_share = os.path.join(HOME, ".local", "share")
    if os.path.isdir(local_share):
        folders.extend(os.path.join(local_share, f) for f in os.listdir(local_share))

    for f in os.listdir(HOME):
        full_path = os.path.join(HOME, f)
        if f.startswith('.') and os.path.isdir(full_path) and f not in ['.config', '.local']:
            folders.append(full_path)

    return [f for f in folders if os.path.isdir(f) and not is_ignored(f)]


# =========================================================
# DATA MODEL
# =========================================================
class FolderItem(GObject.Object):
    """Wraps a single folder path plus its lazily-computed size."""
    __gtype_name__ = "FolderItem"

    def __init__(self, path):
        super().__init__()
        self.path = path
        self.size = None  # None until computed in the background

    @property
    def size_text(self):
        return format_size(self.size) if self.size is not None else "calculating\u2026"


class FolderRow(Adw.ActionRow):
    """An Adw.ActionRow that remembers which FolderItem it represents."""
    def __init__(self, item: FolderItem):
        super().__init__()
        self.item = item
        self.set_title(GLib.markup_escape_text(item.path))
        self.set_subtitle(item.size_text)
        self.set_title_lines(1)
        self.set_subtitle_lines(1)

    def refresh(self):
        self.set_subtitle(self.item.size_text)


# =========================================================
# MAIN APPLICATION WINDOW
# =========================================================
class OrphyCleanerWindow(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="OrphyCleaner")

        self.settings = self._load_settings()
        w = self.settings.get("width", 1400)
        h = self.settings.get("height", 830)
        self.set_default_size(w, h)
        self.connect("close-request", self._on_close_request)

        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        os.makedirs(os.path.dirname(KEPT_FILE), exist_ok=True)

        self.cache_file = CACHE_FILE
        try:
            if os.path.exists(self.cache_file) and os.path.getsize(self.cache_file) > 0:
                with open(self.cache_file, "r") as f:
                    self.pkg_descriptions = json.load(f)
            else:
                self.pkg_descriptions = {}
        except Exception:
            self.pkg_descriptions = {}

        self.aur_last_query = {}
        self.aur_backoff_base = 10
        self.aur_backoff_max = 300

        self.results = {cat: [] for cat in CATEGORY_STYLES.keys()}
        self.current_category = None
        self.kept_file = KEPT_FILE

        self.folder_items = {}          # path -> FolderItem (shared across categories)
        self.category_rows = {}         # category -> sidebar Adw.ActionRow
        self.category_count_labels = {}  # category -> count Gtk.Label
        self.folder_row_by_path = {}    # path -> FolderRow currently shown in the list
        self.sizing_in_progress = set()
        self._switching_category = False

        self._build_actions()
        self._build_ui()

        self.folders_to_scan = prepare_folders()
        threading.Thread(target=self._load_system_data_thread, daemon=True).start()

    # =========================================================
    # SETTINGS
    # =========================================================
    def _load_settings(self):
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r") as f:
                    return json.load(f)
        except Exception:
            pass
        return {}

    def _save_settings(self):
        try:
            os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
            self.settings["width"] = self.get_width()
            self.settings["height"] = self.get_height()
            with open(SETTINGS_FILE, "w") as f:
                json.dump(self.settings, f, indent=2)
        except Exception:
            pass

    def _on_close_request(self, *args):
        self._save_settings()
        return False  # allow the window to close

    # =========================================================
    # ACTIONS (win.*) - drives menu, context menu and keyboard shortcuts
    # =========================================================
    def _build_actions(self):
        def add(name, callback):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", lambda a, p: callback())
            self.add_action(action)

        add("open-folder", self.open_folder)
        add("load-description", self.load_description)
        add("keep-folder", self.keep_folder)
        add("unkeep-folder", self.unkeep_folder)
        add("delete-folder", self.delete_folder)
        add("export-list", self.export_orphaned_list)
        add("focus-search", lambda: self.search_entry.grab_focus())
        add("open-help", self.open_help)
        add("show-about", self.show_about)

        app = self.get_application()
        app.set_accels_for_action("win.delete-folder", ["Delete"])
        app.set_accels_for_action("win.open-folder", ["Return"])
        app.set_accels_for_action("win.focus-search", ["<Control>f"])

    # =========================================================
    # UI CONSTRUCTION
    # =========================================================
    def _build_ui(self):
        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        title_widget = Adw.WindowTitle(title="OrphyCleaner", subtitle=f"v{__version__}")
        header.set_title_widget(title_widget)

        menu_model = Gio.Menu()
        menu_model.append("Help", "win.open-help")
        menu_model.append("About OrphyCleaner", "win.show-about")
        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic", tooltip_text="Main Menu")
        menu_button.set_menu_model(menu_model)
        header.pack_end(menu_button)

        toolbar_view.add_top_bar(header)

        self.toast_overlay = Adw.ToastOverlay()

        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.stack.add_named(self._build_scan_page(), "scanning")
        self.stack.add_named(self._build_main_page(), "main")
        self.stack.set_visible_child_name("scanning")

        self.toast_overlay.set_child(self.stack)
        toolbar_view.set_content(self.toast_overlay)
        self.set_content(toolbar_view)

    def _build_scan_page(self):
        status = Adw.StatusPage()
        status.set_title("Scanning your home folder\u2026")
        status.set_icon_name("folder-symbolic")

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_halign(Gtk.Align.CENTER)
        box.set_size_request(420, -1)

        self.scan_progress_bar = Gtk.ProgressBar()
        self.scan_status_label = Gtk.Label(label="Loading installed package data\u2026")
        self.scan_status_label.add_css_class("dim-label")
        self.scan_status_label.set_wrap(True)
        self.scan_status_label.set_justify(Gtk.Justification.CENTER)

        box.append(self.scan_progress_bar)
        box.append(self.scan_status_label)
        status.set_child(box)
        return status

    def _build_main_page(self):
        root = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)

        root.append(self._build_sidebar())
        root.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        root.append(self._build_folder_panel())
        root.append(Gtk.Separator(orientation=Gtk.Orientation.VERTICAL))
        root.append(self._build_action_panel())
        return root

    def _build_sidebar(self):
        outer = Gtk.ScrolledWindow()
        outer.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        outer.set_size_request(340, -1)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)

        cat_label = Gtk.Label(label="Categories")
        cat_label.add_css_class("heading")
        cat_label.set_xalign(0)
        box.append(cat_label)

        self.category_list = Gtk.ListBox()
        self.category_list.add_css_class("boxed-list")
        self.category_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        for cat in CATEGORY_ORDER:
            row = Adw.ActionRow(title=cat)
            icon = Gtk.Image.new_from_icon_name(CATEGORY_ICONS[cat])
            icon.add_css_class(CATEGORY_STYLES[cat])
            row.add_prefix(icon)
            count_label = Gtk.Label(label="0")
            count_label.add_css_class("numeric")
            count_label.add_css_class(CATEGORY_STYLES[cat])
            row.add_suffix(count_label)
            row.category = cat
            self.category_list.append(row)
            self.category_rows[cat] = row
            self.category_count_labels[cat] = count_label
        self.category_list.connect(
            "row-selected",
            lambda lb, row: self.show_category(row.category) if row is not None else None,
        )
        box.append(self.category_list)

        info_group = Adw.PreferencesGroup(title="How to use")
        info_row = Adw.ActionRow()
        info_label = Gtk.Label(
            label=(
                "1. Select a category to see folders.\n"
                "2. Only \u2018Orphaned\u2019 folders can be deleted.\n"
                "3. Use Keep/Unkeep to mark important folders."
            )
        )
        info_label.set_wrap(True)
        info_label.set_xalign(0)
        info_label.set_margin_top(6)
        info_label.set_margin_bottom(6)
        info_row.set_child(info_label)
        info_group.add(info_row)
        box.append(info_group)

        warning_group = Adw.PreferencesGroup()
        warning_row = Adw.ActionRow()
        warning_title = Gtk.Label(label="\u26a0 WARNING")
        warning_title.add_css_class("heading")
        warning_title.add_css_class("error")
        warning_title.set_xalign(0)
        warning_body = Gtk.Label(
            label=(
                "\u2022 Deleting folders is permanent if Trash is unavailable.\n"
                "\u2022 Double-check and backup before deleting anything.\n"
                "\u2022 This application is not 100% accurate."
            )
        )
        warning_body.set_wrap(True)
        warning_body.set_xalign(0)
        warning_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        warning_box.set_margin_top(6)
        warning_box.set_margin_bottom(6)
        warning_box.append(warning_title)
        warning_box.append(warning_body)
        warning_row.set_child(warning_box)
        warning_group.add(warning_row)
        box.append(warning_group)

        outer.set_child(box)
        return outer

    def _build_folder_panel(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_hexpand(True)

        search_bar_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        search_bar_box.set_margin_top(8)
        search_bar_box.set_margin_bottom(8)
        search_bar_box.set_margin_start(8)
        search_bar_box.set_margin_end(8)
        self.search_entry = Gtk.SearchEntry(placeholder_text="Filter folders\u2026")
        self.search_entry.set_hexpand(True)
        self.search_entry.connect("search-changed", lambda e: self.show_category(self.current_category))
        search_bar_box.append(self.search_entry)
        box.append(search_bar_box)

        scroller = Gtk.ScrolledWindow()
        scroller.set_vexpand(True)
        scroller.set_hexpand(True)

        self.folder_list = Gtk.ListBox()
        self.folder_list.add_css_class("boxed-list")
        self.folder_list.set_margin_start(8)
        self.folder_list.set_margin_end(8)
        self.folder_list.set_margin_bottom(8)
        self.folder_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.folder_list.connect("row-selected", self._on_folder_selected)
        self.folder_list.connect("row-activated", lambda lb, row: self.open_folder())

        gesture = Gtk.GestureClick(button=3)
        gesture.connect("pressed", self._on_folder_right_click)
        self.folder_list.add_controller(gesture)

        scroller.set_child(self.folder_list)
        box.append(scroller)
        return box

    def _build_action_panel(self):
        outer = Gtk.ScrolledWindow()
        outer.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        outer.set_size_request(230, -1)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(12)
        box.set_margin_bottom(12)
        box.set_margin_start(12)
        box.set_margin_end(12)

        self.keep_button = Gtk.Button(label="Keep")
        self.keep_button.add_css_class("suggested-action")
        self.keep_button.connect("clicked", lambda b: self.keep_folder())
        box.append(self.keep_button)

        self.load_desc_button = Gtk.Button(label="Load Description")
        self.load_desc_button.connect("clicked", lambda b: self.load_description())
        box.append(self.load_desc_button)

        self.open_button = Gtk.Button(label="Open Folder")
        self.open_button.connect("clicked", lambda b: self.open_folder())
        box.append(self.open_button)

        self.delete_button = Gtk.Button(label="Delete")
        self.delete_button.add_css_class("destructive-action")
        self.delete_button.connect("clicked", lambda b: self.delete_folder())
        box.append(self.delete_button)

        self.export_button = Gtk.Button(label="Export List")
        self.export_button.connect("clicked", lambda b: self.export_orphaned_list())
        box.append(self.export_button)

        box.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        self.desc_label = Gtk.Label(label="")
        self.desc_label.set_wrap(True)
        self.desc_label.set_xalign(0)
        self.desc_label.set_yalign(0)
        self.desc_label.add_css_class("dim-label")
        self.desc_label.add_css_class("caption")
        box.append(self.desc_label)

        outer.set_child(box)
        return outer

    # =========================================================
    # BACKGROUND STARTUP
    # =========================================================
    def _load_system_data_thread(self):
        installed_pkgs = get_installed_packages()
        installed_aur = get_aur_packages()
        installed_flatpaks = get_flatpaks()
        installed_cmds = get_installed_commands()
        desktop_apps = get_desktop_apps()
        appimages = get_appimages()

        def apply():
            self.installed_pkgs = installed_pkgs
            self.installed_aur = installed_aur
            self.installed_flatpaks = installed_flatpaks
            self.installed_cmds = installed_cmds
            self.desktop_apps = desktop_apps
            self.appimages = appimages

            self.load_kept_folders()
            self.scan_status_label.set_label("Scanning folders\u2026")
            threading.Thread(target=self._scan_thread, daemon=True).start()
            return False

        GLib.idle_add(apply)

    # =========================================================
    # SCANNING LOGIC
    # =========================================================
    def load_kept_folders(self):
        if os.path.exists(self.kept_file):
            with open(self.kept_file, "r") as f:
                for line in f:
                    path = line.strip()
                    if os.path.isdir(path):
                        self.results["Kept"].append(path)

    def _classify(self, folder):
        base = os.path.basename(folder)
        name = ALIAS_MAP.get(base, normalize(base.lstrip('.')))

        if name in self.installed_pkgs:
            return "Installed (package match)"
        elif name in self.installed_cmds:
            return "Installed (executable found)"
        elif any(name in app for app in self.installed_flatpaks):
            return "Installed (Flatpak)"
        elif any(name in app for app in self.desktop_apps):
            return "Installed (desktop file match)"
        elif any(name in app for app in self.appimages):
            return "Installed (AppImage)"
        elif any(name in pkg for pkg in self.installed_pkgs):
            return "Maybe Installed (partial package match)"
        else:
            return "Orphaned"

    def _scan_thread(self):
        total = len(self.folders_to_scan)
        kept_set = set(self.results["Kept"])
        for i, folder in enumerate(self.folders_to_scan):
            if folder not in kept_set:
                cat = self._classify(folder)
                self.results[cat].append(folder)
            GLib.idle_add(self._update_scan_progress, i + 1, total, folder)
        GLib.idle_add(self._on_scan_complete)

    def _update_scan_progress(self, done, total, folder):
        frac = done / total if total else 1.0
        self.scan_progress_bar.set_fraction(frac)
        self.scan_status_label.set_label(f"Scanning ({done}/{total})\u2026\n{folder}")
        return False

    def _on_scan_complete(self):
        for cat in CATEGORY_ORDER:
            self._refresh_category_count(cat)
        self.stack.set_visible_child_name("main")
        self.show_category("Orphaned")
        return False

    # =========================================================
    # CATEGORY HANDLING
    # =========================================================
    def _refresh_category_count(self, cat):
        count = len(self.results.get(cat, []))
        label = str(count)
        if cat == "Orphaned" and count:
            total = sum((self.folder_items[f].size or 0) for f in self.results.get(cat, []) if f in self.folder_items)
            if total:
                label = f"{count} \u2014 {format_size(total)}"
        self.category_count_labels[cat].set_label(label)

    def show_category(self, category):
        if category is None or self._switching_category:
            return
        self._switching_category = True
        try:
            self._show_category_impl(category)
        finally:
            self._switching_category = False

    def _show_category_impl(self, category):
        self.current_category = category

        child = self.folder_list.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.folder_list.remove(child)
            child = nxt
        self.folder_row_by_path = {}

        target_row = self.category_rows.get(category)
        if target_row is not None and self.category_list.get_selected_row() is not target_row:
            self.category_list.select_row(target_row)

        query = self.search_entry.get_text().strip().lower()
        folders = self.results.get(category, [])
        if query:
            folders = [f for f in folders if query in f.lower()]

        for path in folders:
            item = self.folder_items.get(path)
            if item is None:
                item = FolderItem(path)
                self.folder_items[path] = item
            row = FolderRow(item)
            self.folder_list.append(row)
            self.folder_row_by_path[path] = row

        if category == "Orphaned":
            self.keep_button.set_label("Keep")
            self.keep_button.set_sensitive(True)
            self.delete_button.set_sensitive(True)
        elif category == "Kept":
            self.keep_button.set_label("Unkeep")
            self.keep_button.set_sensitive(True)
            self.delete_button.set_sensitive(False)
        else:
            self.keep_button.set_sensitive(False)
            self.delete_button.set_sensitive(False)

        missing = [f for f in folders if f not in self.sizing_in_progress and
                   (f not in self.folder_items or self.folder_items[f].size is None)]
        if missing:
            self.sizing_in_progress.update(missing)
            threading.Thread(target=self._compute_sizes_thread, args=(category, missing), daemon=True).start()

    def _compute_sizes_thread(self, category, folders):
        for folder in folders:
            size = get_folder_size(folder)
            self.sizing_in_progress.discard(folder)
            GLib.idle_add(self._on_size_computed, folder, size, category)

    def _on_size_computed(self, folder, size, category):
        item = self.folder_items.get(folder)
        if item is None:
            item = FolderItem(folder)
            self.folder_items[folder] = item
        item.size = size
        row = self.folder_row_by_path.get(folder)
        if self.current_category == category and row is not None:
            row.refresh()
        self._refresh_category_count(category)
        return False

    def _on_folder_selected(self, listbox, row):
        pass  # selection tracked via listbox.get_selected_row() when needed

    def _listbox_rows(self, listbox):
        rows = []
        child = listbox.get_first_child()
        while child is not None:
            rows.append(child)
            child = child.get_next_sibling()
        return rows

    def _selected_item(self):
        row = self.folder_list.get_selected_row()
        return row.item if row is not None else None

    def _on_folder_right_click(self, gesture, n_press, x, y):
        row = self.folder_list.get_row_at_y(int(y))
        if row is None:
            return
        self.folder_list.select_row(row)

        menu = Gio.Menu()
        menu.append("Open Folder", "win.open-folder")
        menu.append("Load Description", "win.load-description")
        if self.current_category == "Orphaned":
            menu.append("Keep", "win.keep-folder")
        elif self.current_category == "Kept":
            menu.append("Unkeep", "win.unkeep-folder")
        if self.current_category == "Orphaned":
            menu.append("Delete", "win.delete-folder")

        popover = Gtk.PopoverMenu.new_from_model(menu)
        popover.set_parent(self.folder_list)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        popover.set_pointing_to(rect)
        popover.popup()

    # =========================================================
    # DESCRIPTION HANDLER (subprocess logic unchanged from the
    # Tkinter version; only the thread -> UI hand-off changed)
    # =========================================================
    def _run_cmd(self, cmd, timeout=5):
        try:
            result = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                text=True, timeout=timeout, env=SUBPROCESS_ENV
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            return ""
        except Exception:
            return ""

    def _parse_desc_from_qi_or_si(self, text):
        if not text:
            return None
        for line in text.splitlines():
            if ":" in line:
                label, val = line.split(":", 1)
                lab = label.strip().lower()
                if "description" in lab or "popis" in lab:
                    return val.strip()
        return None

    def _parse_desc_from_ss(self, text, wanted_name):
        if not text:
            return None
        lines = text.splitlines()
        wanted_name = wanted_name.strip().lower()
        for i, line in enumerate(lines):
            line = line.strip("\n")
            if not line or line.startswith("==>") or "matches found" in line.lower():
                continue
            if re.search(r"/" + re.escape(wanted_name) + r"\b", line.lower()):
                if i + 1 < len(lines):
                    nxt = lines[i + 1]
                    if nxt.startswith("    ") or nxt.startswith("\t"):
                        return nxt.strip()
        for line in lines:
            if line.startswith("    ") or line.startswith("\t"):
                val = line.strip()
                if val and "matches found" not in val.lower():
                    return val
        return None

    def _search_pacman(self, name):
        out = self._run_cmd(["pacman", "-Qi", name], timeout=2)
        desc = self._parse_desc_from_qi_or_si(out)
        if desc:
            return desc
        out = self._run_cmd(["pacman", "-Si", name], timeout=8)
        desc = self._parse_desc_from_qi_or_si(out)
        if desc:
            return desc
        out = self._run_cmd(["pacman", "-Ss", f"^{name}$"], timeout=8)
        desc = self._parse_desc_from_ss(out, name)
        if desc:
            return desc
        return None

    def _search_aur(self, pkg_name):
        cache_key = f"aur:{pkg_name}"
        if cache_key in self.pkg_descriptions:
            if self.pkg_descriptions[cache_key] == "<not found>":
                return None
            return self.pkg_descriptions[cache_key]

        now = time.time()
        last_attempt, backoff = self.aur_last_query.get(pkg_name, (0, self.aur_backoff_base))
        if now - last_attempt < backoff:
            return None

        if shutil.which("yay"):
            helper = "yay"
        elif shutil.which("paru"):
            helper = "paru"
        else:
            self.pkg_descriptions[cache_key] = "<not found>"
            return None

        retries = 2
        delay = 1
        attempt = 0
        while attempt < retries:
            attempt += 1
            try:
                result = subprocess.run(
                    [helper, "-Si", pkg_name], capture_output=True, text=True,
                    check=False, timeout=6, env=SUBPROCESS_ENV
                )
                if result.returncode == 0 and result.stdout.strip():
                    desc = self._parse_desc_from_qi_or_si(result.stdout)
                    if desc:
                        self.pkg_descriptions[cache_key] = desc
                        self.aur_last_query.pop(pkg_name, None)
                        return desc
                    break
                else:
                    time.sleep(delay)
                    delay *= 2
            except subprocess.TimeoutExpired:
                time.sleep(delay)
                delay *= 2
            except Exception:
                break

        next_backoff = min(backoff * 2, self.aur_backoff_max)
        self.aur_last_query[pkg_name] = (time.time(), next_backoff)
        self.pkg_descriptions[cache_key] = "<not found>"
        return None

    def _flatpak_installed_ids(self):
        return get_flatpak_ids_raw()

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
            for line in out.splitlines():
                cols = [c.strip() for c in line.split("\t")]
                if len(cols) >= 2:
                    nm, appid = cols[0].lower(), cols[1].lower()
                    if target in nm or target in appid:
                        self.pkg_descriptions[cache_key] = cols[2] if len(cols) > 2 else cols[0]
                        return self.pkg_descriptions[cache_key]

        self.pkg_descriptions[cache_key] = "<not found>"
        return None

    def _derive_name_candidates(self, folder_path):
        rel = os.path.relpath(folder_path, HOME) if folder_path.startswith(HOME) else folder_path
        parts = [p for p in rel.split(os.sep) if p]
        base = os.path.basename(folder_path)
        cand = set()

        for i, p in enumerate(parts):
            if p == ".config" and i + 1 < len(parts):
                cand.add(parts[i + 1])
            if p == ".local" and i + 2 < len(parts) and parts[i + 1] == "share":
                cand.add(parts[i + 2])

        cand.add(base)
        if base.startswith("."):
            cand.add(base.lstrip("."))
        if base in ALIAS_MAP:
            cand.add(ALIAS_MAP[base])

        norm = set()
        for c in cand:
            n = c.strip().lower().replace(" ", "-")
            if len(n) >= 2:
                norm.add(n)
        return sorted(norm, key=len)

    def load_description(self):
        threading.Thread(target=self._load_description_thread, daemon=True).start()

    def _update_desc_label(self, text):
        self.desc_label.set_label(text)
        return False

    def _load_description_thread(self):
        item = self._selected_item()
        if item is None:
            GLib.idle_add(self._update_desc_label, "Select a folder first")
            return
        folder_path = item.path

        GLib.idle_add(self._update_desc_label, "Loading description\u2026")

        candidates = self._derive_name_candidates(folder_path)
        best_desc = None
        best_name = None

        for cand in candidates:
            for source, search_func in [
                ("pacman", self._search_pacman),
                ("aur", self._search_aur),
                ("flatpak", self._search_flatpak),
            ]:
                cache_key = f"{source}:{cand}"
                cached = self.pkg_descriptions.get(cache_key)
                if cached and cached != "<not found>":
                    best_desc, best_name = cached, cand
                    break

                GLib.idle_add(self._update_desc_label, f"Searching {source.upper()} for {cand}\u2026")
                desc = search_func(cand)
                if desc:
                    best_desc, best_name = desc, cand
                    self.pkg_descriptions[cache_key] = desc
                    break
                else:
                    self.pkg_descriptions[cache_key] = "<not found>"

            if best_desc:
                break

        if not best_desc:
            best_name = candidates[0] if candidates else "(unknown)"
            best_desc = "Description not found"
            self.pkg_descriptions[f"any:{best_name}"] = best_desc

        try:
            with open(self.cache_file, "w") as f:
                json.dump(self.pkg_descriptions, f, indent=2)
        except Exception:
            pass

        GLib.idle_add(self._update_desc_label, f"{best_name}: {best_desc}")

    # =========================================================
    # ACTION HANDLERS
    # =========================================================
    def _toast(self, text):
        self.toast_overlay.add_toast(Adw.Toast(title=text, timeout=4))

    def move_folder_between_categories(self, src_category, dst_category):
        if self.current_category != src_category:
            return None
        item = self._selected_item()
        if item is None:
            return None
        folder = item.path
        if folder not in self.results.get(src_category, []):
            return None

        prev_index = self._listbox_rows(self.folder_list).index(self.folder_list.get_selected_row())

        self.results[src_category].remove(folder)
        self.results.setdefault(dst_category, []).append(folder)
        self.show_category(src_category)
        self._refresh_category_count(dst_category)
        self._select_row_near_index(prev_index)
        return folder

    def _select_row_near_index(self, index):
        rows = self._listbox_rows(self.folder_list)
        if not rows:
            return
        target = rows[min(index, len(rows) - 1)]
        self.folder_list.select_row(target)

    def keep_folder(self):
        folder = self.move_folder_between_categories("Orphaned", "Kept")
        if folder:
            self.save_kept_folders()
            self._toast(f"Kept {os.path.basename(folder)}")

    def unkeep_folder(self):
        folder = self.move_folder_between_categories("Kept", "Orphaned")
        if folder:
            self.save_kept_folders()
            self._toast(f"Unkept {os.path.basename(folder)}")

    def save_kept_folders(self):
        with open(self.kept_file, "w") as f:
            for fpath in self.results["Kept"]:
                f.write(fpath + "\n")

    def open_folder(self):
        item = self._selected_item()
        if item is None:
            return
        if not shutil.which("xdg-open"):
            self._toast("xdg-open was not found on this system.")
            return
        try:
            subprocess.Popen(["xdg-open", item.path])
        except Exception as e:
            self._toast(f"Could not open folder: {e}")

    def open_help(self):
        # Gtk.UriLauncher passes a proper activation token to the compositor
        # (the same mechanism Adw.AboutWindow's links use), so the browser
        # window is raised and focused instead of opening in the background.
        launcher = Gtk.UriLauncher(uri="https://orphycleaner.mayday.sk/#help")
        launcher.launch(self, None, self._on_uri_launched)

    def _on_uri_launched(self, launcher, result):
        try:
            launcher.launch_finish(result)
        except GLib.Error as e:
            self._toast(f"Could not open link: {e.message}")

    def show_about(self):
        about = Adw.AboutWindow(
            transient_for=self,
            application_name="OrphyCleaner",
            application_icon="folder-symbolic",
            version=__version__,
            developer_name="Jozef Gaal",
            developers=["Jozef Gaal (dodog)"],
            copyright="\u00a9 Jozef Gaal",
            license_type=Gtk.License.AGPL_3_0,
            website="https://orphycleaner.mayday.sk",
            issue_url="https://github.com/dodog/orphycleaner/issues",
            comments=(
                "Scans your home directory for config folders that may belong "
                "to uninstalled or unused applications."
            ),
        )
        about.present()

    def delete_folder(self):
        item = self._selected_item()
        if item is None:
            return
        if self.current_category != "Orphaned":
            self._toast("Only Orphaned folders can be deleted.")
            return
        folder = item.path

        has_trash = bool(shutil.which("gio"))
        heading = "Confirm Delete" if has_trash else "Confirm Permanent Delete"
        body = (
            f"Are you sure you want to move this folder to Trash?\n\n{folder}"
            if has_trash else
            f"Trash is not available.\n\nAre you sure you want to permanently delete this folder?\n\n{folder}"
        )

        dialog = Adw.MessageDialog(
            transient_for=self, heading=heading, body=body,
        )
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._on_delete_confirmed, folder, has_trash)
        dialog.present()

    def _on_delete_confirmed(self, dialog, response, folder, has_trash):
        if response != "delete":
            return
        if has_trash:
            result = subprocess.run(["gio", "trash", folder], stderr=subprocess.PIPE, text=True)
        else:
            result = subprocess.run(["rm", "-rf", folder], stderr=subprocess.PIPE, text=True)

        if result.returncode != 0:
            self._toast(f"Could not delete folder: {result.stderr.strip()}")
            return

        selected_row = self.folder_list.get_selected_row()
        prev_index = self._listbox_rows(self.folder_list).index(selected_row) if selected_row else 0

        if folder in self.results.get("Orphaned", []):
            self.results["Orphaned"].remove(folder)
        self.folder_items.pop(folder, None)
        self.show_category("Orphaned")
        self._select_row_near_index(prev_index)
        self._toast(f"Deleted {os.path.basename(folder)}")

    def export_orphaned_list(self):
        folders = self.results.get("Orphaned", [])
        if not folders:
            self._toast("No orphaned folders to export.")
            return

        dialog = Gtk.FileDialog()
        dialog.set_initial_name("orphycleaner_orphaned.txt")
        dialog.save(self, None, self._on_export_path_chosen, folders)

    def _on_export_path_chosen(self, dialog, result, folders):
        try:
            gfile = dialog.save_finish(result)
        except GLib.Error:
            return  # cancelled
        if gfile is None:
            return
        path = gfile.get_path()
        try:
            with open(path, "w") as f:
                total = 0
                for folder in folders:
                    item = self.folder_items.get(folder)
                    size = item.size if item else None
                    total += size or 0
                    size_str = format_size(size) if size is not None else "unknown"
                    f.write(f"{folder}\t{size_str}\n")
                f.write(f"\nTotal reclaimable (of folders sized so far): {format_size(total)}\n")
            self._toast(f"Orphaned folder list saved to {path}")
        except Exception as e:
            self._toast(f"Could not save file: {e}")


# =========================================================
# ENTRY POINT
# =========================================================
class OrphyCleanerApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
        self.win = None

    def do_activate(self):
        if self.win is None:
            self.win = OrphyCleanerWindow(self)
        self.win.present()


if __name__ == "__main__":
    app = OrphyCleanerApp()
    app.run(sys.argv)
