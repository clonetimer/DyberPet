# DyberPet 角色新增流水线（P4）

适用：原创 Q版、原神、无限机兵，以及通过模之屋/B站等正规渠道取得的合法素材。本流程面向维护者；普通用户继续用软件中的“系统 → 角色管理 → 添加角色”。

## 设计与权利边界

**发现资源 ≠ 有权下载 ≠ 有权改编 ≠ 有权再分发。** 模之屋存在公开配布、联系作者、仅展示等状态，且须遵守各作者使用规约。B站配布作者常常要求阅读 README 或附加限制，例如不允许二次配布、商业用途，甚至软件用途限制。所有素材须记录具体作品 URL、作者、版本、许可截图或原始文字依据与核查人。仅有模之屋首页或B站视频不能作为许可证明。

**3D资源不等于 DyberPet 2D动作。** PMX、PMD、VRM、Blend、FBX 是建模/渲染输入，必须使用经许可的模型及动作在本地 MMD/Blender 等软件中渲染透明背景动作序列，之后才运行 PNG/GIF 转换。当前流水线只生成渲染任务说明，不假装自动完成骨骼动作或 3D 视觉设计。

**素材不入仓库。** 本地流水线工作区 data/character_pipeline 已被 .gitignore 排除，不主动下载或重新分发第三方图像、3D模型与音频。

## 流水线

1. 发现：从来源清单寻找具体作者的作品，记录链接与角色类型。
2. 建档：新建候选 ID、人物、作品渠道和需要的动画/模型格式。
3. 本地采集：用户自己取得素材，记录源路径和 SHA-256 哈希。
4. 权限审查：人工记录具体授权文本/证据、审核人、本地使用许可、改编许可、再分发许可三项独立结论。
5. 内容准备：2D动画直接构建；PMX/VRM先生成渲染计划，待离线生成透明PNG/GIF后重新建档。
6. 构建：转换成 DyberPet 原生主角色；做动作及目录完整性校验，生成 ANIMATION_PREVIEW.png、IMPORT_REPORT.json 和 PIPELINE_SOURCE.json。
7. 人工验收：Windows真实桌宠检查帧动画、站立与走路、贴地/悬浮、拖拽、缩放、交互、角色切换；必须记录人工审核人。
8. 可选打包：只有证据明确允许改编和再分发且人工视觉/运行验收通过，才可创建独立本地 ZIP。**不会自动上传 GitHub Release**。

## 已建立的来源池

| 优先级 | 渠道 | 适合获取 | 常见限制 |
|---|---|---|---|
| 1 | DyberPet 自有[角色合集](collection.md) | 原生主角色MOD、迷你宠物 | 需区分res/role和res/pet；不要混装 |
| 2 | [Codex Pets](https://codex-pet.org/zh/pets/) | V1/V2透明图集 | 需要检查具体素材作者与版权 |
| 3 | [模之屋](https://www.aplaybox.com/model) | PMX/VRM/Blender及动作 | 模型作者与动作作者规则分别审查，可能仅用于MMD |
| 4 | [哔哩哔哩](https://www.bilibili.com) | 作者配布视频、GIF/PNG、模型、教程 | 视频公开 ≠ 素材包可随意重发 |
| 5 | [VRoid Hub](https://hub.vroid.com) | VRM模型 | 核查逐项个人/改编/再分发条款 |

来源库还收录了 DyberPet 原角色合集可追溯的 B站创作者主页：[栎咕咕](https://space.bilibili.com/14004864)（纳西妲、派蒙迷你宠物等）、[吾道咕咕](https://space.bilibili.com/393688614)（流萤、守岸人等）、[代号皮克嗖儿](https://space.bilibili.com/9959876)（像素猫等）。这些是**作者定位索引**，不是对其所有作品的永久使用授权。

结构化登记位于 tools/character_sources.json。初始候选：纳西妲原生主角色、派蒙Codex图集、阿丽莎3D/动作待寻。它们均标记为“授权未核实”，不能由发现条目直接进入发布。

## Windows 命令示例

在仓库根目录、当前Python环境安装 Pillow 后，依次运行：

    py -m pip install "Pillow>=10,<13"
    py tools/character_pipeline.py sources
    py tools/character_pipeline.py new genshin_paimon_001 --name 派蒙 --channel codex_pets --kind codex --profile genshin_paimon --url https://codex-pet.org/zh/pets/paimon/
    py tools/character_pipeline.py attach genshin_paimon_001 --asset "D:\Art\Paimon"

**严格限制**：以下 rights 命令必须在真人阅读对应素材作者规约、并确认允许本地使用及改编之后执行。证据路径为本地保存的真实条款文件；不得把示例当成已有授权。

    py tools/character_pipeline.py rights genshin_paimon_001 --reviewer "审核者" --evidence "D:\Art\Paimon\LICENSE.txt" --local-use --derivatives
    py tools/character_pipeline.py inspect genshin_paimon_001
    py tools/character_pipeline.py build genshin_paimon_001

构建产物位置：data/character_pipeline/build/genshin_paimon_001/ChibiPipelineRole。查看 ANIMATION_PREVIEW.png 及 IMPORT_REPORT.json，再在软件中通过“添加角色 → 角色文件夹”选择此目录进行真实桌面验收：

    py tools/character_pipeline.py qa genshin_paimon_001 --reviewer "视觉与运行验收人" --visual-pass --runtime-pass

**只有在权利证据明确允许再分发时**，人工登记 rights 命令才可增加 --redistribution；之后执行：

    py tools/character_pipeline.py package genshin_paimon_001

package 命令仅生成本地 data/character_pipeline/releases/genshin_paimon_001.zip；未获改编/再分发许可则报错。审核记录属于人工声明，不代表工具可代替律师或自动核实许可真实性。

## 模之屋 PMX / VRM 的转换准备

    py tools/character_pipeline.py new ailimit_arrisa_3d --name 阿丽莎 --channel aplaybox --kind model3d --profile ailimit_arrisa --url "作者的具体模型地址"
    py tools/character_pipeline.py attach ailimit_arrisa_3d --asset "D:\Models\Arrisa\model.pmx"
    py tools/character_pipeline.py render-plan ailimit_arrisa_3d

生成 data/character_pipeline/plans/ailimit_arrisa_3d.json，列出所需的待机、左右走、招呼、跳跃、休息、睡眠等透明帧、视角一致性要求，以及待办权限。作者可能只允许MMD环境内使用，不能默认转换为桌宠。获得许可并离线渲染出 idle_0.png、idle_1.png 等后，另建 kind=frames 候选，走正常授权审查与转换流程。

## 来源维护

    py tools/audit_character_sources.py
    py tools/audit_character_sources.py --max-age-days 90 --strict-freshness

第一项仅做离线注册表格式/重复/更新时间审查，不自动联网；第二项在来源人工核查超过90天时以非零状态提示维护。建议每月人工确认 AplayBox、B站等入口的可用性，以及候选作品页面是否仍有效。自动CI通过不等于链接可下载、模型已获授权。

## 验收门槛

代码：Windows/Linux × Python3.9/3.11 回归测试、独立CLI测试，外加Windows真实Qt动作加载冒烟。人工：目标人物视觉、动作连续性、脚底/悬浮、信息卡和桌宠交互。3D：必须先有实际透明帧，不能把PMX配置模板视作成品角色。最终：公开发布角色包时逐角色核对权利、证据、作者署名及改编后的再分发范围。
