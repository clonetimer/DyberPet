# DyberPet 新角色：咕嘎与 Doro（本地图集转换）

本工具为 DyberPet 增加一种**无需修改 GUI 或动画引擎**的角色 MOD 制作方式：将用户自行取得、有权使用的 Codex Pets 精灵图转换为 DyberPet 原生角色。

## 素材来源和授权边界

- **Doro**：可参考 [awesome-codex-pet 角色目录](https://github.com/legeling/awesome-codex-pet/blob/main/pets.json) 中的 doro--lingxiaotian。该素材条目标注 CC BY-NC 4.0，**仅限非商业用途且须署名**。这是同人作品的素材许可，不代替《胜利女神：妮姬》相关原始 IP 许可。也可选择其他明确授权的 Doro 图集，并手动填写实际作者/许可。
- **咕嘎**：可参考 [Codex Pets 社区图集](https://download.yudidc.cc/pets/) 中的 guga，或 [咕咕嘎嘎 DyberPet 桌宠作者的视频](https://www.bilibili.com/video/BV16wXEBEEo9/)。目前查到的 guga--circus 条目**没有明确的再分发授权**。公开提供下载并不等同于允许将素材纳入另一个公开发行的软件。发布角色包前应联系具体画师确认授权。
- 不批量抓取表情包、商品图片、视频截图等冒充有授权的角色动作素材。
- 该脚本仅处理使用者自己放到电脑上的图集；仓库**不内置或自动下载第三方美术文件**。

## Windows 操作步骤

**推荐方式（无需命令行）**：将原始 Codex Pets 图集解压成文件夹（其中有 pet.json 和 spritesheet.webp），打开 DyberPet 软件的 **系统 → 角色管理 → 添加角色**，选择该文件夹。程序自动识别图集并转换、生成角色头像与信息卡，不增加或改动原界面控件。导入结束后建议重启，再切换新角色。

该入口仅在用户选择有效的 Codex Pets 角色文件夹时运行转换器；普通 DyberPet 角色文件夹仍走原有导入逻辑。图集转换依赖 Pillow，缺少时会提示安装。

**命令行备选方式**：在仓库根目录打开 PowerShell，安装图像处理依赖：

    py -m pip install Pillow

下载角色对应的 Codex Pets 图集，将每个角色分别放在一个文件夹，例如 D:\Downloads\guga 和 D:\Downloads\doro。每个文件夹包含 pet.json 和 spritesheet.webp；也支持直接选择单个 WebP/PNG 图集。

分别执行：

    py tools/import_codex_pet.py "D:\Downloads\guga" --preset guga --source-url "实际素材出处"
    py tools/import_codex_pet.py "D:\Downloads\doro" --preset doro --source-url "实际素材出处"

如果使用并非上面指定的画师/素材版本，请**覆盖默认署名信息**：

    py tools/import_codex_pet.py "D:\Downloads\spritesheet.webp" --preset doro --folder DoroV2 --author "实际原作者" --license "实际许可" --source-url "实际网址"

生成位置：res/role/Guga 或 res/role/Doro。角色目录将包含：

    Guga/
      act_conf.json
      pet_conf.json
      ASSET_SOURCE.txt
      info/info.json
      info/pfp.png
      info/cover.png
      IMPORT_REPORT.json
      action/idle_0.png
      action/left_walk_0.png
      ...

重启 DyberPet，打开 **系统 → 角色管理**，选择新增的角色。

如遇到同名目录，脚本会直接拒绝覆盖，避免修改已有角色或影响存档。请使用不同的 --folder 参数，或自行备份并管理旧 MOD。

## 动作映射

| Codex 动作 | DyberPet 映射 | 表现 |
| --- | --- | --- |
| idle | default | 正常待机 |
| running-right / running-left | right / left | 左右位移 |
| waving | patpat | 拍拍、挥手 |
| jumping | drag / fall | 拖拽和松手时的代用动画 |
| waiting | 随机休息 | 待机时随机触发 |
| failed | 动作资源 | 预留失败表情动作 |
| running | 动作资源 | 跑步动画，可后续定制 |
| review | focus | 专注状态 |
| V2 第 9–10 行 | 左顾右盼 | 16 方向环视 |

图集尺寸：V1 为 1536×1872，V2 为 1536×2288，每格 192×208。转换时保留透明通道和统一帧画布，默认角色显示比例为 0.65。缺少可选动作会回退到 idle；idle 缺失将报错。

**动作限制**：Codex Pets 的原始图集不一定包含真实落地、睡觉或吃东西的连续帧，因此目前只是将现有九种动画映射成可交互的基础角色，不能声称与专门制作的完整 DyberPet 角色模组等价。后续可通过专门绘制的帧扩充相关动作。

## 素材质量检查

转换器会生成 IMPORT_REPORT.json，记录所有帧数量、成功映射动作以及质量警告（例如某动作中间存在空白帧、V2 环视帧不完整）。同时自动从待机帧生成角色头像 pfp.png 和角色信息卡封面 cover.png。没有有效待机帧时拒绝导入。

若某个动作没有任何有效帧，随机动作池会直接省略该动作，而不会在菜单里出现徒有其名的动作。部分互动（例如拖拽和落地）仍会使用其他动作回退。

**注意**：V2 的 16 向环视帧当前用于随机“左顾右盼”动作，并不等同于实时追踪鼠标指针。

## 验证

    py -m unittest discover -s tests -p "test_import_codex_pet.py" -v
    py run_DyberPet.py

确认：透明背景、左右位移、拍拍响应、拖拽、松手、角色切换、缩放、角色信息卡，以及其他角色不受影响。

单元测试验证的是**精灵图裁切和角色配置**。实际 PySide6/Windows UI 的运行验收需要本地桌面环境；不要把单元测试通过等同于视觉验收通过。

## 发布要求

导入的美术作品保留独立授权；不会因为仓库代码使用 GPL-3.0 就自动变成 GPL 素材。默认不要把生成的 PNG 直接提交公共仓库。只有明确具备再分发权时才考虑独立角色包或 Release，并同时保留 ASSET_SOURCE.txt 的作者、许可、来源信息。
