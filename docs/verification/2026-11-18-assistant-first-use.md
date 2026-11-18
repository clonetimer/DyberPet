# 首次使用闭环验证记录

日期：2026-11-18。分支：`feat/ai-companion-runtime-20261117`，接续基线：`069d6d4cdaa42cc1faf4ad781574a539359fabb6`。本文件记录提交前的源代码与界面验证；新提交的 Actions 运行、完整 SHA 和候选包元数据在 [PR #99](https://github.com/clonetimer/DyberPet/pull/99) 的本批 Validation 中记录，不拿基线的绿色结果代替本批结果。

## 交付范围

- 模型列表直接进入可编辑下拉框；保留手填和刷新期间的新选择。
- 明确区分地址不合法、连接失败、超时、HTTP、坏响应和空列表；列表不代表已加载或支持聊天。
- 模型检查使用已有取消传输；修改地址、角色切换、关闭和主动取消拒绝迟到结果，并收敛设置标签。
- 识别组件/模型目录与朗读组件分别进行被动初检；不导入音频驱动或打开设备。源码与冻结包给出各自可执行的缺组件处理方式。
- 配置缺失和请求失败保留问题与附件，不覆盖用户新输入；原有配置 schema 兼容。
- 可滚动助手窗口，限制初始尺寸在屏幕可用区域内。

## 环境与执行

Linux；分别使用 Python 3.12.14 / PySide6 6.8.3 与 Python 3.11.18 / PySide6 6.5.2；两者均安装 PyOpenGL 3.1.10、Pillow 12.3.0。设置 `QT_QPA_PLATFORM=offscreen`，各次完整回归使用独立的 `XDG_CONFIG_HOME`，避免并行进程共享持久化窗口设置。

```bash
QT_QPA_PLATFORM=offscreen python -m unittest discover -s tests -v
```

基线在改动前重跑：**673 项、668 通过、5 环境跳过、0 失败，26.975 秒**。本批首次集成：**725 项、720 通过、5 环境跳过、0 失败，30.216 秒**。独立审阅后的修复增加 4 项测试；首批提交 `906f8f8` 前完整回归为 **729 项、724 通过、5 环境跳过、0 失败，32.355 秒**。该提交的远端矩阵仍暴露旧 Python 兼容和行走测试夹具问题，见下文，不能视为远端验收通过。

兼容修复增加 3 项测试；最终两套环境分别执行 **732 项、727 通过、5 环境跳过、0 失败**，Python 3.12 / Qt 6.8 用时 **33.161 秒**，Python 3.11 / Qt 6.5 用时 **32.747 秒**。完整套件包含 **92 项实际 Qt 测试**。

| 检查 | 结果与范围 |
| --- | --- |
| 最终完整回归 | 两套真实 Python/Qt 环境各 732 项，727 通过，5 环境跳过，0 失败；相对基线新增 59 项行为回归 |
| 模型发现与诊断 | 26 项；真实回环 HTTP 的 GET、取消、重定向、代理隔离、响应和 ID 上限、JSON/SSE 超时；中文错误提示 |
| 被动语音初检 | 15 项；两种 Vosk 结构、组件缺失/异常、无音频模块导入、冻结包恢复方式 |
| 首次使用 Qt | 18 项；真实 Qt worker、地址竞态、选择与输入保留、关闭重开、角色切换、PPL 错误不误导模型排查 |
| Python 3.9 语法与编译 | 8 个本批 Python 文件通过 AST 的 3.9 grammar 检查与 compile；不代替真实运行时验证 |
| 旧 Python 运行时 | 实际 Python 3.9.25 与 3.11.9 各通过 26 项发现/诊断测试及 51 项相关协议回归；包含失败到通过的对照 |
| 改动格式 | `git diff --check` 通过 |
| 打包包含关系 | Windows 与 Linux 现有构建都 collect `DyberPet.assistant` 子模块，新模块同时由 UI 静态导入；实际冻结 EXE 结果仍以本批 Actions 为准 |

### 5 个环境跳过

| 测试 | 原因 |
| --- | --- |
| `test_assistant_ppl_live.RealPPLCharacterTest.test_http_session_event_idempotency_and_sqlite_restart` | 未在本地 checkout 独立 PPL 工程；远端固定版本 PPL 作业另跑真实合约 |
| `test_native_gesture_runtime.NativeGestureTests.test_actual_qt_interaction_worker_plays_then_resumes` | 当前测试环境缺完整原主程序桌面依赖 |
| `test_native_sprite_canvas.LiveNativeCanvasTests.test_real_live_pet_widget_receives_normalized_canvas` | 当前测试环境缺完整原主程序桌面依赖 |
| `test_pet_pointer_gestures.PetPointerIntentTests.test_qt_mouse_jitter_stays_pat_no_worker_pause` | 原主程序依赖导入不可用；不是助手 Qt 套件被跳过 |
| `test_pet_pointer_gestures.PetPointerIntentTests.test_qt_qualified_drag_starts_exactly_one_original_drag_interaction` | 同上 |

## 审阅、复现与修复

独立审阅逐项阅读生产代码与新增测试，运行最初 52 项新增测试，并以 Qt 探针检查连接失败内容保留及关闭后的对象回收。未发现数据丢失或新增 worker 泄漏；指出三项实际体验问题，均在本批修复：

1. 冻结 EXE 缺组件仍推荐 pip：新增测试先失败，随后区分源码/便携包指引。
2. 关闭后重开、切换角色仍显示“正在检查”：模型与语音路径先复现失败，再统一收敛取消状态。
3. PPL 错误被提示启动 LM Studio / OpenAI：通过聊天前 PPL 请求路径复现连接和 404 两种错误，再改为公共服务诊断。

审阅原将后两项标为轻微问题；实施者将其作为首次使用状态准确性与旧服务兼容性问题一并修复。没有为本轮新增安装器、模型启动器、密钥管理或其他服务能力。未发现具体证据的系统文件操作永久阻塞不作为本批阻塞项；被动检查仍在线程中进行，关闭遵守既有等待线程规则。

## 首批 CI 失败与兼容修复

首批源码提交为 [`906f8f88afff68caeb5ab9689e7d793c5c18a36c`](https://github.com/clonetimer/DyberPet/commit/906f8f88afff68caeb5ab9689e7d793c5c18a36c)。[桌宠助手矩阵](https://github.com/clonetimer/DyberPet/actions/runs/44247073083)与[角色导入矩阵](https://github.com/clonetimer/DyberPet/actions/runs/44247073073)的失败日志指出三类问题，均先复现再修复：

1. 较旧 Python 3.11 / 3.9 的 `urlsplit` 能从 `http://[::1]unexpected:1234` 提取合法 hostname/port。新增原始 authority 校验，并保留模拟旧解析器结构的回归；实际 Python 3.11.9 上原实现失败、修复后通过。
2. Python 3.9 的 `socket.timeout` 尚非 `TimeoutError` 别名，JSON 与可取消传输将超时错误归为连接失败。实际 Python 3.9.25 重现后同时识别两类异常，并补充 SSE 响应头超时。
3. 原生行走的渲染顺序测试读取真实保存位置、依赖宿主屏幕，却无条件要求向左行走成功。固定屏幕与可行走位置，隔离整个窗口生命周期的设置读写，保留生产边界逻辑和全部原断言。Qt 6.5.2 上以保存的左边缘位置重现同一失败，修正后通过且外部设置不变；远端当时的实际几何值未记录，不能推定相同。

兼容修复后重新执行上述两套完整套件，而非只重跑失败项。对应新提交的完整 SHA、所有工作流结论、作业数量和候选包元数据记录在 PR Validation，明确与首批失败提交区分。

## 真实 Qt 布局证据

截图来自实际运行的 `PetAssistantDialog`，不是生成图或设计稿。使用无模型、无音频驱动的干净测试环境，没有填入虚构的模型回复或设备成功状态。

- [首次设置界面](../images/assistant-first-use.png)
- [滚动到底部后的操作区](../images/assistant-first-use-actions.png)

新增提示后，未滚动的原布局最低需要 977 逻辑像素；改为滚动内容后，窗口可保持 **900×760**，初始内容滚动范围 **337** 像素。执行实际缺组件检查后内容变长，滚动到 **375/375** 可完整访问底部操作。较小屏幕的可达性来自滚动容器，不是强行裁切布局。

## 证据边界

真实 LM Studio 模型加载、生成质量、首段延迟，真实麦克风、TTS 驱动与可听效果，CPU/GPU/FPS 和长期运行尚未在本地硬件验收。回环 HTTP 与离屏 Qt 证明协议、控件和生命周期；语音初检只证明组件可发现和目录标识存在。新 SHA 的 Windows/Linux 候选包必须核对实际 Actions 结果，不能根据静态包含规则宣称通过。
