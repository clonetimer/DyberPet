"""Isolated, read-only-to-user acceptance for the bundled character importer.

A disposable, original geometrical PNG is created under a temporary folder.
No downloaded art, user files, role installation or network traffic is used.
"""
from __future__ import annotations

import tempfile
from pathlib import Path


def verify_portable_character_importer():
    """Exercise the same GIF/PNG converter the character management GUI calls."""
    from PIL import Image, ImageDraw
    from tools.character_pipeline import registry
    from tools.chibi_profiles import CHIBI_PROFILES
    from tools.import_chibi_animations import convert_animation_folder
    from tools.import_codex_pet import convert as codex_converter
    from tools.install_native_role import validate_native_role, install_native_role

    # Import the two remaining GUI paths too; only the synthetic frames path
    # needs to perform an actual conversion for this smoke gate.
    if not callable(codex_converter) or not callable(install_native_role):
        raise RuntimeError("Character importer entrypoints are missing")
    profiles = len(CHIBI_PROFILES)
    candidates = len(registry()["candidates"])
    if not profiles or "chibi" not in CHIBI_PROFILES:
        raise RuntimeError("Bundled Q-style character profiles are unavailable")

    with tempfile.TemporaryDirectory(prefix="dyberpet-import-smoke-") as td:
        root = Path(td)
        input_dir = root / "synthetic-source"
        input_dir.mkdir()
        art = Image.new("RGBA", (96, 112), (0, 0, 0, 0))
        pen = ImageDraw.Draw(art)
        pen.ellipse((20, 8, 75, 75), fill=(40, 145, 195, 255))
        pen.rectangle((35, 65, 61, 105), fill=(35, 100, 180, 255))
        art.save(input_dir / "idle_0.png")
        role = convert_animation_folder(
            input_dir, root / "output", folder="SyntheticImportCheck",
            name="CI synthetic", profile="chibi", author="DyberPet CI",
            license_name="original disposable geometry")
        result = validate_native_role(role)
        if result["actions"] < 1 or result["images"] < 1:
            raise RuntimeError("Converted role is missing playable actions")
        if not (role / "ANIMATION_PREVIEW.png").is_file():
            raise RuntimeError("Character converter did not create its preview")
        return {
            "ok": True,
            "profile_count": profiles,
            "source_registry_candidates": candidates,
            "synthetic_actions": result["actions"],
            "synthetic_frames": result["images"],
            "modified_user_roles": False,
            "third_party_art_included": False,
        }
