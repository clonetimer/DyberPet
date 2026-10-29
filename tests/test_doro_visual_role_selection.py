"""R62: Doro first-class visual-character choice, safe and no duplicate saves."""
from __future__ import annotations
import os
import unittest
from unittest.mock import patch
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


class Settings:
    def __init__(self):
        self.data = {}
    def value(self, key, default=None, type=None):
        return self.data.get(key, default)
    def setValue(self, key, value):
        self.data[key] = value


class FakeDoroWindow:
    def __init__(self):
        self.closed = 0
    def close(self):
        self.closed += 1


class DoroVisualCharacterTests(unittest.TestCase):
    def test_choice_only_persists_after_native_engine_success(self):
        import DyberPet.DyberSettings.doro_live2d_dialog as live
        cfg = Settings()
        payload = {"model_json": "/user/Local/Doro.model3.json"}
        ready = {}
        fake = FakeDoroWindow()
        def open_role(info, on_ready=None, on_failed=None):
            self.assertIs(info, payload)
            ready["done"], ready["failed"] = on_ready, on_failed
            return fake
        with (patch.object(live, "QSettings", return_value=cfg),
              patch.object(live, "_resolve_installed_doro", return_value=payload["model_json"]),
              patch.object(live, "inspect_local_live2d", return_value=payload),
              patch.object(live, "open_doro_desktop", side_effect=open_role)):
            self.assertIs(live.choose_doro_visual_role(), fake)
            self.assertFalse(live.doro_visual_role_selected())
            self.assertEqual(cfg.data, {})
            ready["done"]()
            self.assertTrue(live.doro_visual_role_selected())
            self.assertEqual(cfg.data[live._SETTINGS_KEY], payload["model_json"])

    def test_failed_load_never_enables_doro_preference(self):
        import DyberPet.DyberSettings.doro_live2d_dialog as live
        cfg = Settings()
        ready = {}
        def open_role(info, on_ready=None, on_failed=None):
            ready["failed"] = on_failed
            return FakeDoroWindow()
        with (patch.object(live, "QSettings", return_value=cfg),
              patch.object(live, "_resolve_installed_doro", return_value="Doro.model3.json"),
              patch.object(live, "inspect_local_live2d", return_value={"model_json":"Doro.model3.json"}),
              patch.object(live, "open_doro_desktop", side_effect=open_role)):
            live.choose_doro_visual_role()
            ready["failed"]("no valid GPU/model")
            self.assertFalse(live.doro_visual_role_selected())
            self.assertNotIn(live._SETTINGS_KEY, cfg.data)

    def test_switching_to_standard_visual_role_closes_all_windows(self):
        import DyberPet.DyberSettings.doro_live2d_dialog as live
        cfg = Settings()
        cfg.setValue(live._AUTOSTART_KEY, True)
        first, second = FakeDoroWindow(), FakeDoroWindow()
        with patch.object(live, "QSettings", return_value=cfg), patch.object(
                live, "_ACTIVE_DORO_WINDOWS", [first, second]):
            self.assertTrue(live.doro_visual_role_selected())
            self.assertTrue(live.choose_standard_visual_role())
            self.assertFalse(live.doro_visual_role_selected())
            self.assertEqual((first.closed, second.closed), (1, 1))

    def test_character_manager_exposes_role_selection_and_regular_switch(self):
        source = (Path(__file__).resolve().parents[1] /
                  "DyberPet" / "DyberSettings" / "CharCardUI.py").read_text("utf-8")
        self.assertIn("选择 Doro 作为桌宠", source)
        self.assertIn("切回普通桌宠", source)
        self.assertIn("self.doroRoleSelect.clicked.connect(self._selectDoroAsPet)", source)
        self.assertIn("self._returnToOrdinaryPet()\n        self._launchStateTooltip()", source)
        self.assertIn("if settings.petname == petname:\n            self._returnToOrdinaryPet()", source)

    def test_regular_sprite_catalog_is_not_pretended_live2d_support(self):
        import DyberPet.DyberSettings.doro_live2d_dialog as live
        # Selecting Doro is a distinct *visual* choice, never synthesizes
        # PetConfig assets or mutates settings.pets/PetData.
        cfg = Settings()
        with patch.object(live, "QSettings", return_value=cfg):
            self.assertFalse(live.doro_visual_role_selected())
        source=(Path(__file__).resolve().parents[1] /
                "DyberPet" / "DyberSettings" / "CharCardUI.py").read_text("utf-8")
        self.assertIn("petlist = settings.pets.copy()", source)
        self.assertNotIn('settings.pets.append("Doro")', source)


if __name__ == "__main__":
    unittest.main()
