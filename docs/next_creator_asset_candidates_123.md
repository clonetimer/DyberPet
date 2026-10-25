# 123 角色公开动画素材：下一批来源核验工作台（2026-10-25）

> 此表是**未核验候选**，不是已安装角色，也不增加 `character_source_coverage.py` 的 30/123 统计。优先真实精细 Q 版，其次画师 Shimeji；拒绝简笔画、空白模板及跨人物错配。

| 候选资源 | 公开页面证明的角色 | 资产形式 | 新覆盖判断 | 核验状态 |
| --- | --- | --- | --- | --- |
| [rullerzhou-afk/codex-fan-pets](https://github.com/rullerzhou-afk/codex-fan-pets) | 可莉、宵宫、桑多涅、派蒙、芙宁娜，另有丘丘人（不在 123 位人物统计内） | `pets/<role>/pet.json` + `spritesheet.webp` | 需与既有来源取并集去重；不可直接加 6 | 待固定 SHA / 帧预览 / 角色 ID |
| [chenxin-dlut/codex-anime-pets](https://github.com/chenxin-dlut/codex-anime-pets) | 芙宁娜、甘雨、胡桃、可莉、雷电将军等 | Codex 角色图集与 contact sheet | 主要为候选画风替代，不推断新增角色 | 待固定 SHA / 视觉分级 / 去重 |
| [ZaytsevZY/genshin-pets](https://github.com/ZaytsevZY/genshin-pets) | 胡桃、茜特菈莉 | 角色安装目录、GIF 与 QA 图 | 胡桃已经有来源；茜特菈莉也须先对照现有名录 | 部分来源已登记，禁止重复计算 |
| [AkshitIreddy/AI-Desktop-Pet](https://github.com/AkshitIreddy/AI-Desktop-Pet) | 绫华、阿贝多、重云、枫原万叶、胡桃、可莉、托马、温迪 | 作者 Shimeji 原动作 | 已固定进入既有工作台 | 已登记，不重复新增 |

## 将候选转为可用来源的必要步骤

1. 确认原作者、仓库具体 commit、角色名与原设特征（发型、服饰、饰品、色彩）；去掉同名其他作品、错配角色和不合格简笔画。
2. 打开每个角色真实待机与行走帧；检查不是一张图复制多帧、不是自动生成的替身。P1 精细 Q 优先，P2 正确 Shimeji 备选。
3. 原样记录 `pet.json` / `spritesheet.webp` 或独立 PNG 的 Git blob、字节数、动作帧映射；不要因为 README 写有角色名字就算“找到素材”。
4. 在独立的 installer manifest 中新增**稳定人物 ID**和哈希，并写下载校验/错误回退测试；来源只能在用户本机主动确认后安装。
5. 在 Windows/Linux 真实 Qt 中预览、切换、透明显示和动作；最终原设还原由逐人视觉复核决定，不能由 CI 绿灯代替。
6. 仅在上述前四项均可信后更新“固定来源覆盖数”；只有真实安装与人工核验均通过才可标记已完成。

## 用户验收状态定义

`missing_source` → `candidate_unverified` → `pinned_source` → `installed_local` → `visual_approved` → `desktop_accepted`。

**禁止:** 自动以演示几何图生成所谓正式人物；把图集来源等同原作外观验收；未经素材权利核实将其他作者图包上传公开 GitHub Release。前端应显示真实状态而非虚假的“123 人已内置”。

本阶段的新增发现来自各上游公开 README，并非逐帧视觉核验结果。

## 2026-10-25：额外公开 Shimeji 资源候选（不计入固定来源）

| 角色（原先未覆盖） | 公开页面 / 署名 | 实际发现 | 计数与下一步 |
| --- | --- | --- | --- |
| 荒泷一斗 `genshin_arataki_itto` | [Arataki Itto Shimeji](https://shimejishop.com/free/arataki-itto-shimeji/)，页面署名 **Ookami** | 页面展示预览及下载入口，且称可运行 Windows/Mac/Linux | 尚未核实原始动画文件来源、内容安全、SHA 和角色真实帧，先不计数 |
| 卡维 `genshin_kaveh` | [Kaveh Shimeji](https://shimejishop.com/free/kaveh-shimeji/)，页面署名 **ilewdha** | 有角色动作预览与下载入口 | 尚未核实原始 PNG/XML 下载包与哈希，先不计数 |
| 基尼奇 `genshin_kinich` | [Kinich Shimeji](https://shimejishop.com/free/kinich-shimeji/)，页面署名 **shimejimascot** | **注意**：分类页写 Free，但详情页只提供 Buy 按钮 | 不当成可免费直接下载；需确认真实资源渠道与作者授权后再转入固定来源 |

候选页面包含“下载软件/运行 .exe/.jar”的文案。安全导入仅应提取经核验的 **图片和角色配置**，不能自动运行任意来源的 EXE、JAR、批处理或脚本。任何公开预览不等于真正取得合法、完整、可用的帧序列。所有这些资源的原设人物相似度亦未验收。
