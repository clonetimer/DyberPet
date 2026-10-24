"""Genshin Chibi expansion roster for existing DyberPet workflows.

These are *selection and manual visual QA dossiers*, not character sprite packs.
No model, skin, sound, game dialogue or license is included. Only Xiao and
Wanderer have item-specific discovery links in DyberPet's existing collection;
the remainder must acquire a particular creator-approved local asset first.
"""
from __future__ import annotations


def role(name, english, height, appearance, motion, hello, wait,
         *, creator_source="", floating=False):
    return {
        "name": name, "english": english, "target_height": height,
        "visual_checks": appearance, "motion_checks": motion,
        "source_work_url": creator_source,
        "suggested_channel": "dyberpet_collection" if creator_source else "aplaybox",
        "kind": "native_zip" if creator_source else "frames",
        "ground_mode": "floating" if floating else "grounded",
        "dialogue": {
            "pat_random_1": hello,
            "pat_random_2": "又有新的冒险想法吗？",
            "feed_done": "谢谢这份点心。",
            "pat_frequent": "慢一点，我们可以好好交流。",
            "pat_focus": wait,
        },
        "original_art_included": False,
        "original_voice_included": False,
        "asset_rights": "not_reviewed",
        "publishable": False,
    }


# The two Bilibili item links below come from DyberPet docs/collection.md,
# not guessed from a search query or interpreted as reuse licenses.
GENSHIN_ROSTER = {
    "xiao": role(
        "魈", "Xiao", 118,
        ["青绿色短发、额部饰物", "仙人风格服装与长枪", "面具须对照具体美术版本"],
        ["警戒待机", "持枪移动", "轻跃"],
        "附近有什么需要留意的吗？", "安静些也好。",
        creator_source="https://www.bilibili.com/video/BV1gv4y1a7Q7"),
    "wanderer": role(
        "流浪者", "Wanderer", 116,
        ["宽檐斗笠与垂饰", "蓝白深色服装轮廓", "版本与服饰需要指定"],
        ["悬浮待机", "轻微漂移", "面部反应"],
        "今天打算去哪里？", "我会在一旁，不用打扰。",
        creator_source="https://www.bilibili.com/video/BV1W24y1p7es",
        floating=True),
    "hu_tao": role(
        "胡桃", "Hu Tao", 112,
        ["深色帽子及花饰", "深棕长发双马尾", "黑红配色与小幽灵"],
        ["蹦跳待机", "小幽灵互动", "欢快小跑"],
        "今天想听个有趣的小故事吗？", "安静的时间也很有意思。"),
    "zhongli": role(
        "钟离", "Zhongli", 124,
        ["深棕渐变发色", "长款深色外衣与金色纹饰", "沉稳的站姿"],
        ["沉稳待机", "缓步移动", "思考手势"],
        "今天有什么值得留心的事？", "慢慢来，稳妥些更好。"),
    "raiden_shogun": role(
        "雷电将军", "Raiden Shogun", 120,
        ["紫色长辫", "紫色和服式服装与腰饰", "武器/发饰需按选定形态"],
        ["端正待机", "转身移动", "武器展示"],
        "今天的安排已经确定了吗？", "我会保持安静。"),
    "venti": role(
        "温迪", "Venti", 112,
        ["绿色羽饰帽", "深色短发与青绿色斗篷", "吟游诗人服装"],
        ["轻快小跳", "演奏动作", "待机摆动"],
        "想听一段新的旋律吗？", "风声会陪着你。"),
    "ganyu": role(
        "甘雨", "Ganyu", 116,
        ["浅蓝色长发", "红黑色角形发饰", "蓝白服饰与项圈配件"],
        ["安静待机", "轻步移动", "困倦反应"],
        "今天的事项要一起整理吗？", "这段时间适合专注。"),
    "kazuha": role(
        "枫原万叶", "Kaedehara Kazuha", 116,
        ["白色短发与红色挑染", "红黑旅者服饰", "枫叶纹饰"],
        ["轻步移动", "观景手势", "微风式待机"],
        "路上又有什么新发现？", "听听窗外的风吧。"),
    "ayaka": role(
        "神里绫华", "Kamisato Ayaka", 116,
        ["浅蓝发色与高束发型", "蓝白日式服装", "折扇和精致发饰"],
        ["礼仪动作", "小步移动", "持扇互动"],
        "要不要安排一段轻松的活动？", "我会安静等你忙完。"),
    "yae_miko": role(
        "八重神子", "Yae Miko", 118,
        ["粉色长发", "巫女式红白衣饰", "耳形发饰的具体造型"],
        ["优雅待机", "漫步", "戏谑小动作"],
        "今天又想到什么新点子了？", "看看事情会如何发展。"),
    "yoimiya": role(
        "宵宫", "Yoimiya", 114,
        ["金色高束发型", "夏日祭风格服饰", "发带与烟花饰物"],
        ["欢呼", "活泼小跑", "庆祝动作"],
        "今天有值得庆祝的事情吗？", "忙完我们再玩一会儿。"),
    "neuvillette": role(
        "那维莱特", "Neuvillette", 124,
        ["银白长发", "蓝黑色正装及披风", "服装装饰与发饰的层次"],
        ["沉稳待机", "整理衣袖", "缓步移动"],
        "有什么需要我帮忙梳理？", "保持思路清晰即可。"),
    "arlecchino": role(
        "阿蕾奇诺", "Arlecchino", 120,
        ["白发与黑色挑染", "黑白红色服装", "红黑色眼部特征"],
        ["克制待机", "冷静移动", "战斗准备"],
        "已经考虑好接下来的步骤了吗？", "专注完成眼前的事。"),
    "navia": role(
        "娜维娅", "Navia", 118,
        ["金色卷发", "宽檐礼帽与花饰", "蓝金礼服、伞与丝带"],
        ["明快互动", "优雅小跑", "持伞姿态"],
        "今天要不要一起想个新方案？", "别担心，我会在附近。"),
}


def as_chibi_profiles():
    """Make supported importer templates; no mutable references escape."""
    import copy
    return {
        "genshin_" + key: {
            "name": item["name"], "franchise": "原神",
            "target_height": item["target_height"],
            **({"ground_mode": "floating"}
               if item["ground_mode"] == "floating" else {}),
            "dialogue": copy.deepcopy(item["dialogue"]),
        }
        for key, item in GENSHIN_ROSTER.items()
    }


def find_role(key: str):
    if not isinstance(key, str):
        raise ValueError("Character id must be a string")
    try:
        return GENSHIN_ROSTER[key]
    except KeyError as exc:
        raise ValueError("Unknown new Genshin character: " + key) from exc
