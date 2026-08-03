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
                    {"data": {"player": {"name": "iiTzEdo"}}},
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
            self.assertEqual(result["state"]["score"], 53.15)
            self.assertEqual(result["state"]["sessionWins"], 1)
            self.assertEqual(result["state"]["sessionLosses"], 0)
            self.assertEqual(len(messages), 1)


if __name__ == "__main__":
    unittest.main()
