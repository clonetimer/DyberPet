# 咕嘎与 Doro：无需手动搬文件的双层角色支持

本功能来自独立 PR #8，面向个人本地使用。保持原来的 123 个原神人物／伙伴演示角色不变，额外增加**两套形态独立、真正含有动画的原创演示皮肤**，并提供“自愿联网安装具体作者发布的二创素材”操作。

## 首次启动就可使用

下载新的 **Windows / Linux 便携候选版**：`res/role/DemoMascotGuga` 和 `res/role/DemoMascotDoro` 已在构建时生成，不需要用户导入、安装 Python 或配置 Node。

- **咕嘎风演示**：原创蓝绿色企鹅连帽、直立摇摆步态；有待机、左右走、挥手、跳跃、等待、阅读等 7 组／46 帧。
- **Doro 风演示**：原创粉色头发、白色横向四足身体；四只爪各有运动帧（左右步态不是双足角色的镜像占位）；同样 7 组／46 帧。
- 两者全由 DyberPet 的 Pillow 绘图代码生成：**不是 CIRCUS 的咕嘎作者图、不是 Doro／桃乐丝真正的二创动画、更不是游戏配音**。

选择 **系统 → 角色管理 → 咕嘎 / Doro** 可看到「原创演示」和「个人来源导入」分开的数量。原有角色不会被覆盖或删除。

## 一键安装真实作者发布的 Codex 图集（仅在用户确认时）

用户选「咕嘎 / Doro」→「【联网安装】咕嘎作者公开图集」或「【联网安装】Doro 二创作者图集」，软件会弹出作者／条款提示，确认后自动完成下载、SHA-256 校验、Codex V1 图集转动作帧、安装与动画结构检查。无需你再去模之屋、网盘或 GitHub 手动下载文件。

上游来源为 [legeling/awesome-codex-pet](https://github.com/legeling/awesome-codex-pet)，精确条目 `guga--circus` / `doro--lingxiaotian`，固定的提交版本为 `db2f6306ce78f6559ab27155d7bfaf00bf43809d`。工具不会接受用户输入的任意 URL，下载最多 6 MiB，每个请求都有固定大小、哈希校验，图集只保存在本机角色目录。**源版本更新时会拒绝安装，而不会改为下载未经校验的新版本**。

| 素材 | 作者／类型 | 使用限制 |
|---|---|---|
| 咕嘎公开图集 | CIRCUS，Codex Pets 社区上传 | 原始提交**没有明确的再分发许可**；建议个人使用，未经许可不可再次发布 |
| Doro 二创图集 | legeling 的 Doro 二创 | 原始条目标注 CC BY-NC 4.0，且 *NIKKE／桃乐丝／Dororong* 的底层知识产权另算，不代表取得官方授权 |

一键安装也不包含原声、声优音频或“完全还原原设”的人工结论。成功安装后会优先列在“个人来源导入”类目；原来的演示皮肤保留，可随时切回。

若设备不联网，仍可在角色管理界面使用内置两套演示皮肤，或通过原有「添加角色」手动导入已经取得的 `pet.json` + `spritesheet.webp` 文件夹。

## 自动验收边界

CI 验证两套内置角色的所有 46 张图像都存在、左右步态至少 4 个不同画面；冻结 Linux Xvfb 与 Windows EXE 确实能读取两套角色，并能打开咕嘎／Doro 状态窗口。作者图集的精确下载另有固定来源验证；**没有经过实机的外观高度还原、原声复现、麦克风和长期稳定运行人工 QA**。

开发者只需要生成本地原创演示：

```bash
python tools/generate_mascot_demos.py --output-root res/role
```

仅在自己明确同意、并了解个人／非商用限制时，运行来源安装：

```bash
python tools/install_creator_mascots.py --mascot guga --personal-use
python tools/install_creator_mascots.py --mascot doro --personal-use
```

安装原作者图集与生成原创演示是两套互相独立、互不覆盖的流程。
