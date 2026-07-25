from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_OVERLAY_CONFIG: dict[str, Any] = {
    "dance": {
        "name": "Dancing GIF",
        "mode": "single",
        "gif": "assets/dancing-dog.gif",
        "pool": ["assets/dancing-dog.gif"],
        "rest": "assets/resting-dog.png",
        "position": "bottom-left",
        "scale": 1.0,
    },
    "spotify": {
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
    "flow": {
        "name": "Now Playing Flow",
        "scale": 1.0,
        "glow": 1.0,
    },
    "audio": {
        "enabled": True,
        "sensitivity": 1.0,
    },
    "nowPlaying": {
        "fallbackBpm": 120,
    },
}

POSITION_CHOICES = {"bottom-left", "bottom-right", "top-left", "top-right"}
DANCE_MODE_CHOICES = {"single", "random"}
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


def _overlay_name(value: Any, default: str) -> str:
    candidate = " ".join(str(value or "").split())
    return candidate[:48] or default


def _asset_list(value: Any, default: list[str]) -> list[str]:
    if not isinstance(value, list):
        return list(default)
    assets: list[str] = []
    for item in value[:32]:
        candidate = str(item or "").strip()
        if candidate and len(candidate) <= 1024 and candidate not in assets:
            assets.append(candidate)
    return assets or list(default)


def _color(value: Any, default: str) -> str:
    candidate = str(value or "").strip().removeprefix("#")
    return candidate.lower() if HEX_COLOR.fullmatch(candidate) else default


def normalize_overlay_config(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    legacy = source.get("appearance") if isinstance(source.get("appearance"), dict) else {}
    dance = source.get("dance") if isinstance(source.get("dance"), dict) else {}
    spotify = source.get("spotify") if isinstance(source.get("spotify"), dict) else {}
    flow = source.get("flow") if isinstance(source.get("flow"), dict) else {}
    audio = source.get("audio") if isinstance(source.get("audio"), dict) else {}
    now_playing = (
        source.get("nowPlaying") if isinstance(source.get("nowPlaying"), dict) else {}
    )
    colors = spotify.get("colors") if isinstance(spotify.get("colors"), dict) else {}
    if not colors and isinstance(legacy.get("colors"), dict):
        colors = legacy["colors"]

    defaults = DEFAULT_OVERLAY_CONFIG
    default_dance = defaults["dance"]
    default_spotify = defaults["spotify"]
    default_flow = defaults["flow"]
    default_colors = default_spotify["colors"]
    dance_gif = _asset_path(
        dance.get("gif", dance.get("media", legacy.get("dog"))),
        default_dance["gif"],
    )
    dance_pool = _asset_list(dance.get("pool"), [dance_gif])
    if dance_gif not in dance_pool:
        dance_pool.insert(0, dance_gif)

    return {
        "dance": {
            "name": _overlay_name(dance.get("name"), default_dance["name"]),
            "mode": _choice(
                dance.get("mode"),
                DANCE_MODE_CHOICES,
                default_dance["mode"],
            ),
            "gif": dance_gif,
            "pool": dance_pool,
            "rest": _asset_path(
                dance.get("rest", legacy.get("rest")),
                default_dance["rest"],
            ),
            "position": _choice(
                dance.get("position", legacy.get("position")),
                POSITION_CHOICES,
                default_dance["position"],
            ),
            "scale": round(
                _number(
                    dance.get("scale", legacy.get("scale")),
                    default_dance["scale"],
                    0.5,
                    2.0,
                ),
                2,
            ),
        },
        "spotify": {
            "position": _choice(
                spotify.get("position", legacy.get("position")),
                POSITION_CHOICES,
                default_spotify["position"],
            ),
            "scale": round(
                _number(
                    spotify.get("scale", legacy.get("scale")),
                    default_spotify["scale"],
                    0.5,
                    2.0,
                ),
                2,
            ),
            "cardWidth": int(
                round(
                    _number(
                        spotify.get("cardWidth", legacy.get("cardWidth")),
                        default_spotify["cardWidth"],
                        240,
                        600,
                    )
                )
            ),
            "colorMode": _choice(
                spotify.get("colorMode", legacy.get("colorMode")),
                COLOR_MODE_CHOICES,
                default_spotify["colorMode"],
            ),
            "colors": {
                "a": _color(colors.get("a"), default_colors["a"]),
                "b": _color(colors.get("b"), default_colors["b"]),
                "c": _color(colors.get("c"), default_colors["c"]),
            },
        },
        "flow": {
            "name": _overlay_name(flow.get("name"), default_flow["name"]),
            "scale": round(
                _number(
                    flow.get("scale"),
                    default_flow["scale"],
                    0.5,
                    2.0,
                ),
                2,
            ),
            "glow": round(
                _number(
                    flow.get("glow"),
                    default_flow["glow"],
                    0.0,
                    2.0,
                ),
                2,
            ),
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
