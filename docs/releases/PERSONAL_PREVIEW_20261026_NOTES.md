# DyberPet Personal Preview · 2026-10-26

**可运行的 Windows/Linux 个人预览版（Pre-release；不是 Stable）**。
源码固定为已完成全部五组 GitHub Actions 验收的 [cfa7c52](https://github.com/clonetimer/DyberPet/commit/cfa7c52e64d3fbcc0ceb5bb4ac972dea03aa2d48)，不合并仍为 Draft 的 PR #25 和 #28，也不改变 main。

## 直接下载使用

- **Windows x64**：`DyberPet-Windows-Personal-PR5.zip`，解压**整个文件夹**，运行 `DyberPet.exe`。这是免安装便携软件，**不是** MSI、Setup.exe。
- **Linux x86_64**：`DyberPet-Linux-Personal-x86_64.tar.gz`，适用于 Ubuntu 24.04/X11 已验收环境，解压后运行 `./DyberPetDesktop/DyberPetDesktop`。
- `INSTALL.zh-CN.md` 说明具体步骤及限制；`SHA256SUMS.txt` 提供独立验证校验值。

## 当前可用范围

内置基础 Kitty 可独立运行；桌宠互动与日常管理、角色导入、搜索、**真实原画逐帧查看**、逐角色 A/B/C 用户自评、手动互动和收藏、FV 动作解锁检查、可选 LM Studio / PPL Persona / 文件操作和离线语音均有相应入口。程序不会默认启动语音录制或远程模型。

**123 是原神角色配置模板，不是已安装的 123 套原设角色**。已固定验证 88 个第三方来源版本覆盖 65/123 位角色，58 位仍缺固定来源；用户需要主动确认/安装个人使用的原画。因公开发布许可尚未获独立确认，原神、咕嘎及 Doro 的第三方原画/原声**未打包**。125 套低保真自动生成占位动画已从最终用户包剔除，防止冒充角色原画。

## 不支持宣称为 Stable 的原因

- Windows 真实实体设备上的 DPI、多屏、麦克风、声卡、长期运行尚未完成用户验收；Linux 只经自动化 X11 验收。
- 荒泷一斗来源的独立动作质量探针仍未通过 crawl/fall 静态姿态检查，未作为已完成来源。
- 角色外观 A/B/C 是用户自评，不代表官方原设符合性、作者授权、原声或实际桌面可用性认证。
- 下载新版前请先备份个人存档和素材，解压到**新目录**，避免覆盖旧版。

五组 CI：[桌宠助手](https://github.com/clonetimer/DyberPet/actions/runs/40280075769)、[角色导入](https://github.com/clonetimer/DyberPet/actions/runs/40280076114)、[Windows 程序包](https://github.com/clonetimer/DyberPet/actions/runs/40280075734)、[Linux X11 冻结包](https://github.com/clonetimer/DyberPet/actions/runs/40280075745)、[咕嘎/Doro 来源](https://github.com/clonetimer/DyberPet/actions/runs/40280075812)。