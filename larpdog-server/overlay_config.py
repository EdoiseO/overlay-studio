from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_OVERLAY_CONFIG: dict[str, Any] = {
    "appearance": {
        "asset": "both",
        "dog": "assets/dancing-dog.gif",
        "rest": "assets/resting-dog.png",
        "position": "bottom-left",
        "scale": 1.0,
        "cardWidth": 335,
        "colorMode": "auto",
        "colors": {
            "a": "ff4d9d",
            "b": "ffd24a",
            "c": "5ee0ff",
        },
    },
    "audio": {
        "enabled": True,
        "sensitivity": 1.0,
    },
    "nowPlaying": {
        "fallbackBpm": 120,
    },
}

ASSET_CHOICES = {"both", "dog", "player"}
POSITION_CHOICES = {"bottom-left", "bottom-right", "top-left", "top-right"}
COLOR_MODE_CHOICES = {"auto", "fixed", "art"}
HEX_COLOR = re.compile(r"^[0-9a-fA-F]{6}$")


def _choice(value: Any, choices: set[str], default: str) -> str:
    candidate = str(value or "").strip().lower()
    return candidate if candidate in choices else default


def _number(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        candidate = float(value)
    except (TypeError, ValueError):
        candidate = default
    return max(minimum, min(maximum, candidate))


def _asset_path(value: Any, default: str) -> str:
    candidate = str(value or "").strip()
    if not candidate or len(candidate) > 1024:
        return default
    return candidate


def _color(value: Any, default: str) -> str:
    candidate = str(value or "").strip().removeprefix("#")
    return candidate.lower() if HEX_COLOR.fullmatch(candidate) else default


def normalize_overlay_config(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    appearance = source.get("appearance") if isinstance(source.get("appearance"), dict) else {}
    audio = source.get("audio") if isinstance(source.get("audio"), dict) else {}
    now_playing = (
        source.get("nowPlaying") if isinstance(source.get("nowPlaying"), dict) else {}
    )
    colors = appearance.get("colors") if isinstance(appearance.get("colors"), dict) else {}

    defaults = DEFAULT_OVERLAY_CONFIG
    default_appearance = defaults["appearance"]
    default_colors = default_appearance["colors"]

    return {
        "appearance": {
            "asset": _choice(
                appearance.get("asset"), ASSET_CHOICES, default_appearance["asset"]
            ),
            "dog": _asset_path(appearance.get("dog"), default_appearance["dog"]),
            "rest": _asset_path(appearance.get("rest"), default_appearance["rest"]),
            "position": _choice(
                appearance.get("position"),
                POSITION_CHOICES,
                default_appearance["position"],
            ),
            "scale": round(
                _number(appearance.get("scale"), default_appearance["scale"], 0.5, 2.0),
                2,
            ),
            "cardWidth": int(
                round(
                    _number(
                        appearance.get("cardWidth"),
                        default_appearance["cardWidth"],
                        240,
                        600,
                    )
                )
            ),
            "colorMode": _choice(
                appearance.get("colorMode"),
                COLOR_MODE_CHOICES,
                default_appearance["colorMode"],
            ),
            "colors": {
                "a": _color(colors.get("a"), default_colors["a"]),
                "b": _color(colors.get("b"), default_colors["b"]),
                "c": _color(colors.get("c"), default_colors["c"]),
            },
        },
        "audio": {
            "enabled": bool(audio.get("enabled", defaults["audio"]["enabled"])),
            "sensitivity": round(
                _number(
                    audio.get("sensitivity"),
                    defaults["audio"]["sensitivity"],
                    0.3,
                    3.0,
                ),
                2,
            ),
        },
        "nowPlaying": {
            "fallbackBpm": int(
                round(
                    _number(
                        now_playing.get("fallbackBpm"),
                        defaults["nowPlaying"]["fallbackBpm"],
                        40,
                        240,
                    )
                )
            )
        },
    }


def load_overlay_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return copy.deepcopy(DEFAULT_OVERLAY_CONFIG)
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return copy.deepcopy(DEFAULT_OVERLAY_CONFIG)
    return normalize_overlay_config(raw)


def save_overlay_config(path: Path, raw: Any) -> dict[str, Any]:
    config = normalize_overlay_config(raw)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(config, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)
    return config
