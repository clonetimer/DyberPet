# Q版三视图设计与内置角色验收门禁（候选）

本规范适用于**实际已内置**的 DyberPet 角色，不适用于仅有名称的角色模板。美术参考、动作和中文角色名称必须属于同一身份与同一造型版本；不能用镜像、三张相似动作帧或不同画师图稿拼接冒充三视图。

## 从三视图到实际桌宠

1. **身份**：登记作者、来源链接、角色中文名和固定造型；咕嘎、Doro 各自核查认可的具体版本，名字相同不意味着形象相同。
2. **同源正、侧、背**：优先从同一作者的原画/模型找到三个独立视角；没有背面时明确记为缺失。人物的头身比、脸型、发饰、服饰、主配色必须一致；四足动物核查身体轴线与步态，悬浮宠物不能硬套站立角色动作。
3. **真实动作**：待机、左右移动、摸头、拖拽、跳跃和专属动作映射原生帧；保持整段动作轮廓锚点固定，保留真实跳跃高度而非逐帧重心突变。
4. **人工验收**：逐角色核对关键标识、正侧背身份和动作换帧；SHA256 只能核实文件字节，不能代替原设审美、人设或权利判断。
5. **内置交付**：随程序一起打包实际的 res/role 目录；空模板、抽象测试动画及镜像背面不能作为已完成角色宣传。

## 可选三视图源 manifest

在角色文件夹下使用 Q_CHIBI_3VIEW.json，支持以下 schema_version=1 的结构。每张图只能相对引用角色目录中的 action/ 或 threeview/ PNG 文件，使用真实原始文件的 64 位 SHA-256：

    {
      "schema_version": 1,
      "artist": "实际原画作者",
      "source_url": "https://example.org/original-author-project",
      "variant": "同一造型版本",
      "views": {
        "front": {"file": "threeview/front.png", "sha256": "填入真实SHA256"},
        "side":  {"file": "threeview/side.png",  "sha256": "填入真实SHA256"},
        "back":  {"file": "threeview/back.png",  "sha256": "填入真实SHA256"}
      }
    }

缺任何一个真实方向图时，不要虚构完整 manifest。三视图预览仍可显示真实待机/左右移动源帧作为候选，但明确“未确认正交视角”。

## 已接入工程的检查

- tools/qchibi_native_threeview.py：源图路径与文件哈希，严格拒绝假背面文件引用。
- tools/qchibi_pose_geometry.py：可见轮廓统一比例，原始画素不变。
- tools/qchibi_threeview_audit.py：对实际安装角色逐一检测同图重用、精确水平镜像及明显尺寸不一致；输出真实角色清单。
- DyberPet/DyberSettings/qchibi_three_view_dialog.py：在 GUI 显示“证据候选/来源可疑/缺失”，不会自动批准形象完成。
- tools/build_windows_portable.ps1：交付 THREEVIEW_AUDIT.json 与安装包。畸形/可疑的三视图源证据会阻断发布；缺失三视图只统计缺口，不阻断已有真实角色使用。

源码根目录下执行：

    python -m unittest discover -s tests -p "test_qchibi_threeview_audit.py" -v
    python tools/qchibi_threeview_audit.py --role-root res/role --out THREEVIEW_AUDIT.json --fail-on-invalid

**私有 65/69 角色包注意**：如果先打 EXE、再恢复私有作者角色 PNG，必须在资源恢复后重做以上扫描，并将更新的 THREEVIEW_AUDIT.json 打入最终 ZIP；不能把公开精简包的旧扫描结果当成真实 69 角色扫描结果。

状态口径：missing_threeview_manifest 表示缺证据；invalid_threeview_evidence 或 threeview_requires_source_correction 表示有问题；threeview_source_candidate_manual_review_required 仅表示三个候选文件通过自动审查；threeview_human_approved 和 character_likeness_verified 仍保持 false，直到确有人工验收记录。

**本轮没有新增第三方 Q版三视图原画、没有宣称咕嘎/Doro 审美通过，也没有生成新完整安装包。** 下一阶段逐角色从同源三视图设计与补齐原生动作。
