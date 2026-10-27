"""R20: do not advertise actions with a corrupt/missing later original frame."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from tools.character_interaction_coverage import (
    _action_inventory, rank_installed_role_variants)


def make_role(root, name, groups):
    folder = root / name
    art = folder / "action"
    art.mkdir(parents=True)
    config = {}
    for action, frame_count in groups.items():
        config[action] = {"images": action}
        for i in range(frame_count):
            Image.new("RGBA", (16, 16), (i * 35 + 80, 60, 220, 255)).save(
                art / f"{action}_{i}.png")
    (folder / "act_conf.json").write_text(
        json.dumps(config), encoding="utf-8")
    return folder


class CompleteOriginalFrameGates(unittest.TestCase):
    def test_corrupt_second_png_disables_only_its_action(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            role = make_role(root, "Candidate", {"wave": 3, "rest": 1})
            self.assertEqual(_action_inventory(root, "Candidate")[0],
                             ["wave", "rest"])
            (role / "action" / "wave_2.png").write_bytes(
                b"not actually a valid final PNG" * 4)
            usable, broken = _action_inventory(root, "Candidate")
            self.assertEqual(usable, ["rest"])
            self.assertEqual(broken, ["wave"])
            ranked = rank_installed_role_variants(root, ["Candidate"])
            self.assertNotIn("greet", ranked[0]["interaction_categories"])
            self.assertIn("rest", ranked[0]["interaction_categories"])
            self.assertTrue(ranked[0]["complete_png_sequences_checked"])
            self.assertFalse(ranked[0]["physical_runtime_playback_verified"])

    def test_missing_middle_frame_and_symlink_are_not_playable(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            role = make_role(root, "Missing", {"walk": 3})
            (role / "action" / "walk_1.png").unlink()
            self.assertEqual(_action_inventory(root, "Missing"),
                             ([], ["walk"]))
            role = make_role(root, "Linked", {"wave": 2})
            target = role / "action" / "wave_1.png"
            target.unlink()
            try:
                target.symlink_to(role / "action" / "wave_0.png")
            except (OSError, NotImplementedError):
                self.skipTest("Windows runner does not permit symlinks")
            self.assertEqual(_action_inventory(root, "Linked"), ([], ["wave"]))

    def test_transparent_middle_frame_cannot_count_as_visible_interaction(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            role = make_role(root, "Invisible", {"wave": 2, "rest": 1})
            Image.new("RGBA", (16, 16), (0, 0, 0, 0)).save(
                role / "action" / "wave_1.png")
            self.assertEqual(_action_inventory(root, "Invisible"),
                             (["rest"], ["wave"]))

    def test_valid_one_frame_motion_is_structurally_loadable_not_motion_approved(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            make_role(root, "Standee", {"crawl": 1, "wave": 2})
            usable, broken = _action_inventory(root, "Standee")
            self.assertEqual(usable, ["crawl", "wave"])
            self.assertFalse(broken)
            ranked = rank_installed_role_variants(root, ["Standee"])
            self.assertTrue(ranked[0]["complete_png_sequences_checked"])
            self.assertFalse(ranked[0]["physical_runtime_playback_verified"])
            # Single-frame crawl remains a risk in the separate motion audit;
            # NEVER fabricate a second pose for this role.


if __name__ == "__main__":
    unittest.main()
