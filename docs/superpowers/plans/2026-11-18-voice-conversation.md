# Voice Conversation Implementation Plan

> **For agentic workers:** 依照已授权的连续执行方式，独立组件并行实现，根代理集成后做一次整批独立审阅；不逐项请求批准。

**Goal:** 用户开启一次，完成多轮说话、模型回复、朗读和再监听，并从原桌宠获得状态反馈。

**Architecture:** 会话控制器弱引用现有助手，在单 worker 的 finished 边界串联识别/聊天/TTS；独立识别器复用 Vosk 模型，原生反馈沿既有 PetWidget 动作路径。

**Tech Stack:** Python 3.9+ / PySide6 6.5.2+ / 现有可选 Vosk、sounddevice、pyttsx3 / unittest；无新增产品依赖。

**Spec:** `docs/superpowers/specs/2026-11-18-voice-conversation-design.md`

## Global Constraints

- 基线 `c460a95`，沿现有独立 feature checkout 与 Draft PR #99；基线三套完整 797 项和精确 SHA 远端工作流已验证，不重复空跑基线。
- 语音必须显式开启；不持久化开启状态；2000 字符/轮、30 秒监听/轮、20 个回复轮次/场、10 分钟/场。
- 保留键盘草稿和待手动发送附件；仅成功聊天回合写历史，语音不进入任务审批/文件执行。
- 单 worker、下一段在 finished 后推进；结束优先，角色/配置变化使排队操作失效。
- 不更换桌宠引擎；状态动作必须真实、已解锁、无声并让用户交互优先。

## Review Focus

- 打断后旧成功已排队，以及结束与“下一轮监听”定时事件竞态。
- 配置 A→B→A、关闭/重新打开、角色/人设变化，旧语音不进入新会话。
- 用户草稿、附件、普通自动朗读和手动停止与语音会话并存。
- 空语句、驱动异常、无效结果、时间/轮数边界不形成快速无限重试。
- 有声或资源不明的动作、拖拽/跟随/用户动作被自动状态抢占。

## Pre-flight

- Task 1 → Task 3：`VoiceTurnRecognizer(model_dir).listen(stop_event, *, on_partial=None, on_ready=None, sample_rate=16000, max_seconds=30.0) -> str`；停止返回空串，失败抛既有 VoiceUnavailable。
- Task 2 → Task 3：宿主信号 `interaction_changed(str, str)`；固定五种 phase，原生侧不修改 ui.py。
- Task 3 复用现有 `_submit` / `_job_finished`，提取 `_send_chat(text, *, voice_turn=False, on_reply=None)`；`_message_reply(result, *, voice_turn=False)` 禁止语音轮次再排普通自动朗读。
- 经验与总体验证由根代理统一维护；并行代理不改共享文档、ui.py 或同一测试文件。

### Task 1: One-utterance recognition

**Files:** 新增 `DyberPet/assistant/voice_turn.py`、`tests/test_assistant_voice_turn.py`。

- [x] 先验证首个非空完整语句、停止丢弃、流关闭后返回、加载缓存、部分识别、超时和失败的回归失败。
- [x] 实现精确接口；Model 在首次 worker listen 加载、同场复用，recognizer/stream 每轮独立。
- [x] 实际 Python 3.9 与 Qt 6.5 环境运行该模块和现有语音生命周期回归，保存结果与经验。

### Task 2: Existing pet feedback

**Files:** 新增 `DyberPet/assistant/interaction_sync.py`、`tests/test_assistant_interaction_sync.py`；修改 `DyberPet/DyberPet.py`。

- [x] 回归验证状态动作与真实宿主方法：去重、角色绑定、无声/解锁判断和用户交互优先；先观察缺口。
- [x] 接入 interaction_changed，只在听/想状态进入时响应；说话复用既有通道，idle 不停止当前用户动作。
- [x] 验证相关原生动作/语音桥接用例；不编辑 ui.py，由根代理加信号。

### Task 3: Voice session and real UI integration

**Files:** 新增 `DyberPet/assistant/voice_session.py`、`tests/test_assistant_voice_session_qt.py`；修改 `DyberPet/assistant/ui.py`、`run_DyberPet.py`。

- [x] 写真实 Qt 两轮 listen→HTTP chat→speech→listen，以及三阶段打断、结束/关闭、配置失效、草稿/附件保留、无重播、失败和会话边界的失败回归。
- [x] 实现 VoiceConversation、三个控件和中文阶段显示；提取已有聊天入口，并在清理后推进。
- [x] 检查打包助手能构造新控件且语音默认未启动；复用既有 smoke，不添加独立 CI 工作流。
- [x] 完成真实窗口截图，三套完整回归与一次独立整批审阅，修复有证据的主要缺陷。

### Task 4: Deliver and record

- [x] 更新用户指南、README、开发经验和验证记录；补记上一批外部验收完成状态。
- [ ] 一批推送原分支并更新 PR，核验本批精确 SHA CI 与新 Windows 候选包。

## 执行记录

- 初始：2026-11-18，工作区干净，沿当前 feature checkout 实施，不再新开产品方向或诊断子项目。

- 实施完成：识别器 33 项、原生反馈 16 项、Qt 会话 15 项；失败回归覆盖流启动清理、取消竞态、阶段间恢复和滚动时停止入口。一次独立整批审阅无待修缺陷，另 8 个 Qt/HTTP 边界检查通过。两张真实窗口截图已更新；最终完整矩阵及发布身份见验证记录与 PR。
- 首次远端：`e97ec6c` 的 Windows 三个作业发现新增 Qt 语音测试等待问题。已有门禁已实际执行并定位失败；测试侧 GIL 调度与 ready 接收边界经确定性对照后修正，保留全部产品代码与超时/断言。修复后的精确 SHA 再验证原门禁；详细证据见验证记录。
- 响应取消补齐：`270e40c` 的 Windows 20 轮与末尾 ready 已通过，仍有同一旧 chat 退出问题。沿 UI/token/socket 核对并补充“服务保持连接、OS shutdown 不唤醒”的真实 HTTP 三种失败回归，在缓冲层下增加取消轮询，保留原解析与时限；4 个新增合约覆盖取消、碎片、chunk 与超时。实现后执行定向审阅、三套完整回归及原 Windows 门禁，不另起产品方向。
