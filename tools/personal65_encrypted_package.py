#!/usr/bin/env python3
"""Cloud-to-one-user encrypted DyberPet offline package.

The PUBLIC recipient key can live in GitHub. The private key must NEVER be
committed, logged, put in an Actions artifact or uploaded to any Git service.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import struct
import sys

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

MAGIC = b"DYP65E01"
CHUNK = 1024 * 1024
MAX_INPUT = 4 * 1024**3


def _safe_paths(src, dest):
    a = Path(src).expanduser()
    b = Path(dest).expanduser()
    if a.is_symlink() or not a.is_file():
        raise ValueError("Input is missing or a symbolic link")
    if b.is_symlink() or b.exists():
        raise FileExistsError("Output already exists; refusing overwrite")
    if not b.parent.is_dir():
        raise ValueError("Output parent directory missing")
    if a.resolve() == b.resolve():
        raise ValueError("Output cannot overwrite input")
    return a, b


def encrypt_file(src, output, public_key_path):
    original, dest = _safe_paths(src, output)
    if original.stat().st_size > MAX_INPUT:
        raise ValueError("Too large for bounded personal package")
    public_path = Path(public_key_path)
    if public_path.is_symlink() or public_path.stat().st_size > 8192:
        raise ValueError("Invalid public key")
    public = serialization.load_pem_public_key(public_path.read_bytes())
    key = secrets.token_bytes(32)
    nonce = secrets.token_bytes(12)
    wrapped = public.encrypt(
        key, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                          algorithm=hashes.SHA256(), label=None))
    if len(wrapped) > 8192:
        raise ValueError("Unexpected RSA key length")
    temporary = dest.with_name(dest.name + ".partial")
    if temporary.exists() or temporary.is_symlink():
        raise FileExistsError("Temporary file exists")
    try:
        with original.open("rb") as reader, temporary.open("xb") as writer:
            writer.write(MAGIC + struct.pack(">H", len(wrapped)) + wrapped + nonce)
            cipher = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
            for part in iter(lambda: reader.read(CHUNK), b""):
                writer.write(cipher.update(part))
            writer.write(cipher.finalize())
            writer.write(cipher.tag)
        os.replace(temporary, dest)
    finally:
        if temporary.exists():
            temporary.unlink()
    return {"algorithm": "RSA-OAEP-SHA256 + AES-256-GCM",
            "input_bytes": original.stat().st_size, "encrypted_bytes": dest.stat().st_size,
            "ciphertext_only": True, "private_key_included": False}


def decrypt_file(src, output, private_key_path):
    encrypted, dest = _safe_paths(src, output)
    secret_path = Path(private_key_path).expanduser()
    if secret_path.is_symlink() or not secret_path.is_file() or secret_path.stat().st_size > 8192:
        raise ValueError("Private key file missing or invalid")
    private = serialization.load_pem_private_key(secret_path.read_bytes(), password=None)
    size = encrypted.stat().st_size
    tmp = dest.with_name(dest.name + ".partial")
    if tmp.exists() or tmp.is_symlink():
        raise FileExistsError("Temporary decrypted ZIP already exists")
    with encrypted.open("rb") as inp:
        if inp.read(8) != MAGIC:
            raise ValueError("Encrypted DyberPet package magic mismatch")
        n = struct.unpack(">H", inp.read(2))[0]
        if not 256 <= n <= 8192:
            raise ValueError("Invalid RSA-encrypted key length")
        wrapped = inp.read(n)
        nonce = inp.read(12)
        if len(wrapped) != n or len(nonce) != 12 or size < (8 + 2 + n + 12 + 16):
            raise ValueError("Encrypted package incomplete")
        key = private.decrypt(
            wrapped, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()),
                                  algorithm=hashes.SHA256(), label=None))
        if len(key) != 32:
            raise ValueError("Invalid AES key")
        payload_at = inp.tell()
        payload_len = size - payload_at - 16
        if payload_len > MAX_INPUT:
            raise ValueError("Encrypted package exceeds size limit")
        inp.seek(-16, os.SEEK_END)
        tag = inp.read(16)
        inp.seek(payload_at)
        cipher = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
        try:
            with tmp.open("xb") as out:
                remaining = payload_len
                while remaining:
                    part = inp.read(min(CHUNK, remaining))
                    if not part:
                        raise ValueError("Truncated encrypted package")
                    out.write(cipher.update(part))
                    remaining -= len(part)
                out.write(cipher.finalize())  # authenticate BEFORE publishing ZIP
            with tmp.open("rb") as f:
                if f.read(2) != b"PK":
                    raise ValueError("Decrypted output is not ZIP")
            os.replace(tmp, dest)
        finally:
            if tmp.exists():
                tmp.unlink()
    return {"verified": True, "decrypted_zip": str(dest),
            "size_bytes": dest.stat().st_size, "key_not_embedded": True}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("mode", choices=("encrypt", "decrypt"))
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--key", type=Path, required=True)
    a = p.parse_args(argv)
    try:
        if a.mode == "encrypt":
            result = encrypt_file(a.input, a.output, a.key)
        else:
            result = decrypt_file(a.input, a.output, a.key)
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, InvalidTag) as e:
        p.exit(2, "Encrypted personal pack failed: " + type(e).__name__ + ": " + str(e)[:220] + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
