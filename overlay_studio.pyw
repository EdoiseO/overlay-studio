from __future__ import annotations

import contextlib
import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from pathlib import Path
from typing import Any

import webview


ROOT_DIR = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", ROOT_DIR))
SERVER_DIR = ROOT_DIR / "larpdog-server"
SERVER_CONFIG_PATH = SERVER_DIR / "config.json"
SERVER_CONFIG_EXAMPLE_PATH = SERVER_DIR / "config.example.json"
OVERLAY_CONFIG_PATH = SERVER_DIR / "overlay-config.json"
APP_SETTINGS_PATH = SERVER_DIR / "app-settings.json"
COUNTER_STATE_PATH = SERVER_DIR / "win-loss.json"
USER_ASSETS_DIR = ROOT_DIR / "user-assets"
PID_PATH = SERVER_DIR / "server.pid"
LOG_PATH = SERVER_DIR / "server.log"
ERROR_LOG_PATH = SERVER_DIR / "server.err"
STUDIO_UI_PATH = RESOURCE_DIR / "studio" / "index.html"

sys.path.insert(0, str(SERVER_DIR))
from counter_store import load_counter_state  # noqa: E402
from overlay_config import (  # noqa: E402
    DEFAULT_OVERLAY_CONFIG,
    load_overlay_config,
    normalize_overlay_config,
    save_overlay_config as save_overlay_config_file,
)


ALLOWED_DANCE_EXTENSIONS = {
    ".gif",
    ".webp",
    ".apng",
    ".png",
    ".webm",
    ".mp4",
    ".mov",
}
ALLOWED_REST_EXTENSIONS = {".gif", ".webp", ".apng", ".png"}


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


def request_json(
    path: str,
    payload: dict[str, Any] | None = None,
    timeout: float = 3,
) -> dict[str, Any]:
    target = urllib.parse.urljoin(base_url(), path.lstrip("/"))
    request: str | urllib.request.Request = target
    if payload is not None:
        request = urllib.request.Request(
            target,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        value = json.loads(response.read().decode("utf-8"))
    return value if isinstance(value, dict) else {}


def is_healthy(timeout: float = 0.6) -> bool:
    try:
        payload = request_json("/health", timeout=timeout)
        return payload.get("app") == "overlay-studio-server"
    except (OSError, ValueError, urllib.error.URLError):
        return False


def hidden_process_options() -> dict[str, Any]:
    if sys.platform != "win32":
        return {}
    return {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)}


class DesktopApi:
    def __init__(self) -> None:
        self._window: webview.Window | None = None
        self._action_lock = threading.Lock()

    def _bind_window(self, window: webview.Window) -> None:
        self._window = window

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

    def _server_command(self) -> list[str] | None:
        if getattr(sys, "frozen", False):
            return [
                str(Path(sys.executable)),
                "--server",
                "--config",
                str(SERVER_CONFIG_PATH),
            ]
        python_executable = self._python_executable()
        if python_executable is None:
            return None
        return [
            str(python_executable),
            "-u",
            str(SERVER_DIR / "main.py"),
            "--config",
            str(SERVER_CONFIG_PATH),
        ]

    @staticmethod
    def _listener_pid(port: int) -> int | None:
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

    def _start_server_blocking(self) -> tuple[bool, str]:
        if is_healthy():
            return True, "Server is already running"
        if self._listener_pid(server_address()[1]) is not None:
            return False, "The configured port is already in use"

        command = self._server_command()
        if command is None:
            return False, "Python environment is missing"
        try:
            SERVER_DIR.mkdir(parents=True, exist_ok=True)
            with LOG_PATH.open("a", encoding="utf-8") as output, ERROR_LOG_PATH.open(
                "a",
                encoding="utf-8",
            ) as errors:
                process = subprocess.Popen(
                    command,
                    cwd=SERVER_DIR,
                    stdout=output,
                    stderr=errors,
                    **hidden_process_options(),
                )
            PID_PATH.write_text(str(process.pid), encoding="ascii")
        except OSError as exc:
            return False, f"Could not start server: {exc}"

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if is_healthy():
                return True, f"Running at {base_url()}"
            if process.poll() is not None:
                return False, "Server exited while starting"
            time.sleep(0.25)
        return False, "Server did not become ready"

    def _stop_server_blocking(self) -> tuple[bool, str]:
        process_ids: list[int] = []
        try:
            process_ids.append(int(PID_PATH.read_text(encoding="ascii").strip()))
        except (OSError, ValueError):
            pass
        listener_pid = self._listener_pid(server_address()[1])
        if listener_pid is not None and listener_pid not in process_ids:
            process_ids.append(listener_pid)
        if not process_ids:
            PID_PATH.unlink(missing_ok=True)
            return True, "Server is stopped"

        for process_id in process_ids:
            subprocess.run(
                ["taskkill", "/PID", str(process_id), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                **hidden_process_options(),
            )

        deadline = time.monotonic() + 7
        while time.monotonic() < deadline:
            if self._listener_pid(server_address()[1]) is None:
                PID_PATH.unlink(missing_ok=True)
                return True, "Server stopped"
            time.sleep(0.2)
        return False, "Server is still running"

    def ensure_server(self) -> dict[str, Any]:
        with self._action_lock:
            success, detail = self._start_server_blocking()
        return {"ok": success, "detail": detail, "state": self.get_state()}

    def server_action(self, action: str) -> dict[str, Any]:
        if action not in {"start", "stop", "restart"}:
            return {"ok": False, "detail": "Unknown server action"}
        with self._action_lock:
            if action == "start":
                success, detail = self._start_server_blocking()
            elif action == "stop":
                success, detail = self._stop_server_blocking()
            else:
                success, detail = self._stop_server_blocking()
                if success:
                    success, detail = self._start_server_blocking()
        return {"ok": success, "detail": detail, "state": self.get_state()}

    def get_state(self) -> dict[str, Any]:
        settings = load_json(APP_SETTINGS_PATH)
        return {
            "running": is_healthy(),
            "baseUrl": base_url(),
            "config": load_overlay_config(OVERLAY_CONFIG_PATH),
            "defaults": DEFAULT_OVERLAY_CONFIG,
            "counter": load_counter_state(COUNTER_STATE_PATH),
            "theme": (
                str(settings.get("theme") or "dark")
                if str(settings.get("theme") or "dark") in {"dark", "light"}
                else "dark"
            ),
        }

    def choose_asset(self, kind: str) -> dict[str, Any]:
        if kind not in {"gif", "rest"} or self._window is None:
            return {"ok": False, "detail": "Unsupported asset type"}
        file_types = (
            (
                "Animated GIF (*.gif)",
                "Animated media (*.webp;*.apng;*.webm;*.mp4;*.mov)",
                "All files (*.*)",
            )
            if kind == "gif"
            else (
                "Images (*.png;*.gif;*.webp;*.apng)",
                "All files (*.*)",
            )
        )
        selected = self._window.create_file_dialog(
            webview.FileDialog.OPEN,
            allow_multiple=False,
            file_types=file_types,
        )
        if not selected:
            return {"ok": False, "cancelled": True}

        source = Path(selected[0])
        allowed = (
            ALLOWED_DANCE_EXTENSIONS if kind == "gif" else ALLOWED_REST_EXTENSIONS
        )
        if source.suffix.lower() not in allowed:
            return {"ok": False, "detail": "Unsupported file type"}

        USER_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
        cleaned_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", source.stem).strip(".-")
        destination_name = f"{cleaned_stem or kind}{source.suffix.lower()}"
        destination = USER_ASSETS_DIR / destination_name
        suffix = 2
        while destination.exists() and source.resolve() != destination.resolve():
            destination_name = f"{cleaned_stem or kind}-{suffix}{source.suffix.lower()}"
            destination = USER_ASSETS_DIR / destination_name
            suffix += 1
        if source.resolve() != destination.resolve():
            shutil.copy2(source, destination)
        return {
            "ok": True,
            "path": f"user-assets/{destination_name}",
            "name": source.name,
        }

    def save_overlay_settings(self, submitted: dict[str, Any]) -> dict[str, Any]:
        saved = save_overlay_config_file(
            OVERLAY_CONFIG_PATH,
            normalize_overlay_config(submitted),
        )
        server_config = load_json(SERVER_CONFIG_PATH, SERVER_CONFIG_EXAMPLE_PATH)
        audio = server_config.setdefault("audio", {})
        if isinstance(audio, dict):
            audio["sensitivity"] = saved["audio"]["sensitivity"]
        save_json(SERVER_CONFIG_PATH, server_config)

        applied = False
        if is_healthy():
            try:
                request_json("/api/config", saved)
                applied = True
            except (OSError, ValueError, urllib.error.URLError):
                applied = False
        return {"ok": True, "applied": applied, "config": saved}

    def update_counter(self, submitted: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(submitted, dict):
            return {"ok": False, "detail": "Expected counter values"}
        if not is_healthy():
            success, detail = self._start_server_blocking()
            if not success:
                return {"ok": False, "detail": detail}
        try:
            state = request_json("/api/win-loss", submitted)
        except (OSError, ValueError, urllib.error.URLError) as exc:
            return {"ok": False, "detail": str(exc)}
        return {"ok": True, "counter": state}

    def set_theme(self, theme: str) -> dict[str, Any]:
        selected = theme if theme in {"dark", "light"} else "dark"
        settings = load_json(APP_SETTINGS_PATH)
        settings["theme"] = selected
        save_json(APP_SETTINGS_PATH, settings)
        return {"ok": True, "theme": selected}

    def open_folder(self, folder: str) -> dict[str, Any]:
        choices = {
            "assets": USER_ASSETS_DIR,
            "logs": SERVER_DIR,
            "overlays": ROOT_DIR / "overlays",
        }
        target = choices.get(folder)
        if target is None:
            return {"ok": False}
        target.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(target)  # type: ignore[attr-defined]
        else:
            webbrowser.open(target.as_uri())
        return {"ok": True}

    def open_url(self, url: str) -> dict[str, Any]:
        parsed = urllib.parse.urlparse(str(url))
        allowed_hosts = {"127.0.0.1", "localhost"}
        if parsed.scheme != "http" or parsed.hostname not in allowed_hosts:
            return {"ok": False, "detail": "Only local overlay URLs can be opened"}
        webbrowser.open(url)
        return {"ok": True}

    def copy_text(self, text: str) -> dict[str, Any]:
        if sys.platform != "win32":
            return {"ok": False, "detail": "Clipboard is unavailable"}
        value = str(text)
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        global_moveable = 0x0002
        unicode_text = 13
        encoded = (value + "\0").encode("utf-16le")

        kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
        user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        user32.SetClipboardData.restype = ctypes.c_void_p

        handle = kernel32.GlobalAlloc(global_moveable, len(encoded))
        if not handle:
            return {"ok": False, "detail": "Could not allocate clipboard memory"}
        locked = kernel32.GlobalLock(handle)
        if not locked:
            kernel32.GlobalFree(handle)
            return {"ok": False, "detail": "Could not access clipboard memory"}
        ctypes.memmove(locked, encoded, len(encoded))
        kernel32.GlobalUnlock(handle)

        if not user32.OpenClipboard(None):
            kernel32.GlobalFree(handle)
            return {"ok": False, "detail": "Clipboard is busy"}
        try:
            user32.EmptyClipboard()
            if not user32.SetClipboardData(unicode_text, handle):
                kernel32.GlobalFree(handle)
                return {"ok": False, "detail": "Could not update clipboard"}
        finally:
            user32.CloseClipboard()
        return {"ok": True}


def run_embedded_server() -> None:
    sys.argv.remove("--server")
    from main import main as server_main

    server_main()


def main() -> None:
    if "--server" in sys.argv:
        run_embedded_server()
        return
    if not STUDIO_UI_PATH.exists():
        raise FileNotFoundError(f"Overlay Studio UI not found: {STUDIO_UI_PATH}")

    api = DesktopApi()
    api._start_server_blocking()
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
    window = webview.create_window(
        "Overlay Studio",
        url=str(STUDIO_UI_PATH),
        js_api=api,
        width=1100,
        height=760,
        min_size=(940, 640),
        background_color="#0f1316",
        text_select=False,
    )
    if window is None:
        raise RuntimeError("Could not create Overlay Studio window")
    api._bind_window(window)
    webview.start(
        gui="edgechromium",
        debug=False,
        http_server=True,
        private_mode=True,
    )


if __name__ == "__main__":
    main()
