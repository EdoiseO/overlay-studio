from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


DEFAULT_COUNTER_STATE: dict[str, Any] = {
    "title": "MARVEL RIVALS",
    "wins": 0,
    "losses": 0,
    "accent": "d7ff45",
}

HEX_COLOR = re.compile(r"^[0-9a-fA-F]{6}$")
ACTIONS = {"win", "loss", "undo-win", "undo-loss", "reset"}


def _count(value: Any, default: int) -> int:
    try:
        candidate = int(value)
    except (TypeError, ValueError):
        candidate = default
    return max(0, min(999, candidate))


def _title(value: Any) -> str:
    candidate = " ".join(str(value or "").strip().split())
    return candidate[:48] or DEFAULT_COUNTER_STATE["title"]


def _color(value: Any) -> str:
    candidate = str(value or "").strip().removeprefix("#")
    if HEX_COLOR.fullmatch(candidate):
        return candidate.lower()
    return DEFAULT_COUNTER_STATE["accent"]


def normalize_counter_state(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    return {
        "title": _title(source.get("title")),
        "wins": _count(source.get("wins"), DEFAULT_COUNTER_STATE["wins"]),
        "losses": _count(source.get("losses"), DEFAULT_COUNTER_STATE["losses"]),
        "accent": _color(source.get("accent")),
    }


def apply_counter_update(current: dict[str, Any], raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    state = normalize_counter_state(current)
    action = str(source.get("action") or "").strip().lower()
    if action and action not in ACTIONS:
        raise ValueError(f"Unknown counter action: {action}")

    if action == "win":
        state["wins"] = min(999, state["wins"] + 1)
    elif action == "loss":
        state["losses"] = min(999, state["losses"] + 1)
    elif action == "undo-win":
        state["wins"] = max(0, state["wins"] - 1)
    elif action == "undo-loss":
        state["losses"] = max(0, state["losses"] - 1)
    elif action == "reset":
        state["wins"] = 0
        state["losses"] = 0

    for key in ("title", "wins", "losses", "accent"):
        if key in source:
            state[key] = source[key]
    return normalize_counter_state(state)


def load_counter_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return dict(DEFAULT_COUNTER_STATE)
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_COUNTER_STATE)
    return normalize_counter_state(raw)


def save_counter_state(path: Path, raw: Any) -> dict[str, Any]:
    state = normalize_counter_state(raw)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(path)
    return state
