# DyberPet R33：Q 版三视图先行工作流（角色美术基准）

适用新制作或重制角色。三视图是**制作的输入依据**，不是三张静态图就能自动变成动态桌宠，也不是自动证明与官方原设相同。

## 固定顺序

1. **锁定角色版本**：中文名称、出处作品、服装版本、体态（站立/四足/悬浮）、要保留的标志性元素。咕嘎先核对企鹅帽/白色腹部及对应版本头饰；Doro 先核对粉发、紫眼、白色四足躯体，不得误做成直立少女。
2. **寻找同一版本的三视图**：优先作者原始角色设定/建模 Q 版三视图；其次同一套可合法使用的 Q 版模型多角度正交截图；不足时先委托/绘制统一的设计稿并人工核对。不能拿同一角色不同画师或不同服装版本拼合。
3. **核实可用性**：具体来源链接、作者、衣装版本、单件模型/美术许可；本地改编和再分发分别判断。可看不等于能复制、改编或随软件发布。
4. **裁切前/侧/背视图**：单张三视图可在本机无损拆成三个图片（PNG/JPEG/WebP）；三张图必须为三个不同的视角，人物脚底同一基线，头身比、眼睛、发型/饰物、配色、服装结构一致。保留原三视图作为不入库的本机证据。
5. **人工四项批准**：轮廓与体型（silhouette）、服装与色彩（outfit）、身份标志（identity）、跨视角一致性（cross_view）；否则构建被阻断。程序只检测图像文件、三个不同的哈希、变更与人工签核，**不能自动知道视角是否真实/角色是否像原作**。
6. **设计动作**：从统一模型/参考设计制作动作关键姿态，按 DyberPet 原生格式导出。基础：待机、左右走、互动、休息、说话；有明确角色需求再增加跳跃/奔跑、睡眠、拖拽/落地、特技。Doro 的四足运动和派蒙悬浮不得套用人形两足模板。
7. **桌面验收**：原设并排比对 + 原生待机/移动/拖拽/交互动作实机预览；查看缩放、透明轮廓、身体朝向及动作衔接。声音、人设、原声使用许可独立审查。
8. **打包**：权利证据允许改编及分发、视觉与运行双验收、图片/动作哈希均未变更才允许本地出包；任何不合格角色留在候选，不计为已达到高保真完成。

## 素材选择优先级

| 等级 | 素材 | 使用条件 |
|---|---|---|
| A | 角色原作者/官方认可的 Q 版正、侧、背设计图 | 身份、版本、可用性独立核验；首选 |
| B | 单一作者 Q 版 3D 模型的三面正交视角 | 模型体态与原设人工确认，模型/渲染许可独立确认 |
| C | 同一形象画师补画的完整三视图 | 必须人工对比官方形象，确认统一风格 |
| D | 多网页零散图、表情包、自动脑补侧/背面 | **不能作为正式动作开发依据** |

## R34：审核前生成本地三视图对照卡

R33 的审批勾选不自动证明角色真实还原。R34 新增可实际查看的本地 PNG 审核卡，**三张参考图在同一缩放因子下并列**，标明原始宽高、前/侧/背标签、底部参考基线和源 SHA-256 前缀。半透明区域使用棋盘格，便于发现背景残留和切图边界。尺寸差异不会被强行拉伸掩盖；若来源裁切尺度不同，需要人工核实，并不能直接将三图当成正交模型视图。

使用方法（先执行 `turnaround-attach`）：

```powershell
py tools/character_pipeline.py turnaround-card doro_q01
# 查看输出 JSON 中的 review_card 路径，在 Windows 图片查看器中打开 PNG，
# 逐项对照同一版本的原作者图与该卡，再进行 turnaround-review。
```

审核卡默认保存在 `data/character_pipeline/review_cards/<候选ID>-<引用指纹>.png`，目录已由 `.gitignore` 排除，**含有原作者的图片副本，不得随源代码发布**。原图变更、丢失或哈希不符会拒绝出卡。相同引用再次生成时拒绝覆盖原审核卡，防止无痕替换审核证据。预览不代表许可、真实三视图或美术通过；勾选审核仍是人工责任。

咕嘎、Doro 的首批参考候选与动作开发目标参阅 [R34 首批角色试点](r34_role_pilot.md)。


## R36：模型三视图和动画帧共用同一批准来源

R35 的 `turnaround-render-model` 先生成并登记模型正/侧/背图；**确认原设后必须在原 model3d 候选上执行 `turnaround-review`，再运行 `render`**。R36 在模型到动作帧的转换处引入强制来源验证。新生成的 `frames` 子候选继承父候选的整套三视图、画师、造型版本和签名；动作仍然需要单独视觉与桌面交互验收。

生产动作渲染应使用严格模式：

```powershell
# guga_q3d01 已完成三视图审核；源 GLB 内还必须包含对应 NLA 动画片段
py tools/character_pipeline.py render guga_q3d01 --require-clips --frames 8 `
  --actions idle,left_walk,right_walk,wave,wait,sleep
# 将生成 guga_q3d01_frames 子候选，它继承已审核的三视图身份。
py tools/character_pipeline.py inspect guga_q3d01_frames
# 子候选还需要第二次逐件权利复核、build、真实外观和桌面交互 QA。
```

**严禁误判**：如果模型没有真实 NLA 动画，非严格的 `render` 会生成程序根节点位移。该产物标记为 `preview_only`，可以进行制作调试，但即使手工勾选了视觉/运行 QA，也**不能调用 `package` 作为完整角色包**。严格模式不仅要求 `--require-clips`，还要求报告中每个动作来源都明确为 `clip`。若源 GLB、审核后的三视图、渲染报告或从属关系被改变，构建/验收/发布被阻断。

用于角色动作的下载文件、素材 URL 和许可证仍必须与同一作者、同一版本绑定。Doro 四足动作必须由四足模型真正的骨骼动作或经过人工核对的四足逐帧动画提供，不能靠简单窗口位移伪造。**真实动作来源与正交三视图未拿到前，咕嘎、Doro 都不计高保真完成。**

## R35：一个授权 3D 模型直接生成正交三视图

针对网络正、侧、背图片经常是不同作者/不同服装版本的问题，R35 新增 **同一 GLB 同一场景生成前 / 右侧 / 背面** 的真实 Blender 渲染器。

使用前提：你已取得同一角色版本的 3D 模型，**逐件人工核实本地改编许可**。仅接受自包含的 `.glb`；FBX、VRM、PMX 需先依照作者条款，在本地通过合法工具导出为 GLB。只在用户本机渲染，不自动下载第三方文件；`.blend` 工程不会被执行。程序执行 Blender 时使用 `--factory-startup --disable-autoexec`。

在仓库根目录使用以下命令：

```powershell
# 创建仅用于本地处理的角色候选，名称必须是中文角色名。
py tools/character_pipeline.py new guga_q3d01 --name "咕嘎" --channel bilibili --kind model3d --url "https://实际模型作者的作品页" --creator "实际作者"
py tools/character_pipeline.py attach guga_q3d01 --asset "D:\\Art\\Guga\\authorized-model.glb"
# 仅在本人实际核对了具体素材的许可、确认允许本地改编时登记。
py tools/character_pipeline.py rights guga_q3d01 --reviewer "实际审核人" --evidence "D:\\Art\\Guga\\LICENSE.txt" --local-use --derivatives
# 同一 GLB 连续渲染三张 512x512 透明 PNG，无人工批准效果。
py tools/character_pipeline.py turnaround-render-model guga_q3d01 --variant "锁定的Q版模型版本" --blender blender --front-yaw 0
py tools/character_pipeline.py turnaround-card guga_q3d01
py tools/character_pipeline.py inspect guga_q3d01
```

`--front-yaw` 默认 0°：假设模型面朝 Blender 的 -Y 方向；若导入模型正面朝向不同，可以通过 `--front-yaw` 调整，再重新生成（不同角度不可覆盖同一路径）。三个相机相差 90° 和 180°，**不能把正交侧视误认为普通斜前方**。三视图共享同一模型、归一化尺寸、相机投影与光照，保留完整透明度，且通过不同哈希、图像尺寸、可见像素和裁切检测。

输出位于已忽略的 `data/character_pipeline/turnaround_generated/`；`TURNAROUND_BLENDER_REPORT.json` 保存模型 SHA-256、各视图 SHA-256、Blender 版本与视角约定。三视图会自动登记到当前候选，但**保持待人工审核**。审核者应打开本地审核卡，确认与原作的身份特征、头身比、前侧背方向和配色一致，之后才可执行 `turnaround-review`。模型三视图正确并不意味着动作或使用许可已被软件自动验证。

没有模型时可通过 `py tools/render_turnaround_blender.py --demo --output "D:\\PetQA\\synthetic-3view"` 演示流程，演示几何是软件原创测试夹具，不是咕嘎或 Doro 的角色替代美术。

R35 私有参考素材（已提交）：仓库所有者可从 `clonetimer/ChatGPT-Download/private_assets/dyberpet/r35` 获取咕嘎和 Doro 的**候选**动画/视线参考；不自动公开或当作三视图证据。权利说明见私有目录 `README.md` 和 `licenses/`。

## Windows 本地 CLI

在仓库根目录（需要 Pillow），新建角色候选后执行；三视图文件仅保留在本机：

```powershell
py tools/character_pipeline.py new doro_q01 --name Doro --channel bilibili --kind frames --url "https://对应作者的具体作品页"
py tools/character_pipeline.py turnaround-attach doro_q01 `
  --front "D:\Art\Doro\front.png" --side "D:\Art\Doro\side.png" --back "D:\Art\Doro\back.png" `
  --reference-url "https://对应作者的具体三视图页" --artist "三视图作者" --variant "Doro四足Q版-确定版本"
py tools/character_pipeline.py attach doro_q01 --asset "D:\Art\Doro\animations"
# 本机逐图核对四项后才执行批准（并非示例命令自动替用户审核）
py tools/character_pipeline.py turnaround-review doro_q01 --reviewer "实际审核人" `
  --silhouette --outfit --identity --cross_view
py tools/character_pipeline.py inspect doro_q01
```

依照 [角色新增流水线](character_pipeline.md) 核实动画素材作者单件许可，登记 `rights` 后才能 `build`。修改三视图图片、替换动作来源、修改角色参考记录都会使签核失效；构建后修改设计必须另建候选 ID。

## 质量验收卡（每个角色一份）

- 角色（中文名）／作品／装束版本／画师／源链接
- 三视图：正面／侧面／背面三个本地图、哈希、尺寸、角色身份标志清单
- 动作矩阵：待机、左/右移动、交互、休息、说话、其他专属动作；每项记录原生帧数量、动画帧播放与桌面事件触发结果
- 人工审查：四项三视图勾选 + 审核人 + 日期；与原设并排核对分数只作为辅助，不以自动分数替代真人审批
- 结果：`待找三视图` → `三视图候选` → `已审核设计` → `动作制作中` → `实机验收` → `完成`

## 与旧安装器的边界

本轮门禁只直接约束 `tools/character_pipeline.py` 的新候选构建、QA 和本地 release，不改动用户已安装的角色，也不影响 `genshin_batch`、原画直接导入等独立安装器。既有 123 角色登记、可下载来源数量和原动作帧质量**不能据此重新标记为已完成**；后续按角色逐一补三视图设计卡，再接统一的角色管理界面。项目当前公开仓库不要上传第三方三视图或需要私有保存的素材。
