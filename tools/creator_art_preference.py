"""Non-deceptive ordering of original-creator character artwork.

Ranks SOURCE PRESENTATION preferences, not actual likeness or visual quality.
Detailed native DyberPet sources shown first; uninspected 2D atlases are not
automatically awarded A quality; user-accepted Shimeji is a valid fallback.
"""
from __future__ import annotations

SOURCE_STYLE = {
    "native": (0, "精细 Q 版优先", "detailed_native_candidate"),
    "codex": (1, "原作者图集·细节待核对", "unreviewed_codex_atlas"),
    "independent_codex": (1, "独立作者图集·细节待核对", "unreviewed_codex_atlas"),
    "codexpetdb_zip": (1, "第三方 ZIP 来源SHA已核验·原设待看图", "unreviewed_codex_atlas"),
    "react_lfs": (1, "Git LFS 原始PNG已校验·部分动作待验收", "unreviewed_codex_atlas"),
    "gmcy_diona": (1, "GMCY 迪奥娜170帧原作·动作语义待验收", "unreviewed_codex_atlas"),
    "gmcy_keqing": (1, "GMCY 刻晴92帧原作·六组动作待人工验收", "unreviewed_codex_atlas"),
    "shimeji": (2, "小型 Shimeji·可接受备选", "acceptable_small_shimeji"),
    "nano_shimeji": (2, "小型 Shimeji·可接受备选", "acceptable_small_shimeji"),
    "pinned_eula_creator": (2, "原作者扩展版Shimeji·原设待人工核对", "acceptable_small_shimeji"),
}
INSTALL_MODE_PROVIDER = {
    "artist_genshin": "native",
    "artist_codex": "codex",
    "artist_external_codex": "independent_codex",
    "pinned_codexpetdb": "codexpetdb_zip",
    "react_shimeji_lfs": "react_lfs",
    "gmcy_diona_original": "gmcy_diona",
    "gmcy_keqing_original": "gmcy_keqing",
    "artist_shimeji": "shimeji",
    "artist_nano": "nano_shimeji",
    "pinned_kaveh_shimeji": "shimeji",
    "pinned_eula_shimeji": "pinned_eula_creator",
}


def source_style(provider):
    try:
        order, label, kind = SOURCE_STYLE[provider]
    except KeyError as exc:
        raise ValueError("Unrecognized real-artist source provider: " + str(provider)) from exc
    return {"preference_order": order, "style_label": label,
            "style_group": kind, "visual_grade": None,
            "visual_qa_status": "pending_human_review"}


def install_preference(mode):
    """Existing native original art first, source-identity before generic art."""
    try:
        return SOURCE_STYLE[INSTALL_MODE_PROVIDER[mode]][0]
    except KeyError as exc:
        raise ValueError("Unrecognized artist install mode") from exc


def candidate_character_style(candidates):
    """Display user preference without granting unseen source a quality grade."""
    if not candidates:
        return "尚无真实作者素材", "missing"
    kinds = {item["style_group"] for item in candidates}
    if "detailed_native_candidate" in kinds:
        return "精细 Q 版优先候选（未人工验收）", "detailed_candidate"
    if "unreviewed_codex_atlas" in kinds:
        return "作者图集待预览（可能为精细或像素版）", "atlas_review"
    return "Shimeji 小型动画候选（未人工验收）", "small_candidate"
