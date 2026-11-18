# 本机试用与诊断设计

## 目标与决定

接续 PR #99 的 `54c913b`。用户要求记录经验并持续推进；本轮把已经可用的模型、连续识别和朗读接入可直接操作的试用窗口，让真实用户能看到实际结果并导出问题证据。继续使用 PySide6、既有单 worker/取消机制及 Python 3.9+，不新增运行依赖。

实施者比较了仅写人工验收表、独立命令行跑分、程序内试用三种方式，选择程序内试用：它复用用户正在运行的模型和声卡链路，能够直接显示结果，也不会要求非程序员另开终端。用户已要求直接推进，具体实现选择由实施者负责。

## 用户行为

- 新增“试用与诊断”非模态窗口；打开窗口只展示本窗口内存中的最近记录，不启动模型或音频。
- “试聊当前模型”向已配置模型发送固定中文问候请求，流式显示在独立试用区。复用本地 HTTP、取消、响应上限；不加入普通历史，不携带记忆、附件或 PPL 快照，不触发自动朗读，保留正在编辑的问题与上一条聊天回复。
- “试听示例”通过现有 TTS 播放固定短句；“开始连续监听”复用当前识别入口，最终文字仍回到输入框由用户检查。停止按钮针对当前操作生效。
- 展示最近 30 次操作的结果、首段/就绪/停止时序、字符数及桌宠进程 CPU/内存采样。CPU 不包括独立模型服务；内存是采样最大值，不宣称真实峰值。GPU、FPS 不测量。
- 人工反馈使用三组选项：模型回复、识别文字、是否听到朗读；值为未检查/符合预期/发现问题，不自动从程序成功推定。
- 报告可预览后通过保存对话框导出 JSON；默认只在内存保存，不跨程序重启恢复记录。同一助手对象关闭重开可保留匿名记录以便排查停止，用户可显式清空。拒绝覆盖已有文件，导出失败不影响正在执行的语音/聊天。

## 证据与隐私

记录只接受固定枚举、布尔值和有限数值；不接受提示词、回复、转写、错误原文、角色名、原始模型 ID、URL、路径、设备名或主机名。固定例句的模型回复也不进入报告。

报告包含 schema_version=1、运行环境、最近 observations、人工 feedback 与固定范围说明。环境只含系统/架构/Python/Qt/PySide 版本、源码/冻结模式和经过白名单校验的构建元数据。已有 BUILD_INFO.json 的 source_commit 标为 checkout_commit；它可能是 PR 合并测试提交，不能冒充源分支 SHA。缺失/损坏元数据明确标记；运行时不执行 git、shell 或网络查询。

每次真实 `_submit` 接受任务后才建立记录，完成在 `_job_finished` 清理字段前结算一次。只有被现有身份/代际保护接受的回调才记入就绪、正文和成功。停止请求与识别返回文字分别记录；缺少 ready 事件只表示“未观察到就绪”。取消后的迟到成功不能恢复成功状态。无成功、错误或取消证据的线程结束记为 interrupted。

修复已观察到的 TTS 语义问题：保留 finished-utterance 的 completed 布尔值；驱动报告未完成且用户未停止时报告失败，不能把“循环退出”写成朗读完成。即使驱动报告完成，是否实际听到仍由人工反馈表达。

## 接口边界

`trial_records.py` 提供 `TrialRecorder(capacity=30, *, clock=None, sampler=None, environment=None)`；`begin(kind)->int`、`text(run_id, count)`、`ready(run_id)`、`request_stop(run_id, reason="user")`、`observe(run_id, *, result_chars=None, model_count=None, recognition_ready=None, tts_ready=None, engine_completed=None)`、`fail(run_id, code)`、`sample(run_id)`、`finish(run_id, outcome)`、`set_feedback(key, value)`、`reset_feedback()`、`clear()`、`snapshot()->dict`。kind 包括 chat/model_probe/plan/listen/speech/models/voice_check/other；outcome 为 running/completed/cancelled/failed/interrupted。记录 ID 只在当前窗口递增。已经结束或未知 ID 的迟到事件无效。

snapshot 结构为 `{schema_version, environment, observations, feedback, limitations}`。每项 observation 包含 `id, kind, outcome, elapsed_ms, first_text_ms, ready_ms, stop_requested_ms, stop_settled_ms, stop_reason, displayed_chars, result_chars, model_count, recognition_ready, tts_ready, engine_completed, error_code, cpu_seconds, cpu_percent_one_core, rss_max_bytes, sample_count`；未知数值/布尔值用 null。feedback 键 model_reply/recognition/speech，值 not_checked/satisfied/problem。

stop_reason 固定为 user/scope_changed/window_closed/configuration_changed；stop_settled_ms 是请求停止到 worker 结束的时长。error_code 保留 invalid_endpoint/connection/timeout/http/redirect/response/no_models/service，并增加 voice_unavailable/internal_error/invalid_result，未知错误归 internal_error。clear 在运行中拒绝，清空后 ID 继续递增，反馈同时清空。

同模块提供 `sample_process_usage()->dict`（cpu_seconds/rss_bytes）、`runtime_environment()->dict`、`export_report(path, report)->None`。Linux 使用 /proc/self/statm 与页大小；Windows 用 GetProcessMemoryInfo；其他/失败返回缺失内存值。采样最多每秒一次，开始/结束强制采样；采样异常不能终止主任务。JSON 上限 64 KiB，导出必须重建白名单字段，不信任任意输入字典。

`trial_dialog.py` 提供 `TrialDialog(provider, parent=None)`，provider 无参数返回上述 snapshot。信号 model_test_requested/speech_test_requested/listen_requested/stop_requested/clear_requested 与 feedback_changed(str,str)。方法 `set_busy(busy, can_stop=False)`、`set_probe_text(text)`、`clear_probe()`、`refresh_report()`。独立试聊文字最多显示 4000 字符；用纯文本控件，报告预览与导出包含同一快照。只在窗口可见时刷新，关闭时停止定时器。

## 验证范围

用真实 Qt worker 验证试聊隔离、停止/关闭/角色和配置切换、报告脱敏与不影响音频控制；标准库模块验证白名单、边界、采样与拒绝覆盖；受控 TTS 驱动验证 completed=False。完整套件在 Python 3.12/Qt 6.8 与 Python 3.11/Qt 6.5 执行，旧 Python 协议/记录测试及远端矩阵补足最低版本。交付前核验新 SHA 的工作流和候选包。

本轮交付的是实际设备可运行的试用和证据工具，不自动宣称真实模型质量、听感、识别准确度或长时性能验收通过。
