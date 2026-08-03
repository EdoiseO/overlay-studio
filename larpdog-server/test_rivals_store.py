from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from rivals_store import (  # noqa: E402
    DEFAULT_RIVALS_STATE,
    apply_rivals_poll,
    load_rivals_record,
    normalize_rivals_state,
    parse_player_uid,
    rank_from_level,
    remove_rivals_instance,
    rivals_status,
    save_rivals_poll,
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
                    "timestamp": 120,
                    "rank_level": 17,
                    "rank_score": 53.25,
                },
                {
                    "match_uid": "match-1",
                    "is_win": True,
                    "timestamp": 110,
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
                    "timestamp": 120,
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
            remove_rivals_instance(path, "rank-card")
            self.assertFalse(rivals_status(path, "rank-card")["linked"])


if __name__ == "__main__":
    unittest.main()
