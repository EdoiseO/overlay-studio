from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from overlay_config import (  # noqa: E402
    add_overlay_instance,
    materialize_instance_config,
    normalize_overlay_config,
    update_instance_config,
)


class DanceProfileConfigTests(unittest.TestCase):
    def test_legacy_dance_settings_migrate_to_default_profile(self) -> None:
        config = normalize_overlay_config(
            {
                "dance": {
                    "gif": "user-assets/dancing/cat.gif",
                    "rest": "user-assets/resting/cat.png",
                },
                "audio": {"sensitivity": 1.7},
                "nowPlaying": {"fallbackBpm": 144},
            }
        )

        profile = config["dance"]["profiles"][0]
        self.assertEqual(config["dance"]["activeProfileId"], "default")
        self.assertEqual(profile["id"], "default")
        self.assertEqual(profile["gif"], "user-assets/dancing/cat.gif")
        self.assertEqual(profile["rest"], "user-assets/resting/cat.png")
        self.assertEqual(profile["sensitivity"], 1.7)
        self.assertEqual(profile["fallbackBpm"], 144)

    def test_profile_limit_and_active_values_are_enforced(self) -> None:
        profiles = [
            {
                "id": f"profile-{index}",
                "name": f"Profile {index}",
                "mode": "single",
                "gif": f"assets/{index}.gif",
                "pool": [f"assets/{index}.gif"],
                "rest": "assets/resting-dog.png",
                "position": "bottom-left",
                "scale": index,
                "sensitivity": index,
                "fallbackBpm": 20 + index,
            }
            for index in range(1, 8)
        ]

        config = normalize_overlay_config(
            {
                "dance": {
                    "activeProfileId": "profile-3",
                    "profiles": profiles,
                }
            }
        )

        self.assertEqual(len(config["dance"]["profiles"]), 5)
        self.assertEqual(config["dance"]["activeProfileId"], "profile-3")
        self.assertEqual(config["dance"]["gif"], "assets/3.gif")
        self.assertEqual(config["dance"]["scale"], 2.0)
        self.assertEqual(config["audio"]["sensitivity"], 3.0)
        self.assertEqual(config["nowPlaying"]["fallbackBpm"], 40)

    def test_profiles_round_trip_per_dance_instance(self) -> None:
        config = add_overlay_instance(
            normalize_overlay_config({}),
            "larpdog-dance",
            "dancing-cats",
            "Dancing Cats",
        )
        profiles = [
            {
                "id": "calm",
                "name": "Calm",
                "mode": "single",
                "gif": "assets/dancing-dog.gif",
                "pool": ["assets/dancing-dog.gif"],
                "rest": "assets/resting-dog.png",
                "position": "bottom-left",
                "scale": 0.8,
                "sensitivity": 0.7,
                "fallbackBpm": 90,
            },
            {
                "id": "party",
                "name": "Party",
                "mode": "random",
                "gif": "user-assets/dancing/a.gif",
                "pool": [
                    "user-assets/dancing/a.gif",
                    "user-assets/dancing/b.gif",
                ],
                "rest": "user-assets/resting/cat.png",
                "position": "bottom-left",
                "scale": 1.4,
                "sensitivity": 2.1,
                "fallbackBpm": 150,
            },
        ]

        updated = update_instance_config(
            config,
            "dancing-cats",
            {
                "dance": {
                    "name": "Dancing Cats",
                    "activeProfileId": "party",
                    "profiles": profiles,
                },
                "audio": {"enabled": True, "sensitivity": 2.1},
                "nowPlaying": {"fallbackBpm": 150},
            },
        )
        instance = materialize_instance_config(updated, "dancing-cats")

        self.assertEqual(instance["dance"]["activeProfileId"], "party")
        self.assertEqual(len(instance["dance"]["profiles"]), 2)
        self.assertEqual(
            instance["dance"]["pool"],
            [
                "user-assets/dancing/a.gif",
                "user-assets/dancing/b.gif",
            ],
        )
        self.assertEqual(instance["audio"]["sensitivity"], 2.1)
        self.assertEqual(instance["nowPlaying"]["fallbackBpm"], 150)


if __name__ == "__main__":
    unittest.main()
