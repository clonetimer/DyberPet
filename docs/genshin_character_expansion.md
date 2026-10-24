# DyberPet 原神角色批量扩展（2026-10-24）

**当前实现：26 名新增原神角色的 Q 版配置、人物辨识项、来源候选及本地批量建档（其中本轮再增 12 名）。没有合法取得的角色动画、模型或配音，因此不称为已安装/可运行的 26 个角色。**

这是从既有角色新增流水线 PR #1 派生的独立开发分支 `feat/genshin-characters-batch-20261024`。不修改 main、原有 Python 桌宠助手 PR #2 或 Rust 实验 PR #3。既有资源导入、许可复核、转换、预览、运行验收仍然是唯一有效的交付步骤。

## 已登记的第一批 14 名角色

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

## 第二批 12 名新增角色（本轮）

| 名称 | 模板 ID | 独特 Q 版形象与动作关注点 | 素材进度 |
|---|---|---|---|
| 迪卢克 | `genshin_diluc` | 红色长发、黑色外套、整理手套 | 逐件素材待核 |
| 琴 | `genshin_jean` | 金色马尾、骑士团制服、行礼 | 逐件素材待核 |
| 莫娜 | `genshin_mona` | 星纹礼帽、占星动作 | 逐件素材待核 |
| 阿贝多 | `genshin_albedo` | 浅金编发、炼金术装束、记录动作 | 逐件素材待核 |
| 优菈 | `genshin_eula` | 浅蓝短发、骑士装、舞步式动作 | 逐件素材待核 |
| 妮露 | `genshin_nilou` | 红发、角状头饰、舞蹈动作 | 逐件素材待核 |
| 艾尔海森 | `genshin_alhaitham` | 灰绿发色、学者装束、阅读 | 逐件素材待核 |
| 卡维 | `genshin_kaveh` | 金色长发、建筑设计稿、交流手势 | 逐件素材待核 |
| 林尼 | `genshin_lyney` | 魔术礼帽、舞台鞠躬 | 逐件素材待核 |
| 琳妮特 | `genshin_lynette` | 猫耳与尾巴、侍者服、端杯动作 | 逐件素材待核 |
| 克洛琳德 | `genshin_clorinde` | 深紫长发、制服、持剑姿态 | 逐件素材待核 |
| 莱欧斯利 | `genshin_wriothesley` | 黑灰短发、拳套、沉稳待机 | 逐件素材待核 |

这 12 名角色都不带第三方 PNG、模型或 WAV，也没有经过逐件确认的配布链接，`creator` 与 `asset_url` 保持空值、`rights_status=unknown`。首次登记时只生成配置模板和人工视觉/动作检查清单；作者授予本地转换或再分发权限必须独立核对。

此前已存在的派蒙、纳西妲、可莉、芙宁娜模板保持不变；现有 **30 个原神角色 Q 版模板选项**（旧 4 + 第一批 14 + 本轮 12）。原创、无限机兵及其他角色模板均不变。

## 适用于非程序员的界面入口

在已有 Windows 桌宠 GUI 中进入 **系统 → 角色管理 → 添加角色**，选择本地合法取得的 GIF/PNG 文件夹、Codex 图集或原生 ZIP；根据实际人物选择“Q版角色模板”。本项目新增的 26 个角色模板会出现在选择列表中。流水线按具体素材转换生成 `pet_conf.json`、`act_conf.json`、动画 PNG、预览与来源报告。若用户没有本地素材，这个模板选择不能自动生成任何角色图像，不能在 UI 中伪装成“已安装”。

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

**已有第一批角色记录的升级方式（推荐）**：不要重新执行 `seed --roles all`。使用下列命令增量创建缺失的记录，已有角色的 case、许可文件和 QA 均保留原样：

```powershell
python tools/genshin_batch.py preview --roles all
python tools/genshin_batch.py seed-missing --roles all
python tools/genshin_batch.py status --roles all
```

`seed-missing` 在完整 case+review 已存在且身份一致时跳过；如果有一半缺失、软链接或身份不一致，会中止整个任务且不创建任何新记录。再次执行为幂等操作，便于以后继续增加角色。

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

自动测试验证的是 26 个模板均进入导入器、每个角色身份/动作/气泡目标单独存在、已知作品链接可追溯、未知链接不造假、批量创建不覆盖既有用户资料、没有素材和授权时不能构建角色或公开打包。

这并不代表所有新增角色的形象、骨骼动作、音色和语气已经达到官方水准。任何角色素材的实际可运行和贴近原设仍须有真实素材与 Windows GUI 人工验收。

## P2：优先核验魈、流浪者的原生资源（2026-10-24）

进一步查证的旧版项目 [DyberPet_GenshinImpact](https://github.com/ChaozhongLiu/DyberPet_GenshinImpact) 在 README 中明确宣布项目已停止维护，并建议用户将**角色文件夹**迁移至新版 DyberPet。原合集对应 [魈视频](https://www.bilibili.com/video/BV1gv4y1a7Q7) 和 [流浪者视频](https://www.bilibili.com/video/BV1W24y1p7es) 可用于追查作者来源，但作者视频并不授权我们重新分发角色动画和游戏配音。旧版有包含 EXE 的全程序压缩包，**它不是单个角色 ZIP，切勿直接安装或运行来提取桌宠素材**。

支持的两条无网络本地入口：

1. **原生单角色 ZIP**：只需包含唯一一个 `pet_conf.json`、`act_conf.json` 以及 `action/xxx_N.png`；不允许包含 exe、bat、DLL、链接或路径穿越条目。
2. **原版已解压的单角色文件夹**：在个人合法取得的旧版资源中选择 `res/role/魈` / `res/role/流浪者` 这一层级，而不是选择全程序根目录，也不要把 `res/pet` 迷你宠物错装成主宠物。新的安装器在后台完成文件上限检查、链接/脚本拒绝、原生动作配置检查，再原子性安装到一个独立且不覆盖现有角色的目录。

对已经合法取得的素材，先执行只读预检：

```powershell
python tools/genshin_batch.py probe --asset "D:/PetAssets/res/role/Xiao"
python tools/genshin_batch.py status --roles xiao,wanderer
```

准备好审核任务后，用之前的 `seed` 命令建立候选，再执行：

```powershell
python tools/character_pipeline.py attach genshin_xiao_main --asset "D:/PetAssets/res/role/Xiao"
python tools/character_pipeline.py inspect genshin_xiao_main
```

成功关联会将原先的 `native_zip` 类型自动标记为真正的 `native_folder`，并清除以前记录的许可与 QA；未获得本地使用许可时后续 `build` 仍会拒绝。获得作品特定的真实许可并完成 `rights` 才能生成本地角色；`qa` 必须经过实际 Windows PySide6 动画/缩放/拖拽和动作预览验收。重新分发仍需额外许可审核。

在图形界面中仍走“系统 → 角色管理 → 添加角色 → 选择角色文件夹”，但检测到 `pet_conf.json` 和 `act_conf.json` 后会使用新增的**安全后台原生文件夹安装器**，而非直接复制未经检验的旧文件。此 GUI 安装仅是本机加载，**并不等价于作品授权审查或可公开发布角色包**。

状态定义遵循真实本地候选记录：`not_seeded` → `awaiting_local_artwork` → `source_attached` → `rights_reviewed` → `built_pending_visual_runtime_qa` → `qa_reviewed`。未完成阶段不宣称“角色已可用”。`status` 会读取源文件用于 SHA-256 完整性校验，但不会输出、复制或上传图像、音效，也不会在状态摘要中显示素材的本地绝对路径。
