from __future__ import annotations

import asyncio
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parent))

from rivals_store import rivals_status, update_rivals_record  # noqa: E402
from rivals_worker import (  # noqa: E402
    MATCHES_ENDPOINT,
    MATCHES_REFRESH_ENDPOINT,
    RivalsPollWorker,
    extract_matches,
    extract_profile_snapshot,
)


class RivalsWorkerTests(unittest.IsolatedAsyncioTestCase):
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

    def test_live_match_refresh_is_rate_limited_per_instance(self) -> None:
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
            self.assertTrue(worker._should_refresh_live_matches("rank-card"))
            self.assertFalse(worker._should_refresh_live_matches("rank-card"))
            self.assertTrue(worker._should_refresh_live_matches("rank-card"))

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

            await worker._poll_instance(mock.MagicMock(), "rank-card", 396536339)

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

            await worker._poll_instance(mock.MagicMock(), "rank-card", 396536339)

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

            await worker._poll_instance(mock.MagicMock(), "rank-card", 502565567)

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

            await worker._poll_instance(mock.MagicMock(), "rank-card", 465451418)

            result = rivals_status(path, "rank-card")
            self.assertEqual(result["state"]["tier"], "one-above-all")
            self.assertEqual(result["state"]["division"], 0)
            self.assertEqual(result["state"]["score"], 123)


if __name__ == "__main__":
    unittest.main()
