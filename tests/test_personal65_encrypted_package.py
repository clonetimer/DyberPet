"""Authenticated recipient-only offline personal bundle tests (no third-party art)."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import zipfile

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.exceptions import InvalidTag

from tools.personal65_encrypted_package import encrypt_file, decrypt_file


class EncryptedBundleTests(unittest.TestCase):
    def setup_fixture(self, root):
        src = root / "original.zip"
        with zipfile.ZipFile(src, "w") as z:
            z.writestr("res/role/SourceUser/anim.png", b"\x89PNG" + b"abc" * 13000)
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        prv = root / "private.pem"
        pub = root / "public.pem"
        prv.write_bytes(private.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()))
        pub.write_bytes(private.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo))
        return src, pub, prv

    def test_roundtrip_does_not_expose_artwork_in_ciphertext(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            src, pub, prv = self.setup_fixture(root)
            encrypted = root / "full.ekp"
            recovered = root / "recovered.zip"
            report = encrypt_file(src, encrypted, pub)
            self.assertTrue(report["ciphertext_only"])
            self.assertNotIn(b"SourceUser/anim.png", encrypted.read_bytes())
            outcome = decrypt_file(encrypted, recovered, prv)
            self.assertTrue(outcome["verified"])
            self.assertEqual(recovered.read_bytes(), src.read_bytes())

    def test_modified_ciphertext_refused_and_partial_deleted(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            src, pub, prv = self.setup_fixture(root)
            cipher = root / "encrypted.ekp"
            encrypt_file(src, cipher, pub)
            material = bytearray(cipher.read_bytes())
            material[-22] ^= 0x80
            cipher.write_bytes(material)
            target = root / "refuse.zip"
            with self.assertRaises(InvalidTag):
                decrypt_file(cipher, target, prv)
            self.assertFalse(target.exists())
            self.assertFalse((root / "refuse.zip.partial").exists())

    def test_output_never_overwritten(self):
        with TemporaryDirectory() as t:
            root = Path(t)
            src, pub, prv = self.setup_fixture(root)
            with self.assertRaises(FileExistsError):
                encrypt_file(src, src, pub)
            encrypted = root / "encrypted.ekp"
            encrypt_file(src, encrypted, pub)
            target = root / "existing.zip"
            target.write_bytes(b"preserve")
            with self.assertRaises(FileExistsError):
                decrypt_file(encrypted, target, prv)
            self.assertEqual(target.read_bytes(), b"preserve")


if __name__ == "__main__":
    unittest.main()
