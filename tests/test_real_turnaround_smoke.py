"""Live Blender regression: same demo mesh from three true camera azimuths."""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.render_turnaround_blender import render_turnaround
from tools.turnaround_gate import capture, verify, TurnaroundError
from tools.turnaround_review_card import render_review_card


class RealTurnaroundSmoke(unittest.TestCase):
    def test_three_cameras_and_unapproved_reference(self):
        blender = os.environ.get("BLENDER_BIN", "blender")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = render_turnaround(blender, root / "views", demo=True,
                                       front_yaw=0, timeout=480)
            report = json.loads((folder / "TURNAROUND_BLENDER_REPORT.json").read_text())
            self.assertTrue(report["demo"])
            self.assertEqual(report["projection"], "orthographic")
            self.assertFalse(report["reviewed"])
            self.assertTrue(report["requires_manual_review"])
            self.assertEqual(set(report["view_sha256"]), {"front", "side", "back"})
            sheet = capture(
                *(folder / (v + ".png") for v in ("front", "side", "back")),
                reference_url="https://example.com/original-synthetic-geometry",
                artist="DyberPet geometry fixture", variant="test-only")
            self.assertEqual(sheet["review"], {})
            with self.assertRaisesRegex(TurnaroundError, "approval"):
                verify(sheet)
            card = render_review_card("synthetic_3view", sheet, root / "cards")
            self.assertTrue(Path(card["review_card"]).is_file())
            dst = os.environ.get("BLENDER_TURNAROUND_ARTIFACT_DIR")
            if dst:
                target = Path(dst)
                target.mkdir(parents=True, exist_ok=True)
                for v in ("front", "side", "back"):
                    shutil.copy2(folder / (v + ".png"), target / (v + ".png"))
                shutil.copy2(folder / "TURNAROUND_BLENDER_REPORT.json", target)
                shutil.copy2(card["review_card"], target / "REVIEW_CARD.png")


if __name__ == "__main__":
    unittest.main()
