"""Headless Qt smoke for true sprite actions in the original-art review dialog."""
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtWidgets import QApplication

from DyberPet.DyberSettings.native_frame_preview import NativeFramePreviewDialog


def role(root, name, actions):
    p = root / name
    (p / "action").mkdir(parents=True)
    (p / "pet_conf.json").write_text("{}", encoding="utf-8")
    conf = {}
    for title in actions:
        conf[title] = {"images": title}
        for frame in range(2):
            Image.new("RGBA", (32, 32), (80 + frame * 25, 90, 200, 255)).save(
                p / "action" / f"{title}_{frame}.png")
    (p / "act_conf.json").write_text(json.dumps(conf), encoding="utf-8")
    return p


class NativeInteractionPreviewShortcutTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_only_real_current_version_actions_enabled(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            role(root, "CreatorA", ["wave", "jump"])
            role(root, "CreatorB", ["rest"])
            dialog = NativeFramePreviewDialog(root, ["CreatorA", "CreatorB"])
            try:
                self.assertTrue(dialog.interaction_buttons["greet"].isEnabled())
                self.assertTrue(dialog.interaction_buttons["jump"].isEnabled())
                self.assertFalse(dialog.interaction_buttons["sleep"].isEnabled())
                self.assertIn("2 / 12", dialog.interaction_summary.text())
                dialog._preview_interaction("greet")
                self.assertEqual(dialog.action.currentData(), "wave")
                dialog._clock.stop()
                dialog.version.setCurrentIndex(1)
                self.assertFalse(dialog.interaction_buttons["greet"].isEnabled())
                self.assertTrue(dialog.interaction_buttons["rest"].isEnabled())
                self.assertIn("1 / 12", dialog.interaction_summary.text())
                before = dialog.action.currentData()
                dialog._preview_interaction("jump")
                self.assertEqual(dialog.action.currentData(), before)
                dialog._preview_interaction("rest")
                self.assertEqual(dialog.action.currentData(), "rest")
            finally:
                dialog._clock.stop()
                dialog.close()

    def test_corrupted_version_disables_all_real_interactions(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            broken = root / "Broken"
            (broken / "action").mkdir(parents=True)
            (broken / "pet_conf.json").write_text("{}", encoding="utf-8")
            (broken / "act_conf.json").write_text(
                json.dumps({"wave": {"images": "wave"}}), encoding="utf-8")
            dialog = NativeFramePreviewDialog(root, ["Broken"])
            try:
                self.assertTrue(all(
                    not b.isEnabled() for b in dialog.interaction_buttons.values()))
                self.assertIn("0 / 12", dialog.interaction_summary.text())
                self.assertFalse(dialog.play.isEnabled())
            finally:
                dialog.close()


if __name__ == "__main__":
    unittest.main()
