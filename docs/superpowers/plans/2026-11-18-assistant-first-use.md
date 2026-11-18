# Assistant First Use Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成模型选择、连接诊断和语音条件提示，降低首次使用门槛。

**Architecture:** 保留当前 PySide6 窗口、工作线程与配置 schema；模型发现复用受限 HTTP，语音检查为无设备副作用的标准库模块。UI 绑定检查时的配置快照并丢弃过期结果。

**Tech Stack:** Python 3.9+、PySide6 6.5.2+、unittest、标准库 HTTP。

**Spec:** `docs/superpowers/specs/2026-11-18-assistant-first-use-design.md`

## Global Constraints

- Python 3.9+；保留 PySide6 6.5.2 兼容性；不增加运行时依赖。
- 仅 loopback HTTP，拒绝代理、重定向和非本地地址。
- 不自动打开麦克风、不自动发送识别文本、不自动下载模型、不启动外部服务。
- 保留既有角色隔离、工作区授权、文件逐步审批、取消与 Qt 生命周期。
- 每阶段更新 `docs/DEVELOPMENT_EXPERIENCE.md`，含改动、原因、踩坑和证据边界。

## Review Focus

- 编辑地址时旧检查仍返回：旧列表和旧错误不能覆盖新配置。
- 刷新返回多模型或不含手填 ID：保留用户选择，不擅自选择第一个。
- Vosk 缺失不应影响 TTS 状态；组件存在不等于麦克风/扬声器可用。
- 网络失败、无模型或配置缺失时保留新输入与审批附件。
- 检查/语音准备与窗口关闭并发：不遗留工作线程或强引用设备回调。

## Pre-flight

- Task 1 → Task 3: `list_local_models(base_url, *, cancel_token=None)` returns `list[str]`; errors remain `AssistantServiceError`, with stable `code` and `status_code`. `service_error_hint(error)` produces a bounded Chinese diagnostic without response-body contents.
- Task 2 → Task 3: `inspect_voice_readiness(model_dir)` returns frozen `VoiceReadiness(recognition_ready, recognition_message, tts_ready, tts_message)`; ready only means preliminary components/structure present.
- Task 1 and Task 2 own separate files and can proceed independently. Task 3 integrates their contracts. All changes stay in the fresh isolated checkout of the existing feature branch.

### Task 1: Model discovery and diagnostics

**Files:** Modify `DyberPet/assistant/persona.py`; create `DyberPet/assistant/service_diagnostics.py`, `tests/test_assistant_model_discovery.py`.

**Interfaces:** Add optional cancellation to existing discovery; preserve old callers. Add `AssistantServiceError.code` with backward-compatible default and `service_error_hint(error: AssistantServiceError) -> str`.

- [x] Write HTTP behavior regressions: exact GET path/no request body, valid deduplicated bounded IDs, invalid response, no models, refused connection, cancellation and local-only guards.
- [x] Run the new tests before implementation and confirm missing behavior.
- [x] Implement structured failure categories and user-facing diagnostics; keep transport bounds.
- [x] Run `python -m unittest discover -s tests -p 'test_assistant_model_discovery.py' -v`; expected all pass.
- [x] Record changed behavior and pitfalls in development experience during integration.

### Task 2: Passive voice readiness

**Files:** Create `DyberPet/assistant/voice_readiness.py`, `tests/test_assistant_voice_readiness.py`.

**Interfaces:** Frozen `VoiceReadiness` with `recognition_ready: bool`, `recognition_message: str`, `tts_ready: bool`, `tts_message: str`; `inspect_voice_readiness(model_dir: str) -> VoiceReadiness`.

- [x] Write behavior regressions for absent components, empty/nonexistent/outer directory, current/legacy layout, separate TTS result, and no driver import/device activity.
- [x] Run tests before implementation and confirm missing behavior.
- [x] Implement bounded standard-library module discovery and path inspection; contain path and import metadata errors.
- [x] Run `python -m unittest discover -s tests -p 'test_assistant_voice_readiness.py' -v`; expected all pass.
- [x] Record changed behavior and pitfalls in development experience during integration.

### Task 3: First-use UI and lifecycle integration

**Files:** Modify `DyberPet/assistant/ui.py`; create `tests/test_assistant_setup_qt.py`; update README and assistant docs.

**Interfaces:** Editable `model_selector` QComboBox with `llm_model` pointing to its QLineEdit for compatibility; `detect_button`, `model_status`, `voice_status`, `tts_status`, `voice_check_button`. Existing configuration read/write remains string-based.

- [x] Write Qt regressions for no automatic network, populated editable dropdown, selection preservation, stale address result/error, repeated check exclusion, passive voice checks, input retained for missing config, and close/cancellation.
- [x] Run tests before implementation and confirm missing behavior.
- [x] Implement explicit discovery with cancellation, endpoint snapshot guard, separate status labels, safe error formatting and local preparation hints.
- [x] Run `python -m unittest discover -s tests -p 'test_assistant_*qt.py' -v`; expected all pass.
- [x] Update guide/README/current status and stage experience; capture real Qt screenshot.

### Task 4: Integrated delivery

- [x] Run `QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v`; read failure/skip details.
- [x] Check Python 3.9 grammar, compile, diff and packaging inclusion of new modules.
- [x] Independent review of the complete batch; fix material findings with regression evidence.
- 发布后门禁：推送到既有 PR #99，使用已核对的分支 SHA；核验新 SHA 的 workflows、jobs 和 Windows artifact，结果写入 PR 的本批 Validation。
- 发布后报告：在 PR 记录新提交验证、候选包元数据与真实设备边界，向用户汇报已完成阶段和链接。
