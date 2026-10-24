# DyberPet Linux x86_64 本地验收（候选版）

验收对象：基于 PR #5 的个人自用角色管理 + Q 版导入 + 助理集成候选，目标是 **Ubuntu 24.04 x86_64 / X11**。本轮不以纯 Python unittest 或 Windows CI 替代 Linux GUI 验收。

## 阶段与合格判据

1. **L0 资源/依赖**：Python 3.11 与 Pillow/PySide6/Fluent Widgets，系统提供 X11/XCB、Xvfb；源码和冻结可执行文件都能找到 `res/language`、`res/role/sys`、`res/items`。资源定位不能依赖从仓库根目录双击。
2. **L1 真实 Linux Qt**：Ubuntu 中用 Xvfb 建立 **X11/XCB** 显示服务器，调用实际 `QPixmap`/`PetConfig`，打开真实的角色管理 QWidget 和“原神角色库”选择对话框。这里不是 Qt 的 `offscreen` 平台模拟。
3. **L2 本地角色**：使用原创合成图测试个人导入、123 模板、已安装/待导入盘点、配置 SHA-256 绑定和撤销不改原始角色。原创星芽必须为 7 类动作/46 帧。
4. **L3 可执行程序**：Linux PyInstaller **onedir** 生成的二进制，从无关工作目录在 Xvfb 内分别启动 `--assistant-smoke` 和 `--linux-ui-smoke`；检查结构化报告后才上传 `DyberPet-Linux-Personal-x86_64.tar.gz`。
5. **L4 保留项**：真实 Ubuntu GNOME/KDE 的系统托盘、真实物理屏幕/多屏和 Wayland 会话、中文配音清晰度、麦克风、原神角色原画一致性、长期运行与掉电恢复需人工验收。Xvfb/X11 自动化通过 **不表示 L4 通过**。

**Linux 命名规范**：原始 Python 包叫 `DyberPet`，Linux ELF 启动器命名为 `DyberPetDesktop`（避免 PyInstaller Linux 启动时把同名 ELF 误当成 Python 包目录）；产品名称保持 DyberPet。

## 从 GitHub Actions 工件安装

在 PR #6 的 `Linux X11 acceptance and portable candidate` 工作流中，只有 `linux-frozen-x11-real-executable` 绿色且 `DyberPet-Linux-Personal-x86_64` 工件存在时，才可认为 L0-L3 通过。

1. 下载工件，得到内层 `DyberPet-Linux-Personal-x86_64.tar.gz`（有些 GitHub Actions 下载会再包一层 ZIP）。
2. 在个人可写目录（如 `~/Applications`）中运行：
   ```bash
   mkdir -p ~/Applications
   tar -xzf DyberPet-Linux-Personal-x86_64.tar.gz -C ~/Applications
   cd ~/Applications/DyberPetDesktop
   ./DyberPetDesktop
   ```
3. 首次运行建议 Ubuntu X11 会话（不是 Wayland 原生支持保证），桌宠角色图片和配置会留在可写的 `res/role`，个人角色关联映射留在 `data/genshin_role_bindings.json`。Linux 用户配置和存档由旧软件写到 `~/.config/DyberPet/data`，因此应单独备份这两处。
4. 缺少 X11/XCB 库时可安装 Ubuntu 系统包：`sudo apt install libxcb-cursor0 libxcb-xinerama0 libxkbcommon-x11-0 libgl1`。这只针对 Ubuntu 24.04，其他 Linux 发行版兼容性**尚未确认**。

## 本地执行验收（开发者）

```bash
python -m pip install -r requirements-linux-portable.txt
xvfb-run -a env QT_QPA_PLATFORM=xcb python run_DyberPet.py --linux-ui-smoke
xvfb-run -a env QT_QPA_PLATFORM=xcb python run_DyberPet.py --assistant-smoke
bash tools/build_linux_portable.sh
xvfb-run -a env QT_QPA_PLATFORM=xcb ./dist/DyberPetDesktop/DyberPetDesktop --assistant-smoke
xvfb-run -a env QT_QPA_PLATFORM=xcb ./dist/DyberPetDesktop/DyberPetDesktop --linux-ui-smoke
```

执行时请通过 `HOME` 指向一个独立测试目录，不要拿个人已有数据直接执行验收。工作流在 GitHub 托管 Ubuntu 环境使用 Xvfb 做这件事。合成素材并不模拟游戏版权角色，工具绝不会从网上自动抓取角色模型或音频。

**验收结论必须结合实际运行结果记录**。未通过的检查不得跳过；不要因为生成了压缩包就把它标为 Linux Stable。
