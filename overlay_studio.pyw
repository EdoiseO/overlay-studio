from __future__ import annotations

import base64
import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk
from typing import Any, Callable


ROOT_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
SERVER_DIR = ROOT_DIR / "larpdog-server"
SERVER_CONFIG_PATH = SERVER_DIR / "config.json"
SERVER_CONFIG_EXAMPLE_PATH = SERVER_DIR / "config.example.json"
OVERLAY_CONFIG_PATH = SERVER_DIR / "overlay-config.json"
APP_SETTINGS_PATH = SERVER_DIR / "app-settings.json"
USER_ASSETS_DIR = ROOT_DIR / "user-assets"
PID_PATH = SERVER_DIR / "server.pid"
LOG_PATH = SERVER_DIR / "server.log"
ERROR_LOG_PATH = SERVER_DIR / "server.err"

sys.path.insert(0, str(SERVER_DIR))
from overlay_config import (  # noqa: E402
    DEFAULT_OVERLAY_CONFIG,
    load_overlay_config,
    normalize_overlay_config,
    save_overlay_config,
)


THEMES = {
    "dark": {
        "background": "#0f1316",
        "panel": "#171d21",
        "panel_alt": "#1c2429",
        "ink": "#f1f5f6",
        "muted": "#8d9aa2",
        "accent": "#4fc8bd",
        "accent_dark": "#36a79e",
        "good": "#49c98d",
        "stopped": "#e36f68",
        "border": "#303a40",
    },
    "light": {
        "background": "#f2f5f5",
        "panel": "#ffffff",
        "panel_alt": "#e9eeee",
        "ink": "#182327",
        "muted": "#65747a",
        "accent": "#087f83",
        "accent_dark": "#05686b",
        "good": "#169873",
        "stopped": "#d05f55",
        "border": "#d8e0e1",
    },
}

BACKGROUND = THEMES["dark"]["background"]
PANEL = THEMES["dark"]["panel"]
PANEL_ALT = THEMES["dark"]["panel_alt"]
INK = THEMES["dark"]["ink"]
MUTED = THEMES["dark"]["muted"]
ACCENT = THEMES["dark"]["accent"]
ACCENT_DARK = THEMES["dark"]["accent_dark"]
GOOD = THEMES["dark"]["good"]
STOPPED = THEMES["dark"]["stopped"]
BORDER = THEMES["dark"]["border"]

POSITION_OPTIONS = {
    "Bottom left": "bottom-left",
    "Bottom right": "bottom-right",
    "Top left": "top-left",
    "Top right": "top-right",
}
COLOR_MODE_OPTIONS = {
    "Match artwork": "auto",
    "Fixed colors": "fixed",
    "Artwork with fallback": "art",
}
DANCE_FILE_TYPES = [
    ("Animated GIF", "*.gif"),
    ("Animated media", "*.webp *.apng *.webm *.mp4 *.mov"),
    ("All files", "*.*"),
]
REST_FILE_TYPES = [
    ("Images", "*.png *.gif *.webp *.apng"),
    ("All files", "*.*"),
]
ALLOWED_ASSET_EXTENSIONS = {".gif", ".webp", ".apng", ".png", ".webm", ".mp4", ".mov"}
REST_ASSET_EXTENSIONS = {".gif", ".webp", ".apng", ".png"}
LIBRARY_COLUMNS = 4
OVERLAY_CARD_SIZE = 200
OVERLAY_PREVIEW_HEIGHT = 96


def activate_theme(theme_name: str) -> str:
    global BACKGROUND, PANEL, PANEL_ALT, INK, MUTED
    global ACCENT, ACCENT_DARK, GOOD, STOPPED, BORDER

    selected = theme_name if theme_name in THEMES else "dark"
    colors = THEMES[selected]
    BACKGROUND = colors["background"]
    PANEL = colors["panel"]
    PANEL_ALT = colors["panel_alt"]
    INK = colors["ink"]
    MUTED = colors["muted"]
    ACCENT = colors["accent"]
    ACCENT_DARK = colors["accent_dark"]
    GOOD = colors["good"]
    STOPPED = colors["stopped"]
    BORDER = colors["border"]
    return selected


def inverse_lookup(options: dict[str, str], value: str) -> str:
    return next((label for label, option in options.items() if option == value), next(iter(options)))


def load_json(path: Path, fallback_path: Path | None = None) -> dict[str, Any]:
    source = path if path.exists() else fallback_path
    if source is None or not source.exists():
        return {}
    try:
        value = json.loads(source.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def save_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(path)


def server_address() -> tuple[str, int]:
    config = load_json(SERVER_CONFIG_PATH, SERVER_CONFIG_EXAMPLE_PATH)
    server = config.get("server") if isinstance(config.get("server"), dict) else {}
    host = str(server.get("host") or "127.0.0.1")
    if host in {"0.0.0.0", "::"}:
        host = "127.0.0.1"
    try:
        port = int(server.get("port", 8473))
    except (TypeError, ValueError):
        port = 8473
    return host, port


def base_url() -> str:
    host, port = server_address()
    return f"http://{host}:{port}/"


def is_healthy(timeout: float = 0.8) -> bool:
    try:
        with urllib.request.urlopen(f"{base_url()}health", timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return response.status == 200 and payload.get("app") in {
            "overlay-studio-server",
            "larpdog-server",
        }
    except (OSError, ValueError, urllib.error.URLError):
        return False


def hidden_process_options() -> dict[str, Any]:
    if sys.platform != "win32":
        return {}
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}


class OverlayStudio:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.app_settings = load_json(APP_SETTINGS_PATH)
        self.theme_name = activate_theme(str(self.app_settings.get("theme") or "dark"))
        self.app_settings["theme"] = self.theme_name

        self.root.title("Overlay Studio")
        self.root.geometry("980x720")
        self.root.minsize(920, 640)
        self.root.configure(background=BACKGROUND)

        self._busy = False
        self._health_check_pending = False
        self._counter_check_pending = False
        self._now_playing_check_pending = False
        self._drawer_visible = False
        self._drawer_x = -290
        self._drawer_animation: str | None = None
        self._pending_assets: dict[str, Path | None] = {"gif": None, "rest": None}
        self._swatch_buttons: dict[str, tk.Button] = {}
        self.save_buttons: list[ttk.Button] = []
        self._library_images: list[tk.PhotoImage] = []
        self._spotify_art_image: tk.PhotoImage | None = None
        self._spotify_art_source = ""
        self._spotify_progress_ratio = 0.0
        self._overlay_status_vars: dict[str, tk.StringVar] = {}
        self._overlay_status_dots: dict[str, tuple[tk.Canvas, int]] = {}
        self._overlay_status_labels: dict[str, tk.Label] = {}

        self._setup_styles()
        self._set_window_icon()
        self._init_customization_vars()
        self._build_ui()
        self._load_customization()
        self._update_overlay_urls()
        self.root.after(150, self._schedule_health_check)
        self.root.after(300, self._load_counter_state_async)
        self.root.after(350, self._load_now_playing_async)

    def _setup_styles(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure(".", font=("Segoe UI", 10), background=BACKGROUND, foreground=INK)
        style.configure("App.TFrame", background=BACKGROUND)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("PanelAlt.TFrame", background=PANEL_ALT)
        style.configure("Header.TLabel", background=BACKGROUND, foreground=INK, font=("Segoe UI Semibold", 20))
        style.configure("Subheader.TLabel", background=BACKGROUND, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("PanelTitle.TLabel", background=PANEL, foreground=INK, font=("Segoe UI Semibold", 11))
        style.configure("Panel.TLabel", background=PANEL, foreground=INK)
        style.configure("Muted.TLabel", background=PANEL, foreground=MUTED)
        style.configure("DrawerTitle.TLabel", background=PANEL, foreground=INK, font=("Segoe UI Semibold", 17))
        style.configure("Drawer.TLabel", background=PANEL, foreground=INK)
        style.configure("DrawerMuted.TLabel", background=PANEL, foreground=MUTED)
        style.configure("Status.TLabel", background=BACKGROUND, foreground=INK, font=("Segoe UI Semibold", 10))
        style.configure(
            "TNotebook",
            background=BACKGROUND,
            borderwidth=0,
            tabmargins=0,
            relief="flat",
            bordercolor=BACKGROUND,
            lightcolor=BACKGROUND,
            darkcolor=BACKGROUND,
        )
        style.layout("TNotebook.Tab", [])
        style.configure("Primary.TButton", background=ACCENT, foreground="#071210", padding=(15, 9))
        style.map(
            "Primary.TButton",
            background=[("active", ACCENT_DARK), ("disabled", BORDER)],
            foreground=[("disabled", MUTED)],
        )
        style.configure("Secondary.TButton", background=PANEL_ALT, foreground=INK, padding=(13, 8))
        style.map("Secondary.TButton", background=[("active", BORDER)])
        style.configure("Danger.TButton", background="#472625", foreground="#ffaaa4", padding=(13, 8))
        style.map("Danger.TButton", background=[("active", "#5a302e")])
        style.configure(
            "CounterPrimary.TButton",
            background=ACCENT,
            foreground="#071210",
            padding=(6, 4),
            font=("Segoe UI Semibold", 9),
        )
        style.map("CounterPrimary.TButton", background=[("active", ACCENT_DARK)])
        style.configure(
            "CounterSecondary.TButton",
            background=PANEL_ALT,
            foreground=INK,
            padding=(6, 4),
            font=("Segoe UI Semibold", 9),
        )
        style.map("CounterSecondary.TButton", background=[("active", BORDER)])
        style.configure(
            "CounterDanger.TButton",
            background="#472625",
            foreground="#ffaaa4",
            padding=(6, 4),
            font=("Segoe UI Semibold", 9),
        )
        style.map("CounterDanger.TButton", background=[("active", "#5a302e")])
        style.configure("TCheckbutton", background=PANEL, foreground=INK)
        style.configure("TRadiobutton", background=PANEL, foreground=INK)
        style.configure("Horizontal.TScale", background=PANEL, troughcolor=BORDER)
        style.configure("TEntry", fieldbackground=PANEL_ALT, foreground=INK, insertcolor=INK)
        style.configure("TSpinbox", fieldbackground=PANEL_ALT, foreground=INK, arrowcolor=INK)
        style.configure("TCombobox", fieldbackground=PANEL_ALT, foreground=INK, arrowcolor=INK)
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", PANEL_ALT)],
            foreground=[("readonly", INK)],
            selectbackground=[("readonly", PANEL_ALT)],
            selectforeground=[("readonly", INK)],
        )

    def _set_window_icon(self) -> None:
        icon_path = ROOT_DIR / "assets" / "resting-dog.png"
        if not icon_path.exists():
            return
        try:
            self._icon = tk.PhotoImage(file=str(icon_path))
            self.root.iconphoto(True, self._icon)
        except tk.TclError:
            self._icon = None

    def _build_ui(self) -> None:
        shell = ttk.Frame(self.root, style="App.TFrame", padding=(22, 18, 22, 20))
        shell.pack(fill="both", expand=True)

        header = ttk.Frame(shell, style="App.TFrame")
        header.pack(fill="x")
        self.menu_button = tk.Button(
            header,
            text="\u2630",
            width=3,
            relief="flat",
            borderwidth=0,
            background=BACKGROUND,
            foreground=INK,
            activebackground=PANEL_ALT,
            activeforeground=INK,
            font=("Segoe UI", 18),
            cursor="hand2",
            command=self.toggle_settings_drawer,
        )
        self.menu_button.pack(side="left", padx=(0, 14))
        title_block = ttk.Frame(header, style="App.TFrame")
        title_block.pack(side="left", fill="x", expand=True)
        ttk.Label(title_block, text="Overlay Studio", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            title_block,
            text="Build, run, and manage stream overlays",
            style="Subheader.TLabel",
        ).pack(anchor="w", pady=(1, 0))

        status_block = ttk.Frame(header, style="App.TFrame")
        status_block.pack(side="right", padx=(16, 0))
        self.header_start_button = ttk.Button(
            status_block,
            text="Start server",
            style="Primary.TButton",
            command=self.start_server,
        )
        self.header_start_button.pack(side="right", padx=(14, 0))
        self.status_dot = tk.Canvas(
            status_block,
            width=14,
            height=14,
            background=BACKGROUND,
            highlightthickness=0,
        )
        self.status_dot.pack(side="left", padx=(0, 7))
        self.status_circle = self.status_dot.create_oval(2, 2, 12, 12, fill=MUTED, outline="")
        self.status_var = tk.StringVar(value="Checking...")
        ttk.Label(status_block, textvariable=self.status_var, style="Status.TLabel").pack(side="left")

        self.notebook = ttk.Notebook(shell)
        self.notebook.pack(fill="both", expand=True, pady=(18, 0))
        self.library_tab = ttk.Frame(self.notebook, style="App.TFrame")
        self.control_tab = ttk.Frame(self.notebook, style="App.TFrame")
        self.customize_tab = ttk.Frame(self.notebook, style="App.TFrame")
        self.spotify_tab = ttk.Frame(self.notebook, style="App.TFrame")
        self.counter_tab = ttk.Frame(self.notebook, style="App.TFrame")
        self.notebook.add(self.library_tab, text="Library")
        self.notebook.add(self.control_tab, text="Server")
        self.notebook.add(self.customize_tab, text="Dance")
        self.notebook.add(self.spotify_tab, text="Spotify")
        self.notebook.add(self.counter_tab, text="Win / Loss")

        self._build_library_tab()
        self._build_control_tab()
        self._build_customize_tab()
        self._build_spotify_tab()
        self._build_counter_tab()
        self._build_settings_drawer()
        self.notebook.select(self.library_tab)

    def _build_library_tab(self) -> None:
        heading = ttk.Frame(self.library_tab, style="App.TFrame")
        heading.pack(fill="x", pady=(2, 16))
        ttk.Label(
            heading,
            text="Your overlays",
            style="Header.TLabel",
        ).pack(side="left")
        ttk.Label(
            heading,
            text="3 installed",
            style="Subheader.TLabel",
        ).pack(side="right", pady=(8, 0))

        grid = tk.Frame(self.library_tab, background=BACKGROUND)
        grid.pack(fill="both", expand=True)
        for column in range(LIBRARY_COLUMNS):
            grid.columnconfigure(column, weight=1, uniform="library")

        self._overlay_card(
            grid,
            column=0,
            title="Larpdog Dance",
            subtitle="Audio-reactive dance GIF",
            kind="dance",
            command=lambda: self._show_page(self.customize_tab),
        )
        self._overlay_card(
            grid,
            column=1,
            title="Spotify Overlay",
            subtitle="Now playing + artwork",
            kind="spotify",
            command=lambda: self._show_page(self.spotify_tab),
        )
        self._overlay_card(
            grid,
            column=2,
            title="Match Record",
            subtitle="Marvel Rivals wins / losses",
            kind="counter",
            command=lambda: self._show_page(self.counter_tab),
        )
        self._add_overlay_card(grid, column=3)

    def _overlay_card(
        self,
        parent: tk.Frame,
        *,
        column: int,
        title: str,
        subtitle: str,
        kind: str,
        command: Callable[[], None],
    ) -> None:
        card = tk.Frame(
            parent,
            width=OVERLAY_CARD_SIZE,
            height=OVERLAY_CARD_SIZE,
            background=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        card.grid(row=0, column=column, sticky="n", padx=8)
        card.pack_propagate(False)

        preview = tk.Frame(card, height=OVERLAY_PREVIEW_HEIGHT, background=PANEL_ALT)
        preview.pack(fill="x")
        preview.pack_propagate(False)

        if kind == "dance":
            icon_path = ROOT_DIR / "assets" / "resting-dog.png"
            try:
                image = tk.PhotoImage(file=str(icon_path))
                factor = max(1, (max(image.width(), image.height()) + 79) // 80)
                image = image.subsample(factor, factor)
                self._library_images.append(image)
                tk.Label(
                    preview,
                    image=image,
                    background=PANEL_ALT,
                    borderwidth=0,
                ).pack(expand=True)
            except tk.TclError:
                tk.Label(
                    preview,
                    text="DANCE",
                    background=PANEL_ALT,
                    foreground=ACCENT,
                    font=("Segoe UI Semibold", 20),
                ).pack(expand=True)
        elif kind == "spotify":
            spotify_preview = tk.Frame(preview, background=PANEL_ALT)
            spotify_preview.pack(expand=True, fill="both", padx=12, pady=10)
            art_frame = tk.Frame(
                spotify_preview,
                width=58,
                height=58,
                background=PANEL_ALT,
            )
            art_frame.pack(side="left")
            art_frame.pack_propagate(False)
            self.spotify_preview_art = tk.Label(
                art_frame,
                text="SP",
                background=PANEL_ALT,
                foreground=ACCENT,
                font=("Segoe UI Semibold", 11),
                borderwidth=1,
                relief="solid",
            )
            self.spotify_preview_art.pack(fill="both", expand=True)
            track_preview = tk.Frame(spotify_preview, background=PANEL_ALT)
            track_preview.pack(side="left", fill="both", expand=True, padx=(10, 0))
            self.spotify_preview_title_var = tk.StringVar(value="waiting for a song...")
            self.spotify_preview_artist_var = tk.StringVar(value="")
            tk.Label(
                track_preview,
                textvariable=self.spotify_preview_title_var,
                background=PANEL_ALT,
                foreground=INK,
                anchor="w",
                font=("Segoe UI Semibold", 10),
            ).pack(fill="x")
            tk.Label(
                track_preview,
                textvariable=self.spotify_preview_artist_var,
                background=PANEL_ALT,
                foreground=MUTED,
                anchor="w",
                font=("Segoe UI", 8),
            ).pack(fill="x", pady=(2, 7))
            self.spotify_preview_progress = tk.Canvas(
                track_preview,
                height=4,
                background=BORDER,
                highlightthickness=0,
            )
            self.spotify_preview_progress.pack(fill="x")
            self.spotify_preview_progress_fill = (
                self.spotify_preview_progress.create_rectangle(
                    0,
                    0,
                    0,
                    4,
                    fill=ACCENT,
                    outline="",
                )
            )
            self.spotify_preview_progress.bind(
                "<Configure>",
                lambda _event: self._paint_spotify_progress(),
            )
        else:
            counter_preview = tk.Frame(preview, background=PANEL_ALT)
            counter_preview.pack(expand=True)
            tk.Label(
                counter_preview,
                text="MATCH RECORD",
                background=PANEL_ALT,
                foreground=ACCENT,
                font=("Segoe UI Semibold", 9),
            ).pack()
            self.library_counter_score_var = tk.StringVar(value="0 W   0 L")
            tk.Label(
                counter_preview,
                textvariable=self.library_counter_score_var,
                background=PANEL_ALT,
                foreground=INK,
                font=("Segoe UI Semibold", 22),
            ).pack(pady=(6, 0))

        body = tk.Frame(card, background=PANEL)
        body.pack(fill="both", expand=True, padx=14, pady=12)
        tk.Label(
            body,
            text=title,
            background=PANEL,
            foreground=INK,
            anchor="w",
            font=("Segoe UI Semibold", 12),
        ).pack(fill="x")
        tk.Label(
            body,
            text=subtitle,
            background=PANEL,
            foreground=MUTED,
            anchor="w",
            font=("Segoe UI", 9),
        ).pack(fill="x", pady=(2, 10))
        footer = tk.Frame(body, background=PANEL)
        footer.pack(fill="x")
        status_dot = tk.Canvas(
            footer,
            width=10,
            height=10,
            background=PANEL,
            highlightthickness=0,
        )
        status_circle = status_dot.create_oval(1, 1, 9, 9, fill=MUTED, outline="")
        status_dot.pack(side="left", padx=(0, 6))
        status_var = tk.StringVar(value="READY")
        self._overlay_status_vars[kind] = status_var
        self._overlay_status_dots[kind] = (status_dot, status_circle)
        status_label = tk.Label(
            footer,
            textvariable=status_var,
            background=PANEL,
            foreground=MUTED,
            font=("Segoe UI Semibold", 8),
        )
        status_label.pack(side="left")
        self._overlay_status_labels[kind] = status_label
        self._make_card_clickable(card, command)

    def _make_card_clickable(self, card: tk.Frame, command: Callable[[], None]) -> None:
        def bind_widget(widget: tk.Misc) -> None:
            with contextlib.suppress(tk.TclError):
                widget.configure(cursor="hand2")
            widget.bind("<Button-1>", lambda _event: command(), add="+")
            widget.bind(
                "<Enter>",
                lambda _event: card.configure(highlightbackground=ACCENT),
                add="+",
            )
            widget.bind(
                "<Leave>",
                lambda _event: self.root.after(12, lambda: self._settle_card_hover(card)),
                add="+",
            )
            for child in widget.winfo_children():
                bind_widget(child)

        bind_widget(card)

    def _settle_card_hover(self, card: tk.Frame) -> None:
        try:
            pointer_x, pointer_y = self.root.winfo_pointerxy()
            under_pointer = self.root.winfo_containing(pointer_x, pointer_y)
            current = under_pointer
            while current is not None:
                if current == card:
                    card.configure(highlightbackground=ACCENT)
                    return
                current = current.master
            card.configure(highlightbackground=BORDER)
        except tk.TclError:
            pass

    def _add_overlay_card(self, parent: tk.Frame, *, column: int) -> None:
        card = tk.Frame(
            parent,
            width=OVERLAY_CARD_SIZE,
            height=OVERLAY_CARD_SIZE,
            background=BACKGROUND,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        card.grid(row=0, column=column, sticky="n", padx=8)
        card.pack_propagate(False)
        content = tk.Frame(card, background=BACKGROUND)
        content.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(
            content,
            text="+",
            background=BACKGROUND,
            foreground=MUTED,
            font=("Segoe UI Light", 38),
        ).pack()
        tk.Label(
            content,
            text="Add overlay",
            background=BACKGROUND,
            foreground=MUTED,
            font=("Segoe UI Semibold", 10),
        ).pack(pady=(2, 0))
        self._make_card_clickable(card, self._show_add_overlay_info)

    def _show_add_overlay_info(self) -> None:
        messagebox.showinfo(
            "Add overlay",
            "This library is ready for the next overlay package. New templates will appear here.",
            parent=self.root,
        )

    def _show_page(self, page: ttk.Frame) -> None:
        self.notebook.select(page)

    def _detail_nav(
        self,
        parent: ttk.Frame,
        title: str,
        secondary_text: str | None = None,
        secondary_command: Callable[[], None] | None = None,
    ) -> None:
        navigation = ttk.Frame(parent, style="App.TFrame")
        navigation.pack(fill="x", pady=(0, 12))
        ttk.Button(
            navigation,
            text="Library",
            style="Secondary.TButton",
            command=lambda: self._show_page(self.library_tab),
        ).pack(side="left")
        ttk.Label(navigation, text=title, style="Header.TLabel").pack(side="left", padx=(14, 0))
        if secondary_text and secondary_command:
            ttk.Button(
                navigation,
                text=secondary_text,
                style="Secondary.TButton",
                command=secondary_command,
            ).pack(side="right")

    def _build_settings_drawer(self) -> None:
        self.drawer_width = 290
        self.settings_drawer = tk.Frame(
            self.root,
            width=self.drawer_width,
            background=PANEL,
            highlightbackground=BORDER,
            highlightthickness=1,
        )
        self.settings_drawer.place(
            x=self._drawer_x,
            y=0,
            width=self.drawer_width,
            relheight=1,
        )
        self.settings_drawer.pack_propagate(False)

        drawer_header = ttk.Frame(self.settings_drawer, style="Panel.TFrame", padding=(20, 20, 14, 12))
        drawer_header.pack(fill="x")
        ttk.Label(drawer_header, text="Settings", style="DrawerTitle.TLabel").pack(side="left")
        tk.Button(
            drawer_header,
            text="\u00d7",
            width=2,
            relief="flat",
            borderwidth=0,
            background=PANEL,
            foreground=MUTED,
            activebackground=PANEL_ALT,
            activeforeground=INK,
            font=("Segoe UI", 18),
            cursor="hand2",
            command=self.toggle_settings_drawer,
        ).pack(side="right")

        navigation = ttk.Frame(self.settings_drawer, style="Panel.TFrame", padding=(20, 8))
        navigation.pack(fill="x")
        ttk.Button(
            navigation,
            text="Overlay library",
            style="Secondary.TButton",
            command=lambda: (self._show_page(self.library_tab), self.toggle_settings_drawer()),
        ).pack(fill="x")
        ttk.Button(
            navigation,
            text="Server controls",
            style="Secondary.TButton",
            command=lambda: (self._show_page(self.control_tab), self.toggle_settings_drawer()),
        ).pack(fill="x", pady=(8, 0))

        divider = tk.Frame(self.settings_drawer, height=1, background=BORDER)
        divider.pack(fill="x", padx=20, pady=18)

        appearance = ttk.Frame(self.settings_drawer, style="Panel.TFrame", padding=(20, 0))
        appearance.pack(fill="x")
        ttk.Label(appearance, text="Appearance", style="PanelTitle.TLabel").pack(anchor="w")
        ttk.Label(appearance, text="Theme", style="DrawerMuted.TLabel").pack(anchor="w", pady=(14, 6))
        self.theme_var = tk.StringVar(value=self.theme_name.title())
        theme_picker = ttk.Combobox(
            appearance,
            textvariable=self.theme_var,
            values=("Dark", "Light"),
            state="readonly",
        )
        theme_picker.pack(fill="x")
        theme_picker.bind("<<ComboboxSelected>>", self._change_theme)

        workspace = ttk.Frame(self.settings_drawer, style="Panel.TFrame", padding=(20, 24))
        workspace.pack(fill="x")
        ttk.Label(workspace, text="Workspace", style="PanelTitle.TLabel").pack(anchor="w")
        ttk.Button(
            workspace,
            text="Open overlay files",
            style="Secondary.TButton",
            command=lambda: self._open_folder(ROOT_DIR / "overlays"),
        ).pack(fill="x", pady=(12, 0))
        ttk.Button(
            workspace,
            text="Open log folder",
            style="Secondary.TButton",
            command=lambda: self._open_folder(SERVER_DIR),
        ).pack(fill="x", pady=(8, 0))

        about = ttk.Frame(self.settings_drawer, style="Panel.TFrame", padding=(20, 12))
        about.pack(side="bottom", fill="x")
        ttk.Label(about, text="Overlay Studio", style="Drawer.TLabel").pack(anchor="w")
        ttk.Label(about, text="Desktop overlay library", style="DrawerMuted.TLabel").pack(
            anchor="w",
            pady=(2, 0),
        )
        self.settings_drawer.lift()

    def toggle_settings_drawer(self) -> None:
        self._drawer_visible = not self._drawer_visible
        if self._drawer_animation is not None:
            with contextlib.suppress(tk.TclError):
                self.root.after_cancel(self._drawer_animation)
        self._animate_settings_drawer()

    def _animate_settings_drawer(self) -> None:
        target = 0 if self._drawer_visible else -self.drawer_width
        difference = target - self._drawer_x
        if abs(difference) <= 1:
            self._drawer_x = target
            self.settings_drawer.place_configure(x=self._drawer_x)
            self._drawer_animation = None
            return
        step = max(-36, min(36, difference))
        self._drawer_x += step
        self.settings_drawer.place_configure(x=self._drawer_x)
        self.settings_drawer.lift()
        self._drawer_animation = self.root.after(12, self._animate_settings_drawer)

    def _change_theme(self, _event: tk.Event[Any] | None = None) -> None:
        selected = self.theme_var.get().strip().lower()
        if selected == self.theme_name:
            return
        self.theme_name = activate_theme(selected)
        self.app_settings["theme"] = self.theme_name
        save_json(APP_SETTINGS_PATH, self.app_settings)
        self._rebuild_ui()

    def _rebuild_ui(self) -> None:
        if self._drawer_animation is not None:
            with contextlib.suppress(tk.TclError):
                self.root.after_cancel(self._drawer_animation)
        for child in self.root.winfo_children():
            child.destroy()
        self.root.configure(background=BACKGROUND)
        self._drawer_visible = False
        self._drawer_x = -290
        self._drawer_animation = None
        self._swatch_buttons = {}
        self._library_images = []
        self._spotify_art_image = None
        self._spotify_art_source = ""
        self._spotify_progress_ratio = 0.0
        self._overlay_status_vars = {}
        self._overlay_status_dots = {}
        self._overlay_status_labels = {}
        self.save_buttons = []
        self._setup_styles()
        self._build_ui()
        self._load_customization()
        self._update_overlay_urls()
        self._render_health(is_healthy())
        self._load_counter_state_async()

    def _panel(self, parent: ttk.Frame, title: str) -> ttk.Frame:
        panel = ttk.Frame(parent, style="Panel.TFrame", padding=18)
        panel.pack(fill="x", pady=(0, 12))
        ttk.Label(panel, text=title, style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 12))
        return panel

    def _init_customization_vars(self) -> None:
        self.dance_position_var = tk.StringVar()
        self.spotify_position_var = tk.StringVar()
        self.gif_asset_var = tk.StringVar()
        self.rest_asset_var = tk.StringVar()
        self.dance_scale_var = tk.DoubleVar(value=1.0)
        self.spotify_scale_var = tk.DoubleVar(value=1.0)
        self.card_width_var = tk.IntVar(value=335)
        self.color_mode_var = tk.StringVar()
        self.color_vars = {
            "a": tk.StringVar(value="ff4d9d"),
            "b": tk.StringVar(value="ffd24a"),
            "c": tk.StringVar(value="5ee0ff"),
        }
        self.sensitivity_var = tk.DoubleVar(value=1.0)
        self.sensitivity_text_var = tk.StringVar(value="1.00")
        self.fallback_bpm_var = tk.IntVar(value=120)
        self.dance_url_var = tk.StringVar()
        self.spotify_url_var = tk.StringVar()

    def _build_control_tab(self) -> None:
        self._detail_nav(self.control_tab, "Server Controls")
        server_panel = self._panel(self.control_tab, "Server")
        details = ttk.Frame(server_panel, style="Panel.TFrame")
        details.pack(fill="x")
        details.columnconfigure(1, weight=1)

        ttk.Label(details, text="Address", style="Muted.TLabel").grid(row=0, column=0, sticky="w")
        self.address_var = tk.StringVar(value=base_url())
        ttk.Label(details, textvariable=self.address_var, style="Panel.TLabel").grid(
            row=0, column=1, sticky="w", padx=(18, 0)
        )
        ttk.Label(details, text="State", style="Muted.TLabel").grid(row=1, column=0, sticky="w", pady=(7, 0))
        self.server_state_var = tk.StringVar(value="Checking the local server")
        ttk.Label(details, textvariable=self.server_state_var, style="Panel.TLabel").grid(
            row=1, column=1, sticky="w", padx=(18, 0), pady=(7, 0)
        )

        actions = ttk.Frame(server_panel, style="Panel.TFrame")
        actions.pack(fill="x", pady=(16, 0))
        self.start_button = ttk.Button(actions, text="Start", style="Primary.TButton", command=self.start_server)
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(actions, text="Stop", style="Danger.TButton", command=self.stop_server)
        self.stop_button.pack(side="left", padx=(8, 0))
        self.restart_button = ttk.Button(
            actions,
            text="Restart",
            style="Secondary.TButton",
            command=self.restart_server,
        )
        self.restart_button.pack(side="left", padx=(8, 0))
        ttk.Button(
            actions,
            text="Open user assets",
            style="Secondary.TButton",
            command=self.open_user_assets,
        ).pack(side="right")

        obs_panel = self._panel(self.control_tab, "Overlay URLs")
        self._source_url_row(obs_panel, "Larpdog Dance", self.dance_url_var)
        self._source_url_row(obs_panel, "Spotify Overlay", self.spotify_url_var)
        tools = ttk.Frame(obs_panel, style="Panel.TFrame")
        tools.pack(fill="x", pady=(12, 0))
        ttk.Button(
            tools,
            text="Open log folder",
            style="Secondary.TButton",
            command=lambda: self._open_folder(SERVER_DIR),
        ).pack(side="left")

        activity_panel = self._panel(self.control_tab, "Activity")
        self.activity_text = tk.Text(
            activity_panel,
            height=7,
            background=PANEL_ALT,
            foreground=INK,
            relief="flat",
            borderwidth=0,
            font=("Consolas", 9),
            padx=10,
            pady=8,
            state="disabled",
            wrap="word",
        )
        self.activity_text.pack(fill="both", expand=True)
        self._log("Overlay Studio opened")

    def _build_customize_tab(self) -> None:
        self._detail_nav(
            self.customize_tab,
            "Larpdog Dance",
            "Server controls",
            lambda: self._show_page(self.control_tab),
        )
        character_panel = self._panel(self.customize_tab, "Dance GIF and layout")
        character_grid = ttk.Frame(character_panel, style="Panel.TFrame")
        character_grid.pack(fill="x")
        character_grid.columnconfigure(1, weight=1)

        self._form_label(character_grid, "Position", 0)
        ttk.Combobox(
            character_grid,
            textvariable=self.dance_position_var,
            values=list(POSITION_OPTIONS),
            state="readonly",
            width=24,
        ).grid(row=0, column=1, sticky="ew", padx=(16, 0))
        self._asset_picker(character_grid, "Dance GIF", "gif", self.gif_asset_var, 1)
        self._asset_picker(character_grid, "Resting image", "rest", self.rest_asset_var, 2)
        self._form_label(character_grid, "Scale", 3)
        ttk.Spinbox(
            character_grid,
            textvariable=self.dance_scale_var,
            from_=0.5,
            to=2.0,
            increment=0.05,
            width=10,
        ).grid(row=3, column=1, sticky="w", padx=(16, 0), pady=(9, 0))

        motion_panel = self._panel(self.customize_tab, "Motion")
        motion_grid = ttk.Frame(motion_panel, style="Panel.TFrame")
        motion_grid.pack(fill="x")
        motion_grid.columnconfigure(1, weight=1)

        self._form_label(motion_grid, "Beat sensitivity", 0)
        sensitivity_row = ttk.Frame(motion_grid, style="Panel.TFrame")
        sensitivity_row.grid(row=0, column=1, sticky="ew", padx=(16, 0))
        sensitivity_row.columnconfigure(0, weight=1)
        ttk.Scale(
            sensitivity_row,
            variable=self.sensitivity_var,
            from_=0.3,
            to=3.0,
            command=self._update_sensitivity_text,
        ).grid(row=0, column=0, sticky="ew")
        ttk.Label(
            sensitivity_row,
            textvariable=self.sensitivity_text_var,
            style="Panel.TLabel",
            width=5,
            anchor="e",
        ).grid(row=0, column=1, padx=(10, 0))

        self._form_label(motion_grid, "Fallback BPM", 1)
        ttk.Spinbox(
            motion_grid,
            textvariable=self.fallback_bpm_var,
            from_=40,
            to=240,
            increment=1,
            width=10,
        ).grid(row=1, column=1, sticky="w", padx=(16, 0), pady=(9, 0))

        source_panel = self._panel(self.customize_tab, "OBS browser source")
        self._source_url_row(source_panel, "Dance source", self.dance_url_var)

        save_bar = ttk.Frame(self.customize_tab, style="App.TFrame")
        save_bar.pack(fill="x", pady=(0, 8))
        dance_save_button = ttk.Button(
            save_bar,
            text="Save and apply",
            style="Primary.TButton",
            command=self.save_customization,
        )
        dance_save_button.pack(side="right")
        self.save_buttons.append(dance_save_button)
        ttk.Button(
            save_bar,
            text="Reset fields",
            style="Secondary.TButton",
            command=self.reset_dance_fields,
        ).pack(side="right", padx=(0, 8))

    def _build_spotify_tab(self) -> None:
        self._detail_nav(
            self.spotify_tab,
            "Spotify Overlay",
            "Server controls",
            lambda: self._show_page(self.control_tab),
        )
        appearance_panel = self._panel(self.spotify_tab, "Player appearance")
        appearance_grid = ttk.Frame(appearance_panel, style="Panel.TFrame")
        appearance_grid.pack(fill="x")
        appearance_grid.columnconfigure(1, weight=1)

        self._form_label(appearance_grid, "Position", 0)
        ttk.Combobox(
            appearance_grid,
            textvariable=self.spotify_position_var,
            values=list(POSITION_OPTIONS),
            state="readonly",
            width=24,
        ).grid(row=0, column=1, sticky="ew", padx=(16, 0))
        self._form_label(appearance_grid, "Scale", 1)
        ttk.Spinbox(
            appearance_grid,
            textvariable=self.spotify_scale_var,
            from_=0.5,
            to=2.0,
            increment=0.05,
            width=10,
        ).grid(row=1, column=1, sticky="w", padx=(16, 0), pady=(9, 0))
        self._form_label(appearance_grid, "Player width", 2)
        ttk.Spinbox(
            appearance_grid,
            textvariable=self.card_width_var,
            from_=240,
            to=600,
            increment=5,
            width=10,
        ).grid(row=2, column=1, sticky="w", padx=(16, 0), pady=(9, 0))
        self._form_label(appearance_grid, "Color behavior", 3)
        ttk.Combobox(
            appearance_grid,
            textvariable=self.color_mode_var,
            values=list(COLOR_MODE_OPTIONS),
            state="readonly",
            width=24,
        ).grid(row=3, column=1, sticky="w", padx=(16, 0), pady=(9, 0))

        self._form_label(appearance_grid, "Palette", 4)
        swatches = ttk.Frame(appearance_grid, style="Panel.TFrame")
        swatches.grid(row=4, column=1, sticky="w", padx=(16, 0), pady=(10, 0))
        for index, key in enumerate(("a", "b", "c")):
            button = tk.Button(
                swatches,
                width=9,
                relief="flat",
                borderwidth=0,
                cursor="hand2",
                font=("Segoe UI Semibold", 9),
                command=lambda color_key=key: self._choose_color(color_key),
            )
            button.grid(row=0, column=index, padx=(0, 7))
            self._swatch_buttons[key] = button

        source_panel = self._panel(self.spotify_tab, "OBS browser source")
        self._source_url_row(source_panel, "Spotify source", self.spotify_url_var)

        save_bar = ttk.Frame(self.spotify_tab, style="App.TFrame")
        save_bar.pack(fill="x", pady=(0, 8))
        spotify_save_button = ttk.Button(
            save_bar,
            text="Save and apply",
            style="Primary.TButton",
            command=self.save_customization,
        )
        spotify_save_button.pack(side="right")
        self.save_buttons.append(spotify_save_button)
        ttk.Button(
            save_bar,
            text="Reset fields",
            style="Secondary.TButton",
            command=self.reset_spotify_fields,
        ).pack(side="right", padx=(0, 8))

    def _source_url_row(
        self,
        parent: ttk.Frame,
        label: str,
        variable: tk.StringVar,
    ) -> None:
        row = ttk.Frame(parent, style="Panel.TFrame")
        row.pack(fill="x", pady=(0, 8))
        ttk.Label(row, text=label, style="Muted.TLabel", width=18).pack(side="left")
        ttk.Entry(row, textvariable=variable, state="readonly").pack(
            side="left",
            fill="x",
            expand=True,
        )
        ttk.Button(
            row,
            text="Copy",
            style="Primary.TButton",
            command=lambda: self.copy_overlay_url(variable, label),
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            row,
            text="Open",
            style="Secondary.TButton",
            command=lambda: self.open_overlay_preview(variable),
        ).pack(side="left", padx=(8, 0))

    def _build_counter_tab(self) -> None:
        self._detail_nav(self.counter_tab, "Match Record")

        counter_panel = self._panel(self.counter_tab, "Scoreboard")
        settings_row = ttk.Frame(counter_panel, style="Panel.TFrame")
        settings_row.pack(fill="x")
        settings_row.columnconfigure(1, weight=1)
        ttk.Label(settings_row, text="Title", style="Muted.TLabel").grid(
            row=0,
            column=0,
            sticky="w",
        )
        self.counter_title_var = tk.StringVar(value="MARVEL RIVALS")
        ttk.Entry(settings_row, textvariable=self.counter_title_var).grid(
            row=0,
            column=1,
            sticky="ew",
            padx=(16, 10),
        )
        self.counter_accent_var = tk.StringVar(value="d7ff45")
        self.counter_accent_button = tk.Button(
            settings_row,
            width=10,
            relief="flat",
            borderwidth=0,
            cursor="hand2",
            font=("Segoe UI Semibold", 9),
            command=self._choose_counter_color,
        )
        self.counter_accent_button.grid(row=0, column=2, padx=(0, 10))
        ttk.Button(
            settings_row,
            text="Save",
            style="Secondary.TButton",
            command=self._save_counter_settings,
        ).grid(row=0, column=3)

        score_row = tk.Frame(counter_panel, background=PANEL)
        score_row.pack(pady=(20, 16))
        self.counter_wins_var = tk.StringVar(value="0")
        self.counter_losses_var = tk.StringVar(value="0")
        self._score_block(
            score_row,
            label="WINS",
            variable=self.counter_wins_var,
            column=0,
            decrement_action="undo-win",
            increment_action="win",
            reset_key="wins",
        )
        tk.Frame(score_row, width=1, height=130, background=BORDER).grid(
            row=0,
            column=1,
            padx=12,
        )
        self._score_block(
            score_row,
            label="LOSSES",
            variable=self.counter_losses_var,
            column=2,
            decrement_action="undo-loss",
            increment_action="loss",
            reset_key="losses",
        )

        source_panel = self._panel(self.counter_tab, "OBS browser source")
        source_row = ttk.Frame(source_panel, style="Panel.TFrame")
        source_row.pack(fill="x")
        self.counter_url_var = tk.StringVar(value=f"{base_url()}overlays/win-loss")
        ttk.Entry(
            source_row,
            textvariable=self.counter_url_var,
            state="readonly",
        ).pack(side="left", fill="x", expand=True)
        ttk.Button(
            source_row,
            text="Copy URL",
            style="Primary.TButton",
            command=self.copy_counter_url,
        ).pack(side="left", padx=(8, 0))
        ttk.Button(
            source_panel,
            text="Open preview",
            style="Secondary.TButton",
            command=self.open_counter_preview,
        ).pack(anchor="e", pady=(10, 0))
        self._update_counter_swatch()

    def _score_block(
        self,
        parent: tk.Frame,
        label: str,
        variable: tk.StringVar,
        column: int,
        decrement_action: str,
        increment_action: str,
        reset_key: str,
    ) -> None:
        block = tk.Frame(parent, width=190, height=140, background=PANEL)
        block.grid(row=0, column=column)
        block.pack_propagate(False)
        tk.Label(
            block,
            text=label,
            background=PANEL,
            foreground=MUTED,
            font=("Segoe UI Semibold", 9),
        ).pack()
        tk.Label(
            block,
            textvariable=variable,
            background=PANEL,
            foreground=INK,
            font=("Segoe UI Semibold", 42),
        ).pack(pady=(0, 8))
        controls = ttk.Frame(block, style="Panel.TFrame")
        controls.pack()
        ttk.Button(
            controls,
            text="-",
            width=2,
            style="CounterSecondary.TButton",
            command=lambda: self._post_counter_action(decrement_action),
        ).pack(side="left")
        ttk.Button(
            controls,
            text="Reset",
            width=5,
            style="CounterDanger.TButton",
            command=lambda: self._reset_counter_field(reset_key),
        ).pack(side="left", padx=5)
        ttk.Button(
            controls,
            text="+",
            width=2,
            style="CounterPrimary.TButton",
            command=lambda: self._post_counter_action(increment_action),
        ).pack(side="left")

    def _choose_counter_color(self) -> None:
        current = f"#{self.counter_accent_var.get()}"
        _rgb, selected = colorchooser.askcolor(
            color=current,
            parent=self.root,
            title="Choose counter accent",
        )
        if not selected:
            return
        self.counter_accent_var.set(selected.removeprefix("#").lower())
        self._update_counter_swatch()

    def _update_counter_swatch(self) -> None:
        value = self.counter_accent_var.get().removeprefix("#")
        if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
            value = "d7ff45"
            self.counter_accent_var.set(value)
        red, green, blue = (int(value[index : index + 2], 16) for index in (0, 2, 4))
        luminance = (red * 299 + green * 587 + blue * 114) / 1000
        foreground = "#101416" if luminance > 145 else "#ffffff"
        self.counter_accent_button.configure(
            text=f"#{value.upper()}",
            background=f"#{value}",
            activebackground=f"#{value}",
            foreground=foreground,
            activeforeground=foreground,
        )

    def _counter_request(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        request: str | urllib.request.Request
        url = f"{base_url()}api/win-loss"
        if payload is None:
            request = url
        else:
            request = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
        with urllib.request.urlopen(request, timeout=3) as response:
            return json.loads(response.read().decode("utf-8"))

    def _now_playing_request(self) -> dict[str, Any]:
        with urllib.request.urlopen(
            f"{base_url()}api/now-playing",
            timeout=3,
        ) as response:
            return json.loads(response.read().decode("utf-8"))

    def _load_now_playing_async(self) -> None:
        if self._now_playing_check_pending or not hasattr(
            self,
            "spotify_preview_title_var",
        ):
            return
        if not is_healthy():
            return
        self._now_playing_check_pending = True

        def worker() -> None:
            try:
                state = self._now_playing_request()
            except Exception:
                state = None
            self._dispatch(lambda: self._complete_now_playing_check(state))

        threading.Thread(
            target=worker,
            name="overlay-studio-now-playing",
            daemon=True,
        ).start()

    def _complete_now_playing_check(self, state: dict[str, Any] | None) -> None:
        self._now_playing_check_pending = False
        self._render_spotify_preview(state)

    @staticmethod
    def _preview_text(value: Any, maximum: int) -> str:
        text = " ".join(str(value or "").split())
        if len(text) <= maximum:
            return text
        return f"{text[: max(1, maximum - 3)].rstrip()}..."

    def _render_spotify_preview(self, state: dict[str, Any] | None) -> None:
        if not hasattr(self, "spotify_preview_title_var"):
            return
        playing = bool(state and state.get("isPlaying"))
        if playing:
            self.spotify_preview_title_var.set(
                self._preview_text(state.get("title"), 18) or "Unknown track"
            )
            self.spotify_preview_artist_var.set(
                self._preview_text(state.get("artist"), 20)
            )
        else:
            self.spotify_preview_title_var.set("waiting for a song...")
            self.spotify_preview_artist_var.set("")

        art_source = str(state.get("art") or "") if playing and state else ""
        if art_source != self._spotify_art_source:
            self._spotify_art_source = art_source
            self._spotify_art_image = None
            if art_source.startswith("data:image/") and "," in art_source:
                try:
                    encoded = art_source.split(",", 1)[1]
                    image = tk.PhotoImage(data=base64.b64decode(encoded))
                    factor = max(
                        1,
                        (max(image.width(), image.height()) + 55) // 56,
                    )
                    self._spotify_art_image = image.subsample(factor, factor)
                except (ValueError, tk.TclError):
                    self._spotify_art_image = None
            self.spotify_preview_art.configure(
                image=self._spotify_art_image or "",
                text="" if self._spotify_art_image else "SP",
            )

        progress = float(state.get("progressMs") or 0) if playing and state else 0
        duration = float(state.get("durationMs") or 0) if playing and state else 0
        self._spotify_progress_ratio = (
            max(0.0, min(1.0, progress / duration)) if duration > 0 else 0.0
        )
        self._paint_spotify_progress()

    def _paint_spotify_progress(self) -> None:
        if not hasattr(self, "spotify_preview_progress"):
            return
        width = max(1, self.spotify_preview_progress.winfo_width())
        self.spotify_preview_progress.coords(
            self.spotify_preview_progress_fill,
            0,
            0,
            int(width * self._spotify_progress_ratio),
            4,
        )

    def _load_counter_state_async(self) -> None:
        if self._counter_check_pending or not hasattr(self, "counter_wins_var"):
            return
        if not is_healthy():
            return
        self._counter_check_pending = True

        def worker() -> None:
            try:
                state = self._counter_request()
            except Exception:
                state = None
            self._dispatch(lambda: self._complete_counter_check(state))

        threading.Thread(target=worker, name="overlay-studio-counter-state", daemon=True).start()

    def _complete_counter_check(self, state: dict[str, Any] | None) -> None:
        self._counter_check_pending = False
        if state:
            self._render_counter_state(state)

    def _render_counter_state(self, state: dict[str, Any]) -> None:
        self.counter_title_var.set(str(state.get("title") or "MARVEL RIVALS"))
        wins = max(0, int(state.get("wins", 0)))
        losses = max(0, int(state.get("losses", 0)))
        self.counter_wins_var.set(str(wins))
        self.counter_losses_var.set(str(losses))
        self.library_counter_score_var.set(f"{wins} W   {losses} L")
        self.counter_accent_var.set(str(state.get("accent") or "d7ff45"))
        self._update_counter_swatch()

    def _post_counter_action(self, action: str) -> None:
        self._send_counter_update({"action": action})

    def _save_counter_settings(self) -> None:
        self._send_counter_update(
            {
                "title": self.counter_title_var.get(),
                "accent": self.counter_accent_var.get(),
            }
        )

    def _send_counter_update(self, payload: dict[str, Any]) -> None:
        if not is_healthy():
            messagebox.showerror(
                "Server is stopped",
                "Start the overlay server before updating the counter.",
                parent=self.root,
            )
            return

        def worker() -> None:
            try:
                state = self._counter_request(payload)
                self._dispatch(lambda: self._finish_counter_update(state))
            except Exception as exc:
                self._dispatch(
                    lambda error=exc: messagebox.showerror(
                        "Counter update failed",
                        str(error),
                        parent=self.root,
                    )
                )

        threading.Thread(target=worker, name="overlay-studio-counter-update", daemon=True).start()

    def _finish_counter_update(self, state: dict[str, Any]) -> None:
        self._render_counter_state(state)
        self._log(
            f"Match record updated: {state.get('wins', 0)} wins, {state.get('losses', 0)} losses"
        )

    def _reset_counter_field(self, key: str) -> None:
        self._send_counter_update({key: 0})

    def copy_counter_url(self) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(self.counter_url_var.get())
        self.root.update_idletasks()
        self._log("Win/loss OBS URL copied")

    def open_counter_preview(self) -> None:
        if not is_healthy():
            messagebox.showerror(
                "Server is stopped",
                "Start the overlay server before opening the preview.",
                parent=self.root,
            )
            return
        webbrowser.open(self.counter_url_var.get())

    def _form_label(self, parent: ttk.Frame, text: str, row: int) -> None:
        ttk.Label(parent, text=text, style="Muted.TLabel").grid(
            row=row,
            column=0,
            sticky="w",
            pady=(9 if row else 0, 0),
        )

    def _asset_picker(
        self,
        parent: ttk.Frame,
        label: str,
        kind: str,
        variable: tk.StringVar,
        row: int,
    ) -> None:
        self._form_label(parent, label, row)
        asset_row = ttk.Frame(parent, style="Panel.TFrame")
        asset_row.grid(row=row, column=1, sticky="ew", padx=(16, 0), pady=(9, 0))
        asset_row.columnconfigure(0, weight=1)
        ttk.Entry(asset_row, textvariable=variable, state="readonly").grid(
            row=0, column=0, sticky="ew"
        )
        ttk.Button(
            asset_row,
            text="Browse",
            style="Secondary.TButton",
            command=lambda: self._choose_asset(kind),
        ).grid(row=0, column=1, padx=(7, 0))
        ttk.Button(
            asset_row,
            text="Default",
            style="Secondary.TButton",
            command=lambda: self._default_asset(kind),
        ).grid(row=0, column=2, padx=(7, 0))

    def _load_customization(self, config: dict[str, Any] | None = None) -> None:
        saved = normalize_overlay_config(config or load_overlay_config(OVERLAY_CONFIG_PATH))
        dance = saved["dance"]
        spotify = saved["spotify"]
        self.dance_position_var.set(inverse_lookup(POSITION_OPTIONS, dance["position"]))
        self.spotify_position_var.set(inverse_lookup(POSITION_OPTIONS, spotify["position"]))
        self.gif_asset_var.set(dance["gif"])
        self.rest_asset_var.set(dance["rest"])
        self.dance_scale_var.set(dance["scale"])
        self.spotify_scale_var.set(spotify["scale"])
        self.card_width_var.set(spotify["cardWidth"])
        self.color_mode_var.set(inverse_lookup(COLOR_MODE_OPTIONS, spotify["colorMode"]))
        for key, value in spotify["colors"].items():
            self.color_vars[key].set(value)
            self._update_swatch(key)
        self.sensitivity_var.set(saved["audio"]["sensitivity"])
        self._update_sensitivity_text(saved["audio"]["sensitivity"])
        self.fallback_bpm_var.set(saved["nowPlaying"]["fallbackBpm"])
        self._pending_assets = {"gif": None, "rest": None}

    def reset_dance_fields(self) -> None:
        dance = DEFAULT_OVERLAY_CONFIG["dance"]
        self.dance_position_var.set(inverse_lookup(POSITION_OPTIONS, dance["position"]))
        self.gif_asset_var.set(dance["gif"])
        self.rest_asset_var.set(dance["rest"])
        self.dance_scale_var.set(dance["scale"])
        self.sensitivity_var.set(DEFAULT_OVERLAY_CONFIG["audio"]["sensitivity"])
        self._update_sensitivity_text(DEFAULT_OVERLAY_CONFIG["audio"]["sensitivity"])
        self.fallback_bpm_var.set(DEFAULT_OVERLAY_CONFIG["nowPlaying"]["fallbackBpm"])
        self._pending_assets = {"gif": None, "rest": None}
        self._log("Dance fields reset; save to apply")

    def reset_spotify_fields(self) -> None:
        spotify = DEFAULT_OVERLAY_CONFIG["spotify"]
        self.spotify_position_var.set(inverse_lookup(POSITION_OPTIONS, spotify["position"]))
        self.spotify_scale_var.set(spotify["scale"])
        self.card_width_var.set(spotify["cardWidth"])
        self.color_mode_var.set(inverse_lookup(COLOR_MODE_OPTIONS, spotify["colorMode"]))
        for key, value in spotify["colors"].items():
            self.color_vars[key].set(value)
            self._update_swatch(key)
        self._log("Spotify fields reset; save to apply")

    def _choose_asset(self, kind: str) -> None:
        selected = filedialog.askopenfilename(
            parent=self.root,
            title="Choose a dance GIF" if kind == "gif" else "Choose a resting image",
            filetypes=DANCE_FILE_TYPES if kind == "gif" else REST_FILE_TYPES,
        )
        if not selected:
            return
        source = Path(selected)
        allowed_extensions = (
            ALLOWED_ASSET_EXTENSIONS if kind == "gif" else REST_ASSET_EXTENSIONS
        )
        if source.suffix.lower() not in allowed_extensions:
            messagebox.showerror(
                "Unsupported file",
                (
                    "Choose a GIF, WebP, APNG, WebM, MP4, or MOV file."
                    if kind == "gif"
                    else "Choose a PNG, GIF, WebP, or APNG image."
                ),
                parent=self.root,
            )
            return
        self._pending_assets[kind] = source
        variable = self.gif_asset_var if kind == "gif" else self.rest_asset_var
        variable.set(source.name)

    def _default_asset(self, kind: str) -> None:
        self._pending_assets[kind] = None
        default = DEFAULT_OVERLAY_CONFIG["dance"][kind]
        variable = self.gif_asset_var if kind == "gif" else self.rest_asset_var
        variable.set(default)

    def _choose_color(self, key: str) -> None:
        current = f"#{self.color_vars[key].get()}"
        _rgb, selected = colorchooser.askcolor(color=current, parent=self.root, title="Choose color")
        if not selected:
            return
        self.color_vars[key].set(selected.removeprefix("#").lower())
        self._update_swatch(key)

    def _update_swatch(self, key: str) -> None:
        value = self.color_vars[key].get().removeprefix("#")
        if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
            value = DEFAULT_OVERLAY_CONFIG["spotify"]["colors"][key]
        red, green, blue = (int(value[index : index + 2], 16) for index in (0, 2, 4))
        luminance = (red * 299 + green * 587 + blue * 114) / 1000
        foreground = "#172126" if luminance > 145 else "#ffffff"
        self._swatch_buttons[key].configure(
            text=f"#{value.upper()}",
            background=f"#{value}",
            activebackground=f"#{value}",
            foreground=foreground,
            activeforeground=foreground,
        )

    def _update_sensitivity_text(self, value: Any) -> None:
        try:
            self.sensitivity_text_var.set(f"{float(value):.2f}")
        except (TypeError, ValueError):
            self.sensitivity_text_var.set("1.00")

    def _gather_customization(self) -> dict[str, Any]:
        return normalize_overlay_config(
            {
                "dance": {
                    "gif": self.gif_asset_var.get(),
                    "rest": self.rest_asset_var.get(),
                    "position": POSITION_OPTIONS.get(
                        self.dance_position_var.get(),
                        "bottom-left",
                    ),
                    "scale": self.dance_scale_var.get(),
                },
                "spotify": {
                    "position": POSITION_OPTIONS.get(
                        self.spotify_position_var.get(),
                        "bottom-left",
                    ),
                    "scale": self.spotify_scale_var.get(),
                    "cardWidth": self.card_width_var.get(),
                    "colorMode": COLOR_MODE_OPTIONS.get(self.color_mode_var.get(), "auto"),
                    "colors": {key: variable.get() for key, variable in self.color_vars.items()},
                },
                "audio": {
                    "enabled": True,
                    "sensitivity": self.sensitivity_var.get(),
                },
                "nowPlaying": {
                    "fallbackBpm": self.fallback_bpm_var.get(),
                },
            }
        )

    def _materialize_asset(self, kind: str, current_value: str) -> str:
        source = self._pending_assets[kind]
        if source is None:
            return current_value
        USER_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        cleaned_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", source.stem).strip(".-") or kind
        destination_name = f"{cleaned_stem}{source.suffix.lower()}"
        destination = USER_ASSETS_DIR / destination_name
        if source.resolve() != destination.resolve():
            shutil.copy2(source, destination)
        return f"user-assets/{destination_name}"

    def save_customization(self) -> None:
        if self._busy:
            return
        try:
            submitted = self._gather_customization()
        except (tk.TclError, ValueError):
            messagebox.showerror(
                "Check the values",
                "Scale, player width, sensitivity, and BPM must be numbers.",
                parent=self.root,
            )
            return

        pending_assets = dict(self._pending_assets)
        self._set_busy(True)
        self._log("Saving customization")

        def worker() -> None:
            self._pending_assets = pending_assets
            try:
                submitted["dance"]["gif"] = self._materialize_asset(
                    "gif", submitted["dance"]["gif"]
                )
                submitted["dance"]["rest"] = self._materialize_asset(
                    "rest", submitted["dance"]["rest"]
                )
                saved = save_overlay_config(OVERLAY_CONFIG_PATH, submitted)

                server_config = load_json(SERVER_CONFIG_PATH, SERVER_CONFIG_EXAMPLE_PATH)
                audio = server_config.setdefault("audio", {})
                if isinstance(audio, dict):
                    audio["sensitivity"] = saved["audio"]["sensitivity"]
                save_json(SERVER_CONFIG_PATH, server_config)

                applied_live = False
                if is_healthy():
                    request = urllib.request.Request(
                        f"{base_url()}api/config",
                        data=json.dumps(saved).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with urllib.request.urlopen(request, timeout=3) as response:
                        applied_live = response.status == 200
                self._dispatch(lambda: self._finish_save(saved, applied_live))
            except Exception as exc:
                self._dispatch(lambda error=exc: self._finish_action(False, f"Save failed: {error}"))

        threading.Thread(target=worker, name="overlay-studio-save", daemon=True).start()

    def _finish_save(self, saved: dict[str, Any], applied_live: bool) -> None:
        self._load_customization(saved)
        self._set_busy(False)
        if applied_live:
            self._log("Customization saved and applied")
            self.server_state_var.set("Running; customization applied")
        else:
            self._log("Customization saved; it will apply when the server starts")
            self.server_state_var.set("Customization saved")

    def _update_overlay_urls(self) -> None:
        self.address_var.set(base_url())
        self.dance_url_var.set(f"{base_url()}overlays/larpdog-dance")
        self.spotify_url_var.set(f"{base_url()}overlays/spotify")

    def copy_overlay_url(self, variable: tk.StringVar, label: str) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(variable.get())
        self.root.update_idletasks()
        self._log(f"{label} URL copied")

    def open_overlay_preview(self, variable: tk.StringVar) -> None:
        if not is_healthy():
            self.start_server(open_after=variable.get())
            return
        webbrowser.open(variable.get())
        self._log("Opened overlay preview")

    def open_user_assets(self) -> None:
        USER_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        self._open_folder(USER_ASSETS_DIR)

    def _open_folder(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            webbrowser.open(path.as_uri())

    def start_server(self, open_after: str | bool = False) -> None:
        if self._busy:
            return
        self._set_busy(True)
        self._log("Starting overlay server")

        def worker() -> None:
            success, detail = self._start_server_blocking()
            self._dispatch(lambda: self._finish_action(success, detail, open_after))

        threading.Thread(target=worker, name="overlay-studio-start", daemon=True).start()

    def stop_server(self) -> None:
        if self._busy:
            return
        self._set_busy(True)
        self._log("Stopping overlay server")

        def worker() -> None:
            success, detail = self._stop_server_blocking()
            self._dispatch(lambda: self._finish_action(success, detail))

        threading.Thread(target=worker, name="overlay-studio-stop", daemon=True).start()

    def restart_server(self) -> None:
        if self._busy:
            return
        self._set_busy(True)
        self._log("Restarting overlay server")

        def worker() -> None:
            stopped, stop_detail = self._stop_server_blocking()
            if not stopped:
                self._dispatch(lambda: self._finish_action(False, stop_detail))
                return
            started, start_detail = self._start_server_blocking()
            self._dispatch(lambda: self._finish_action(started, start_detail))

        threading.Thread(target=worker, name="overlay-studio-restart", daemon=True).start()

    def _python_executable(self) -> Path | None:
        preferred = SERVER_DIR / ".venv" / "Scripts" / "python.exe"
        if preferred.exists():
            return preferred
        current = Path(sys.executable)
        if current.name.lower() == "pythonw.exe":
            console_python = current.with_name("python.exe")
            if console_python.exists():
                return console_python
        return current if current.exists() else None

    def _start_server_blocking(self) -> tuple[bool, str]:
        if is_healthy():
            return True, "Server is already running"
        python_executable = self._python_executable()
        if python_executable is None:
            return False, "Python environment is missing"

        try:
            with LOG_PATH.open("a", encoding="utf-8") as output, ERROR_LOG_PATH.open(
                "a", encoding="utf-8"
            ) as errors:
                process = subprocess.Popen(
                    [
                        str(python_executable),
                        "-u",
                        str(SERVER_DIR / "main.py"),
                        "--config",
                        str(SERVER_CONFIG_PATH),
                    ],
                    cwd=SERVER_DIR,
                    stdout=output,
                    stderr=errors,
                    **hidden_process_options(),
                )
            PID_PATH.write_text(str(process.pid), encoding="ascii")
        except OSError as exc:
            return False, f"Could not start server: {exc}"

        deadline = time.monotonic() + 9
        while time.monotonic() < deadline:
            if is_healthy():
                return True, f"Running at {base_url()}"
            if process.poll() is not None:
                return False, "Server exited while starting; check the log folder"
            time.sleep(0.25)
        return False, "Server did not become ready; check the log folder"

    def _stop_server_blocking(self) -> tuple[bool, str]:
        if not is_healthy():
            PID_PATH.unlink(missing_ok=True)
            return True, "Server is stopped"

        process_ids: list[int] = []
        try:
            process_ids.append(int(PID_PATH.read_text(encoding="ascii").strip()))
        except (OSError, ValueError):
            pass
        listener_pid = self._listener_pid(server_address()[1])
        if listener_pid is not None and listener_pid not in process_ids:
            process_ids.append(listener_pid)
        if not process_ids:
            return False, "Could not identify the local server process"

        for process_id in process_ids:
            subprocess.run(
                ["taskkill", "/PID", str(process_id), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                **hidden_process_options(),
            )

        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            if not is_healthy():
                PID_PATH.unlink(missing_ok=True)
                return True, "Server stopped"
            time.sleep(0.2)
        return False, "Server is still running"

    def _listener_pid(self, port: int) -> int | None:
        try:
            output = subprocess.check_output(
                ["netstat", "-ano", "-p", "tcp"],
                text=True,
                encoding="utf-8",
                errors="replace",
                **hidden_process_options(),
            )
        except (OSError, subprocess.SubprocessError):
            return None
        pattern = re.compile(
            rf"^\s*TCP\s+\S+:{port}\s+\S+\s+LISTENING\s+(\d+)\s*$",
            re.IGNORECASE,
        )
        for line in output.splitlines():
            match = pattern.match(line)
            if match:
                return int(match.group(1))
        return None

    def _finish_action(
        self,
        success: bool,
        detail: str,
        open_after: str | bool = False,
    ) -> None:
        self._set_busy(False)
        self._log(detail)
        running = is_healthy()
        self._render_health(running)
        if not success:
            messagebox.showerror("Overlay Studio", detail, parent=self.root)
        elif open_after and running:
            preview_url = open_after if isinstance(open_after, str) else self.dance_url_var.get()
            webbrowser.open(preview_url)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        buttons = [
            self.header_start_button,
            self.start_button,
            self.stop_button,
            self.restart_button,
            *self.save_buttons,
        ]
        for button in buttons:
            button.configure(state=state)

    def _schedule_health_check(self) -> None:
        if self._health_check_pending:
            return
        self._health_check_pending = True

        def worker() -> None:
            running = is_healthy()
            self._dispatch(lambda: self._complete_health_check(running))

        threading.Thread(target=worker, name="overlay-studio-health", daemon=True).start()

    def _complete_health_check(self, running: bool) -> None:
        self._health_check_pending = False
        self._render_health(running)
        if running:
            self._load_counter_state_async()
            self._load_now_playing_async()
        self.root.after(2500, self._schedule_health_check)

    def _render_health(self, running: bool) -> None:
        self.address_var.set(base_url())
        self._update_overlay_urls()
        self.counter_url_var.set(f"{base_url()}overlays/win-loss")
        self.status_dot.itemconfigure(self.status_circle, fill=GOOD if running else STOPPED)
        self.status_var.set("Running" if running else "Stopped")
        if not running:
            self._render_spotify_preview(None)
        for overlay_kind, status_var in self._overlay_status_vars.items():
            status_var.set("RUNNING" if running else "OFFLINE")
            dot_canvas, dot_circle = self._overlay_status_dots[overlay_kind]
            dot_canvas.itemconfigure(dot_circle, fill=GOOD if running else STOPPED)
            self._overlay_status_labels[overlay_kind].configure(
                foreground=GOOD if running else STOPPED
            )
        if not self._busy:
            self.server_state_var.set(
                "Ready for OBS and Spotify" if running else "Not running"
            )
            self.start_button.configure(state="disabled" if running else "normal")
            self.stop_button.configure(state="normal" if running else "disabled")
            self.restart_button.configure(state="normal" if running else "disabled")
            self.header_start_button.configure(
                text="Server ready" if running else "Start server",
                state="disabled" if running else "normal",
            )

    def _dispatch(self, callback: Callable[[], None]) -> None:
        try:
            self.root.after(0, callback)
        except tk.TclError:
            pass

    def _log(self, message: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self.activity_text.configure(state="normal")
        self.activity_text.insert("end", f"{timestamp}  {message}\n")
        self.activity_text.see("end")
        self.activity_text.configure(state="disabled")


def main() -> None:
    root = tk.Tk()
    OverlayStudio(root)
    root.mainloop()


if __name__ == "__main__":
    main()
