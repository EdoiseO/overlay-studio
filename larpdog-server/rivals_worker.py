from __future__ import annotations

import asyncio
import datetime as dt
import json
import math
import random
import time
from collections import defaultdict, deque
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from aiohttp import ClientSession, ClientTimeout

from rivals_store import (
    RivalsStateFileError,
    is_competitive_match,
    linked_rivals_instances,
    load_rate_limit_state,
    reserve_rivals_request,
    save_rate_limit_state,
    save_rivals_poll_failures,
    save_rivals_polls,
    save_rivals_poll_waits,
)


SITE_ORIGIN = "https://rivalsdata.com"
PROFILE_ENDPOINT = "https://api.rivalsdata.com/player"
MATCHES_ENDPOINT = "https://api.rivalsdata.com/player/matches/cached"
MATCHES_REFRESH_ENDPOINT = "https://api.rivalsdata.com/player/matches"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_MATCHES = 64
DEFAULT_POLL_SECONDS = 120.0
MIN_POLL_SECONDS = 60.0
MAX_POLL_SECONDS = 900.0
DEFAULT_PROFILE_REFRESH_SECONDS = 300.0
MIN_PROFILE_REFRESH_SECONDS = 120.0
MAX_PROFILE_REFRESH_SECONDS = 900.0
DEFAULT_LIVE_REFRESH_SECONDS = 120.0
MIN_LIVE_REFRESH_SECONDS = 60.0
MAX_LIVE_REFRESH_SECONDS = 900.0
DEFAULT_RATE_LIMIT_BACKOFF_SECONDS = 300.0
DEFAULT_TRANSIENT_BACKOFF_SECONDS = 120.0
MIN_RATE_LIMIT_BACKOFF_SECONDS = 60.0
MAX_RATE_LIMIT_BACKOFF_SECONDS = 3600.0
DEFAULT_MAX_REQUESTS_PER_HOUR = 120
MIN_MAX_REQUESTS_PER_HOUR = 12
MAX_MAX_REQUESTS_PER_HOUR = 120
MANUAL_REFRESH_SECONDS = 60.0
STARTUP_DELAY_MIN_SECONDS = 5.0
STARTUP_DELAY_MAX_SECONDS = 15.0
POLL_JITTER_RATIO = 0.1
REFRESH_GATE_TOLERANCE_RATIO = 1.0 - POLL_JITTER_RATIO
INVALID_JSON_BACKOFF_THRESHOLD = 3
REQUEST_BUDGET_HEADROOM_RATIO = 0.9
MATCH_REQUESTS_PER_REFRESH = 2
PROTECTION_DECAY_INTERVAL_SECONDS = 300.0
ERROR_RELOG_INTERVAL_SECONDS = 900.0


class RivalsRateLimitError(RuntimeError):
    def __init__(self, retry_after_seconds: float | None = None) -> None:
        super().__init__("Rivals Data rate limit reached")
        self.retry_after_seconds = retry_after_seconds


class RivalsProviderBackoffError(RuntimeError):
    def __init__(
        self,
        message: str,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class RivalsRequestBudgetError(RuntimeError):
    def __init__(self, retry_after_seconds: float) -> None:
        super().__init__("Local Rivals request budget is pacing updates")
        self.retry_after_seconds = retry_after_seconds


def _bounded_seconds(
    value: Any,
    default: float,
    minimum: float,
    maximum: float,
) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    if not math.isfinite(number):
        number = default
    return max(minimum, min(maximum, number))


def _parse_retry_after(value: Any, now: dt.datetime | None = None) -> float | None:
    candidate = str(value or "").strip()
    if not candidate:
        return None
    try:
        seconds = float(candidate)
    except ValueError:
        seconds = math.nan
    if math.isfinite(seconds) and seconds >= 0:
        return seconds
    try:
        retry_at = parsedate_to_datetime(candidate)
    except (TypeError, ValueError, OverflowError):
        return None
    if retry_at.tzinfo is None:
        retry_at = retry_at.replace(tzinfo=dt.timezone.utc)
    current = now or dt.datetime.now(dt.timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=dt.timezone.utc)
    return max(0.0, (retry_at - current).total_seconds())


def _walk_dicts(value: Any, maximum: int = 512) -> list[dict[str, Any]]:
    queue: deque[tuple[Any, int]] = deque([(value, 0)])
    result: list[dict[str, Any]] = []
    while queue and len(result) < maximum:
        candidate, depth = queue.popleft()
        if depth > 7:
            continue
        if isinstance(candidate, dict):
            result.append(candidate)
            queue.extend((child, depth + 1) for child in candidate.values())
        elif isinstance(candidate, list):
            queue.extend((child, depth + 1) for child in candidate[:MAX_MATCHES])
    return result


def _optional_integer(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return None


def _latest_rank_season(
    payload: Any,
) -> tuple[int | None, dict[str, Any] | None]:
    for candidate in _walk_dicts(payload):
        seasons = candidate.get(
            "rank_game_season",
            candidate.get("rankGameSeason"),
        )
        if not isinstance(seasons, dict):
            continue

        ranked: list[tuple[int, int | None, dict[str, Any]]] = []
        for key, record in list(seasons.items())[:MAX_MATCHES]:
            if not isinstance(record, dict):
                continue
            season = _optional_integer(
                record.get("rank_game_id", record.get("rankGameId"))
            )
            sort_key = season
            if sort_key is None:
                sort_key = _optional_integer(key)
            if sort_key is not None:
                ranked.append((sort_key, season, record))
        if ranked:
            _sort_key, season, record = max(ranked, key=lambda item: item[0])
            return season, record
    return None, None


def extract_profile_snapshot(payload: Any) -> tuple[str, Any, Any]:
    dictionaries = _walk_dicts(payload)
    name = ""
    rank_level: Any = None
    rank_score: Any = None
    _season, latest_rank = _latest_rank_season(payload)
    if latest_rank is not None:
        rank_level = latest_rank.get(
            "rank_level",
            latest_rank.get("rankLevel", latest_rank.get("level")),
        )
        rank_score = latest_rank.get("rank_score", latest_rank.get("rankScore"))
    for candidate in dictionaries:
        if not name:
            for key in ("player_name", "playerName", "nickname", "name"):
                value = candidate.get(key)
                if isinstance(value, str) and value.strip():
                    name = value.strip()
                    break
        if rank_level is None:
            for key in ("rank_level", "rankLevel"):
                if key in candidate:
                    rank_level = candidate[key]
                    break
        if rank_score is None:
            for key in ("rank_score", "rankScore"):
                if key in candidate:
                    rank_score = candidate[key]
                    break
        if name and rank_level is not None and rank_score is not None:
            break
    return name, rank_level, rank_score


def extract_matches(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        candidates = payload
    else:
        candidates: list[Any] = []
        for candidate in _walk_dicts(payload):
            for key in ("matches", "data", "history", "match_history"):
                value = candidate.get(key)
                if isinstance(value, list) and any(
                    isinstance(item, dict)
                    and ("match_uid" in item or "matchUid" in item)
                    for item in value[:3]
                ):
                    candidates = value
                    break
            if candidates:
                break
    return [item for item in candidates[:MAX_MATCHES] if isinstance(item, dict)]


class RivalsPollWorker:
    def __init__(
        self,
        state_path: Path,
        broadcast: Callable[[dict[str, Any]], Awaitable[None]],
        config: dict[str, Any],
        *,
        store_lock: asyncio.Lock,
        logger: Callable[[str], None],
    ) -> None:
        self.state_path = state_path
        self.broadcast = broadcast
        self.config = config
        self.store_lock = store_lock
        self.logger = logger
        self.task: asyncio.Task[None] | None = None
        self._last_errors: dict[str, tuple[str, float]] = {}
        self.profile_refresh_seconds = _bounded_seconds(
            config.get(
                "profile_refresh_seconds",
                DEFAULT_PROFILE_REFRESH_SECONDS,
            ),
            DEFAULT_PROFILE_REFRESH_SECONDS,
            MIN_PROFILE_REFRESH_SECONDS,
            MAX_PROFILE_REFRESH_SECONDS,
        )
        self.live_refresh_seconds = _bounded_seconds(
            config.get("live_refresh_seconds", DEFAULT_LIVE_REFRESH_SECONDS),
            DEFAULT_LIVE_REFRESH_SECONDS,
            MIN_LIVE_REFRESH_SECONDS,
            MAX_LIVE_REFRESH_SECONDS,
        )
        self.rate_limit_backoff_seconds = _bounded_seconds(
            config.get(
                "rate_limit_backoff_seconds",
                DEFAULT_RATE_LIMIT_BACKOFF_SECONDS,
            ),
            DEFAULT_RATE_LIMIT_BACKOFF_SECONDS,
            MIN_RATE_LIMIT_BACKOFF_SECONDS,
            MAX_RATE_LIMIT_BACKOFF_SECONDS,
        )
        self.transient_backoff_seconds = _bounded_seconds(
            config.get(
                "transient_backoff_seconds",
                DEFAULT_TRANSIENT_BACKOFF_SECONDS,
            ),
            DEFAULT_TRANSIENT_BACKOFF_SECONDS,
            MIN_RATE_LIMIT_BACKOFF_SECONDS,
            MAX_RATE_LIMIT_BACKOFF_SECONDS,
        )
        self.max_requests_per_hour = int(
            round(
                _bounded_seconds(
                    config.get(
                        "max_requests_per_hour",
                        DEFAULT_MAX_REQUESTS_PER_HOUR,
                    ),
                    DEFAULT_MAX_REQUESTS_PER_HOUR,
                    MIN_MAX_REQUESTS_PER_HOUR,
                    MAX_MAX_REQUESTS_PER_HOUR,
                )
            )
        )
        self._effective_profile_refresh_seconds = self.profile_refresh_seconds
        self._effective_live_refresh_seconds = self.live_refresh_seconds
        self._cadence_account_count = 0
        self._last_profile_refresh_at: dict[int, float] = {}
        self._profile_snapshots: dict[
            int,
            tuple[str, Any, Any, int | None],
        ] = {}
        self._last_live_refresh_at: dict[int, float] = {}
        self._match_snapshots: dict[int, list[dict[str, Any]]] = {}
        self._rate_limit_until = 0.0
        self._rate_limit_wall_until = 0
        self._rate_limit_failures = 0
        self._invalid_json_failures: dict[str, int] = {}
        self._successful_requests_this_cycle = 0
        self._had_recoverable_error_this_cycle = False
        self._last_protection_decay_at = 0.0
        self._uid_rotation = 0
        self._wake_event = asyncio.Event()
        self._forced_refresh_uids: set[int] = set()
        self._last_manual_refresh_at: dict[int, float] = {}
        self._protection_restored = False
        self._state_file_error = ""

    def start(self) -> None:
        if not self.config.get("enabled", True):
            self.logger("Rivals Data polling disabled in config.")
            return
        try:
            self._restore_provider_state()
        except RivalsStateFileError as exc:
            self._report_state_file_error(exc)
        self.task = asyncio.create_task(
            self._run(),
            name="overlay-studio-rivals-data",
        )

    async def stop(self) -> None:
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    def _report_state_file_error(self, error: Exception) -> None:
        message = " ".join(str(error).split())[:500]
        if message == self._state_file_error:
            return
        self._state_file_error = message
        self.logger(f"CRITICAL: {message}")

    def _restore_provider_state(self) -> None:
        if self._protection_restored:
            return
        saved = load_rate_limit_state(self.state_path)
        wall_now = time.time()
        self._rate_limit_failures = saved["failures"]
        if saved["until"] > wall_now:
            remaining = saved["until"] - wall_now
            self._rate_limit_until = time.monotonic() + remaining
            self._rate_limit_wall_until = saved["until"]
            self.logger(
                "Restored Rivals Data protection cooldown for about "
                f"{max(1, math.ceil(remaining / 60))} minutes."
            )
        elif saved["until"]:
            self._rate_limit_until = 0.0
            self._rate_limit_wall_until = 0
            save_rate_limit_state(
                self.state_path,
                0,
                self._rate_limit_failures,
            )
        self._protection_restored = True

    def cooldown_remaining(self) -> float:
        return max(0.0, self._rate_limit_until - time.monotonic())

    def wake_for_link(self, uid: int) -> None:
        self._forced_refresh_uids.add(uid)
        self._wake_event.set()

    def request_manual_refresh(self, uid: int) -> dict[str, Any]:
        now = time.monotonic()
        cooldown = self.cooldown_remaining()
        if cooldown > 0:
            return {
                "accepted": False,
                "retryAfter": max(1, math.ceil(cooldown)),
                "retryAt": self._rate_limit_wall_until,
                "detail": "Updates are temporarily paused",
            }
        previous = self._last_manual_refresh_at.get(uid)
        if previous is not None and now - previous < MANUAL_REFRESH_SECONDS:
            retry_after = math.ceil(MANUAL_REFRESH_SECONDS - (now - previous))
            return {
                "accepted": False,
                "retryAfter": max(1, retry_after),
                "retryAt": int(time.time()) + max(1, retry_after),
                "detail": "Refresh is available once per minute",
            }
        self._last_manual_refresh_at[uid] = now
        self._forced_refresh_uids.add(uid)
        self._wake_event.set()
        return {
            "accepted": True,
            "retryAfter": int(MANUAL_REFRESH_SECONDS),
            "retryAt": int(time.time() + MANUAL_REFRESH_SECONDS),
            "detail": "Refresh requested",
        }

    def _set_adaptive_cadence(self, account_count: int) -> None:
        count = max(0, int(account_count))
        if count <= 0:
            self._effective_profile_refresh_seconds = self.profile_refresh_seconds
            self._effective_live_refresh_seconds = self.live_refresh_seconds
        else:
            safe_budget = max(
                1.0,
                self.max_requests_per_hour * REQUEST_BUDGET_HEADROOM_RATIO,
            )
            worst_case_per_account = (
                3600.0
                / (
                    self.profile_refresh_seconds
                    * REFRESH_GATE_TOLERANCE_RATIO
                )
                + MATCH_REQUESTS_PER_REFRESH
                * 3600.0
                / (
                    self.live_refresh_seconds
                    * REFRESH_GATE_TOLERANCE_RATIO
                )
            )
            scale = max(
                1.0,
                count * worst_case_per_account / safe_budget,
            )
            self._effective_profile_refresh_seconds = (
                self.profile_refresh_seconds * scale
            )
            self._effective_live_refresh_seconds = self.live_refresh_seconds * scale
        self._cadence_account_count = count

    async def _reserve_request_slot(self, endpoint: str) -> None:
        async with self.store_lock:
            allowed, retry_after, count = reserve_rivals_request(
                self.state_path,
                self.max_requests_per_hour,
            )
        if not allowed:
            raise RivalsRequestBudgetError(float(retry_after))
        endpoint_name = endpoint.removeprefix("https://api.rivalsdata.com")
        self.logger(
            f"Rivals Data request {count}/{self.max_requests_per_hour}: "
            f"{endpoint_name}"
        )

    async def _request_json(
        self,
        session: ClientSession,
        endpoint: str,
        uid: int,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        await self._reserve_request_slot(endpoint)
        request_body: dict[str, Any] = {"uid": uid}
        if payload:
            request_body.update(payload)
        async with session.post(endpoint, json=request_body) as response:
            if response.status == 429:
                raise RivalsRateLimitError(
                    _parse_retry_after(response.headers.get("Retry-After"))
                )
            if response.status in {403, 408} or 500 <= response.status <= 599:
                raise RivalsProviderBackoffError(
                    f"Rivals Data returned HTTP {response.status}",
                    _parse_retry_after(response.headers.get("Retry-After")),
                )
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(f"Rivals Data returned HTTP {response.status}")
            if (
                response.content_length is not None
                and response.content_length > MAX_RESPONSE_BYTES
            ):
                raise RuntimeError("Rivals Data response was too large")
            body = bytearray()
            async for chunk in response.content.iter_chunked(64 * 1024):
                body.extend(chunk)
                if len(body) > MAX_RESPONSE_BYTES:
                    raise RuntimeError("Rivals Data response was too large")
            content_type = str(response.headers.get("Content-Type") or "").lower()
        try:
            text = bytes(body).decode("utf-8")
        except UnicodeDecodeError as exc:
            failures = self._invalid_json_failures.get(endpoint, 0) + 1
            self._invalid_json_failures[endpoint] = failures
            if failures >= INVALID_JSON_BACKOFF_THRESHOLD:
                raise RivalsProviderBackoffError(
                    "Rivals Data repeatedly returned invalid JSON"
                ) from exc
            raise RuntimeError("Rivals Data returned invalid JSON") from exc
        stripped = text.lstrip().lower()
        if "text/html" in content_type or stripped.startswith(("<!doctype", "<html")):
            self._invalid_json_failures[endpoint] = (
                self._invalid_json_failures.get(endpoint, 0) + 1
            )
            raise RivalsProviderBackoffError(
                "Rivals Data returned a browser challenge instead of JSON"
            )
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            failures = self._invalid_json_failures.get(endpoint, 0) + 1
            self._invalid_json_failures[endpoint] = failures
            if failures >= INVALID_JSON_BACKOFF_THRESHOLD:
                raise RivalsProviderBackoffError(
                    "Rivals Data repeatedly returned invalid JSON"
                ) from exc
            raise RuntimeError("Rivals Data returned invalid JSON") from exc
        self._invalid_json_failures.pop(endpoint, None)
        self._successful_requests_this_cycle += 1
        return parsed

    async def _load_profile_snapshot(
        self,
        session: ClientSession,
        uid: int,
        *,
        force: bool = False,
    ) -> tuple[str, Any, Any, int | None]:
        cached = self._profile_snapshots.get(uid)
        now = time.monotonic()
        previous = self._last_profile_refresh_at.get(uid)
        if (
            not force
            and cached is not None
            and previous is not None
            and now - previous
            < (
                self._effective_profile_refresh_seconds
                * REFRESH_GATE_TOLERANCE_RATIO
            )
        ):
            return cached

        self._last_profile_refresh_at[uid] = now
        try:
            profile = await self._request_json(session, PROFILE_ENDPOINT, uid)
        except asyncio.CancelledError:
            raise
        except (
            RivalsRateLimitError,
            RivalsProviderBackoffError,
            RivalsRequestBudgetError,
        ):
            raise
        except Exception:
            self._had_recoverable_error_this_cycle = True
            if cached is not None:
                return cached
            return "", None, None, None

        player_name, rank_level, rank_score = extract_profile_snapshot(profile)
        profile_season, _profile_rank = _latest_rank_season(profile)
        if (
            player_name
            or rank_level is not None
            or rank_score is not None
            or profile_season is not None
        ):
            snapshot = (
                player_name,
                rank_level,
                rank_score,
                profile_season,
            )
            self._profile_snapshots[uid] = snapshot
            return snapshot
        if cached is not None:
            return cached
        return "", None, None, None

    def _should_refresh_live_matches(self, uid: int, *, force: bool = False) -> bool:
        now = time.monotonic()
        previous = self._last_live_refresh_at.get(uid)
        if (
            not force
            and uid in self._match_snapshots
            and previous is not None
            and now - previous
            < (
                self._effective_live_refresh_seconds
                * REFRESH_GATE_TOLERANCE_RATIO
            )
        ):
            return False
        self._last_live_refresh_at[uid] = now
        return True

    async def _load_matches(
        self,
        session: ClientSession,
        uid: int,
        profile_season: int | None,
        *,
        force: bool = False,
    ) -> list[dict[str, Any]]:
        if not self._should_refresh_live_matches(uid, force=force):
            return list(self._match_snapshots.get(uid, []))

        refresh_payload: dict[str, Any] = {"cursor": None}
        if profile_season is not None:
            refresh_payload["season"] = profile_season
        try:
            live_payload = await self._request_json(
                session,
                MATCHES_REFRESH_ENDPOINT,
                uid,
                refresh_payload,
            )
        except asyncio.CancelledError:
            raise
        except (
            RivalsRateLimitError,
            RivalsProviderBackoffError,
            RivalsRequestBudgetError,
        ):
            raise
        except Exception:
            self._had_recoverable_error_this_cycle = True
            live_payload = None

        live_matches = [
            match
            for match in extract_matches(live_payload)
            if is_competitive_match(match)
        ]
        if live_matches:
            self._match_snapshots[uid] = live_matches
            return list(live_matches)

        cached_payload = await self._request_json(session, MATCHES_ENDPOINT, uid)
        cached_matches = [
            match
            for match in extract_matches(cached_payload)
            if is_competitive_match(match)
        ]
        self._match_snapshots[uid] = cached_matches
        return list(cached_matches)

    async def _fetch_uid(
        self,
        session: ClientSession,
        uid: int,
        *,
        force: bool = False,
    ) -> tuple[str, Any, Any, list[dict[str, Any]]]:
        (
            player_name,
            rank_level,
            rank_score,
            profile_season,
        ) = await self._load_profile_snapshot(session, uid, force=force)
        matches = await self._load_matches(
            session,
            uid,
            profile_season,
            force=force,
        )
        if matches:
            # Profile scores are current while the cached match list can lag.
            # Keep a complete profile rank pair together; otherwise use the
            # newest match pair or fill a missing level from the same season.
            newest = matches[0]
            match_level = newest.get("rank_level", newest.get("rankLevel"))
            match_score = newest.get("rank_score", newest.get("rankScore"))
            match_season = _optional_integer(newest.get("season"))
            profile_pair_is_current = (
                rank_level is not None
                and rank_score is not None
                and (
                    profile_season is None
                    or match_season is None
                    or profile_season >= match_season
                )
            )
            if not profile_pair_is_current:
                if (
                    rank_score is not None
                    and rank_level is None
                    and profile_season is not None
                    and profile_season == match_season
                    and match_level is not None
                ):
                    rank_level = match_level
                else:
                    rank_level = match_level if match_level is not None else rank_level
                    rank_score = match_score if match_score is not None else rank_score

        return player_name, rank_level, rank_score, matches

    async def _poll_uid(
        self,
        session: ClientSession,
        uid: int,
        instance_ids: list[str],
        *,
        force: bool = False,
    ) -> None:
        successful_requests_before = self._successful_requests_this_cycle
        player_name, rank_level, rank_score, matches = await self._fetch_uid(
            session,
            uid,
            force=force,
        )
        verified_update = (
            self._successful_requests_this_cycle > successful_requests_before
        )

        async with self.store_lock:
            results = save_rivals_polls(
                self.state_path,
                instance_ids,
                uid,
                player_name=player_name,
                rank_level=rank_level,
                rank_score=rank_score,
                matches=matches,
                mark_success=verified_update,
            )
        for instance_id, (state, changed) in results.items():
            if changed:
                await self.broadcast(
                    {
                        "type": "rivals",
                        "instanceId": instance_id,
                        "state": state,
                    }
                )

    def _report_error(self, instance_id: str, error: Exception) -> None:
        message = " ".join(str(error).split()) or type(error).__name__
        message = message[:180]
        now = time.monotonic()
        # Deduplicate repeats, but never go fully silent: once the backoff
        # ladder saturates every message is identical, so plain deduplication
        # hides a permanently stuck tracker behind an empty log.
        last_message, last_logged_at = self._last_errors.get(
            instance_id,
            ("", 0.0),
        )
        if (
            last_message == message
            and now - last_logged_at < ERROR_RELOG_INTERVAL_SECONDS
        ):
            return
        repeated = last_message == message
        self._last_errors[instance_id] = (message, now)
        self.logger(
            f"Rivals Data polling error for {instance_id}: {message}."
            + (" Still failing." if repeated else "")
            + " Keeping the last known overlay state."
        )

    def _begin_provider_cooldown(
        self,
        error: RivalsRateLimitError | RivalsProviderBackoffError,
    ) -> tuple[float, int]:
        self._rate_limit_failures = min(5, self._rate_limit_failures + 1)
        base = (
            self.rate_limit_backoff_seconds
            if isinstance(error, RivalsRateLimitError)
            else self.transient_backoff_seconds
        )
        fallback = min(
            MAX_RATE_LIMIT_BACKOFF_SECONDS,
            base * (2 ** (self._rate_limit_failures - 1)),
        )
        requested = error.retry_after_seconds
        if requested is None:
            delay = fallback
        elif self._rate_limit_failures <= 1:
            delay = requested
        else:
            delay = max(requested, fallback)
        delay = max(
            MIN_RATE_LIMIT_BACKOFF_SECONDS,
            min(MAX_RATE_LIMIT_BACKOFF_SECONDS, delay),
        )
        self._rate_limit_until = max(
            self._rate_limit_until,
            time.monotonic() + delay,
        )
        wall_until = int(math.ceil(time.time() + delay))
        self._rate_limit_wall_until = max(
            self._rate_limit_wall_until,
            wall_until,
        )
        return delay, self._rate_limit_wall_until

    def _pause_detail(self, error: Exception, delay: float) -> RuntimeError:
        minutes = max(1, math.ceil(delay / 60.0))
        unit = "minute" if minutes == 1 else "minutes"
        if isinstance(error, RivalsRateLimitError):
            reason = "Rivals Data rate limit reached"
        else:
            reason = str(error)
        return RuntimeError(
            f"{reason}; updates paused for about {minutes} {unit}"
        )

    async def poll_once(self, session: ClientSession) -> float:
        self._restore_provider_state()
        cooldown_remaining = self.cooldown_remaining()
        if cooldown_remaining > 0:
            return cooldown_remaining

        async with self.store_lock:
            linked = linked_rivals_instances(self.state_path)
        grouped: dict[int, list[str]] = defaultdict(list)
        for instance_id, uid in linked:
            grouped[uid].append(instance_id)
        if not grouped:
            self._set_adaptive_cadence(0)
            return 0.0

        uids = list(grouped)
        self._set_adaptive_cadence(len(uids))
        start = self._uid_rotation % len(uids)
        ordered_uids = [*uids[start:], *uids[:start]]
        self._uid_rotation = (start + 1) % len(uids)
        all_succeeded = True
        self._successful_requests_this_cycle = 0
        self._had_recoverable_error_this_cycle = False
        for uid_index, uid in enumerate(ordered_uids):
            instance_ids = grouped[uid]
            force = uid in self._forced_refresh_uids
            self._forced_refresh_uids.discard(uid)
            try:
                await self._poll_uid(
                    session,
                    uid,
                    instance_ids,
                    force=force,
                )
            except asyncio.CancelledError:
                raise
            except RivalsRequestBudgetError as exc:
                self._uid_rotation = (start + uid_index) % len(uids)
                delay = max(
                    1.0,
                    min(MAX_RATE_LIMIT_BACKOFF_SECONDS, exc.retry_after_seconds),
                )
                minutes = max(1, math.ceil(delay / 60.0))
                unit = "minute" if minutes == 1 else "minutes"
                detail = (
                    "Local request budget is pacing updates; next slot in "
                    f"about {minutes} {unit}"
                )
                queued = [
                    (queued_instance, queued_uid)
                    for queued_uid in ordered_uids[uid_index:]
                    for queued_instance in grouped[queued_uid]
                ]
                async with self.store_lock:
                    queued_instances = save_rivals_poll_waits(
                        self.state_path,
                        queued,
                        detail,
                    )
                retained_errors = len(queued) - len(queued_instances)
                retained_note = (
                    f" {retained_errors} provider error status(es) were preserved."
                    if retained_errors
                    else ""
                )
                self.logger(
                    f"{detail}. {len(queued_instances)} linked overlay(s) remain "
                    "queued; provider cooldown was not changed."
                    f"{retained_note}"
                )
                return delay
            except (
                RivalsRateLimitError,
                RivalsProviderBackoffError,
            ) as exc:
                delay, wall_until = self._begin_provider_cooldown(exc)
                detail = self._pause_detail(exc, delay)
                async with self.store_lock:
                    save_rivals_poll_failures(
                        self.state_path,
                        linked,
                        detail,
                        rate_limit_until=wall_until,
                        rate_limit_failures=self._rate_limit_failures,
                    )
                self._report_error(instance_ids[0], detail)
                return delay
            except Exception as exc:
                all_succeeded = False
                async with self.store_lock:
                    save_rivals_poll_failures(
                        self.state_path,
                        [(instance_id, uid) for instance_id in instance_ids],
                        exc,
                    )
                for instance_id in instance_ids:
                    self._report_error(instance_id, exc)
            else:
                for instance_id in instance_ids:
                    if instance_id in self._last_errors:
                        self._last_errors.pop(instance_id, None)
                        self.logger(
                            f"Rivals Data polling recovered for {instance_id}."
                        )
        clean_cycle = all_succeeded and not self._had_recoverable_error_this_cycle
        now = time.monotonic()
        decay_due = (
            self._last_protection_decay_at <= 0
            or now - self._last_protection_decay_at
            >= PROTECTION_DECAY_INTERVAL_SECONDS
        )
        if clean_cycle and decay_due:
            self._last_protection_decay_at = now
            self._rate_limit_failures = max(0, self._rate_limit_failures - 1)
            self._rate_limit_until = 0.0
            self._rate_limit_wall_until = 0
            async with self.store_lock:
                save_rate_limit_state(
                    self.state_path,
                    0,
                    self._rate_limit_failures,
                )
        return 0.0

    async def _wait_for_wake(self, delay: float) -> None:
        try:
            await asyncio.wait_for(
                self._wake_event.wait(),
                timeout=max(0.0, delay),
            )
        except asyncio.TimeoutError:
            pass
        finally:
            self._wake_event.clear()

    async def _run(self) -> None:
        poll_seconds = _bounded_seconds(
            self.config.get("poll_seconds", DEFAULT_POLL_SECONDS),
            DEFAULT_POLL_SECONDS,
            MIN_POLL_SECONDS,
            MAX_POLL_SECONDS,
        )
        timeout_seconds = _bounded_seconds(
            self.config.get("timeout_seconds", 12),
            12.0,
            3.0,
            30.0,
        )
        timeout = ClientTimeout(total=timeout_seconds)
        # INTERIM WORKAROUND, pending a supported integration.
        #
        # The API began returning HTTP 403 after ~26 otherwise-successful
        # requests, which looks like WAF/bot filtering. Origin and Referer are
        # sent to match what rivalsdata.com's own frontend sends. Be honest
        # about what that means: it asserts a provenance the request does not
        # have. The User-Agent stays truthful so the operator can still
        # identify and block this client if they choose to.
        #
        # This is not provider-authorized. We are asking rivalsdata for a
        # supported way to read a player's own profile; remove this block if
        # they decline, and do not escalate the imitation (a spoofed browser
        # User-Agent, cookie replay, or challenge solving) if 403s persist.
        # Persistent 403s mean the provider is declining automated access.
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": SITE_ORIGIN,
            "Referer": f"{SITE_ORIGIN}/",
            "User-Agent": "Overlay-Studio/1.0 (local stream overlay)",
        }
        self.logger(
            f"Rivals Data worker checks every {poll_seconds:g} seconds; "
            f"base profile and live-history cadence is "
            f"{self.profile_refresh_seconds:g} and "
            f"{self.live_refresh_seconds:g} seconds. Linked accounts share "
            f"a {self.max_requests_per_hour}-request/hour safety budget, "
            "with cached history used only as fallback."
        )
        async with ClientSession(timeout=timeout, headers=headers) as session:
            await self._wait_for_wake(
                random.uniform(
                    STARTUP_DELAY_MIN_SECONDS,
                    STARTUP_DELAY_MAX_SECONDS,
                )
            )
            while True:
                try:
                    cooldown = await self.poll_once(session)
                except RivalsStateFileError as exc:
                    self._report_state_file_error(exc)
                    cooldown = poll_seconds
                else:
                    self._state_file_error = ""
                if cooldown > 0:
                    delay = max(poll_seconds, cooldown)
                else:
                    delay = poll_seconds * random.uniform(
                        1.0 - POLL_JITTER_RATIO,
                        1.0 + POLL_JITTER_RATIO,
                    )
                await self._wait_for_wake(delay)
