# DyberPet Personal65 私有预览版（Windows x64，Python 与 Rust）

## 版本定位

此候选基线来自 `release/personal65-python-rust-20261026`，其最新角色功能建立在 PR #28 的 65 个固定来源候选和 PR #29 的个人本地批量安装器上。

- **Python**：完整 PySide6/Python 桌宠，无 Rust 依赖。
- **RustHybrid**：桌宠 UI、语音、文件操作仍由 Python/PySide6 负责；Rust 仅以 PyO3 加速校验和资源索引。启动脚本设置 `DYBERPET_NATIVE_BACKEND=rust`，打包的真实 EXE smoke 必须报告 `native_backend.active=rust`。
- 两个压缩包是便携版，解压**整个目录**；不是单文件程序，不是纯 Rust 重写，也不是传统 Setup.exe 安装包。
- 65 指 **123 个原神模板中已有固定素材来源的 65 个角色**，并非已经完成 65 个原画包预装、原声或人工美术验收。另有 58 个角色尚无固定来源。
- 第三方图片、语音不会进入 GitHub Release。仓库 Private 不自动许可复制或再分发他人素材。

## 如果 Releases 已生成

从私有仓库 `Releases → v0.13.0-private65-rc1` 下载以下二者之一，并核对 `SHA256SUMS.txt`：

- `DyberPet-Personal65-Windows-Python.zip`
- `DyberPet-Personal65-Windows-RustHybrid.zip`

解压到新的空目录，避免覆盖旧版本和个人资料。双击 **`Run-DyberPet.cmd`** 启动。RustHybrid 如果原生模块丢失，程序会拒绝假装成 Rust 成功运行。

角色导入步骤：

1. 备份旧版 `data/`、`res/role/` 和个人配置。第三方素材从来不会随应用自动移入新的文件夹。
2. 双击 **`Install-65-Roles.cmd`**。程序先生成 `data/personal65-plan.json`，列出已安装、可获取、需手动导入和缺来源的人物。
3. 阅读该角色来源的使用条件；符合个人使用范围时输入 `INSTALL`，才会下载并校验选定的固定来源素材。原始内容的 SHA256/大小、人物识别 ID、动作帧会依现有安装器逐项检查。
4. 完成后查看 `data/personal65-install-report.json`：`installed_unreviewed` 是“本机安装且结构验证”的数量，不等于原设形象、声线、动作或 Windows 真机通过验收。
5. 打开桌宠 `系统 → 角色管理 → 全部角色库`，切换 **“已安装真实来源素材”**，逐个检查角色形象、头饰、衣装、动作帧和实际桌面行为。

如果某项来源失败，请保留报告；安装器不会覆盖已有真实角色。界面可手动导入现有 ZIP 等个人文件。不允许将本机原画文件加入下一次 Release。

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
