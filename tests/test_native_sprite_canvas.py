"""R47 live Q-chibi desktop rendering, with test-only synthetic Qt sprites.

No artist assets are generated, redistributed, or modified.
"""
from __future__ import annotations

import os
from types import SimpleNamespace
import unittest


class LiveNativeCanvasTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        try:
            from PySide6.QtWidgets import QApplication
            from PySide6.QtGui import QPainter, QPixmap, QColor
            from PySide6.QtCore import Qt
            from tools.native_sprite_canvas import NativeSpriteCanvas, _alpha_rect
        except ImportError:
            raise unittest.SkipTest("Qt dependencies not installed")
        cls.app = QApplication.instance() or QApplication([])
        cls.Qt = Qt
        cls.QPixmap = QPixmap
        cls.QPainter = QPainter
        cls.QColor = QColor
        cls.Canvas = NativeSpriteCanvas
        cls._alpha_rect = staticmethod(_alpha_rect)

    def sprite(self, width, height, x, y, w=40, h=60):
        p = self.QPixmap(width, height)
        p.fill(self.Qt.GlobalColor.transparent)
        painter = self.QPainter(p)
        painter.fillRect(x, y, w, h, self.QColor("#ff5588"))
        painter.end()
        return p

    @staticmethod
    def role(mapping, width=128, height=128):
        actions = {key: SimpleNamespace(images=frames) for key, frames in mapping.items()}
        return SimpleNamespace(width=width, height=height, act_dict=actions)

    def test_live_role_aligns_same_visible_figure_with_different_transparent_canvases(self):
        stand = self.sprite(128, 128, 20, 60)
        sideways = self.sprite(256, 256, 145, 155)
        signatures = (stand.cacheKey(), sideways.cacheKey())
        runtime = self.Canvas(self.role({"stand": [stand], "walk": [sideways]}))
        self.assertTrue(runtime.enabled)
        self.assertEqual(runtime.viewport(1), (256, 256))
        a, b = runtime.render(stand, 1), runtime.render(sideways, 1)
        self.assertEqual((a.width(), a.height()), (256, 256))
        self.assertEqual((b.width(), b.height()), (256, 256))
        ar, br = self._alpha_rect(a), self._alpha_rect(b)
        self.assertEqual((ar.x(), ar.y(), ar.width(), ar.height()),
                         (br.x(), br.y(), br.width(), br.height()))
        self.assertEqual((stand.cacheKey(), sideways.cacheKey()), signatures)
        self.assertEqual(runtime.render(stand, 1).cacheKey(), a.cacheKey())

    def test_bobbing_up_and_down_is_preserved_with_one_action_anchor(self):
        idle = self.sprite(128, 128, 20, 65)
        jump_ground = self.sprite(256, 256, 140, 160)
        jump_air = self.sprite(256, 256, 140, 110)
        runtime = self.Canvas(self.role({"idle": [idle], "jump": [jump_ground, jump_air]}))
        self.assertTrue(runtime.enabled)
        ground = self._alpha_rect(runtime.render(jump_ground, 1))
        air = self._alpha_rect(runtime.render(jump_air, 1))
        self.assertEqual(ground.y() - air.y(), 50)
        self.assertEqual(ground.width(), air.width())
        self.assertEqual(ground.height(), air.height())

    def test_consistent_native_frames_not_changed(self):
        a = self.sprite(128, 128, 10, 10)
        b = self.sprite(128, 128, 14, 10)
        runtime = self.Canvas(self.role({"walk": [a, b]}))
        self.assertFalse(runtime.enabled)
        self.assertEqual(runtime.render(a, 2).cacheKey(), a.cacheKey())

    def test_bad_or_giant_image_does_not_allocate_unbounded_canvas(self):
        a = self.sprite(128, 128, 10, 10)
        b = self.sprite(1550, 80, 10, 10)
        runtime = self.Canvas(self.role({"a": [a], "b": [b]}))
        self.assertFalse(runtime.enabled)

    def test_real_live_pet_widget_receives_normalized_canvas(self):
        try:
            from DyberPet.DyberPet import PetWidget
            from DyberPet import settings
            from PySide6.QtWidgets import QLabel
        except ImportError:
            self.skipTest("DyberPet GUI dependencies unavailable")
        a = self.sprite(128, 128, 20, 60)
        b = self.sprite(256, 256, 145, 155)
        runtime = self.Canvas(self.role({"idle": [a], "walk": [b]}))
        label = QLabel()
        class FakePet:
            def __init__(self):
                self._sprite_canvas = runtime
                self.label = label
                self.moves = []
                self.image = None
            def pos(self):
                from PySide6.QtCore import QPoint
                return QPoint(0, 0)
            def move(self, x, y):
                self.moves.append((x, y))
        pet = FakePet()
        old = (getattr(settings, "current_img", None),
               getattr(settings, "current_anchor", None),
               getattr(settings, "previous_anchor", None),
               getattr(settings, "tunable_scale", None))
        try:
            settings.tunable_scale = 1
            settings.current_anchor = [0, 0]
            settings.previous_anchor = [0, 0]
            settings.current_img = a
            PetWidget.set_img(pet)
            first = label.pixmap()
            settings.current_img = b
            PetWidget.set_img(pet)
            second = label.pixmap()
            self.assertEqual((first.width(), first.height()), (256, 256))
            self.assertEqual((second.width(), second.height()), (256, 256))
            self.assertEqual(self._alpha_rect(first).size(),
                             self._alpha_rect(second).size())
            self.assertEqual(pet.image.cacheKey(), b.cacheKey())
            self.assertFalse(pet.moves)
        finally:
            (settings.current_img, settings.current_anchor,
             settings.previous_anchor, settings.tunable_scale) = old


if __name__ == "__main__":
    unittest.main()
