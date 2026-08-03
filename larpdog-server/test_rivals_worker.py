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


if __name__ == "__main__":
    unittest.main()
