# DyberPet Personal65 私有预览版（Windows x64，Python 与 Rust）

## 2026-10-28 候选版本状态（R24）

- R27 那维莱特与莱欧斯利的两份原始 Git LFS 模块均已在 CI 完成全量 SHA-256、46 帧原生 PNG、10 类动作及本机安全安装核验；最新**固定来源覆盖 68/123**、缺 **55/123**。`crawl` / `fall` 缺少独立运动帧，原设美术、实际运动、配音和授权仍未验收。历史 Personal65 包名与旧的 65/58、66/57 段落属于旧阶段，**不等于当前预装角色数量**。
- 目前 GitHub API 返回该仓库 **Public**。私有预发布工作流因此不会创建 `v0.13.0-private65-rc1` Release，这是安全门禁而非打包故障。两份 Windows ZIP 已在 [Actions 运行 40542222679](https://github.com/clonetimer/DyberPet/actions/runs/40542222679) 作为短期 artifacts 产出，分别是 `personal65-python` 与 `personal65-rust`；artifacts 不是发行版 Release，也没有预装第三方角色原画。
- 对 10 月 27 日成功构建的真实 Python ZIP 进行补充检查，发现还混入了 CI 离屏运行生成的 `data/pet_data.json`、`data/settings.json`、`data/task_data.json` 和 `data/version`。R24 在最终运行检查结束后清除整个临时 `data/` 目录，再打包；程序首次启动时会自动生成新的数据目录和个人初始存档。实际旧 ZIP 不具备这项修复，请勿将它当作全新安装交付介质。
- 新增最终 ZIP 检查：逐项验证 `DyberPet.exe`、本机角色安装助手、双击启动入口、实际 Python/Rust 模式、运行时动态来源数（最低 R23 66/123，当前 R27 68/123）、ZIP CRC；拒绝含私人 `data/`、`Source*/` 原画、过时占位角色标记的包。失败时构建直接停止，不上传伪成功包。
- 解压新包后请优先使用 **`Install-Available-Roles.cmd`**，阅读来源条件并本机选择安装，然后在 **系统 → 角色管理 → 全部角色库** 中查看真正识别的角色。首次添加新角色需重启程序激活；来源覆盖不能替代实际安装数量或人工形象/动作验收。
- 即使上述 ZIP 门禁和 Windows CI 均通过，也不表示用户的 Windows 桌面真实播放、声线、外形相似度或来源许可已经验证，仍只称 **candidate / preview**。


## 版本定位

此候选基线来自 `release/personal65-python-rust-20261026`，其最新角色功能建立在 PR #28 的 65 个固定来源候选和 PR #29 的个人本地批量安装器上。

- **Python**：完整 PySide6/Python 桌宠，无 Rust 依赖。
- **RustHybrid**：桌宠 UI、语音、文件操作仍由 Python/PySide6 负责；Rust 仅以 PyO3 加速校验和资源索引。启动脚本设置 `DYBERPET_NATIVE_BACKEND=rust`，打包的真实 EXE smoke 必须报告 `native_backend.active=rust`。
- 两个压缩包是便携版，解压**整个目录**；不是单文件程序，不是纯 Rust 重写，也不是传统 Setup.exe 安装包。
- 65 指 **123 个原神模板中已有固定素材来源的 65 个角色（另外提供咕嘎、Doro 两只吉祥物的本地导入入口）**，并非已经完成 65 个原画包预装、原声或人工美术验收。另有 58 个角色尚无固定来源。
- 第三方图片、语音不会进入 GitHub Release。仓库 Private 不自动许可复制或再分发他人素材。

## 如果 Releases 已生成

从私有仓库 `Releases → v0.13.0-private65-rc1` 下载以下二者之一，并核对 `SHA256SUMS.txt`：

- `DyberPet-Personal65-Windows-Python.zip`
- `DyberPet-Personal65-Windows-RustHybrid.zip`

解压到新的空目录，避免覆盖旧版本和个人资料。双击 **`Run-DyberPet.cmd`** 启动。RustHybrid 如果原生模块丢失，程序会拒绝假装成 Rust 成功运行。

咕嘎/Doro：解压后双击 **`Install-Guga-Doro.cmd`**，先生成两只角色的来源与安装状态清单。在确认各自作者的个人使用条件后，输入 `INSTALL`，安装程序会在本机下载固定哈希的创作者图集并转换为原生动作。咕嘎与 Doro 不计入 65 个原神角色来源，角色仍需在 GUI 中进行外观和动作人工验收；真实原画、原声没有预装。

角色导入步骤：

1. 备份旧版 `data/`、`res/role/` 和个人配置。第三方素材从来不会随应用自动移入新的文件夹。
2. 双击 **`Install-65-Roles.cmd`**。程序先生成 `data/personal65-plan.json`，列出已安装、可获取、需手动导入和缺来源的人物。
3. 阅读该角色来源的使用条件；符合个人使用范围时输入 `INSTALL`，才会下载并校验选定的固定来源素材。原始内容的 SHA256/大小、人物识别 ID、动作帧会依现有安装器逐项检查。
4. 完成后查看 `data/personal65-install-report.json`：`installed_unreviewed` 是“本机安装且结构验证”的数量，不等于原设形象、声线、动作或 Windows 真机通过验收。
5. 打开桌宠 `系统 → 角色管理 → 全部角色库`，切换 **“已安装真实来源素材”**，逐个检查角色形象、头饰、衣装、动作帧和实际桌面行为。

如果某项来源失败，请保留报告；安装器不会覆盖已有真实角色。界面可手动导入现有 ZIP 等个人文件。不允许将本机原画文件加入下一次 Release。

### 安装成功数量的复核和进度提示

新版 `Install-65-Roles.cmd` 会逐角色打印安装编号、来源尝试、失败后固定来源回退及完成后的角色库复核情况；`Install-Guga-Doro.cmd` 同样报告两位吉祥物的最终状态。网络来源下载成功、安装器函数正常返回，**不等于**角色已经完成安装。安装批次结束后会重新扫描 `res/role`，匹配到同一人物身份且原生动画结构有效，才计入 `installed_unreviewed`。

报告新字段 `post_install_inventory_checked` 表示扫描是否成功，`post_install_recognized_creator_profiles` 表示本机当前可识别的不同原神角色总数；失败记录中 `post_install_validation_failed` 表示原本返回成功、但实际没有认出有效对应素材。咕嘎/Doro 报告有对应的 `post_install_recognized_mascots`。即使文件成功安装，**原设相似度、动作自然性、声线及真机使用仍未通过自动验收**。

若显示 `failed`，先查看 JSON 报告，确认真实角色文件存在、导入凭据与身份一致；修复后可重新运行安装器，仅处理仍未安装的目标。已有角色和存档不会被安装器自动覆盖。

## GitHub 托管构建被拒时：在本机一次构建两个包

GitHub Actions 在私有仓库需要有可用额度/账户计费设置。若看到两个 Windows 任务**瞬间失败且没有任何执行步骤**，应优先排查账户 Billing / Actions Budget，不能判定程序构建失败。在该限制解决前，使用自己的 Windows PC 构建（本地执行不会消耗 GitHub-hosted runner 分钟）。

先安装：

- Git 与 GitHub CLI（`gh`，需要推送 Release 时使用）。
- **Python 3.11 x64**，确保 PowerShell 中 `py -3.11` 可运行。
- **Rust stable MSVC 工具链**（rustup）及 Visual Studio C++ Build Tools（用于 PyO3 64 位编译）。
- 能联网安装 Python 依赖和 Rust crate 的环境；构建会下载编译依赖，不会代替你下载第三方角色原画。

Windows PowerShell：

```powershell
git clone https://github.com/clonetimer/DyberPet.git D:\Project\DyberPet
cd D:\Project\DyberPet
git fetch origin release/personal65-python-rust-20261026
git switch release/personal65-python-rust-20261026
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\Build-And-Publish-Personal65.ps1
```

脚本创建独立虚拟环境、构建 Python 与 Rust/PyO3 原生扩展、执行离线基本回归，并实际打包和测试两个 **EXE**，最后留下两个 ZIP 和 `SHA256SUMS.txt`。任何阶段失败就立即停止，不输出虚假的 Stable 结论。

若需要把**成功构建的两个 ZIP** 发布到私有仓库，再执行：

```powershell
gh auth login
powershell -NoProfile -ExecutionPolicy Bypass -File .\tools\Build-And-Publish-Personal65.ps1 -Publish
```

`-Publish` 会验证仓库仍是 Private，再创建或更新私有 `v0.13.0-private65-rc1` Release。为避免下载错误，它会重新验证并构建两个 ZIP，而不是直接上传未经验证的旧产物。

## 尚未完成的验收

- 65 个来源逐个允许本机使用、原始作者出处与形象相似度人工核对。
- 65 个角色在你的 Windows 真机上真实安装、可播放动作和切换测试；当前 Actions 仅覆盖来源结构/像素与 Qt 离屏等自动测试。
- 原设配音、麦克风/声卡、多屏高 DPI、长时间运行与 CPU/GPU 资源测量。
- Rust 混合版的用户侧性能增益，而不是仅证明原生模块成功载入。

因此，Release 标签应为 **private prerelease RC**，不标为 Stable。

## R10 · Doro 的独立手绘 V2 实际素材（2026-10-27）

**已直接打开和观察真实源图集**：来自
[awesome-codex-pet / doro--godxxy1229](https://github.com/legeling/awesome-codex-pet/tree/db2f6306ce78f6559ab27155d7bfaf00bf43809d/pets/doro--godxxy1229)
的 `spritesheet.webp`，确认为 702,066 字节，完整 SHA-256 为
`a22d84a8836f60c535b7bf418eda5d68ba99ca36338f3816fc8a043b77bf3228`。
原图可辨粉色头发、紫色眼睛、白色四足身体，存在不同的表情和动作姿态，包括键盘与放大镜的互动画面。**这些只是源图直接观察，不表示配音、原设还原、所有帧播放自然性已通过验收。** 它不是从其他角色伪装而来的原设原图；这是一位独立作者的非商业同人改绘，底层 NIKKE 角色权利另计。

R10 保留原 `doro--lingxiaotian` 作为 classic 来源，不覆盖它；新增一个严格白名单的 `handdrawn_v2` 来源。直接安装命令可使用：

```powershell
python -m tools.install_creator_mascots --mascot doro --variant handdrawn_v2 --personal-use --output-root res/role
```

Windows Personal65 便携版中，继续启动 `Make-My-Offline-DyberPet.cmd`，键入 `INSTALL` 后，本机批量角色安装器会为**尚缺此版本**的 Doro 优先使用手绘 V2；经典 Doro 即使已安装，也可以在不同独立文件夹中保留。这项安装发生在用户本机，下载依据固定的两个原图 SHA-256 做校验，不把任何第三方人物原画上传至 GitHub Release。

可在源码中查看：
`python -m tools.personal_source_batch --mascots --doro-v2 --role-root res/role`
（只读规划）或显式加 `--install --accept-personal-use`（本地安装）。

`guga` 沿用原固定 CIRCUS 来源，未在 R10 更换或声称新增视觉验收。只有完成真实图像与多姿态的逐帧检查后，才能评估其外观/互动质量。Doro V2 仍不含原声，且不能因新版本源文件 SHA 匹配而认定官方授权或人工最终审核通过。

## R11 · 直接在角色管理界面安装 Doro 手绘 V2

在 **角色管理 → 咕嘎 / Doro 创作者素材** 中选择 Doro 下载，现会出现两项真实创作者来源：默认 **godxxy1229 手绘 V2**，以及 **legeling 经典版**。选择时会再次展示来源、非商业使用限制与没有原声的说明，需要你明确确认后才会联网。关闭选择框或拒绝确认不会触发下载。**这是原作者同人动画素材，不是官方游戏原画。**

安装期间使用原有异步 `ChibiImportThread`，下载固定提交的 `pet.json` 与 `spritesheet.webp`，逐文件校验长度及 SHA-256，离线提取原生动画，并通过 `CheckCharFiles` 和 `scan_mascot_library` 确认新目录确实绑定到所选 Doro 作者版本；失败不会计入已安装成功，也不会修改用户旧的 Doro 目录。重新打开角色库，可同时预览经典 Doro 与手绘 V2 的真实逐帧动作，并手动选择使用其中一套。

旧版咕嘎仍单独提供，由 CIRCUS 发布的来源未因本变更获得外观认证。R11 没有增加任何新的原神来源，123 模板 / 65 固定来源 / 58 尚缺来源的统计保持不变。后续仍应优先逐人检查原作形象、真实动作和可用的完整角色安装文件。

## R17 · 新角色只能在完整启动加载后切换（2026-10-27）

原有 GUI 把单独导入的新角色立即加入管理列表，并提供“切换”，但正在运行的 `PetData` / `ActData` 并没有重新初始化该角色；批量导入的角色甚至没有立即进入切换列表。直接切换可能使用缺失的运行时动作状态。

R17 将新导入的角色明确标为**需重启激活**：运行期间的切换按钮不再向尚未加载的角色发送 `change_pet`，而是询问是否将其设为“下次启动的默认桌宠”。批量安装结束后，从安装回执与新鲜角色库存进行**同人物、同文件夹、非演示、结构认可**交叉检查，仅将真实可定位的原画版本提供给用户即时逐帧预览，并在用户再次选择后写入下一次启动的默认角色。不会修改当前桌宠，也不假设安装动作等于原设、音色或真机通过验收。

界面也将“先试装 2 位”确认信息上限明确改为 2 位，不再错误显示 65 位。正常退出程序后重新启动即可按默认角色加载；此阶段**不宣称支持热加载**，避免状态与存档混乱。

## R19 · 卡维 Kaveh 原始 Shimeji 动画的可选本机安装

R18 GitHub Actions 已从 [ShimejiShop 卡维来源页](https://shimejishop.com/free/kaveh-shimeji/) 实际下载，并核验了 `ilewdha` 署名候选 ZIP 的 **990,054 字节**、SHA-256 `86b14aff32b1eeec87800c632817a21b22779a654d876d79a854fb14da4669c9` 和 **46 张原始 PNG**。本轮将此来源作为**独立、用户自愿选择的第二套卡维候选素材**，不删除已有卡维 Codex 源、不上传第三方图片。

在 **系统 → 角色管理 → 安装作者原画角色**，选择带有「卡维 ilewdha · 真实 PNG 原画 ZIP」的选项；软件明确显示来源、已知单帧动作、使用许可待确认并要求手动同意。联网后必须校验**全部 ZIP 字节长度和 SHA-256**，否则不会安装。使用项目原生 Shimeji PNG 转换器并保存原始 `source_frames/` 与审计报告，新角色使用独立的 `SourceKavehIlewdha...` 文件夹；安装后请逐帧预览，并正常重启才能激活新动作。

Windows Python/RustHybrid 都使用同一已校验的作者素材安装器。源码入口：
```powershell
python -m tools.install_pinned_kaveh_shimeji kaveh_ilewdha --accept-personal-use --role-root res/role
```

也可以从来源页合法取得原始 ZIP，使用 `--archive <本机ZIP绝对路径>` 在离线环境严格校验后导入。仅获取匹配精确哈希的原件；不执行发行者 ZIP 内 EXE/JAR。不得认为发布网页的署名已经获得了作者本人明确授权。

**质量边界：** 该候选包含约 10 个原生动作定义，但 `crawl`、`fall` 都只有一帧，完整动作质量门禁未通过；真实互动、原设人物长相及使用条款仍须人工复核。**原神人物固定来源覆盖仍为 65/123，缺 58 位。** 这套“卡维备用版本”不被自动晋升为已通过美术验收的正式来源，因此正式来源统计继续保持 88 套；用户个人导入成功只改变自己的本机角色库。

## R20 · 角色“动作可用”由首帧检查升级为完整帧检查

旧版互动库存验证仅解码动作的 `prefix_0.png`；后续编号帧即使丢失、损坏、指向软链接或完全透明，也可能让用户界面错误地认为动作可用。R20 对**每个用于互动的原生动作序列**执行只读、有限额的全帧预检：按原始编号顺序核对完整性及从 0 开始的索引，拒绝被替换/链接的帧，真实解码所有 PNG 的数据流，检查尺寸、总数量和全透明帧。别名动作复用已完成的动作前缀验证结果；不会合成或改写图片。

任何一帧损坏，都不再将该动作算入可用互动类别；同角色其他完整动作仍可使用。为了兼容已有 GUI 及外部报告，保留历史 `first_frames_decodable` / `has_decodable_first_frames` 状态标签，但新增 `complete_png_sequences_checked` 明确标注升级后的结构验收，仍明确 `physical_runtime_playback_verified=false`。

**边界：** 单帧坠落、爬行等结构可解码，但“动作是否真的动起来”仍由独立 R7 像素与真人播放质量审计评估。本次不把静态图片变成真正的动画，不冒充原设、配音或艺术授权验收。实际本机交互仍需试用。

## R22 · 16 位人物的 17 套作者 Shimeji：启用更多原始姿态，不伪造新动画

来自 Poseima/nano-pet 的固定来源为 **17 套原画图包，实际只对应 16 位不同原神人物**，其中温迪有两套来源。原始图包每套约 45/46 张真实 Shimeji 画师 PNG，原先导入只映射其中 9 组动作；还存在一个真实互动故障：旧版「行走」`random_act` 同时引用待机 `default` 和行走帧，严格 PetWidget 语义映射会拒绝这个混合组。

本轮 R22 从这些**已有作者原画**额外提供五项精确命名的可预览姿态组：`lookaround`（Shimeji 26、15、27、16、28、17、29 原始转头七帧）、`ceiling_crawl`（23–25）、`edge_sit`（30–33）、`window_carry`（34–36）和 `jump_pose`（22 单张跳起造型）。`jump_pose` 仅作原画姿态预览，**不登记为已实现的跳跃互动**。`shime38–46` 是分身/复制动作，严禁冒充摸头动作。

本轮还将真实 `random_act` 菜单中的「散步」绑定仅有 `left_walk/right_walk`，增加「休息」绑定 `rest`，在完整七张转头原画存在时增加「观察」绑定 `lookaround`。这三项与当前 PetWidget 真实随机动作组调用契约相符，并不绕过用户解锁状态。空的旅行者 Aether 图包缺少 `shime29`，因而会**仅跳过七帧转头观察**，其他完整来源仍正常安装，不自动补绘第七帧。安装回执写明哪些可选动作被跳过。

标准 Shimeji 编号动作语义可对照 [Shimeji Sprite Reference](https://github.com/shimeji-ai/Shimeji-AI-Pets/blob/main/animation-reference/SPRITE-REFERENCE.md)。真实图包 SHA/Git blob 已固定；CI 单独尝试实际下载钟离与空的原画，生成本机临时角色与逐动作质量记录，不上传任何第三方 PNG。不能因为图包有真实 46 帧就判断它完全贴合原作人物、动作自然、配音准确或具有分发权。

**覆盖仍为 65/123**。R22 增强已覆盖人物的真实交互，而不是虚报新增 17 位。

### R22 独立原画在线核验和已安装角色升级

隔离的 [NanoPet 两位原画验收](https://github.com/clonetimer/DyberPet/actions/runs/40515166028) 下载并逐帧核对固定版本：钟离为 46 张原始 PNG、15 项原生动作，七帧 `lookaround`、三帧 `ceiling_crawl`、四帧 `edge_sit`、三帧 `window_carry` 各帧姿态均不同；空（旅行者）为 45 张原始 PNG、14 项原生动作，`shime29` 缺失，因此不提供七帧观察互动，但真实散步和休息仍通过原生菜单语义检查。两者的 `jump_pose` 都是一张原画静态姿态，不宣称为连续跳跃。

**已安装旧版也可以升级：** 在桌宠角色管理界面再次手动选择 NanoPet 原作者来源（提示确认），R22 会为同一人物、同一原作者的新版动作配置安全创建**另一独立角色目录**；原有角色目录、状态和图片完全保留。新目录仍使用精确 Git Blob 校验和全部原画帧，升级后手动预览并重启启用。如果是从 Python CLI 执行，则需要明确附加 `--as-new-version`，否则仍拒绝覆盖：

```powershell
python -m tools.install_nanopet_shimeji zhongli-by-vol-tuna --accept-personal-use --as-new-version --role-root res/role
```

这是同一作者原画的**动画映射改进**，不是新画师素材、角色新增或对真实桌面稳定性的自动认证。

## R23 · 优菈 SaylaMars 110-frame Shimeji 原作者资源正式固定（2026-10-27）

画师 SaylaMars 的 [Eula FANBOX 原帖](https://saylamars.fanbox.cc/posts/8264436) 的公开附件已实际下载验证：8,400,168 字节、SHA-256 `f4952ea151e0ead70b501e9e2637f9dae1194e0da1b5d312046964fc19046803`。ZIP 内有 110 张 PNG，109 张对应 `shime1…110` 的不同编号，第一组标准原画全部存在。R23 的**严格来源专用扩展导入器**保留 109 张编号原画字节不变，完整 PNG 解码，但只从已知 Shimeji 原画序列映射 15 个原生动作，其余编号 47…110 保留用于人工审查，不臆测自定义 XML 中的动作语义，也不执行 EXE/JAR。

真实隔离 CI 证实左/右行走、拖拽、攀爬、着地拥有多张不同姿态原画；匍匐和下落仅单帧，仍标记为动作弱项。源文件完整性验收 **不等于** 角色原设形象、美术权益、自然运动、语音或 Windows 实机验收。

首次安装可在桌宠的 **角色管理 → 真实作者素材 → 优菈 SaylaMars** 主动选择，并确认从画师发布页获取的许可条件。CLI 命令：

```powershell
python -m tools.install_pinned_eula_shimeji eula_saylamars_original --accept-personal-use --role-root res/role
```

如已直接从画师获取完全相同的原始 ZIP，附加 `--archive "C:\\Users\\YourUser\\Downloads\\Eula-original.zip"` 可以不联网安装。任何 ZIP 不匹配原始大小或 SHA 都被拒绝，旧角色不会被覆盖。只安装到用户本地角色目录；第三方原画不会进入 GitHub 源码仓库或公开 Windows 包。

**真实来源登记从 65/123 变为 66/123，仍缺 57 位人物来源。** 这仍不是 66 人均已本机安装或通过视觉验收。当前优菈还需要手工比对原设（头发、发饰、服装、表情）和连续动作体验。

## R23-RC：正式 Python / RustHybrid 打包门禁修复

PR #56 之后原画来源覆盖实际变成 **66/123**（尚缺 57）。此前 `build_personal65_windows.ps1` 仍硬要求 `ready_for_opt_in == 65` 与 `missing_source == 58`，造成两种 Windows EXE 都已成功编译，但在冻结包验收阶段被旧断言拦截，没能上传 ZIP。现改为从冻结后的可执行安装助手实际源清单读取覆盖数字，校验合计必须是 123 且不得退回到少于 66 个固定来源。元数据中的人数亦取源清单真实数值，而非历史写死的 65/58。

新包同时提供 `Install-Available-Roles.cmd`（自动从当次清单识别可安装上限），旧的 `Install-65-Roles.cmd` 作为兼容入口仍可运行。为避免用户自行生成离线包时把 65/66 错认成全覆盖，本机 `LOCAL_OFFLINE_BUILD.json` 中新增 `genshin_current_pinned_source_target` 和 `genshin_all_pinned_sources_target_reached`；历史 `genshin_65_source_target_reached` 字段仅为旧版兼容。此改动并未预装第三方原画、声音或完成原设美术/许可验收。
