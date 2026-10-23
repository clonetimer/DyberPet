"""Pure clip-resolution tests; no bpy runtime required."""
import unittest

from tools.chibi_clip_map import choose_clips, normalize

class ClipMapTest(unittest.TestCase):
    def test_names_and_case_insensitivity(self):
        chosen=choose_clips(("idle","left_walk","right_walk","wave"),
                            ["Idle","Walk-Left","RightWalk","WAVING"])
        self.assertEqual(chosen,{"idle":"Idle","left_walk":"Walk-Left",
                                 "right_walk":"RightWalk","wave":"WAVING"})

    def test_no_silent_walk_mapping(self):
        found=choose_clips(("idle","left_walk","right_walk"),["Idle","Walk"])
        self.assertEqual(found,{"idle":"Idle"})

    def test_explicit_mapping_and_multiple_object_tracks(self):
        chosen=choose_clips(("idle","wave"), ["ArmsWave","ArmsWave","Stand"],
                            overrides={"wave":"ArmsWave","idle":"Stand"})
        self.assertEqual(chosen["wave"],"ArmsWave")

    def test_reject_ambiguous_normalized_names(self):
        with self.assertRaisesRegex(ValueError,"Ambiguous"):
            choose_clips(("idle",), ["Idle","idle"])

    def test_reject_unknown_override(self):
        with self.assertRaisesRegex(ValueError,"not requested"):
            choose_clips(("idle",), ["Idle"], {"wave":"Idle"})

    def test_reject_one_clip_reused(self):
        with self.assertRaisesRegex(ValueError,"multiple actions"):
            choose_clips(("idle","wave"),["Idle"],
                         overrides={"wave":"Idle"})

    def test_limited_normalization(self):
        self.assertEqual(normalize("  Right-Walk  "),"right_walk")
        self.assertNotEqual(normalize("left_walk"),normalize("right_walk"))


if __name__ == "__main__":
    unittest.main()
