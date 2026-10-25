"""Pure searchable view over a read-only 125-character capability report.

Every returned row references local evidence from character_progress(); no
new source art, voice or physical-device acceptance is inferred.
"""
from __future__ import annotations

try:
    from .genshin_roster import GENSHIN_ROSTER
except ImportError:
    from genshin_roster import GENSHIN_ROSTER


def _keywords(entry):
    identity = str(entry["id"])
    names = [str(entry["name"]), identity, identity.replace("_", " ")]
    if identity.startswith("genshin_"):
        known = GENSHIN_ROSTER.get(identity[len("genshin_"):])
        if known:
            names.append(str(known.get("english", "")))
    elif identity == "mascot_doro":
        names.extend(("Doro", "Dororong", "桃乐丝", "多萝"))
    elif identity == "mascot_guga":
        names.extend(("Guga", "咕嘎", "企鹅"))
    return " ".join(names).casefold()


def query_character_catalog(entries, text="", family="all", status="all", source_lookup=None):
    """Rank personal art before demo art; filter locally with no side effects.

    family: all / genshin / mascot
    status: all / personal / demo / missing / source / source_missing
    source_lookup: an explicit read-only map of pinned provenance entries; never
    conflate candidates with installed or visually verified art.
    """
    if family not in ("all", "genshin", "mascot"):
        raise ValueError("Unknown character family filter")
    if status not in ("all", "personal", "demo", "missing", "source", "source_missing"):
        raise ValueError("Unknown character status filter")
    if status in ("source", "source_missing") and source_lookup is None:
        raise ValueError("Creator-source filter needs the verified source registry")
    source_lookup = source_lookup or {}
    words = str(text or "").strip().casefold().split()
    found = []
    for row in entries:
        if family != "all" and row["family"] != family:
            continue
        source = source_lookup.get(row["id"], {})
        if status == "source" and not source.get("source_found", False):
            continue
        if status == "source_missing" and (row["family"] != "genshin" or source.get("source_found", False)):
            continue
        if status == "personal" and not row["personal_art_structurally_installed"]:
            continue
        if status == "demo" and not row["native_original_demo"]:
            continue
        if status == "missing" and row["native_preview_ready"]:
            continue
        searchable = _keywords(row)
        if any(part not in searchable for part in words):
            continue
        found.append(row)
    return sorted(found, key=lambda r: (
        0 if r["personal_art_structurally_installed"] else
        1 if source_lookup.get(r["id"], {}).get("source_found") else
        2 if r["native_original_demo"] else 3,
        source_lookup.get(r["id"], {}).get("recommended_source", {}).get("preference_order", 3)
        if source_lookup.get(r["id"], {}).get("recommended_source") else 3,
        r["family"] != "genshin", str(r["name"]).casefold(), str(r["id"])))


def describe_character_status(row):
    if row["personal_art_structurally_installed"]:
        return "个人素材已安装 · 原设和权利未验证"
    if row["native_original_demo"]:
        return "程序原创演示可用 · 非官方角色美术"
    return "仅有模板 · 暂无可播放动画"
