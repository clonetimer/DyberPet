# Assistant Activity and Cancellation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 让用户可停止模型生成，并让桌宠助手准确显示准备、活动和停止状态。

**Architecture:** 保留 Qt 单工作线程，以线程安全取消 token 中断本地 HTTP，UI 丢弃取消后的回调。独立活动呈现与实际音频就绪信号连接，现有文件审批保持原有边界。

**Tech Stack:** Python 标准库、PySide6、现有 Vosk/pyttsx3 可选适配。

**Spec:** `docs/superpowers/specs/2026-11-18-assistant-activity-design.md`

## Global Constraints

- Python 3.9/3.11；Windows Qt 6.5.2；不新增生产依赖。
- 本地 HTTP 仍限制 loopback、禁用代理/重定向并维持已有响应上限。
- 取消不保存部分历史，不自动朗读，不打开取消草案的审阅或执行文件动作。
- 保留已显示片段、用户新输入和可重试附件；作用域改变时按既有规则清除。
- 不强杀线程；音频驱动仅由所属工作线程调用。
- 交付既有分支与 Draft PR；不合并、不发布。

## Review Focus

- 服务器未返回响应头或正文时停止，工作线程仍应能退出。
- 成功信号已排队后停止，仍不能持久化、朗读或展示草案。
- 停止后立即切换角色/关闭，旧信号不能覆盖新状态或阻止关闭。
- 麦克风/语音引擎初始化中停止，不应声称设备已工作或再启动播报。
- 气泡关闭、无可用动作、用户已有输入时，原控制偏好和文字应保留。

## Task 1: 可取消本地 HTTP

**Files:** 新增 `DyberPet/assistant/request_control.py` 和 `tests/test_assistant_request_control.py`；修改 `persona.py`、`task_planner.py`。

**Interfaces:** `CancellationToken.cancel()`、`.cancelled`、`.raise_if_cancelled()`；`RequestCancelled(RuntimeError)`；现有 `stream_local_chat`、`_json_request`、`generate_task_plan` 和 `PPLCharacterClient.state` 新增可选关键字 `cancel_token=None`。

- [x] 先写并运行真实本地服务器回归：头部/正文阻塞、取消前发送、取消后无 delta、大小/重定向边界。
- [x] 实现线程安全 token 与连接中断，兼容现有调用。
- [x] 运行 transport/planner/persona 相关测试，记录实际结果。

## Task 2: 语音准备与停止边界

**Files:** 修改 `DyberPet/assistant/voice.py`；新增 `tests/test_assistant_voice_lifecycle.py`。

**Interfaces:** `recognize_until_stopped(..., on_ready=None)` 在输入流成功打开且尚未停止后回调一次；初始化中停止返回空文本。`speak_interruptible` 提前及分阶段检查 stop event，停止返回 False。

- [x] 写假音频驱动行为回归，先确认旧实现无法满足准备/停止顺序。
- [x] 实现 ready 和初始化阶段停止保护；保持正常最终识别结果。
- [x] 运行新生命周期及既有语音测试。

## Task 3: UI 活动状态与停止生成

**Files:** 修改 `DyberPet/assistant/ui.py`、`DyberPet/DyberPet.py`；新增 `tests/test_assistant_activity_qt.py`，按需扩充原生桥接测试。

**Interfaces:** UI 增加 `stop_generation()`、停止按钮、活动标签和单调时钟指标；通过本次 stop event 身份绑定麦克风 ready，所有取消与作用域变化统一失效。

- [x] 写 Qt 行为回归：部分文字保留、不存历史、附件/输入保留、取消草案、晚到成功、关闭与重试。
- [x] 集成 token、状态、计时和音频 ready；保持普通提示与活动标签独立。
- [x] 修复朗读气泡开关，验证只调用已解锁动作。
- [x] 运行全部 Qt 及目标回归；生成实际离屏界面截图。

## Task 4: 经验、验证与交付

**Files:** 更新 `docs/DEVELOPMENT_EXPERIENCE.md`、`docs/pet_assistant.md`；新增本批验证记录。

- [x] 更新上一批已核验基线，记录取消层次、设备 ready、迟到信号和证据边界。
- [x] 独立审阅并解决具体问题，运行完整测试与差异检查。
- [ ] 一次同步本批代码到既有分支，核验精确提交的 CI 与 Windows 产物，并更新 PR 证据。

本文件在远端运行启动前随代码冻结；交付状态与运行 ID 见 PR #99 的最新 Validation 记录。
