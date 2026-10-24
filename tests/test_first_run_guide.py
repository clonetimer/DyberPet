"""A clean install can select only genuine local roles; old saves are untouched."""
from pathlib import Path
import tempfile
import unittest

from DyberPet.assistant.first_run import installed_playable_roles, needs_first_run


class FirstRunTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.roles = self.root / "res" / "role"
        self.roles.mkdir(parents=True)

    def _role(self, name, *, frame=True, demo=False):
        role = self.roles / name
        role.mkdir()
        (role / "pet_conf.json").write_text("{}", encoding="utf8")
        (role / "act_conf.json").write_text("{}", encoding="utf8")
        (role / "action").mkdir()
        if frame:
            (role / "action" / "idle_0.png").write_bytes(b"synthetic")
        if demo:
            (role / "BUILTIN_CHIBI_DEMO.json").write_text("{}", encoding="utf8")
        return role

    def test_first_run_gate_never_overrides_existing_settings(self):
        self.assertTrue(needs_first_run(self.root))
        self.assertFalse(needs_first_run(self.root, ["--assistant-smoke"]))
        self.assertFalse(needs_first_run(self.root, ["--linux-ui-smoke"]))
        folder = self.root / "data"
        folder.mkdir()
        (folder / "settings.json").write_text("{}", encoding="utf8")
        self.assertFalse(needs_first_run(self.root))

    def test_list_only_installed_playable_local_roles(self):
        lisa = self._role("DemoG_lisa", demo=True)
        (lisa / "BUILTIN_CHIBI_DEMO.json").write_text(
            '{"name":"丽莎","profile":"genshin_lisa"}', encoding="utf8")
        self._role("Kitty")
        self._role("template_only", frame=False)
        (self.roles / "sys").mkdir()
        before = {
            p.relative_to(self.root): p.read_bytes()
            for p in self.root.rglob("*") if p.is_file()
        }
        result = installed_playable_roles(self.roles)
        self.assertEqual([x["folder"] for x in result], ["Kitty", "DemoG_lisa"])
        self.assertFalse(result[0]["demo"])
        self.assertTrue(result[1]["demo"])
        self.assertEqual(result[1]["display"], "丽莎")
        after = {
            p.relative_to(self.root): p.read_bytes()
            for p in self.root.rglob("*") if p.is_file()
        }
        self.assertEqual(before, after)

    def test_creator_art_is_searchable_by_chinese_name_and_ranked_first(self):
        self._role("DemoG_nahida", demo=True)
        creator = self._role("SourceGenshinNahida")
        (creator / "PERSONAL_IMPORT.json").write_text(
            '{"selected_profile":"genshin_nahida","display_name":"纳西妲",'
            '"source_repository":"ChaozhongLiu/DyberPet_GenshinImpact",'
            '"source_kind":"artist_original_animation"}', encoding="utf-8")
        result = installed_playable_roles(self.roles)
        self.assertEqual(result[0]["folder"], "SourceGenshinNahida")
        self.assertEqual(result[0]["display"], "纳西妲")
        self.assertTrue(result[0]["artist_source"])
        self.assertFalse(result[0]["demo"])
        self.assertEqual(result[1]["folder"], "DemoG_nahida")
        self.assertFalse(result[1]["artist_source"])
        self.assertTrue(result[1]["demo"])

    def test_empty_or_broken_directory_is_not_invented_as_playable(self):
        self.assertEqual(installed_playable_roles(self.roles), [])
        self._role("no_png", frame=False)
        self.assertEqual(installed_playable_roles(self.roles), [])


if __name__ == "__main__":
    unittest.main()
