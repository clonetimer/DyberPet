"""R46: real desktop click/pat versus deliberate drag behavior.

No third-party art used. Synthetic pointer events test the actual PetWidget
event handlers without constructing the whole desktop simulation.
"""
from __future__ import annotations

import ast
import math
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import unittest

from tools.pet_pointer_gestures import deliberate_drag, drag_threshold


class PetPointerIntentTests(unittest.TestCase):
    def test_touch_jitter_stays_click_and_crossing_threshold_starts_drag(self):
        self.assertFalse(deliberate_drag(100, 200, 104, 202, 10))
        self.assertFalse(deliberate_drag(100, 200, 106, 208, 11))
        self.assertTrue(deliberate_drag(100, 200, 106, 208, 10))
        self.assertTrue(deliberate_drag(100, 200, 100, 190, 10))
        self.assertFalse(deliberate_drag(1, 1, math.nan, 1, 10))

    def test_respects_os_preference_and_rejects_absurd_distances(self):
        self.assertEqual(drag_threshold(2), 6)
        self.assertEqual(drag_threshold(10), 10)
        self.assertEqual(drag_threshold(16), 16)
        self.assertEqual(drag_threshold(999), 24)
        self.assertEqual(drag_threshold(None), 10)
        self.assertEqual(drag_threshold(float("inf")), 10)

    def test_pointer_events_live_in_real_pet_window_not_just_preview(self):
        file = (Path(__file__).resolve().parents[1] / "DyberPet" / "DyberPet.py")
        code = ast.parse(file.read_text(encoding="utf-8"))
        methods = {node.name: node for node in ast.walk(code)
                   if isinstance(node, ast.FunctionDef)}
        press = ast.unparse(methods["mousePressEvent"])
        move = ast.unparse(methods["mouseMoveEvent"])
        release = ast.unparse(methods["mouseReleaseEvent"])
        self.assertIn("self._drag_press_global = event.globalPos()", press)
        self.assertNotIn("start_interact('mousedrag')", press)
        self.assertIn("deliberate_drag", move)
        self.assertIn("QApplication.startDragDistance()", move)
        self.assertEqual(move.count("start_interact('mousedrag')"), 1)
        self.assertIn("self.patpat()", release)
        self.assertIn("self._drag_press_global = None", release)

    def test_qt_mouse_jitter_stays_pat_no_worker_pause(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        try:
            from PySide6.QtCore import Qt, QPoint
            from PySide6.QtWidgets import QApplication
            from DyberPet.DyberPet import PetWidget
            import DyberPet.settings as settings
        except ImportError:
            self.skipTest("Qt unavailable")
        app = QApplication.instance() or QApplication([])
        class PointerEvent:
            def __init__(self, xy):
                self.xy = QPoint(*xy)
                self.accepted = False
            def globalPos(self):
                return self.xy
            def buttons(self):
                return Qt.LeftButton
            def button(self):
                return Qt.LeftButton
            def accept(self):
                self.accepted = True

        char = SimpleNamespace(
            is_follow_mouse=True, mouse_moving=False,
            _drag_press_global=QPoint(300, 300), mouse_drag_pos=QPoint(5, 5),
            cursor_dragged=Qt.ClosedHandCursor, cursor_default=Qt.ArrowCursor,
            workers={"Animation": Mock(), "Interaction": Mock()},
            setCursor=Mock(), move=Mock(), patpat=Mock(),
        )
        with patch.object(settings, "set_fall", True), \
             patch.object(settings, "onfloor", 1), \
             patch.object(settings, "draging", 0), \
             patch.object(settings, "mouseposx3", 0), \
             patch.object(settings, "mouseposy3", 0):
            small = PointerEvent((302, 303))
            PetWidget.mouseMoveEvent(char, small)
            self.assertTrue(small.accepted)
            self.assertFalse(char.mouse_moving)
            char.workers["Animation"].pause.assert_not_called()
            char.workers["Interaction"].start_interact.assert_not_called()
            char.move.assert_not_called()

            released = PointerEvent((302, 303))
            PetWidget.mouseReleaseEvent(char, released)
            char.patpat.assert_called_once()
            self.assertIsNone(char._drag_press_global)

    def test_qt_qualified_drag_starts_exactly_one_original_drag_interaction(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        try:
            from PySide6.QtCore import Qt, QPoint
            from PySide6.QtWidgets import QApplication
            from DyberPet.DyberPet import PetWidget
            import DyberPet.settings as settings
        except ImportError:
            self.skipTest("Qt unavailable")
        app = QApplication.instance() or QApplication([])
        class PointerEvent:
            def __init__(self, pos):
                self._pos = QPoint(*pos)
                self.accepted = False
            def globalPos(self):
                return self._pos
            def buttons(self):
                return Qt.LeftButton
            def accept(self):
                self.accepted = True
        char = SimpleNamespace(
            is_follow_mouse=True, mouse_moving=False,
            _drag_press_global=QPoint(200, 200), mouse_drag_pos=QPoint(3, 4),
            cursor_dragged=Qt.ClosedHandCursor,
            workers={"Animation": Mock(), "Interaction": Mock()},
            setCursor=Mock(), move=Mock(),
        )
        positions = ("mouseposx1", "mouseposx2", "mouseposx3", "mouseposx4",
                     "mouseposy1", "mouseposy2", "mouseposy3", "mouseposy4")
        saved = {p: getattr(settings, p) for p in positions}
        try:
            with patch.object(settings, "set_fall", True), \
                 patch.object(settings, "onfloor", 1), \
                 patch.object(settings, "draging", 0):
                settings.mouseposx3 = 0
                first = PointerEvent((230, 200))
                PetWidget.mouseMoveEvent(char, first)
                self.assertTrue(char.mouse_moving)
                self.assertEqual(settings.onfloor, 0)
                self.assertEqual(settings.draging, 1)
                self.assertTrue(first.accepted)
                self.assertEqual(char.move.call_count, 1)
                char.workers["Animation"].pause.assert_called_once()
                char.workers["Interaction"].start_interact.assert_called_once_with("mousedrag")
                second = PointerEvent((240, 200))
                PetWidget.mouseMoveEvent(char, second)
                self.assertEqual(char.move.call_count, 2)
                char.workers["Interaction"].start_interact.assert_called_once()
        finally:
            for key, value in saved.items():
                setattr(settings, key, value)


if __name__ == "__main__":
    unittest.main()
