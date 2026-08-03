from __future__ import annotations

import json
import math
import re
import time
import urllib.parse
from pathlib import Path
from typing import Any, Iterable


DEFAULT_RIVALS_STATE: dict[str, Any] = {
    "playerName": "Player",
    "tier": "bronze",
    "division": 3,
    "score": 0.0,
    "sessionWins": 0,
    "sessionLosses": 0,
    "label": "This session",
    "showName": True,
    "shellColor": "141418",
    "textColor": "ffffff",
    "accentColor": "f6f7fb",
    "winColor": "5fd97a",
    "lossColor": "ff5f6d",
    "font": "display",
    "weight": 800,
    "scale": 1.0,
    "corners": 18,
    "glow": 1.0,
}

PUBLIC_KEYS = tuple(DEFAULT_RIVALS_STATE)
VISUAL_KEYS = {
    "label",
    "showName",
    "shellColor",
    "textColor",
    "accentColor",
    "winColor",
    "lossColor",
    "font",
    "weight",
    "scale",
    "corners",
    "glow",
}
TIER_ORDER = (
    "bronze",
    "silver",
    "gold",
    "platinum",
    "diamond",
    "grandmaster",
    "celestial",
    "eternity",
    "one-above-all",
)
FONT_CHOICES = {
    "montserrat",
    "poppins",
    "archivo",
    "nunito",
    "anton",
    "sans",
    "display",
}
HEX_COLOR = re.compile(r"^[0-9a-fA-F]{6}$")
INSTANCE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
MATCH_UID = re.compile(r"^[A-Za-z0-9_.:-]{1,160}$")
MAX_INSTANCES = 64
MAX_SEEN_MATCHES = 64
MAX_STATE_FILE_BYTES = 1024 * 1024
MAX_PLAYER_UID = 9_999_999_999_999_999_999
MAX_SCORE = 1_000_000_000.0
MAX_SESSION_RESULTS = 999
POLL_STATUSES = {"unlinked", "waiting", "ok", "error"}
COMPETITIVE_GAME_MODE_ID = 2
COMPETITIVE_PLAY_MODE_ID = 200
RANK_SCORE_BASE = 3000.0
RANK_SCORE_STEP = 100.0
RANK_SCORE_CAP_LEVEL = 22
RANK_SCORE_TOP_TIER_BONUS = 30.0


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


def _integer(value: Any, default: int, minimum: int, maximum: int) -> int:
    return int(round(_number(value, default, minimum, maximum)))


def _text(value: Any, default: str, maximum: int) -> str:
    candidate = " ".join(str(value or "").strip().split())
    return candidate[:maximum] or default


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


def rank_from_level(value: Any) -> tuple[str, int]:
    """Map Rivals Data's ascending 1..23 rank level to display rank."""
    level = _integer(value, 1, 1, 23)
    if level <= 21:
        tier_index = (level - 1) // 3
        division = 3 - ((level - 1) % 3)
        return TIER_ORDER[tier_index], division
    if level == 22:
        return "eternity", 0
    return "one-above-all", 0


def is_competitive_match(raw: Any) -> bool:
    """Accept ranked matches while preserving compatibility with older payloads."""
    if not isinstance(raw, dict):
        return False

    supplied_modes: list[int] = []
    for value in (
        raw.get("game_mode_id", raw.get("gameModeId")),
        raw.get("game_play_mode_id", raw.get("gamePlayModeId")),
    ):
        if value is None:
            continue
        try:
            supplied_modes.append(int(value))
        except (TypeError, ValueError):
            supplied_modes.append(-1)

    if not supplied_modes:
        return True
    return (
        COMPETITIVE_GAME_MODE_ID in supplied_modes
        or COMPETITIVE_PLAY_MODE_ID in supplied_modes
    )


def rank_progress_score(value: Any, rank_level: Any) -> float:
    """Convert Rivals Data's season-scale score into the displayed RS value."""
    score = _number(value, 0, 0, MAX_SCORE)
    if score < RANK_SCORE_BASE or rank_level is None:
        return round(score, 2)

    level = _integer(rank_level, 1, 1, 23)
    threshold_level = min(level, RANK_SCORE_CAP_LEVEL)
    threshold = RANK_SCORE_BASE + ((threshold_level - 1) * RANK_SCORE_STEP)
    if level >= RANK_SCORE_CAP_LEVEL:
        return float(
            math.floor(max(0.0, score - threshold + RANK_SCORE_TOP_TIER_BONUS))
        )
    return round(max(0.0, score - threshold), 2)


def normalize_rivals_state(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    defaults = DEFAULT_RIVALS_STATE
    tier = str(source.get("tier") or "").strip().lower()
    if tier not in TIER_ORDER:
        tier = defaults["tier"]
    division = (
        0
        if tier in {"eternity", "one-above-all"}
        else _integer(source.get("division"), defaults["division"], 1, 3)
    )
    weight = int(
        round(_number(source.get("weight"), defaults["weight"], 300, 900) / 100)
        * 100
    )
    font = str(source.get("font") or "").strip().lower()
    if font not in FONT_CHOICES:
        font = defaults["font"]
    return {
        "playerName": _text(
            source.get("playerName"), defaults["playerName"], 32
        ),
        "tier": tier,
        "division": division,
        "score": round(
            _number(source.get("score"), defaults["score"], 0, MAX_SCORE),
            2,
        ),
        "sessionWins": _integer(
            source.get("sessionWins"),
            defaults["sessionWins"],
            0,
            MAX_SESSION_RESULTS,
        ),
        "sessionLosses": _integer(
            source.get("sessionLosses"),
            defaults["sessionLosses"],
            0,
            MAX_SESSION_RESULTS,
        ),
        "label": _text(source.get("label"), defaults["label"], 24),
        "showName": _boolean(source.get("showName"), defaults["showName"]),
        "shellColor": _color(
            source.get("shellColor"), defaults["shellColor"]
        ),
        "textColor": _color(source.get("textColor"), defaults["textColor"]),
        "accentColor": _color(
            source.get("accentColor"), defaults["accentColor"]
        ),
        "winColor": _color(source.get("winColor"), defaults["winColor"]),
        "lossColor": _color(
            source.get("lossColor"), defaults["lossColor"]
        ),
        "font": font,
        "weight": weight,
        "scale": round(
            _number(source.get("scale"), defaults["scale"], 0.5, 1.6),
            2,
        ),
        "corners": _integer(
            source.get("corners"), defaults["corners"], 0, 40
        ),
        "glow": round(
            _number(source.get("glow"), defaults["glow"], 0, 2.5),
            2,
        ),
    }


def parse_player_uid(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("Enter a valid Rivals Data player ID or profile URL")
    if isinstance(value, int):
        candidate = str(value)
    else:
        candidate = str(value or "").strip()
    if not candidate or len(candidate) > 256:
        raise ValueError("Enter a valid Rivals Data player ID or profile URL")
    if candidate.isdigit():
        uid = int(candidate)
    else:
        try:
            parsed = urllib.parse.urlsplit(candidate)
        except ValueError:
            parsed = urllib.parse.SplitResult("", "", "", "", "")
        hostname = str(parsed.hostname or "").lower().rstrip(".")
        match = re.fullmatch(r"/player/(\d+)/?", parsed.path)
        if (
            parsed.scheme.lower() not in {"http", "https"}
            or hostname not in {"rivalsdata.com", "www.rivalsdata.com"}
            or parsed.username is not None
            or parsed.password is not None
            or match is None
        ):
            raise ValueError("Enter a valid Rivals Data player ID or profile URL")
        uid = int(match.group(1))
    if uid < 1 or uid > MAX_PLAYER_UID:
        raise ValueError("Enter a valid Rivals Data player ID or profile URL")
    return uid


def _normalize_match_uid(value: Any) -> str:
    candidate = str(value or "").strip()
    return candidate if MATCH_UID.fullmatch(candidate) else ""


def _normalize_private(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    uid: int | None
    try:
        uid = parse_player_uid(source.get("uid")) if source.get("uid") else None
    except ValueError:
        uid = None
    seen: list[str] = []
    supplied_seen = source.get("seenMatchUids")
    if isinstance(supplied_seen, list):
        for value in supplied_seen:
            match_uid = _normalize_match_uid(value)
            if match_uid and match_uid not in seen:
                seen.append(match_uid)
            if len(seen) >= MAX_SEEN_MATCHES:
                break
    last_seen = _normalize_match_uid(source.get("lastSeenMatchUid"))
    if last_seen and last_seen not in seen:
        seen.insert(0, last_seen)
        seen = seen[:MAX_SEEN_MATCHES]
    poll_status = str(source.get("pollStatus") or "").strip().lower()
    if poll_status not in POLL_STATUSES:
        poll_status = "waiting" if uid is not None else "unlinked"
    if uid is None:
        poll_status = "unlinked"
    poll_error = " ".join(str(source.get("lastPollError") or "").split())
    return {
        "uid": uid,
        "lastSeenMatchUid": last_seen,
        "seenMatchUids": seen,
        "sessionStartedAt": _integer(
            source.get("sessionStartedAt"), 0, 0, 4_102_444_800
        ),
        "pollStatus": poll_status,
        "lastPollAt": _integer(
            source.get("lastPollAt"), 0, 0, 4_102_444_800
        ),
        "lastPollError": poll_error[:180] if poll_status == "error" else "",
    }


def _normalize_record(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    state_source = source.get("state") if isinstance(source.get("state"), dict) else source
    return {
        "state": normalize_rivals_state(state_source),
        "private": _normalize_private(source.get("private")),
    }


def normalize_rivals_document(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    supplied = source.get("instances") if isinstance(source.get("instances"), dict) else {}
    instances: dict[str, dict[str, Any]] = {}
    for instance_id, record in list(supplied.items())[:MAX_INSTANCES]:
        candidate = str(instance_id or "")
        if INSTANCE_ID.fullmatch(candidate):
            instances[candidate] = _normalize_record(record)
    return {"instances": instances}


def load_rivals_document(path: Path) -> dict[str, Any]:
    if not path.exists():
        return normalize_rivals_document({})
    try:
        if path.stat().st_size > MAX_STATE_FILE_BYTES:
            return normalize_rivals_document({})
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return normalize_rivals_document({})
    return normalize_rivals_document(raw)


def load_rivals_record(path: Path, instance_id: str) -> dict[str, Any]:
    if not INSTANCE_ID.fullmatch(str(instance_id or "")):
        raise ValueError("Invalid Rivals Rank instance")
    document = load_rivals_document(path)
    return _normalize_record(document["instances"].get(instance_id, {}))


def load_rivals_state(path: Path, instance_id: str) -> dict[str, Any]:
    return dict(load_rivals_record(path, instance_id)["state"])


def _public_poll_status(private: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": private["pollStatus"],
        "lastAttemptAt": private["lastPollAt"],
        "detail": private["lastPollError"],
    }


def load_rivals_studio_state(
    path: Path,
    instance_ids: Iterable[str],
) -> dict[str, dict[str, Any]]:
    document = load_rivals_document(path)
    states: dict[str, dict[str, Any]] = {}
    linked: dict[str, bool] = {}
    polls: dict[str, dict[str, Any]] = {}
    for instance_id in instance_ids:
        candidate = str(instance_id or "")
        if not INSTANCE_ID.fullmatch(candidate):
            continue
        record = _normalize_record(document["instances"].get(candidate, {}))
        states[candidate] = dict(record["state"])
        linked[candidate] = record["private"]["uid"] is not None
        polls[candidate] = _public_poll_status(record["private"])
    return {"states": states, "linked": linked, "polls": polls}


def rivals_status(path: Path, instance_id: str) -> dict[str, Any]:
    record = load_rivals_record(path, instance_id)
    return {
        "state": dict(record["state"]),
        "linked": record["private"]["uid"] is not None,
        "poll": _public_poll_status(record["private"]),
    }


def linked_rivals_instances(path: Path) -> list[tuple[str, int]]:
    result: list[tuple[str, int]] = []
    for instance_id, record in load_rivals_document(path)["instances"].items():
        uid = record["private"]["uid"]
        if isinstance(uid, int):
            result.append((instance_id, uid))
    return result


def _write_rivals_document(path: Path, document: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    temporary_path.write_text(
        json.dumps(normalize_rivals_document(document), indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(path)


def _save_record(path: Path, instance_id: str, record: dict[str, Any]) -> None:
    document = load_rivals_document(path)
    document["instances"][instance_id] = _normalize_record(record)
    _write_rivals_document(path, document)


def update_rivals_record(
    path: Path,
    instance_id: str,
    raw: Any,
    *,
    now: int | None = None,
) -> dict[str, Any]:
    if not INSTANCE_ID.fullmatch(str(instance_id or "")):
        raise ValueError("Invalid Rivals Rank instance")
    source = raw if isinstance(raw, dict) else {}
    action = str(source.get("action") or "").strip().lower()
    if action not in {"", "reset-session", "unlink"}:
        raise ValueError(f"Unknown Rivals action: {action}")
    timestamp = int(time.time()) if now is None else max(0, int(now))
    record = load_rivals_record(path, instance_id)
    state = dict(record["state"])
    private = dict(record["private"])

    visual_patch = {key: source[key] for key in VISUAL_KEYS if key in source}
    state = normalize_rivals_state({**state, **visual_patch})

    if "uid" in source and str(source.get("uid") or "").strip():
        uid = parse_player_uid(source["uid"])
        if uid != private.get("uid"):
            private = {
                "uid": uid,
                "lastSeenMatchUid": "",
                "seenMatchUids": [],
                "sessionStartedAt": timestamp,
                "pollStatus": "waiting",
                "lastPollAt": 0,
                "lastPollError": "",
            }
            state = normalize_rivals_state(
                {
                    **state,
                    "playerName": DEFAULT_RIVALS_STATE["playerName"],
                    "tier": DEFAULT_RIVALS_STATE["tier"],
                    "division": DEFAULT_RIVALS_STATE["division"],
                    "score": DEFAULT_RIVALS_STATE["score"],
                    "sessionWins": 0,
                    "sessionLosses": 0,
                }
            )

    if action == "reset-session":
        state["sessionWins"] = 0
        state["sessionLosses"] = 0
        private["sessionStartedAt"] = timestamp
    elif action == "unlink":
        private = _normalize_private({})
        state = normalize_rivals_state(
            {
                **state,
                "playerName": DEFAULT_RIVALS_STATE["playerName"],
                "tier": DEFAULT_RIVALS_STATE["tier"],
                "division": DEFAULT_RIVALS_STATE["division"],
                "score": DEFAULT_RIVALS_STATE["score"],
                "sessionWins": 0,
                "sessionLosses": 0,
            }
        )

    _save_record(path, instance_id, {"state": state, "private": private})
    normalized_private = _normalize_private(private)
    return {
        "state": state,
        "linked": normalized_private["uid"] is not None,
        "poll": _public_poll_status(normalized_private),
    }


def _match_values(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict) or not is_competitive_match(raw):
        return None
    match_uid = _normalize_match_uid(raw.get("match_uid", raw.get("matchUid")))
    if not match_uid:
        return None
    return {
        "uid": match_uid,
        "isWin": _boolean(raw.get("is_win", raw.get("isWin")), False),
        "timestamp": _integer(raw.get("timestamp"), 0, 0, 4_102_444_800),
        "rankLevel": _integer(
            raw.get("rank_level", raw.get("rankLevel")), 0, 0, 23
        ),
        "rankScore": round(
            _number(
                raw.get("rank_score", raw.get("rankScore")),
                0,
                0,
                MAX_SCORE,
            ),
            2,
        ),
    }


def apply_rivals_poll(
    record: dict[str, Any],
    *,
    player_name: str = "",
    rank_level: Any = None,
    rank_score: Any = None,
    matches: Iterable[Any] = (),
    now: int | None = None,
) -> dict[str, Any]:
    normalized = _normalize_record(record)
    state = dict(normalized["state"])
    private = dict(normalized["private"])
    timestamp = int(time.time()) if now is None else max(0, int(now))
    if private["sessionStartedAt"] <= 0:
        private["sessionStartedAt"] = timestamp

    parsed_matches = [
        parsed
        for parsed in (_match_values(match) for match in matches)
        if parsed is not None
    ]
    newest = parsed_matches[0] if parsed_matches else None
    effective_level = rank_level
    if effective_level is None and newest and newest["rankLevel"]:
        effective_level = newest["rankLevel"]
    effective_score = rank_score
    if effective_score is None and newest:
        effective_score = newest["rankScore"]
    if effective_level is not None:
        state["tier"], state["division"] = rank_from_level(effective_level)
    if effective_score is not None:
        state["score"] = rank_progress_score(effective_score, effective_level)
    if str(player_name or "").strip():
        state["playerName"] = _text(
            player_name, state["playerName"], 32
        )

    prior_seen = set(private["seenMatchUids"])
    baseline = not prior_seen and not private["lastSeenMatchUid"]
    new_matches = [
        match
        for match in parsed_matches
        if match["uid"] not in prior_seen
        and (
            (
                baseline
                and match["timestamp"] > 0
                and match["timestamp"] >= private["sessionStartedAt"]
            )
            or (
                not baseline
                and (
                    match["timestamp"] <= 0
                    or match["timestamp"] >= private["sessionStartedAt"]
                )
            )
        )
    ]
    state["sessionWins"] = min(
        MAX_SESSION_RESULTS,
        state["sessionWins"] + sum(1 for match in new_matches if match["isWin"]),
    )
    state["sessionLosses"] = min(
        MAX_SESSION_RESULTS,
        state["sessionLosses"]
        + sum(1 for match in new_matches if not match["isWin"]),
    )

    current_ids = [match["uid"] for match in parsed_matches]
    combined = list(dict.fromkeys([*current_ids, *private["seenMatchUids"]]))
    private["seenMatchUids"] = combined[:MAX_SEEN_MATCHES]
    if current_ids:
        private["lastSeenMatchUid"] = current_ids[0]
    private["pollStatus"] = "ok"
    private["lastPollAt"] = timestamp
    private["lastPollError"] = ""
    return {
        "state": normalize_rivals_state(state),
        "private": _normalize_private(private),
    }


def save_rivals_poll(
    path: Path,
    instance_id: str,
    expected_uid: int,
    *,
    player_name: str = "",
    rank_level: Any = None,
    rank_score: Any = None,
    matches: Iterable[Any] = (),
    now: int | None = None,
) -> tuple[dict[str, Any], bool]:
    record = load_rivals_record(path, instance_id)
    if record["private"]["uid"] != expected_uid:
        return dict(record["state"]), False
    updated = apply_rivals_poll(
        record,
        player_name=player_name,
        rank_level=rank_level,
        rank_score=rank_score,
        matches=matches,
        now=now,
    )
    public_changed = updated["state"] != record["state"]
    if updated != record:
        _save_record(path, instance_id, updated)
    return dict(updated["state"]), public_changed


def save_rivals_poll_failure(
    path: Path,
    instance_id: str,
    expected_uid: int,
    error: Any,
    *,
    now: int | None = None,
) -> bool:
    record = load_rivals_record(path, instance_id)
    if record["private"]["uid"] != expected_uid:
        return False
    timestamp = int(time.time()) if now is None else max(0, int(now))
    private = dict(record["private"])
    private["pollStatus"] = "error"
    private["lastPollAt"] = timestamp
    private["lastPollError"] = " ".join(str(error or "Unknown error").split())[:180]
    _save_record(
        path,
        instance_id,
        {"state": record["state"], "private": private},
    )
    return True


def remove_rivals_instance(path: Path, instance_id: str) -> None:
    document = load_rivals_document(path)
    if document["instances"].pop(str(instance_id), None) is not None:
        _write_rivals_document(path, document)
