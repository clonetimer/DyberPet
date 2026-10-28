"""Curated Chinese creator-first ART REFERENCE index for all 125 templates.

A family-level lead is NEVER asserted to contain any particular character.
Metadata is intentionally link-only; no protected artwork/model is bundled,
downloaded, inspected on the user's computer, or automatically approved.
"""
from __future__ import annotations

import argparse
import json
from urllib.parse import urlsplit

try:
    from .chibi_profiles import CHIBI_PROFILES
    from .generate_mascot_demos import MASCOTS
except ImportError:
    from chibi_profiles import CHIBI_PROFILES
    from generate_mascot_demos import MASCOTS


# scope="role" means the source explicitly shows that character.
# scope="family" means it is only a discovery starting point.
# rights="unknown" includes artist and original-character IP, even if code is open.
SOURCES = (
    {
        "id": "guga_bilibili_v03", "scope": "role", "roles": ("mascot_guga",),
        "name": "咕嘎桌宠 v0.3｜作者动态示范", "creator": "氧化钙你五月",
        "url": "https://www.bilibili.com/video/BV1MGLN6eEuh/",
        "type": "dyberpet_native_preview", "rights": "unknown",
        "note": "DyberPet 原生动作/聊天示范；视频注明含 AI 内容、禁止未经许可转载；需单独核实角色包权利。",
        "lineage": "guga-bilibili-creator",
    },
    {
        "id": "guga_bilibili_v02", "scope": "role", "roles": ("mascot_guga",),
        "name": "咕嘎桌宠 v0.2｜原生角色动作", "creator": "氧化钙你五月",
        "url": "https://www.bilibili.com/video/BV1UJoEBrE9J/",
        "type": "dyberpet_native_preview", "rights": "unknown",
        "note": "作者公开了替换 res/role/咕咕嘎嘎 的目录说明；下载或可自用不等于可二次打包。",
        "lineage": "guga-bilibili-creator",
    },
    {
        "id": "guga_codex_author", "scope": "role", "roles": ("mascot_guga",),
        "name": "咕嘎 Codex 原画动作参考", "creator": "Eijnewgnaw / wwj",
        "url": "https://github.com/Eijnewgnaw/gugugaga-codexpet",
        "type": "codex_spritesheet", "rights": "mixed",
        "note": "贡献者仓库 MIT，不自动证明底层角色形象权利或与 B 站作者为同一画风；禁止拼接身份版本。",
        "lineage": "guga-codex-wwj",
    },
    {
        "id": "doro_live2d_creator", "scope": "role", "roles": ("mascot_doro",),
        "name": "Dororong 四足 Live2D｜美术基准", "creator": "0x4682B4 / 六碳糖",
        "url": "https://www.bilibili.com/video/BV16z421B7HQ/",
        "type": "live2d_creator_showcase", "rights": "no_redistribution",
        "note": "用户认可审美方向；作者禁止未经授权再分发模型，不能上传到公有或私有仓库。",
        "lineage": "doro-hexose-live2d",
    },
    {
        "id": "doro_dororo_runtime", "scope": "role", "roles": ("mascot_doro",),
        "name": "Dororo 桌宠实际动作及交互参考", "creator": "MelanTech（美术源 0x4682B4）",
        "url": "https://github.com/MelanTech/Dororo",
        "type": "live2d_runtime_example", "rights": "no_redistribution",
        "note": "Godot 原生桌宠代码 GPL，但角色美术仍按 0x4682B4 的模型条款；与上一个来源是同一原画链。",
        "lineage": "doro-hexose-live2d",
    },
    {
        "id": "genshin_nuo_nahida", "scope": "role", "roles": ("genshin_nahida",),
        "name": "栎曦_Nuo 纳西妲原创 DyberPet 动画", "creator": "栎曦_Nuo",
        "url": "https://www.bilibili.com/video/BV1fd4y1W7ht/",
        "type": "dyberpet_native_creator", "rights": "unknown",
        "note": "原绘作者明确与旧版 DyberPet 关联；使用需按其署名要求并另查角色动画再分发许可。",
        "lineage": "genshin-nuo-native",
    },
    {
        "id": "genshin_nuo_xiao", "scope": "role", "roles": ("genshin_xiao",),
        "name": "栎曦_Nuo 魈桌宠来源", "creator": "栎曦_Nuo",
        "url": "https://www.bilibili.com/video/BV1gv4y1a7Q7/",
        "type": "dyberpet_native_creator", "rights": "unknown",
        "note": "视频为角色专属来源线索，尚需核实能否获取对应动作包及许可。",
        "lineage": "genshin-nuo-native",
    },
    {
        "id": "genshin_ayaka_live2d", "scope": "role", "roles": ("genshin_ayaka",),
        "name": "绫华猫猫 14 套表情动作", "creator": "书呆儿 / 二当家",
        "url": "https://www.bilibili.com/video/BV1ix4y117SK/",
        "type": "live2d_creator_showcase", "rights": "restricted",
        "note": "付费 Live2D；作者称可自用、非盈利直播，禁止二次售卖。不能转为可自由分发的 PNG。",
        "lineage": "genshin-ayaka-cat-live2d",
    },
    {
        "id": "genshin_wanderer_native", "scope": "role",
        "roles": ("genshin_wanderer",),
        "name": "流浪者｜原生 DyberPet 旧版独立角色文件夹",
        "creator": "栎曦_Nuo / DyberPet_GenshinImpact",
        "url": "https://github.com/ChaozhongLiu/DyberPet_GenshinImpact/tree/main/res/role",
        "type": "dyberpet_native_creator", "rights": "unknown",
        "note": "原项目 res/role 下确有「流浪者」文件夹；这不证明与用户想要的现代装束完全一致，也非可再分发许可。",
        "lineage": "genshin-nuo-native",
    },
    {
        "id": "genshin_hutao_pixel", "scope": "role",
        "roles": ("genshin_hu_tao",),
        "name": "胡桃｜Codex v2 作者 Q 版像素动作",
        "creator": "ZaytsevZY",
        "url": "https://github.com/ZaytsevZY/genshin-pets/tree/main/pets/hutao",
        "type": "codex_spritesheet", "rights": "unknown",
        "note": "原仓库有 pet.json + spritesheet.webp 和独立动作预览；像素风仅作为对照候选，仍需审美验收及使用许可。",
        "lineage": "genshin-zaytsev-pixel",
    },
    {
        "id": "genshin_citlali_pixel", "scope": "role",
        "roles": ("genshin_citlali",),
        "name": "茜特菈莉｜Codex v2 作者 Q 版像素动作",
        "creator": "ZaytsevZY",
        "url": "https://github.com/ZaytsevZY/genshin-pets/tree/main/pets/citlali",
        "type": "codex_spritesheet", "rights": "unknown",
        "note": "作者明确是坐垫读书的像素 Q 版，可作定制动作创作参考；未经形象人工确认不标成完成。",
        "lineage": "genshin-zaytsev-pixel",
    },
    {
        "id": "genshin_nuo_original_collection", "scope": "family", "roles": ("genshin",),
        "name": "栎曦_Nuo 的原神 DyberPet 作品系列（仅发现入口）",
        "creator": "栎曦_Nuo / DyberPet_GenshinImpact",
        "url": "https://github.com/ChaozhongLiu/DyberPet_GenshinImpact",
        "type": "family_discovery", "rights": "unknown",
        "note": "原版旧项目已停止维护；不是 123 位角色的逐人资产证据。必须确认具体角色、版本、作者和许可。",
        "lineage": "genshin-nuo-native",
    },
)


def _all_roles():
    roles = {k for k in CHIBI_PROFILES if k.startswith("genshin_")}
    roles.update("mascot_" + key for key in MASCOTS)
    return roles


def validate_sources():
    """Fail closed for mistaken identities and accidental non-HTTPS endpoints."""
    ids = set()
    roles = _all_roles()
    if len(roles) != 125:
        raise ValueError("Unexpected 125-role catalog; update source policy")
    for item in SOURCES:
        if item["id"] in ids:
            raise ValueError("Repeated source ID: " + item["id"])
        ids.add(item["id"])
        u = urlsplit(item["url"])
        if (u.scheme != "https" or not u.netloc or u.username or u.password
                or u.hostname not in ("www.bilibili.com", "github.com")):
            raise ValueError("Source URL must be a known creator page over HTTPS")
        if item["scope"] not in ("role", "family"):
            raise ValueError("Invalid source scope")
        if item["scope"] == "role" and not set(item["roles"]).issubset(roles):
            raise ValueError("Specific source references an unknown role")
        if item["scope"] == "family" and item["roles"] != ("genshin",):
            raise ValueError("Family link may only be an explicit Genshin discovery lead")
        if item["rights"] not in ("unknown", "mixed", "restricted", "no_redistribution"):
            raise ValueError("Unknown or misleading rights state")
        if not item["creator"] or not item["lineage"] or not item["note"]:
            raise ValueError("A source requires lineage, artist, and caveats")
    return len(ids)


def sources_for_role(role_id):
    """Return independently attributable direct examples, then discovery leads.

    Reference evidence is NOT an installed character, a license, nor an
    approved design. The family link stays family-scoped even in UI.
    """
    if role_id not in _all_roles():
        raise ValueError("Unknown role: " + str(role_id))
    family = "genshin" if role_id.startswith("genshin_") else "mascot"
    result = []
    for item in SOURCES:
        exact = item["scope"] == "role" and role_id in item["roles"]
        broad = item["scope"] == "family" and family in item["roles"]
        if exact or broad:
            result.append({k: v for k, v in item.items() if k != "roles"})
    return result


def source_coverage():
    """Counts source discovery, not completed, usable or installable roles."""
    roles = sorted(_all_roles())
    detailed = {role: sources_for_role(role) for role in roles}
    exact = sum(any(s["scope"] == "role" for s in vals)
                for vals in detailed.values())
    broad_only = sum(vals and not any(s["scope"] == "role" for s in vals)
                     for vals in detailed.values())
    return {
        "template_count": len(roles), "specific_source_leads": exact,
        "family_discovery_only": broad_only,
        "without_source_lead": len(roles) - exact - broad_only,
        "creator_fidelity_approved": 0,
        "physical_desktop_qa_approved": 0,
        "notes": "Sources are manually reviewed leads, not rights grants, sprites or finished pets",
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--id", help="Exact character ID, or omit for whole-index coverage")
    opts = p.parse_args(argv)
    validate_sources()
    result = sources_for_role(opts.id) if opts.id else source_coverage()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
