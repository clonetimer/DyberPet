# 任务草案批次验证记录

日期：2026-11-18（北京时间）。开发基线 `541dae2bd417852bda1d48b1e6d19608c8cd6032`；工作分支 `feat/ai-companion-runtime-20261117`；更新既有 Draft [PR #99](https://github.com/clonetimer/DyberPet/pull/99)。

## 本地最终验证

运行环境：Linux、Python 3.12.14、PySide6 6.8.3、PyOpenGL 3.1.10，`QT_QPA_PLATFORM=offscreen`。这些是本地验证环境，没有改变项目的便携包依赖版本；Windows CI 继续使用仓库固定依赖。

| 检查 | 结果 | 边界 |
| --- | --- | --- |
| `python -m unittest discover -s tests -v` | 631 项：626 通过、5 跳过、0 失败，26.803 秒 | 包含真实临时文件系统、回环 HTTP 和 Qt 控件；耗时仅为该次测试运行时间，不是产品性能基准 |
| 新规划 HTTP 合约 | 9 项通过，已包含在完整测试内 | 本地 HTTP 测试服务，不是真实 LLM |
| Qt 助手与任务界面 | 58 项已包含在完整测试内 | 离屏控件、真实事件循环、QThread、Esc；无实机麦克风/TTS/GPU 测量 |
| Live2D 本地模块定向复验 | 24 项通过 | 最初 2 项因未安装已声明的 PyOpenGL 失败；补齐测试环境后定向和全套复验通过，未改 Live2D 产品代码 |
| Python 3.9 语法检查 | 10 个新增/修改 Python 文件通过 | `ast.parse(feature_version=(3, 9))`，不是 Python 3.9 运行时验证；实际版本矩阵以 CI 为准 |
| `compileall` / `git diff --check` | 通过 | 编译助手模块、空白检查 |

五项跳过：

- `test_http_session_event_idempotency_and_sqlite_restart`：本地未另行检出 PPL；CI 有固定版本真实合约作业。
- `test_actual_qt_interaction_worker_plays_then_resumes`：缺少完整桌面依赖。
- `test_real_live_pet_widget_receives_normalized_canvas`：缺少完整 DyberPet GUI 依赖。
- `test_qt_mouse_jitter_stays_pat_no_worker_pause` 与 `test_qt_qualified_drag_starts_exactly_one_original_drag_interaction`：当前环境未具备这两项所需的完整 Qt 桌宠依赖。

## 审查发现与修复证据

独立审查报告的三个重要问题均已用失败用例复现，再修复并包含在最终完整测试中：

1. **Esc 绕过关闭撤销。** 真实 Qt 按键会使父窗口隐藏但任务仍可审批；现将拒绝事件与关闭统一，覆盖已打开草案和正在运行的规划线程。
2. **外层模型 JSON 歧义。** 重复 `finish_reason`/`content`、非有限数值和畸形控制字段原可通过；现使用任务专用严格解码器和类型校验。
3. **旧语音部分文本污染状态。** 工作区重置后旧部分转写原仍可显示；现对全部 worker 进度、成功、错误做会话代次检查，并立即撤销监听状态。

其他已验证边界：两个工作区切换竞争回归；角色/目录切换时的旧确认；失败和取消保留先前文件；审计收尾警告不重试；双击只执行当前步骤；重复生成不累积父级隐藏任务窗口。修正“查看下一步”后的父窗口状态同步。

## 视觉证据

[审阅窗口截图](../images/approved-task-plan-review.png) 来自真实 Qt 控件，合成文本、临时目录。截图时第一步已创建、第二步待审批；随后关闭并清理临时目录。截图未使用模型生成，不构成模型质量或 Windows 桌面效果证明。

## 远端验证边界

本记录随代码一起提交，创建时尚无本批提交的 Actions 运行 ID。必须按最终完整 SHA 核验 Desktop assistant 和 Windows portable 的运行结论，再写入 PR 的验证结果；不得沿用开发经验文档中的旧绿色基线。真实模型成功率、首段/完整回复延迟、麦克风与 TTS 设备体验、CPU/GPU/FPS 和长时间资源占用仍需实机证据。
