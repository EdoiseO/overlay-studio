from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable


DEFAULT_COUNTER_STATE: dict[str, Any] = {
    "title": "MARVEL RIVALS",
    "wins": 0,
    "losses": 0,
    "accent": "d7ff45",
}

HEX_COLOR = re.compile(r"^[0-9a-fA-F]{6}$")
INSTANCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
ACTIONS = {"win", "loss", "undo-win", "undo-loss", "reset"}
LEGACY_COUNTER_INSTANCE_ID = "match-record"


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


def normalize_counter_document(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    if isinstance(source.get("legacy"), dict):
        legacy = normalize_counter_state(source["legacy"])
        supplied_instances = (
            source.get("instances")
            if isinstance(source.get("instances"), dict)
            else {}
        )
    else:
        legacy = normalize_counter_state(source)
        supplied_instances = {}
    instances: dict[str, dict[str, Any]] = {}
    for instance_id, state in list(supplied_instances.items())[:64]:
        candidate = str(instance_id or "")
        if INSTANCE_ID.fullmatch(candidate):
            instances[candidate] = normalize_counter_state(state)
    return {"legacy": legacy, "instances": instances}


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


def load_counter_document(path: Path) -> dict[str, Any]:
    if not path.exists():
        return normalize_counter_document({})
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return normalize_counter_document({})
    return normalize_counter_document(raw)


def load_counter_state(
    path: Path,
    instance_id: str | None = None,
) -> dict[str, Any]:
    document = load_counter_document(path)
    if not instance_id or instance_id == LEGACY_COUNTER_INSTANCE_ID:
        return dict(document["legacy"])
    return dict(
        document["instances"].get(instance_id, DEFAULT_COUNTER_STATE)
    )


def load_counter_states(
    path: Path,
    instance_ids: Iterable[str],
) -> dict[str, dict[str, Any]]:
    return {
        instance_id: load_counter_state(path, instance_id)
        for instance_id in instance_ids
        if INSTANCE_ID.fullmatch(str(instance_id or ""))
    }


def _write_counter_document(path: Path, document: dict[str, Any]) -> None:
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


def save_counter_state(
    path: Path,
    raw: Any,
    instance_id: str | None = None,
) -> dict[str, Any]:
    state = normalize_counter_state(raw)
    document = load_counter_document(path)
    if not instance_id or instance_id == LEGACY_COUNTER_INSTANCE_ID:
        document["legacy"] = state
    elif INSTANCE_ID.fullmatch(str(instance_id)):
        document["instances"][str(instance_id)] = state
    else:
        raise ValueError("Invalid counter instance")
    _write_counter_document(path, document)
    return state


def remove_counter_instance(path: Path, instance_id: str) -> None:
    if instance_id == LEGACY_COUNTER_INSTANCE_ID:
        return
    document = load_counter_document(path)
    if document["instances"].pop(str(instance_id), None) is not None:
        _write_counter_document(path, document)
