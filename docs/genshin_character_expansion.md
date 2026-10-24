# DyberPet 原神角色批量扩展（2026-10-24）

**本轮实现：14 名新增原神角色的 Q 版配置、具体辨识项、作者来源登记和本地批量候选建档。没有合法取得的角色动画、模型或配音，因此不称为已安装/可运行的 14 个角色。**

这是从既有角色新增流水线 PR #1 派生的独立开发分支 `feat/genshin-characters-batch-20261024`。不修改 main、原有 Python 桌宠助手 PR #2 或 Rust 实验 PR #3。既有资源导入、许可复核、转换、预览、运行验收仍然是唯一有效的交付步骤。

## 新增 14 名角色

| 名称 | 模板 ID | 形象辨识或动作重点 | 当前素材入口 |
|---|---|---|---|
| 魈 | `genshin_xiao` | 青发、护法面具、长枪、警戒待机 | [原合集对应作品](https://www.bilibili.com/video/BV1gv4y1a7Q7)；权利未确认 |
| 流浪者 | `genshin_wanderer` | 宽檐斗笠、蓝色服装、悬浮待机 | [原合集对应作品](https://www.bilibili.com/video/BV1W24y1p7es)；权利未确认 |
| 胡桃 | `genshin_hu_tao` | 花饰帽、长发、小幽灵、欢快动作 | 具体素材待寻 |
| 钟离 | `genshin_zhongli` | 深色长外套、金色装饰、沉稳动作 | 具体素材待寻 |
| 雷电将军 | `genshin_raiden_shogun` | 紫色长辫、紫色服装、武器动作 | 具体素材待寻 |
| 温迪 | `genshin_venti` | 羽饰帽、绿斗篷、演奏动作 | 具体素材待寻 |
| 甘雨 | `genshin_ganyu` | 蓝发、角形发饰、安静待机 | 具体素材待寻 |
| 枫原万叶 | `genshin_kazuha` | 白发红色挑染、枫叶纹饰、轻步动作 | 具体素材待寻 |
| 神里绫华 | `genshin_ayaka` | 浅蓝高束发、折扇、礼仪动作 | 具体素材待寻 |
| 八重神子 | `genshin_yae_miko` | 粉色长发、巫女衣饰、优雅姿态 | 具体素材待寻 |
| 宵宫 | `genshin_yoimiya` | 金色束发、祭典服饰、庆祝动作 | 具体素材待寻 |
| 那维莱特 | `genshin_neuvillette` | 银白长发、蓝黑色正式服装、缓步动作 | 具体素材待寻 |
| 阿蕾奇诺 | `genshin_arlecchino` | 黑白挑染、红黑服饰、冷静战斗姿态 | 具体素材待寻 |
| 娜维娅 | `genshin_navia` | 金发、宽檐礼帽、蓝金服装及伞 | 具体素材待寻 |

此前已存在的派蒙、纳西妲、可莉、芙宁娜模板保持不变，总共拥有 18 名原神角色的 Q 版选项（其中新增 14 名）；原创、无限机兵及其他角色的模板也保持不变。

## 适用于非程序员的界面入口

在已有 Windows 桌宠 GUI 中进入 **系统 → 角色管理 → 添加角色**，选择本地合法取得的 GIF/PNG 文件夹、Codex 图集或原生 ZIP；根据实际人物选择“Q版角色模板”。新增加的 14 个角色会出现在选择列表中。流水线按具体素材转换生成 `pet_conf.json`、`act_conf.json`、动画 PNG、预览与来源报告。若用户没有本地素材，这个模板选择不能自动生成任何角色图像，不能在 UI 中伪装成“已安装”。

## 批量候选建档：一次建立全部角色的审核任务

在仓库目录使用 Windows PowerShell 或 Git Bash：

```powershell
python tools/genshin_batch.py list
python tools/genshin_batch.py preview --roles all
python tools/genshin_batch.py seed --roles all
```

或只建立两个角色：

```powershell
python tools/genshin_batch.py seed --roles xiao,hu_tao
```

输出默认放在已被 Git 忽略的 `data/character_pipeline/cases/`，每个角色有独立的 `cases/genshin_<id>_main.json` 和 `reviews/genshin_<id>_main.json`。这些文件含角色目标、来源、视觉与动作核对清单、操作建议，**初始全部未审核**，不含游戏音频、美术或自动授权声明。

相同角色已有 case 或检查清单时，本次 seed **拒绝改写**，而非覆盖用户的授权证据和此前 QA；`preview` 永不写文件。不要把这些尚未批准的资料文件当作可分发 MOD。

## 从候选到真正的可用桌宠

以下以魈为例。实际素材必须由用户从有权使用的作品来源取得，若作者只提供展示/视频，不能据此提取图像再发行。

```powershell
# 用户确认实际格式后，为该角色使用对应的本地资源
python tools/character_pipeline.py attach genshin_xiao_main --asset 'D:/PetAssets/XiaoRole.zip'

# 检查作者对该作品的许可原文并人工填入真实证据路径或记录
python tools/character_pipeline.py rights genshin_xiao_main --reviewer 'local-user' --evidence 'D:/PetAssets/Xiao-terms.txt' --local-use --derivatives

# 仅在许可条件适配时才转码、生成角色 PNG 与预览
python tools/character_pipeline.py build genshin_xiao_main

# 使用本机 Qt/DyberPet 验收实际视觉、动作、角色缩放与稳定性
python tools/character_pipeline.py qa genshin_xiao_main --reviewer 'local-user' --visual-pass --runtime-pass
```

**重要**：上面 `.zip` 只是举例的本地文件路径，仓库没有自动下载任何素材。原合集文件解压格式可能不同，须先检查实际格式；如果得到的是分镜图集、GIF/PNG 或 3D 模型，应选对相应的流水线种类，3D 模型须额外离线渲染并复查衍生许可。`--redistribution` 权限必须有独立作品许可才可以录入；只有这样并完成 QA 才能尝试 `package`。仅个人可用不能自动推导为可公开分发。

## 来源与后续维护

- 源记录：`tools/character_sources.json`，保留用户可追溯的作者和具体作品信息；没有找到素材时 `asset_url` 留空、状态 `research_needed`，不把模之屋首页当作具体模型 URL。
- 角色具体特征：`tools/genshin_roster.py`，由此生成现有导入 GUI 兼容的 `genshin_*` 模板，以及每个候选的人工验收清单。
- 执行/质量：沿用 `tools/character_pipeline.py` 的权限门禁、源哈希检查、同一来源可追溯、生成与实际运行 QA，以及 Windows/Linux GitHub Actions。
- 原有角色合集的魈、流浪者条目已有来源链接，但并不意味着我们已经取得其重新分发许可。派蒙还可能属于 `res/pet` 迷你宠物，与主桌宠 `res/role` 不可互换。
- 若有新的作者素材，先单独审查 **作品、模型、动作、音频** 的不同权利范围，再把候选从 `research_needed` 改为有具体来源证据的状态；不能仅因属于同一游戏便批量通过。

## 验收边界

自动测试验证的是 14 个模板均进入导入器、每个角色身份/动作/气泡目标单独存在、已知作品链接可追溯、未知链接不造假、批量创建不覆盖既有用户资料、没有素材和授权时不能构建角色或公开打包。

这并不代表所有新增角色的形象、骨骼动作、音色和语气已经达到官方水准。任何角色素材的实际可运行和贴近原设仍须有真实素材与 Windows GUI 人工验收。
