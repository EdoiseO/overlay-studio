from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


sys.path.insert(0, str(Path(__file__).resolve().parent))

from rivals_store import (  # noqa: E402
    DEFAULT_RIVALS_STATE,
    MAX_SEEN_MATCHES,
    apply_rivals_poll,
    is_competitive_match,
    load_rivals_record,
    load_rivals_document,
    load_rivals_studio_state,
    load_rate_limit_state,
    normalize_rivals_state,
    parse_player_uid,
    rank_progress_score,
    rank_from_level,
    remove_rivals_instance,
    rivals_status,
    reserve_rivals_request,
    save_rate_limit_state,
    save_rivals_poll,
    save_rivals_poll_failures,
    update_rivals_record,
)


class RivalsStoreTests(unittest.TestCase):
    def test_maps_all_23_rank_levels(self) -> None:
        expected = [
            ("bronze", 3),
            ("bronze", 2),
            ("bronze", 1),
            ("silver", 3),
            ("silver", 2),
            ("silver", 1),
            ("gold", 3),
            ("gold", 2),
            ("gold", 1),
            ("platinum", 3),
            ("platinum", 2),
            ("platinum", 1),
            ("diamond", 3),
            ("diamond", 2),
            ("diamond", 1),
            ("grandmaster", 3),
            ("grandmaster", 2),
            ("grandmaster", 1),
            ("celestial", 3),
            ("celestial", 2),
            ("celestial", 1),
            ("eternity", 0),
            ("one-above-all", 0),
        ]
        self.assertEqual(
            [rank_from_level(level) for level in range(1, 24)],
            expected,
        )

    def test_identifies_competitive_matches_and_normalizes_rank_score(self) -> None:
        self.assertTrue(is_competitive_match({"game_mode_id": 2}))
        self.assertTrue(is_competitive_match({"game_play_mode_id": "200"}))
        self.assertTrue(is_competitive_match({"match_uid": "legacy-shape"}))
        self.assertFalse(
            is_competitive_match(
                {"game_mode_id": 1, "game_play_mode_id": 100}
            )
        )
        self.assertEqual(rank_progress_score(4653.152, 17), 53.15)
        self.assertEqual(rank_progress_score(5129.99, 22), 59)
        self.assertEqual(rank_progress_score(5193.232359915297, 23), 123)
        self.assertEqual(rank_progress_score(56, 17), 56)

    def test_parses_only_numeric_ids_and_rivals_data_profile_urls(self) -> None:
        self.assertEqual(parse_player_uid("396536339"), 396536339)
        self.assertEqual(
            parse_player_uid("https://rivalsdata.com/player/396536339"),
            396536339,
        )
        self.assertEqual(
            parse_player_uid("https://www.rivalsdata.com/player/396536339/"),
            396536339,
        )
        for invalid in (
            "",
            "https://attacker.example/player/396536339",
            "https://rivalsdata.com/leaderboard/396536339",
            "javascript:alert(1)",
            True,
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValueError):
                    parse_player_uid(invalid)

    def test_normalizes_untrusted_public_state(self) -> None:
        state = normalize_rivals_state(
            {
                "playerName": "  A   player  ",
                "tier": "unknown",
                "division": 99,
                "score": float("inf"),
                "sessionWins": -2,
                "sessionLosses": 5000,
                "label": "A very long custom session label that is clipped",
                "showName": "off",
                "shellColor": "#ABCDEF",
                "textColor": "nope",
                "font": "comic-sans",
                "weight": 744,
                "scale": 8,
                "corners": -5,
                "glow": 9,
            }
        )
        self.assertEqual(state["playerName"], "A player")
        self.assertEqual(state["tier"], "bronze")
        self.assertEqual(state["division"], 3)
        self.assertEqual(state["score"], 0)
        self.assertEqual(state["sessionWins"], 0)
        self.assertEqual(state["sessionLosses"], 999)
        self.assertEqual(len(state["label"]), 24)
        self.assertFalse(state["showName"])
        self.assertEqual(state["shellColor"], "abcdef")
        self.assertEqual(state["textColor"], DEFAULT_RIVALS_STATE["textColor"])
        self.assertEqual(state["font"], "display")
        self.assertEqual(state["weight"], 700)
        self.assertEqual(state["scale"], 1.6)
        self.assertEqual(state["corners"], 0)
        self.assertEqual(state["glow"], 2.5)

    def test_baselines_then_counts_only_new_matches(self) -> None:
        record = {
            "state": DEFAULT_RIVALS_STATE,
            "private": {
                "uid": 396536339,
                "sessionStartedAt": 100,
            },
        }
        baseline = apply_rivals_poll(
            record,
            player_name="iiTzEdo",
            matches=[
                {
                    "match_uid": "match-2",
                    "is_win": False,
                    "timestamp": 95,
                    "rank_level": 17,
                    "rank_score": 53.25,
                },
                {
                    "match_uid": "match-1",
                    "is_win": True,
                    "timestamp": 90,
                    "rank_level": 16,
                    "rank_score": 40,
                },
            ],
            now=125,
        )
        self.assertEqual(baseline["state"]["playerName"], "iiTzEdo")
        self.assertEqual(baseline["state"]["tier"], "grandmaster")
        self.assertEqual(baseline["state"]["division"], 2)
        self.assertEqual(baseline["state"]["score"], 53.25)
        self.assertEqual(baseline["state"]["sessionWins"], 0)
        self.assertEqual(baseline["state"]["sessionLosses"], 0)

        updated = apply_rivals_poll(
            baseline,
            matches=[
                {
                    "match_uid": "match-4",
                    "is_win": False,
                    "timestamp": 140,
                    "rank_level": 18,
                    "rank_score": 72,
                },
                {
                    "match_uid": "match-3",
                    "is_win": True,
                    "timestamp": 130,
                    "rank_level": 17,
                    "rank_score": 61,
                },
                {
                    "match_uid": "match-2",
                    "is_win": False,
                    "timestamp": 95,
                    "rank_level": 17,
                    "rank_score": 53.25,
                },
            ],
            now=145,
        )
        self.assertEqual(updated["state"]["sessionWins"], 1)
        self.assertEqual(updated["state"]["sessionLosses"], 1)
        self.assertEqual(updated["state"]["division"], 1)
        self.assertEqual(updated["state"]["score"], 72)

    def test_current_profile_rank_pair_beats_stale_cached_match(self) -> None:
        record = {
            "state": DEFAULT_RIVALS_STATE,
            "private": {"uid": 502565567, "sessionStartedAt": 100},
        }
        updated = apply_rivals_poll(
            record,
            player_name="iiTzMag",
            rank_level=13,
            rank_score=4251.905999370158,
            matches=[
                {
                    "match_uid": "stale-cached-rank",
                    "is_win": True,
                    "timestamp": 110,
                    "rank_level": 12,
                    "rank_score": 4205.962459730864,
                }
            ],
            now=115,
        )

        self.assertEqual(updated["state"]["tier"], "diamond")
        self.assertEqual(updated["state"]["division"], 3)
        self.assertEqual(updated["state"]["score"], 51.91)

    def test_document_level_protection_state_upgrades_and_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "rivals.json"
            path.write_text('{"instances":{}}', encoding="utf-8")

            self.assertEqual(
                load_rate_limit_state(path),
                {"until": 0, "failures": 0},
            )
            saved = save_rate_limit_state(path, 1_900_000_000, 3)

            self.assertEqual(saved, {"until": 1_900_000_000, "failures": 3})
            self.assertEqual(load_rate_limit_state(path), saved)

    def test_document_cache_returns_independent_normalized_copies(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "rivals.json"
            save_rate_limit_state(path, 1_900_000_000, 2)

            first = load_rivals_document(path)
            first["rateLimit"]["failures"] = 0
            second = load_rivals_document(path)

            self.assertEqual(second["rateLimit"]["failures"], 2)

    def test_request_budget_is_persisted_as_a_rolling_window(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "rivals.json"

            for timestamp in (100, 101, 102):
                allowed, retry_after, count = reserve_rivals_request(
                    path,
                    3,
                    now=timestamp,
                )
                self.assertTrue(allowed)
                self.assertEqual(retry_after, 0)
                self.assertEqual(count, timestamp - 99)

            allowed, retry_after, count = reserve_rivals_request(
                path,
                3,
                now=103,
            )
            self.assertFalse(allowed)
            self.assertEqual(retry_after, 3597)
            self.assertEqual(count, 3)

            allowed, _retry_after, count = reserve_rivals_request(
                path,
                3,
                now=3700,
            )
            self.assertTrue(allowed)
            self.assertEqual(count, 3)

    def test_seen_match_history_retains_multiple_full_api_windows(self) -> None:
        self.assertGreaterEqual(MAX_SEEN_MATCHES, 256)
        record = {
            "state": DEFAULT_RIVALS_STATE,
            "private": {"uid": 396536339, "sessionStartedAt": 100},
        }
        historical = [
            {
                "match_uid": f"historical-{index}",
                "is_win": True,
                "timestamp": 90,
            }
            for index in range(64)
        ]
        baseline = apply_rivals_poll(record, matches=historical, now=105)
        current = [
            {
                "match_uid": f"current-{index}",
                "is_win": True,
                "timestamp": 110,
            }
            for index in range(64)
        ]
        updated = apply_rivals_poll(baseline, matches=current, now=115)
        replayed = apply_rivals_poll(updated, matches=historical, now=120)

        self.assertEqual(updated["state"]["sessionWins"], 64)
        self.assertEqual(replayed["state"]["sessionWins"], 64)
        self.assertEqual(len(replayed["private"]["seenMatchUids"]), 128)

    def test_provider_failure_updates_all_instances_with_one_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "rivals.json"
            linked = []
            for index, uid in enumerate((396536339, 502565567, 465451418)):
                instance_id = f"rank-{index}"
                update_rivals_record(
                    path,
                    instance_id,
                    {"uid": str(uid)},
                    now=100,
                )
                linked.append((instance_id, uid))

            import rivals_store

            writer = rivals_store._write_rivals_document
            with mock.patch(
                "rivals_store._write_rivals_document",
                wraps=writer,
            ) as write:
                changed = save_rivals_poll_failures(
                    path,
                    linked,
                    RuntimeError("provider paused"),
                    rate_limit_until=1_900_000_000,
                    rate_limit_failures=2,
                    now=200,
                )

            self.assertEqual(changed, ["rank-0", "rank-1", "rank-2"])
            self.assertEqual(write.call_count, 1)

    def test_link_reset_poll_and_remove_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "rivals.json"
            linked = update_rivals_record(
                path,
                "rank-card",
                {
                    "uid": "https://rivalsdata.com/player/396536339",
                    "label": "Ranked run",
                },
                now=100,
            )
            self.assertTrue(linked["linked"])
            self.assertEqual(linked["poll"]["status"], "waiting")
            self.assertNotIn("uid", linked["state"])

            state, changed = save_rivals_poll(
                path,
                "rank-card",
                396536339,
                player_name="iiTzEdo",
                matches=[
                    {
                        "match_uid": "first",
                        "is_win": True,
                        "timestamp": 110,
                        "rank_level": 17,
                        "rank_score": 56,
                    }
                ],
                now=115,
            )
            self.assertTrue(changed)
            self.assertEqual(state["playerName"], "iiTzEdo")
            self.assertEqual(state["sessionWins"], 1)
            self.assertEqual(
                rivals_status(path, "rank-card")["poll"]["status"],
                "ok",
            )

            reset = update_rivals_record(
                path,
                "rank-card",
                {"action": "reset-session"},
                now=200,
            )
            self.assertEqual(reset["state"]["sessionWins"], 0)
            self.assertEqual(reset["state"]["tier"], "grandmaster")
            self.assertEqual(
                load_rivals_record(path, "rank-card")["private"]["sessionStartedAt"],
                200,
            )

            serialized_public = json.dumps(rivals_status(path, "rank-card"))
            self.assertNotIn("396536339", serialized_public)
            self.assertNotIn("uid", serialized_public.lower())
            self.assertEqual(
                load_rivals_studio_state(path, ["rank-card"])["linked"],
                {"rank-card": True},
            )
            remove_rivals_instance(path, "rank-card")
            self.assertFalse(rivals_status(path, "rank-card")["linked"])


if __name__ == "__main__":
    unittest.main()
