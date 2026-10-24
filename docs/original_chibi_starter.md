# 一键生成可运行的原创 Q 版角色：星芽

本功能为尚未取得第三方游戏角色美术或动作授权的用户提供真正可运行的演示角色，**不只是配置模板**。素材全部由 `tools/create_original_mascot.py` 使用 Pillow 在本地数学绘制；不会访问网络、下载游戏文件、生成或克隆第三方语音。

## 图形界面：零代码使用

1. 进入 **系统 → 角色管理 → 添加角色**。
2. 在类型选项中选 **生成原创 Q 版示例角色（不需下载素材）**。
3. 查看说明并确认。本地后台线程会绘制星芽的动作帧、角色配置、头像、气泡文字及动作预览，不会覆盖已有同名角色。
4. 生成完成后可以打开 `ANIMATION_PREVIEW.png` 检查所有动作。可以切换到新角色，在真实 Windows 桌面观察动画和菜单；导入成功本身不等于真实桌面 QA 通过。

生成内容包括待机 8 帧、左走 6 帧、右走 6 帧、挥手 8 帧、跳跃 6 帧、休息 6 帧、阅读 6 帧，**共 46 张** 192×208 RGBA 原创动作图；另有 `pet_conf.json`、`act_conf.json`、头像、封面、气泡和 `ORIGINAL_GENERATION.json`。这是独立绘制的原创萌芽形象，不是原神角色、Doro、咕嘎或其他已有商业角色。

## 不用 Python：直接下载原创角色 ZIP

在此 PR 的 [GitHub Actions 角色流水线](https://github.com/clonetimer/DyberPet/actions/workflows/character-mod-importer.yml) 中，`downloadable-original-role` 会在四种系统/Python 单元测试及 Windows Qt 实际角色加载测试成功后，自动生成并验证 `StarSprout-Original-Role.zip`，然后上传 `StarSprout-Original-Role` 工件（保存 14 天）。

下载该工件后先解压一次，取出里面的 `StarSprout-Original-Role.zip`，**不要二次解压这个角色包**。打开已有 DyberPet 程序，选择 **系统 → 角色管理 → 添加角色 → 选择原生角色 ZIP 压缩包**，导入内层 ZIP。它使用与其他安全角色 ZIP 相同的本地校验和安装逻辑；若已有同名角色会自动分配新目录，不覆盖以前的角色。

GitHub Actions 只提供通过结构与离屏 Qt 检查的原创动画 ZIP，不表示已经测试你的实体屏幕、声音设备或连续运行表现。

## 命令行（可选）

开发者可在仓库根目录运行：

```powershell
python -m pip install Pillow
python tools/create_original_mascot.py --output-root data/original_chibi_demo
```

如确实希望角色安装在现有 DyberPet 下：

```powershell
python tools/create_original_mascot.py --output-root res/role
```

默认名字 `StarSprout`；已有同名时自动生成 `StarSprout_2` 等未占用名字。手动指定 `--folder StarSproutTest` 必须是安全 ASCII 名称且不允许覆盖已有目录。建议非程序员使用图形界面。

## 自动验收与边界

- `tests/test_original_mascot.py` 验证逐动作所有 PNG 可解码、实际像素有变化、角色配置可用、头像/动作预览齐全、安全目录命名以及重复导入不覆盖既有文件。
- Windows Qt loader smoke 调用 **真实** `QPixmap` 与 `DyberPet.conf.PetConfig.init_config`，不是模拟加载器。
- 素材只会写入本机指定目录，不会自动传到 GitHub；生成报告不会虚构版权授权或人工验收。
- 自动通过不证明真实桌面 DPI、多屏、音频同步和动画节奏均已人工确认。任何第三方角色包仍由独立的素材授权审查流程管理。

此角色用于验证完整安装流水线和满足无素材用户的基础体验。原神 30 个模板目前仍需用户提供合法取得的对应素材，不能把这一原创角色重新命名并宣称属于某个游戏 IP。
