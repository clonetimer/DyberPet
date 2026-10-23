"""Character-specific reference dossiers, NOT playable art or licensed voices.

All visual criteria are for human review against an explicitly chosen source
version. A green engineering check must NEVER mean canonical likeness, source
license or voice identity has been independently verified.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class CharacterProfile:
    key: str
    title: str
    aliases: tuple[str, ...]
    origin: str
    visual_checks: tuple[str, ...]
    motion_checks: tuple[str, ...]
    tone_checks: tuple[str, ...]
    audio_checks: tuple[str, ...]
    references: tuple[str, ...]
    floating: bool = False
    variant_note: str = "先指定具体画师、发行版本及服装变体，再进行逐项对照。"


PROFILES = {
    "guga": CharacterProfile(
        "guga", "咕嘎（企鹅二创）", ("guga", "gugugaga", "咕嘎", "咕咕嘎嘎"),
        "公开传播的企鹅化二创，不存在自动可推定的唯一原版",
        ("企鹅连帽轮廓及头身比例", "脸、发饰、企鹅嘴/肚皮/脚的版本细节", "眼神和表情"),
        ("站立摇摆", "短步移动", "互动反应", "睡眠", "说话动作"),
        ("活泼、简短的拟声词；不得把普通 TTS 当成原声",),
        ("核对作者的标志性短音效", "对话 TTS 另外验收音色"),
        ("https://www.bilibili.com/video/BV1MGLN6eEuh/",),
    ),
    "doro": CharacterProfile(
        "doro", "Doro／桃乐丝迷因", ("doro", "dororong", "doro狗", "粉狗", "桃乐丝猫猫"),
        "GODDESS OF VICTORY: NIKKE 桃乐丝衍生迷因",
        ("桃乐丝式粉发与侧边发饰", "大眼与紫色眼睛特征",
         "白色圆润四足身体；不能画成直立粉发少女"),
        ("四足爬行或快速奔跑", "夸张表情", "跳跃/趴卧", "休息"),
        ("顽皮、短句、夸张拟声，区分 Doro 和原角色桃乐丝的说话方式",),
        ("仅核对具体授权版本的 Doro 拟声；不同二创并非统一配音",
         "自然语言朗读声线与标志音效分离"),
        ("https://knowyourmeme.com/memes/dororong",
         "https://game.udn.com/game/story/122089/7497754"),
    ),
    "paimon": CharacterProfile(
        "paimon", "派蒙", ("paimon", "派蒙"),
        "原神角色，非 DyberPet 原合集中的独立主角色版本",
        ("白色短发与头饰", "星形/环形标志及服饰", "小型悬浮伙伴的比例"),
        ("悬浮待机", "左右漂浮", "说话手势", "吃惊/开心", "休息"),
        ("热情、好奇、常作同伴式提醒；避免照搬台词",),
        ("对照选定语种的具体官方配音或获得许可的个人音效",
         "禁止把系统默认朗读冒充原声"),
        ("https://genshin.hoyoverse.com/",), floating=True,
    ),
    "nahida": CharacterProfile(
        "nahida", "纳西妲", ("nahida", "纳西妲"),
        "原神草神角色，需区分主游戏造型与同人 Q版",
        ("浅色双马尾与绿眼", "白绿配色", "叶形饰物和服装层次"),
        ("轻步移动", "观察/思索", "自然元素互动", "休息"),
        ("温和、好奇、善于观察和解释；不复刻原作句子",),
        ("具体语言版本的声音风格人工复核",),
        ("https://genshin.hoyoverse.com/",),
    ),
    "klee": CharacterProfile(
        "klee", "可莉", ("klee", "可莉"),
        "原神角色",
        ("红色帽子与白色装饰", "红白童趣服装", "背包及冒险装备"),
        ("蹦跳", "小跑", "欢呼", "休息"),
        ("天真、活泼、冒险兴趣；不生成原作完整台词",),
        ("儿童般轻快的表现需单独验收，不能声称系统 TTS 是原配",),
        ("https://genshin.hoyoverse.com/",),
    ),
    "furina": CharacterProfile(
        "furina", "芙宁娜", ("furina", "芙宁娜"),
        "原神枫丹角色；服装与发色视具体形态和版本确认",
        ("蓝白双色与礼帽", "戏剧感的服装剪裁", "异色/高亮眼睛特征"),
        ("优雅展示", "谢幕/表演", "惊讶", "休息"),
        ("戏剧性、讲究仪态，避免把夸张说话方式写死为唯一性格",),
        ("核对具体游戏版本及语种的语调与节奏",),
        ("https://genshin.hoyoverse.com/",),
    ),
    "arrisa": CharacterProfile(
        "arrisa", "阿丽莎 Arrisa", ("arrisa", "arisa", "ailimit_arrisa", "阿丽莎"),
        "无限机兵 AI LIMIT 的 Blader 主角",
        ("科幻末世服装和战斗装备", "发型/衣饰应以官方具体版本为准",
         "武器与角色比例 Q版化但保持辨识特征"),
        ("武器待机", "短步移动", "战斗动作", "巡视/休息"),
        ("坚韧、探索、审慎；不虚构游戏中不存在的固定口癖",),
        ("官方音效或角色说话段落的权利与有无须分别核对",
         "没有明确参考时不要声称具有唯一官方配音声线"),
        ("https://www.ailimit.com/", "https://www.sensegames.com/games/ailimit"),
    ),
}


def _canonical(raw: str) -> str:
    return re.sub(r"[\s_\-（）()\[\]]+", "", raw.casefold())


def resolve_profile(character_name: str) -> Optional[CharacterProfile]:
    """Exact alias / clearly separated variant suffix, not broad substring match."""
    if not isinstance(character_name, str):
        return None
    name = character_name.strip().casefold()
    if not name:
        return None
    norm = _canonical(name)
    for profile in PROFILES.values():
        for alias in profile.aliases:
            if norm == _canonical(alias):
                return profile
    # Normalize only recognized variant endings; never substring-match a name.
    for profile in PROFILES.values():
        for alias in sorted(profile.aliases, key=len, reverse=True):
            canonical_alias = _canonical(alias)
            if norm.startswith(canonical_alias):
                suffix = norm[len(canonical_alias):]
                if re.fullmatch(r"(?:v[0-9]+|[0-9]+|q版[0-9]*|q|chibi(?:v?[0-9]+)?)", suffix):
                    return profile
    return None


def matching_profiles() -> tuple[CharacterProfile, ...]:
    return tuple(PROFILES.values())
