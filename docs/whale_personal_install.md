# DyberPet · 鲸鱼娘 Whale Pet 原始动画本机安装说明（R25）

来源：[luweiyabo/dsh-whale-pet](https://github.com/luweiyabo/dsh-whale-pet)，锁定提交
`b61b445e6be05a732fc6738b825240aeffdf6769`。

## 许可与范围

- 上游原创代码采用 MIT；`assets/thumb/` 中大量 WebM 美术资源来自 PC2005-cloud/dsh-pet，另受允许开源项目使用但禁止商业用途的规则约束。具体以 [上游资产声明](https://github.com/luweiyabo/dsh-whale-pet/blob/main/THIRD_PARTY_ASSETS.md) 为准。
- DyberPet 本次只登记 95 个原始上游动画文件的路径、长度、Git Blob 哈希和代码转换逻辑。**公开仓库、CI 产物、发布 ZIP 均不含第三方动画和原声**。只有用户在自己的设备上明确同意后才会下载。
- 这是一位**独立新增的非原神角色**，不计入 123 个原神模板 / 66 个已有来源人物。此处的“95”是动画片段数量，**不是 95 个新角色**。
- 实际通过的视频解码与原生帧结构验收并不等于原设外观美术、自然动作、配音/原声、真实 Windows 桌面体验已完成验收，也不授予商业转用或再分发许可。
- 原项目用于 DeepSeek Harness Web UI 的 Agent 活动感知与 Web 屏幕漫游没有在本次移植中实现。这里只复用了作者的真实动作素材和 DyberPet 已有的交互机制。

## R26 中文名称与精简安装包

- 所有已知角色在界面中优先显示**中文角色名称**，本角色正式显示名为 **鲸鱼娘**。原有文件夹 ID（例如 `SourceWhalePet`）保持不变，避免破坏旧存档和角色切换。
- Windows 便携包不再重复内置约 83 MiB 的 FFmpeg 解码程序。只有当用户明确选择安装鲸鱼娘时，程序才会从 **PyPI imageio-ffmpeg 0.6.0 的官方 Windows x64 wheel** 获取解码器，校验固定 wheel SHA-256 和单独二进制 SHA-256，并缓存到本机 `data/tools/whale_ffmpeg/`；以后重新安装可复用已校验的缓存。
- 解码器为正常 Whale WebM-to-PNG 转码所需。首次联网安装会额外下载约 31 MB 的官方 wheel；断网使用鲸鱼娘既有角色不受影响，首次断网安装须提供本机 FFmpeg 可执行文件。
- 该精简策略只影响首次安装，不删除已安装角色、语音功能、模型、Qt 或其他桌宠行为；GitHub 公共安装包仍不分发第三方原画。

## Windows 一键安装（Python 和 RustHybrid 通用）

1. 解压包含 R25 变更的 **新 Windows 候选构建包**，不要覆盖旧桌宠目录。
2. 在桌宠 **系统 → 角色管理 → 添加角色**，选择“个人非商用：安装鲸鱼娘 Whale Pet（原始 WebM 动作）”。亦可直接双击新包根目录的 `Install-Whale-Pet.cmd`。
3. 建议先选核心 16 项原画动作（8 FPS）；需要完整作者原画库时可选 95 项（5 FPS、转换时间和磁盘占用明显增加）。确认素材的非商业使用条款后输入 `INSTALL`（仅命令行入口需要）。
4. 安装器依次下载固定版本的视频，核对**原视频文件长度及 Git Blob 哈希**，使用随安装包提供的 FFmpeg 解码成 RGBA PNG 帧，再生成 DyberPet `pet_conf.json` / `act_conf.json`。原画、转换结果及本机使用回执只在本机角色目录保留，不写入 GitHub。
5. 完成后于角色管理确认鲸鱼娘可见，使用原生逐帧预览，正常退出并重启 DyberPet 后选择角色。新导入角色不能直接热切换。
6. 如果下载失败或媒体透明度/安全校验不通过，安装不会覆盖既有角色；排查本机网络与 FFmpeg，不得绕过哈希/透明度校验。

## 开发者 CLI

在有 Python 3.11 / Pillow / `imageio-ffmpeg` 的源码目录：

```powershell
python -m tools.install_whale_pet --output-root res/role --selection core --accept-noncommercial-source-terms
# 全量动画（95 个视频，5 FPS，下限为仍可辨动作，但低于源片帧率）:
python -m tools.install_whale_pet --output-root res/role --selection full --accept-noncommercial-source-terms
```

源码 `tools/whale_creator_sources.json` 记录 95 个固定素材的 Git 对象身份。导入器不会执行上游插件 JavaScript、下载安装包或额外工具指令；只下载白名单内已锁定的视频媒体。

## 已知局限

- 原 WebM 是 640×360 透明画布；DyberPet 适配器等比例缩放到 320×180。保持动作原有画面比例与透明通道，但暂未做按人物像素精确裁剪与点击命中框收缩。
- 核心版 8 FPS / 完整版 5 FPS 是为降低本机原生 PNG 帧数量做的抽帧，不等价于原视频完整播放帧率；更流畅的原视频直接播放需后续原生播放器专项评估。
- 浏览器原项目的事件驱动触发、Web 版拖拽和窗口漫游不能简单等价于 DyberPet 的桌面动作。已适配原画待机、移动外观、拖拽时原始素材、坠落造型及其余菜单动作；需在真机验证。
- RustHybrid 仍是 PySide6 UI + Rust 加速，不是原生纯 Rust WebM 视频桌宠。

