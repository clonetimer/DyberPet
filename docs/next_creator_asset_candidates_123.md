# 123 角色公开动画素材：下一批来源核验工作台（2026-10-25）

> 此表是**未核验候选**，不是已安装角色，也不增加 `character_source_coverage.py` 的 30/123 统计。优先真实精细 Q 版，其次画师 Shimeji；拒绝简笔画、空白模板及跨人物错配。

| 候选资源 | 公开页面证明的角色 | 资产形式 | 新覆盖判断 | 核验状态 |
| --- | --- | --- | --- | --- |
| [rullerzhou-afk/codex-fan-pets](https://github.com/rullerzhou-afk/codex-fan-pets) | 可莉、宵宫、桑多涅、派蒙、芙宁娜，另有丘丘人（不在 123 位人物统计内） | `pets/<role>/pet.json` + `spritesheet.webp` | 需与既有来源取并集去重；不可直接加 6 | 待固定 SHA / 帧预览 / 角色 ID |
| [chenxin-dlut/codex-anime-pets](https://github.com/chenxin-dlut/codex-anime-pets) | 芙宁娜、甘雨、胡桃、可莉、雷电将军等 | Codex 角色图集与 contact sheet | 主要为候选画风替代，不推断新增角色 | 待固定 SHA / 视觉分级 / 去重 |
| [ZaytsevZY/genshin-pets](https://github.com/ZaytsevZY/genshin-pets) | 胡桃、茜特菈莉 | 角色安装目录、GIF 与 QA 图 | 胡桃已经有来源；茜特菈莉也须先对照现有名录 | 部分来源已登记，禁止重复计算 |
| [AkshitIreddy/AI-Desktop-Pet](https://github.com/AkshitIreddy/AI-Desktop-Pet) | 绫华、阿贝多、重云、枫原万叶、胡桃、可莉、托马、温迪 | 作者 Shimeji 原动作 | 已固定进入既有工作台 | 已登记，不重复新增 |

## 将候选转为可用来源的必要步骤

1. 确认原作者、仓库具体 commit、角色名与原设特征（发型、服饰、饰品、色彩）；去掉同名其他作品、错配角色和不合格简笔画。
2. 打开每个角色真实待机与行走帧；检查不是一张图复制多帧、不是自动生成的替身。P1 精细 Q 优先，P2 正确 Shimeji 备选。
3. 原样记录 `pet.json` / `spritesheet.webp` 或独立 PNG 的 Git blob、字节数、动作帧映射；不要因为 README 写有角色名字就算“找到素材”。
4. 在独立的 installer manifest 中新增**稳定人物 ID**和哈希，并写下载校验/错误回退测试；来源只能在用户本机主动确认后安装。
5. 在 Windows/Linux 真实 Qt 中预览、切换、透明显示和动作；最终原设还原由逐人视觉复核决定，不能由 CI 绿灯代替。
6. 仅在上述前四项均可信后更新“固定来源覆盖数”；只有真实安装与人工核验均通过才可标记已完成。

## 用户验收状态定义

`missing_source` → `candidate_unverified` → `pinned_source` → `installed_local` → `visual_approved` → `desktop_accepted`。

**禁止:** 自动以演示几何图生成所谓正式人物；把图集来源等同原作外观验收；未经素材权利核实将其他作者图包上传公开 GitHub Release。前端应显示真实状态而非虚假的“123 人已内置”。

本阶段的新增发现来自各上游公开 README，并非逐帧视觉核验结果。

## 2026-10-25：额外公开 Shimeji 资源候选（不计入固定来源）

| 角色（原先未覆盖） | 公开页面 / 署名 | 实际发现 | 计数与下一步 |
| --- | --- | --- | --- |
| 荒泷一斗 `genshin_arataki_itto` | [Arataki Itto Shimeji](https://shimejishop.com/free/arataki-itto-shimeji/)，页面署名 **Ookami** | 页面展示预览及下载入口，且称可运行 Windows/Mac/Linux | 尚未核实原始动画文件来源、内容安全、SHA 和角色真实帧，先不计数 |
| 卡维 `genshin_kaveh` | [Kaveh Shimeji](https://shimejishop.com/free/kaveh-shimeji/)，页面署名 **ilewdha** | 有角色动作预览与下载入口 | 尚未核实原始 PNG/XML 下载包与哈希，先不计数 |
| 基尼奇 `genshin_kinich` | [Kinich Shimeji](https://shimejishop.com/free/kinich-shimeji/)，页面署名 **shimejimascot** | **注意**：分类页写 Free，但详情页只提供 Buy 按钮 | 不当成可免费直接下载；需确认真实资源渠道与作者授权后再转入固定来源 |

候选页面包含“下载软件/运行 .exe/.jar”的文案。安全导入仅应提取经核验的 **图片和角色配置**，不能自动运行任意来源的 EXE、JAR、批处理或脚本。任何公开预览不等于真正取得合法、完整、可用的帧序列。所有这些资源的原设人物相似度亦未验收。

## 2026-10-25：两套 Shimeji 公开压缩包直链（下载入口已核实，素材未验收）

在源站实际点击下载按钮，得到以下压缩包地址，而不只是介绍页面：

| 角色 | 公开介绍/作者署名 | 用户本机压缩包获取地址 | 状态 |
| --- | --- | --- | --- |
| 荒泷一斗 | [ShimejiShop/Ookami](https://shimejishop.com/free/arataki-itto-shimeji/) | https://shimejishop.com/free/wp-content/uploads/2026/09/50036.zip | `candidate_archive_unverified` |
| 卡维 | [ShimejiShop/ilewdha](https://shimejishop.com/free/kaveh-shimeji/) | https://shimejishop.com/free/wp-content/uploads/2025/09/628.zip | `candidate_archive_unverified` |

本轮尚不能从运行环境取得 ZIP 字节，所以**没有谎称计算了 SHA-256、验证了 ZIP 内动画帧、安装成功或人工确认了角色外观**。这两个 ZIP 不能计入已固定校验的 31 人，也不能直接让程序执行包内的任何 EXE、JAR 或脚本。下一步在用户本机安全扫描后只提取真实 PNG/XML 等素材，再经独立角色绑定与原设视觉核验。不要把网页的“100% safe”宣传当作实际安全审计结果。

这些直链仅便于私人本机下载安装包；DyberPet 代码和公开 Release 仍不重新发布该动画包。


## 2026-10-26 · 荒泷一斗真实原始 ZIP 的独立探针

原先页面署名和压缩包直链仍只是未验证候选。新增独立 GitHub Actions 作业
`itto-external-shimeji-probe` 和离线模拟单元测试；只访问
[页面明确指向的 50036.zip](https://shimejishop.com/free/arataki-itto-shimeji/)，限制下载大小与跳转域名；无脚本执行，只读取 PNG，核对 ZIP SHA、shime1/2/3 帧、动作真序列、DyberPet 原生安装器预览及回执。即使通过文件结构，ZIP 并没有本项目可独立信任的《原神》角色 ID 绑定，因此仍需真人对照画面确认才可纳入固定来源。当前已固定来源仍为 65/123，不能以页面署名、截图或目录宣传代替原设美术验收。


## 2026-10-26 · Ookami 荒泷一斗候选：真实基本 ZIP 核验，待查完整动作

GitHub Actions [40266080104](https://github.com/clonetimer/DyberPet/actions/runs/40266080104) 中独立非门禁作业真正下载了上游基本 ZIP（1,071,157 字节，SHA-256 `6af3ed562cc59a9b6e0a3c351a5abc69213edda44d30f891f2c6c38ebd9b4b33`）。确认了 46 张 Shimeji 编号原始 PNG、10 个本机转换的原生动作和完整图片安全导入，**但深度结构审计检出 `movement_has_no_distinct_frames`**，且 ZIP 自身不能证明人物一定是《原神》荒泷一斗。因而仍为未计覆盖候选，不能称作动态动作合格。

来源网站同页还提供第二份明确命名的 `50036_full_animation.zip`，本次追加严格 URL 白名单、两包独立校验及每项异常动作明细输出。若两包均没有通过深度结构验收，CI 非门禁任务会失败而非虚报 PASS；若完整动画版通过结构检测，其人设外观、作者身份及来源许可仍必须人工复核后才能晋级固定来源。当前全项目仍为 **88 套 / 65 位 / 缺 58 位**。

## R18 · 卡维 Shimeji 候选原画的独立审计（2026-10-27）

卡维 **已在** 65 位固定来源原神角色名单之中（CodexPetDB 的 `kaveh`），本轮检索到的另一份原作不是第 66 位人物，也不能冒充“新增角色”。它的价值在于可能作为卡维现有图集的**另一套原作者动作/画风候选**。

- 公开页面：`https://shimejishop.com/free/kaveh-shimeji/`；页面列出 Kaveh / Genshin Impact，并署名画师 `ilewdha`，但这不是画师直接授权或官方身份凭证。
- 页面下载链接：`https://shimejishop.com/free/wp-content/uploads/2025/09/628.zip`。
- `tools/probe_shimejishop_kaveh.py` 仅在隔离 CI 中、使用固定 HTTPS URL 拉取，不允许跨站跳转，限定 32 MiB，只读真实 `shimeN.png`，跳过 EXE/JAR/脚本，以现有 Shimeji 转换器生成临时本地桌宠并进行完整帧和运动姿态审计。
- 逐动作记录原始帧数、非透明像素去边界后的不同姿态数以及静态/重复/透明风险；始终标记 **未验证原设相似度、画师权益、真实 Windows 动作体验**。审核不通过时不得晋升固定来源或包装第三方素材。
- CI 只能上传可公开的文字日志，不上传第三方 ZIP、PNG 或用户私人角色存档；此前 65/123 来源数字仍维持不变。

若本轮审计通过，下一次才考虑在现有角色的“同人物原画 A/B”中以精确 SHA、来源许可确认和用户主动下载方式提供候选；不使用合成简笔画或虚构动作填充缺失帧。

### R18 真实 CI 下载与动作审计结果

[R18 独立核验作业](https://github.com/clonetimer/DyberPet/actions/runs/40499103815) 在 GitHub-hosted Ubuntu 环境访问上游原始 ZIP，完整读取了 990,054 字节，并测得 SHA-256：
`86b14aff32b1eeec87800c632817a21b22779a654d876d79a854fb14da4669c9`。解包识别 **46 张原始 PNG、10 个可通过 DyberPet 原生结构检查的动作**，没有执行源站 EXE/JAR，也没有提交、发布原画。

R7 去透明边界姿态审计显示：左右走各 3 帧/3 个不同姿态，攀爬 3/3，拖拽 6/6，着地 2/2；匍匐 `crawl` 1/1 与坠落 `fall` 1/1 均命中 `single_frame_motion`。**完整像素动作结构审计未通过**（`movement_has_no_distinct_frames`），所以不能宣称“10 个高质量动作”或“卡维动作质量已完成”。本轮独立探针只对走路真实姿态多样性放行，不会把整个角色默认为 Q 版/外观/动作/许可合格。

尽管原始下载 SHA 已验证，这份作者素材仍处于**需人审的第二套 Kaveh 候选**，不是可无条件分发的内置资源；现有 CodexPetDB Kaveh 来源不删除或替换。可在许可与原设验收后评估作为严格哈希可选本地下载来源，禁止计作原神角色来源覆盖净增人物。

## R23 · 新缺失人物候选：优菈（Eula），来自原始画师（2026-10-27）

- 人物固定 ID：`genshin_eula`，此前仍属于 **58 位缺来源角色**。
- 画师直接发布：[SaylaMars 原帖 r/EulaMains](https://www.reddit.com/r/EulaMains/comments/1e808mg/desktop_eula_pet/)；2024-07-20 画师说明自行绘制 Eula 动画并修改 Shimeji 配置，免费发放桌宠。
- 画师个人发布页：[Eula Shimeji (Desktop Pet), Pixiv FANBOX](https://saylamars.fanbox.cc/posts/8264436)。
- 额外交叉证据：[作者 HoYoLAB 预告](https://www.hoyolab.com/article/30892460)，作者自己指向同一 FANBOX 原帖。**这种直接作者证据优于第三方镜像，但仍不能替代 ZIP 级哈希和逐帧核验**。
- `tools/probe_artist_eula_fanbox.py` 检查公开 FANBOX 帖子的作者 ID、帖子 ID、角色名称和公开附件清单；只访问公开接口，不登录、不绕过付费或权限，拒绝外部下载站与不安全重定向。若公开附件直接可获取且为标准 Shimeji ZIP，才在临时目录读取 PNG、核对原始 SHA-256、转换为 Eula 专属原生角色并审计不同动作姿态；绝不执行 ZIP 中的 JAR/EXE。
- 非门禁 CI 记录结果，无源图上传。若 FANBOX 不向匿名客户端开放下载、ZIP 非标准格式或图片身份未确认，该来源继续标记为 **unverified_candidate**，既不触及现有 65/123 计数，也不自动填充默认角色；后续可由用户按照原帖的下载方法取得原始文件，再走已有的本地 ZIP 安全导入。
- 2026-10-27 尚无经核实的作者原始 ZIP SHA 和权利许可，**不宣称新第 66 人已经交付**。
