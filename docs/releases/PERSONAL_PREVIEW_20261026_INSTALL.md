# DyberPet 个人预览版：从下载到运行

**版本**：v0.12.0-personal-preview.1 · **源码**：cfa7c52e64d3fbcc0ceb5bb4ac972dea03aa2d48

这是**可直接解压运行的个人预览版**，不是点击“下一步”的系统安装器，也不是 Stable。无须先安装 Python、Rust 或 Node。

## Windows x64

1. 先备份以前的个人存档、角色包，不要直接覆盖旧软件目录。
2. 下载 `DyberPet-Windows-Personal-PR5.zip`，右键「全部解压缩」至自己有写入权限的新位置，例如 `D:\\Apps\\DyberPet-Preview`。
3. 进入完整解压后的文件夹，运行 `DyberPet.exe`。不要把 EXE 单独移走，相关 `_internal`、`res` 等文件需要留在旁边。
4. 先用自带 Kitty 测试桌宠功能。可右键桌宠进入系统菜单、角色管理和桌宠助手。需要桌面快捷方式，可右键 EXE 发送到桌面快捷方式。

## Linux x86_64（Ubuntu 24.04/X11 自动化验收环境）

```bash
mkdir -p "$HOME/Applications/dyberpet-preview"
tar -xzf DyberPet-Linux-Personal-x86_64.tar.gz -C "$HOME/Applications/dyberpet-preview"
cd "$HOME/Applications/dyberpet-preview"
chmod +x DyberPetDesktop/DyberPetDesktop
./DyberPetDesktop/DyberPetDesktop
```

需要 X11 图形桌面及依赖的 Qt/XCB 系统共享库。若程序报告缺库，可按发行版补齐 `libxcb-cursor0`、`libxkbcommon-x11-0`、`libgl1`、`libegl1`、`libespeak1` 等；尚未宣称支持所有 Wayland 发行版。

## 安装自己的角色原画

1. 「系统 → 角色管理 → 全部角色库」可搜索 123 项原神角色配置。
2. 需要在有固定来源的人物条目中由用户**主动选择**来源、明确确认后安装原画，或导入合法取得的本地原生角色 ZIP；发布包不包含 65 位第三方原画。
3. 安装完后用「预览本机原画逐帧动作」在多个来源版本之间切换，检查逐帧动作。可人工勾选原设对照和动作检查，进行 A/B/C 外观自评并导出 JSON。
4. 助手只播放当前角色真实载入且已解锁的动作。收藏、TTS 的动作许可同样随素材与亲密度同步更新。

## 可选助手

LM Studio 本地对话需要用户自行启动服务。离线 TTS、按键触发的麦克风录入、PPL 人设和受控个人文件操作依需求启用；**不需要**为了使用基础桌宠部署大模型。

## 文件完整性与注意事项

下载 Release 附带的 `SHA256SUMS.txt`。Windows PowerShell 使用 `Get-FileHash .\\DyberPet-Windows-Personal-PR5.zip -Algorithm SHA256`；Linux 使用 `sha256sum -c SHA256SUMS.txt`（所有待核验文件位于同一目录）。

不要上传他人原画、角色原声、个人存档、私密配置或聊天记录到公开仓库 Issue。来源完整性通过不代表角色原设外观、配音或权利通过；**荒泷一斗动作候选**仍待修复。