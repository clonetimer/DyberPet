"""R34: offline, image-grounded, no-unreviewed-publication contact sheet."""
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from tools.turnaround_gate import capture, TurnaroundError
from tools.turnaround_review_card import render_review_card, CARD_WIDTH, CARD_HEIGHT
from tools.character_pipeline import init_case, attach_turnaround, turnaround_card


class TurnaroundReviewCardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        paths = []
        for idx, name in enumerate(("front", "side", "back")):
            p = self.root / (name + ".png")
            img = Image.new("RGBA", (128 + idx * 16, 210), (0, 0, 0, 0))
            ImageDraw.Draw(img).ellipse((20 + idx, 25, 80 + idx, 150),
                                        fill=(50 + idx * 50, 90, 160, 255))
            img.save(p)
            paths.append(p)
        self.paths = paths
        self.sheet = capture(
            *paths, reference_url="https://example.org/design/single-version",
            artist="QA author", variant="chibi_v1")

    def test_generates_private_card_without_approving_likeness(self):
        result = render_review_card("doro_q01", self.sheet, self.root / "reviews")
        out = Path(result["review_card"])
        self.assertTrue(out.exists())
        self.assertEqual(out.parent, self.root / "reviews")
        with Image.open(out) as img:
            self.assertEqual(img.size, (CARD_WIDTH, CARD_HEIGHT))
            self.assertEqual(img.format, "PNG")
        self.assertEqual(len(result["source_sha256"]), 3)
        self.assertEqual(len(result["sha256"]), 64)
        self.assertIn("awaiting", result["status"])
        self.assertEqual(self.sheet["review"], {})

    def test_rejects_changed_source_instead_of_making_stale_card(self):
        Image.new("RGB", (200, 210), "magenta").save(self.paths[1])
        with self.assertRaisesRegex(TurnaroundError, "changed"):
            render_review_card("doro_q01", self.sheet, self.root / "reviews")
        self.assertFalse((self.root / "reviews").exists())

    def test_does_not_overwrite_old_review_image(self):
        result = render_review_card("doro_q01", self.sheet, self.root / "reviews")
        with self.assertRaises(FileExistsError):
            render_review_card("doro_q01", self.sheet, self.root / "reviews")
        self.assertTrue(Path(result["review_card"]).exists())

    def test_pipeline_exposes_local_card_without_implicit_approval(self):
        workspace = self.root / "workspace"
        case = init_case(workspace, "doro_q01", "Doro", "bilibili",
                         "https://www.bilibili.com/", "frames")
        attach_turnaround(
            case, front=self.paths[0], side=self.paths[1], back=self.paths[2],
            reference_url=self.sheet["reference_url"],
            artist=self.sheet["artist"], variant=self.sheet["variant"])
        result = turnaround_card(case)
        self.assertTrue(Path(result["review_card"]).is_file())
        self.assertEqual(Path(result["review_card"]).parent,
                         workspace / "review_cards")
        self.assertIn("awaiting", result["status"])

    def test_rejects_invalid_candidate(self):
        with self.assertRaisesRegex(TurnaroundError, "candidate"):
            render_review_card("../../outside", self.sheet, self.root / "reviews")


if __name__ == "__main__":
    unittest.main()
