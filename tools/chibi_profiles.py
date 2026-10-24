"""Chibi character *configuration* presets: no artwork or licensed voice assets.

A preset affects presentation and original desktop interaction text only.
The artwork creator, source and redistribution permission remain separate.
"""
from __future__ import annotations

# Stable IDs for the importer CLI; names are for selection and credit context.
CHIBI_PROFILES = {
    "chibi": {
        "name": "Q版原创角色", "franchise": "原创", "target_height": 116,
        "dialogue": {
            "pat_random_1": "嘿嘿，找到你啦！",
            "pat_random_2": "今天也要有好心情。",
            "feed_done": "谢谢款待！",
            "pat_frequent": "慢一点，我会转圈圈的！",
            "pat_focus": "安静模式启动，陪你专心。",
        },
    },
    "genshin_paimon": {
        "name": "派蒙", "franchise": "原神", "target_height": 112,
        "ground_mode": "floating",
        "dialogue": {
            "pat_random_1": "今天要去哪里冒险？",
            "pat_random_2": "前面好像有什么好玩的！",
            "feed_done": "好吃！继续出发！",
            "pat_frequent": "哎呀，别一直点我！",
            "pat_focus": "你忙你的，我在旁边看着。",
        },
    },
    "genshin_nahida": {
        "name": "纳西妲", "franchise": "原神", "target_height": 116,
        "dialogue": {
            "pat_random_1": "今天又学到了什么呢？",
            "pat_random_2": "想听听你的新发现。",
            "feed_done": "多谢你的心意。",
            "pat_frequent": "有事情想告诉我吗？",
            "pat_focus": "专注也是一场小小的探索。",
        },
    },
    "genshin_klee": {
        "name": "可莉", "franchise": "原神", "target_height": 110,
        "dialogue": {
            "pat_random_1": "今天也一起玩吧！",
            "pat_random_2": "蹦蹦跳跳好开心！",
            "feed_done": "谢谢！",
            "pat_frequent": "嘿嘿，转晕啦！",
            "pat_focus": "那我乖乖等你忙完。",
        },
    },
    "genshin_furina": {
        "name": "芙宁娜", "franchise": "原神", "target_height": 116,
        "dialogue": {
            "pat_random_1": "今天的舞台准备好了吗？",
            "pat_random_2": "观众已经入座啦。",
            "feed_done": "这份点心不错。",
            "pat_frequent": "注意台上的节奏！",
            "pat_focus": "这一幕交给你来演绎。",
        },
    },
    "ailimit_arrisa": {
        "name": "阿丽莎", "franchise": "无限机兵 / AI LIMIT", "target_height": 122,
        "dialogue": {
            "pat_random_1": "系统状态稳定。",
            "pat_random_2": "新的探索路线已记录。",
            "feed_done": "能量已补充。",
            "pat_frequent": "信号接收过于密集。",
            "pat_focus": "保持专注，我会留意周围。",
        },
    },
    "arknights_amiya": {
        "name": "阿米娅", "franchise": "明日方舟", "target_height": 114,
        "dialogue": {
            "pat_random_1": "今天的计划安排好了。",
            "pat_random_2": "记得适当休息。",
            "feed_done": "谢谢照顾。",
            "pat_frequent": "我在听，请慢慢说。",
            "pat_focus": "一起把眼前的任务完成。",
        },
    },
    "starrail_march7": {
        "name": "三月七", "franchise": "崩坏：星穹铁道", "target_height": 114,
        "dialogue": {
            "pat_random_1": "拍张纪念照怎么样？",
            "pat_random_2": "又是值得记录的一天！",
            "feed_done": "不错不错！",
            "pat_frequent": "等等，镜头都晃了！",
            "pat_focus": "忙完再一起逛逛！",
        },
    },
    "wuthering_rover": {
        "name": "漂泊者", "franchise": "鸣潮", "target_height": 118,
        "dialogue": {
            "pat_random_1": "准备好出发了吗？",
            "pat_random_2": "前方还有新的风景。",
            "feed_done": "状态恢复。",
            "pat_frequent": "我在这里。",
            "pat_focus": "集中精神，慢慢来。",
        },
    },
}

# These profiles enter the existing role-import GUI, conversion, preview and
# speech-bubble workflows automatically. No artwork is included.
try:
    from .genshin_roster import as_chibi_profiles
except ImportError:  # standalone tool usage: python tools/import_chibi_animations.py
    from genshin_roster import as_chibi_profiles

CHIBI_PROFILES.update(as_chibi_profiles())



def match_chibi_profile(user_input: str) -> str:
    """Resolve typed Chinese, English or stable ID without guessing ambiguities.

    QInputDialog allows typing but should not require the whole GUI label.
    A profile is ONLY a formatting preset; it is not an installed artwork.
    """
    if not isinstance(user_input, str) or not user_input.strip():
        raise ValueError("请输入角色中文名、英文名或模板 ID")
    raw = user_input.strip().casefold()
    from_candidates = []
    for key, entry in CHIBI_PROFILES.items():
        if raw in (key.casefold(), entry["name"].casefold()):
            from_candidates.append(key)
    try:
        from .genshin_roster import GENSHIN_ROSTER
    except ImportError:
        from genshin_roster import GENSHIN_ROSTER
    for key, entry in GENSHIN_ROSTER.items():
        if raw == entry["english"].casefold():
            from_candidates.append("genshin_" + key)
    unique = sorted(set(from_candidates))
    if len(unique) == 1:
        return unique[0]
    if len(unique) > 1:
        raise ValueError("多个角色名称相同，请使用完整模板 ID")
    # Disallow single-letter prefix guesses; short input must be an exact name
    # (e.g. one Chinese character 琴 is still accepted above).
    if len(raw) < 2:
        raise ValueError("请输入更完整的角色名")
    prefix = sorted({key for key, entry in CHIBI_PROFILES.items()
                     if entry["name"].casefold().startswith(raw)
                     or key.casefold().startswith(raw)})
    if len(prefix) == 1:
        return prefix[0]
    if len(prefix) > 1:
        raise ValueError("匹配到多个角色，请继续输入以消除歧义")
    raise ValueError("没有匹配的角色模板")

def available_role_folder(root, suggested):
    """Pick a safe unused role folder name; never overwrite existing artwork.

    GUI imports may use non-Latin source names; unlike an explicit CLI
    --folder override, these should not force a manual rename.
    """
    import re
    from pathlib import Path

    clean = re.sub(r"[^A-Za-z0-9_-]+", "_", str(suggested or "")).strip("_")
    clean = clean[:34].strip("_")
    if not clean or not re.match(r"^[A-Za-z]", clean):
        clean = "ChibiPet"
    root = Path(root)
    for count in range(1, 1001):
        suffix = f"_{count}" if count > 1 else ""
        folder = clean + suffix
        if not (root / folder).exists():
            return folder
    raise ValueError("Too many similarly named character folders")


def get_profile(profile_id: str | None) -> dict | None:
    """Return a copy to keep global templates immutable for callers."""
    if profile_id is None:
        return None
    if profile_id not in CHIBI_PROFILES:
        raise ValueError("Unknown chibi profile: " + str(profile_id))
    profile = CHIBI_PROFILES[profile_id]
    return {**profile, "dialogue": dict(profile["dialogue"])}


def make_bubble_config(profile_id: str | None) -> dict:
    profile = get_profile(profile_id)
    if profile is None:
        return {}
    return {
        kind: {"icon": None, "message": line,
               "start_audio": None, "end_audio": None}
        for kind, line in profile["dialogue"].items()
    }
