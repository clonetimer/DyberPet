# DyberPet 桌宠助手：交互文件、离线语音与 PPL 人设（P0）

右键桌宠 → Desktop Pet Assistant (Files / Voice / Persona)，打开独立对话框。不改变现有养成/动画/其他右键菜单。此分支与角色导入流水线 PR 独立。

## 文件：由用户手动确认的操作

默认目录为当前用户的 Documents/DyberPetAssistant。只有 .txt / .md / .json / .csv 文件可操作，最多 256 KiB，不允许覆盖，禁止跨目录、路径穿越和符号链接。用户可点击“本次授权其他文件夹”，**逐次显式确认**一个位于用户主目录内的具体子文件夹；不得直接授权主目录/桌面/文档根目录及隐藏系统目录。授权不写入设置，点击“恢复默认目录”立即撤销；不会递归操作子目录。
“创建文件”：明确填写文件名/内容，二次确认。 “删除到可恢复区”：选择文件并再次确认，仅移到目录内 .pet_trash，不是永久删除，也不是系统回收站。“恢复文件”：允许恢复，若同名目标已存在则拒绝覆盖。
聊天模型输出不会被解释为文件操作；语音识别只是填回文本框。现在不支持任意磁盘路径和自然语言直接删除。

## 语音：可选离线模块，不会常开麦克风

在运行桌宠的 Python 环境中执行：

    pip install vosk sounddevice pyttsx3

下载所需语言的 Vosk 离线识别模型：https://alphacephei.com/vosk/models ，将解压后的本地文件夹绝对路径输入“离线识别模型”。点击“录音识别（4秒）”后，麦克风采样约4秒（16kHz、单声道）；只在内存中转写，识别文字放回输入框，必须再次手动发送。
“朗读上一条回复”调用本机 pyttsx3，中文声线取决于系统已安装语音。缺少扩展依赖时给出提示，不影响原有桌宠运行。当前不提供常开监听、唤醒词或语音实时打断。

## 互动反馈与配置持久化

对话成功后，桌宠会通过 DyberPet 现有的气泡机制展示前120个字符；文件创建/移入可恢复区/恢复成功时也会显示气泡提示。设置“交互成功时播放已解锁动作”可选当前角色**真正存在且已经解锁**的动画，不会伪造不存在的“挥手/工作”动作。角色切换会刷新可用动作表，正在执行的旧角色对话不会展示到新角色身上。

勾选“自动朗读模型回复”可在本地模型返回后自动调用离线 TTS，默认关闭。用户点击“保存助手设置”时，模型地址/模型ID、语音模型路径、PPL 连接开关、每角色人设偏好、气泡/自动朗读配置将保存到应用配置目录（Windows APPDATA/DyberPet/assistant.json，Linux ~/.config/DyberPet/assistant.json）。配置文件采用原子写入，不保存聊天记录、录音、PPL 原始内容及人设快照；临时文件夹授权不持久化。切换角色时自动清除旧人设快照，避免错用。

## 多角色贴近原设档案

除了咕嘎，Doro、派蒙、纳西妲、可莉、芙宁娜、阿丽莎也能使用独立的人设模板与“核查当前角色 / 登记本地授权 WAV / 试听”入口。默认声音仍为系统 TTS，不等于任何角色原声；短音效与 TTS 分离，按角色的独立本地记录保存，跨角色记录和变更哈希均被拒绝。缺少合法动画包时，检查会明确报错，不把预设当成完整模型。详见 [多角色贴近原设验收规范](character_fidelity.md)。

## 派蒙迷你宠物（SubPet）

若安装的是 `res/pet/Paimon` 或 `res/pet/派蒙`，它属于迷你宠物而不是主桌宠 `res/role`。本版已在迷你宠物的原生 Qt 动画窗口中增加受控悬浮：当只以地面为基准、仅在 X 轴跟随主桌宠时，缓慢离地并周期浮动；同时跟随 X/Y 的原有角色配置不会被覆盖。拖拽、坠落、关闭时暂停或停止补偿。

迷你宠物右键菜单新增 **Suspend Hover / Enable Hover**，只对该迷你宠物本次运行有效。默认是否启用由用户保存的 `motion_enabled` 读取。在桌宠助手中也可以点击 **检查派蒙迷你宠物（res/pet）**，查看本机实际安装目录、X/Y 跟随模式和是否适合额外悬浮；即使当前主桌宠不是派蒙，也可以执行这项检查。

注意：这里没有自动下载派蒙图集、官方配音或原版动作；主角色与迷你宠物的代码路径分开，更多验收细节见 [多角色原设验收](character_fidelity.md)。

## Doro 四足跑动与文字转语音反馈（P6）

Doro 的原生左右移动动作需在安装的角色中提供**每个方向至少四张不同画面帧**、正确的 `left/right` 动作引用及方向信息；桌宠现在只针对这些确认过的原生步行动作施加可关闭的 1.3 倍位移补偿，不会把跳跃、挥手、鼠标拖拽或其他水平交互动作加速。没有这种动作包时，仍按原版普通移动，且“核查当前角色”会提示素材不足。帧数不能证明画面里确实有四条腿的正确步态。

在本地 LM Studio 对话后，若选择“自动朗读”，则桌宠会在本机 TTS 引擎**确认收到朗读内容**时显示回复气泡；如果角色配置内已经存在明确的 `talk`、`speak`、`说话` 或 `口型` 等已解锁的原生动作，也会触发一次该动作。没有说话动作时，只有文字和语音，不伪造口型。朗读失败时依然展示文本，且清理“说话中”的视觉状态。

此功能不包含音素级口型同步、按语音时长重复播放的完整唇形动画或官方角色声线克隆；角色声音仍取决于用户本机 TTS 引擎及实际许可的本地音频。

## PPL 人设分层

仓库：https://github.com/clonetimer/PPL 。Character Governance 提供关系状态、信任度、事件规则和审计，不是聊天模型。Persona DSL 是独立的编译/render 合同，生成 LLM-facing 的静态/动态提示词。不能把两者混为一谈。

可选启用 PPL Character Governance：在独立目录克隆 PPL 后安装 Node >=22.16；npm install；运行 node product/character-governance/bin/server.mjs。默认监听 http://127.0.0.1:8790 。为跨重启持久化配置 PPL_DB SQLite 文件（依 PPL 仓库说明）。在桌宠勾选“读取 PPL 关系状态”后会按当前角色创建或恢复独立 session。只有用户点击“向 PPL 发送安慰事件”才提交 COMFORT 事件，每条唯一 eventId；聊天文本不会自动影响角色状态。

要使用 PPL 0.3 完整人设，先在 PPL 项目中使用官方 CLI 对 .ppl 程序执行 resolve/render 并将输出重定向为 UTF-8 文本文件。示例在组件目录执行：

    node dist/src/cli.js render examples/zhuang_fangyi/persona.ppl --module-root modules --runtime examples/zhuang_fangyi/runtime.lover.json > persona.txt

然后点击桌宠窗口的“导入 PPL Persona DSL 渲染快照（文本）”，选择可信的本地文本并确认。人设快照最大16000字符，仅在本次应用进程内保存；它是某时刻的 PPL 渲染结果，不代表桌宠直接编译 .ppl 或提交 PPL Runtime 状态。

## 本地模型（LM Studio）

先在 LM Studio 启动 OpenAI-compatible 服务并加载模型；在桌宠助手中填写 http://127.0.0.1:1234 和所加载模型的准确 model ID。文本发送到本机 /v1/chat/completions；PPL 关系状态及可选渲染快照作为提示词上下文。
仅支持 loopback HTTP 服务，拒绝远程URL、代理、重定向；请求在 Qt 工作线程执行并有超时和响应大小限制。不配置本地模型时不会伪造回答；聊天内容默认不落盘。文件操作永远由 GUI 手动触发。

## 自动化与真实运行边界

tests/test_assistant_files.py、tests/test_assistant_persona_voice.py 覆盖文件隔离、删除恢复、PPL 会话/event 协议、语音输入保护和本地模型通信条件。tests/test_assistant_qt.py 验证 Qt 离屏 GUI 操作。GitHub Actions 提供 Windows/Linux Python3.9/3.11 及 Windows PySide6 冒烟。
实机麦克风、Vosk 中文准确度、pyttsx3 中文 TTS、真实 LM Studio/PPL 进程及 Windows EXE 安装仍需要独立验收。当前 PPL 连接使用已公开的 Character Governance HTTP API，并未自动启动、改写或内置 PPL 服务。


## 一键本机功能自检（个人版候选）

在桌宠上右键打开「桌宠助手」，点击 **本机功能自检（无联网／录音）**。这个按钮只读：
- 检查可选的 `pyttsx3`、`vosk`、`sounddevice` 依赖是否能够在当前 Python 环境被发现；
- 检查 Vosk 模型路径是否包含 `am/final.mdl` 与 `conf/model.conf` 等基本目录结构，空文件夹不再误报为就绪；
- 检查 LM Studio 的模型 ID 是否填写，以及 URL 是否是显式端口的本机 HTTP 地址；
- 若用户启用了 PPL，检查 PPL URL 是否仍是有效的本机 HTTP 地址。

**自检不会打开麦克风、试听扬声器、连接 LM Studio/PPL、持久化聊天或更改任何本地文件。** 显示「已配置」仅代表准备条件满足，不代表实际设备和模型服务已经验收。之后用户仍需分别手工点击「录音识别」「朗读上一条回复」「检测模型」完成对应的真实测试。声音原设相似度与 123 个角色图集视觉 QA 不由自检宣告通过。

实现为 `DyberPet/assistant/readiness.py`（无 GUI 依赖），离线用例在 `tests/test_assistant_readiness.py`；Qt 集成覆盖于 `tests/test_assistant_qt.py`。

## 所有角色的主动互动快捷动作（本轮追加）

桌宠助手新增 **「主动互动（仅已解锁原生动作）」**：根据当前主桌宠已安装并解锁的动画，动态展示「打招呼、蹦一蹦、观察周围、休息一下、散步、说话动作、睡觉、摸摸头、爬行」。用户选择后点击「让当前桌宠执行」，只通过原有 `action_requested` 信号调用运行时，运行时再次检查当前人物的 `unlocked` 状态，故不会由语言模型的文本或普通语音识别结果自动触发。

同一类互动可以使用原画 Codex（如 `wave`, `jump`, `lookaround`）或原生 DyberPet 中文动作组（如「打招呼」「左右散步」），**严格全名匹配**，不会把「attack_wave_effect」之类不相关的动作猜作招手。缺对应动作时禁用按钮并提示用户导入更完整的原作者素材；不使用占位图、不重复一帧冒充多种动作，当前角色切换后立刻清空原角色动作授权并重新同步。

该功能对**全部 123 位原神模板和咕嘎/Doro 两位独立角色**采用统一运行时接口，但**只有真实安装且解锁的动作才可执行**。实现 `DyberPet/assistant/role_interactions.py`，单元测试 `tests/test_role_interactions.py`，Qt 行为测试 `tests/test_assistant_qt.py`。这是可靠的交互入口，不等于 125 个角色原设动作素材已经齐全。

## 每位桌宠的真实互动素材审计（不拿演示角色冒充已完成）

`tools/character_interaction_coverage.py` 会扫描 123 位原神人物模板和咕嘎/Doro 独立角色，针对**本机真正安装的创作者素材**记录动作名称、哪些快捷互动有真实帧、哪些尚缺，并输出每角色清单；内置几何 Q 版演示一律不计入艺术作品互动覆盖。

命令：`python tools/character_interaction_coverage.py --output character-interactions.json`。此清单不连接网络、不修改任何角色文件；`runtime_unlock_qa_verified=false`、`character_likeness_qa_verified=false` 直到后续逐角色真实 Qt/外观人工验收。源动作名称存在只说明图集可能支持该类别，不表示游戏状态已解锁，更不代表角色自己的独特姿势或音色已达标。

目标是将每名角色的 **动作素材存在 → 实机能触发 → 动画连续且原设辨识度合格** 三层分别闭环，缺的内容明确列出来，再持续从公开作者来源补真实素材。

**Shimeji 动作语义补齐：** 新增 `patpat`/`climb` 精确别名，仅当选中角色的 `act_conf` 真有对应动画、当前运行实例确已解锁时才可触发。程序只播放已有真实帧，不能用重复/空素材冒充抚摸、爬行动作。测试覆盖缺动作与假名称不误匹配。
