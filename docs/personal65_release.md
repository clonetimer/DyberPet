# DyberPet Personal65 私有预览版（Windows x64，Python 与 Rust）

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
