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

    def test_native_group_map_rejects_locked_mixed_and_fake_animations(self):
        from DyberPet.assistant.native_groups import runtime_group_interactions
        options = {
            x: {"unlocked": True, "act_type": "random_act"} for x in
            ("打招呼", "左右散步", "休息", "蹦一蹦", "假动作")}
        groups = [{"name": "打招呼", "act_list": ["wave"]},
                  {"name": "左右散步", "act_list": ["left_walk", "right_walk"]},
                  {"name": "休息", "act_list": ["wait"]},
                  {"name": "蹦一蹦", "act_list": ["jump"]},
                  {"name": "假动作", "act_list": ["idle", "wave"]}]
        options["蹦一蹦"]["unlocked"] = False
        m = runtime_group_interactions(
            options, groups, {"idle", "wave", "wait", "left_walk", "right_walk", "jump"})
        actions = {x["id"]: x["action"] for x in m if x["available"]}
        self.assertEqual(actions, {"greet": "打招呼", "walk": "左右散步",
                                   "rest": "休息"})
        self.assertNotIn("假动作", actions.values())

    def test_fv_unlock_refreshes_assistant_action_buttons_in_real_main_source(self):
        # Main application cannot be imported in a pure unit test because it
        # creates Qt/system settings on import. Inspect the genuine method AST.
        import ast
        source = (Path(__file__).resolve().parents[1] /
                  "DyberPet" / "DyberPet.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        methods = [n for cls in tree.body if isinstance(cls, ast.ClassDef)
                   for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and n.name == "_update_fvlock"]
        self.assertEqual(len(methods), 1)
        syncs = [call for call in ast.walk(methods[0]) if isinstance(call, ast.Call)
                 and isinstance(call.func, ast.Attribute)
                 and call.func.attr == "_sync_assistant_actions"]
        self.assertEqual(len(syncs), 1)

    def test_direct_roster_id_fallback_only_for_valid_curated_ids(self):
        with tempfile.TemporaryDirectory() as td:
            self.assertEqual(persona_for_local_role("genshin_kaveh", td),
                             "genshin_kaveh")
            self.assertIsNone(persona_for_local_role("genshin_wrong", td))


if __name__ == "__main__":
    unittest.main()
