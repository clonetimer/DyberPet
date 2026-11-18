# Voice Controls and Complete Playback Implementation Plan

> **For agentic workers:** 用户已授权整批连续执行；独立设备与播放组件并行，协调者负责共享 UI/配置/捕获接入与一次整批审阅，不逐阶段请求批准。

**Goal:** 用户能选对麦克风，为角色选择系统音色/语速，并听完已成功生成的长回复且随时停止。

**Architecture:** 保留现有单 worker/VoiceConversation 编排；纯元数据设备目录与独立完整 TTS 播放组件供所有入口共用，Qt 设置控件不触碰原生驱动。

**Tech Stack:** Python 3.9+ / PySide6 6.5.2+ / 已有可选 sounddevice、Vosk、pyttsx3；无新依赖。

**Spec:** `docs/superpowers/specs/2026-11-18-voice-controls-design.md`

## Global Constraints

- 基线 `6b9bcbc`，同一 feature checkout / PR #99；上一批完整回归与远端全绿已核验，不重复基线。
- 设备保存 name≤256 / host_api≤128；音色 ID≤512；语速 100–230、默认170；最多100个角色；配置总16KiB。
- 回复≤2000字符，段≤500字符，播放总时限300秒；一次引擎/worker/ready/完成。
- 枚举不录音/不发声/不加载 Vosk；无自动开麦、无私有 PortAudio 重初始化、无跨线程驱动调用。
- 失败和停止不冒充完整播放；下一次监听只能在最终成功且旧 worker 清理后开始。

## Review Focus

- 已保存索引重新编号、同名同 host API、多种 host API 同名设备；唯一精确匹配或明确失败。
- TTS 属性设置通过 error 事件失败，以及上段 finished 在下一段到达，不能提前完成或偷偷使用默认音色。
- 音频设置 A→B→A、角色切换和刷新迟到结果，旧音频/进度不能复活。
- 老配置无新增字段、损坏新字段、保存失败与缺失设备，都保留正确选择并不给错误默认值。
- 长回复第二段失败/取消、全部段末尾刚好停止、总超时，不能开启下一轮麦克风。

## Pre-flight

- Task1 → Task3：voice_devices 的三种 frozen元数据与 resolve_microphone(selection, sd)；None 为系统默认，不查询设备。
- Task2 → Task3：speech 的可选 voice_id、rate、on_progress(completed,total)，公开 voice.py 继续导出同名函数；错误类从 voice_errors 统一导出。
- 文件所有权：Task1 只改 voice_devices.py 与其测试；Task2 只改 speech.py、voice_errors.py、其测试及必要的旧 TTS 驱动替身；协调者改 voice.py、voice_turn.py、UI/设置/会话、共享文档。

### Task 1: Device and installed-voice selection

**Files:** 新增 `DyberPet/assistant/voice_devices.py`、`tests/test_assistant_voice_devices.py`。

**Interfaces:** 使用 Spec 中确切 dataclass 与函数签名，元数据不得持有原生引擎/设备对象。

- [x] 写失败回归：只列输入设备、同名不同 API、重新编号、缺失/歧义拒绝、默认不枚举、声线元数据、两侧独立失败与取消后不初始化另一侧。
- [x] 实现被动目录与使用时精确解析；所有 TTS 生命周期在调用 worker 内完成。
- [x] 运行 `python -m unittest discover -s tests -p 'test_assistant_voice_devices.py' -v`，全部通过，记录 API 边界与经验。

### Task 2: Complete, interruptible speech

**Files:** 新增 `DyberPet/assistant/speech.py`、`DyberPet/assistant/voice_errors.py`、`tests/test_assistant_speech_output.py`；必要时更新旧 TTS 设备替身。

**Interfaces:** Spec 的 speak_interruptible/speak_once/split_speech_text；原 voice.py 的兼容导出由协调者接入。

- [x] 先复现 500 字符后丢失；覆盖 2000 字符全文、每段≤500、保留标点顺序；超过上限明确失败而非截断。
- [x] 覆盖选定音色/语速、音色消失、属性 error、命名回调、单次 ready、段进度、第二段取消/失败、总超时和清理。
- [x] 实现单引擎顺序分段；每段独立身份、整条一个期限；驱动错误由主循环处理。
- [x] 运行新播放测试及既有语音生命周期/人格语音测试，断言与停止策略保持严格。

### Task 3: Settings, all entry points and real Qt integration

**Files:** 新增 `DyberPet/assistant/audio_settings.py`、`tests/test_assistant_audio_settings_qt.py`；修改 preferences.py、voice.py、voice_turn.py、voice_session.py、ui.py、相关设置/捕获/会话测试与 packaged smoke。

- [x] 设置回归先证明旧 schema 默认兼容、保存/加载音频字段、无效字段拒绝、未知数据不落盘。
- [x] 三个捕获入口接入选定设备；保留停止后丢弃/手动听写收尾各自语义和关闭生命周期。
- [x] Qt 回归先验证无自动目录/录音、刷新与已保存项、当前音色试听、角色恢复、配置变化取消、迟到进度拒绝、全部入口传参。
- [x] 接入紧凑可展开设置区、角色配置、一次刷新 worker、同一试听/播放链和分段进度；继续使用固定语音控制条。
- [x] 一条真实 Qt + HTTP + 生产分段播放 + 受控音频驱动流程，确认第二段完成前不开麦及取消/错误不接续。
- [x] 定向回归通过后做真实窗口截图、一次整批审阅与三套完整套件。

### Task 4: Record and deliver

- [x] 更新使用说明、README、开发经验和验证记录；落实上一批已完成交付状态。
- **发布验收：** 一批提交原分支并更新 PR；核验本批 head 的5个远端工作流与新 Windows 包，保留 Draft。精确 SHA、远端结果与产物由 [PR #99](https://github.com/clonetimer/DyberPet/pull/99) 本批验收段持续记录，不为写入自指提交再生成文档提交。

## 执行记录

- 2026-11-18：工作区干净，基线/PR head 均为6b9bcbc，上一批5工作流17作业成功。用户已要求持续整批推进，沿语音主线实施本批，省略重复审批。
- 选择：系统音色/语速按角色保存，麦克风全局；名字+API仅为当前库可用身份匹配，不声称硬件永久UID或完整热插拔能力。
- Task1 完成：34 项目录/解析回归通过；发现坏元数据可能隐藏同名设备，先失败后禁止从部分目录证明唯一匹配。经验43已记录。
- Task3 检查点：设置持久化13项、真实Qt设置11项通过；播放参数测试发现宿主同名on_progress关键字截获，绑定到任务后通过。经验44已记录；实际捕获和生产分段播放整合仍在执行。
- 分工调整：目录实现者继续负责voice.py的识别函数、voice_turn.py与新设备选择捕获测试；协调者等其完成后统一替换旧TTS导出，避免同文件并发修改。
- Task2/3 整合：实际识别入口17项、既有一句话捕获33项通过；完整播放27项加既有生命周期/人格共72项通过。Qt设置13项、会话19项通过；两张实际界面截图及800×600可见性已核验。
- 一次整批独立审阅发现纯空白段无回调、普通自动朗读未撤销两个实际缺陷；均先复现再修复，分别记录经验48/49。首个全量Python3.9原生崩溃单独追踪，完整门禁在修正后执行，不用专项绿灯代替。
- 最终本地门禁：两个审阅问题均独立复核关闭；Qt夹具明确GUI线程销毁后，原48项与相同单次后台GC压力各通过。三套完整964项均959通过、5既有环境跳过；22个Python文件的3.9编译及diff检查通过。详细证据与限制见 [验证记录](../../verification/2026-11-18-voice-controls.md)。
