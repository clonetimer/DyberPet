# 原神 123 人物：真实作者素材覆盖计划（2026-10-25）

> **不能用简笔画/程序低保真代替人物原画。**
> “角色模板存在”“发现创作者素材”“已安装能运行”“符合原设视觉”“拥有发布许可”是五项不同的事实。
> 本项目任何脚本都不能用自动生成的通用人物来冒充角色完成。

## 本阶段实测可追溯信息（不是 123 人完工声明）

- 人物/伙伴模板：**123**，与 GUI 名录一致；另有咕嘎和 Doro 两个独立吉祥物，不计入 123。
- 固定来源候选：**78 个动画来源选项，对应 55 个不同原神人物**；其中含同一人物的多个作者版本。
- **68 个角色尚无本项目固定校验的创作者素材来源**；后续需要按角色逐一检索并确认是该角色，不得凭文件名或艺术风格推断。
- 逐帧像素来源/下载安全/原生格式自动测试 ≠ 游戏原设像貌人工验收。**当前不宣称任何一个人物已完成形象人工验收、全部原作动作验收或 Windows 实机验收。**
- 所有新增素材均从公开资源**经用户确认后下载到本机**，仓库不直接提交、再发布未确认权利的二创图集。

## 已明确的真实素材路线

| 来源类型 | 可用入口 | 固定版本 | 说明 |
| --- | --- | --- | --- |
| 老版原神 DyberPet | [原始 GitHub 仓库](https://github.com/ChaozhongLiu/DyberPet_GenshinImpact) | `0789950b81802cc51ebeeecfc24be16aaee16e74` | 纳西妲、魈、流浪者。真实完整动作，下载体积大 |
| Codex Pets 作者图集 | [原始作者合集](https://github.com/legeling/awesome-codex-pet) | `db2f6306ce78f6559ab27155d7bfaf00bf43809d` | 原 12 个图集 + 茜特菈莉、书桌版可莉、伙伴版派蒙；下载所需两个文件，验证 Git blob 身份 |
| 公开 Shimeji 原角色动画 | [AI-Desktop-Pet 素材仓库](https://github.com/AkshitIreddy/AI-Desktop-Pet/tree/master/public/assets) | `e54db597c94c1f19102bec2e7e2cb3490a9d5a7d` | 阿贝多、绫华、重云、胡桃、枫原万叶、可莉、托马、温迪，共 8 个原始动作图集；上游 README 提及 @uuteki。逐 PNG 哈希校验、无像素重绘 |

**特别提示：** 上游开源项目代码的许可证不一定授权包含的美术；素材具体使用条件及每个二创作者的许可需核实。个人本机使用不等于可把素材打进 GitHub Release 发布。素材是否符合游戏原设仍需逐帧对照。

### 2026-10-25 扩增来源：原作者 17 套 Shimeji 与五份独立 Codex

| 来源 | 固定提交 | 素材范围与内容 |
| --- | --- | --- |
| [Nano Pet 原神画师目录](https://github.com/Poseima/nano-pet/tree/main/NanoPetAssets/genshin-impact) | `abf4ec309fbe44dba6675d71c0cccb2dc419f38c` | **17 套**人物及不同画师版本，**781 个原始 PNG**；新增角色包括空、荧、达达利亚、迪卢克、凯亚、雷泽、钟离；魈已通过旧来源覆盖但可选画师版本更多 |
| [独立 Linnea 桌宠](https://github.com/Alchuang22-dev/Linnea-Codex-Pet) | `57a95bd88bdd773448863d7049b8db1d8aec6f39` | 莉奈娅的创作者 Codex 精灵图集；新增 1 个来源覆盖的人物 |
| [Genshin Pets](https://github.com/ZaytsevZY/genshin-pets) | `88cc8fe7de174eab62a6eafb417c1a1ea8b4bf95` | 独立像素风胡桃原画版，非新增人物 |
| [Nahida Mini](https://github.com/Rukkhadevata-Karrenay/nahida-mini-codex-pet) | `3b0c593fb8c93544ebb3cb28f55f97c82ed0e6d1` | 独立 Q 版纳西妲，非新增人物 |
| [Sandrone 桑多涅](https://github.com/crema-lida/genshin-codex-pets/tree/main/Sandrone/sandrone) | `52c50711ef2d47fe28deddf69fbb36618ffa0de2` | 桑多涅的一套独立像素艺术图集；新增 1 个来源覆盖人物 |
| [Sandrone 木偶版](https://github.com/sqybi/codex-fan-pets-gi/tree/main/pets/sandrone-marionette) | `7e1deb0c5b825856ccad0f4c01a0d3ca03dbe1ff` | 桑多涅的另一套独立作者版本，与上项同一人物，不重复计数 |
| [刻晴双版本](https://github.com/PengZirong/keqing-codex-pet) | `f8c45f36164accbed15c46084bce2b274ca82d8b` | **精细 Q 版与经典比例版**。实看作者待机 GIF 后纳入固定图集，新增刻晴 1 人；原始美术仍未获正式人工验收或分发授权 |

Nano Pet 中标记为 **Xiao catboy** 的非原设变体已明确排除，不能作为“标准魈”验收凭据。素材导入仅把能确认语义的原始动作帧绑定到运行时，其余源帧仍全部原样保存在 `source_frames/`。个别来源具有特殊文件名或缺帧，按原作者文件逐项固定哈希，绝不填图、造帧或假装完整原设动作。

先前阶段的 31/123 是**角色身份可溯源的候选来源覆盖率**，不是美术相似度已通过率，更不是 30 个 Windows 真机已验收角色。未经来源许可不要将这些美术直接打包再分发。

## 新确定的风格优先级：精细 Q 版先行，Shimeji 作为备选

- **P1：精细 Q 版优先**。已核对过帧形态的老版 DyberPet 纳西妲、魈、流浪者为第一组的视觉风格示例；刻晴作者 Q 版也可优先预览，但不能直接计作人工相似度通过。
- **P1 待视觉核对：独立作者 / Codex 图集**。部分保留较丰富的服饰、眼睛与头饰，也可能仅有少量像素细节；不能仅凭 WebP 尺寸、作者名称和文件哈希自动评 A。
- **P2：原作者 Shimeji 小型动画**。只要人物辨识度确实满足要求可以使用，不能把非原设、简笔画、其他游戏同名人物充作合格素材。
- **人工 A/B/C 结果目前一律待审**。P1/P2 是用户指定的选材及安装排序，而 A/B/C 是逐角色视觉对比后的结果，绝不虚构。
- **新安装的角色库直接展示已找到来源的 47 位原神角色**；仍缺 76 位可切换“仍缺公开作者素材”筛选；不将“来源发现”混同“安装完成”。GUI 来源选择器优先推荐精细原生版，其次需看图核对的作者图集，最后可接受的 Shimeji。

## 用户可直接操作的流程

1. 更新独立候选分支，启动 DyberPet。
2. **系统 → 角色管理 → 安装作者原画角色**；候选列表支持三种来源。选中一个明确的角色和作者版本，确认网络下载。
3. 安装器验证原始文件内容，生成独立的 `SourceShimeji<角色>` 或现有的 Codex/原生角色文件夹，**永不覆盖**用户旧角色或存档。
4. **快速选桌宠**，切换为刚导入的真实作者角色；检查发型、装饰、服饰、颜色、待机/左右走/跌落/拖动；对只有 Shimeji 原始动作的模型，不得宣传“完整原版 DyberPet 动作”。
5. 如来源不满足视觉要求，该角色仍属于待整改；不要用 QA 程序演示图补位，也不要强行通过。

开发/本机批量审查（只查询，不下载）：

```bash
python tools/character_source_coverage.py --missing-only --output missing-123-sources.json
python tools/character_source_coverage.py --output creator-source-coverage.json
```

个人本机手动安装（选一个）：

```bash
python tools/install_artist_shimeji.py albedo --role-root res/role --accept-personal-use
python tools/install_artist_codex.py citlali --role-root res/role --accept-personal-use
python tools/install_artist_genshin.py xiao --role-root res/role --accept-personal-use
python tools/install_nanopet_shimeji.py zhongli-by-vol-tuna --role-root res/role --accept-personal-use
python tools/install_external_codex.py linnea --role-root res/role --accept-personal-use
python tools/install_external_codex.py sandrone --role-root res/role --accept-personal-use
python tools/install_external_codex.py keqing_chibi --role-root res/role --accept-personal-use
python tools/install_external_codex.py keqing_classic --role-root res/role --accept-personal-use
```

运行联网安装前阅读对应作者页面的资源条款。离线自动测试不直接从网络下载文件或把真实美术图片提交到测试仓库。

## 123 人逐项验收条件

一个角色满足全部项目才能标记 `ready`：

1. **正确身份**：明确原神角色与皮肤/版本，而非同名的其他作品；有具体原始来源 URL、原始版本、作者信息。
2. **真实素材**：作者源 PNG/GIF/动图/原生 MOD，排除几何线条占位、重复涂色图、AI 自动猜形补位。
3. **校验可信**：原始像素/下载哈希校验，透明边缘、头身比例、全身衣装与关键饰物没有被裁剪或扭曲。
4. **动作可用**：原素材具有的待机/移动/拖动/跌落等实际帧正确关联，不把静态图复制为不同动作并假装完成。
5. **人工验收**：逐角色与公开原设参考对照，至少检查发型、轮廓、服饰、标志性道具和动作；必要时记录差异并回退。
6. **平台验收**：真实 Windows 运行，检查 DPI、切换角色、透明显示、动画性能和资源失败后的数据完整性。
7. **来源条件**：明确本机使用/分发权限边界；没拿到再分发授权时保持用户本机选取，不上传美术包到公开发布文件。

这些条件不可由单独的 GitHub Actions PASS 替代。Rust 分支只消费同一已核对的原始资源，不另行生成“简笔画替代”。

## 下阶段继续补齐 88 人

统一角色清单为唯一工作台：每项至少登记可信素材候选、是否真实可下载、创作者署名、固定 Git/文件哈希、角色识别线索、真人预览结论。优先筛查人物误匹配风险；确实找不到适当来源时保留 `missing_source`，不能为了做满 123 而造假。对外默认角色选择器应继续隐藏程序演示图，展示“待获取真实资源”而不是错误的“已完成”。

## 本轮追加：3 个固定原作者备选图集（2026-10-25）

已确认 [rullerzhou-afk/codex-fan-pets](https://github.com/rullerzhou-afk/codex-fan-pets) 固定版本 `7e1deb0c5b825856ccad0f4c01a0d3ca03dbe1ff` 的 **可莉、宵宫、芙宁娜** 三组 `pet.json` 与 `spritesheet.webp`。三组文件均登记精确 Git blob SHA 和字节长度，并在外部 Codex 安装器中绑定对应原神模板，扩展为 **53 个固定来源选项、30 名角色、93 名待补来源**。

三组属于**既有角色的新作者版本**，不能计作新增已覆盖人物、真人美术验收或 Windows 实机安装完成。源目录含中文，安装器严格允许 Unicode 字母和数字及安全路径分隔符，仍拒绝目录穿越。个人安装示例：

```bash
python tools/install_external_codex.py klee_fan --role-root res/role --accept-personal-use
python tools/install_external_codex.py yoimiya_fan --role-root res/role --accept-personal-use
python tools/install_external_codex.py furina_fan --role-root res/role --accept-personal-use
```

新来源需要逐帧评估 Q 版人物辨识度，再决定是否在界面中优先推荐；现阶段仍只算来源候选。

## 2026-10-25：新增独立人物早柚 Sayu 的固定图集来源

- 公共作者资源：[mn8821236/petscodex/cozy-sayu](https://github.com/mn8821236/petscodex/tree/a4e3532b15da80e73845f1c431a44e55b5b894fb/cozy-sayu)，上游登记的艺术作者为 Cozy Critters Studio，精确 Git 提交 `a4e3532b15da80e73845f1c431a44e55b5b894fb`。
- `pet.json`：467 字节，Git blob `625d83dc3eacea82d0b08d699a0d4c6a139d5c37`；`spritesheet.webp`：1,554,794 字节，Git blob `6aaefa1074a2e72d73333a171575b4ff8b9693e7`。来源描述对应《原神》的早柚；两份原始文件均可追溯，安装器仅按固定文件读取，绝不拉取整个巨大上游仓库。
- 早柚此前未有固定动画来源，因此候选来源数由 53 → **54**，不同人物覆盖由 30 → **31/123**，尚缺由 93 → **92**。这些都只是固定**素材候选**数量，不是人工视觉合格数。
- 本机个人安装命令：`python tools/install_external_codex.py sayu_cozy --role-root res/role --accept-personal-use`。原始图集经 Git blob 校验后转换成独立的原生角色，旧角色不会覆盖。
- **画风与身份人工验收仍未完成**：必须检查早柚的狸猫头饰、衣装、忍者包、尺寸比例、动画连续性；若显著偏离原设，不能标记为正式完成。代码自动化测试不证明人物像貌或分发授权。CI 增加了真实联网下载/转换门禁。

## 本机直接导入第三方标准 Shimeji ZIP（2026-10-25）

新入口：**系统 → 角色管理 → 添加角色 → 个人本地导入：Shimeji 原画 ZIP（仅提取图片）**。适用此前已经手动下载、包含标准 `img/shime1.png`～`shime46.png` 编号图片的 Shimeji ZIP（不保证所有变体兼容）。

- 仅从本机选择 ZIP，用户明确选择与原画对应的原神人物模板；不会根据 ZIP 文件名、网页名称或服饰颜色猜身份。
- 解析 ZIP 时设置成员数、总解压量、单 PNG 大小及长宽上限，拒绝重号和明显的压缩异常；**不会解压或运行 .exe/.jar/.bat/.py/.sh**，不执行任何外来代码。
- 要求真有标准 `shime38` 待机、至少两张不同走路姿态帧；源 `shime*.png` 按原始字节存入 `source_frames/`，将真实存在的帧映射为有限的待机、行走、拖拽、跌落、抚摸等动作；缺少的动作不能造帧冒充。
- 使用临时目录完成原生配置、资源结构检查、逐帧预览；验证失败不创建正式角色，成功后独立目录安装，不覆盖旧角色/存档。
- 来源收据记录 ZIP SHA-256、用户选的人物 ID、原始帧数量，**明确艺术原设相似度、来源权利和 Windows 实机动画都未人工验收**。该功能本身不增加已核验固定作者来源的 31/123 数字。
- 例如此前找到的 [荒泷一斗](https://shimejishop.com/free/wp-content/uploads/2026/09/50036.zip)、[卡维](https://shimejishop.com/free/wp-content/uploads/2025/09/628.zip) ZIP，目前仍需要实际下载、检查其内部帧约定、检查和原设的相似度。不能因为有 ZIP 下载按钮就宣称已安装。

命令行也可使用：`python tools/install_personal_shimeji_zip.py --archive your.zip --profile genshin_kaveh --personal-use`。优先使用图形界面，不要求普通用户配置命令行。

## 社区 Codex ZIP 来源检索与本机导入（2026-10-25）

本轮扩展了两个对非程序员有实际帮助的功能：

1. **社区候选预览**：在「全部角色库」先切换「仍缺公开作者素材（待补齐）」，选中对应人物，点击「浏览本人物公开候选（待核验）」，只打开可信指定域名的 [CodexPetDB 原神角色合集](https://codexpetdb.com/en/collections/genshin-impact) 中该人物的预览页。该合集当日列出 **35** 个素材条目，其中 **33** 个有精确人物 ID 对应，2 个 Manekina 变体不属于本项目 123 个原神角色模板；与已固定版本来源去重后，得到 **29 个以前缺来源人物的新检索线索**。下载素材真实性、美术相似度、许可、哈希均未审查，不能算来源已固定的角色。
2. **安全的个人 ZIP 导入**：用户从可信页面手动下载 Codex ZIP 后，在「系统 → 角色管理 → 添加角色 → 个人本地导入：Codex 动画 ZIP（仅提取图集）」选择压缩包，并手动绑定原神人物。只处理同一目录内的 `pet.json` 与 `spritesheet.webp` 或 PNG；校验格式、图集尺寸、压缩大小与 ZIP 路径、资源 SHA-256；绝不执行或解压外部程序和脚本。导入时完整保留作者图集原始动作像素，另生成原生桌宠动作与本机收据，且不会覆盖已有角色。CLI 同等入口：`python tools/install_personal_codex_zip.py --archive "pet.zip" --profile genshin_kaveh --personal-use`。

对应模块 `tools/community_codex_leads.py` 可执行 `--new-leads-only --output unreviewed-leads.json` 查看 29 个待审线索，并与精确哈希来源统计 `tools/character_source_coverage.py` **完全隔离**。双重测试 `tests/test_personal_codex_zip.py`、`tests/test_community_codex_leads.py` 验证打包安全、像素完整性、角色绑定、缺口计数和 GUI 明确点击，纳入 GitHub Actions。

**覆盖分母与结论不变：当前精确版本来源 54 套、31/123 个人物；29 位仅新增网络候选，不是 31→60 已验收。** 即使本机安装成功，还要比较游戏人物外形、作者署名、声音/动作质量后才能标为完成。

## 2026-10-25 本轮补充：React-Shimeji 作者候选及独立检索界面

- 从 [CarbonNeuron/react-shimeji](https://github.com/CarbonNeuron/react-shimeji/tree/35b507062be71e8b9dbea6d20b77a9901dfe9114) 的 2,224 套公开角色包中，核对 **艾尔海森、安柏、哥伦比娅、菲谢尔、菲米尼、卡维** 6 位此前没有固定来源的角色。各自 `package.json` 标明角色名；`index.ts` 采用 **Git LFS** 储存，已固定上游 commit、pointer Git blob SHA、实际大文件要求的 SHA-256 和声明大小；其中 4 位带可打开的 `preview.png`。详情见 `tools/react_shimeji_source_leads.py`。
- **重要边界：** 当前通过 GitHub API 只能获取 LFS **指针**，无法访问其 0.7–1.2 MB 原始动画文件字节并检查人物/帧的真实质量。这是 6 条**候选线索**，绝不作为已固定可安装的创作者原画、人工原设一致性验收或画师再发布授权。此处的 MIT package 标记不能替代游戏角色美术的授权证明。
- 此前登记的 [CodexPetDB 原神目录](https://codexpetdb.com/en/collections/genshin-impact) 29 位未覆盖人物线索与本轮 6 位去重后，有 **31 位不同的未覆盖人物**具有至少一条待核验网络线索：新增的两个独立人选是安柏和菲谢尔。仍有 **61 位**缺少本项目已登记的这两类候选线索（92-31）；以上候选绝不冒充已固定素材来源。
- 「全部角色库」新增筛选 **「有社区候选、待核验真实性」**，显示 31 位候选人物并保留当前角色 ID。选中人物后点击「浏览本人物公开候选（待核验）」：若该人物对应多个来源，由用户明确选择浏览；**不后台下载、不运行 npm、Git LFS TypeScript 或 Shimeji 代码、不导入未经审核的画风**。直接查看已有 `preview.png` 也不能充当动态动画完整验收。
- 独立测试 `tests/test_react_shimeji_leads.py` 核对 6 位、LFS SHA-256、31/123 固定来源不变；实际 Qt 测试 `tests/test_react_shimeji_qt.py` 核对“31 位来源候选”界面筛选、无触发时不联网、安柏单一来源直达和卡维双来源取消/确认分支。所有 CI 门禁按同一 SHA 验收。

**新的真实来源冻结计数仍是 54 个版本 / 31 个不同角色 / 92 人缺固定素材。** 工作目标是把已检索的候选逐人补上真实帧、视觉对照、可复现安装和动作验收，直到 123 人全部完善；只增长候选数不是项目完成度。

## React-Shimeji LFS 动画的安全本地转换（2026-10-25 追加）

此前六份候选仅有 GitHub LFS 指针；本轮进一步实现 `tools/install_pinned_react_shimeji.py`，支持**用户亲自下载完整的上游 `index.ts` 后**转换为可供 DyberPet 使用的真实像素动画，绝不执行 JS/TS 或安装第三方 npm 包。

- 入口：角色管理 → 添加角色 → **「个人本地导入：React-Shimeji 完整图集 TS（先校验 LFS）」** → 选择本机完整 `.ts` → 选对应六位人物 ID。支持艾尔海森、安柏、哥伦比娅、菲谢尔、菲米尼、卡维；其余人物不允许猜测匹配。
- 若拿到的还是 `version https://git-lfs.github.com/spec/v1` 开头的**指针**，程序将明确拒绝，不当成动画。只允许该人物固定 LFS OID 的 SHA-256 和文件字节长度都匹配的实际大文件。
- 源文件仅解析上游脚本生成器的 **JSON 字面量字段**（`id`、`spritesheet`、`sprites`、`actions`、`behaviors`），只读取嵌入的 PNG base64 数据和原始帧坐标。校验图集大小、坐标边界以及必须存在的真实待机和两种不同走路帧。
- 程序把图集的原始像素裁切成临时 `shimeN.png` 图片，由现有 `install_personal_shimeji_zip.py` 的安全原生角色安装器复用动作映射、失败回退、文件不覆盖和本机收据；作者图集不在 GitHub 仓库中重新分发。
- 新增 `tests/test_pinned_react_shimeji.py`：通过离线合成的小型 PNG 图集测试**真实坐标裁切**、SHA 拒绝、LFS 指针拒绝、错误人物拒绝、坏矩形拒绝、不执行恶意脚本文本以及重复安装不覆盖旧角色；纳入角色导入 CI。
- **注意：** 这使符合上游规范的实际 LFS 大文件有了可审计的安装途径，但当前环境无法获取六份实际图集字节，所以尚未完成它们的真实包端到端验证、原设画风验收或声音测试；因此固定来源仍为 **54 版本/31 人**，6 位仍为待验收的网络候选。CI 使用人造测试图检验转换安全和功能，不将其当作任何原神角色的原设形象。

## 工程纠错：标准 Shimeji 编号动作语义修复（2026-10-25）

对照 [Shimeji-ee 原版 `conf/actions.xml`](https://github.com/logany20/shimeji-ee/blob/master/conf/actions.xml) 和 [Shimeji-Desktop 同规范](https://github.com/DalekCraft2/Shimeji-Desktop/blob/main/conf/actions.xml)，发现原先复用 `tools/install_nanopet_shimeji.py::GROUPS` 的**通用**编号映射有误：

- 原先 `stand=(38,)`，但标准站立 `Stand` 使用 `shime1.png`，标准行走 `Walk` 使用 `shime1/2/1/3`。第 38 张为克隆/拉起同伴姿态，不应映射为通用站立。已统一改为 `stand=(1,)`，取 1 帧尺寸，而非错误的 38 帧尺寸。
- 原先 `pat=(31,32,33)`，实际上这些是窗沿坐姿；**标准包并不保证存在单独的抚摸响应动画**。已从通用动作映射中删除该伪造的 `patpat` 来源，`pet_conf` 的触摸反馈暂回退到原有待机姿势，界面不会称作作者真正的抚摸特技。
- 更明确地将 `shime11` 归类为坐下/休息，`shime21` 归类为躺下，`shime20` 为匍匐，`shime18/19` 为落地缓冲，`shime12–14` 为攀爬。原始 PNG 全部保留，未进行 AI 伪造或重复复制。
- 通用个人 ZIP 不再把第 38 帧设为强制必要条件；测试加入**不含 38 但有 1/2/3**的标准合法包，并确保仍能转换，单元测试同时确认没有凭空生成 `patpat` 动作。
- 修复覆盖固定 NanoPet 作者素材、Shimeji ZIP 个人导入及 React-Shimeji 图集 LFS 导入。旧本机已导入的目录需要用户选择原作者版本重新导入，以更新已有动作，代码不会自动覆盖或删除旧角色。

**验收边界：** 此项是标准编号资源的动作语义纠错，不能证明每位画师都严格遵循同一动作排布。若源角色具有**独立自定义的 `actions.xml` 映射**，后续应优先读取该特定作者定义，而不是无条件假定所有动画都一样；原设画质仍须真人看真实帧。

## 2026-10-25：抚摸互动纠错和本机安装事务修复

- Codex V1/V2 原作者图集的 `wave` 仅能证明角色可招手，不能证明提供真实抚摸响应。修复 `tools/import_codex_pet.py`：`patpat` 从错误的 `wave` 回退到 `idle`，真正的 `wave` 仍可作为独立「打招呼」动作。增加只含原始待机+招手的回归测试，禁止让角色被摸头时无故挥手。真实独立抚摸动作需后续寻找画师原始帧。
- React-Shimeji 完整 LFS 本机导入以前先提交安装目录，再回写 `PERSONAL_IMPORT.json` 来源校验信息；若发生磁盘写入失败，会遗留缺少可信来源记录的半成品桌宠。现通过 `install_personal_shimeji_zip(..., verified_react_sha=...)` 在临时安装目录内一次性写好来源 SHA、原始像素声明和人工未验收标记，预览生成完成后才原子性重命名，失败自动清理暂存目录。
- 增加异常注入测试：故意让原生预览生成器失败，确认本机 `res/role` 不出现半安装角色；无效来源摘要被拒绝且不会创建角色目录；不影响原有不覆盖已安装角色的规则。
- **上述是动作真实性、安装完整性和回归可靠性整改，不增加可固定校验的原画覆盖数量。** 仍为 31/123 位已有固定来源，其他 92 位待补；所有角色的人工原设视觉/实际设备验收须独立完成。

## 2026-10-25：异常大 ZIP 导入边界加固

- 标准 Shimeji ZIP 导入原先限制 ZIP 条目数及解压字节数，但在编制来源收据时用 `source.read_bytes()` 一次性读取整个 ZIP。现在先拒绝大于 **96 MiB** 的本机原始 ZIP，然后用 **1 MiB 分块计算 SHA-256**，不把异常大压缩包一次性载入内存。
- 增加超过原始 ZIP 限制的稀疏文件测试，验证进入 ZIP 解析和创建角色目录之前就被拒绝；正常压缩包的流式摘要与原始 SHA-256 完全一致。
- 入口继续只提取标准编号 PNG，不执行第三方 ZIP 中的 EXE、JAR 或脚本；原始压缩包安全性与人物原画视觉验收仍分开判定。

## 2026-10-25 · 四位不同原神人物原始图集正式 SHA 校验（35/123）

本轮把前一阶段 31 名纯网络线索里的**卡维、基尼奇、绮良良、艾尔海森**四人推进为“提供方固定 ZIP + 本项目独立逐字节 SHA-256 校验通过”。与 GitHub LFS 的仅指针候选不同，GitHub Actions 已**真实下载**对应 ZIP 并验证 `pet.json.id`、图集格式/尺寸以及下载包的全文件长度。固定素材来源统计由 **54 → 58 套**，不同角色由 **31 → 35 人**，缺固定校验来源由 **92 → 88 人**；四份文件是原画提供方的作品，不是 DyberPet 自画占位。

| 人物 | 固定 r1 ZIP SHA-256 | 已验证字节 | 在线来源 |
| --- | --- | ---: | --- |
| 卡维 | `5d1d0ca4ec073d547947b18cecc4c659b363664eaf8a866b248130c4920e1065` | 813,411 | [原始 ZIP 说明](https://codexpetdb.com/en/pets/gi-kaveh/download) |
| 基尼奇 | `fdda86a6f1e9cdad9eb967385ed05a5ec561730f45350ee2661046adef2a177f` | 1,153,165 | [原始 ZIP 说明](https://codexpetdb.com/en/pets/gi-kinich/download) |
| 绮良良 | `5bf7fe02a4cbfd93587e0d33e0b56b5ca44e9f77a9de31e742a33435dd87d21a` | 655,190 | [原始 ZIP 说明](https://codexpetdb.com/en/pets/gi-kirara/download) |
| 艾尔海森 | `90e3b8427f80616b8ec48d2fa5c1c2ac8c1f6c7389dab5aa4874dd4729f6162b` | 824,182 | [原始 ZIP 说明](https://codexpetdb.com/en/pets/gi-alhaitham/download) |

证据：`Character MOD importer tests` 中名为 **Public CodexPetDB r1 ZIP integrity (non-gating candidate)** 的独立下载步骤在 GitHub CI 真实读取了这四份 ZIP；首次额外进行安装验收时重复下载触发 CDN 429。现已整改为单次下载→本地缓存哈希复核→原生转换，不再让同一安装过程对源站请求两次。**本项目不在 GitHub 提供/再分发实际图集 ZIP。**

**非程序员操作：** 「系统→角色管理→添加角色→个人使用：下载 SHA-256 固定的四位原神角色原画 ZIP」选择本人，确认仅私用下载。系统按完整 ZIP 字节长度+哈希双重校验、仅提取 `pet.json` 和 `spritesheet.webp/png`，在临时目录原生转换并写入人物身份、ZIP 来源收据、16 动作原帧预览和逐帧质量审查 JSON，全部准备好后才提交新角色目录。错误 ZIP/断网/QA 过程异常不会覆盖老宠物。

**严格验收分离：** 35/123 是固定可校验来源覆盖，并非 35 人都已安装到用户电脑或原设视觉通过。原画轮廓、配色、道具、表情、动作独特性、原声授权、Windows 实机动画及许可均需逐人人工检查。结构性 QA 可发现重复静帧和缺帧，却无法自行证实原设相似度。

## 2026-10-25 · 从角色库直接安装 + 离线 ZIP 安装修复

- 修复「**全部角色库 → 选中卡维 / 基尼奇 / 绮良良 / 艾尔海森 → 安装真实作者素材**」未列出新固定来源的缺陷。统一来源菜单现在包含 `codexpetdb_zip`，只向选中的正确人物显示匹配的已固定 SHA-256 素材，不会把《明日方舟》的同名绮良或原创 Amber 方块宠物当成《原神》人物。
- 修复工作线程把 `"kaveh"` 转换为 `Path("kaveh")` 后直接传给字符串键安装器的错误；改为明确传递被选中的原始字符串 `source_key`。
- 支持两种非程序员入口：**① 角色库专属原画安装（在线下载）**；**②「添加角色 → 个人本地导入：已下载的 SHA-256 固定原画 ZIP（断网可用）」**。后者可解决第三方 CDN 429 限流或甲方设备临时无网络场景；文件仍必须通过固定版本大小/哈希/角色 ID/图集解析，不接受任意同名 ZIP。
- 两种入口均由 `ChibiImportThread` 调用相同的原子安装器，安装成功提示打开作者原始动作预览；没有通过视觉人工验收时仍保持明确的「待人工检查」状态。
- 新增 `tests/test_pinned_gui_dispatch.py`，直接提取并执行生产版后台线程的 `run` 实现，在不依赖 Qt 的测试环境下用模拟安装器核验在线和离线两种分发参数、字符串角色 ID 以及失败不改老角色，并加入角色导入 CI。
- 角色覆盖仍为 **35/123 固定版本来源，88 人待补齐**；本轮重点在用户真正能获取/安装/查看这四个新增角色，不额外声称视觉原设已通过。

## 2026-10-25 · 第二批固定原始素材：39/123

白术、坎蒂丝、夏沃蕾、莱依拉已在 [Character MOD importer CI](https://github.com/clonetimer/DyberPet/actions/runs/40199505490) 中真正完成**原始 ZIP 下载→全文件 SHA-256→人物 ID→图集尺寸→原生角色安装→逐帧质量报告**。四份原件分别为 828,590、1,030,614、744,234、977,903 字节；每份转换获得 9 类原生动作和 57 帧图片。所有来源标记依旧保留“**未进行人工原设外观/独特互动/声音验收**”。

截至本轮正式固定来源为 **62 套版本、39 名角色**，剩余 **84 名**缺固定来源。新增四位已加入本人电脑上的 GUI 专属素材安装入口（在线 SHA 校验 / 手动已下载 ZIP 安装）。另有千织、赛诺、迪希雅、菲米尼四份公开目录哈希记录正处于下一批未核实候选库 `tools/codexpetdb_pending_zip_leads.json`，只有真实安装验证通过后才提升来源计数。

如需核查人物形象一致性，请优先从已安装原始 PNG 动画预览检查五官、发饰、服装、代表性道具和动作姿态。**仅以真实帧数或文件签名合格不能代表人物视觉还原合格**。

## 2026-10-25 · 第三批真实 ZIP 完整验收：43/123

第三批千织、赛诺、迪希雅、菲米尼由 [GitHub Actions](https://github.com/clonetimer/DyberPet/actions/runs/40200108936) 完成来源 SHA-256、原始文件长度、`pet.json` 人物身份、图集解码、原生安装及动作帧结构报告，四位每人 **9 类动画、57 帧**；并没有把作者美术存放进本项目 GitHub。原有 39 人正式来源集合现新增四个人物的固定版本记录，累计为 **66 套来源、43/123 人，剩余 80 人缺固定来源**。

对应来源现在可以在 GUI 的「全部角色库 → 该人物 → 安装作者原画」中选择；输入错误角色包时必须拒绝，所有新人物仍显示原设画风和专属语音待人工核对，不应把「自动化 9 类动画」当作实际有“摸摸头/坐下/攀爬”等全部独特动作。

`tools/discover_new_codexpetdb_pins.py` 从来源方官方 JSON 目录筛选当前缺固定来源的动画包，提供其固定版本哈希及文件大小；这些扫描候选不得直接入库，必须经过 `tools/verify_pending_codexpetdb.py` 实际下载与原生动作验收，才可提升“固定来源”计数。下一阶段将延续分批验证、逐个原设视觉核查、角色音效匹配。

## 2026-10-25 · 第四批实测固定素材：47/123

对 [CodexPetDB 原神合集](https://codexpetdb.com/en/collections/genshin-impact) 已发现的 ZIP 继续进行独立验证。[CI 检验批次](https://github.com/clonetimer/DyberPet/actions/runs/40202505076) 最初发现**艾梅莉埃**指定版本返回 HTTP 404，已明确排除失效来源，不得仅凭目录元数据就计入人数。改选**伊安珊**后，四份素材均实际下载并完成全 ZIP SHA-256、长度、人物 `pet.json.id`、原始 PNG/WebP 图集、原生安装、动作逐帧结构审查。

| 本批人物 | 实际 ZIP 字节数 | 验证所得原生动画 |
| --- | ---: | --- |
| 夏洛蒂 | 835,499 | 9 类动作 / 57 帧 |
| 哥伦比娅 | 1,212,976 | 9 类动作 / 57 帧 |
| 嘉明 | 1,141,319 | 9 类动作 / 57 帧 |
| 伊安珊 | 783,798 | 9 类动作 / 57 帧 |

四份来源均已录入 `tools/codexpetdb_pinned_zip_leads.json`，GUI 可对指定人物选择个人在线或离线 SHA-256 安装。新来源固定覆盖 **66→70 套、43→47 位不同人物**，剩余 **76 位**缺少此级来源验证。**9 类动作**只表明该图集转换器具备对应原始帧和动作配置，不意味着每位人物有自己独特的高还原摸头/语音等专属动作。

与用户要求保持一致：角色外观是否符合原设，需要逐人看源图与游戏人物服装/配色/道具/辨识度；当前未执行这四人的人眼原设对照，不批准 A/B/C。Windows 本人设备与 GitHub Actions 是不同的验收环境，仍需单独检查。

## 2026-10-25 · 持续覆盖到 51 / 123：爱诺、达莉娅、菲林斯、蓝砚

本轮从独立官方公开目录发现的待核验项目中，新增四位**原神人物专属发布 ZIP**，并在 GitHub Actions [run 40206859844](https://github.com/clonetimer/DyberPet/actions/runs/40206859844) 的「Next four Genshin ZIP byte and animation verification」真实下载安装、比对完整 SHA-256、`pet.json.id`、PNG/WebP 图集，并转换成每人 **9 类原生动作 / 57 帧**。四人原画 ZIP 内容及原生转换检查全部成功，均有本机临时工作区的动作像素结构报告；源图集未复制进 Git 仓库，也没有发布到发行介质。

| 人物 | SHA-256 | ZIP 字节数 | 结论 |
| --- | --- | ---: | --- |
| 爱诺（Aino） | `37b16a5d7d002b8d702de543782ba71a54397006d02676cea304c109a6233b11` | 1,245,895 | ZIP+动作结构通过 |
| 达莉娅（Dahlia） | `67184f9eafc466af27baf82c475b598cb79085ce9d8acd947330dd219ec7566f` | 720,705 | ZIP+动作结构通过 |
| 菲林斯（Flins） | `860561c7accdcda2a970fa8e3b20264a1079492ad87fae136a2ef29ae029ecda` | 733,245 | ZIP+动作结构通过 |
| 蓝砚（Lan Yan） | `f821e89ebb1eecbb9ef3d3f7b879577c6cfe0177381997dce930f4f06a3b32cb` | 882,508 | ZIP+动作结构通过 |

固定可校验作者来源由 **70 → 74 套、47 → 51 位不同人物、缺口 76 → 72 位**。其中 CodexPetDB 已精确固定 20 个 ZIP；其余来源来自既有独立画师/原生或 Shimeji 资源。上述结果证明素材文件一致、人物 ID 映射和结构性动作安装成功，但**绝不等同于原作美术相似度、授权许可、声优原声或 Windows 实际屏幕播放通过**。这些人仍需逐帧人工与原设对照，不可盖章「形象完善」。

新增 4 位所用验证候选保存在 `tools/codexpetdb_next_zip_probe.json`，通过后纳入 `tools/codexpetdb_pinned_zip_leads.json`；测试矩阵同步要求 **74 / 51 / 72**。后续新角色需要独立验证新的 ZIP，不应将已固定的候选反复下载来增加计数。

## 2026-10-25 · 源码分支新增四名经过独立 ZIP 校验的原神人物（55/123）

本轮通过 GitHub Actions「Next four Genshin ZIP byte and animation verification」在 **2026-10-25** 真实获取全量 ZIP、校验 SHA-256、源文件长度、`pet.json.id`、原始 WebP/PNG 图集，并完成每位人物的 DyberPet 原生安装和 `ACTION_PIXEL_AUDIT.json`。与上一批 51 人来源去重后，新增四位不同人物：

| 角色 | 固定来源 SHA-256 | ZIP 字节数 | 原生动作 |
| --- | --- | ---: | --- |
| 杜林 Durin | `8fc8bfa96092c3f060ba51ea6765f3847bc5a0b740929c3b3b97b430aba4c1bc` | 1,008,717 | 9 类 / 57 帧 |
| 伊涅芙 Ineffa | `c278705518a21cf959ec164d4f5e349af64079326e302a9bc31c87f4e4e4664f` | 844,872 | 9 类 / 57 帧 |
| 雅霍达 Jahoda | `e9ecf6019e672519fcbbe8347193f4e4e483be4bd448348408f68fbe31bd41b8` | 827,665 | 9 类 / 57 帧 |
| 菈乌玛 Lauma | `e52b9873ff3bd8085239c6454fdacadf2551db12671f8f1a1ec369789c7408ec` | 869,915 | 9 类 / 57 帧 |

该批独立测试日志：[GitHub Actions #40208685596](https://github.com/clonetimer/DyberPet/actions/runs/40208685596)。测试回执明确 `independent_actual_bytes_verified=true`、`native_install_verified=true`、`character_likeness_manually_verified=false`。

- 本项目来源登记已扩展至 **24 份 CodexPetDB ZIP**，总计 **78 份固定来源，覆盖 55/123 人物；68 人仍无固定来源**。
- 作者原始 PNG/WebP 不提交到仓库或公开 Release，普通用户通过「角色管理→安装真实作者素材」选择已核验版本；如网络限流可在本机导入已下载的匹配 ZIP。
- **55/123 不等于 55 人形象经过人工核准，也不等于全部 55 人已在用户电脑安装。** 尚需逐个与网络原设外观比对、专属互动动作和声音、Windows/Linux 图形桌面实际播放。
