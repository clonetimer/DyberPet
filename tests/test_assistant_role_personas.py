"""All 123 optional personae are distinct from original art and bound by receipt."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from DyberPet.assistant.persona import PERSONAS, make_system_prompt
from DyberPet.assistant.role_personas import persona_for_local_role


class RolePersonaTests(unittest.TestCase):
    def test_123_nonofficial_text_roles_exist_and_remain_distinct(self):
        keys = sorted(k for k in PERSONAS if k.startswith("genshin_"))
        self.assertEqual(len(keys), 123)
        self.assertIn("卡维", PERSONAS["genshin_kaveh"].style)
        self.assertIn("绮良良", PERSONAS["genshin_kirara"].style)
        self.assertNotEqual(PERSONAS["genshin_kaveh"].style,
                            PERSONAS["genshin_kirara"].style)
        for key in keys:
            prompt = make_system_prompt(key)
            self.assertIn("文件创建、删除或恢复只能通过桌宠界面", prompt)
            self.assertIn("不", PERSONAS[key].boundaries)
            self.assertIn("非官方", PERSONAS[key].name)

    def test_receipt_based_role_resolution_and_no_filename_guessing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name, profile in (("SourceKaveh", "genshin_kaveh"),
                                  ("SourceKirara", "genshin_kirara")):
                folder = root / name
                folder.mkdir()
                (folder / "PERSONAL_IMPORT.json").write_text(
                    json.dumps({"selected_profile": profile}), encoding="utf-8")
                self.assertEqual(persona_for_local_role(name, root), profile)
            self.assertIsNone(persona_for_local_role("KavehNoReceipt", root))
            (root / "UnknownKaveh").mkdir()
            self.assertIsNone(persona_for_local_role("UnknownKaveh", root))
            self.assertIsNone(persona_for_local_role("../SourceKaveh", root))
            self.assertIsNone(persona_for_local_role("SourceKaveh/..", root))
            (root / "SourceKaveh" / "IMPORT_REPORT.json").write_text(
                json.dumps({"profile": "genshin_kirara"}), encoding="utf-8")
            self.assertIsNone(persona_for_local_role("SourceKaveh", root))
            self.assertEqual(persona_for_local_role("SourceKirara", root),
                             "genshin_kirara")

    def test_direct_roster_id_fallback_only_for_valid_curated_ids(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(persona_for_local_role("genshin_kaveh", td),
                             "genshin_kaveh")
            self.assertIsNone(persona_for_local_role("genshin_wrong", td))


if __name__ == "__main__":
    unittest.main()
