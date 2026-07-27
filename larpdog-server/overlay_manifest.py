from __future__ import annotations

import copy
import json
import re
import threading
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


OVERLAY_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
SETTING_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
MAX_MANIFEST_BYTES = 32 * 1024
MAX_OVERLAY_FILE_BYTES = 2 * 1024 * 1024

_manifest_cache: dict[
    Path,
    tuple[
        tuple[tuple[str, int, int], ...],
        list[dict[str, Any]],
    ],
] = {}
_manifest_cache_lock = threading.Lock()


class ManifestParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._capturing = False
        self._chunks: list[str] = []
        self.payload: str | None = None

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag.lower() != "script" or self.payload is not None:
            return
        values = {
            str(key).lower(): str(value or "")
            for key, value in attrs
        }
        if (
            values.get("id") == "overlay-manifest"
            and values.get("type", "").lower() == "application/json"
        ):
            self._capturing = True
            self._chunks = []

    def handle_data(self, data: str) -> None:
        if self._capturing:
            self._chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._capturing:
            payload = "".join(self._chunks).strip()
            if len(payload.encode("utf-8")) <= MAX_MANIFEST_BYTES:
                self.payload = payload
            self._capturing = False


def _text(value: Any, maximum: int) -> str:
    return " ".join(str(value or "").split())[:maximum]


def read_overlay_manifest(path: Path) -> dict[str, Any] | None:
    overlay_type = path.stem
    if not OVERLAY_NAME.fullmatch(overlay_type):
        return None
    try:
        if path.stat().st_size > MAX_OVERLAY_FILE_BYTES:
            return None
        with path.open("rb") as stream:
            raw_content = stream.read(MAX_OVERLAY_FILE_BYTES + 1)
        if len(raw_content) > MAX_OVERLAY_FILE_BYTES:
            return None
        content = raw_content.decode("utf-8-sig")
    except (OSError, UnicodeError):
        return None
    parser = ManifestParser()
    try:
        parser.feed(content)
        raw = json.loads(parser.payload or "")
    except (ValueError, TypeError):
        return None
    if not isinstance(raw, dict):
        return None

    name = _text(raw.get("name"), 80)
    description = _text(raw.get("description"), 240)
    category = _text(raw.get("category"), 32).lower()
    canvas = raw.get("canvas") if isinstance(raw.get("canvas"), dict) else {}
    try:
        width = int(canvas.get("w"))
        height = int(canvas.get("h"))
    except (TypeError, ValueError):
        return None
    if (
        not name
        or not description
        or not SETTING_NAME.fullmatch(category)
        or not 100 <= width <= 4096
        or not 100 <= height <= 4096
    ):
        return None

    settings: list[str] = []
    supplied_settings = raw.get("settings")
    if isinstance(supplied_settings, list):
        for supplied in supplied_settings[:32]:
            setting = str(supplied or "")
            if SETTING_NAME.fullmatch(setting) and setting not in settings:
                settings.append(setting)

    studio_view = str(raw.get("studioView") or "")
    if studio_view and not SETTING_NAME.fullmatch(studio_view):
        studio_view = ""
    return {
        "type": overlay_type,
        "name": name,
        "description": description,
        "category": category,
        "canvas": {"w": width, "h": height},
        "settings": settings,
        "studioView": studio_view,
        "route": f"/overlays/{overlay_type}",
    }


def clear_overlay_manifest_cache() -> None:
    with _manifest_cache_lock:
        _manifest_cache.clear()


def scan_overlay_manifests(overlays_dir: Path) -> list[dict[str, Any]]:
    try:
        paths = sorted(overlays_dir.glob("*.html"))
    except OSError:
        return []

    readable_paths: list[Path] = []
    snapshot_entries: list[tuple[str, int, int]] = []
    for path in paths:
        try:
            metadata = path.stat()
        except OSError:
            continue
        readable_paths.append(path)
        snapshot_entries.append(
            (path.name, metadata.st_mtime_ns, metadata.st_size)
        )

    try:
        cache_key = overlays_dir.resolve()
    except OSError:
        cache_key = overlays_dir.absolute()
    snapshot = tuple(snapshot_entries)
    with _manifest_cache_lock:
        cached = _manifest_cache.get(cache_key)
        if cached is not None and cached[0] == snapshot:
            return copy.deepcopy(cached[1])

    manifests: list[dict[str, Any]] = []
    for path in readable_paths:
        manifest = read_overlay_manifest(path)
        if manifest is not None:
            manifests.append(manifest)

    with _manifest_cache_lock:
        _manifest_cache[cache_key] = (snapshot, copy.deepcopy(manifests))
    return copy.deepcopy(manifests)
