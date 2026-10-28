"""R26 Chinese identity display and size-safe on-demand FFmpeg installer tests."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools.character_display_name import chinese_character_name
from tools.whale_ffmpeg_runtime import fetch_pinned_windows_ffmpeg


class _Response(io.BytesIO):
    def __init__(self, data, url):
        super().__init__(data)
        self._url = url

    def geturl(self):
        return self._url


class ChineseRoleLabels(unittest.TestCase):
    def test_original_internal_identifiers_are_not_renamed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for folder, expected in (
                ("SourceWhalePet", "鲸鱼娘"),
                ("SourceWhalePet_2", "鲸鱼娘"),
                ("SourceGuga", "咕嘎"),
                ("SourceDoroHanddrawnV2", "朵萝"),
                ("Kitty", "小猫")):
                self.assertEqual(chinese_character_name(folder, root), expected)

    def test_profile_receipt_resolves_correct_chinese_identity(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            role = root / "SourceGenshinNahida"
            role.mkdir()
            (role / "PERSONAL_IMPORT.json").write_text(json.dumps({
                "selected_profile": "genshin_nahida",
                "display_name": "Nahida"
            }), encoding="utf-8")
            self.assertEqual(chinese_character_name(role.name, root), "纳西妲")
            self.assertTrue(role.name == "SourceGenshinNahida")

    def test_chinese_override_and_unknown_role_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "ArtistOriginal"
            folder.mkdir()
            (folder / "PERSONAL_IMPORT.json").write_text(
                json.dumps({"display_name_zh": "小鲸鱼"}), encoding="utf-8")
            self.assertEqual(chinese_character_name(folder.name, root), "小鲸鱼")
            self.assertEqual(chinese_character_name("UnknownArtist", root), "UnknownArtist")


class PinnedOnDemandDecoder(unittest.TestCase):
    def test_wheel_both_checksums_and_local_cache(self):
        import tools.whale_ffmpeg_runtime as runtime
        filename = runtime.MEMBER_NAME
        video_tool = b"synthetic-decoder-byte-content-for-tests"
        raw = io.BytesIO()
        with zipfile.ZipFile(raw, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(filename, video_tool)
        wheel = raw.getvalue()
        url = "https://files.pythonhosted.org/packages/synthetic/" + runtime.WHEEL_NAME
        metadata = {"urls": [{
            "filename": runtime.WHEEL_NAME, "url": url,
            "digests": {"sha256": hashlib.sha256(wheel).hexdigest()}
        }]}
        calls = []
        def open_url(address, timeout):
            calls.append(address)
            if address == runtime.METADATA_URL:
                return _Response(json.dumps(metadata).encode(), address)
            if address == url:
                return _Response(wheel, address)
            raise AssertionError(address)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(runtime, "WHEEL_SHA256", hashlib.sha256(wheel).hexdigest()), \
                 patch.object(runtime, "BIN_SHA256", hashlib.sha256(video_tool).hexdigest()):
                exe = Path(fetch_pinned_windows_ffmpeg(root, opener=open_url))
                self.assertEqual(exe.read_bytes(), video_tool)
                self.assertEqual(len(calls), 2)
                self.assertEqual(fetch_pinned_windows_ffmpeg(root, opener=open_url), str(exe))
                self.assertEqual(len(calls), 2)
                exe.write_bytes(b"corrupt")
                with self.assertRaisesRegex(ValueError, "Cached FFmpeg has changed"):
                    fetch_pinned_windows_ffmpeg(root, opener=open_url)

    def test_mismatched_metadata_fails_without_installed_exe(self):
        import tools.whale_ffmpeg_runtime as runtime
        metadata = {"urls": [{"filename": runtime.WHEEL_NAME,
                              "url": "https://evil.test/win.whl",
                              "digests": {"sha256": runtime.WHEEL_SHA256}}]}
        def opener(url, timeout):
            return _Response(json.dumps(metadata).encode(), url)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaisesRegex(ValueError, "wheel identity mismatch"):
                fetch_pinned_windows_ffmpeg(root, opener=opener)
            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
