from __future__ import annotations

import base64
import binascii
import configparser
import contextlib
import copy
import ctypes
import ipaddress
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from html.parser import HTMLParser
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
GOAL_STATE_PATH = SERVER_DIR / "goal.json"
USER_ASSETS_DIR = ROOT_DIR / "user-assets"
PID_PATH = SERVER_DIR / "server.pid"
LOG_PATH = SERVER_DIR / "server.log"
ERROR_LOG_PATH = SERVER_DIR / "server.err"
STUDIO_UI_PATH = RESOURCE_DIR / "studio" / "index.html"
WINDOW_SIZE = (1000, 700)
WINDOW_MIN_SIZE = (900, 620)
WINDOW_MAX_SIZE = (1000, 700)

sys.path.insert(0, str(SERVER_DIR))
from counter_store import (  # noqa: E402
    load_counter_state,
    load_counter_states,
    remove_counter_instance,
)
from goal_store import (  # noqa: E402
    DEFAULT_GOAL_BAR_STATE,
    DEFAULT_GOAL_STATE,
    GOAL_OVERLAY_TYPES,
    goal_defaults_for_type,
    load_goal_state,
    load_goal_states,
    remove_goal_instance,
)
from overlay_config import (  # noqa: E402
    DEFAULT_OVERLAY_CONFIG,
    add_overlay_instance as add_overlay_instance_config,
    is_valid_instance_id,
    load_overlay_config,
    materialize_instance_config,
    normalize_overlay_config,
    remove_overlay_instance as remove_overlay_instance_config,
    rename_overlay_instance as rename_overlay_instance_config,
    save_overlay_config as save_overlay_config_file,
    update_instance_config,
)
from overlay_manifest import scan_overlay_manifests  # noqa: E402


ALLOWED_DANCE_EXTENSIONS = {
    ".gif",
    ".webp",
    ".apng",
    ".png",
    ".webm",
    ".mp4",
    ".mov",
}
ALLOWED_REST_EXTENSIONS = {".gif", ".webp", ".apng", ".png", ".jpg", ".jpeg"}
DANCE_VIDEO_EXTENSIONS = {".webm", ".mp4", ".mov"}
MAX_DRAG_IMPORT_BYTES = 25 * 1024 * 1024
MAX_SHORTCUT_BYTES = 64 * 1024
MAX_SHORTCUT_PAGE_BYTES = 1024 * 1024
SHORTCUT_PAGE_TYPES = {"application/xhtml+xml", "text/html"}
REMOTE_MEDIA_TYPES = {
    "image/apng": ".png",
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/x-png": ".png",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
}


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


def media_library(config: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    dancing: dict[str, dict[str, Any]] = {}
    resting: dict[str, dict[str, Any]] = {}

    def add_asset(
        collection: dict[str, dict[str, Any]],
        relative_path: str,
        label: str | None = None,
    ) -> None:
        normalized = str(relative_path or "").replace("\\", "/").strip()
        if not normalized or normalized in collection:
            return
        parsed = urllib.parse.urlparse(normalized)
        filename = Path(urllib.parse.unquote(parsed.path)).name
        suffix = Path(filename).suffix.lower()
        stem = Path(filename).stem
        display_name = label or re.sub(r"[-_]+", " ", stem).strip() or filename
        collection[normalized] = {
            "path": normalized,
            "name": display_name,
            "type": "video" if suffix in DANCE_VIDEO_EXTENSIONS else "image",
            "deletable": normalized.startswith(
                ("user-assets/dancing/", "user-assets/resting/")
            ),
        }

    dance = config["dance"]
    dance_paths = {
        str(dance["gif"]).replace("\\", "/"),
        *(str(path).replace("\\", "/") for path in dance["pool"]),
    }
    rest_paths = {str(dance["rest"]).replace("\\", "/")}

    add_asset(dancing, DEFAULT_OVERLAY_CONFIG["dance"]["gif"], "Default dance")
    add_asset(resting, DEFAULT_OVERLAY_CONFIG["dance"]["rest"], "Default resting image")
    for path in dance_paths:
        add_asset(dancing, path)
    for path in rest_paths:
        add_asset(resting, path)

    USER_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for asset in sorted(USER_ASSETS_DIR.rglob("*")):
        if not asset.is_file():
            continue
        suffix = asset.suffix.lower()
        relative = f"user-assets/{asset.relative_to(USER_ASSETS_DIR).as_posix()}"
        first_folder = asset.relative_to(USER_ASSETS_DIR).parts[0].lower()
        if first_folder == "dancing":
            if suffix in ALLOWED_DANCE_EXTENSIONS:
                add_asset(dancing, relative)
            continue
        if first_folder == "resting":
            if suffix in ALLOWED_REST_EXTENSIONS:
                add_asset(resting, relative)
            continue
        if relative in dance_paths:
            add_asset(dancing, relative)
        if relative in rest_paths:
            add_asset(resting, relative)
        if relative in dance_paths or relative in rest_paths:
            continue
        if suffix in DANCE_VIDEO_EXTENSIONS or suffix in {".gif", ".webp", ".apng"}:
            add_asset(dancing, relative)
        elif suffix in ALLOWED_REST_EXTENSIONS:
            add_asset(resting, relative)

    return {
        "dancing": list(dancing.values()),
        "resting": list(resting.values()),
    }


def asset_destination(
    kind: str,
    filename: str,
    *,
    content: bytes | None = None,
    source: Path | None = None,
) -> Path:
    destination_dir = USER_ASSETS_DIR / ("dancing" if kind == "gif" else "resting")
    destination_dir.mkdir(parents=True, exist_ok=True)
    supplied_name = Path(filename).name
    extension = Path(supplied_name).suffix.lower()
    cleaned_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(supplied_name).stem).strip(
        ".-"
    )
    base_name = cleaned_stem or kind
    destination = destination_dir / f"{base_name}{extension}"
    suffix = 2
    while destination.exists():
        if source is not None and source.resolve() == destination.resolve():
            return destination
        if (
            content is not None
            and destination.stat().st_size == len(content)
            and destination.read_bytes() == content
        ):
            return destination
        destination = destination_dir / f"{base_name}-{suffix}{extension}"
        suffix += 1
    return destination


def copy_user_asset(
    source: Path,
    kind: str,
    content: bytes | None = None,
) -> str:
    copied_content = source.read_bytes() if content is None else content
    destination = asset_destination(
        kind,
        source.name,
        content=copied_content,
        source=source,
    )
    if not destination.exists():
        shutil.copy2(source, destination)
    return f"user-assets/{destination.relative_to(USER_ASSETS_DIR).as_posix()}"


def prepare_legacy_asset_migration(
    config: dict[str, Any],
) -> tuple[dict[str, Any], list[Path], bool]:
    migrated = copy.deepcopy(config)
    dance = migrated["dance"]

    def normalized(value: Any) -> str:
        return str(value or "").replace("\\", "/")

    dance_paths = {
        normalized(dance["gif"]),
        *(normalized(path) for path in dance["pool"]),
    }
    rest_path = normalized(dance["rest"])
    cleanup: list[Path] = []
    config_changed = False

    USER_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    for source in sorted(USER_ASSETS_DIR.iterdir()):
        if not source.is_file() or source.name.startswith("."):
            continue
        suffix = source.suffix.lower()
        old_path = f"user-assets/{source.name}"
        categories: list[str] = []
        if old_path in dance_paths:
            categories.append("gif")
        if old_path == rest_path:
            categories.append("rest")
        if not categories:
            if suffix in DANCE_VIDEO_EXTENSIONS or suffix in {
                ".gif",
                ".webp",
                ".apng",
            }:
                categories.append("gif")
            elif suffix in ALLOWED_REST_EXTENSIONS:
                categories.append("rest")

        content: bytes | None = None
        destinations: dict[str, str] = {}
        for kind in categories:
            allowed = (
                ALLOWED_DANCE_EXTENSIONS
                if kind == "gif"
                else ALLOWED_REST_EXTENSIONS
            )
            if suffix not in allowed:
                continue
            try:
                if content is None:
                    content = source.read_bytes()
                destinations[kind] = copy_user_asset(source, kind, content)
            except OSError:
                continue
        if not destinations:
            continue

        if old_path in dance_paths and "gif" in destinations:
            dance["gif"] = (
                destinations["gif"]
                if normalized(dance["gif"]) == old_path
                else dance["gif"]
            )
            dance["pool"] = [
                destinations["gif"] if normalized(path) == old_path else path
                for path in dance["pool"]
            ]
            config_changed = True
        if old_path == rest_path and "rest" in destinations:
            dance["rest"] = destinations["rest"]
            config_changed = True
        if len(destinations) == len(categories):
            cleanup.append(source)

    return migrated, cleanup, config_changed


def validate_public_https_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme.lower() != "https":
        raise ValueError("Internet shortcuts must use HTTPS")
    if (
        not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("Internet shortcut address is not valid")
    try:
        port = parsed.port
    except ValueError as error:
        raise ValueError("Internet shortcut address is not valid") from error
    if port not in {None, 443}:
        raise ValueError("Internet shortcuts must use the standard HTTPS port")
    if parsed.hostname.rstrip(".").lower().endswith(".local"):
        raise ValueError("Internet shortcuts cannot use local network addresses")

    try:
        addresses = socket.getaddrinfo(
            parsed.hostname,
            443,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as error:
        raise ValueError("Internet shortcut host could not be resolved") from error
    if not addresses:
        raise ValueError("Internet shortcut host could not be resolved")
    for address in addresses:
        host_address = address[4][0].split("%", 1)[0]
        try:
            ip_address = ipaddress.ip_address(host_address)
        except ValueError as error:
            raise ValueError("Internet shortcut host address is not valid") from error
        if not ip_address.is_global:
            raise ValueError("Internet shortcuts cannot use local network addresses")
    return urllib.parse.urlunsplit(parsed)


class PublicHttpsRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self,
        request: urllib.request.Request,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> urllib.request.Request | None:
        target = urllib.parse.urljoin(request.full_url, new_url)
        validate_public_https_url(target)
        return super().redirect_request(
            request,
            file_pointer,
            code,
            message,
            headers,
            target,
        )


def parse_internet_shortcut(content: bytes) -> str:
    if not content or len(content) > MAX_SHORTCUT_BYTES:
        raise ValueError("Internet shortcut must be between 1 byte and 64 KB")

    encodings = (
        ("utf-16",)
        if content.startswith((b"\xff\xfe", b"\xfe\xff"))
        else ("utf-8-sig", "cp1252")
    )
    decoded: str | None = None
    for encoding in encodings:
        try:
            decoded = content.decode(encoding)
            break
        except UnicodeError:
            continue
    if decoded is None:
        raise ValueError("Could not read that Internet shortcut")

    parser = configparser.ConfigParser(interpolation=None)
    try:
        parser.read_string(decoded)
    except configparser.Error as error:
        raise ValueError("Could not read that Internet shortcut") from error
    section = next(
        (
            name
            for name in parser.sections()
            if name.lower() == "internetshortcut"
        ),
        None,
    )
    if section is None:
        raise ValueError("That file is not an Internet shortcut")
    url = parser.get(section, "URL", fallback="").strip()
    if not url:
        raise ValueError("That Internet shortcut does not contain an address")
    return validate_public_https_url(url)


def sniff_media_extension(content: bytes) -> str | None:
    if content.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if (
        len(content) >= 12
        and content.startswith(b"RIFF")
        and content[8:12] == b"WEBP"
    ):
        return ".webp"
    if content.startswith(b"\x1a\x45\xdf\xa3"):
        return ".webm"
    if len(content) >= 12 and content[4:8] == b"ftyp":
        return ".mov" if content[8:12] == b"qt  " else ".mp4"
    return None


def validate_imported_media(
    kind: str,
    declared_extension: str,
    content: bytes,
) -> None:
    detected_extension = sniff_media_extension(content)
    if detected_extension is None:
        raise ValueError("That file does not contain supported image or video data")

    compatible_extensions = (
        declared_extension == detected_extension
        or {declared_extension, detected_extension} <= {".jpg", ".jpeg"}
        or {declared_extension, detected_extension} <= {".png", ".apng"}
        or {declared_extension, detected_extension} <= {".mp4", ".mov"}
    )
    if not compatible_extensions:
        raise ValueError(
            f"File contents do not match the {declared_extension} extension"
        )

    allowed = ALLOWED_DANCE_EXTENSIONS if kind == "gif" else ALLOWED_REST_EXTENSIONS
    if detected_extension not in allowed:
        raise ValueError("That media type is not supported here")


class ShortcutMediaMetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.media: list[tuple[str, str]] = []

    def handle_starttag(
        self,
        tag: str,
        attributes: list[tuple[str, str | None]],
    ) -> None:
        if tag.lower() != "meta":
            return
        values = {
            key.lower(): value
            for key, value in attributes
            if key is not None and value is not None
        }
        property_name = (
            values.get("property") or values.get("name") or ""
        ).lower()
        content = values.get("content", "").strip()
        if property_name and content:
            self.media.append((property_name, content))


def shortcut_page_media_urls(
    content: bytes,
    page_url: str,
    kind: str,
) -> list[str]:
    parser = ShortcutMediaMetadataParser()
    parser.feed(content.decode("utf-8", errors="replace"))
    priorities = [
        "og:image:secure_url",
        "og:image",
        "twitter:image",
        "twitter:image:src",
    ]
    if kind == "gif":
        priorities.extend(
            [
                "og:video:secure_url",
                "og:video",
                "twitter:player:stream",
            ]
        )

    candidates: list[str] = []
    for property_name in priorities:
        for label, value in parser.media:
            if label != property_name:
                continue
            candidate = urllib.parse.urljoin(page_url, value)
            try:
                candidate = validate_public_https_url(candidate)
            except ValueError:
                continue
            if candidate not in candidates:
                candidates.append(candidate)
            if len(candidates) >= 8:
                return candidates
    return candidates


def fetch_shortcut_target(
    url: str,
    *,
    allow_page: bool,
) -> tuple[str, str, bytes, bool]:
    opener = urllib.request.build_opener(PublicHttpsRedirectHandler())
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "image/*,video/*,text/html;q=0.8",
            "User-Agent": "Overlay Studio/1.0",
        },
    )
    try:
        with opener.open(request, timeout=15) as response:
            final_url = validate_public_https_url(response.geturl())
            content_type = (
                response.headers.get("Content-Type", "")
                .partition(";")[0]
                .strip()
                .lower()
            )
            is_page = content_type in SHORTCUT_PAGE_TYPES
            if is_page:
                if not allow_page:
                    raise ValueError("Media link returned another webpage")
                content = response.read(MAX_SHORTCUT_PAGE_BYTES)
            else:
                content_length = response.headers.get("Content-Length")
                if content_length is not None:
                    try:
                        declared_size = int(content_length)
                    except ValueError:
                        declared_size = 0
                    if declared_size > MAX_DRAG_IMPORT_BYTES:
                        raise ValueError("Shortcut media must be 25 MB or smaller")
                content = response.read(MAX_DRAG_IMPORT_BYTES + 1)
    except ValueError:
        raise
    except (OSError, urllib.error.URLError) as error:
        raise ValueError(
            "Could not download media from that Internet shortcut"
        ) from error
    return final_url, content_type, content, is_page


def validate_shortcut_media_payload(
    kind: str,
    content_type: str,
    content: bytes,
) -> str:
    if not content or len(content) > MAX_DRAG_IMPORT_BYTES:
        raise ValueError("Shortcut media must be between 1 byte and 25 MB")
    extension = sniff_media_extension(content)
    if extension is None:
        raise ValueError("Internet shortcut did not download supported media")
    declared_extension = REMOTE_MEDIA_TYPES.get(content_type)
    if content_type and content_type != "application/octet-stream":
        extensions_match = declared_extension == extension or {
            declared_extension,
            extension,
        } == {".mov", ".mp4"}
        if declared_extension is None or not extensions_match:
            raise ValueError("Internet shortcut returned an unexpected file type")

    allowed = ALLOWED_DANCE_EXTENSIONS if kind == "gif" else ALLOWED_REST_EXTENSIONS
    if extension not in allowed:
        raise ValueError("Internet shortcut media is not supported here")
    return extension


def download_shortcut_media(
    kind: str,
    shortcut_name: str,
    shortcut_content: bytes,
) -> tuple[str, str]:
    url = parse_internet_shortcut(shortcut_content)
    final_url, content_type, content, is_page = fetch_shortcut_target(
        url,
        allow_page=True,
    )
    if is_page:
        candidates = shortcut_page_media_urls(content, final_url, kind)
        for candidate in candidates:
            try:
                final_url, content_type, content, nested_page = (
                    fetch_shortcut_target(candidate, allow_page=False)
                )
                if nested_page:
                    continue
                extension = validate_shortcut_media_payload(
                    kind,
                    content_type,
                    content,
                )
                break
            except ValueError:
                continue
        else:
            raise ValueError(
                "Webpage shortcut did not provide supported media under 25 MB"
            )
    else:
        extension = validate_shortcut_media_payload(kind, content_type, content)

    remote_name = Path(
        urllib.parse.unquote(urllib.parse.urlsplit(final_url).path)
    ).name
    fallback_stem = Path(Path(shortcut_name).stem).stem
    stem = Path(remote_name).stem if remote_name else fallback_stem
    imported_name = f"{stem or kind}{extension}"
    destination = asset_destination(kind, imported_name, content=content)
    if not destination.exists():
        temporary_path = destination.with_suffix(f"{destination.suffix}.tmp")
        temporary_path.write_bytes(content)
        temporary_path.replace(destination)
    relative_path = f"user-assets/{destination.relative_to(USER_ASSETS_DIR).as_posix()}"
    return relative_path, imported_name


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
        config = load_overlay_config(OVERLAY_CONFIG_PATH)
        try:
            migrated, legacy_assets, config_changed = prepare_legacy_asset_migration(
                config
            )
            if config_changed:
                config = self.save_overlay_settings(migrated)["config"]
            else:
                config = migrated
            for legacy_asset in legacy_assets:
                legacy_asset.unlink(missing_ok=True)
        except OSError:
            config = load_overlay_config(OVERLAY_CONFIG_PATH)
        goal_instances = {
            instance_id: instance
            for instance_id, instance in config["instances"].items()
            if instance["type"] in GOAL_OVERLAY_TYPES
        }
        return {
            "running": is_healthy(),
            "baseUrl": base_url(),
            "config": config,
            "defaults": DEFAULT_OVERLAY_CONFIG,
            "catalog": scan_overlay_manifests(ROOT_DIR / "overlays"),
            "mediaLibrary": media_library(config),
            "counter": load_counter_state(COUNTER_STATE_PATH),
            "counters": load_counter_states(
                COUNTER_STATE_PATH,
                (
                    instance_id
                    for instance_id, instance in config["instances"].items()
                    if instance["type"] == "win-loss"
                ),
            ),
            "goal": load_goal_state(GOAL_STATE_PATH),
            "goalDefaults": DEFAULT_GOAL_STATE,
            "goalBarDefaults": DEFAULT_GOAL_BAR_STATE,
            "goals": load_goal_states(
                GOAL_STATE_PATH,
                goal_instances,
                {
                    instance_id: goal_defaults_for_type(instance["type"])
                    for instance_id, instance in goal_instances.items()
                },
            ),
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
                "Internet shortcuts (*.url)",
                "All files (*.*)",
            )
            if kind == "gif"
            else (
                "Images (*.png;*.jpg;*.jpeg;*.gif;*.webp;*.apng)",
                "Internet shortcuts (*.url)",
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
        extension = source.suffix.lower()
        if extension == ".url":
            try:
                with source.open("rb") as shortcut_file:
                    shortcut_content = shortcut_file.read(MAX_SHORTCUT_BYTES + 1)
                relative_path, imported_name = download_shortcut_media(
                    kind,
                    source.name,
                    shortcut_content,
                )
            except (OSError, ValueError) as error:
                return {"ok": False, "detail": str(error)}
            return {
                "ok": True,
                "path": relative_path,
                "name": imported_name,
                "library": media_library(load_overlay_config(OVERLAY_CONFIG_PATH)),
            }
        if extension not in allowed:
            return {"ok": False, "detail": "Unsupported file type"}

        try:
            with source.open("rb") as media_file:
                validate_imported_media(kind, extension, media_file.read(16))
        except (OSError, ValueError) as error:
            return {"ok": False, "detail": str(error)}

        destination = asset_destination(kind, source.name, source=source)
        if source.resolve() != destination.resolve():
            shutil.copy2(source, destination)
        relative_path = f"user-assets/{destination.relative_to(USER_ASSETS_DIR).as_posix()}"
        return {
            "ok": True,
            "path": relative_path,
            "name": source.name,
            "library": media_library(load_overlay_config(OVERLAY_CONFIG_PATH)),
        }

    def import_asset(
        self,
        kind: str,
        filename: str,
        data_url: str,
    ) -> dict[str, Any]:
        if kind not in {"gif", "rest"}:
            return {"ok": False, "detail": "Unsupported asset type"}
        supplied_name = Path(str(filename or "")).name
        extension = Path(supplied_name).suffix.lower()
        allowed = (
            ALLOWED_DANCE_EXTENSIONS if kind == "gif" else ALLOWED_REST_EXTENSIONS
        )
        if extension not in allowed and extension != ".url":
            return {
                "ok": False,
                "detail": f"Unsupported file type: {extension or 'none'}",
            }

        header, separator, encoded = str(data_url or "").partition(",")
        if not separator or ";base64" not in header.lower():
            return {"ok": False, "detail": "Could not read that dropped file"}
        maximum_bytes = (
            MAX_SHORTCUT_BYTES if extension == ".url" else MAX_DRAG_IMPORT_BYTES
        )
        if len(encoded) > (maximum_bytes * 4 // 3) + 8:
            return {
                "ok": False,
                "detail": (
                    "Internet shortcuts must be 64 KB or smaller"
                    if extension == ".url"
                    else "Dropped files must be 25 MB or smaller; use Add media instead"
                ),
            }
        try:
            content = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError):
            return {"ok": False, "detail": "Could not decode that dropped file"}
        if not content or len(content) > maximum_bytes:
            return {
                "ok": False,
                "detail": (
                    "Internet shortcuts must be between 1 byte and 64 KB"
                    if extension == ".url"
                    else "Dropped files must be between 1 byte and 25 MB"
                ),
            }

        if extension != ".url":
            try:
                validate_imported_media(kind, extension, content)
            except ValueError as error:
                return {"ok": False, "detail": str(error)}

        if extension == ".url":
            try:
                relative_path, imported_name = download_shortcut_media(
                    kind,
                    supplied_name,
                    content,
                )
            except ValueError as error:
                return {"ok": False, "detail": str(error)}
            return {
                "ok": True,
                "path": relative_path,
                "name": imported_name,
                "library": media_library(load_overlay_config(OVERLAY_CONFIG_PATH)),
            }

        destination = asset_destination(kind, supplied_name, content=content)
        if not destination.exists():
            temporary_path = destination.with_suffix(f"{destination.suffix}.tmp")
            temporary_path.write_bytes(content)
            temporary_path.replace(destination)
        relative_path = f"user-assets/{destination.relative_to(USER_ASSETS_DIR).as_posix()}"
        return {
            "ok": True,
            "path": relative_path,
            "name": supplied_name,
            "library": media_library(load_overlay_config(OVERLAY_CONFIG_PATH)),
        }

    def delete_asset(self, kind: str, relative_path: str) -> dict[str, Any]:
        if kind not in {"gif", "rest"}:
            return {"ok": False, "detail": "Unsupported asset type"}
        normalized = str(relative_path or "").replace("\\", "/").strip()
        folder = "dancing" if kind == "gif" else "resting"
        prefix = f"user-assets/{folder}/"
        if not normalized.startswith(prefix):
            return {
                "ok": False,
                "detail": f"Only imported {folder} media can be deleted here",
            }

        relative = Path(normalized.removeprefix(prefix))
        allowed = (
            ALLOWED_DANCE_EXTENSIONS if kind == "gif" else ALLOWED_REST_EXTENSIONS
        )
        if (
            not relative.parts
            or relative.is_absolute()
            or ".." in relative.parts
            or relative.suffix.lower() not in allowed
        ):
            return {"ok": False, "detail": "Invalid media path"}

        try:
            assets_root = USER_ASSETS_DIR.resolve()
            target = (USER_ASSETS_DIR / folder / relative).resolve()
        except OSError:
            return {"ok": False, "detail": "Invalid media path"}
        try:
            target.relative_to(assets_root)
        except ValueError:
            return {"ok": False, "detail": "Invalid media path"}
        if not target.is_file():
            return {"ok": False, "detail": "That media file no longer exists"}

        original_config = load_overlay_config(OVERLAY_CONFIG_PATH)
        config = copy.deepcopy(original_config)

        def same_asset(value: Any) -> bool:
            return str(value or "").replace("\\", "/") == normalized

        dance_sections = [config["dance"]]
        dance_sections.extend(
            instance["config"]["dance"]
            for instance in config["instances"].values()
            if (
                instance.get("type") == "larpdog-dance"
                and isinstance(instance.get("config"), dict)
                and isinstance(instance["config"].get("dance"), dict)
            )
        )

        def dance_entries() -> list[dict[str, Any]]:
            entries: list[dict[str, Any]] = []
            for dance in dance_sections:
                entries.append(dance)
                profiles = dance.get("profiles")
                if isinstance(profiles, list):
                    entries.extend(
                        profile
                        for profile in profiles
                        if isinstance(profile, dict)
                    )
            return entries

        entries = dance_entries()
        try:
            if kind == "gif":
                preserved_rest = None
                if any(same_asset(entry.get("rest")) for entry in entries):
                    if target.suffix.lower() not in ALLOWED_REST_EXTENSIONS:
                        return {
                            "ok": False,
                            "detail": "This file is also used as the resting image",
                        }
                    preserved_rest = copy_user_asset(target, "rest")
                default_dance = DEFAULT_OVERLAY_CONFIG["dance"]["gif"]
                for entry in entries:
                    if preserved_rest and same_asset(entry.get("rest")):
                        entry["rest"] = preserved_rest
                    pool = entry.get("pool")
                    remaining_pool = [
                        path
                        for path in (pool if isinstance(pool, list) else [])
                        if not same_asset(path)
                    ]
                    if same_asset(entry.get("gif")):
                        entry["gif"] = (
                            remaining_pool[0] if remaining_pool else default_dance
                        )
                    if not remaining_pool:
                        remaining_pool = [entry.get("gif") or default_dance]
                    if entry.get("gif") not in remaining_pool:
                        remaining_pool.insert(0, entry.get("gif") or default_dance)
                    entry["pool"] = list(dict.fromkeys(remaining_pool))
            else:
                dance_references_target = any(
                    same_asset(entry.get("gif"))
                    or any(
                        same_asset(path)
                        for path in (
                            entry.get("pool")
                            if isinstance(entry.get("pool"), list)
                            else []
                        )
                    )
                    for entry in entries
                )
                preserved_path = None
                if dance_references_target:
                    if target.suffix.lower() not in ALLOWED_DANCE_EXTENSIONS:
                        return {
                            "ok": False,
                            "detail": "This file is also used as dancing media",
                        }
                    preserved_path = copy_user_asset(target, "gif")
                for entry in entries:
                    if preserved_path and same_asset(entry.get("gif")):
                        entry["gif"] = preserved_path
                    pool = entry.get("pool")
                    if preserved_path and isinstance(pool, list):
                        entry["pool"] = list(
                            dict.fromkeys(
                                preserved_path if same_asset(path) else path
                                for path in pool
                            )
                        )
                    if same_asset(entry.get("rest")):
                        entry["rest"] = DEFAULT_OVERLAY_CONFIG["dance"]["rest"]
        except OSError:
            return {"ok": False, "detail": "Could not separate that media file"}

        try:
            saved = self.save_overlay_settings(config)
            target.unlink()
        except OSError:
            with contextlib.suppress(OSError):
                self.save_overlay_settings(original_config)
            return {"ok": False, "detail": "Could not delete that media file"}

        return {
            "ok": True,
            "name": target.name,
            "path": normalized,
            "config": saved["config"],
            "library": media_library(saved["config"]),
        }

    def add_overlay_instance(self, overlay_type: str) -> dict[str, Any]:
        catalog = {
            manifest["type"]: manifest
            for manifest in scan_overlay_manifests(ROOT_DIR / "overlays")
        }
        manifest = catalog.get(str(overlay_type or ""))
        if manifest is None:
            return {"ok": False, "detail": "Overlay type not found"}
        config = load_overlay_config(OVERLAY_CONFIG_PATH)
        base_id = manifest["type"]
        instance_id = base_id
        suffix = 2
        while instance_id in config["instances"]:
            instance_id = f"{base_id}-{suffix}"
            suffix += 1
        try:
            updated = add_overlay_instance_config(
                config,
                manifest["type"],
                instance_id,
                manifest["name"],
            )
            save_overlay_config_file(OVERLAY_CONFIG_PATH, updated)
        except (OSError, ValueError) as error:
            return {"ok": False, "detail": str(error)}
        return {
            "ok": True,
            "instanceId": instance_id,
            "state": self.get_state(),
        }

    def remove_overlay_instance(self, instance_id: str) -> dict[str, Any]:
        if not is_valid_instance_id(instance_id):
            return {"ok": False, "detail": "Invalid overlay instance"}
        config = load_overlay_config(OVERLAY_CONFIG_PATH)
        try:
            updated = remove_overlay_instance_config(config, instance_id)
            save_overlay_config_file(OVERLAY_CONFIG_PATH, updated)
            remove_counter_instance(COUNTER_STATE_PATH, instance_id)
            remove_goal_instance(GOAL_STATE_PATH, instance_id)
        except (OSError, ValueError) as error:
            return {"ok": False, "detail": str(error)}
        return {"ok": True, "state": self.get_state()}

    def rename_overlay_instance(
        self,
        instance_id: str,
        name: str,
    ) -> dict[str, Any]:
        if not is_valid_instance_id(instance_id):
            return {"ok": False, "detail": "Invalid overlay instance"}
        config = load_overlay_config(OVERLAY_CONFIG_PATH)
        try:
            updated = rename_overlay_instance_config(config, instance_id, name)
            save_overlay_config_file(OVERLAY_CONFIG_PATH, updated)
        except (OSError, ValueError) as error:
            return {"ok": False, "detail": str(error)}
        return {"ok": True, "state": self.get_state()}

    def save_overlay_settings(
        self,
        submitted: dict[str, Any],
        instance_id: str | None = None,
    ) -> dict[str, Any]:
        if instance_id:
            if not is_valid_instance_id(instance_id):
                return {"ok": False, "detail": "Invalid overlay instance"}
            current = load_overlay_config(OVERLAY_CONFIG_PATH)
            try:
                normalized = update_instance_config(
                    current,
                    instance_id,
                    submitted,
                )
            except ValueError as error:
                return {"ok": False, "detail": str(error)}
        else:
            normalized = normalize_overlay_config(submitted)
        saved = save_overlay_config_file(
            OVERLAY_CONFIG_PATH,
            normalized,
        )
        server_config = load_json(SERVER_CONFIG_PATH, SERVER_CONFIG_EXAMPLE_PATH)
        audio = server_config.setdefault("audio", {})
        if isinstance(audio, dict):
            audio["sensitivity"] = saved["audio"]["sensitivity"]
        save_json(SERVER_CONFIG_PATH, server_config)

        applied = False
        if is_healthy():
            try:
                request_json(
                    (
                        f"/api/config?i={urllib.parse.quote(instance_id)}"
                        if instance_id
                        else "/api/config"
                    ),
                    submitted if instance_id else saved,
                )
                applied = True
            except (OSError, ValueError, urllib.error.URLError):
                applied = False
        return {
            "ok": True,
            "applied": applied,
            "config": saved,
            "instanceConfig": materialize_instance_config(saved, instance_id),
        }

    def update_counter(
        self,
        submitted: dict[str, Any],
        instance_id: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(submitted, dict):
            return {"ok": False, "detail": "Expected counter values"}
        if instance_id and not is_valid_instance_id(instance_id):
            return {"ok": False, "detail": "Invalid overlay instance"}
        if not is_healthy():
            success, detail = self._start_server_blocking()
            if not success:
                return {"ok": False, "detail": detail}
        try:
            state = request_json(
                (
                    f"/api/win-loss?i={urllib.parse.quote(instance_id)}"
                    if instance_id
                    else "/api/win-loss"
                ),
                submitted,
            )
        except (OSError, ValueError, urllib.error.URLError) as exc:
            return {"ok": False, "detail": str(exc)}
        return {"ok": True, "counter": state}

    def update_goal(
        self,
        submitted: dict[str, Any],
        instance_id: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(submitted, dict):
            return {"ok": False, "detail": "Expected goal values"}
        if instance_id and not is_valid_instance_id(instance_id):
            return {"ok": False, "detail": "Invalid overlay instance"}
        if not is_healthy():
            success, detail = self._start_server_blocking()
            if not success:
                return {"ok": False, "detail": detail}
        try:
            state = request_json(
                (
                    f"/api/goal?i={urllib.parse.quote(instance_id)}"
                    if instance_id
                    else "/api/goal"
                ),
                submitted,
            )
        except (OSError, ValueError, urllib.error.URLError) as exc:
            return {"ok": False, "detail": str(exc)}
        return {"ok": True, "goal": state}

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


def constrain_window_size(window: webview.Window) -> None:
    if sys.platform != "win32" or window.native is None:
        return

    from System.Drawing import Size

    scale = window.native._scale
    window.native.MaximumSize = Size(
        int(WINDOW_MAX_SIZE[0] * scale),
        int(WINDOW_MAX_SIZE[1] * scale),
    )
    window.native.MaximizeBox = False


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
        width=WINDOW_SIZE[0],
        height=WINDOW_SIZE[1],
        min_size=WINDOW_MIN_SIZE,
        background_color="#0f1316",
        text_select=False,
    )
    if window is None:
        raise RuntimeError("Could not create Overlay Studio window")
    window.events.before_show += constrain_window_size
    api._bind_window(window)
    webview.start(
        gui="edgechromium",
        debug=False,
        http_server=True,
        private_mode=True,
    )


if __name__ == "__main__":
    main()
