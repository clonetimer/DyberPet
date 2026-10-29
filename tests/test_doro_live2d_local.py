"""R52: real Cubism local model inventory, without storing third-party Doro art."""
from __future__ import annotations
import json
import os
import tempfile
import unittest
from pathlib import Path

from tools.doro_live2d_local import inspect_local_live2d


class DoroLocalModelTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory()
        self.addCleanup(t.cleanup)
        self.root = Path(t.name)
        self.folder = self.root / "Doro"
        self.folder.mkdir()
        self._make("Doro.moc3")
        self._make("texture.png")
        self._make("idle.motion3.json")
        self._make("happy.exp3.json")
        self.model = self.folder / "Doro.model3.json"
        self.data = {
            "Version": 3,
            "FileReferences": {
                "Moc": "Doro.moc3", "Textures": ["texture.png"],
                "Motions": {"Idle": [{"File": "idle.motion3.json"}]},
                "Expressions": [{"Name": "happy", "File": "happy.exp3.json"}],
            }
        }
        self._save()

    def _make(self, name):
        path = self.folder / name
        path.write_bytes(b"TEST_ONLY_NOT_A_REAL_DORO_MODEL")

    def _save(self):
        self.model.write_text(json.dumps(self.data), encoding="utf-8")

    def test_local_model_inventory_no_modifications_and_no_approval_claim(self):
        before = {x.name: x.read_bytes() for x in self.folder.iterdir()}
        result = inspect_local_live2d(self.model)
        self.assertEqual(result["resource_files_checked"], 4)
        self.assertEqual(result["motion_groups"], {"Idle": 1})
        self.assertEqual(result["expressions"], ["happy"])
        self.assertFalse(result["is_user_approved_doro_likeness"])
        self.assertFalse(result["independent_orthographic_threeview_complete"])
        self.assertFalse(result["redistribution_rights_verified"])
        self.assertEqual(before, {x.name: x.read_bytes() for x in self.folder.iterdir()})

    def test_reject_parent_directory_traversal(self):
        self.data["FileReferences"]["Moc"] = "../Doro.moc3"
        self._save()
        with self.assertRaisesRegex(ValueError, "below model directory"):
            inspect_local_live2d(self.model)

    def test_reject_remote_or_absolute_resources(self):
        for name in ("https://example.com/asset.png", "/tmp/asset.png",
                     "C:/Windows/asset.png", "\\\\server\\share\\asset.png"):
            self.data["FileReferences"]["Textures"] = [name]
            self._save()
            with self.subTest(name=name), self.assertRaises(ValueError):
                inspect_local_live2d(self.model)

    def test_missing_art_blocks_preview(self):
        (self.folder / "texture.png").unlink()
        with self.assertRaisesRegex(ValueError, "Missing"):
            inspect_local_live2d(self.model)

    def test_real_doro_sidecar_owner_idle_is_registered(self):
        self._make("Idle.motion3.json")
        (self.folder / "Doro.vtube.json").write_text(json.dumps({
            "FileReferences": {
                "Model": "Doro.model3.json", "IdleAnimation": "Idle.motion3.json",
                "IdleAnimationWhenTrackingLost": ""
            }
        }), encoding="utf-8")
        report = inspect_local_live2d(self.model)
        self.assertEqual(report["motion_groups"]["OwnerIdle"], 1)
        self.assertEqual(Path(report["extra_motions"]["OwnerIdle"][0]).name.lower(),
                         "idle.motion3.json")
        self.assertEqual(report["resource_files_checked"], 5)

    def test_optional_vtube_hotkey_expressions_use_only_existing_artist_files(self):
        self._make("Exp1.exp3.json")
        before = {x.name: x.read_bytes() for x in self.folder.iterdir()}
        (self.folder / "Doro.vtube.json").write_text(json.dumps({
            "FileReferences": {"Model": "Doro.model3.json"},
            "Hotkeys": [
                {"Action": "ToggleExpression", "Name": "Exp1", "File": "Exp1.exp3.json", "Folder": ""},
                {"Action": "ToggleExpression", "Name": "Absent", "File": "Absent.exp3.json", "Folder": ""},
                {"Action": "ToggleExpression", "Name": "happy", "File": "happy.exp3.json", "Folder": ""},
                {"Action": "ChangeModel", "Name": "Change", "File": "other.exp3.json"},
            ],
        }), encoding="utf-8")
        report = inspect_local_live2d(self.model)
        self.assertEqual(report["expressions"], ["happy", "Exp1"])
        self.assertEqual(list(report["extra_expressions"]), ["Exp1"])
        self.assertEqual(Path(report["extra_expressions"]["Exp1"]).name, "Exp1.exp3.json")
        self.assertEqual(report["resource_files_checked"], 5)
        for name, value in before.items():
            self.assertEqual((self.folder / name).read_bytes(), value)

    def test_vtube_hotkeys_without_installed_file_are_not_claimed(self):
        (self.folder / "Doro.vtube.json").write_text(json.dumps({
            "FileReferences": {"Model": "Doro.model3.json"},
            "Hotkeys": [{"Action": "ToggleExpression",
                         "Name": "Exp2", "File": "Exp2.exp3.json"}]
        }), encoding="utf-8")
        report = inspect_local_live2d(self.model)
        self.assertEqual(report["expressions"], ["happy"])
        self.assertEqual(report["extra_expressions"], {})

    def test_unsafe_vtube_hotkey_reference_fails_before_file_probe(self):
        for path in ("../outside.exp3.json", "C:/secret.exp3.json",
                     "https://bad/Exp1.exp3.json", r"..\\Exp1.exp3.json"):
            (self.folder / "Doro.vtube.json").write_text(json.dumps({
                "FileReferences": {"Model": "Doro.model3.json"},
                "Hotkeys": [{"Action": "ToggleExpression",
                             "Name": "Exp1", "File": path}]
            }), encoding="utf-8")
            with self.subTest(path=path), self.assertRaises(ValueError):
                inspect_local_live2d(self.model)

    def test_native_engine_loads_only_installed_vtube_expression(self):
        from unittest.mock import patch
        import sys
        from types import ModuleType
        from PySide6.QtWidgets import QApplication
        from DyberPet.DyberSettings.doro_live2d_dialog import _DoroGLView

        app = QApplication.instance() or QApplication([])
        calls = []
        class FakeModel:
            def LoadModelJson(self, path):
                calls.append(("model", path))
            def LoadExtraExpression(self, name, path):
                calls.append(("expression", name, path))
            def Resize(self, w, h):
                pass

        fake = ModuleType("live2d")
        fake.init = lambda: None
        fake.glInit = lambda: None
        fake.Model = FakeModel
        view = _DoroGLView({
            "model_json": "synthetic.model3.json",
            "extra_motions": {},
            "extra_expressions": {"Exp1": "local/Exp1.exp3.json"},
            "expressions": ["happy", "Exp1"],
        })
        original_flags = _DoroGLView._framework_ready, _DoroGLView._backend_ready
        try:
            _DoroGLView._framework_ready = False
            _DoroGLView._backend_ready = False
            with patch.dict(sys.modules, {"live2d": fake}):
                view.initializeGL()
            self.assertIsNone(view.error)
            self.assertEqual(calls, [
                ("model", "synthetic.model3.json"),
                ("expression", "Exp1", "local/Exp1.exp3.json")])
        finally:
            view.stop()
            _DoroGLView._framework_ready, _DoroGLView._backend_ready = original_flags

    def test_sidecar_cannot_attach_another_model_or_escape_owner_root(self):
        self._make("Idle.motion3.json")
        sidecar = self.folder / "Doro.vtube.json"
        for model_name, motion in (("Other.model3.json", "Idle.motion3.json"),
                                   ("Doro.model3.json", "../Idle.motion3.json")):
            sidecar.write_text(json.dumps({
                "FileReferences": {"Model": model_name, "IdleAnimation": motion}
            }), encoding="utf-8")
            with self.subTest(model_name=model_name, motion=motion):
                with self.assertRaises(ValueError):
                    inspect_local_live2d(self.model)

    def test_missing_motions_are_not_fabricated(self):
        self.data["FileReferences"]["Motions"] = {}
        self._save()
        result = inspect_local_live2d(self.model)
        self.assertEqual(result["motion_groups"], {})

    def test_duplicate_reference_refused(self):
        self.data["FileReferences"]["Textures"] = ["texture.png", "texture.png"]
        self._save()
        with self.assertRaisesRegex(ValueError, "repeated"):
            inspect_local_live2d(self.model)

    def test_symlink_to_outside_refused(self):
        link = self.folder / "foreign.png"
        try:
            link.symlink_to(self.root / "outside.png")
        except (NotImplementedError, OSError):
            self.skipTest("Symlink not permitted by runner")
        self.data["FileReferences"]["Textures"] = ["foreign.png"]
        self._save()
        with self.assertRaisesRegex(ValueError, "linked"):
            inspect_local_live2d(self.model)

    def test_original_hit_areas_are_reported_but_no_art_approval(self):
        self.data["HitAreas"] = [
            {"Name": "HitAreaFace", "Id": "Face"},
            {"Name": "HitAreaLegBack", "Id": "Leg_back_L"}
        ]
        self._save()
        report = inspect_local_live2d(self.model)
        self.assertEqual(report["hit_areas"],
                         {"HitAreaFace": "Face", "HitAreaLegBack": "Leg_back_L"})
        self.assertFalse(report["is_user_approved_doro_likeness"])

    def test_malformed_or_duplicate_hit_areas_fail_closed(self):
        cases = [
            [{"Name": "HitAreaFace", "Id": "Face"},
             {"Name": "HitAreaFace", "Id": "Other"}],
            [{"Name": "HitAreaFace"}], ["untrusted"],
        ]
        for areas in cases:
            self.data["HitAreas"] = areas
            self._save()
            with self.subTest(areas=areas), self.assertRaises(ValueError):
                inspect_local_live2d(self.model)

    def test_doro_click_mapping_uses_only_real_source_expressions(self):
        from tools.doro_live2d_interaction import (
            click_expression_for_area, is_same_source_area_press,
        )
        expressions = ["Idle", "Doubt", "Amaze", "Sullen"]
        self.assertEqual(click_expression_for_area("HitAreaFace", expressions),
                         "Amaze")
        self.assertEqual(click_expression_for_area("HitAreaLegBack", expressions),
                         "Doubt")
        self.assertIsNone(click_expression_for_area("Unknown", expressions))
        self.assertIsNone(click_expression_for_area("HitAreaFace", ["NoAmaze"]))
        self.assertFalse(is_same_source_area_press(None, "HitAreaFace"))
        self.assertFalse(is_same_source_area_press("HitAreaFace", "HitAreaLegBack"))
        self.assertTrue(is_same_source_area_press("HitAreaFace", "HitAreaFace"))

    def test_qt_shared_context_flag_is_configured_before_application(self):
        src = (Path(__file__).resolve().parents[1] /
               "run_DyberPet.py").read_text(encoding="utf-8")
        self.assertIn("AA_ShareOpenGLContexts, True", src)
        self.assertLess(src.index("AA_ShareOpenGLContexts, True"),
                        src.index("class DyberPetApp(QApplication):"))

    def test_actual_qt_pointer_events_trigger_only_real_face_hits(self):
        from PySide6.QtWidgets import QApplication
        from PySide6.QtGui import QMouseEvent
        from PySide6.QtCore import Qt, QEvent, QPointF
        from DyberPet.DyberSettings.doro_live2d_dialog import DoroDesktopWindow

        app = QApplication.instance() or QApplication([])
        class FakeModel:
            def __init__(self):
                self.expressions = []
            def IsAreaHit(self, area, x, y):
                return area == "HitAreaFace" and 10 <= x <= 30 and 10 <= y <= 30
            def HitDrawable(self, x, y, topOnly=False):
                return ["Body"] if 40 <= x <= 80 and 40 <= y <= 80 else []
            def SetExpression(self, name, fadeoutMs=-1.0):
                self.expressions.append(name)
            def Drag(self, x, y):
                pass

        info = {"model_json": "synthetic.model3.json",
                "hit_areas": {"HitAreaFace": "Face", "HitAreaLegBack": "Leg_back_L"},
                "motion_groups": {}, "expressions": ["Amaze", "Idle"]}
        window = DoroDesktopWindow(info)
        engine = FakeModel()
        window.model = engine

        def mouse(typ, x, y, button, buttons):
            return QMouseEvent(typ, QPointF(x,y), QPointF(x,y),
                               button, buttons, Qt.KeyboardModifier.NoModifier)
        try:
            # Clicking outside character (transparent viewport) cannot pet.
            window.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, 150, 150,
                                         Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton))
            window.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, 150, 150,
                                           Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton))
            self.assertEqual(engine.expressions, [])
            # Genuine model face hit triggers an original source expression.
            window.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, 15, 15,
                                         Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton))
            window.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, 15, 15,
                                           Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton))
            self.assertEqual(engine.expressions, ["Amaze"])
            # Starting on the face and releasing outside does not trigger petting.
            window.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, 15, 15,
                                         Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton))
            window.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, 150, 150,
                                           Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton))
            self.assertEqual(engine.expressions, ["Amaze"])
            # Real visible non-face body is draggable but not a 'pet' hit.
            window.mousePressEvent(mouse(QEvent.Type.MouseButtonPress, 50, 50,
                                         Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton))
            self.assertTrue(window._pressed_model)
            window.mouseMoveEvent(mouse(QEvent.Type.MouseMove, 80, 80,
                                        Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton))
            self.assertTrue(window._moved)
            window.mouseReleaseEvent(mouse(QEvent.Type.MouseButtonRelease, 80, 80,
                                           Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton))
            self.assertEqual(engine.expressions, ["Amaze"])
        finally:
            window.model = None
            window.close()

    def test_native_backend_init_called_only_once_across_two_gl_widgets(self):
        from unittest.mock import patch
        import sys
        from types import ModuleType
        from PySide6.QtWidgets import QApplication
        from DyberPet.DyberSettings.doro_live2d_dialog import _DoroGLView

        app = QApplication.instance() or QApplication([])
        calls = {"glInit": 0, "init": 0}

        class StubModel:
            def LoadModelJson(self, path):
                pass
            def Resize(self, width, height):
                pass

        def gl_init():
            calls["glInit"] += 1
            if calls["glInit"] > 1:
                raise RuntimeError("native backend already initialized")

        fake = ModuleType("live2d")
        fake.init = lambda: calls.__setitem__("init", calls["init"] + 1)
        fake.glInit = gl_init
        fake.Model = StubModel
        old_flags = _DoroGLView._framework_ready, _DoroGLView._backend_ready
        first = _DoroGLView({
            "model_json": "synthetic.model3.json",
            "extra_motions": {}, "hit_areas": {},
        })
        second = _DoroGLView({
            "model_json": "synthetic.model3.json",
            "extra_motions": {}, "hit_areas": {},
        })
        try:
            _DoroGLView._framework_ready = False
            _DoroGLView._backend_ready = False
            with patch.dict(sys.modules, {"live2d": fake}):
                first.initializeGL()
                second.initializeGL()
            self.assertEqual(calls, {"glInit": 1, "init": 1},
                             f"first={first.error!r}, second={second.error!r}")
            self.assertIsNone(first.error)
            self.assertIsNone(second.error)
        finally:
            first.stop()
            second.stop()
            _DoroGLView._framework_ready, _DoroGLView._backend_ready = old_flags

    def test_qt_dialog_hook_has_real_doro_only_action(self):
        source = (Path(__file__).resolve().parents[1]
                  / "DyberPet" / "DyberSettings" / "CharCardUI.py").read_text("utf-8")
        self.assertIn("【Doro 专项】", source)
        self.assertIn("from .doro_live2d_dialog import open_doro_live2d", source)
        self.assertIn("open_doro_live2d(self)", source)

    def test_desktop_pet_is_a_real_window_not_a_thumbnail(self):
        import ast
        module = (Path(__file__).resolve().parents[1]
                  / "DyberPet" / "DyberSettings" / "doro_live2d_dialog.py")
        tree = ast.parse(module.read_text(encoding="utf-8"))
        cls = next(x for x in tree.body if isinstance(x, ast.ClassDef)
                   and x.name == "DoroDesktopWindow")
        methods = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
        self.assertTrue({"mouseMoveEvent", "mouseReleaseEvent",
                         "wheelEvent", "_show_actions", "closeEvent"} <= methods)
        self.assertIn("WindowStaysOnTopHint", module.read_text(encoding="utf-8"))
        self.assertIn("open_doro_desktop(self.model_info)",
                      module.read_text(encoding="utf-8"))

    def test_duplicate_doro_launch_reuses_one_window_and_switch_closes_old(self):
        from unittest.mock import patch
        import DyberPet.DyberSettings.doro_live2d_dialog as viewer

        original = list(viewer._ACTIVE_DORO_WINDOWS)

        class FakeWindow:
            def __init__(self, info):
                self.model_info = info
                self.visible = False
                self.focused = 0

            def isVisible(self):
                return self.visible

            def show(self):
                self.visible = True

            def close(self):
                self.visible = False
                if self in viewer._ACTIVE_DORO_WINDOWS:
                    viewer._ACTIVE_DORO_WINDOWS.remove(self)

            def raise_(self):
                self.focused += 1

            def activateWindow(self):
                self.focused += 1

        try:
            viewer._ACTIVE_DORO_WINDOWS.clear()
            with patch.object(viewer, "DoroDesktopWindow", FakeWindow):
                first = viewer.open_doro_desktop({"model_json": "Doro1.model3.json"})
                self.assertTrue(first.isVisible())
                repeat = viewer.open_doro_desktop({"model_json": "Doro1.model3.json"})
                self.assertIs(repeat, first)
                self.assertEqual(len(viewer._ACTIVE_DORO_WINDOWS), 1)
                self.assertEqual(first.focused, 2)
                different = viewer.open_doro_desktop({"model_json": "Doro2.model3.json"})
                self.assertIsNot(different, first)
                self.assertFalse(first.isVisible())
                self.assertTrue(different.isVisible())
                self.assertEqual(len(viewer._ACTIVE_DORO_WINDOWS), 1)
                different.close()
                self.assertEqual(len(viewer._ACTIVE_DORO_WINDOWS), 0)
        finally:
            viewer._ACTIVE_DORO_WINDOWS[:] = original

    def test_model_failure_shows_explicit_status_and_reselection_is_available(self):
        source = (Path(__file__).resolve().parents[1]
                  / "DyberPet" / "DyberSettings" / "doro_live2d_dialog.py").read_text("utf-8")
        self.assertIn("loadFailed = Signal(str)", source)
        self.assertIn("loadFailed.connect(self._on_model_failed)", source)
        self.assertIn("更换本机 Live2D 模型文件", source)
        self.assertIn("GetMotionGroups().get(group, 0)", source)

    def test_qt_preview_module_compiles_without_optional_engine_import(self):
        import ast
        file = (Path(__file__).resolve().parents[1]
                / "DyberPet" / "DyberSettings" / "doro_live2d_dialog.py")
        tree = ast.parse(file.read_text(encoding="utf-8"))
        self.assertTrue(any(isinstance(n, ast.ClassDef)
                            and n.name == "_DoroGLView" for n in tree.body))
        self.assertTrue(any(isinstance(n, ast.ClassDef)
                            and n.name == "DoroLive2DPreviewDialog"
                            for n in tree.body))


if __name__ == "__main__":
    unittest.main()
