"""Doro / Genshin / Arrisa fidelity regression tests, no copyrighted media."""
import json
import tempfile
import unittest
import wave
from pathlib import Path

from DyberPet.assistant.character_profiles import PROFILES, resolve_profile
from DyberPet.assistant.character_fidelity import (
    FidelityError, inspect_character_role, inspect_guga_role,
)
from DyberPet.assistant.character_audio import (
    manifest_for, register, read, play,
)
from DyberPet.assistant.persona import PERSONAS


class ProfileCatalogTests(unittest.TestCase):
    def test_all_key_roles_have_nonempty_dossiers(self):
        names = ("guga", "doro", "paimon", "nahida", "klee", "furina", "arrisa")
        self.assertEqual(set(PROFILES), set(names))
        for key, profile in PROFILES.items():
            with self.subTest(role=key):
                self.assertGreaterEqual(len(profile.visual_checks), 2)
                self.assertGreaterEqual(len(profile.motion_checks), 3)
                self.assertGreaterEqual(len(profile.audio_checks), 1)
                self.assertGreaterEqual(len(profile.references), 1)
                self.assertIn(key, PERSONAS)
                self.assertEqual(resolve_profile(profile.aliases[0]).key, key)

    def test_genuine_doro_is_not_replaced_with_dorothy(self):
        doro = PROFILES["doro"]
        self.assertTrue(any("四足" in c for c in doro.visual_checks))
        self.assertTrue(any("粉发" in c for c in doro.visual_checks))
        self.assertEqual(resolve_profile("Dororong").key, "doro")
        self.assertIsNone(resolve_profile("Dorothy"))

    def test_variants_and_unrelated_names_are_separate(self):
        self.assertEqual(resolve_profile("Paimon-Q版").key, "paimon")
        self.assertEqual(resolve_profile("纳西妲_2").key, "nahida")
        self.assertEqual(resolve_profile("Furina (v2)").key, "furina")
        self.assertIsNone(resolve_profile("unrelatedGugaHack"))
        self.assertIsNone(resolve_profile("../Doro"))
        self.assertIsNone(resolve_profile("Kitty"))

    def test_paimon_uses_floating_reference(self):
        self.assertTrue(PROFILES["paimon"].floating)
        self.assertFalse(PROFILES["klee"].floating)


class CharacterAuditTests(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.root = Path(holder.name)

    def make_role(self, name):
        root = self.root / name
        (root / "action").mkdir(parents=True)
        (root / "act_conf.json").write_text(
            json.dumps({"default": {"images": "stand"}}), encoding="utf-8")
        (root / "pet_conf.json").write_text(
            json.dumps({"width": 64, "height": 72}), encoding="utf-8")
        return root

    def test_per_role_audits_do_not_claim_fidelity(self):
        for role in ("Doro", "派蒙", "纳西妲", "可莉", "芙宁娜", "阿丽莎"):
            with self.subTest(role=role):
                output = inspect_character_role(self.make_role(role), role)
                self.assertEqual(output["authenticity_status"], "not_verified")
                self.assertGreater(len(output["expected_visual_checks"]), 1)
                self.assertIn("profile_key", output)
                self.assertTrue(output["issues"])
                self.assertTrue(output["reference_pages"])

    def test_old_guga_api_remains_valid(self):
        folder = self.make_role("Guga")
        self.assertEqual(inspect_guga_role(folder)["profile_key"], "guga")
        self.assertEqual(inspect_guga_role(folder)["target"],
                         "guga_penguin_fan_derivative")

    def test_unknown_profile_rejected(self):
        with self.assertRaisesRegex(FidelityError, "No registered"):
            inspect_character_role(self.make_role("Kitty"), "Kitty")


class PerRoleWavTests(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.root = Path(holder.name)
        self.wav = self.root / "synthetic.wav"
        with wave.open(str(self.wav), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(bytes(16000))
        self.records = self.root / "records"

    def record(self, role):
        return register(role, self.wav, "Original synthetic test author",
                        "https://example.com/synthetic",
                        acknowledged_local_rights=True,
                        manifest_root=self.records)

    def test_different_characters_have_separate_records(self):
        one = self.record("Doro")
        two = self.record("派蒙")
        self.assertNotEqual(manifest_for("Doro", root=self.records),
                            manifest_for("派蒙", root=self.records))
        self.assertEqual(read("Doro", manifest_root=self.records)["profile_key"], "doro")
        self.assertEqual(read("派蒙", manifest_root=self.records)["profile_key"], "paimon")
        self.assertFalse(one["distribution_allowed"])
        self.assertFalse(two["voice_identity_verified"])

    def test_swap_manifest_blocks_cross_role(self):
        self.record("Doro")
        doro = manifest_for("Doro", root=self.records)
        paimon = manifest_for("派蒙", root=self.records)
        paimon.write_bytes(doro.read_bytes())
        with self.assertRaisesRegex(FidelityError, "another role"):
            read("派蒙", manifest_root=self.records)

    def test_rights_and_fingerprint_required(self):
        with self.assertRaisesRegex(FidelityError, "permission"):
            register("Doro", self.wav, "author", "https://example.com",
                     acknowledged_local_rights=False, manifest_root=self.records)
        self.record("Doro")
        with wave.open(str(self.wav), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(16000)
            audio.writeframes(bytes(18000))
        with self.assertRaisesRegex(FidelityError, "changed"):
            read("Doro", manifest_root=self.records)
        with self.assertRaisesRegex(FidelityError, "changed"):
            play("Doro", manifest_root=self.records)

    def test_unknown_character_not_registered(self):
        with self.assertRaises(FidelityError):
            self.record("OtherName")
        with self.assertRaises(FidelityError):
            manifest_for("../Doro", root=self.records)


if __name__ == "__main__":
    unittest.main()
