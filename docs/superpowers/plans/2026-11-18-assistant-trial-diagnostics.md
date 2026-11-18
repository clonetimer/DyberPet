# Assistant Trial Diagnostics Implementation Plan

> **For agentic workers:** Execute the following independent components in parallel, integrate through the fixed interfaces, then review the whole batch once. The user has requested continuous execution without intermediate approvals.

**Goal:** 让用户在实际桌宠里试聊、试听，查看并导出准确且不含聊天正文的运行诊断。

**Architecture:** 复用现有单 worker 与取消/身份保护；独立标准库记录器接收数值和枚举，独立 Qt 窗口展示/导出，主助手只负责已接受事件的接线。

**Tech Stack:** Python 3.9+ / PySide6 6.5.2+ / unittest / 标准库；无新增依赖。

**Spec:** `docs/superpowers/specs/2026-11-18-assistant-trial-diagnostics-design.md`

## Global Constraints

- 保留角色隔离、逐项文件审批、用户输入/附件、原有历史与配置 schema。
- 30 条内存记录、64 KiB JSON、4000 字符试聊预览；不记录敏感正文、URL、ID、路径或错误原文。
- 不自动启动模型/音频；实际成功与人工质量评价分别报告。
- 构建 checkout SHA 与 PR head 不混称；未获取的 GPU/FPS 数据不填零。
- 每阶段记录改动、原因、踩坑；以真实失败到通过和当前 SHA CI 为依据。

## Review Focus

- 取消后已排队的成功、ready 与错误不能改写终态或新操作。
- 停止监听可以返回有效转写，不能等同“识别失败”。
- 试聊/试听不能覆盖聊天输入、附件、上一回复或自动朗读。
- 导出失败与关闭诊断窗口不能终止主助手任务；窗口定时器和回调不泄漏。
- 非白名单字段、非有限数值、任意元数据及错误字符串不得进入报告。

## Pre-flight

- Task 1 → Task 3/4: recorder 与 snapshot 的精确签名、字段、状态枚举见 spec；接口由 Task 1 负责，使用方不得静默扩展。
- Task 2 → Task 4: TTS 仍返回 True/False 或 VoiceUnavailable；False 只表示用户停止，驱动失败抛异常。
- Task 3 → Task 4: TrialDialog 的信号与方法见 spec；不直接引用主助手、音频模块或模型客户端。
- 工作区为既有独立 feature checkout，基线 `54c913b`，开始时干净；保留原 PR #99。

### Task 1: Bounded records, metrics and export

**Files:** create `DyberPet/assistant/trial_records.py`, `tests/test_assistant_trial_records.py`.

- [x] 先写行为回归并观察失败：终态幂等/迟到拒绝、时序算术、30 条淘汰、有效转写与停止并存、资源失败降级、元数据与导出白名单、拒绝覆盖。
- [x] 实现 spec 中 TrialRecorder、sample_process_usage、runtime_environment、export_report。
- [x] 21 项在 Python 3.9.25 / 3.11.18 / 3.12.14 通过；另复现并修复 Windows ctypes 类型缓存增长。

### Task 2: Honest TTS completion

**Files:** modify `DyberPet/assistant/voice.py`, `tests/test_assistant_voice_lifecycle.py`.

- [x] 用受控引擎 completed=False 且未请求停止，复现原实现错误返回 True；含停止/完成先后竞态，共 5 个预期失败。
- [x] 保存完成布尔值；驱动未完成则抛 VoiceUnavailable，用户停止保留 False，清理仍在 worker 中完成。
- [x] 跑语音生命周期与既有 persona/voice/动作回归：完成元数据修复后两套环境各 51 项通过。

### Task 3: Trial window

**Files:** create `DyberPet/assistant/trial_dialog.py`, `tests/test_assistant_trial_dialog_qt.py`.

- [x] 先写真实 Qt 回归：打开/刷新无模型音频副作用、按钮/信号、忙碌与停止、人工反馈、纯文本预览、导出取消/失败/已有文件、关闭停表。
- [x] 实现独立非模态窗口、试聊预览、记录说明、人工反馈、报告预览与显式导出。
- [x] 两个 Qt 版本各 19 项通过。

### Task 4: Integrate actual operations

**Files:** modify `DyberPet/assistant/ui.py`; create `tests/test_assistant_trial_qt.py`.

- [x] 写并运行集成失败回归：真实 worker 的试聊无记忆/附件/PPL与历史写入、取消重试、设备就绪/转写、错误脱敏、角色和配置失效、后台记录与导出隔离。
- [x] `_submit` 分配记录 ID，接受回调时记录，`_job_finished` 清理前结算；控制错误仅存类别。
- [x] 加试聊、试听、统一停止及窗口入口；复用真实客户端与音频任务，不重写传输。
- [x] 16 项集成回归通过；独立审阅指出的队列成功覆盖停止、未观测完成值和前景提示均先失败再修复。

### Task 5: Deliver one integrated batch

- [x] 更新使用/Windows 指南，修正过时的四秒 UI 说明；归档经验与真实截图/验证记录。
- [x] 将 Qt 6.8 全量崩溃缩为固定 61 项序列，证实测试 MagicMock 保留窗口到后台 GC；只修正已证实的四个函数替身，同序列与释放线程追踪均通过。
- [x] 两套完整回归各 797 项、792 通过、5 环境跳过、0 失败；实际 Python 3.9 的 72 项影响范围回归、9 文件语法/编译与 diff 检查通过。一次独立审阅的具体问题均先复现后修复。
- [ ] 推送原分支，核验当前 SHA CI/候选包，更新 PR Validation；不把旧批次绿色结果移作本批证据。
