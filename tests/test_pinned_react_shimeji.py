"""Pinned React-Shimeji LFS: no JS execution; crop only original PNG art."""
from __future__ import annotations

from io import BytesIO
import base64
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from tools.install_pinned_react_shimeji import (
    decode_pinned_frames, install_pinned_react_shimeji, _parse_only_literal_source)
from tools.react_shimeji_source_leads import CANDIDATES
from tools.install_native_role import validate_native_role


def _fake_upstream_source():
    image = Image.new("RGBA", (192, 64), (0, 0, 0, 0))
    painter = ImageDraw.Draw(image)
    coords = {}
    for i, frame in enumerate((1, 2, 3, 38)):
        color = ((50 + i * 37) % 255, (10 + i * 51) % 255, 125, 255)
        painter.rectangle((i * 48, 0, i * 48 + 47, 63), fill=color)
        coords["/shime%d.png" % frame] = {"x": i * 48, "y": 0, "width": 48, "height": 64}
    atlas = BytesIO()
    image.save(atlas, format="PNG")
    as_uri = "data:image/png;base64," + base64.b64encode(atlas.getvalue()).decode("ascii")
    # Uses the upstream generator's JSON-literal *fields*, not executable JS.
    fields = (
        "  id: " + json.dumps("kaveh-2f46f2") + ",\n"
        "  spritesheet: " + json.dumps(as_uri) + ",\n"
        "  sprites: " + json.dumps(coords) + ",\n"
        "  actions: " + json.dumps("<Mascot/>") + ",\n"
        "  behaviors: " + json.dumps("<Mascot/>") + ",\n"
    )
    return ("// harmless generated file\nexport const character = {\n" +
            fields + "} as const;\nexport default character;\n").encode("utf-8")


class ReactShimejiImportTests(unittest.TestCase):
    def setup_fixture(self, root):
        source = Path(root) / "index.ts"
        payload = _fake_upstream_source()
        source.write_bytes(payload)
        digest = hashlib.sha256(payload).hexdigest()
        candidate = ("kaveh-2f46f2", digest, len(payload), "a" * 40, "b" * 40)
        return source, candidate

    def test_correct_lfs_sha_and_pixels_import_without_executing_typescript(self):
        with tempfile.TemporaryDirectory() as td:
            source, candidate = self.setup_fixture(td)
            roles = Path(td) / "roles"
            with patch.dict(CANDIDATES, {"genshin_kaveh": candidate}):
                frames, digest = decode_pinned_frames(source, profile="genshin_kaveh")
                self.assertEqual(set(frames), {1, 2, 3, 38})
                self.assertEqual(digest, candidate[1])
                with self.assertRaisesRegex(ValueError, "Explicit private"):
                    install_pinned_react_shimeji(
                        source, roles, profile="genshin_kaveh", confirmed=False)
                self.assertFalse(roles.exists())
                output = install_pinned_react_shimeji(
                    source, roles, profile="genshin_kaveh", confirmed=True)
                self.assertTrue(output.is_dir())
                self.assertGreaterEqual(validate_native_role(output)["actions"], 3)
                receipt = json.loads((output / "PERSONAL_IMPORT.json").read_text("utf-8"))
                self.assertEqual(receipt["source_kind"], "pinned_react_shimeji_lfs_local_only")
                self.assertEqual(receipt["source_module_sha256"], digest)
                self.assertFalse(receipt["source_author_likeness_qa_passed"])
                self.assertFalse(receipt["redistribution_allowed_by_tool"])
                self.assertEqual((output / "source_frames" / "shime38.png").read_bytes(),
                                 frames[38])
                self.assertEqual((output / "action" / "stand_0.png").read_bytes(),
                                 frames[1])
                self.assertNotIn("patpat", json.loads(
                    (output / "act_conf.json").read_text("utf-8")))
                second = install_pinned_react_shimeji(
                    source, roles, profile="genshin_kaveh", confirmed=True)
                self.assertNotEqual(output, second)
                self.assertTrue(output.exists())

    def test_reject_pointer_bad_hash_wrong_id_or_other_characters(self):
        with tempfile.TemporaryDirectory() as td:
            source, good = self.setup_fixture(td)
            wrong = (good[0], "f" * 64, good[2], good[3], good[4])
            with patch.dict(CANDIDATES, {"genshin_kaveh": wrong}):
                with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                    decode_pinned_frames(source, profile="genshin_kaveh")
            with patch.dict(CANDIDATES, {"genshin_kaveh": good}):
                with self.assertRaisesRegex(ValueError, "Only explicitly pinned"):
                    decode_pinned_frames(source, profile="genshin_unknown")
                source.write_text(
                    "version https://git-lfs.github.com/spec/v1\n"
                    "oid sha256:00\nsize 0\n", encoding="utf-8")
                text = source.read_bytes()
                pinned_pointer = (good[0], hashlib.sha256(text).hexdigest(),
                                  len(text), good[3], good[4])
            with patch.dict(CANDIDATES, {"genshin_kaveh": pinned_pointer}):
                with self.assertRaisesRegex(ValueError, "only a Git LFS pointer"):
                    decode_pinned_frames(source, profile="genshin_kaveh")
            with self.assertRaisesRegex(ValueError, "does not match"):
                _parse_only_literal_source(_fake_upstream_source(), expected_id="amber-ef95b4")

    def test_reject_bad_coordinates_and_bad_base64_without_running_script(self):
        source = _fake_upstream_source()
        source = source.replace(b'"width": 48', b'"width": -1', 1)
        with self.assertRaisesRegex(ValueError, "Frame rectangle"):
            with tempfile.TemporaryDirectory() as td:
                path = Path(td) / "index.ts"
                path.write_bytes(source + b"\nraise RuntimeError('never execute me');")
                content = path.read_bytes()
                pin = ("kaveh-2f46f2", hashlib.sha256(content).hexdigest(),
                       len(content), "a"*40, "b"*40)
                with patch.dict(CANDIDATES, {"genshin_kaveh": pin}):
                    decode_pinned_frames(path, profile="genshin_kaveh")


if __name__ == "__main__":
    unittest.main()
