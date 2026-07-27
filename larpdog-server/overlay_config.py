from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any


DEFAULT_DANCE_PROFILE: dict[str, Any] = {
    "id": "default",
    "name": "Default",
    "mode": "single",
    "gif": "assets/dancing-dog.gif",
    "pool": ["assets/dancing-dog.gif"],
    "rest": "assets/resting-dog.png",
    "position": "bottom-left",
    "scale": 1.0,
    "sensitivity": 1.0,
    "fallbackBpm": 120,
}

SOCIAL_PLATFORMS = (
    "twitch",
    "youtube",
    "instagram",
    "x",
    "twitter",
    "tiktok",
    "discord",
    "kick",
    "facebook",
    "snapchat",
    "telegram",
    "whatsapp",
    "linkedin",
    "threads",
    "bluesky",
    "reddit",
)
DEFAULT_SOCIAL_ACCOUNTS = [
    {
        "platform": platform,
        "enabled": platform in {"twitch", "youtube", "instagram", "tiktok"},
        "handle": "yourname",
    }
    for platform in SOCIAL_PLATFORMS
]
DEFAULT_SOCIAL_CONFIG: dict[str, Any] = {
    "accounts": copy.deepcopy(DEFAULT_SOCIAL_ACCOUNTS),
    "layout": "sticker",
    "mode": "individual",
    "sharedName": "",
    "heading": "Stay connected",
    "align": "center",
    "iconShape": "rounded",
    "size": "medium",
    "brand": True,
    "color": "f6f7fb",
    "shellColor": "141418",
    "textColor": "ffffff",
    "font": "display",
    "weight": 800,
    "outline": 3,
    "scale": 1.0,
    "cycle": 4.0,
    "rotatorShape": "capsule",
    "transition": "slide",
    "prefix": "@",
    "timer": True,
    "showPlatform": True,
}


DEFAULT_OVERLAY_CONFIG: dict[str, Any] = {
    "dance": {
        "name": "Dancing GIF",
        "activeProfileId": DEFAULT_DANCE_PROFILE["id"],
        "profiles": [copy.deepcopy(DEFAULT_DANCE_PROFILE)],
        "mode": DEFAULT_DANCE_PROFILE["mode"],
        "gif": DEFAULT_DANCE_PROFILE["gif"],
        "pool": list(DEFAULT_DANCE_PROFILE["pool"]),
        "rest": DEFAULT_DANCE_PROFILE["rest"],
        "position": DEFAULT_DANCE_PROFILE["position"],
        "scale": DEFAULT_DANCE_PROFILE["scale"],
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
    "social": copy.deepcopy(DEFAULT_SOCIAL_CONFIG),
}

INSTANCE_ID_PATTERN = r"[A-Za-z0-9][A-Za-z0-9_-]*"
INSTANCE_ID = re.compile(rf"^{INSTANCE_ID_PATTERN}$")
DANCE_PROFILE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,31}$")
POSITION_CHOICES = {"bottom-left", "bottom-right", "top-left", "top-right"}
DANCE_MODE_CHOICES = {"single", "random"}
COLOR_MODE_CHOICES = {"auto", "fixed", "art"}
SOCIAL_LAYOUT_CHOICES = {"sticker", "flat", "compact", "stacked", "fused"}
SOCIAL_MODE_CHOICES = {"individual", "shared"}
SOCIAL_ALIGN_CHOICES = {"left", "center", "right"}
SOCIAL_ICON_SHAPES = {"rounded", "circle", "square", "diamond", "hex"}
SOCIAL_SIZE_CHOICES = {"small", "medium", "large"}
SOCIAL_FONT_CHOICES = {"sans", "display", "round", "mono", "serif"}
SOCIAL_ROTATOR_SHAPES = {"capsule", "rounded", "square", "cut"}
SOCIAL_TRANSITIONS = {"slide", "fade", "flip"}
HEX_COLOR = re.compile(r"^[0-9a-fA-F]{6}$")
MAX_INSTANCES = 64
MAX_DANCE_PROFILES = 5
MAX_SOCIAL_BAR_ACCOUNTS = 8

LEGACY_INSTANCE_SPECS = (
    ("dancing-gif", "larpdog-dance", "Dancing GIF"),
    ("spotify-overlay", "spotify", "Spotify Overlay"),
    ("match-record", "win-loss", "Match Record"),
    ("now-playing-flow", "now-playing-flow", "Now Playing Flow"),
)
LEGACY_INSTANCE_IDS = {
    overlay_type: instance_id
    for instance_id, overlay_type, _name in LEGACY_INSTANCE_SPECS
}


def is_valid_instance_id(value: Any) -> bool:
    return bool(INSTANCE_ID.fullmatch(str(value or "")))


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


def _profile_name(value: Any, default: str) -> str:
    candidate = " ".join(str(value or "").split())
    return candidate[:32] or default


def normalize_overlay_name(value: Any, default: str = "Overlay") -> str:
    return _overlay_name(value, default)


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


def _short_text(value: Any, default: str, maximum: int) -> str:
    candidate = " ".join(str(value or "").split())
    return candidate[:maximum] if candidate else default


def _normalize_social_accounts(
    raw: Any,
    *,
    overlay_type: str,
) -> list[dict[str, Any]]:
    supplied = raw if isinstance(raw, list) else []
    has_supplied_accounts = isinstance(raw, list)
    by_platform: dict[str, dict[str, Any]] = {}
    for item in supplied[: len(SOCIAL_PLATFORMS)]:
        if not isinstance(item, dict):
            continue
        platform = str(item.get("platform") or "").strip().lower()
        if platform not in SOCIAL_PLATFORMS or platform in by_platform:
            continue
        handle = _short_text(
            str(item.get("handle") or "").lstrip("@"),
            "",
            64,
        )
        by_platform[platform] = {
            "platform": platform,
            "enabled": bool(item.get("enabled")),
            "handle": handle,
        }

    accounts: list[dict[str, Any]] = []
    enabled_count = 0
    for default in DEFAULT_SOCIAL_ACCOUNTS:
        fallback = (
            {
                "platform": default["platform"],
                "enabled": False,
                "handle": default["handle"],
            }
            if has_supplied_accounts
            else copy.deepcopy(default)
        )
        account = by_platform.get(default["platform"], fallback)
        enabled = bool(account["enabled"])
        if (
            overlay_type == "social"
            and enabled
            and enabled_count >= MAX_SOCIAL_BAR_ACCOUNTS
        ):
            enabled = False
        if enabled:
            enabled_count += 1
        accounts.append(
            {
                "platform": default["platform"],
                "enabled": enabled,
                "handle": account["handle"],
            }
        )
    return accounts


def _normalize_social(raw: Any, overlay_type: str = "social") -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    defaults = DEFAULT_SOCIAL_CONFIG
    prefix = (
        defaults["prefix"]
        if "prefix" not in source
        else " ".join(str(source.get("prefix") or "").split())[:4]
    )
    return {
        "accounts": _normalize_social_accounts(
            source.get("accounts"),
            overlay_type=overlay_type,
        ),
        "layout": _choice(
            source.get("layout"),
            SOCIAL_LAYOUT_CHOICES,
            defaults["layout"],
        ),
        "mode": _choice(
            source.get("mode"),
            SOCIAL_MODE_CHOICES,
            defaults["mode"],
        ),
        "sharedName": _short_text(source.get("sharedName"), "", 64),
        "heading": _short_text(
            source.get("heading"),
            defaults["heading"],
            32,
        ),
        "align": _choice(
            source.get("align"),
            SOCIAL_ALIGN_CHOICES,
            defaults["align"],
        ),
        "iconShape": _choice(
            source.get("iconShape"),
            SOCIAL_ICON_SHAPES,
            defaults["iconShape"],
        ),
        "size": _choice(
            source.get("size"),
            SOCIAL_SIZE_CHOICES,
            defaults["size"],
        ),
        "brand": bool(source.get("brand", defaults["brand"])),
        "color": _color(source.get("color"), defaults["color"]),
        "shellColor": _color(
            source.get("shellColor"),
            defaults["shellColor"],
        ),
        "textColor": _color(
            source.get("textColor"),
            defaults["textColor"],
        ),
        "font": _choice(
            source.get("font"),
            SOCIAL_FONT_CHOICES,
            defaults["font"],
        ),
        "weight": int(
            round(_number(source.get("weight"), defaults["weight"], 300, 900))
        ),
        "outline": int(
            round(_number(source.get("outline"), defaults["outline"], 0, 8))
        ),
        "scale": round(
            _number(source.get("scale"), defaults["scale"], 0.5, 2.0),
            2,
        ),
        "cycle": round(
            _number(source.get("cycle"), defaults["cycle"], 1.5, 30.0),
            1,
        ),
        "rotatorShape": _choice(
            source.get("rotatorShape"),
            SOCIAL_ROTATOR_SHAPES,
            defaults["rotatorShape"],
        ),
        "transition": _choice(
            source.get("transition"),
            SOCIAL_TRANSITIONS,
            defaults["transition"],
        ),
        "prefix": prefix,
        "timer": bool(source.get("timer", defaults["timer"])),
        "showPlatform": bool(
            source.get("showPlatform", defaults["showPlatform"])
        ),
    }


def _profile_id(value: Any, index: int, used_ids: set[str]) -> str:
    candidate = str(value or "").strip()
    if not DANCE_PROFILE_ID.fullmatch(candidate) or candidate in used_ids:
        candidate = "default" if index == 0 else f"profile-{index + 1}"
    suffix = 2
    unique = candidate
    while unique in used_ids:
        unique = f"{candidate[:28]}-{suffix}"
        suffix += 1
    return unique


def _normalize_dance_profile(
    raw: Any,
    *,
    index: int,
    used_ids: set[str],
    fallback: dict[str, Any],
) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    profile_id = _profile_id(source.get("id"), index, used_ids)
    used_ids.add(profile_id)
    dance_gif = _asset_path(source.get("gif"), fallback["gif"])
    dance_pool = _asset_list(source.get("pool"), [dance_gif])
    if dance_gif not in dance_pool:
        dance_pool.insert(0, dance_gif)
    return {
        "id": profile_id,
        "name": _profile_name(source.get("name"), f"Profile {index + 1}"),
        "mode": _choice(
            source.get("mode"),
            DANCE_MODE_CHOICES,
            fallback["mode"],
        ),
        "gif": dance_gif,
        "pool": dance_pool,
        "rest": _asset_path(source.get("rest"), fallback["rest"]),
        "position": _choice(
            source.get("position"),
            POSITION_CHOICES,
            fallback["position"],
        ),
        "scale": round(
            _number(source.get("scale"), fallback["scale"], 0.5, 2.0),
            2,
        ),
        "sensitivity": round(
            _number(
                source.get("sensitivity"),
                fallback["sensitivity"],
                0.3,
                3.0,
            ),
            2,
        ),
        "fallbackBpm": int(
            round(
                _number(
                    source.get("fallbackBpm"),
                    fallback["fallbackBpm"],
                    40,
                    240,
                )
            )
        ),
    }


def _normalize_flat_config(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    legacy = (
        source.get("appearance")
        if isinstance(source.get("appearance"), dict)
        else {}
    )
    dance = source.get("dance") if isinstance(source.get("dance"), dict) else {}
    spotify = (
        source.get("spotify") if isinstance(source.get("spotify"), dict) else {}
    )
    flow = source.get("flow") if isinstance(source.get("flow"), dict) else {}
    audio = source.get("audio") if isinstance(source.get("audio"), dict) else {}
    now_playing = (
        source.get("nowPlaying")
        if isinstance(source.get("nowPlaying"), dict)
        else {}
    )
    social = source.get("social") if isinstance(source.get("social"), dict) else {}
    colors = (
        spotify.get("colors")
        if isinstance(spotify.get("colors"), dict)
        else {}
    )
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
    dance_mode = _choice(
        dance.get("mode"),
        DANCE_MODE_CHOICES,
        default_dance["mode"],
    )
    dance_rest = _asset_path(
        dance.get("rest", legacy.get("rest")),
        default_dance["rest"],
    )
    dance_position = _choice(
        dance.get("position", legacy.get("position")),
        POSITION_CHOICES,
        default_dance["position"],
    )
    dance_scale = round(
        _number(
            dance.get("scale", legacy.get("scale")),
            default_dance["scale"],
            0.5,
            2.0,
        ),
        2,
    )
    audio_sensitivity = round(
        _number(
            audio.get("sensitivity"),
            defaults["audio"]["sensitivity"],
            0.3,
            3.0,
        ),
        2,
    )
    fallback_bpm = int(
        round(
            _number(
                now_playing.get("fallbackBpm"),
                defaults["nowPlaying"]["fallbackBpm"],
                40,
                240,
            )
        )
    )
    profile_fallback = {
        "mode": dance_mode,
        "gif": dance_gif,
        "pool": dance_pool,
        "rest": dance_rest,
        "position": dance_position,
        "scale": dance_scale,
        "sensitivity": audio_sensitivity,
        "fallbackBpm": fallback_bpm,
    }
    supplied_profiles = dance.get("profiles")
    profile_sources = (
        supplied_profiles[:MAX_DANCE_PROFILES]
        if isinstance(supplied_profiles, list)
        else []
    )
    if not profile_sources:
        profile_sources = [
            {
                "id": "default",
                "name": "Default",
                **profile_fallback,
            }
        ]
    used_profile_ids: set[str] = set()
    dance_profiles = [
        _normalize_dance_profile(
            profile,
            index=index,
            used_ids=used_profile_ids,
            fallback=profile_fallback,
        )
        for index, profile in enumerate(profile_sources)
        if isinstance(profile, dict)
    ]
    if not dance_profiles:
        dance_profiles = [
            _normalize_dance_profile(
                {
                    "id": "default",
                    "name": "Default",
                    **profile_fallback,
                },
                index=0,
                used_ids=set(),
                fallback=profile_fallback,
            )
        ]
    requested_profile_id = str(dance.get("activeProfileId") or "").strip()
    active_profile = next(
        (
            profile
            for profile in dance_profiles
            if profile["id"] == requested_profile_id
        ),
        dance_profiles[0],
    )

    return {
        "dance": {
            "name": _overlay_name(dance.get("name"), default_dance["name"]),
            "activeProfileId": active_profile["id"],
            "profiles": dance_profiles,
            "mode": active_profile["mode"],
            "gif": active_profile["gif"],
            "pool": list(active_profile["pool"]),
            "rest": active_profile["rest"],
            "position": active_profile["position"],
            "scale": active_profile["scale"],
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
            "sensitivity": active_profile["sensitivity"],
        },
        "nowPlaying": {
            "fallbackBpm": active_profile["fallbackBpm"],
        },
        "social": _normalize_social(social),
    }


def _instance_config(
    overlay_type: str,
    raw: Any,
    fallback: dict[str, Any],
) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    combined: dict[str, Any] = {}
    keys: tuple[str, ...]
    if overlay_type == "larpdog-dance":
        keys = ("dance", "audio", "nowPlaying")
    elif overlay_type == "spotify":
        keys = ("spotify",)
    elif overlay_type == "now-playing-flow":
        keys = ("flow",)
    elif overlay_type in {"social", "social-rotator"}:
        return {
            "social": _normalize_social(
                source.get("social"),
                overlay_type,
            )
        }
    else:
        return {}
    for key in keys:
        value = source.get(key, fallback.get(key))
        if isinstance(value, dict):
            combined[key] = value
    normalized = _normalize_flat_config(combined)
    return {key: normalized[key] for key in keys}


def _legacy_instances(flat: dict[str, Any]) -> dict[str, dict[str, Any]]:
    instances: dict[str, dict[str, Any]] = {}
    for instance_id, overlay_type, default_name in LEGACY_INSTANCE_SPECS:
        name = default_name
        if overlay_type == "larpdog-dance":
            name = flat["dance"]["name"]
        elif overlay_type == "now-playing-flow":
            name = flat["flow"]["name"]
        instances[instance_id] = {
            "id": instance_id,
            "type": overlay_type,
            "name": name,
            "config": _instance_config(overlay_type, flat, flat),
        }
    return instances


def normalize_overlay_config(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    flat = _normalize_flat_config(source)
    has_instances = "instances" in source
    supplied_instances = (
        source.get("instances")
        if isinstance(source.get("instances"), dict)
        else {}
    )
    instances: dict[str, dict[str, Any]] = {}
    if has_instances:
        for supplied_id, supplied in list(supplied_instances.items())[:MAX_INSTANCES]:
            instance_id = str(supplied_id or "")
            if not is_valid_instance_id(instance_id) or not isinstance(supplied, dict):
                continue
            overlay_type = str(supplied.get("type") or "").strip()
            if not is_valid_instance_id(overlay_type):
                continue
            instances[instance_id] = {
                "id": instance_id,
                "type": overlay_type,
                "name": _overlay_name(
                    supplied.get("name"),
                    overlay_type.replace("-", " ").title(),
                ),
                "config": _instance_config(
                    overlay_type,
                    supplied.get("config"),
                    flat,
                ),
            }
    else:
        instances = _legacy_instances(flat)

    return {
        **flat,
        "instances": instances,
    }


def materialize_instance_config(
    raw: Any,
    instance_id: str | None,
) -> dict[str, Any]:
    config = normalize_overlay_config(raw)
    materialized = {
        key: copy.deepcopy(config[key])
        for key in (
            "dance",
            "spotify",
            "flow",
            "audio",
            "nowPlaying",
            "social",
        )
    }
    if not instance_id:
        return materialized
    instance = config["instances"].get(str(instance_id))
    if not isinstance(instance, dict):
        return materialized
    for key, value in instance["config"].items():
        materialized[key] = copy.deepcopy(value)
    return materialized


def update_instance_config(
    raw: Any,
    instance_id: str,
    submitted: Any,
) -> dict[str, Any]:
    config = normalize_overlay_config(raw)
    instance = config["instances"].get(str(instance_id))
    if not isinstance(instance, dict):
        raise ValueError("Overlay instance not found")
    current = materialize_instance_config(config, instance_id)
    source = submitted if isinstance(submitted, dict) else {}
    merged = copy.deepcopy(current)
    for key in ("dance", "spotify", "flow", "audio", "nowPlaying", "social"):
        if isinstance(source.get(key), dict):
            merged[key] = source[key]
    instance["config"] = _instance_config(instance["type"], merged, current)

    if LEGACY_INSTANCE_IDS.get(instance["type"]) == instance_id:
        for key, value in instance["config"].items():
            config[key] = copy.deepcopy(value)
    return normalize_overlay_config(config)


def add_overlay_instance(
    raw: Any,
    overlay_type: str,
    instance_id: str,
    name: str,
) -> dict[str, Any]:
    config = normalize_overlay_config(raw)
    if not is_valid_instance_id(overlay_type) or not is_valid_instance_id(instance_id):
        raise ValueError("Invalid overlay instance")
    if instance_id in config["instances"]:
        raise ValueError("Overlay instance already exists")
    if len(config["instances"]) >= MAX_INSTANCES:
        raise ValueError("Overlay instance limit reached")
    flat = materialize_instance_config(config, None)
    config["instances"][instance_id] = {
        "id": instance_id,
        "type": overlay_type,
        "name": _overlay_name(name, overlay_type.replace("-", " ").title()),
        "config": _instance_config(overlay_type, flat, flat),
    }
    return normalize_overlay_config(config)


def rename_overlay_instance(
    raw: Any,
    instance_id: str,
    name: Any,
) -> dict[str, Any]:
    config = normalize_overlay_config(raw)
    instance = config["instances"].get(str(instance_id))
    if not isinstance(instance, dict):
        raise ValueError("Overlay instance not found")
    instance["name"] = _overlay_name(name, instance["name"])
    return normalize_overlay_config(config)


def remove_overlay_instance(raw: Any, instance_id: str) -> dict[str, Any]:
    config = normalize_overlay_config(raw)
    if str(instance_id) not in config["instances"]:
        raise ValueError("Overlay instance not found")
    del config["instances"][str(instance_id)]
    return normalize_overlay_config(config)


def load_overlay_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return normalize_overlay_config({})
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return normalize_overlay_config({})
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
