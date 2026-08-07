from __future__ import annotations

import copy
import json
import math
import re
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any, Iterable


DEFAULT_RIVALS_STATE: dict[str, Any] = {
    # "ready" stays False until a poll actually returns rank data, so the
    # overlay can distinguish "no data yet" from a genuine Bronze III.
    "ready": False,
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
MAX_SEEN_MATCHES = 256
MAX_STATE_FILE_BYTES = 4 * 1024 * 1024
MAX_PLAYER_UID = 9_999_999_999_999_999_999
MAX_SCORE = 1_000_000_000.0
MAX_SESSION_RESULTS = 999
MAX_RATE_LIMIT_FAILURES = 5
MAX_REQUEST_BUDGET_ENTRIES = 120
MAX_REQUEST_BUDGET_FILE_BYTES = 32 * 1024
MAX_EPOCH_SECONDS = 4_102_444_800
REQUEST_BUDGET_WINDOW_SECONDS = 60 * 60
POLL_STATUSES = {"unlinked", "waiting", "queued", "ok", "error"}
COMPETITIVE_GAME_MODE_ID = 2
COMPETITIVE_PLAY_MODE_ID = 200
RANK_SCORE_BASE = 3000.0
RANK_SCORE_STEP = 100.0
RANK_SCORE_CAP_LEVEL = 22
RANK_SCORE_TOP_TIER_BONUS = 30.0
_DOCUMENT_CACHE: dict[
    str,
    tuple[int, int, dict[str, Any]],
] = {}
_DOCUMENT_CACHE_LOCK = threading.Lock()
_REQUEST_BUDGET_LOCK = threading.Lock()


class RivalsStateFileError(RuntimeError):
    """Raised when Rivals state cannot be read or safely replaced."""


class RivalsStateFileTooLargeError(RivalsStateFileError):
    pass


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
        "ready": _boolean(source.get("ready"), defaults["ready"]),
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
        "lastPollError": (
            poll_error[:180]
            if poll_status in {"error", "waiting", "queued"}
            else ""
        ),
    }


def _normalize_record(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    state_source = source.get("state") if isinstance(source.get("state"), dict) else source
    private = _normalize_private(source.get("private"))
    state = normalize_rivals_state(state_source)
    # Records written before "ready" existed need a conservative migration.
    # lastPollAt alone is not evidence: queued and failed attempts update it too.
    # Preserve a completed legacy poll, or unmistakably non-default rank data
    # retained after a later error, without turning a 403-only record into a
    # plausible-looking Bronze III card.
    legacy_rank_changed = any(
        state[key] != DEFAULT_RIVALS_STATE[key]
        for key in ("tier", "division", "score")
    )
    legacy_rank_evidence = (
        private["lastPollAt"] > 0
        and (private["pollStatus"] == "ok" or legacy_rank_changed)
    )
    if "ready" not in state_source and legacy_rank_evidence:
        state["ready"] = True
    return {
        "state": state,
        "private": private,
    }


def _normalize_rate_limit(raw: Any) -> dict[str, int]:
    source = raw if isinstance(raw, dict) else {}
    return {
        "until": _integer(source.get("until"), 0, 0, MAX_EPOCH_SECONDS),
        "failures": _integer(
            source.get("failures"),
            0,
            0,
            MAX_RATE_LIMIT_FAILURES,
        ),
    }


def _normalize_request_budget(raw: Any) -> dict[str, list[int]]:
    source = raw if isinstance(raw, dict) else {}
    supplied = source.get("requests")
    requests: list[int] = []
    if isinstance(supplied, list):
        for value in supplied[-MAX_REQUEST_BUDGET_ENTRIES:]:
            timestamp = _integer(value, 0, 0, MAX_EPOCH_SECONDS)
            if timestamp > 0:
                requests.append(timestamp)
    return {"requests": sorted(requests)}


def normalize_rivals_document(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, dict) else {}
    supplied = source.get("instances") if isinstance(source.get("instances"), dict) else {}
    instances: dict[str, dict[str, Any]] = {}
    for instance_id, record in list(supplied.items())[:MAX_INSTANCES]:
        candidate = str(instance_id or "")
        if INSTANCE_ID.fullmatch(candidate):
            instances[candidate] = _normalize_record(record)
    return {
        "rateLimit": _normalize_rate_limit(source.get("rateLimit")),
        "instances": instances,
    }


def _state_file_size(path: Path) -> int:
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return 0
    if size > MAX_STATE_FILE_BYTES:
        raise RivalsStateFileTooLargeError(
            f"Rivals state file is {size:,} bytes; the safety limit is "
            f"{MAX_STATE_FILE_BYTES:,} bytes. Refusing to load or overwrite "
            f"{path.name}. Back up the file before repairing it."
        )
    return size


def load_rivals_document(path: Path) -> dict[str, Any]:
    cache_key = str(path.absolute())
    if not path.exists():
        with _DOCUMENT_CACHE_LOCK:
            _DOCUMENT_CACHE.pop(cache_key, None)
        return normalize_rivals_document({})
    try:
        stat = path.stat()
        _state_file_size(path)
        with _DOCUMENT_CACHE_LOCK:
            cached = _DOCUMENT_CACHE.get(cache_key)
            if (
                cached is not None
                and cached[0] == stat.st_mtime_ns
                and cached[1] == stat.st_size
            ):
                return copy.deepcopy(cached[2])
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return normalize_rivals_document({})
    normalized = normalize_rivals_document(raw)
    with _DOCUMENT_CACHE_LOCK:
        _DOCUMENT_CACHE[cache_key] = (
            stat.st_mtime_ns,
            stat.st_size,
            copy.deepcopy(normalized),
        )
    return normalized


def load_rate_limit_state(path: Path) -> dict[str, int]:
    return dict(load_rivals_document(path)["rateLimit"])


def request_budget_path(path: Path) -> Path:
    return path.with_name(f"{path.stem}-request-budget.json")


def _read_legacy_request_budget(path: Path) -> list[int]:
    if not path.exists():
        return []
    _state_file_size(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return []
    source = raw if isinstance(raw, dict) else {}
    return _normalize_request_budget(source.get("requestBudget"))["requests"]


def _read_request_budget(path: Path) -> list[int]:
    sidecar = request_budget_path(path)
    if sidecar.exists():
        try:
            if sidecar.stat().st_size > MAX_REQUEST_BUDGET_FILE_BYTES:
                return []
            raw = json.loads(sidecar.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError):
            return []
        return _normalize_request_budget(raw)["requests"]
    # Carry forward the old in-document ledger on the first upgraded run.
    return _read_legacy_request_budget(path)


def _write_request_budget(path: Path, requests: Iterable[int]) -> None:
    sidecar = request_budget_path(path)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = sidecar.with_suffix(f"{sidecar.suffix}.tmp")
    normalized = _normalize_request_budget({"requests": list(requests)})
    temporary_path.write_text(
        json.dumps(normalized, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(sidecar)


def _migrate_legacy_request_budget(path: Path) -> None:
    sidecar = request_budget_path(path)
    if sidecar.exists():
        return
    with _REQUEST_BUDGET_LOCK:
        if sidecar.exists():
            return
        requests = _read_legacy_request_budget(path)
        if requests:
            _write_request_budget(path, requests)


def load_request_budget_state(
    path: Path,
    *,
    now: int | None = None,
) -> list[int]:
    timestamp = int(time.time()) if now is None else max(0, int(now))
    cutoff = timestamp - REQUEST_BUDGET_WINDOW_SECONDS
    with _REQUEST_BUDGET_LOCK:
        requests = _read_request_budget(path)
    return [
        request_at
        for request_at in requests
        if cutoff < request_at <= timestamp + REQUEST_BUDGET_WINDOW_SECONDS
    ]


def load_rivals_record(path: Path, instance_id: str) -> dict[str, Any]:
    if not INSTANCE_ID.fullmatch(str(instance_id or "")):
        raise ValueError("Invalid Rivals Rank instance")
    document = load_rivals_document(path)
    return _normalize_record(document["instances"].get(instance_id, {}))


def load_rivals_state(path: Path, instance_id: str) -> dict[str, Any]:
    return dict(load_rivals_record(path, instance_id)["state"])


def _public_poll_status(
    private: dict[str, Any],
    rate_limit: dict[str, int] | None = None,
    *,
    now: int | None = None,
) -> dict[str, Any]:
    timestamp = int(time.time()) if now is None else max(0, int(now))
    paused_until = _normalize_rate_limit(rate_limit).get("until", 0)
    paused = private["uid"] is not None and paused_until > timestamp
    status = "error" if paused else private["pollStatus"]
    detail = private["lastPollError"]
    if paused and (private["pollStatus"] != "error" or not detail):
        detail = "Rivals Data updates are temporarily paused"
    elif status == "waiting" and not detail:
        detail = "Waiting for the first Rivals Data update"
    elif status == "queued" and not detail:
        detail = "Local request budget is pacing updates"
    return {
        "status": status,
        "lastAttemptAt": private["lastPollAt"],
        "detail": detail,
        "retryAt": paused_until if paused else 0,
    }


def load_rivals_studio_state(
    path: Path,
    instance_ids: Iterable[str],
) -> dict[str, dict[str, Any]]:
    document = load_rivals_document(path)
    rate_limit = document["rateLimit"]
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
        polls[candidate] = _public_poll_status(record["private"], rate_limit)
    return {"states": states, "linked": linked, "polls": polls}


def rivals_status(path: Path, instance_id: str) -> dict[str, Any]:
    document = load_rivals_document(path)
    if not INSTANCE_ID.fullmatch(str(instance_id or "")):
        raise ValueError("Invalid Rivals Rank instance")
    record = _normalize_record(document["instances"].get(instance_id, {}))
    return {
        "state": dict(record["state"]),
        "linked": record["private"]["uid"] is not None,
        "poll": _public_poll_status(record["private"], document["rateLimit"]),
    }


def linked_rivals_instances(path: Path) -> list[tuple[str, int]]:
    result: list[tuple[str, int]] = []
    for instance_id, record in load_rivals_document(path)["instances"].items():
        uid = record["private"]["uid"]
        if isinstance(uid, int):
            result.append((instance_id, uid))
    return result


def linked_rivals_uid(path: Path, instance_id: str) -> int | None:
    private = load_rivals_record(path, instance_id)["private"]
    uid = private["uid"]
    return uid if isinstance(uid, int) else None


def _write_rivals_document(path: Path, document: dict[str, Any]) -> None:
    _state_file_size(path)
    # Lock ordering invariant: callers must not hold _REQUEST_BUDGET_LOCK.
    # Legacy-ledger migration acquires that non-reentrant lock before writing.
    _migrate_legacy_request_budget(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    normalized = normalize_rivals_document(document)
    serialized = json.dumps(normalized, indent=2) + "\n"
    serialized_size = len(serialized.encode("utf-8"))
    if serialized_size > MAX_STATE_FILE_BYTES:
        raise RivalsStateFileTooLargeError(
            f"Saving Rivals state would create a {serialized_size:,}-byte "
            f"file; the safety limit is {MAX_STATE_FILE_BYTES:,} bytes. "
            "The existing state was not replaced."
        )
    temporary_path.write_text(serialized, encoding="utf-8")
    temporary_path.replace(path)
    stat = path.stat()
    with _DOCUMENT_CACHE_LOCK:
        _DOCUMENT_CACHE[str(path.absolute())] = (
            stat.st_mtime_ns,
            stat.st_size,
            copy.deepcopy(normalized),
        )


def save_rate_limit_state(
    path: Path,
    until: Any,
    failures: Any,
) -> dict[str, int]:
    document = load_rivals_document(path)
    normalized = _normalize_rate_limit(
        {"until": until, "failures": failures}
    )
    if normalized != document["rateLimit"]:
        document["rateLimit"] = normalized
        _write_rivals_document(path, document)
    return dict(normalized)


def reserve_rivals_request(
    path: Path,
    maximum: int,
    *,
    now: int | None = None,
) -> tuple[bool, int, int]:
    timestamp = int(time.time()) if now is None else max(0, int(now))
    limit = _integer(
        maximum,
        MAX_REQUEST_BUDGET_ENTRIES,
        1,
        MAX_REQUEST_BUDGET_ENTRIES,
    )
    cutoff = timestamp - REQUEST_BUDGET_WINDOW_SECONDS
    with _REQUEST_BUDGET_LOCK:
        stored = _read_request_budget(path)
        requests = [
            request_at
            for request_at in stored
            if cutoff < request_at <= timestamp + REQUEST_BUDGET_WINDOW_SECONDS
        ]
        requests.sort()
        if len(requests) >= limit:
            retry_after = max(
                1,
                requests[0] + REQUEST_BUDGET_WINDOW_SECONDS - timestamp,
            )
            if requests != stored:
                _write_request_budget(path, requests)
            return False, retry_after, len(requests)
        requests.append(timestamp)
        _write_request_budget(path, requests)
        return True, 0, len(requests)


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
    if action not in {"", "refresh", "reset-session", "unlink"}:
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
                    "ready": False,
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
                "ready": False,
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
        "poll": _public_poll_status(
            normalized_private,
            load_rate_limit_state(path),
        ),
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
    mark_success: bool = True,
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
    # Only claim the card is real once a poll actually produced rank data.
    # Without this the overlay renders DEFAULT_RIVALS_STATE (Bronze III, 0 RS)
    # as if it were fetched, which is worse on stream than showing nothing.
    if mark_success and effective_level is not None:
        state["ready"] = True

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
    if mark_success:
        private["pollStatus"] = "ok"
        private["lastPollAt"] = timestamp
        private["lastPollError"] = ""
    return {
        "state": normalize_rivals_state(state),
        "private": _normalize_private(private),
    }


def save_rivals_polls(
    path: Path,
    instance_ids: Iterable[str],
    expected_uid: int,
    *,
    player_name: str = "",
    rank_level: Any = None,
    rank_score: Any = None,
    matches: Iterable[Any] = (),
    mark_success: bool = True,
    now: int | None = None,
) -> dict[str, tuple[dict[str, Any], bool]]:
    document = load_rivals_document(path)
    results: dict[str, tuple[dict[str, Any], bool]] = {}
    changed_document = False
    supplied_matches = list(matches)
    for instance_id in instance_ids:
        candidate = str(instance_id or "")
        if not INSTANCE_ID.fullmatch(candidate):
            continue
        record = _normalize_record(document["instances"].get(candidate, {}))
        if record["private"]["uid"] != expected_uid:
            results[candidate] = (dict(record["state"]), False)
            continue
        updated = apply_rivals_poll(
            record,
            player_name=player_name,
            rank_level=rank_level,
            rank_score=rank_score,
            matches=supplied_matches,
            mark_success=mark_success,
            now=now,
        )
        public_changed = updated["state"] != record["state"]
        results[candidate] = (dict(updated["state"]), public_changed)
        if updated != record:
            document["instances"][candidate] = updated
            changed_document = True
    if changed_document:
        _write_rivals_document(path, document)
    return results


def save_rivals_poll(
    path: Path,
    instance_id: str,
    expected_uid: int,
    *,
    player_name: str = "",
    rank_level: Any = None,
    rank_score: Any = None,
    matches: Iterable[Any] = (),
    mark_success: bool = True,
    now: int | None = None,
) -> tuple[dict[str, Any], bool]:
    results = save_rivals_polls(
        path,
        [instance_id],
        expected_uid,
        player_name=player_name,
        rank_level=rank_level,
        rank_score=rank_score,
        matches=matches,
        mark_success=mark_success,
        now=now,
    )
    if instance_id in results:
        return results[instance_id]
    return load_rivals_state(path, instance_id), False


def save_rivals_poll_waits(
    path: Path,
    linked: Iterable[tuple[str, int]],
    detail: Any,
    *,
    now: int | None = None,
) -> list[str]:
    timestamp = int(time.time()) if now is None else max(0, int(now))
    message = " ".join(str(detail or "Update queued").split())[:180]
    document = load_rivals_document(path)
    changed: list[str] = []
    for instance_id, expected_uid in linked:
        candidate = str(instance_id or "")
        if not INSTANCE_ID.fullmatch(candidate):
            continue
        record = _normalize_record(document["instances"].get(candidate, {}))
        if record["private"]["uid"] != expected_uid:
            continue
        private = dict(record["private"])
        if private["pollStatus"] == "error":
            continue
        private["pollStatus"] = "queued"
        private["lastPollAt"] = timestamp
        private["lastPollError"] = message
        document["instances"][candidate] = _normalize_record(
            {"state": record["state"], "private": private}
        )
        changed.append(candidate)
    if changed:
        _write_rivals_document(path, document)
    return changed


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


def save_rivals_poll_failures(
    path: Path,
    linked: Iterable[tuple[str, int]],
    error: Any,
    *,
    rate_limit_until: Any | None = None,
    rate_limit_failures: Any | None = None,
    now: int | None = None,
) -> list[str]:
    timestamp = int(time.time()) if now is None else max(0, int(now))
    message = " ".join(str(error or "Unknown error").split())[:180]
    document = load_rivals_document(path)
    changed: list[str] = []
    for instance_id, expected_uid in linked:
        candidate = str(instance_id or "")
        if not INSTANCE_ID.fullmatch(candidate):
            continue
        record = _normalize_record(document["instances"].get(candidate, {}))
        if record["private"]["uid"] != expected_uid:
            continue
        private = dict(record["private"])
        private["pollStatus"] = "error"
        private["lastPollAt"] = timestamp
        private["lastPollError"] = message
        updated = {"state": record["state"], "private": private}
        document["instances"][candidate] = _normalize_record(updated)
        changed.append(candidate)
    if rate_limit_until is not None or rate_limit_failures is not None:
        document["rateLimit"] = _normalize_rate_limit(
            {
                "until": (
                    document["rateLimit"]["until"]
                    if rate_limit_until is None
                    else rate_limit_until
                ),
                "failures": (
                    document["rateLimit"]["failures"]
                    if rate_limit_failures is None
                    else rate_limit_failures
                ),
            }
        )
    if changed or rate_limit_until is not None or rate_limit_failures is not None:
        _write_rivals_document(path, document)
    return changed


def remove_rivals_instance(path: Path, instance_id: str) -> None:
    document = load_rivals_document(path)
    if document["instances"].pop(str(instance_id), None) is not None:
        _write_rivals_document(path, document)
