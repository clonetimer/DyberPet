"""Read-only artist-sprite appearance cues for human side-by-side inspection.

These cues were assembled from three *actual* pinned source default PNGs.
They are not a neural/automatic likeness classifier, and all grades remain
human-unreviewed until the user compares the character reference and EVERY
installed sprite frame. No artwork, sound, or official reference is bundled.
"""
from __future__ import annotations

from pathlib import Path

# Anchors are original Git blobs for the actual inspected PNGs, not license,
# avatar-fidelity or whole-animation approvals.
REVIEWED_EXAMPLES = {
    "genshin_nahida": {
        "name": "纳西妲",
        "source_repo": "ChaozhongLiu/DyberPet_GenshinImpact",
        "source_commit": "0789950b81802cc51ebeeecfc24be16aaee16e74",
        "inspected_source_file": "res/role/纳西妲/action/hx_0.png",
        "source_png_git_blob": "9d6893fd9304ef7c8d011b0cac0e807e188c0a0d",
        "look_for": (
            "白色头发及绿色挑染", "鲜绿色眼睛", "枝叶形绿色头饰",
            "尖耳轮廓", "白绿金色服饰"),
        "specific_review_risks": ("发饰形状是否丢失", "头身比例是否圆润", "所有动作是否保持原本发色与服饰"),
    },
    "genshin_xiao": {
        "name": "魈",
        "source_repo": "ChaozhongLiu/DyberPet_GenshinImpact",
        "source_commit": "0789950b81802cc51ebeeecfc24be16aaee16e74",
        "inspected_source_file": "res/role/魈/action/stand_0.png",
        "source_png_git_blob": "111112768a305901213c54cf8efbbe68c934fc01",
        "look_for": (
            "深色短发与青绿色挑染", "额头菱形标记",
            "金色眼睛", "紫色与青绿色服饰"),
        "specific_review_risks": ("是否因缩放过小丢失面部识别特征", "动作中的头饰/手臂像素是否错位"),
    },
    "genshin_wanderer": {
        "name": "流浪者",
        "source_repo": "ChaozhongLiu/DyberPet_GenshinImpact",
        "source_commit": "0789950b81802cc51ebeeecfc24be16aaee16e74",
        "inspected_source_file": "res/role/流浪者/action/stand_0.png",
        "source_png_git_blob": "4467a4c6c41abcb41d61294292ad6b5231400b1c",
        "look_for": (
            "宽檐蓝色斗笠及悬挂饰带", "深色短发",
            "蓝紫色眼睛", "蓝黑服饰与装饰"),
        "specific_review_risks": ("斗笠和长饰带在拖拽时是否裁切", "同版本是否出现脱帽/错配人物"),
    },
}


# Four early Genshin templates live directly in chibi_profiles rather than
# the later GENSHIN_ROSTER. No extra creator PNG was personally inspected for
# these roster-only checklists (Nahida has the R8 independent example).
BASE_TEMPLATE_CUES = {
    "genshin_paimon": {
        "visual_checks": ("白色短发及深色星形发饰", "披风与金色装饰",
                          "漂浮姿态及衣装轮廓"),
        "motion_checks": ("漂浮待机时头饰是否错位", "说话/动作是否和静态立牌区分"),
    },
    "genshin_klee": {
        "visual_checks": ("红色帽子与白色四叶草图案", "浅金短发及精灵耳",
                          "红白童装与小背包"),
        "motion_checks": ("跑跳动作的不同可见姿态", "帽子、书包有无裁断"),
    },
    "genshin_furina": {
        "visual_checks": ("蓝白双配色发型", "蓝白法庭礼服与礼帽",
                          "蓝色饰物、长燕尾装饰"),
        "motion_checks": ("礼帽/服装装饰的多帧完整性", "是否有不同人物版本混入"),
    },
    "genshin_nahida": {
        "visual_checks": REVIEWED_EXAMPLES["genshin_nahida"]["look_for"],
        "motion_checks": REVIEWED_EXAMPLES["genshin_nahida"]["specific_review_risks"],
    },
}


def cues_for_local_role(role_root, folder):
    """Provide informative cues only for a source-bound installed Genshin role.

    Do not infer identity from a folder name or a caller-provided string. A
    genuine import receipt/verified binding is required. This function
    intentionally does not read or assign any human-approval verdict.
    """
    from tools.character_interaction_coverage import _safe_installed_role
    from tools.genshin_library import _profile_of
    from tools.genshin_role_bindings import binding_status, load_bindings
    from tools.role_family import known_mascot_family

    root = Path(role_root).expanduser()
    role = _safe_installed_role(root, folder)
    if known_mascot_family(role) is not None:
        return None
    if ((role / "BUILTIN_CHIBI_DEMO.json").exists() or
            (role / "BUILTIN_MASCOT_DEMO.json").exists()):
        return None
    profile = _profile_of(role)
    if profile is None:
        profile = binding_status(role, load_bindings(root).get(folder))
    # Templates cover the full 123-person selection registry, but supply only
    # human checklist hints: they are not artwork inspection evidence.
    from tools.genshin_roster import GENSHIN_ROSTER
    if not isinstance(profile, str) or not profile.startswith("genshin_"):
        return None
    dossier = GENSHIN_ROSTER.get(profile[len("genshin_"):])
    if dossier is None:
        from tools.chibi_profiles import CHIBI_PROFILES
        base = BASE_TEMPLATE_CUES.get(profile)
        if base is None or profile not in CHIBI_PROFILES:
            return None
        dossier = {"name": CHIBI_PROFILES[profile]["name"], **base}
    example = REVIEWED_EXAMPLES.get(profile)
    if example is None:
        return {
            "profile": profile, "name": dossier["name"],
            "look_for": list(dossier.get("visual_checks", ())),
            "specific_review_risks": list(dossier.get("motion_checks", ())),
            "reference": None, "inspected_png_git_blob": None,
            "checklist_origin": "roster_template_not_independent_png_inspection",
            "reference_is_an_example_not_a_exact_version_match": False,
            "original_likeness_automatically_approved": False,
            "all_actions_visually_checked": False,
        }
    return {
        "profile": profile,
        "name": example["name"],
        "look_for": list(example["look_for"]),
        "specific_review_risks": list(example["specific_review_risks"]),
        "reference": f"https://github.com/{example['source_repo']}/blob/"
                     f"{example['source_commit']}/{example['inspected_source_file']}",
        "inspected_png_git_blob": example["source_png_git_blob"],
        "checklist_origin": "one_independently_opened_pinned_source_png_example",
        "reference_is_an_example_not_a_exact_version_match": True,
        "original_likeness_automatically_approved": False,
        "all_actions_visually_checked": False,
    }


def cue_text(record):
    """Human-facing guidance, never a visual approval badge."""
    if record is None:
        return "未知角色或未绑定来源；请对照可靠原设图片逐帧检查发型、服饰、头身比例和动态。"
    if record["checklist_origin"] == "roster_template_not_independent_png_inspection":
        provenance = "角色模板的待核对要点（未直接检视该角色作者PNG）："
    else:
        provenance = "已直接查看过一份固定来源样本PNG；本机版本仍须逐帧对照："
    return (record["name"] + " · " + provenance +
            "、".join(record["look_for"]) + "。动作检查：" +
            "、".join(record["specific_review_risks"]) +
            "。以上不代表本机版本形象、动态或原设符合性验收通过。")
