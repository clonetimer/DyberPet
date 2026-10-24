"""Local, user-provided Guga signature sound (NOT voice cloning or speech TTS).

No sound is bundled or fetched from a video. Registration stores only an
absolute local WAV path, attribution, source URL and checksum. A checked clip
is allowed for user-initiated preview, never auto-played as proof of identity.
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
from .preferences import default_preference_path

MAX_MANIFEST = 8192


def default_sound_manifest() -> Path:
    return default_preference_path().parent / "guga_local_sound.json"


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as inp:
        for chunk in iter(lambda: inp.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record_local_clip(
    clip_path: str | Path, creator: str, source_url: str,
    *, acknowledged_local_rights: bool, destination: str | Path | None = None
) -> dict:
    """Records a human assertion, not a legal determination or distribution grant."""
    if acknowledged_local_rights is not True:
        raise FidelityError("Local audio use must be explicitly confirmed")
    creator = creator.strip()
    parsed = urlsplit(source_url.strip())
    if not creator or len(creator) > 120 or parsed.scheme != "https" or not parsed.netloc:
        raise FidelityError("Provide the actual creator name and HTTPS source page")
    clip = Path(clip_path).expanduser()
    props = inspect_wav(clip)
    record = {
        "schema_version": 1, "character": "guga",
        "clip": str(clip.resolve()), "sha256": _hash_file(clip),
        "creator": creator, "source_url": source_url.strip(),
        "rights": "user_attested_local_preview_only",
        "distribution_allowed": False,
        "voice_identity_verified": False,
        "wave": props,
    }
    manifest = Path(destination) if destination is not None else default_sound_manifest()
    payload = json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8")
    if len(payload) > MAX_MANIFEST:
        raise FidelityError("Audio metadata is too long")
    manifest.parent.mkdir(parents=True, exist_ok=True)
    if manifest.is_symlink():
        raise FidelityError("Refusing to replace a symlinked sound manifest")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", dir=str(manifest.parent), prefix=".guga-", suffix=".tmp",
            delete=False
        ) as fd:
            temporary = Path(fd.name)
            fd.write(payload)
            fd.flush()
            os.fsync(fd.fileno())
        temporary.replace(manifest)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()
    return record


def load_local_clip(destination: str | Path | None = None) -> dict | None:
    manifest = Path(destination) if destination is not None else default_sound_manifest()
    if not manifest.exists():
        return None
    if manifest.is_symlink() or manifest.stat().st_size > MAX_MANIFEST:
        raise FidelityError("Invalid local sound manifest")
    try:
        data = json.loads(manifest.read_text("utf-8"))
    except (ValueError, OSError, UnicodeError) as exc:
        raise FidelityError("Local sound manifest is corrupt") from exc
    if (not isinstance(data, dict) or data.get("schema_version") != 1
            or data.get("character") != "guga"
            or data.get("rights") != "user_attested_local_preview_only"
            or data.get("distribution_allowed") is not False):
        raise FidelityError("Unsupported or unsafe local sound record")
    clip = Path(data.get("clip", ""))
    props = inspect_wav(clip)
    if data.get("sha256") != _hash_file(clip):
        raise FidelityError("WAV changed since registration; re-register before playing")
    data["wave"] = props
    return data


def play_local_clip(destination: str | Path | None = None) -> str:
    record = load_local_clip(destination)
    if not record:
        raise FidelityError("No locally authorized Guga audio is configured")
    file = Path(record["clip"])
    if os.name == "nt":
        import winsound
        # Synchronous playback runs inside the assistant's worker thread.
        winsound.PlaySound(str(file),
                           winsound.SND_FILENAME | winsound.SND_SYNC | winsound.SND_NODEFAULT)
    else:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise FidelityError("Linux preview requires the optional sounddevice package") from exc
        with wave.open(str(file), "rb") as inp:
            with sd.RawOutputStream(
                samplerate=inp.getframerate(), channels=inp.getnchannels(),
                dtype="int16"
            ) as device:
                while True:
                    part = inp.readframes(4096)
                    if not part:
                        break
                    device.write(part)
    return record["creator"]
