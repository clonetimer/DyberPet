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
