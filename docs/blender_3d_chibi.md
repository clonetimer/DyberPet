# P5 — Blender 3D → 透明 PNG → Q版桌宠（首版）

此阶段完成可执行的原生 Blender 离屏渲染链路，而不是只生成 render-plan。**自动化测试使用程序生成的原创几何人物**，不使用、下载或附带任何游戏人物美术。工具对用户模型仅提供规范化相机和整体运动帧，**不具备 MMD/VMD 骨骼动作重定向、IK绑定或自动角色美术制作能力**。

## 首版支持范围

- 原始模型：自有或已获具体授权的本地 **GLB、内嵌式 GLTF、FBX**。非内嵌的 GLTF 引用外部纹理和二进制文件，当前单文件哈希无法覆盖，要求先导出为 GLB。
- **PMX、PMD、VRM、BLEND**：不直接接入自动导入。先在已有许可证允许的前提下，用 Blender/MMD 对应插件导入，再导出自包含的 GLB。动作数据的许可应单独核实。
- 输出：192×208 RGBA 透明 PNG；每个动作从 0 开始编号，例：idle_0.png、idle_1.png、left_walk_0.png。
- 运动：程序对模型整体进行轻量的待机呼吸、左右移动、跳跃、休息和观察；不承诺真实走路步态、手臂挥动或面部表情。**当前只有合成原创测试模型含独立右臂挥手运动**。
- 相机：正交、固定视角、背景透明；使用 Cycles CPU 便于离屏渲染。
- 自动检查：透明背景、非空像素、帧数量、192×208 尺寸、接近边缘的裁切警告、生成 JSON 报告。
- 失败保护：工作在独立临时目录，成功且检查通过后才将透明帧移动至结果目录。不会覆盖已有角色或者输入模型。

## Windows 测试方式

安装 Blender 4.x，确认命令行可找到 blender.exe；桌宠 Python 环境须安装 Pillow：

    py -m pip install "Pillow>=10,<13"
    blender --version

先运行**原创合成模型**测试（不需要下载第三方资源），输出 3 类动作，每类 2 帧：

    py tools/render_chibi_blender.py --demo --blender "C:\Program Files\Blender Foundation\Blender 4.5\blender.exe" --output "D:\Art\DemoFrames" --frames 2 --actions idle,left_walk,wave

输出 DemoFrames 下有 idle_0.png、left_walk_0.png、wave_0.png、BLENDER_RENDER_REPORT.json。再验证 DyberPet 原生角色转换：

    py tools/import_chibi_animations.py "D:\Art\DemoFrames" --profile chibi --folder BlenderDemo

实际有权使用的 GLB 或 FBX 模型示例：

    py tools/render_chibi_blender.py --source "D:\Models\LicensedMascot.glb" --blender blender --output "D:\Art\LicensedMascotFrames" --frames 6 --actions idle,left_walk,right_walk,wave,jump,wait,review

**注意**：这个输入脚本是本地文件执行，3D 模型仍可能携带外部贴图或者异常数据。Blender 以 --disable-autoexec 禁用自动运行模型内脚本，但是不构成对不可信文件的完整沙盒隔离。仅处理可信、合法获取的资源。

## 接入 P4 角色新增流水线

以具体模之屋模型为例（必须经真人查看作品权限）：

    py tools/character_pipeline.py new original_chibi_3d --name 原创Q版 --channel aplaybox --kind model3d --profile chibi --url "具体作者作品链接"
    py tools/character_pipeline.py attach original_chibi_3d --asset "D:\Models\OriginalChibi.glb"
    py tools/character_pipeline.py rights original_chibi_3d --reviewer "审核员" --evidence "D:\Models\LICENSE.txt" --local-use --derivatives
    py tools/character_pipeline.py render original_chibi_3d --blender blender --frames 6

render 命令在被忽略的 data/character_pipeline/renders 下保存透明 PNG，并建立新的 **original_chibi_3d_frames** 子候选记录。子候选保留原模型来源和 SHA-256 关系，但**不继承已通过的权限批准**，仍须审查最终渲染用途和动作素材：

    py tools/character_pipeline.py inspect original_chibi_3d_frames
    py tools/character_pipeline.py rights original_chibi_3d_frames --reviewer "审核员" --evidence "D:\Models\LICENSE.txt" --local-use --derivatives
    py tools/character_pipeline.py build original_chibi_3d_frames

角色包构建后检查 ANIMATION_PREVIEW.png 和 IMPORT_REPORT.json，导入 Windows DyberPet 实际播放；人工确认真实视觉与运行，再记录 QA。公开打包必须另外核查允许再分发的权利。

## P6：优先使用模型自带动画片段

经过授权的 GLB/GLTF 导入 Blender 后，glTF 的骨骼/对象动作通常被组织在 NLA 轨道中。新增的导入器现在支持按轨道名称将动作映射到 DyberPet 的 idle、left_walk、right_walk、wave、jump、wait、sleep、review。

- 有对应片段：同时启用该动作名在各对象上的 NLA 轨道，采样真实动作，输出报告的 animation_sources 标为 clip。
- 无匹配片段：只输出程序生成的整体运动 procedural_fallback；不将其宣称为真实骨骼/表情动作。
- 开启 --require-clips：所选全部动作必须有对应 NLA 片段，缺少任何一个都拒绝输出。
- 可用 --clip-map <映射文件.json> 为不规范的片段名建立显式对应关系。文件内容的 SHA-256 记录在渲染报告中。
- 不将名称为 walk 的单一片段自动当作左右两个动作；真实骨骼动作可能依赖分别提供左右动画或人工重新制作。

仅包含 Idle、WalkLeft、WalkRight 和 Wave 的模型示例：

    py tools/render_chibi_blender.py --source "D:\Models\Character.glb" --output "D:\Art\ActionFrames" --frames 8 --actions idle,left_walk,right_walk,wave --require-clips

如果作者命名为 Character_Stand 和 Hand_Greet，先在本地建立 clip_map.json：

    {
      "idle": "Character_Stand",
      "wave": "Hand_Greet"
    }

    py tools/render_chibi_blender.py --source "D:\Models\Character.glb" --output "D:\Art\ActionFrames" --frames 8 --actions idle,wave --require-clips --clip-map "D:\Models\clip_map.json"

完整新增流水线也提供 render 命令的 --require-clips 与 --clip-map 参数。动作轨道存在并不代表骨骼绑定正确或作品已授权公开发布，必须另行人工验收。

## 自动化测试的验收口径

代码测试：Python 3.9/3.11 × Windows/Linux 的输入校验、安全路径、GLTF 外部资源拒绝、来源追溯与发布闸门。真实渲染：单独的 Blender chibi render smoke 在 Ubuntu 安装系统 Blender，以原创几何模型生成透明 PNG 后直接构建 DyberPet 角色。GUI：保留 Windows PySide6 PetConfig/QPixmap 真实动作加载冒烟。

**仍然不能认定为完成**：任意 PMX/VRM 一键导入；真实阿丽莎、派蒙、纳西妲的合法素材下载、复杂骨骼动作或角色专属 Q版模型生成；Windows 真正桌面实时交互及 EXE 打包。
