from __future__ import annotations

import asyncio
import datetime as dt
import json
import math
import time
from collections import deque
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Awaitable, Callable

from aiohttp import ClientSession, ClientTimeout

from rivals_store import (
    is_competitive_match,
    linked_rivals_instances,
    save_rivals_poll,
    save_rivals_poll_failure,
)


PROFILE_ENDPOINT = "https://api.rivalsdata.com/player"
MATCHES_ENDPOINT = "https://api.rivalsdata.com/player/matches/cached"
MATCHES_REFRESH_ENDPOINT = "https://api.rivalsdata.com/player/matches"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_MATCHES = 64
DEFAULT_POLL_SECONDS = 120.0
MIN_POLL_SECONDS = 60.0
MAX_POLL_SECONDS = 300.0
DEFAULT_PROFILE_REFRESH_SECONDS = 300.0
MIN_PROFILE_REFRESH_SECONDS = 120.0
MAX_PROFILE_REFRESH_SECONDS = 900.0
DEFAULT_LIVE_REFRESH_SECONDS = 300.0
MIN_LIVE_REFRESH_SECONDS = 60.0
MAX_LIVE_REFRESH_SECONDS = 900.0
DEFAULT_RATE_LIMIT_BACKOFF_SECONDS = 300.0
MIN_RATE_LIMIT_BACKOFF_SECONDS = 60.0
MAX_RATE_LIMIT_BACKOFF_SECONDS = 3600.0


class RivalsRateLimitError(RuntimeError):
    def __init__(self, retry_after_seconds: float | None = None) -> None:
        super().__init__("Rivals Data rate limit reached")
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
        self._last_errors: dict[str, str] = {}
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
        self._last_profile_refresh_at: dict[str, float] = {}
        self._profile_snapshots: dict[
            str,
            tuple[int, str, Any, Any, int | None],
        ] = {}
        self._last_live_refresh_at: dict[str, float] = {}
        self._rate_limit_until = 0.0
        self._rate_limit_failures = 0

    def start(self) -> None:
        if not self.config.get("enabled", True):
            self.logger("Rivals Data polling disabled in config.")
            return
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

    async def _request_json(
        self,
        session: ClientSession,
        endpoint: str,
        uid: int,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        request_body: dict[str, Any] = {"uid": uid}
        if payload:
            request_body.update(payload)
        async with session.post(endpoint, json=request_body) as response:
            if response.status == 429:
                raise RivalsRateLimitError(
                    _parse_retry_after(response.headers.get("Retry-After"))
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
        try:
            return json.loads(bytes(body).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise RuntimeError("Rivals Data returned invalid JSON") from exc

    async def _load_profile_snapshot(
        self,
        session: ClientSession,
        instance_id: str,
        uid: int,
    ) -> tuple[str, Any, Any, int | None]:
        cached = self._profile_snapshots.get(instance_id)
        cached_matches_uid = cached is not None and cached[0] == uid
        now = time.monotonic()
        previous = self._last_profile_refresh_at.get(instance_id)
        if (
            cached_matches_uid
            and previous is not None
            and now - previous < self.profile_refresh_seconds
        ):
            return cached[1:]

        self._last_profile_refresh_at[instance_id] = now
        try:
            profile = await self._request_json(session, PROFILE_ENDPOINT, uid)
        except asyncio.CancelledError:
            raise
        except RivalsRateLimitError:
            raise
        except Exception:
            if cached_matches_uid:
                return cached[1:]
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
                uid,
                player_name,
                rank_level,
                rank_score,
                profile_season,
            )
            self._profile_snapshots[instance_id] = snapshot
            return snapshot[1:]
        if cached_matches_uid:
            return cached[1:]
        return "", None, None, None

    def _should_refresh_live_matches(self, instance_id: str) -> bool:
        now = time.monotonic()
        previous = self._last_live_refresh_at.get(instance_id)
        if previous is not None and now - previous < self.live_refresh_seconds:
            return False
        self._last_live_refresh_at[instance_id] = now
        return True

    async def _load_matches_payload(
        self,
        session: ClientSession,
        instance_id: str,
        uid: int,
        profile_season: int | None,
    ) -> Any:
        if self._should_refresh_live_matches(instance_id):
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
            except RivalsRateLimitError:
                raise
            except Exception:
                live_payload = None
            if any(
                is_competitive_match(match)
                for match in extract_matches(live_payload)
            ):
                return live_payload
        return await self._request_json(session, MATCHES_ENDPOINT, uid)

    async def _poll_instance(
        self,
        session: ClientSession,
        instance_id: str,
        uid: int,
    ) -> None:
        (
            player_name,
            rank_level,
            rank_score,
            profile_season,
        ) = await self._load_profile_snapshot(session, instance_id, uid)
        matches_payload = await self._load_matches_payload(
            session, instance_id, uid, profile_season
        )
        matches = [
            match
            for match in extract_matches(matches_payload)
            if is_competitive_match(match)
        ]
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

        async with self.store_lock:
            state, changed = save_rivals_poll(
                self.state_path,
                instance_id,
                uid,
                player_name=player_name,
                rank_level=rank_level,
                rank_score=rank_score,
                matches=matches,
            )
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
        if self._last_errors.get(instance_id) == message:
            return
        self._last_errors[instance_id] = message
        self.logger(
            f"Rivals Data polling error for {instance_id}: {message}. "
            "Keeping the last known overlay state."
        )

    def _begin_rate_limit_cooldown(self, error: RivalsRateLimitError) -> float:
        self._rate_limit_failures = min(5, self._rate_limit_failures + 1)
        fallback = min(
            MAX_RATE_LIMIT_BACKOFF_SECONDS,
            self.rate_limit_backoff_seconds
            * (2 ** (self._rate_limit_failures - 1)),
        )
        requested = error.retry_after_seconds
        delay = fallback if requested is None else requested
        delay = max(
            MIN_RATE_LIMIT_BACKOFF_SECONDS,
            min(MAX_RATE_LIMIT_BACKOFF_SECONDS, delay),
        )
        self._rate_limit_until = max(
            self._rate_limit_until,
            time.monotonic() + delay,
        )
        return delay

    def _rate_limit_detail(self, delay: float) -> RuntimeError:
        minutes = max(1, math.ceil(delay / 60.0))
        unit = "minute" if minutes == 1 else "minutes"
        return RuntimeError(
            f"Rivals Data rate limit reached; updates paused for about "
            f"{minutes} {unit}"
        )

    async def poll_once(self, session: ClientSession) -> float:
        cooldown_remaining = self._rate_limit_until - time.monotonic()
        if cooldown_remaining > 0:
            return cooldown_remaining

        async with self.store_lock:
            linked = linked_rivals_instances(self.state_path)
        completed = False
        for instance_id, uid in linked:
            try:
                await self._poll_instance(session, instance_id, uid)
            except asyncio.CancelledError:
                raise
            except RivalsRateLimitError as exc:
                delay = self._begin_rate_limit_cooldown(exc)
                detail = self._rate_limit_detail(delay)
                async with self.store_lock:
                    for paused_instance_id, paused_uid in linked:
                        save_rivals_poll_failure(
                            self.state_path,
                            paused_instance_id,
                            paused_uid,
                            detail,
                        )
                self._report_error(instance_id, detail)
                return delay
            except Exception as exc:
                async with self.store_lock:
                    save_rivals_poll_failure(
                        self.state_path,
                        instance_id,
                        uid,
                        exc,
                    )
                self._report_error(instance_id, exc)
            else:
                completed = True
                if instance_id in self._last_errors:
                    self._last_errors.pop(instance_id, None)
                    self.logger(f"Rivals Data polling recovered for {instance_id}.")
        if completed:
            self._rate_limit_failures = 0
            self._rate_limit_until = 0.0
        return 0.0

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
        headers = {
            "Accept": "application/json",
            "User-Agent": "Overlay-Studio/1.0 (local stream overlay)",
        }
        self.logger(
            f"Rivals Data polling enabled every {poll_seconds:g} seconds; "
            f"profile and live-history refreshes every "
            f"{self.profile_refresh_seconds:g} and "
            f"{self.live_refresh_seconds:g} seconds."
        )
        async with ClientSession(timeout=timeout, headers=headers) as session:
            while True:
                cooldown = await self.poll_once(session)
                await asyncio.sleep(max(poll_seconds, cooldown))
