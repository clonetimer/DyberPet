"""7.1 dated *profile-only* expansion to the original curated Genshin roster.

Source snapshot (2026-10-24): GameWith all-character list (last updated
2026-10-22), cross-checked with HoYoverse 7.1 launch announcement.
https://gamewith.net/genshin-impact/article/show/22357
https://www.gamespress.com/uk-UA/Genshin-Impact-Version-71-Launches-September-23-as-Forces-Gather-in-Sn

This is not the game asset database or a downloader. Localized names for some
new Snezhnaya/Nod-Krai entries are deliberately left in Latin when unverified.
Official artwork and voice are NOT included; visual cues are manual review
checkpoints, not certified replicas. Paimon is handled separately in existing
non-playable companion presets. The Traveler has separate Aether/Lumine
appearance templates, not one per element; unreleased 7.2 names excluded.
"""
from __future__ import annotations

SNAPSHOT_VERSION = "7.1"
SNAPSHOT_DATE = "2026-10-24"
SNAPSHOT_SOURCES = (
    "https://gamewith.net/genshin-impact/article/show/22357",
    "https://www.gamespress.com/uk-UA/Genshin-Impact-Version-71-Launches-September-23-as-Forces-Gather-in-Sn",
)
# id | label | English name | region | element | manual silhouette cue |
# manual outfit cue | suggested idle/motion QA cue
RAW_SUPPLEMENTAL = """amber|安柏|Amber|蒙德|火|红色兔耳头饰|侦察骑士服与护目镜|招手及射箭姿势
barbara|芭芭拉|Barbara|蒙德|水|金色双马尾|白蓝修女与偶像装|祈祷与唱歌动作
bennett|班尼特|Bennett|蒙德|火|浅白发与护目镜|绷带和冒险者短装|冒险鼓劲与小跳
dahlia|塔利雅|Dahlia|蒙德|水|教会执事礼装|圣职配饰与披肩|礼仪与水元素动作
diona|迪奥娜|Diona|蒙德|冰|粉色猫耳与尾巴|酒馆制服和摇壶|摇饮料与甩尾
durin|杜林|Durin|蒙德|火|龙主题装饰|对照官方衣装与发型|龙之姿态与火焰效果
fischl|菲谢尔|Fischl|蒙德|雷|金色长发与眼罩|紫黑色礼服及夜鸦元素|夸张谢幕与夜鸦互动
kaeya|凯亚|Kaeya|蒙德|冰|深蓝色侧分长发|眼罩与西风骑士披肩|潇洒转身
lohen|Lohen|Lohen|蒙德|冰|按7.1正式立绘复核发型|核对服饰装饰及轮廓|冰元素姿态
lisa|丽莎|Lisa|蒙德|雷|浅棕色波浪长发和魔女帽|紫白色图书管理员衣装|翻书与雷元素咒语
mika|米卡|Mika|蒙德|冰|浅金色短发|侦察队制服与测绘本|地图记录
noelle|诺艾尔|Noelle|蒙德|岩|银白色短发|女仆甲胄与蔷薇配饰|整理盔甲与鞠躬
prune|Prune|Prune|蒙德|风|核对正式立绘发型|核对风元素衣装及装饰|风元素动作
razor|雷泽|Razor|蒙德|雷|灰白长发与兽耳兜帽|兽群主题披风|低伏奔跑与雷爪动作
rosaria|罗莎莉亚|Rosaria|蒙德|冰|深红色长发|黑白修女服装与头饰|长枪收势
sucrose|砂糖|Sucrose|蒙德|风|浅绿发色和兽耳|炼金实验服及眼镜|实验记录与风蝶互动
varka|法尔伽|Varka|蒙德|风|骑士团大团长衣装|按官方形象核对发型盔甲|大剑战斗架势
baizhu|白术|Baizhu|璃月|草|绿发与眼镜|白色药师外袍及白蛇|诊疗与药草动作
beidou|北斗|Beidou|璃月|雷|黑红长发与眼罩|船长式衣装与大剑|船长挥手与大剑动作
chongyun|重云|Chongyun|璃月|冰|浅蓝色短发|白蓝方士衣装|符咒与驱邪手势
gaming|嘉明|Gaming|璃月|火|深色短发和额部饰物|醒狮主题服装|舞狮与腾跃
keqing|刻晴|Keqing|璃月|雷|紫色双发髻|紫白衣饰与剑|迅捷冲刺
lan_yan|蓝砚|Lan Yan|璃月|风|青蓝色发饰|璃月编织工艺服饰|藤编饰物与风刃姿态
ningguang|凝光|Ningguang|璃月|岩|白金色长发|黑白金礼服与发饰|凝玉手势
qiqi|七七|Qiqi|璃月|冰|紫色短发与符箓帽|僵尸风衣装和药篓|缓慢行走与记事
shenhe|申鹤|Shenhe|璃月|冰|银白长发|红绳与仙家服饰|符箓和长枪姿势
xiangling|香菱|Xiangling|璃月|火|双发髻与金色发带|厨师裙装和锅巴元素|做菜与锅巴互动
xianyun|闲云|Xianyun|璃月|风|眼镜与鹤羽造型|青白长衣及仙人元素|鹤形舞步
xingqiu|行秋|Xingqiu|璃月|水|蓝色短发|书卷与锦缎衣装|阅读与持剑
xinyan|辛焱|Xinyan|璃月|火|黑色高双髻|摇滚音乐衣饰|弹奏乐器与摇滚挥手
yanfei|烟绯|Yanfei|璃月|火|粉发与鹿角状头饰|法律顾问服饰及卷宗|读法典与辩论
yaoyao|瑶瑶|Yaoyao|璃月|草|绿色发带与双丸子头|童装和月桂元素|抱月桂与小跑
yelan|夜兰|Yelan|璃月|水|深蓝色短发|白色披肩与骰子装饰|骰子抛接与巡查
yun_jin|云堇|Yun Jin|璃月|岩|戏曲头饰|中式戏曲服装与彩球|戏曲亮相与转身
arataki_itto|荒泷一斗|Arataki Itto|稻妻|岩|白发和赤角|鬼族披挂和大棒|夸张炫耀和大步走
chiori|千织|Chiori|稻妻|岩|金色发饰|裁缝设计衣装和双刀|裁布与量尺寸
gorou|五郎|Gorou|稻妻|岩|棕色兽耳和尾巴|海祇军装和弓|警戒竖耳和拉弓
kamisato_ayato|神里绫人|Kamisato Ayato|稻妻|水|浅蓝短发|社奉行白蓝礼服|饮茶与挥剑
kirara|绮良良|Kirara|稻妻|草|猫耳与双尾|快递箱和短裙制服|快递冲刺与竖耳
kujou_sara|九条裟罗|Kujou Sara|稻妻|雷|黑色短发|天狗面具和军装|列队和拉弓
sangonomiya_kokomi|珊瑚宫心海|Sangonomiya Kokomi|稻妻|水|浅粉色长发|海洋贝饰与紫白巫女装|游鱼式游动
sayu|早柚|Sayu|稻妻|风|狸猫连帽服|小型忍者包与尾巴|滚动与打瞌睡
shikanoin_heizou|鹿野院平藏|Shikanoin Heizou|稻妻|风|酒红色短发|侦探服装与腰饰|推理与近身拳法
kuki_shinobu|久岐忍|Kuki Shinobu|稻妻|雷|绿色短发及面罩|忍者装束与佩饰|敏捷潜行与收刀
thoma|托马|Thoma|稻妻|火|金色短发和红色额带|家政与忍者混合装束|扫地与招手
yumemizuki_mizuki|梦见月瑞希|Yumemizuki Mizuki|稻妻|风|浅紫粉发色|妖怪与梦境主题服饰|轻飘待机和梦境动作
candace|坎蒂丝|Candace|须弥|水|双色瞳|沙漠护卫衣装与圆盾|持盾守卫
collei|柯莱|Collei|须弥|草|绿色短发|巡林员披肩及短弓|巡林与记录
cyno|赛诺|Cyno|须弥|雷|胡狼头盔|沙漠守护衣装及长枪|严肃待机与雷枪
dehya|迪希雅|Dehya|须弥|火|兽耳式头发装饰|黑红沙漠佣兵衣装|拳击与战斗热身
dori|多莉|Dori|须弥|雷|粉发与大帽子|商人裙装和宝石|精明手势与金币展示
faruzan|珐露珊|Faruzan|须弥|风|湖蓝双马尾|学者装束与几何装饰|古文字研读与机关动作
layla|莱依拉|Layla|须弥|冰|深蓝长发|星月主题学生衣装|昏昏欲睡的漂浮动作
sethos|赛索斯|Sethos|须弥|雷|深棕肤色与浅色发丝|沙漠旅者服装与弓|迅捷拉弓
tighnari|提纳里|Tighnari|须弥|草|大兽耳与深绿短发|巡林员披风和尾巴|观察植物和甩尾
charlotte|夏洛蒂|Charlotte|枫丹|冰|粉色双马尾|记者装束与相机|拍照与采访问答
chevreuse|夏沃蕾|Chevreuse|枫丹|火|深紫长发|特巡队制服和长枪|整队与瞄准
emilie|艾梅莉埃|Emilie|枫丹|草|浅金绿发色|调香师衣装与香水|调香与花香特效
escoffier|爱可菲|Escoffier|枫丹|冰|高礼帽式厨师头饰|厨师裙装和冰元素|料理与冰霜动作
freminet|菲米尼|Freminet|枫丹|冰|灰金色短发|潜水服与头盔|潜水准备与企鹅互动
sigewinne|希格雯|Sigewinne|枫丹|水|浅粉色双马尾|美露莘护士衣装|诊疗与药瓶互动
chasca|恰斯卡|Chasca|纳塔|风|红黑长发|牛仔式飞行装扮|持弓腾空
citlali|茜特菈莉|Citlali|纳塔|冰|粉色长发|纳塔占卜装束|占卜与浮空
iansan|伊安珊|Iansan|纳塔|雷|深色肤色与亮色发饰|运动员装束|训练冲刺与拍手
ifa|伊法|Ifa|纳塔|风|宽檐帽和兽医装备|纳塔兽医制服|照顾小龙
kachina|卡齐娜|Kachina|纳塔|岩|棕黄色小辫|采矿装束与钻头|转动钻机与小跑
kinich|基尼奇|Kinich|纳塔|草|黑绿发色与机械饰物|龙族猎人衣装|攀跃与伙伴互动
mavuika|玛薇卡|Mavuika|纳塔|火|橙红长发|骑士机车风服饰|疾驰与火焰动作
mualani|玛拉妮|Mualani|纳塔|水|深蓝短发|冲浪装备与鳍形配件|冲浪滑行
ororon|欧洛伦|Ororon|纳塔|雷|深蓝发色与兽耳装饰|夜魂装束和披肩|夜间巡查
varesa|瓦雷莎|Varesa|纳塔|雷|紫粉色长发|竞技运动装束|奔跑与冲锋
xilonen|希诺宁|Xilonen|纳塔|岩|兽耳与金发|宝石首饰和滑轮|滑行和音乐动作
aino|爱诺|Aino|挪德卡莱|水|浅蓝色双马尾|机械发明家装束|维修机械和招手
columbina|哥伦比娅|Columbina|挪德卡莱|水|黑发与白色头饰|月之少女主题衣装|月光式漂浮
flins|菲林斯|Flins|挪德卡莱|雷|深色长衣|灯塔守卫标志与长枪|执灯警戒
illuga|Illuga|Illuga|挪德卡莱|岩|按正式人物立绘复核发型|灯守与岩元素饰物|长枪警戒
ineffa|伊涅芙|Ineffa|挪德卡莱|雷|机械人形轮廓|女仆机器人装束|机械巡航
jahoda|Jahoda|Jahoda|挪德卡莱|风|按正式立绘核对帽饰|侦察装束和弓|拉弓与疾走
lauma|菈乌玛|Lauma|挪德卡莱|草|鹿角形装饰|自然与祭司主题衣饰|林间祝祷
linnea|Linnea|Linnea|挪德卡莱|岩|按正式立绘确认发型|冒险家衣装与岩元素|探险与持弓
nefer|奈芙尔|Nefer|挪德卡莱|草|深色发色与面饰|商会主题服装|交涉与召唤草元素
zibai|兹白|Zibai|挪德卡莱|岩|按正式立绘确认发饰|月与岩元素主题服装|持剑与战斗姿态
alyosha|Alyosha|Alyosha|至冬|雷|按正式7.1立绘核对发型|至冬军风装束|雷元素近身动作
nicole|Nicole|Nicole|至冬|火|按正式7.1立绘核对帽饰|魔女会与火元素主题|施法动作
odette|Odette|Odette|至冬|冰|按正式7.1立绘核对服饰|至冬主题装饰|冰元素施法
sandrone|桑多涅|Sandrone|至冬|冰|浅金色卷发|机械傀儡主题装束|机关操纵动作
tartaglia|达达利亚|Tartaglia|至冬|水|橘红色短发|灰色制服和红色围巾|双刃与弓姿态
vesna|Vesna|Vesna|至冬|风|按7.1正式立绘核对发型|至冬风元素剑士衣饰|精灵风剑舞
vodyanitsa|Vodyanitsa|Vodyanitsa|至冬|水|按7.1正式立绘核对帽饰|至冬水元素法师衣饰|星旋术式
aloy|埃洛伊|Aloy|其他|冰|红色长辫|猎人毛皮服装与弓|狩猎警戒
skirk|丝柯克|Skirk|其他|冰|银紫色长发|深渊风格服饰|剑术和瞬移
traveler_aether|空（旅行者）|Traveler Aether|其他|多元素|金色短发与发辫|金白色旅装|旅行探索与持剑
traveler_lumine|荧（旅行者）|Traveler Lumine|其他|多元素|金色短发与发饰|金白色旅装裙|旅行探索与持剑"""


def supplemental_profiles(role_factory):
    result = {}
    for lineno, line in enumerate(RAW_SUPPLEMENTAL.splitlines(), 1):
        parts = line.split("|")
        if len(parts) != 8:
            raise ValueError("Malformed Genshin roster snapshot at line " + str(lineno))
        key, name, english, region, element, silhouette, attire, motion = parts
        if key in result:
            raise ValueError("Duplicate supplemental Genshin ID: " + key)
        # Height is an editable chibi preset, not a claim about original
        # character scale or exact canonical body measurements.
        height = 110 if key in ("qiqi", "diona", "sayu", "yaoyao", "kachina",
                                "sigewinne") else 116
        appearance = [silhouette, attire,
                      "核对所选版本的官方造型、发饰、配色与持物是否一致"]
        movement = [motion, "观察待机到行走的连贯性",
                    "对照实际授权素材检查交互动作，不替代原角色动作"]
        entry = role_factory(name, english, height, appearance, movement,
                             name + "的桌宠模板已就绪，今天想做些什么？",
                             "我会静静地陪着你处理任务。")
        entry["region"] = region
        entry["element"] = element
        entry["snapshot_status"] = "template_only"
        entry["official_art_verified"] = False
        entry["character_identity_verified"] = False
        result[key] = entry
    return result
