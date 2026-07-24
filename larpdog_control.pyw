from __future__ import annotations

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


BACKGROUND = "#f2f5f5"
PANEL = "#ffffff"
INK = "#182327"
MUTED = "#65747a"
ACCENT = "#087f83"
ACCENT_DARK = "#05686b"
GOOD = "#169873"
STOPPED = "#d05f55"
BORDER = "#d8e0e1"

DISPLAY_OPTIONS = {
    "Dog + player": "both",
    "Dog only": "dog",
    "Player only": "player",
}
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
OBS_VIEW_OPTIONS = {
    "Saved layout": "",
    "Dog + player": "?asset=both",
    "Dog only": "?asset=dog",
    "Player only": "?asset=player",
}
ASSET_FILE_TYPES = [
    ("Character media", "*.gif *.webp *.apng *.png *.webm *.mp4 *.mov"),
    ("All files", "*.*"),
]
ALLOWED_ASSET_EXTENSIONS = {".gif", ".webp", ".apng", ".png", ".webm", ".mp4", ".mov"}


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
        return response.status == 200 and payload.get("app") == "larpdog-server"
    except (OSError, ValueError, urllib.error.URLError):
        return False


def hidden_process_options() -> dict[str, Any]:
    if sys.platform != "win32":
        return {}
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}


class LarpdogControl:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Larpdog Control")
        self.root.geometry("820x720")
        self.root.minsize(740, 640)
        self.root.configure(background=BACKGROUND)

        self._busy = False
        self._health_check_pending = False
        self._pending_assets: dict[str, Path | None] = {"dog": None, "rest": None}
        self._swatch_buttons: dict[str, tk.Button] = {}

        self._setup_styles()
        self._set_window_icon()
        self._build_ui()
        self._load_customization()
        self._update_obs_url()
        self.root.after(150, self._schedule_health_check)

    def _setup_styles(self) -> None:
        style = ttk.Style(self.root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

        style.configure(".", font=("Segoe UI", 10), background=BACKGROUND, foreground=INK)
        style.configure("App.TFrame", background=BACKGROUND)
        style.configure("Panel.TFrame", background=PANEL)
        style.configure("Header.TLabel", background=BACKGROUND, foreground=INK, font=("Segoe UI Semibold", 20))
        style.configure("Subheader.TLabel", background=BACKGROUND, foreground=MUTED, font=("Segoe UI", 10))
        style.configure("PanelTitle.TLabel", background=PANEL, foreground=INK, font=("Segoe UI Semibold", 11))
        style.configure("Panel.TLabel", background=PANEL, foreground=INK)
        style.configure("Muted.TLabel", background=PANEL, foreground=MUTED)
        style.configure("Status.TLabel", background=BACKGROUND, foreground=INK, font=("Segoe UI Semibold", 10))
        style.configure("TNotebook", background=BACKGROUND, borderwidth=0, tabmargins=(0, 8, 0, 0))
        style.configure("TNotebook.Tab", padding=(18, 9), font=("Segoe UI Semibold", 10))
        style.map(
            "TNotebook.Tab",
            background=[("selected", PANEL), ("!selected", "#e5ebeb")],
            foreground=[("selected", INK), ("!selected", MUTED)],
        )
        style.configure("Primary.TButton", background=ACCENT, foreground="#ffffff", padding=(15, 9))
        style.map(
            "Primary.TButton",
            background=[("active", ACCENT_DARK), ("disabled", "#9ebabb")],
            foreground=[("disabled", "#edf4f4")],
        )
        style.configure("Secondary.TButton", background="#e7eeee", foreground=INK, padding=(13, 8))
        style.map("Secondary.TButton", background=[("active", "#d8e4e4")])
        style.configure("Danger.TButton", background="#f4e4e2", foreground="#9b3f38", padding=(13, 8))
        style.map("Danger.TButton", background=[("active", "#ead2cf")])
        style.configure("TCheckbutton", background=PANEL, foreground=INK)
        style.configure("Horizontal.TScale", background=PANEL, troughcolor="#dbe4e4")

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
        shell = ttk.Frame(self.root, style="App.TFrame", padding=(24, 20, 24, 20))
        shell.pack(fill="both", expand=True)

        header = ttk.Frame(shell, style="App.TFrame")
        header.pack(fill="x")
        title_block = ttk.Frame(header, style="App.TFrame")
        title_block.pack(side="left", fill="x", expand=True)
        ttk.Label(title_block, text="Larpdog Control", style="Header.TLabel").pack(anchor="w")
        ttk.Label(
            title_block,
            text="Spotify overlay companion",
            style="Subheader.TLabel",
        ).pack(anchor="w", pady=(1, 0))

        status_block = ttk.Frame(header, style="App.TFrame")
        status_block.pack(side="right", padx=(16, 0))
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
        self.notebook.pack(fill="both", expand=True, pady=(14, 0))
        self.control_tab = ttk.Frame(self.notebook, style="App.TFrame", padding=(0, 14, 0, 0))
        self.customize_tab = ttk.Frame(self.notebook, style="App.TFrame", padding=(0, 14, 0, 0))
        self.notebook.add(self.control_tab, text="Control")
        self.notebook.add(self.customize_tab, text="Customize")

        self._build_control_tab()
        self._build_customize_tab()

    def _panel(self, parent: ttk.Frame, title: str) -> ttk.Frame:
        panel = ttk.Frame(parent, style="Panel.TFrame", padding=18)
        panel.pack(fill="x", pady=(0, 12))
        ttk.Label(panel, text=title, style="PanelTitle.TLabel").pack(anchor="w", pady=(0, 12))
        return panel

    def _build_control_tab(self) -> None:
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
            text="Open preview",
            style="Secondary.TButton",
            command=self.open_preview,
        ).pack(side="right")

        obs_panel = self._panel(self.control_tab, "OBS browser source")
        view_row = ttk.Frame(obs_panel, style="Panel.TFrame")
        view_row.pack(fill="x")
        ttk.Label(view_row, text="View", style="Muted.TLabel").pack(side="left")
        self.obs_view_var = tk.StringVar(value="Saved layout")
        view_combo = ttk.Combobox(
            view_row,
            textvariable=self.obs_view_var,
            values=list(OBS_VIEW_OPTIONS),
            state="readonly",
            width=20,
        )
        view_combo.pack(side="left", padx=(18, 0))
        view_combo.bind("<<ComboboxSelected>>", lambda _event: self._update_obs_url())

        url_row = ttk.Frame(obs_panel, style="Panel.TFrame")
        url_row.pack(fill="x", pady=(12, 0))
        self.obs_url_var = tk.StringVar()
        obs_entry = ttk.Entry(url_row, textvariable=self.obs_url_var, state="readonly")
        obs_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(
            url_row,
            text="Copy URL",
            style="Primary.TButton",
            command=self.copy_obs_url,
        ).pack(side="left", padx=(8, 0))

        tools = ttk.Frame(obs_panel, style="Panel.TFrame")
        tools.pack(fill="x", pady=(10, 0))
        ttk.Button(
            tools,
            text="Open user assets",
            style="Secondary.TButton",
            command=self.open_user_assets,
        ).pack(side="left")
        ttk.Button(
            tools,
            text="Open log folder",
            style="Secondary.TButton",
            command=lambda: self._open_folder(SERVER_DIR),
        ).pack(side="left", padx=(8, 0))

        activity_panel = self._panel(self.control_tab, "Activity")
        self.activity_text = tk.Text(
            activity_panel,
            height=7,
            background="#f7f9f9",
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
        self._log("Control app opened")

    def _build_customize_tab(self) -> None:
        self.customize_canvas = tk.Canvas(
            self.customize_tab,
            background=BACKGROUND,
            highlightthickness=0,
            borderwidth=0,
        )
        customize_scrollbar = ttk.Scrollbar(
            self.customize_tab,
            orient="vertical",
            command=self.customize_canvas.yview,
        )
        self.customize_canvas.configure(yscrollcommand=customize_scrollbar.set)
        customize_scrollbar.pack(side="right", fill="y")
        self.customize_canvas.pack(side="left", fill="both", expand=True)

        content = ttk.Frame(self.customize_canvas, style="App.TFrame")
        content_window = self.customize_canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind(
            "<Configure>",
            lambda _event: self.customize_canvas.configure(
                scrollregion=self.customize_canvas.bbox("all")
            ),
        )
        self.customize_canvas.bind(
            "<Configure>",
            lambda event: self.customize_canvas.itemconfigure(
                content_window,
                width=event.width,
            ),
        )
        content.bind(
            "<Enter>",
            lambda _event: self.root.bind_all("<MouseWheel>", self._scroll_customize),
        )
        content.bind(
            "<Leave>",
            lambda _event: self.root.unbind_all("<MouseWheel>"),
        )

        character_panel = self._panel(content, "Character and layout")
        character_grid = ttk.Frame(character_panel, style="Panel.TFrame")
        character_grid.pack(fill="x")
        character_grid.columnconfigure(1, weight=1)

        self.display_var = tk.StringVar()
        self.position_var = tk.StringVar()
        self.dog_asset_var = tk.StringVar()
        self.rest_asset_var = tk.StringVar()

        self._form_label(character_grid, "Display", 0)
        ttk.Combobox(
            character_grid,
            textvariable=self.display_var,
            values=list(DISPLAY_OPTIONS),
            state="readonly",
            width=24,
        ).grid(row=0, column=1, sticky="ew", padx=(16, 0))
        self._form_label(character_grid, "Position", 1)
        ttk.Combobox(
            character_grid,
            textvariable=self.position_var,
            values=list(POSITION_OPTIONS),
            state="readonly",
            width=24,
        ).grid(row=1, column=1, sticky="ew", padx=(16, 0), pady=(9, 0))

        self._asset_picker(character_grid, "Dancing media", "dog", self.dog_asset_var, 2)
        self._asset_picker(character_grid, "Resting image", "rest", self.rest_asset_var, 3)

        appearance_panel = self._panel(content, "Appearance")
        appearance_grid = ttk.Frame(appearance_panel, style="Panel.TFrame")
        appearance_grid.pack(fill="x")
        appearance_grid.columnconfigure(1, weight=1)

        self.scale_var = tk.DoubleVar(value=1.0)
        self.card_width_var = tk.IntVar(value=335)
        self.color_mode_var = tk.StringVar()
        self.color_vars = {
            "a": tk.StringVar(value="ff4d9d"),
            "b": tk.StringVar(value="ffd24a"),
            "c": tk.StringVar(value="5ee0ff"),
        }

        self._form_label(appearance_grid, "Scale", 0)
        ttk.Spinbox(
            appearance_grid,
            textvariable=self.scale_var,
            from_=0.5,
            to=2.0,
            increment=0.05,
            width=10,
        ).grid(row=0, column=1, sticky="w", padx=(16, 0))
        self._form_label(appearance_grid, "Player width", 1)
        ttk.Spinbox(
            appearance_grid,
            textvariable=self.card_width_var,
            from_=240,
            to=600,
            increment=5,
            width=10,
        ).grid(row=1, column=1, sticky="w", padx=(16, 0), pady=(9, 0))
        self._form_label(appearance_grid, "Color behavior", 2)
        ttk.Combobox(
            appearance_grid,
            textvariable=self.color_mode_var,
            values=list(COLOR_MODE_OPTIONS),
            state="readonly",
            width=24,
        ).grid(row=2, column=1, sticky="w", padx=(16, 0), pady=(9, 0))

        self._form_label(appearance_grid, "Palette", 3)
        swatches = ttk.Frame(appearance_grid, style="Panel.TFrame")
        swatches.grid(row=3, column=1, sticky="w", padx=(16, 0), pady=(10, 0))
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

        motion_panel = self._panel(content, "Motion")
        motion_grid = ttk.Frame(motion_panel, style="Panel.TFrame")
        motion_grid.pack(fill="x")
        motion_grid.columnconfigure(1, weight=1)

        self.sensitivity_var = tk.DoubleVar(value=1.0)
        self.sensitivity_text_var = tk.StringVar(value="1.00")
        self.fallback_bpm_var = tk.IntVar(value=120)
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

        save_bar = ttk.Frame(content, style="App.TFrame")
        save_bar.pack(fill="x", pady=(0, 8))
        self.save_button = ttk.Button(
            save_bar,
            text="Save and apply",
            style="Primary.TButton",
            command=self.save_customization,
        )
        self.save_button.pack(side="right")
        ttk.Button(
            save_bar,
            text="Reset fields",
            style="Secondary.TButton",
            command=self.reset_customization_fields,
        ).pack(side="right", padx=(0, 8))

    def _scroll_customize(self, event: tk.Event[Any]) -> str:
        self.customize_canvas.yview_scroll(int(-event.delta / 120), "units")
        return "break"

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
        appearance = saved["appearance"]
        self.display_var.set(inverse_lookup(DISPLAY_OPTIONS, appearance["asset"]))
        self.position_var.set(inverse_lookup(POSITION_OPTIONS, appearance["position"]))
        self.dog_asset_var.set(appearance["dog"])
        self.rest_asset_var.set(appearance["rest"])
        self.scale_var.set(appearance["scale"])
        self.card_width_var.set(appearance["cardWidth"])
        self.color_mode_var.set(inverse_lookup(COLOR_MODE_OPTIONS, appearance["colorMode"]))
        for key, value in appearance["colors"].items():
            self.color_vars[key].set(value)
            self._update_swatch(key)
        self.sensitivity_var.set(saved["audio"]["sensitivity"])
        self._update_sensitivity_text(saved["audio"]["sensitivity"])
        self.fallback_bpm_var.set(saved["nowPlaying"]["fallbackBpm"])
        self._pending_assets = {"dog": None, "rest": None}

    def reset_customization_fields(self) -> None:
        self._load_customization(DEFAULT_OVERLAY_CONFIG)
        self._log("Customization fields reset; save to apply")

    def _choose_asset(self, kind: str) -> None:
        selected = filedialog.askopenfilename(
            parent=self.root,
            title="Choose character media",
            filetypes=ASSET_FILE_TYPES,
        )
        if not selected:
            return
        source = Path(selected)
        if source.suffix.lower() not in ALLOWED_ASSET_EXTENSIONS:
            messagebox.showerror(
                "Unsupported file",
                "Choose a PNG, GIF, WebP, APNG, WebM, MP4, or MOV file.",
                parent=self.root,
            )
            return
        self._pending_assets[kind] = source
        variable = self.dog_asset_var if kind == "dog" else self.rest_asset_var
        variable.set(source.name)

    def _default_asset(self, kind: str) -> None:
        self._pending_assets[kind] = None
        default = DEFAULT_OVERLAY_CONFIG["appearance"][kind]
        variable = self.dog_asset_var if kind == "dog" else self.rest_asset_var
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
            value = DEFAULT_OVERLAY_CONFIG["appearance"]["colors"][key]
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
                "appearance": {
                    "asset": DISPLAY_OPTIONS.get(self.display_var.get(), "both"),
                    "dog": self.dog_asset_var.get(),
                    "rest": self.rest_asset_var.get(),
                    "position": POSITION_OPTIONS.get(self.position_var.get(), "bottom-left"),
                    "scale": self.scale_var.get(),
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
                submitted["appearance"]["dog"] = self._materialize_asset(
                    "dog", submitted["appearance"]["dog"]
                )
                submitted["appearance"]["rest"] = self._materialize_asset(
                    "rest", submitted["appearance"]["rest"]
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

        threading.Thread(target=worker, name="larpdog-save", daemon=True).start()

    def _finish_save(self, saved: dict[str, Any], applied_live: bool) -> None:
        self._load_customization(saved)
        self._set_busy(False)
        if applied_live:
            self._log("Customization saved and applied")
            self.server_state_var.set("Running; customization applied")
        else:
            self._log("Customization saved; it will apply when the server starts")
            self.server_state_var.set("Customization saved")

    def _update_obs_url(self) -> None:
        self.address_var.set(base_url())
        suffix = OBS_VIEW_OPTIONS.get(self.obs_view_var.get(), "")
        self.obs_url_var.set(f"{base_url()}{suffix}")

    def copy_obs_url(self) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(self.obs_url_var.get())
        self.root.update_idletasks()
        self._log("OBS URL copied")

    def open_preview(self) -> None:
        if not is_healthy():
            self.start_server(open_after=True)
            return
        webbrowser.open(self.obs_url_var.get())
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

    def start_server(self, open_after: bool = False) -> None:
        if self._busy:
            return
        self._set_busy(True)
        self._log("Starting overlay server")

        def worker() -> None:
            success, detail = self._start_server_blocking()
            self._dispatch(lambda: self._finish_action(success, detail, open_after))

        threading.Thread(target=worker, name="larpdog-start", daemon=True).start()

    def stop_server(self) -> None:
        if self._busy:
            return
        self._set_busy(True)
        self._log("Stopping overlay server")

        def worker() -> None:
            success, detail = self._stop_server_blocking()
            self._dispatch(lambda: self._finish_action(success, detail))

        threading.Thread(target=worker, name="larpdog-stop", daemon=True).start()

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

        threading.Thread(target=worker, name="larpdog-restart", daemon=True).start()

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

    def _finish_action(self, success: bool, detail: str, open_after: bool = False) -> None:
        self._set_busy(False)
        self._log(detail)
        running = is_healthy()
        self._render_health(running)
        if not success:
            messagebox.showerror("Larpdog Control", detail, parent=self.root)
        elif open_after and running:
            webbrowser.open(self.obs_url_var.get())

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        state = "disabled" if busy else "normal"
        for button in (self.start_button, self.stop_button, self.restart_button, self.save_button):
            button.configure(state=state)

    def _schedule_health_check(self) -> None:
        if self._health_check_pending:
            return
        self._health_check_pending = True

        def worker() -> None:
            running = is_healthy()
            self._dispatch(lambda: self._complete_health_check(running))

        threading.Thread(target=worker, name="larpdog-health", daemon=True).start()

    def _complete_health_check(self, running: bool) -> None:
        self._health_check_pending = False
        self._render_health(running)
        self.root.after(2500, self._schedule_health_check)

    def _render_health(self, running: bool) -> None:
        self.address_var.set(base_url())
        self._update_obs_url()
        self.status_dot.itemconfigure(self.status_circle, fill=GOOD if running else STOPPED)
        self.status_var.set("Running" if running else "Stopped")
        if not self._busy:
            self.server_state_var.set(
                "Ready for OBS and Spotify" if running else "Not running"
            )
            self.start_button.configure(state="disabled" if running else "normal")
            self.stop_button.configure(state="normal" if running else "disabled")
            self.restart_button.configure(state="normal" if running else "disabled")

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
    LarpdogControl(root)
    root.mainloop()


if __name__ == "__main__":
    main()
