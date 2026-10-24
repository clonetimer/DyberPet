"""Character-scoped local signature audio preview (not voice identity / free-form TTS).

Each known role gets an independent safe manifest. Only the user can approve
a specific licensed WAV and press Play; no media or model weights are bundled.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import wave
from pathlib import Path
from urllib.parse import urlsplit

from .character_fidelity import FidelityError, inspect_wav
from .native_bridge import sha256_file
from .character_profiles import resolve_profile
from .preferences import default_preference_path

MAX_RECORD = 8192


def manifest_for(character_name: str, *, root: Path | None = None) -> Path:
    profile = resolve_profile(character_name)
    if profile is None:
        raise FidelityError("Unknown character profile; cannot register sound")
    location = (Path(root) if root is not None
                else default_preference_path().parent / "character_sounds")
    return location / (profile.key + ".json")


def digest(path: Path) -> str:
    return sha256_file(path)


def register(character_name: str, clip_path: str | Path, creator: str, source_url: str,
             *, acknowledged_local_rights: bool,
             manifest_root: Path | None = None) -> dict:
    profile = resolve_profile(character_name)
    if profile is None:
        raise FidelityError("Unknown character profile")
    if acknowledged_local_rights is not True:
        raise FidelityError("Explicit local sound usage permission is required")
    creator = creator.strip()
    url = urlsplit(source_url.strip())
    if (not creator or len(creator) > 120 or
            url.scheme != "https" or not url.netloc):
        raise FidelityError("Provide actual creator and HTTPS work-specific source URL")
    clip = Path(clip_path).expanduser()
    metadata = inspect_wav(clip)
    record = {
        "schema_version": 1, "profile_key": profile.key,
        "clip": str(clip.resolve()), "sha256": digest(clip),
        "creator": creator, "source_url": source_url.strip(),
        "rights": "user_attested_local_preview_only",
        "distribution_allowed": False,
        "voice_identity_verified": False,
        "wave": metadata,
    }
    destination = manifest_for(character_name, root=manifest_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_symlink():
        raise FidelityError("Sound manifest is a symbolic link")
    payload = json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8")
    if len(payload) > MAX_RECORD:
        raise FidelityError("Sound record too large")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="wb", dir=str(destination.parent),
                prefix=".sound-", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary), str(destination))
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return record


def read(character_name: str, *, manifest_root: Path | None = None) -> dict | None:
    profile = resolve_profile(character_name)
    if profile is None:
        raise FidelityError("Unknown character profile")
    recordfile = manifest_for(character_name, root=manifest_root)
    if not recordfile.exists():
        return None
    if recordfile.is_symlink() or recordfile.stat().st_size > MAX_RECORD:
        raise FidelityError("Invalid sound record")
    try:
        record = json.loads(recordfile.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise FidelityError("Corrupt sound record") from exc
    if (not isinstance(record, dict) or record.get("schema_version") != 1
            or record.get("profile_key") != profile.key
            or record.get("rights") != "user_attested_local_preview_only"
            or record.get("distribution_allowed") is not False
            or record.get("voice_identity_verified") is not False):
        raise FidelityError("Sound belongs to another role or has unsafe metadata")
    clip = Path(record.get("clip") or "")
    metadata = inspect_wav(clip)
    if digest(clip) != record.get("sha256"):
        raise FidelityError("Local WAV changed; re-register before playback")
    record["wave"] = metadata
    return record


def play(character_name: str, *, manifest_root: Path | None = None) -> str:
    record = read(character_name, manifest_root=manifest_root)
    if record is None:
        raise FidelityError("No authorized local sound registered for this character")
    path = Path(record["clip"])
    if os.name == "nt":
        import winsound
        winsound.PlaySound(
            str(path), winsound.SND_FILENAME | winsound.SND_SYNC |
            winsound.SND_NODEFAULT)
    else:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise FidelityError("Install optional sounddevice to preview WAV on Linux") from exc
        with wave.open(str(path), "rb") as inp:
            with sd.RawOutputStream(samplerate=inp.getframerate(),
                                    channels=inp.getnchannels(), dtype="int16") as speaker:
                while True:
                    block = inp.readframes(4096)
                    if not block:
                        break
                    speaker.write(block)
    return record["creator"]
