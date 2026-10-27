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
    if profile not in REVIEWED_EXAMPLES:
        return None
    item = REVIEWED_EXAMPLES[profile]
    return {
        "profile": profile,
        "name": item["name"],
        "look_for": list(item["look_for"]),
        "specific_review_risks": list(item["specific_review_risks"]),
        "reference": f"https://github.com/{item['source_repo']}/blob/"
                     f"{item['source_commit']}/{item['inspected_source_file']}",
        "inspected_png_git_blob": item["source_png_git_blob"],
        "reference_is_an_example_not_a_exact_version_match": True,
        "original_likeness_automatically_approved": False,
        "all_actions_visually_checked": False,
    }


def cue_text(record):
    """Human-facing guidance, never a visual approval badge."""
    if record is None:
        return "该人物尚无独立外观特征检查条目；请对照可信原设图片，逐帧检查发型、服饰、头身比例和动态。"
    return (record["name"] + " · 原画身份对照重点：" +
            "、".join(record["look_for"]) + "。需重点复核：" +
            "、".join(record["specific_review_risks"]) +
            "。这是核对提示，不表示本机原画已符合原设。")
