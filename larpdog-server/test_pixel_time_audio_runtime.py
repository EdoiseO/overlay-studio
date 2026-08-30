from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")


@unittest.skipUnless(NODE, "Node.js is required for the Web Audio runtime test")
class PixelTimeAudioRuntimeTests(unittest.TestCase):
    def test_chime_reports_only_real_playback_and_releases_outputs(self) -> None:
        completed = subprocess.run(
            [NODE, str(Path(__file__).with_suffix(".mjs"))],
            cwd=ROOT_DIR,
            capture_output=True,
            check=False,
            text=True,
            timeout=10,
        )
        self.assertEqual(
            completed.returncode,
            0,
            f"{completed.stdout}\n{completed.stderr}".strip(),
        )


if __name__ == "__main__":
    unittest.main()
