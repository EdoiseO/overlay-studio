from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

from overlay_config import (  # noqa: E402
    add_overlay_instance,
    load_overlay_config,
    materialize_instance_config,
    normalize_overlay_config,
    reorder_overlay_instances,
    save_overlay_config,
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


class PlatformBadgeConfigTests(unittest.TestCase):
    def test_platform_badge_defaults_are_materialized(self) -> None:
        config = normalize_overlay_config({})

        self.assertEqual(
            config["platformBadge"],
            {
                "platform": "twitch",
                "handle": "yourname",
                "prefix": "",
                "useBrandColor": True,
                "badgeColor": "9146ff",
                "corners": 4,
                "width": 340,
                "height": 96,
                "scale": 1.0,
                "font": "display",
                "weight": 700,
            },
        )

    def test_platform_badge_round_trips_and_clamps_instance_settings(self) -> None:
        config = add_overlay_instance(
            normalize_overlay_config({}),
            "platform-badge",
            "platform-badge-main",
            "Platform Badge",
        )

        updated = update_instance_config(
            config,
            "platform-badge-main",
            {
                "platformBadge": {
                    "platform": "snapchat",
                    "handle": "  creator   name  ",
                    "prefix": "  @  ",
                    "useBrandColor": "false",
                    "badgeColor": "#ABCDEF",
                    "corners": 99,
                    "width": 999,
                    "height": 10,
                    "scale": 0.1,
                    "font": "poppins",
                    "weight": 1200,
                }
            },
        )
        badge = materialize_instance_config(
            normalize_overlay_config(updated),
            "platform-badge-main",
        )["platformBadge"]

        self.assertEqual(badge["platform"], "snapchat")
        self.assertEqual(badge["handle"], "creator name")
        self.assertEqual(badge["prefix"], "@")
        self.assertFalse(badge["useBrandColor"])
        self.assertEqual(badge["badgeColor"], "abcdef")
        self.assertEqual(badge["corners"], 24)
        self.assertEqual(badge["width"], 720)
        self.assertEqual(badge["height"], 48)
        self.assertEqual(badge["scale"], 0.5)
        self.assertEqual(badge["font"], "poppins")
        self.assertEqual(badge["weight"], 900)

    def test_platform_badge_rejects_unknown_choices_and_bad_color(self) -> None:
        badge = normalize_overlay_config(
            {
                "platformBadge": {
                    "platform": "unknown",
                    "font": "comic-sans",
                    "badgeColor": "not-a-color",
                }
            }
        )["platformBadge"]

        self.assertEqual(badge["platform"], "twitch")
        self.assertEqual(badge["font"], "display")
        self.assertEqual(badge["badgeColor"], "9146ff")


class MinecraftSpotifyConfigTests(unittest.TestCase):
    def test_minecraft_spotify_settings_round_trip_without_touching_spotify(self) -> None:
        config = add_overlay_instance(
            normalize_overlay_config({}),
            "minecraft-spotify",
            "minecraft-spotify-main",
            "Minecraft Spotify",
        )
        original_spotify = materialize_instance_config(
            config,
            "spotify-overlay",
        )["spotify"]

        updated = update_instance_config(
            config,
            "minecraft-spotify-main",
            {
                "minecraftSpotify": {
                    "scale": 1.35,
                    "cardSize": 404,
                    "accentColor": "#55AA33",
                    "shellColor": "101820",
                    "textColor": "F8F4E8",
                    "pixelShadow": 0.65,
                },
                "spotify": {
                    "cardWidth": 600,
                    "colorMode": "fixed",
                },
            },
        )
        materialized = materialize_instance_config(
            normalize_overlay_config(updated),
            "minecraft-spotify-main",
        )

        self.assertEqual(
            materialized["minecraftSpotify"],
            {
                "scale": 1.35,
                "cardSize": 404,
                "accentColor": "55aa33",
                "shellColor": "101820",
                "textColor": "f8f4e8",
                "pixelShadow": 0.65,
            },
        )
        self.assertEqual(materialized["spotify"], original_spotify)
        self.assertEqual(
            updated["instances"]["minecraft-spotify-main"]["config"].keys(),
            {"minecraftSpotify"},
        )

    def test_minecraft_spotify_settings_are_bounded_and_validated(self) -> None:
        config = add_overlay_instance(
            normalize_overlay_config({}),
            "minecraft-spotify",
            "minecraft-spotify-main",
            "Minecraft Spotify",
        )
        updated = update_instance_config(
            config,
            "minecraft-spotify-main",
            {
                "minecraftSpotify": {
                    "scale": 99,
                    "cardSize": 10,
                    "accentColor": "invalid",
                    "pixelShadow": -4,
                }
            },
        )
        settings = materialize_instance_config(
            updated,
            "minecraft-spotify-main",
        )["minecraftSpotify"]

        self.assertEqual(settings["scale"], 2.0)
        self.assertEqual(settings["cardSize"], 320)
        self.assertEqual(settings["accentColor"], "70b237")
        self.assertEqual(settings["pixelShadow"], 0.0)


class SocialOverlayConfigTests(unittest.TestCase):
    def test_social_bar_limits_platforms_and_normalizes_fields(self) -> None:
        config = add_overlay_instance(
            normalize_overlay_config({}),
            "social",
            "social-main",
            "Main Socials",
        )
        accounts = [
            {
                "platform": platform,
                "enabled": True,
                "handle": f"@{'x' * 80}{index}",
            }
            for index, platform in enumerate(
                [
                    "twitch",
                    "youtube",
                    "instagram",
                    "x",
                    "twitter",
                    "tiktok",
                    "discord",
                    "kick",
                    "facebook",
                    "reddit",
                ]
            )
        ]
        accounts.append(
            {"platform": "not-a-platform", "enabled": True, "handle": "bad"}
        )

        updated = update_instance_config(
            config,
            "social-main",
            {
                "social": {
                    "accounts": accounts,
                    "layout": "fused",
                    "iconShape": "hex",
                    "iconBackground": False,
                    "outline": 99,
                    "scale": 0.1,
                }
            },
        )
        social = materialize_instance_config(updated, "social-main")["social"]
        enabled = [item for item in social["accounts"] if item["enabled"]]

        self.assertEqual(len(social["accounts"]), 16)
        self.assertEqual(len(enabled), 8)
        self.assertEqual([item["platform"] for item in enabled][-1], "kick")
        self.assertNotIn("not-a-platform", [item["platform"] for item in social["accounts"]])
        self.assertEqual(len(social["accounts"][0]["handle"]), 64)
        self.assertFalse(social["accounts"][0]["handle"].startswith("@"))
        self.assertEqual(social["layout"], "fused")
        self.assertEqual(social["iconShape"], "hex")
        self.assertFalse(social["iconBackground"])
        self.assertEqual(social["outline"], 8)
        self.assertEqual(social["scale"], 0.5)

    def test_social_rotator_limits_platforms_and_bounds_timing(self) -> None:
        config = add_overlay_instance(
            normalize_overlay_config({}),
            "social-rotator",
            "rotating-socials",
            "Rotating Socials",
        )
        accounts = [
            {"platform": platform, "enabled": True, "handle": platform}
            for platform in (
                "twitch",
                "youtube",
                "instagram",
                "x",
                "twitter",
                "tiktok",
                "discord",
                "kick",
                "facebook",
                "snapchat",
                "telegram",
                "whatsapp",
                "linkedin",
                "threads",
                "bluesky",
                "reddit",
            )
        ]

        updated = update_instance_config(
            config,
            "rotating-socials",
            {
                "social": {
                    "accounts": accounts,
                    "cycle": 100,
                    "weight": 1200,
                    "scale": 4,
                    "prefix": "",
                    "rotatorShape": "cut",
                    "transition": "flip",
                }
            },
        )
        social = materialize_instance_config(
            updated,
            "rotating-socials",
        )["social"]

        self.assertEqual(
            len([item for item in social["accounts"] if item["enabled"]]),
            12,
        )
        self.assertEqual(
            [item["platform"] for item in social["accounts"] if item["enabled"]][
                -1
            ],
            "whatsapp",
        )
        self.assertEqual(social["cycle"], 30.0)
        self.assertEqual(social["weight"], 900)
        self.assertEqual(social["scale"], 2.0)
        self.assertEqual(social["prefix"], "")
        self.assertEqual(social["rotatorShape"], "cut")
        self.assertEqual(social["transition"], "flip")

    def test_social_instances_keep_independent_accounts(self) -> None:
        config = normalize_overlay_config({})
        config = add_overlay_instance(
            config,
            "social",
            "social-one",
            "Social One",
        )
        config = add_overlay_instance(
            config,
            "social",
            "social-two",
            "Social Two",
        )
        config = update_instance_config(
            config,
            "social-one",
            {
                "social": {
                    "accounts": [
                        {
                            "platform": "reddit",
                            "enabled": True,
                            "handle": "first",
                        }
                    ]
                }
            },
        )

        first = materialize_instance_config(config, "social-one")["social"]
        second = materialize_instance_config(config, "social-two")["social"]

        self.assertEqual(
            [item["platform"] for item in first["accounts"] if item["enabled"]],
            ["reddit"],
        )
        self.assertEqual(
            [item["platform"] for item in second["accounts"] if item["enabled"]],
            ["twitch", "youtube", "instagram", "tiktok"],
        )

    def test_social_grouped_settings_round_trip_per_instance(self) -> None:
        config = add_overlay_instance(
            normalize_overlay_config({}),
            "social-grouped",
            "grouped-main",
            "Grouped Socials",
        )

        updated = update_instance_config(
            config,
            "grouped-main",
            {
                "socialGrouped": {
                    "groups": (
                        "twitch+youtube:First Name,invalid:ignored,"
                        "tiktok|instagram:second"
                    ),
                    "groupGap": -99,
                    "separate": True,
                    "logoOutline": 99,
                    "textOutline": 4.25,
                    "textGap": -99,
                    "textSide": "left",
                    "textCase": "upper",
                    "join": "miter",
                    "outlineOpacity": 2,
                    "shadow": False,
                    "preset": "custom",
                }
            },
        )
        restarted = normalize_overlay_config(updated)
        grouped = materialize_instance_config(
            restarted,
            "grouped-main",
        )["socialGrouped"]

        self.assertEqual(
            grouped["groups"],
            "twitch+youtube:First Name,tiktok+instagram:second",
        )
        self.assertEqual(grouped["groupGap"], -20)
        self.assertTrue(grouped["separate"])
        self.assertEqual(grouped["logoOutline"], 10)
        self.assertEqual(grouped["textOutline"], 4.25)
        self.assertEqual(grouped["textGap"], -14)
        self.assertEqual(grouped["textSide"], "left")
        self.assertEqual(grouped["textCase"], "upper")
        self.assertEqual(grouped["join"], "miter")
        self.assertEqual(grouped["outlineOpacity"], 1)
        self.assertFalse(grouped["shadow"])


class OverlayOrderConfigTests(unittest.TestCase):
    def setUp(self) -> None:
        config = normalize_overlay_config({"instances": {}})
        for instance_id, overlay_type, name in (
            ("dance-one", "larpdog-dance", "Dance One"),
            ("social-one", "social", "Social One"),
            ("goal-one", "goal", "Goal One"),
        ):
            config = add_overlay_instance(
                config,
                overlay_type,
                instance_id,
                name,
            )
        self.config = config

    def test_reorders_instances_without_changing_their_values(self) -> None:
        reordered = reorder_overlay_instances(
            self.config,
            ["goal-one", "dance-one", "social-one"],
        )

        self.assertEqual(
            list(reordered["instances"]),
            ["goal-one", "dance-one", "social-one"],
        )
        self.assertEqual(
            reordered["instances"]["dance-one"],
            self.config["instances"]["dance-one"],
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "overlay-config.json"
            save_overlay_config(path, reordered)
            self.assertEqual(
                list(load_overlay_config(path)["instances"]),
                ["goal-one", "dance-one", "social-one"],
            )

    def test_rejects_partial_duplicate_or_unknown_orders(self) -> None:
        invalid_orders = (
            ["dance-one", "social-one"],
            ["dance-one", "dance-one", "goal-one"],
            ["dance-one", "social-one", "missing"],
            "dance-one,social-one,goal-one",
        )
        for order in invalid_orders:
            with self.subTest(order=order):
                with self.assertRaisesRegex(ValueError, "[Oo]verlay order"):
                    reorder_overlay_instances(self.config, order)


if __name__ == "__main__":
    unittest.main()
