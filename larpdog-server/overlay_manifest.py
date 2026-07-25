from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


OVERLAY_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
SETTING_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
MAX_MANIFEST_BYTES = 32 * 1024


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
        content = path.read_text(encoding="utf-8-sig")
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


def scan_overlay_manifests(overlays_dir: Path) -> list[dict[str, Any]]:
    manifests: list[dict[str, Any]] = []
    try:
        paths = sorted(overlays_dir.glob("*.html"))
    except OSError:
        return manifests
    for path in paths:
        manifest = read_overlay_manifest(path)
        if manifest is not None:
            manifests.append(manifest)
    return manifests
