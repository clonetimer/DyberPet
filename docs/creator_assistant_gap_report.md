# 角色素材与互动缺口总览（个人使用）

在 **系统 → 角色管理 → 全部角色库 → 导出全部角色素材与互动缺口 JSON** 中，用户选择输出位置后导出。没有选择文件就不写入；该功能不联网、不会下载角色、更不会修改已安装角色。

脚本入口（可离线使用）：

```powershell
python tools/creator_assistant_gap_report.py --role-root res/role --output DyberPet_role_gaps.json
```

报告分别统计：原神人物固定素材来源（123 名）；咕嘎与 Doro 两个独立吉祥物；用户本机有导入目录但素材损坏的角色；至少有一项首帧 PNG 可解码的角色；当前原画里静态可识别的动作类别与缺少的动作类别。

状态字段：
- `missing_pinned_source`：没有在来源清单内固定到原始资源的版本，并不否认用户可能拥有自己的素材。
- `pinned_source_not_installed`：只有可追溯的来源记录，当前电脑没有本地原画。
- `local_creator_files_unplayable`：本机发现导入目录，但没有任何首帧通过安全解码检查。
- `local_creator_first_frame_decodable`：至少一个动作的首帧可解码，**绝不表示全动画能够播放或符合人物原设**。

故意保持 `human_original_likeness_verified`、`complete_motion_sequence_verified`、`physical_desktop_playback_verified`、`voice_fidelity_verified`、`rights_verified` 为 `false`；用户不能靠文件大小、GIF、来源名称或者 CI 通过来自动盖章。咕嘎/Doro 不计入 123 人物的来源覆盖分母，内置几何演示图不计入真实作者素材。

完整逐帧结构审查请继续运行 `tools/artist_animation_audit.py`；外观与实际动态须在 Windows/Linux 真实桌面手工看图验收。


## 可选深度逐帧审计（2026-10-26）

日常 GUI 导出维持较快的首帧检查，不阻塞大量角色的界面。对已经导入真实画师素材的本机角色，可在 Windows PowerShell 里执行：

```powershell
python tools/creator_assistant_gap_report.py --role-root res/role --deep-frame-audit --output DyberPet_role_gaps_deep.json
```

这会逐原生角色调用 `artist_animation_audit.audit_native_character`，读取每个动作的**所有** PNG，检查序列连续、图像可解码、尺寸、透明帧、重复静帧，以及运动动作是否存在不同画面；有一套坏图不会阻止其它角色的报告输出。结果位于 `full_frame_structure_audit`，`passed_structure` 仅表示图像序列结构检查通过，不代表原设美术、动作语义、实际桌面播放、音色、版权或人工质量评审通过。标准的 `complete_motion_sequence_verified` 仍为 false。


## 2026-10-26 · 多素材版本不能合并冒充单个角色的互动能力

同一人物可保留不同作者的多个已安装版本（例如一版只有挥手，另一版只有跳跃）。总览报告的 `available_action_categories_in_art` 是**全部版本的并集**，不能据此断言当前桌宠同时拥有这些动作。新增：

- `per_installed_creator_version`：逐目录记录本机已解码的原画动作与每个动作类别。坏目录有独立异常，不计入可用素材。
- `categories_shared_by_every_usable_version`：所有可解码版本共同拥有的交互类别。
- `categories_missing_from_at_least_one_usable_version`：有的版本有、有的版本没有的交互类别。
- `roles_with_version_specific_action_gaps`：受多版本差异影响的人物数。

总览导出入口仍为系统的「全部角色库 → 导出全部角色素材与互动缺口 JSON」。正在运行的桌宠助手只能操作当前角色由 PetWidget **实时已解锁** 的原生动作，不能从其他文件夹借动作。所有结构性识别仍非原设人物视觉、人设声音或物理桌面验收。


## 2026-10-26 · 当前角色互动作业报告纠正名称空间混用

`act_conf.json` 的 `wave`、`jump` 等是**原生 PNG 动画键**；正在运行的 PetWidget 将 `pet_conf.random_act` 中的中文**动作组名**传给 `Interaction_worker.start_interact('actlist', ...)`。如果报告直接取两者名称的交集，会将真实可执行动作误报为未解锁。本轮导出和弹窗使用同一份实时校验通过的 `runtime_group_plan`，单独列出 `runtime_action_group_mapping`、`runtime_group_evidence_available`、`currently_unlocked_categories`；素材动作列依然只表示原画存在，不能代表已解锁或形象验收。离线非 GUI 调用保留旧名称报告兼容行为。


## 2026-10-26：本机真实作者动作逐帧预览

全部角色库里选中已安装真实素材的人物，点击「预览本机原画逐帧动作」；界面支持切换已关联的创作者版本、逐个选择动作、上一帧/下一帧、拖动帧位置与自动循环播放。所见为**当前本机来源的原始 PNG**，而非自动生成的原神替代形象；从未安装、仅素材网页、演示角色不能假装已经存在原画。所有序列先经过本地索引完整性及 PNG 解码检查，文件大小和像素数量受限，不下载、不修改素材、不写验收状态。实际桌面鼠标交互、人物服饰原设忠实度、声音仍需单独审核。


## 2026-10-26：逐角色人工外观 A/B/C 与动作核对记录（本机导出）

真实作者逐帧预览界面增加“原设外观”评级（未评价/A 较吻合/B 部分差异/C 明显不符）、“已人工对照原设”和“已人工检查动作”勾选、差异备注，以及“导出本版本人工核对记录 JSON”。仅在用户明确勾选对照时允许 A/B/C 评级；不会由 AI 或 PNG 解码结果自动赋予评级。记录保存当前安装目录、各动作已显示帧数、源码文件总数及源码字节的 SHA-256 快照，用户更换原画后不能沿用旧快照成绩。声线、原作身份、权利、Windows/Linux 真实桌面使用仍分别标为未验证。本记录为**用户自评**，不是官方或本项目独立验收证明。不会将第三方图像写入仓库，也不会向外部上传。


## 2026-10-26 · 作者素材安装成功后直接预览真实动画

原先安装作者来源后的确认按钮只打开静态 `ANIMATION_PREVIEW.png` 拼图，无法判断动作是否连续。本轮使已校验原作者来源的安装成功提示直接打开 `NativeFramePreviewDialog`，自动聚焦**刚刚安装的角色版本**，支持逐帧、自动播放与 A/B/C 用户自评；非创作者演示导入仍保留传统缩略图预览。用户取消时不触发下载或文件写入。损坏素材引发可见警告，不会导致桌宠主程序崩溃。
