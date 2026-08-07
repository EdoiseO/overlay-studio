from __future__ import annotations

import asyncio
import datetime as dt
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parent))

from rivals_store import (  # noqa: E402
    load_rate_limit_state,
    reserve_rivals_request,
    rivals_status,
    save_rate_limit_state,
    save_rivals_poll_failures,
    update_rivals_record,
)
from rivals_worker import (  # noqa: E402
    MATCHES_ENDPOINT,
    MATCHES_REFRESH_ENDPOINT,
    PROFILE_ENDPOINT,
    ERROR_RELOG_INTERVAL_SECONDS,
    REFRESH_GATE_TOLERANCE_RATIO,
    SITE_ORIGIN,
    RivalsProviderBackoffError,
    RivalsRateLimitError,
    RivalsRequestBudgetError,
    RivalsPollWorker,
    _parse_retry_after,
    extract_matches,
    extract_profile_snapshot,
)


class FakeResponseContent:
    def __init__(self, body: bytes) -> None:
        self.body = body

    async def iter_chunked(self, _size: int):
        yield self.body


class FakeResponse:
    def __init__(
        self,
        status: int,
        body: bytes = b"",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self.headers = headers or {}
        self.content_length = len(body)
        self.content = FakeResponseContent(body)

    async def __aenter__(self) -> "FakeResponse":
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None


class RivalsWorkerTests(unittest.IsolatedAsyncioTestCase):
    def test_retry_after_accepts_seconds_and_http_dates(self) -> None:
        now = dt.datetime(2026, 8, 6, 18, 0, tzinfo=dt.timezone.utc)

        self.assertEqual(_parse_retry_after("120", now), 120)
        self.assertEqual(
            _parse_retry_after("Thu, 06 Aug 2026 18:05:00 GMT", now),
            300,
        )
        self.assertIsNone(_parse_retry_after("not-a-delay", now))

    async def test_http_429_captures_retry_after(self) -> None:
        class Response:
            status = 429
            headers = {"Retry-After": "180"}

            async def __aenter__(self) -> "Response":
                return self

            async def __aexit__(self, *_args: object) -> None:
                return None

        session = mock.MagicMock()
        session.post.return_value = Response()
        worker = RivalsPollWorker(
            Path("unused.json"),
            mock.AsyncMock(),
            {},
            store_lock=asyncio.Lock(),
            logger=lambda _message: None,
        )
        worker._reserve_request_slot = mock.AsyncMock()  # type: ignore[method-assign]

        with self.assertRaises(RivalsRateLimitError) as raised:
            await worker._request_json(session, PROFILE_ENDPOINT, 396536339)

        self.assertEqual(raised.exception.retry_after_seconds, 180)

    async def test_http_403_requests_provider_backoff(self) -> None:
        session = mock.MagicMock()
        session.post.return_value = FakeResponse(403)
        worker = RivalsPollWorker(
            Path("unused.json"),
            mock.AsyncMock(),
            {},
            store_lock=asyncio.Lock(),
            logger=lambda _message: None,
        )
        worker._reserve_request_slot = mock.AsyncMock()  # type: ignore[method-assign]

        with self.assertRaises(RivalsProviderBackoffError) as raised:
            await worker._request_json(session, PROFILE_ENDPOINT, 396536339)

        self.assertIn("HTTP 403", str(raised.exception))

    async def test_html_challenge_requests_provider_backoff(self) -> None:
        session = mock.MagicMock()
        session.post.return_value = FakeResponse(
            200,
            b"<!doctype html><title>Just a moment</title>",
            {"Content-Type": "text/html; charset=UTF-8"},
        )
        worker = RivalsPollWorker(
            Path("unused.json"),
            mock.AsyncMock(),
            {},
            store_lock=asyncio.Lock(),
            logger=lambda _message: None,
        )
        worker._reserve_request_slot = mock.AsyncMock()  # type: ignore[method-assign]

        with self.assertRaises(RivalsProviderBackoffError) as raised:
            await worker._request_json(session, PROFILE_ENDPOINT, 396536339)

        self.assertIn("browser challenge", str(raised.exception))

    async def test_repeated_invalid_json_requests_provider_backoff(self) -> None:
        session = mock.MagicMock()
        session.post.return_value = FakeResponse(
            200,
            b"not-json",
            {"Content-Type": "application/json"},
        )
        worker = RivalsPollWorker(
            Path("unused.json"),
            mock.AsyncMock(),
            {},
            store_lock=asyncio.Lock(),
            logger=lambda _message: None,
        )
        worker._reserve_request_slot = mock.AsyncMock()  # type: ignore[method-assign]

        for _attempt in range(2):
            with self.assertRaisesRegex(RuntimeError, "invalid JSON"):
                await worker._request_json(session, PROFILE_ENDPOINT, 396536339)
        with self.assertRaises(RivalsProviderBackoffError):
            await worker._request_json(session, PROFILE_ENDPOINT, 396536339)

    async def test_valid_other_endpoint_does_not_clear_invalid_json_streak(
        self,
    ) -> None:
        invalid = FakeResponse(
            200,
            b"not-json",
            {"Content-Type": "application/json"},
        )
        valid = FakeResponse(
            200,
            b"{}",
            {"Content-Type": "application/json"},
        )
        session = mock.MagicMock()
        session.post.side_effect = [invalid, valid, invalid, valid, invalid]
        worker = RivalsPollWorker(
            Path("unused.json"),
            mock.AsyncMock(),
            {},
            store_lock=asyncio.Lock(),
            logger=lambda _message: None,
        )
        worker._reserve_request_slot = mock.AsyncMock()  # type: ignore[method-assign]

        for _attempt in range(2):
            with self.assertRaisesRegex(RuntimeError, "invalid JSON"):
                await worker._request_json(session, PROFILE_ENDPOINT, 396536339)
            self.assertEqual(
                await worker._request_json(session, MATCHES_ENDPOINT, 396536339),
                {},
            )
        with self.assertRaises(RivalsProviderBackoffError):
            await worker._request_json(session, PROFILE_ENDPOINT, 396536339)

    async def test_hourly_budget_blocks_before_session_request(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "rivals.json"
            for _index in range(12):
                allowed, _retry_after, _count = reserve_rivals_request(
                    path,
                    12,
                    now=1_000,
                )
                self.assertTrue(allowed)
            worker = RivalsPollWorker(
                path,
                mock.AsyncMock(),
                {"max_requests_per_hour": 12},
                store_lock=asyncio.Lock(),
                logger=lambda _message: None,
            )
            session = mock.MagicMock()

            with (
                mock.patch("rivals_store.time.time", return_value=1_001),
                mock.patch("rivals_worker.time.time", return_value=1_001),
                self.assertRaises(RivalsRequestBudgetError),
            ):
                await worker._request_json(
                    session,
                    PROFILE_ENDPOINT,
                    396536339,
                )

            session.post.assert_not_called()

    async def test_local_budget_queues_work_without_provider_cooldown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "rivals.json"
            for instance_id, uid in (
                ("rank-one", "396536339"),
                ("rank-two", "502565567"),
            ):
                update_rivals_record(path, instance_id, {"uid": uid}, now=100)
            save_rivals_poll_failures(
                path,
                [("rank-one", 396536339)],
                RuntimeError("Rivals Data returned HTTP 503"),
                now=110,
            )
            logs: list[str] = []
            worker = RivalsPollWorker(
                path,
                mock.AsyncMock(),
                {},
                store_lock=asyncio.Lock(),
                logger=logs.append,
            )
            worker._poll_uid = mock.AsyncMock(  # type: ignore[method-assign]
                side_effect=RivalsRequestBudgetError(240)
            )

            delay = await worker.poll_once(mock.MagicMock())

            self.assertEqual(delay, 240)
            self.assertEqual(worker._rate_limit_until, 0)
            self.assertEqual(
                load_rate_limit_state(path),
                {"until": 0, "failures": 0},
            )
            provider_poll = rivals_status(path, "rank-one")["poll"]
            self.assertEqual(provider_poll["status"], "error")
            self.assertEqual(
                provider_poll["detail"],
                "Rivals Data returned HTTP 503",
            )
            queued_poll = rivals_status(path, "rank-two")["poll"]
            self.assertEqual(queued_poll["status"], "queued")
            self.assertIn("Local request budget", queued_poll["detail"])
            self.assertIn("provider cooldown was not changed", logs[0])
            self.assertIn("provider error status(es) were preserved", logs[0])

    def test_extracts_nested_profile_and_match_payloads(self) -> None:
        self.assertEqual(
            extract_profile_snapshot(
                {
                    "data": {
                        "player": {"name": "iiTzEdo"},
                        "rank": {"rank_level": 17, "rank_score": 56},
                    }
                }
            ),
            ("iiTzEdo", 17, 56),
        )
        matches = extract_matches(
            {"data": {"matches": [{"match_uid": "one", "is_win": True}]}}
        )
        self.assertEqual(matches[0]["match_uid"], "one")

    def test_profile_snapshot_uses_the_current_rank_season(self) -> None:
        self.assertEqual(
            extract_profile_snapshot(
                {
                    "name": "iiTzEdo",
                    "rank_game_season": {
                        "1001004": {
                            "rank_game_id": 4,
                            "level": 14,
                            "rank_score": 4351.74,
                        },
                        "1001018": {
                            "rank_game_id": 18,
                            "level": 13,
                            "rank_score": 4656.718,
                        },
                    },
                }
            ),
            ("iiTzEdo", 13, 4656.718),
        )

    def test_live_match_refresh_is_rate_limited_per_uid(self) -> None:
        worker = RivalsPollWorker(
            Path("unused.json"),
            mock.AsyncMock(),
            {"live_refresh_seconds": 60},
            store_lock=asyncio.Lock(),
            logger=lambda _message: None,
        )
        with mock.patch(
            "rivals_worker.time.monotonic",
            side_effect=[100.0, 130.0, 160.0],
        ):
            self.assertTrue(worker._should_refresh_live_matches(396536339))
            worker._match_snapshots[396536339] = []
            self.assertFalse(worker._should_refresh_live_matches(396536339))
            self.assertTrue(worker._should_refresh_live_matches(396536339))

    def test_multiple_accounts_stretch_cadence_below_shared_budget(self) -> None:
        worker = RivalsPollWorker(
            Path("unused.json"),
            mock.AsyncMock(),
            {},
            store_lock=asyncio.Lock(),
            logger=lambda _message: None,
        )

        worker._set_adaptive_cadence(1)
        self.assertEqual(worker._effective_profile_refresh_seconds, 300)
        self.assertEqual(worker._effective_live_refresh_seconds, 120)

        worker._set_adaptive_cadence(4)
        hourly_worst_case = 4 * (
            3600
            / (
                worker._effective_profile_refresh_seconds
                * REFRESH_GATE_TOLERANCE_RATIO
            )
            + 2
            * 3600
            / (
                worker._effective_live_refresh_seconds
                * REFRESH_GATE_TOLERANCE_RATIO
            )
        )
        self.assertAlmostEqual(
            worker._effective_profile_refresh_seconds,
            888.8888888888889,
        )
        self.assertAlmostEqual(
            worker._effective_live_refresh_seconds,
            355.55555555555554,
        )
        self.assertLessEqual(hourly_worst_case, 108.000001)

    def test_live_refresh_gate_averages_two_minutes_with_jitter(self) -> None:
        worker = RivalsPollWorker(
            Path("unused.json"),
            mock.AsyncMock(),
            {},
            store_lock=asyncio.Lock(),
            logger=lambda _message: None,
        )
        uid = 396536339
        increments = [108.0, 132.0] * 7 + [120.0]
        timestamps = [0.0]
        for increment in increments:
            timestamps.append(timestamps[-1] + increment)
        request_times: list[float] = []

        with mock.patch(
            "rivals_worker.time.monotonic",
            side_effect=timestamps,
        ):
            for timestamp in timestamps:
                if worker._should_refresh_live_matches(uid):
                    request_times.append(timestamp)
                    worker._match_snapshots[uid] = []

        intervals = [
            current - previous
            for previous, current in zip(request_times, request_times[1:])
        ]
        self.assertEqual(request_times[-1], 1800)
        self.assertAlmostEqual(sum(intervals) / len(intervals), 120)

    async def test_profile_snapshot_is_reused_between_refreshes(self) -> None:
        worker = RivalsPollWorker(
            Path("unused.json"),
            mock.AsyncMock(),
            {"profile_refresh_seconds": 300},
            store_lock=asyncio.Lock(),
            logger=lambda _message: None,
        )
        worker._request_json = mock.AsyncMock(  # type: ignore[method-assign]
            return_value={
                "name": "iiTzEdo",
                "rank_game_season": {
                    "1001018": {
                        "rank_game_id": 18,
                        "level": 17,
                        "rank_score": 4656.718,
                    }
                },
            }
        )

        with mock.patch(
            "rivals_worker.time.monotonic",
            side_effect=[100.0, 200.0, 401.0],
        ):
            first = await worker._load_profile_snapshot(
                mock.MagicMock(), 396536339
            )
            second = await worker._load_profile_snapshot(
                mock.MagicMock(), 396536339
            )
            third = await worker._load_profile_snapshot(
                mock.MagicMock(), 396536339
            )

        self.assertEqual(first, second)
        self.assertEqual(second, third)
        self.assertEqual(worker._request_json.await_count, 2)

    async def test_rate_limit_stops_live_refresh_fallback_request(self) -> None:
        worker = RivalsPollWorker(
            Path("unused.json"),
            mock.AsyncMock(),
            {},
            store_lock=asyncio.Lock(),
            logger=lambda _message: None,
        )
        worker._request_json = mock.AsyncMock(  # type: ignore[method-assign]
            side_effect=RivalsRateLimitError()
        )

        with self.assertRaises(RivalsRateLimitError):
            await worker._load_matches(
                mock.MagicMock(),
                396536339,
                18,
            )

        self.assertEqual(worker._request_json.await_count, 1)

    async def test_rate_limit_pauses_all_linked_instances(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "rivals.json"
            update_rivals_record(path, "rank-one", {"uid": "396536339"}, now=100)
            update_rivals_record(path, "rank-two", {"uid": "502565567"}, now=100)
            logs: list[str] = []
            worker = RivalsPollWorker(
                path,
                mock.AsyncMock(),
                {"rate_limit_backoff_seconds": 300},
                store_lock=asyncio.Lock(),
                logger=logs.append,
            )
            worker._poll_uid = mock.AsyncMock(  # type: ignore[method-assign]
                side_effect=RivalsRateLimitError()
            )

            # cooldown_remaining, _begin_provider_cooldown, _report_error,
            # then cooldown_remaining again on the second cycle.
            with mock.patch(
                "rivals_worker.time.monotonic",
                side_effect=[100.0, 100.0, 100.0, 101.0],
            ):
                first_delay = await worker.poll_once(mock.MagicMock())
                second_delay = await worker.poll_once(mock.MagicMock())

            self.assertEqual(first_delay, 300)
            self.assertEqual(second_delay, 299)
            self.assertEqual(worker._poll_uid.await_count, 1)
            self.assertIn("updates paused for about 5 minutes", logs[0])
            self.assertEqual(rivals_status(path, "rank-one")["poll"]["status"], "error")
            self.assertEqual(rivals_status(path, "rank-two")["poll"]["status"], "error")

    async def test_persisted_cooldown_survives_worker_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "rivals.json"
            update_rivals_record(path, "rank-card", {"uid": "396536339"}, now=100)
            wall_now = int(time.time())
            save_rate_limit_state(path, wall_now + 300, 2)
            worker = RivalsPollWorker(
                path,
                mock.AsyncMock(),
                {},
                store_lock=asyncio.Lock(),
                logger=lambda _message: None,
            )
            worker._poll_uid = mock.AsyncMock()  # type: ignore[method-assign]

            with (
                mock.patch("rivals_worker.time.time", return_value=wall_now),
                mock.patch("rivals_worker.time.monotonic", return_value=100.0),
            ):
                delay = await worker.poll_once(mock.MagicMock())

            self.assertEqual(delay, 300)
            self.assertEqual(worker._rate_limit_failures, 2)
            worker._poll_uid.assert_not_awaited()
            self.assertEqual(load_rate_limit_state(path)["failures"], 2)
            self.assertEqual(
                rivals_status(path, "rank-card")["poll"]["retryAt"],
                wall_now + 300,
            )

    def test_repeated_retry_after_escalates_past_server_floor(self) -> None:
        worker = RivalsPollWorker(
            Path("unused.json"),
            mock.AsyncMock(),
            {"rate_limit_backoff_seconds": 300},
            store_lock=asyncio.Lock(),
            logger=lambda _message: None,
        )
        with (
            mock.patch("rivals_worker.time.monotonic", return_value=100.0),
            mock.patch("rivals_worker.time.time", return_value=1_000.0),
        ):
            first, _first_until = worker._begin_provider_cooldown(
                RivalsRateLimitError(60)
            )
            second, _second_until = worker._begin_provider_cooldown(
                RivalsRateLimitError(60)
            )

        self.assertEqual(first, 60)
        self.assertEqual(second, 600)

    def test_manual_refresh_obeys_cooldown_and_one_minute_debounce(self) -> None:
        worker = RivalsPollWorker(
            Path("unused.json"),
            mock.AsyncMock(),
            {},
            store_lock=asyncio.Lock(),
            logger=lambda _message: None,
        )
        with (
            mock.patch("rivals_worker.time.monotonic", return_value=100.0),
            mock.patch("rivals_worker.time.time", return_value=1_000.0),
        ):
            worker._rate_limit_until = 340.0
            worker._rate_limit_wall_until = 1_240
            paused = worker.request_manual_refresh(396536339)
            self.assertFalse(paused["accepted"])
            self.assertEqual(paused["retryAfter"], 240)
            self.assertFalse(worker._wake_event.is_set())

            worker._rate_limit_until = 0.0
            accepted = worker.request_manual_refresh(396536339)
            repeated = worker.request_manual_refresh(396536339)

        self.assertTrue(accepted["accepted"])
        self.assertFalse(repeated["accepted"])
        self.assertEqual(repeated["retryAfter"], 60)
        self.assertTrue(worker._wake_event.is_set())

    async def test_clean_cached_cycle_decrements_failure_ladder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "rivals.json"
            update_rivals_record(path, "rank-card", {"uid": "396536339"}, now=100)
            save_rate_limit_state(path, 0, 3)
            worker = RivalsPollWorker(
                path,
                mock.AsyncMock(),
                {},
                store_lock=asyncio.Lock(),
                logger=lambda _message: None,
            )

            worker._poll_uid = mock.AsyncMock(  # type: ignore[method-assign]
                return_value=None
            )
            await worker.poll_once(mock.MagicMock())

            self.assertEqual(worker._rate_limit_failures, 2)
            self.assertEqual(load_rate_limit_state(path)["failures"], 2)

    async def test_partial_fallback_cycle_does_not_decay_failure_ladder(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "rivals.json"
            update_rivals_record(path, "rank-card", {"uid": "396536339"}, now=100)
            save_rate_limit_state(path, 0, 3)
            worker = RivalsPollWorker(
                path,
                mock.AsyncMock(),
                {},
                store_lock=asyncio.Lock(),
                logger=lambda _message: None,
            )

            async def fallback_poll(*_args: object, **_kwargs: object) -> None:
                worker._successful_requests_this_cycle += 1
                worker._had_recoverable_error_this_cycle = True

            worker._poll_uid = mock.AsyncMock(  # type: ignore[method-assign]
                side_effect=fallback_poll
            )
            await worker.poll_once(mock.MagicMock())

            self.assertEqual(worker._rate_limit_failures, 3)
            self.assertEqual(load_rate_limit_state(path)["failures"], 3)

    async def test_same_uid_is_fetched_once_and_updates_both_instances(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "rivals.json"
            for instance_id in ("rank-main", "rank-corner"):
                update_rivals_record(
                    path,
                    instance_id,
                    {"uid": "396536339"},
                    now=100,
                )
            messages: list[dict[str, object]] = []

            async def broadcast(message: dict[str, object]) -> None:
                messages.append(message)

            worker = RivalsPollWorker(
                path,
                broadcast,
                {},
                store_lock=asyncio.Lock(),
                logger=lambda _message: None,
            )
            worker._fetch_uid = mock.AsyncMock(  # type: ignore[method-assign]
                return_value=(
                    "iiTzEdo",
                    17,
                    4656.718,
                    [
                        {
                            "match_uid": "shared-match",
                            "is_win": True,
                            "timestamp": 110,
                            "rank_level": 17,
                            "rank_score": 4656.718,
                            "game_mode_id": 2,
                        }
                    ],
                )
            )

            await worker.poll_once(mock.MagicMock())

            worker._fetch_uid.assert_awaited_once()
            self.assertEqual(len(messages), 2)
            for instance_id in ("rank-main", "rank-corner"):
                state = rivals_status(path, instance_id)["state"]
                self.assertEqual(state["playerName"], "iiTzEdo")
                self.assertEqual(state["sessionWins"], 1)

    async def test_five_minute_refresh_schedule_uses_eight_requests(self) -> None:
        worker = RivalsPollWorker(
            Path("unused.json"),
            mock.AsyncMock(),
            {
                "profile_refresh_seconds": 300,
                "live_refresh_seconds": 300,
            },
            store_lock=asyncio.Lock(),
            logger=lambda _message: None,
        )
        live = {
            "matches": [
                {
                    "match_uid": "ranked-match",
                    "is_win": True,
                    "timestamp": 110,
                    "rank_level": 17,
                    "rank_score": 4656.718,
                    "game_mode_id": 2,
                }
            ]
        }
        profile = {
            "name": "iiTzEdo",
            "rank_game_season": {
                "1001018": {
                    "rank_game_id": 18,
                    "level": 17,
                    "rank_score": 4656.718,
                }
            },
        }
        worker._request_json = mock.AsyncMock(  # type: ignore[method-assign]
            side_effect=[profile, live, profile, live, profile, live, profile, live]
        )

        with mock.patch(
            "rivals_worker.time.monotonic",
            side_effect=[
                0.0,
                0.0,
                120.0,
                120.0,
                300.0,
                300.0,
                600.0,
                600.0,
                900.0,
                900.0,
            ],
        ):
            await worker._fetch_uid(mock.MagicMock(), 396536339)
            await worker._fetch_uid(mock.MagicMock(), 396536339)
            await worker._fetch_uid(mock.MagicMock(), 396536339)
            await worker._fetch_uid(mock.MagicMock(), 396536339)
            await worker._fetch_uid(mock.MagicMock(), 396536339)

        endpoints = [call.args[1] for call in worker._request_json.await_args_list]
        self.assertEqual(
            endpoints,
            [PROFILE_ENDPOINT, MATCHES_REFRESH_ENDPOINT] * 4,
        )
        self.assertNotIn(MATCHES_ENDPOINT, endpoints)

    async def test_poll_failure_keeps_last_known_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "rivals.json"
            update_rivals_record(
                path,
                "rank-card",
                {"uid": "396536339", "label": "Ranked run"},
                now=100,
            )
            before = rivals_status(path, "rank-card")
            messages: list[dict[str, object]] = []
            logs: list[str] = []

            async def broadcast(message: dict[str, object]) -> None:
                messages.append(message)

            worker = RivalsPollWorker(
                path,
                broadcast,
                {},
                store_lock=asyncio.Lock(),
                logger=logs.append,
            )
            worker._request_json = mock.AsyncMock(  # type: ignore[method-assign]
                side_effect=RuntimeError("service unavailable")
            )

            await worker.poll_once(mock.MagicMock())

            after = rivals_status(path, "rank-card")
            self.assertEqual(after["state"], before["state"])
            self.assertEqual(after["linked"], before["linked"])
            self.assertEqual(messages, [])
            self.assertEqual(len(logs), 1)
            self.assertIn("last known overlay state", logs[0])
            self.assertEqual(after["poll"]["status"], "error")
            self.assertIn("service unavailable", after["poll"]["detail"])

    async def test_cached_cycle_does_not_clear_previous_poll_error(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "rivals.json"
            uid = 396536339
            update_rivals_record(path, "rank-card", {"uid": str(uid)}, now=100)
            save_rivals_poll_failures(
                path,
                [("rank-card", uid)],
                RuntimeError("live history unavailable"),
                now=110,
            )
            worker = RivalsPollWorker(
                path,
                mock.AsyncMock(),
                {},
                store_lock=asyncio.Lock(),
                logger=lambda _message: None,
            )
            worker._profile_snapshots[uid] = ("iiTzEdo", 17, 4656.718, 18)
            worker._match_snapshots[uid] = []
            worker._last_profile_refresh_at[uid] = 100.0
            worker._last_live_refresh_at[uid] = 100.0
            worker._request_json = mock.AsyncMock()  # type: ignore[method-assign]

            with mock.patch("rivals_worker.time.monotonic", return_value=150.0):
                await worker._poll_uid(
                    mock.MagicMock(),
                    uid,
                    ["rank-card"],
                )

            worker._request_json.assert_not_awaited()
            poll = rivals_status(path, "rank-card")["poll"]
            self.assertEqual(poll["status"], "error")
            self.assertEqual(poll["detail"], "live history unavailable")

    async def test_poll_uses_competitive_match_for_rank_and_session(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "rivals.json"
            update_rivals_record(
                path,
                "rank-card",
                {"uid": "396536339"},
                now=100,
            )
            messages: list[dict[str, object]] = []

            async def broadcast(message: dict[str, object]) -> None:
                messages.append(message)

            worker = RivalsPollWorker(
                path,
                broadcast,
                {},
                store_lock=asyncio.Lock(),
                logger=lambda _message: None,
            )
            worker._request_json = mock.AsyncMock(  # type: ignore[method-assign]
                side_effect=[
                    {
                        "name": "iiTzEdo",
                        "rank_game_season": {
                            "1001018": {
                                "rank_game_id": 18,
                                "rank_score": 4656.718,
                            }
                        },
                    },
                    {
                        "data": {
                            "matches": [
                                {
                                    "match_uid": "newer-quick-play",
                                    "is_win": False,
                                    "timestamp": 120,
                                    "rank_level": 1,
                                    "rank_score": 4062.55,
                                    "game_mode_id": 1,
                                    "game_play_mode_id": 100,
                                },
                                {
                                    "match_uid": "ranked-match",
                                    "is_win": True,
                                    "timestamp": 110,
                                    "season": 18,
                                    "rank_level": 17,
                                    "rank_score": 4653.152,
                                    "game_mode_id": 2,
                                    "game_play_mode_id": 200,
                                },
                            ]
                        }
                    },
                ]
            )

            await worker._poll_uid(
                mock.MagicMock(),
                396536339,
                ["rank-card"],
            )

            result = rivals_status(path, "rank-card")
            self.assertEqual(result["state"]["playerName"], "iiTzEdo")
            self.assertEqual(result["state"]["tier"], "grandmaster")
            self.assertEqual(result["state"]["division"], 2)
            self.assertEqual(result["state"]["score"], 56.72)
            self.assertEqual(result["state"]["sessionWins"], 1)
            self.assertEqual(result["state"]["sessionLosses"], 0)
            self.assertEqual(len(messages), 1)
            self.assertEqual(
                worker._request_json.await_args_list[1].args[1],
                MATCHES_REFRESH_ENDPOINT,
            )

    async def test_poll_falls_back_when_live_match_refresh_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "rivals.json"
            update_rivals_record(
                path,
                "rank-card",
                {"uid": "396536339"},
                now=100,
            )

            async def broadcast(_message: dict[str, object]) -> None:
                return None

            worker = RivalsPollWorker(
                path,
                broadcast,
                {},
                store_lock=asyncio.Lock(),
                logger=lambda _message: None,
            )
            worker._request_json = mock.AsyncMock(  # type: ignore[method-assign]
                side_effect=[
                    {
                        "name": "iiTzEdo",
                        "rank_game_season": {
                            "1001018": {
                                "rank_game_id": 18,
                                "level": 17,
                                "rank_score": 4656.718,
                            }
                        },
                    },
                    RuntimeError("live history unavailable"),
                    {
                        "matches": [
                            {
                                "match_uid": "cached-ranked-match",
                                "is_win": True,
                                "timestamp": 110,
                                "season": 18,
                                "rank_level": 17,
                                "rank_score": 4653.152,
                                "game_mode_id": 2,
                                "game_play_mode_id": 200,
                            }
                        ]
                    },
                ]
            )

            await worker._poll_uid(
                mock.MagicMock(),
                396536339,
                ["rank-card"],
            )

            result = rivals_status(path, "rank-card")
            self.assertEqual(result["state"]["tier"], "grandmaster")
            self.assertEqual(result["state"]["division"], 2)
            self.assertEqual(result["state"]["score"], 56.72)
            self.assertEqual(
                worker._request_json.await_args_list[2].args[1],
                MATCHES_ENDPOINT,
            )

    async def test_poll_keeps_current_profile_rank_pair_together(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "rivals.json"
            update_rivals_record(
                path,
                "rank-card",
                {"uid": "502565567"},
                now=100,
            )

            async def broadcast(_message: dict[str, object]) -> None:
                return None

            worker = RivalsPollWorker(
                path,
                broadcast,
                {},
                store_lock=asyncio.Lock(),
                logger=lambda _message: None,
            )
            worker._request_json = mock.AsyncMock(  # type: ignore[method-assign]
                side_effect=[
                    {
                        "name": "iiTzMag",
                        "rank_game_season": {
                            "1001018": {
                                "rank_game_id": 18,
                                "level": 13,
                                "rank_score": 4251.905999370158,
                            }
                        },
                    },
                    {
                        "matches": [
                            {
                                "match_uid": "stale-cached-rank",
                                "is_win": True,
                                "timestamp": 110,
                                "season": 18,
                                "rank_level": 12,
                                "rank_score": 4205.962459730864,
                                "game_mode_id": 2,
                                "game_play_mode_id": 200,
                            }
                        ]
                    },
                ]
            )

            await worker._poll_uid(
                mock.MagicMock(),
                502565567,
                ["rank-card"],
            )

            result = rivals_status(path, "rank-card")
            self.assertEqual(result["state"]["playerName"], "iiTzMag")
            self.assertEqual(result["state"]["tier"], "diamond")
            self.assertEqual(result["state"]["division"], 3)
            self.assertEqual(result["state"]["score"], 51.91)

    async def test_poll_uses_live_profile_score_for_one_above_all(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "rivals.json"
            update_rivals_record(
                path,
                "rank-card",
                {"uid": "465451418"},
                now=100,
            )

            async def broadcast(_message: dict[str, object]) -> None:
                return None

            worker = RivalsPollWorker(
                path,
                broadcast,
                {},
                store_lock=asyncio.Lock(),
                logger=lambda _message: None,
            )
            worker._request_json = mock.AsyncMock(  # type: ignore[method-assign]
                side_effect=[
                    {
                        "name": "Top Player",
                        "rank_game_season": {
                            "1001018": {
                                "rank_game_id": 18,
                                "level": 23,
                                "rank_score": 5193.232359915297,
                            }
                        },
                    },
                    {
                        "matches": [
                            {
                                "match_uid": "cached-ranked-match",
                                "is_win": True,
                                "timestamp": 110,
                                "season": 18,
                                "rank_level": 23,
                                "rank_score": 5176.0,
                                "game_mode_id": 2,
                                "game_play_mode_id": 200,
                            }
                        ]
                    },
                ]
            )

            await worker._poll_uid(
                mock.MagicMock(),
                465451418,
                ["rank-card"],
            )

            result = rivals_status(path, "rank-card")
            self.assertEqual(result["state"]["tier"], "one-above-all")
            self.assertEqual(result["state"]["division"], 0)
            self.assertEqual(result["state"]["score"], 123)

    async def test_outgoing_requests_carry_the_site_origin_headers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "rivals.json"
            worker = RivalsPollWorker(
                path,
                mock.AsyncMock(),
                {},
                store_lock=asyncio.Lock(),
                logger=lambda _message: None,
            )
            captured: dict[str, str] = {}

            class RecordingSession:
                def __init__(self, **kwargs: object) -> None:
                    captured.update(kwargs.get("headers") or {})

                async def __aenter__(self) -> RecordingSession:
                    raise AssertionError("stop before any network call")

                async def __aexit__(self, *_exc: object) -> bool:
                    return False

            with mock.patch("rivals_worker.ClientSession", RecordingSession):
                with self.assertRaises(AssertionError):
                    await worker._run()

            self.assertEqual(captured.get("Origin"), SITE_ORIGIN)
            self.assertEqual(captured.get("Referer"), f"{SITE_ORIGIN}/")
            self.assertEqual(captured.get("Content-Type"), "application/json")
            # The User-Agent must stay identifiable rather than imitating a
            # browser, so the provider can recognise and block this client.
            self.assertIn("Overlay-Studio", captured.get("User-Agent", ""))

    async def test_identical_errors_are_suppressed_then_relogged(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "rivals.json"
            logs: list[str] = []
            worker = RivalsPollWorker(
                path,
                mock.AsyncMock(),
                {},
                store_lock=asyncio.Lock(),
                logger=logs.append,
            )
            failure = RuntimeError("Rivals Data returned HTTP 403")

            # Once the backoff ladder saturates every message is identical, so
            # plain deduplication would hide a permanently stuck tracker.
            with mock.patch(
                "rivals_worker.time.monotonic",
                side_effect=[
                    1000.0,
                    1000.0 + ERROR_RELOG_INTERVAL_SECONDS - 1,
                    1000.0 + ERROR_RELOG_INTERVAL_SECONDS + 1,
                ],
            ):
                worker._report_error("rank-card", failure)
                worker._report_error("rank-card", failure)
                worker._report_error("rank-card", failure)

            self.assertEqual(len(logs), 2)
            self.assertNotIn("Still failing", logs[0])
            self.assertIn("Still failing", logs[1])
            self.assertIn("HTTP 403", logs[1])


if __name__ == "__main__":
    unittest.main()
