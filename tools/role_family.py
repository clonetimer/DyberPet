"""Read-only explicit source-family detection for local DyberPet roles.

Only source receipts establish role family. Directory names, sprite colors,
display names and similar appearance cues are never trusted as identity.
"""
from __future__ import annotations

import json
from pathlib import Path

MAX_RECEIPT_BYTES = 128 * 1024
KNOWN_MASCOTS = {"guga": "guga--circus", "doro": "doro--lingxiaotian"}
KNOWN_MASCOT_SOURCE_IDS = {
    "guga": frozenset(("guga--circus",)),
    "doro": frozenset(("doro--lingxiaotian", "doro--godxxy1229")),
}
DEMO_GENERATOR = "DyberPet-first-party-mascot-chibi-v1"


def _read_role_receipt(folder, name):
    path = Path(folder) / name
    if path.is_symlink():
        raise ValueError("Linked identity receipt is not permitted: " + name)
    if not path.exists():
        return None
    if not path.is_file() or path.stat().st_size > MAX_RECEIPT_BYTES:
        raise ValueError("Unsafe identity receipt: " + name)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Role identity receipt must be a JSON object: " + name)
    return data


def known_mascot_family(folder):
    """Return 'guga'/'doro'/None; reject contradictions, do not write files."""
    demo = _read_role_receipt(folder, "BUILTIN_MASCOT_DEMO.json")
    report = _read_role_receipt(folder, "IMPORT_REPORT.json")
    other = _read_role_receipt(folder, "PERSONAL_IMPORT.json")
    genshin = _read_role_receipt(folder, "BUILTIN_CHIBI_DEMO.json")

    identities = []
    if demo is not None:
        kind = demo.get("mascot")
        if (kind not in KNOWN_MASCOTS
                or demo.get("generator") != DEMO_GENERATOR
                or demo.get("original_geometry") is not True
                or demo.get("external_artist_sprite_included") is not False):
            raise ValueError("Invalid or contradictory mascot demo provenance")
        identities.append(kind)
    if report is not None and report.get("mascot_preset") is not None:
        kind = report["mascot_preset"]
        if (kind not in KNOWN_MASCOTS
                or report.get("source_manifest_id") not in KNOWN_MASCOT_SOURCE_IDS[kind]):
            raise ValueError("Invalid or unknown mascot creator source identity")
        identities.append(kind)
    if not identities:
        return None
    if len(set(identities)) != 1:
        raise ValueError("Conflicting Guga and Doro identity receipts")
    # Reject simultaneous Genshin claims instead of silently classifying one
    # library as valid and letting the other report a different owner.
    if genshin is not None:
        raise ValueError("Mascot source also claims Genshin artwork")
    if other is not None:
        # Guga/Doro now have PERSONAL_IMPORT provenance just like Codex art.
        # Accept only a matching mascot identity; never allow a Genshin
        # profile or another mascot's source ID to cross family boundaries.
        selected = other.get("selected_profile")
        source_id = other.get("source_id")
        if selected not in (None, identities[0]) or (
                source_id is not None and
                source_id not in KNOWN_MASCOT_SOURCE_IDS[identities[0]]):
            raise ValueError("Mascot source conflicts with personal/Genshin identity")
        if (report is not None and source_id is not None and
                source_id != report.get("source_manifest_id")):
            raise ValueError("Personal mascot source ID must match importer report")
        if selected is not None and other.get("source_kind") not in (
                None, "curated_creator_spritesheet"):
            raise ValueError("Mascot source kind conflicts with local provenance")
    if report is not None and isinstance(report.get("profile"), str) and (
            report["profile"].startswith("genshin_")):
        raise ValueError("Contradictory Genshin profile in mascot source")
    return identities[0]
