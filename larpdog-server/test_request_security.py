from __future__ import annotations

import sys
import unittest
from pathlib import Path

from aiohttp import web
from aiohttp.test_utils import make_mocked_request


sys.path.insert(0, str(Path(__file__).resolve().parent))

from main import require_local_json_write  # noqa: E402


def make_write_request(
    *,
    content_type: str = "application/json",
    host: str = "127.0.0.1:8473",
    origin: str | None = None,
    referer: str | None = None,
) -> web.Request:
    headers = {
        "Content-Type": content_type,
        "Host": host,
    }
    if origin is not None:
        headers["Origin"] = origin
    if referer is not None:
        headers["Referer"] = referer
    return make_mocked_request("POST", "/api/config", headers=headers)


class LocalJsonWriteTests(unittest.TestCase):
    def test_accepts_json_from_non_browser_clients(self) -> None:
        require_local_json_write(make_write_request())

    def test_accepts_same_origin_loopback_browser_request(self) -> None:
        require_local_json_write(
            make_write_request(origin="http://127.0.0.1:8473")
        )

    def test_accepts_same_origin_localhost_referer(self) -> None:
        require_local_json_write(
            make_write_request(
                host="localhost:8473",
                referer="http://localhost:8473/studio/settings",
            )
        )

    def test_rejects_simple_text_plain_request(self) -> None:
        with self.assertRaises(web.HTTPUnsupportedMediaType):
            require_local_json_write(
                make_write_request(
                    content_type="text/plain",
                    origin="https://attacker.example",
                )
            )

    def test_rejects_non_loopback_host(self) -> None:
        with self.assertRaises(web.HTTPForbidden):
            require_local_json_write(make_write_request(host="attacker.example"))

    def test_rejects_remote_origin(self) -> None:
        with self.assertRaises(web.HTTPForbidden):
            require_local_json_write(
                make_write_request(origin="https://attacker.example")
            )

    def test_rejects_mismatched_loopback_origin(self) -> None:
        with self.assertRaises(web.HTTPForbidden):
            require_local_json_write(
                make_write_request(origin="http://127.0.0.1:9000")
            )

    def test_rejects_null_origin(self) -> None:
        with self.assertRaises(web.HTTPForbidden):
            require_local_json_write(make_write_request(origin="null"))


if __name__ == "__main__":
    unittest.main()
