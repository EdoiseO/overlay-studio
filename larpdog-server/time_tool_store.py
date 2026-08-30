from __future__ import annotations

import json
import math
import re
import time
from pathlib import Path
from typing import Any


CLOCK_TIME_TOOL_OVERLAY_TYPES = {
    "minecraft-clock-line",
}
COUNTDOWN_TIME_TOOL_OVERLAY_TYPES = {
    "minecraft-countdown-line",
}
STOPWATCH_TIME_TOOL_OVERLAY_TYPES = {
    "minecraft-stopwatch-line",
}
TIME_TOOL_OVERLAY_TYPES = {
    *CLOCK_TIME_TOOL_OVERLAY_TYPES,
    *COUNTDOWN_TIME_TOOL_OVERLAY_TYPES,
    *STOPWATCH_TIME_TOOL_OVERLAY_TYPES,
}
TIME_ZONE_CHOICES = {
    "local",
    "UTC",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Phoenix",
    "America/Los_Angeles",
    "America/Anchorage",
    "Pacific/Honolulu",
}
ACTIONS = {"start", "pause", "reset", "test-sound"}
HEX_COLOR = re.compile(r"^[0-9a-fA-F]{6}$")
INSTANCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
MAX_DURATION_SECONDS = 359_999
MAX_TIMER_MILLISECONDS = MAX_DURATION_SECONDS * 1000
MAX_TIMESTAMP_MILLISECONDS = 4_102_444_800_000

COMMON_DEFAULTS: dict[str, Any] = {
    "accentColor": "70b237",
    "shellColor": "292725",
    "textColor": "fffbed",
    "showLabel": True,
    "scale": 1.0,
    "glow": 0.7,
    "digitShadow": 1.0,
}
CLOCK_DEFAULTS: dict[str, Any] = {
    **COMMON_DEFAULTS,
    "label": "LOCAL TIME",
    "timezone": "local",
    "timezoneLabel": "",
    "hour12": True,
    "showSeconds": True,
    "showDate": True,
}
COUNTDOWN_DEFAULTS: dict[str, Any] = {
    **COMMON_DEFAULTS,
    "label": "STARTING IN",
    "durationSeconds": 600,
    "remainingMs": 600_000,
    "running": False,
    "startedAt": 0,
    "finishText": "TIME'S UP",
    "showTenths": False,
    "soundEnabled": True,
    "soundVolume": 0.8,
}
STOPWATCH_DEFAULTS: dict[str, Any] = {
    **COMMON_DEFAULTS,
    "label": "TIME SPENT",
    "elapsedMs": 0,
    "running": False,
    "startedAt": 0,
    "showTenths": False,
}


def _line_defaults(defaults: dict[str, Any]) -> dict[str, Any]:
    return {
        **defaults,
        "glow": 0.0,
        "digitShadow": 0.0,
    }


DEFAULT_TIME_TOOL_STATES: dict[str, dict[str, Any]] = {
    "minecraft-clock-line": _line_defaults(CLOCK_DEFAULTS),
    "minecraft-countdown-line": _line_defaults(COUNTDOWN_DEFAULTS),
    "minecraft-stopwatch-line": _line_defaults(STOPWATCH_DEFAULTS),
}


def time_tool_defaults_for_type(overlay_type: str) -> dict[str, Any]:
    defaults = DEFAULT_TIME_TOOL_STATES.get(overlay_type)
    if defaults is None:
        raise ValueError("Unknown time-tool overlay type")
    return dict(defaults)


def _number(value: Any, default: float, minimum: float, maximum: float) -> float:
    try:
        candidate = float(value)
    except (TypeError, ValueError):
        candidate = default
    if not math.isfinite(candidate):
        candidate = default
    return max(minimum, min(maximum, candidate))


def _boolean(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    candidate = str(value or "").strip().lower()
    if candidate in {"1", "true", "yes", "on"}:
        return True
    if candidate in {"0", "false", "no", "off"}:
        return False
    return default


def _text(value: Any, default: str, maximum: int, *, allow_empty: bool = False) -> str:
    candidate = " ".join(str(value if value is not None else default).split())
    candidate = "".join(
        character
        for character in candidate
        if character >= " " and character != "\x7f"
    )[:maximum]
    if candidate or allow_empty:
        return candidate
    return default


def _color(value: Any, default: str) -> str:
    candidate = str(value or "").strip().removeprefix("#")
    return candidate.lower() if HEX_COLOR.fullmatch(candidate) else default


def _common_state(source: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": _text(source.get("label"), defaults["label"], 32),
        "accentColor": _color(
            source.get("accentColor"),
            defaults["accentColor"],
        ),
        "shellColor": _color(
            source.get("shellColor"),
            defaults["shellColor"],
        ),
        "textColor": _color(
            source.get("textColor"),
            defaults["textColor"],
        ),
        "showLabel": _boolean(
            source.get("showLabel"),
            defaults["showLabel"],
        ),
        "scale": round(
            _number(source.get("scale"), defaults["scale"], 0.5, 1.25),
            2,
        ),
        "glow": round(
            _number(source.get("glow"), defaults["glow"], 0, 2),
            2,
        ),
        "digitShadow": round(
            _number(
                source.get("digitShadow"),
                defaults["digitShadow"],
                0,
                1,
            ),
            2,
        ),
    }


def normalize_time_tool_state(raw: Any, overlay_type: str) -> dict[str, Any]:
    defaults = time_tool_defaults_for_type(overlay_type)
    source = raw if isinstance(raw, dict) else {}
    state = _common_state(source, defaults)

    if overlay_type in CLOCK_TIME_TOOL_OVERLAY_TYPES:
        timezone = str(source.get("timezone") or "").strip()
        state.update(
            {
                "timezone": (
                    timezone
                    if timezone in TIME_ZONE_CHOICES
                    else defaults["timezone"]
                ),
                "timezoneLabel": _text(
                    source.get("timezoneLabel"),
                    defaults["timezoneLabel"],
                    16,
                    allow_empty=True,
                ),
                "hour12": _boolean(source.get("hour12"), defaults["hour12"]),
                "showSeconds": _boolean(
                    source.get("showSeconds"),
                    defaults["showSeconds"],
                ),
                "showDate": _boolean(
                    source.get("showDate"),
                    defaults["showDate"],
                ),
            }
        )
        return state

    state["running"] = _boolean(source.get("running"), defaults["running"])
    state["startedAt"] = int(
        round(
            _number(
                source.get("startedAt"),
                defaults["startedAt"],
                0,
                MAX_TIMESTAMP_MILLISECONDS,
            )
        )
    )
    state["showTenths"] = _boolean(
        source.get("showTenths"),
        defaults["showTenths"],
    )

    if overlay_type in COUNTDOWN_TIME_TOOL_OVERLAY_TYPES:
        duration = int(
            round(
                _number(
                    source.get("durationSeconds"),
                    defaults["durationSeconds"],
                    1,
                    MAX_DURATION_SECONDS,
                )
            )
        )
        state.update(
            {
                "durationSeconds": duration,
                "remainingMs": int(
                    round(
                        _number(
                            source.get("remainingMs"),
                            duration * 1000,
                            0,
                            duration * 1000,
                        )
                    )
                ),
                "finishText": _text(
                    source.get("finishText"),
                    defaults["finishText"],
                    24,
                ),
                "soundEnabled": _boolean(
                    source.get("soundEnabled"),
                    defaults["soundEnabled"],
                ),
                "soundVolume": round(
                    _number(
                        source.get("soundVolume"),
                        defaults["soundVolume"],
                        0.0,
                        1.0,
                    ),
                    2,
                ),
            }
        )
    elif overlay_type in STOPWATCH_TIME_TOOL_OVERLAY_TYPES:
        state["elapsedMs"] = int(
            round(
                _number(
                    source.get("elapsedMs"),
                    defaults["elapsedMs"],
                    0,
                    MAX_TIMER_MILLISECONDS,
                )
            )
        )
    return state


def snapshot_time_tool_state(
    raw: Any,
    overlay_type: str,
    now_ms: int | None = None,
) -> dict[str, Any]:
    state = normalize_time_tool_state(raw, overlay_type)
    if overlay_type in CLOCK_TIME_TOOL_OVERLAY_TYPES or not state["running"]:
        return state
    now = int(time.time() * 1000) if now_ms is None else int(now_ms)
    delta = max(0, now - state["startedAt"])
    if overlay_type in COUNTDOWN_TIME_TOOL_OVERLAY_TYPES:
        state["remainingMs"] = max(0, state["remainingMs"] - delta)
        if state["remainingMs"] == 0:
            state["running"] = False
            state["startedAt"] = 0
        else:
            state["startedAt"] = now
    else:
        state["elapsedMs"] = min(
            MAX_TIMER_MILLISECONDS,
            state["elapsedMs"] + delta,
        )
        if state["elapsedMs"] >= MAX_TIMER_MILLISECONDS:
            state["running"] = False
            state["startedAt"] = 0
        else:
            state["startedAt"] = now
    return state


def apply_time_tool_update(
    current: Any,
    raw: Any,
    overlay_type: str,
    now_ms: int | None = None,
) -> dict[str, Any]:
    if overlay_type not in TIME_TOOL_OVERLAY_TYPES:
        raise ValueError("Unknown time-tool overlay type")
    source = raw if isinstance(raw, dict) else {}
    now = int(time.time() * 1000) if now_ms is None else int(now_ms)
    state = snapshot_time_tool_state(current, overlay_type, now)
    action = str(source.get("action") or "").strip().lower()
    if action and action not in ACTIONS:
        raise ValueError(f"Unknown time-tool action: {action}")

    for key in (
        "label",
        "accentColor",
        "shellColor",
        "textColor",
        "showLabel",
        "scale",
        "glow",
        "digitShadow",
        "showTenths",
    ):
        if key in source:
            state[key] = source[key]

    if overlay_type in CLOCK_TIME_TOOL_OVERLAY_TYPES:
        for key in (
            "timezone",
            "timezoneLabel",
            "hour12",
            "showSeconds",
            "showDate",
        ):
            if key in source:
                state[key] = source[key]
        return normalize_time_tool_state(state, overlay_type)

    if overlay_type in COUNTDOWN_TIME_TOOL_OVERLAY_TYPES:
        if "finishText" in source:
            state["finishText"] = source["finishText"]
        if "soundEnabled" in source:
            state["soundEnabled"] = source["soundEnabled"]
        if "soundVolume" in source:
            state["soundVolume"] = source["soundVolume"]
        if "durationSeconds" in source:
            normalized_duration = normalize_time_tool_state(
                {**state, "durationSeconds": source["durationSeconds"]},
                overlay_type,
            )["durationSeconds"]
            if normalized_duration != state["durationSeconds"]:
                state["durationSeconds"] = normalized_duration
                state["remainingMs"] = normalized_duration * 1000
                state["running"] = False
                state["startedAt"] = 0

        if action == "test-sound":
            return normalize_time_tool_state(state, overlay_type)
    elif action == "test-sound":
        raise ValueError("Completion sounds are only available for countdowns")

    if action == "start":
        if (
            overlay_type in COUNTDOWN_TIME_TOOL_OVERLAY_TYPES
            and state["remainingMs"] <= 0
        ):
            state["remainingMs"] = state["durationSeconds"] * 1000
        state["running"] = True
        state["startedAt"] = now
    elif action == "pause":
        state["running"] = False
        state["startedAt"] = 0
    elif action == "reset":
        state["running"] = False
        state["startedAt"] = 0
        if overlay_type in COUNTDOWN_TIME_TOOL_OVERLAY_TYPES:
            state["remainingMs"] = state["durationSeconds"] * 1000
        else:
            state["elapsedMs"] = 0

    return normalize_time_tool_state(state, overlay_type)


def _read_document(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"instances": {}}
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {"instances": {}}
    source = raw if isinstance(raw, dict) else {}
    supplied = source.get("instances")
    return {"instances": supplied if isinstance(supplied, dict) else {}}


def load_time_tool_state(
    path: Path,
    instance_id: str,
    overlay_type: str,
    now_ms: int | None = None,
) -> dict[str, Any]:
    document = _read_document(path)
    raw = document["instances"].get(instance_id, {})
    return snapshot_time_tool_state(raw, overlay_type, now_ms)


def load_time_tool_states(
    path: Path,
    instances: dict[str, dict[str, Any]],
    now_ms: int | None = None,
) -> dict[str, dict[str, Any]]:
    return {
        instance_id: load_time_tool_state(
            path,
            instance_id,
            instance["type"],
            now_ms,
        )
        for instance_id, instance in instances.items()
        if (
            INSTANCE_ID.fullmatch(str(instance_id or ""))
            and instance.get("type") in TIME_TOOL_OVERLAY_TYPES
        )
    }


def save_time_tool_state(
    path: Path,
    raw: Any,
    instance_id: str,
    overlay_type: str,
) -> dict[str, Any]:
    if not INSTANCE_ID.fullmatch(str(instance_id or "")):
        raise ValueError("Invalid time-tool instance")
    state = normalize_time_tool_state(raw, overlay_type)
    document = _read_document(path)
    document["instances"][instance_id] = state
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(document, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)
    return state


def remove_time_tool_instance(path: Path, instance_id: str) -> None:
    document = _read_document(path)
    if document["instances"].pop(str(instance_id), None) is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(document, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)
