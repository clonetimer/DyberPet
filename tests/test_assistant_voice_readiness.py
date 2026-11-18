"""Passive audio setup checks must not load drivers or touch devices."""
import importlib
import importlib.machinery
import sys
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path
from types import ModuleType
from unittest.mock import patch


_AUDIO_MODULES = ("vosk", "sounddevice", "pyttsx3")


def _discoverable_module(name):
    module = ModuleType(name)
    module.__spec__ = importlib.machinery.ModuleSpec(name, loader=None)
    return module


class VoiceReadinessTests(unittest.TestCase):
    def setUp(self):
        try:
            self.voice = importlib.import_module("DyberPet.assistant.voice_readiness")
        except ModuleNotFoundError as exc:
            if exc.name != "DyberPet.assistant.voice_readiness":
                raise
            self.fail("The passive voice readiness inspector is not implemented")
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def model(self, *markers, name="model"):
        folder = self.root / name
        folder.mkdir(parents=True, exist_ok=True)
        for marker in markers:
            target = folder / marker
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"structure only; not a loadable model")
        return folder

    def inspect(self, model_dir, *, present=_AUDIO_MODULES):
        modules = {
            name: _discoverable_module(name) if name in present else None
            for name in _AUDIO_MODULES
        }
        with patch.dict(sys.modules, modules), \
                patch("DyberPet.assistant.voice_readiness.shutil.which",
                      return_value="/usr/bin/espeak-ng"):
            return self.voice.inspect_voice_readiness(str(model_dir))

    def test_missing_components_name_installation_actions(self):
        folder = self.model("am/final.mdl", "conf/model.conf")
        result = self.inspect(folder, present=())
        self.assertFalse(result.recognition_ready)
        self.assertFalse(result.tts_ready)
        for name in ("vosk", "sounddevice"):
            self.assertIn(name, result.recognition_message)
        self.assertIn("pip install", result.recognition_message)
        self.assertIn("pyttsx3", result.tts_message)
        self.assertIn("pip install", result.tts_message)

    def test_frozen_application_directs_missing_components_to_portable_package(self):
        folder = self.model("am/final.mdl", "conf/model.conf")
        with patch.object(sys, "frozen", True, create=True):
            result = self.inspect(folder, present=())
        for message in (result.recognition_message, result.tts_message):
            self.assertIn("便携包", message)
            self.assertIn("解压", message)
            self.assertNotIn("pip install", message)

    def test_current_model_structure_is_only_preliminary_readiness(self):
        folder = self.model("am/final.mdl", "conf/model.conf")
        result = self.inspect(folder)
        self.assertIsInstance(result, self.voice.VoiceReadiness)
        self.assertTrue(result.recognition_ready)
        self.assertTrue(result.tts_ready)
        self.assertIn("初检", result.recognition_message)
        self.assertIn("未", result.recognition_message)
        self.assertIn("麦克风", result.recognition_message)
        self.assertIn("未", result.tts_message)
        self.assertIn("驱动", result.tts_message)
        with self.assertRaises(FrozenInstanceError):
            result.recognition_ready = False

    def test_legacy_model_structure_remains_supported(self):
        folder = self.model("final.mdl", "mfcc.conf")
        self.assertTrue(self.inspect(folder).recognition_ready)

    def test_each_recognition_component_is_required_independently_of_tts(self):
        folder = self.model("am/final.mdl", "conf/model.conf")
        for absent in ("vosk", "sounddevice"):
            with self.subTest(absent=absent):
                result = self.inspect(folder, present=set(_AUDIO_MODULES) - {absent})
                self.assertFalse(result.recognition_ready)
                self.assertIn(absent, result.recognition_message)
                self.assertTrue(result.tts_ready)

    def test_missing_tts_does_not_block_recognition(self):
        folder = self.model("am/final.mdl", "conf/model.conf")
        result = self.inspect(folder, present=("vosk", "sounddevice"))
        self.assertTrue(result.recognition_ready)
        self.assertFalse(result.tts_ready)

    def test_empty_model_path_requests_an_explicit_model_selection(self):
        for model_dir in ("", "  \t"):
            with self.subTest(model_dir=model_dir):
                result = self.inspect(model_dir)
                self.assertFalse(result.recognition_ready)
                self.assertIn("选择", result.recognition_message)
                self.assertIn("解压", result.recognition_message)
                self.assertTrue(result.tts_ready)

    def test_missing_directory_or_file_is_not_a_model_directory(self):
        file_path = self.root / "model.zip"
        file_path.write_bytes(b"not a directory")
        for model_dir in (self.root / "missing", file_path):
            with self.subTest(model_dir=model_dir):
                result = self.inspect(model_dir)
                self.assertFalse(result.recognition_ready)
                self.assertIn("目录", result.recognition_message)
                self.assertIn("重新选择", result.recognition_message)
                self.assertTrue(result.tts_ready)

    def test_outer_folder_hints_at_selecting_the_inner_model_folder(self):
        folder = self.model("am/final.mdl", "conf/model.conf", name="download/model")
        result = self.inspect(folder.parent)
        self.assertFalse(result.recognition_ready)
        self.assertIn("外层", result.recognition_message)
        self.assertIn("模型文件夹", result.recognition_message)

    def test_incomplete_or_mixed_model_layout_is_not_ready(self):
        cases = (
            ("am/final.mdl",),
            ("conf/model.conf",),
            ("final.mdl",),
            ("mfcc.conf",),
            ("am/final.mdl", "mfcc.conf"),
        )
        for index, markers in enumerate(cases):
            with self.subTest(markers=markers):
                folder = self.model(*markers, name="partial-" + str(index))
                self.assertFalse(self.inspect(folder).recognition_ready)

    def test_model_markers_must_be_files(self):
        folder = self.model()
        (folder / "am/final.mdl").mkdir(parents=True)
        (folder / "conf/model.conf").mkdir(parents=True)
        self.assertFalse(self.inspect(folder).recognition_ready)

    def test_unreadable_or_invalid_path_keeps_tts_result_available(self):
        folder = self.model("am/final.mdl", "conf/model.conf")
        cases = (
            ("expanduser", RuntimeError("home unavailable")),
            ("is_dir", PermissionError("private path")),
            ("is_file", ValueError("invalid path")),
        )
        for method, error in cases:
            with self.subTest(method=method):
                with patch.object(Path, method, side_effect=error):
                    result = self.inspect(folder)
                self.assertFalse(result.recognition_ready)
                self.assertIn("路径", result.recognition_message)
                self.assertTrue(result.tts_ready)
                self.assertNotIn(str(error), result.recognition_message)

    def test_malformed_module_metadata_is_contained_per_component(self):
        folder = self.model("am/final.mdl", "conf/model.conf")
        for malformed_name in _AUDIO_MODULES:
            with self.subTest(module=malformed_name):
                modules = {name: _discoverable_module(name) for name in _AUDIO_MODULES}
                # find_spec raises ValueError for an existing module without a spec.
                modules[malformed_name] = ModuleType(malformed_name)
                with patch.dict(sys.modules, modules):
                    result = self.voice.inspect_voice_readiness(str(folder))
                self.assertEqual(result.recognition_ready, malformed_name == "pyttsx3")
                self.assertEqual(result.tts_ready, malformed_name != "pyttsx3")

    def test_discovery_errors_are_reported_without_breaking_other_components(self):
        folder = self.model("am/final.mdl", "conf/model.conf")
        for error in (ImportError("bad finder"), OSError("finder unavailable"),
                      AttributeError("bad metadata"), ValueError("missing spec")):
            with self.subTest(error=type(error).__name__):
                def discover(name):
                    if name == "vosk":
                        raise error
                    return importlib.machinery.ModuleSpec(name, loader=None)

                with patch("importlib.util.find_spec", side_effect=discover):
                    result = self.voice.inspect_voice_readiness(str(folder))
                self.assertFalse(result.recognition_ready)
                self.assertIn("vosk", result.recognition_message)
                self.assertTrue(result.tts_ready)

    def test_discoverable_audio_modules_are_never_imported(self):
        folder = self.model("am/final.mdl", "conf/model.conf")
        modules_dir = self.root / "audio_modules"
        modules_dir.mkdir()
        for name in _AUDIO_MODULES:
            (modules_dir / (name + ".py")).write_text(
                "raise AssertionError('audio driver imported during passive check')\n",
                encoding="utf-8",
            )
        with patch.dict(sys.modules), patch.object(sys, "path", [str(modules_dir)] + sys.path), \\
                patch("DyberPet.assistant.voice_readiness.shutil.which", return_value="/usr/bin/espeak-ng"):
            for name in _AUDIO_MODULES:
                sys.modules.pop(name, None)
            importlib.invalidate_caches()
            inspector = importlib.reload(self.voice)
            result = inspector.inspect_voice_readiness(str(folder))
            self.assertTrue(result.recognition_ready)
            self.assertTrue(result.tts_ready)
            self.assertTrue(all(name not in sys.modules for name in _AUDIO_MODULES))


if __name__ == "__main__":
    unittest.main()
