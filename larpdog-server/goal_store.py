from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Iterable


DEFAULT_GOAL_STATE: dict[str, Any] = {
    "label": "Tip goal",
    "current": 0.0,
    "target": 50.0,
    "format": "currency",
    "symbol": "$",
    "color": "ffe2a0",
    "track": "3c3028",
    "labelColor": "f5e3be",
    "font": "serif",
    "weight": 500,
    "particles": True,
    "percent": True,
    "scale": 1.0,
    "glow": 1.0,
}

HEX_COLOR = re.compile(r"^[0-9a-fA-F]{6}$")
INSTANCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
FORMAT_CHOICES = {"currency", "number"}
FONT_CHOICES = {"serif", "sans", "round", "mono", "display"}
ACTIONS = {"add", "subtract", "reset", "complete"}
MAX_GOAL_VALUE = 1_000_000_000.0


def _number(
    value: Any,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    try:
        candidate = float(value)
    except (TypeError, ValueError):
        candidate = default
    if not math.isfinite(candidate):
        candidate = default
    return max(minimum, min(maximum, candidate))


def _text(value: Any, default: str, maximum: int) -> str:
    candidate = " ".join(str(value or "").strip().split())
    return candidate[:maximum] or default


def _choice(value: Any, choices: set[str], default: str) -> str:
    candidate = str(value or "").strip().lower()
    return candidate if candidate in choices else default


def _color(value: Any, default: str) -> str:
    candidate = str(value or "").strip().removeprefix("#")
    return candidate.lower() if HEX_COLOR.fullmatch(candidate) else default


def _boolean(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    candidate = str(value or "").strip().lower()
    if candidate in {"1", "true", "yes", "on"}:
        return True
    if candidate in {"0", "false", "no", "off"}:
        return False
    return default


def normalize_goal_state(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    defaults = DEFAULT_GOAL_STATE
    weight = int(
        round(
            _number(
                source.get("weight"),
                defaults["weight"],
                100,
                900,
            )
            / 100
        )
        * 100
    )
    return {
        "label": _text(source.get("label"), defaults["label"], 64),
        "current": round(
            _number(
                source.get("current"),
                defaults["current"],
                0,
                MAX_GOAL_VALUE,
            ),
            2,
        ),
        "target": round(
            _number(
                source.get("target"),
                defaults["target"],
                0.01,
                MAX_GOAL_VALUE,
            ),
            2,
        ),
        "format": _choice(
            source.get("format"),
            FORMAT_CHOICES,
            defaults["format"],
        ),
        "symbol": _text(source.get("symbol"), defaults["symbol"], 4),
        "color": _color(source.get("color"), defaults["color"]),
        "track": _color(source.get("track"), defaults["track"]),
        "labelColor": _color(
            source.get("labelColor"),
            defaults["labelColor"],
        ),
        "font": _choice(
            source.get("font"),
            FONT_CHOICES,
            defaults["font"],
        ),
        "weight": weight,
        "particles": _boolean(
            source.get("particles"),
            defaults["particles"],
        ),
        "percent": _boolean(source.get("percent"), defaults["percent"]),
        "scale": round(
            _number(source.get("scale"), defaults["scale"], 0.5, 1.2),
            2,
        ),
        "glow": round(
            _number(source.get("glow"), defaults["glow"], 0, 2.5),
            2,
        ),
    }


def apply_goal_update(current: dict[str, Any], raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    state = normalize_goal_state(current)
    action = str(source.get("action") or "").strip().lower()
    if action and action not in ACTIONS:
        raise ValueError(f"Unknown goal action: {action}")

    amount = abs(
        _number(source.get("amount"), 1.0, -MAX_GOAL_VALUE, MAX_GOAL_VALUE)
    )
    if action == "add":
        state["current"] = min(MAX_GOAL_VALUE, state["current"] + amount)
    elif action == "subtract":
        state["current"] = max(0.0, state["current"] - amount)
    elif action == "reset":
        state["current"] = 0.0
    elif action == "complete":
        state["current"] = state["target"]

    for key in DEFAULT_GOAL_STATE:
        if key in source:
            state[key] = source[key]
    return normalize_goal_state(state)


def normalize_goal_document(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    if isinstance(source.get("legacy"), dict):
        legacy = normalize_goal_state(source["legacy"])
        supplied_instances = (
            source.get("instances")
            if isinstance(source.get("instances"), dict)
            else {}
        )
    else:
        legacy = normalize_goal_state(source)
        supplied_instances = {}
    instances: dict[str, dict[str, Any]] = {}
    for instance_id, state in list(supplied_instances.items())[:64]:
        candidate = str(instance_id or "")
        if INSTANCE_ID.fullmatch(candidate):
            instances[candidate] = normalize_goal_state(state)
    return {"legacy": legacy, "instances": instances}


def load_goal_document(path: Path) -> dict[str, Any]:
    if not path.exists():
        return normalize_goal_document({})
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return normalize_goal_document({})
    return normalize_goal_document(raw)


def load_goal_state(
    path: Path,
    instance_id: str | None = None,
) -> dict[str, Any]:
    document = load_goal_document(path)
    if not instance_id:
        return dict(document["legacy"])
    return dict(
        document["instances"].get(instance_id, DEFAULT_GOAL_STATE)
    )


def load_goal_states(
    path: Path,
    instance_ids: Iterable[str],
) -> dict[str, dict[str, Any]]:
    return {
        instance_id: load_goal_state(path, instance_id)
        for instance_id in instance_ids
        if INSTANCE_ID.fullmatch(str(instance_id or ""))
    }


def _write_goal_document(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any]
    if document["instances"]:
        payload = document
    else:
        payload = document["legacy"]
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(payload, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def save_goal_state(
    path: Path,
    raw: Any,
    instance_id: str | None = None,
) -> dict[str, Any]:
    state = normalize_goal_state(raw)
    document = load_goal_document(path)
    if not instance_id:
        document["legacy"] = state
    elif INSTANCE_ID.fullmatch(str(instance_id)):
        document["instances"][str(instance_id)] = state
    else:
        raise ValueError("Invalid goal instance")
    _write_goal_document(path, document)
    return state


def remove_goal_instance(path: Path, instance_id: str) -> None:
    document = load_goal_document(path)
    if document["instances"].pop(str(instance_id), None) is not None:
        _write_goal_document(path, document)
