# 原神 123 人物：真实作者素材覆盖计划（2026-10-25）

> **不能用简笔画/程序低保真代替人物原画。**
> “角色模板存在”“发现创作者素材”“已安装能运行”“符合原设视觉”“拥有发布许可”是五项不同的事实。
> 本项目任何脚本都不能用自动生成的通用人物来冒充角色完成。

## 本阶段实测可追溯信息（不是 123 人完工声明）

- 人物/伙伴模板：**123**，与 GUI 名录一致；另有咕嘎和 Doro 两个独立吉祥物，不计入 123。
- 固定来源候选：**53 个动画来源选项，对应 30 个不同原神人物**；其中含同一人物的多个作者版本。
- **93 个角色尚无本项目固定校验的创作者素材来源**；后续需要按角色逐一检索并确认是该角色，不得凭文件名或艺术风格推断。
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

这一阶段的 30/123 是**角色身份可溯源的候选来源覆盖率**，不是美术相似度已通过率，更不是 30 个 Windows 真机已验收角色。未经来源许可不要将这些美术直接打包再分发。

## 新确定的风格优先级：精细 Q 版先行，Shimeji 作为备选

- **P1：精细 Q 版优先**。已核对过帧形态的老版 DyberPet 纳西妲、魈、流浪者为第一组的视觉风格示例；刻晴作者 Q 版也可优先预览，但不能直接计作人工相似度通过。
- **P1 待视觉核对：独立作者 / Codex 图集**。部分保留较丰富的服饰、眼睛与头饰，也可能仅有少量像素细节；不能仅凭 WebP 尺寸、作者名称和文件哈希自动评 A。
- **P2：原作者 Shimeji 小型动画**。只要人物辨识度确实满足要求可以使用，不能把非原设、简笔画、其他游戏同名人物充作合格素材。
- **人工 A/B/C 结果目前一律待审**。P1/P2 是用户指定的选材及安装排序，而 A/B/C 是逐角色视觉对比后的结果，绝不虚构。
- **新安装的角色库直接展示已找到来源的 30 位原神角色**；仍缺 93 位可切换“仍缺公开作者素材”筛选；不将“来源发现”混同“安装完成”。GUI 来源选择器优先推荐精细原生版，其次需看图核对的作者图集，最后可接受的 Shimeji。

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

## 下阶段继续补齐 93 人

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
