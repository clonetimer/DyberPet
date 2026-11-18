# 可停止生成与活动反馈：本批验证记录

日期：2026-11-18。开发基线：`9945a311cdfe60532e8d136c33cb4103217cd2ba`。本记录随本批代码提交保存；远端运行 ID、提交 SHA 与产物元数据在 [Draft PR #99](https://github.com/clonetimer/DyberPet/pull/99) 的 Validation 和 Latest Windows candidate 部分登记。

## 交付范围

- 聊天与任务草案均可停止，取消 token 贯穿可选 PPL 状态获取和本地模型 HTTP。
- 取消立即阻止迟到结果提交，工作线程退出后才恢复按钮；聊天片段保留且标注未完成，不写完整历史、不自动朗读，取消草案不创建审阅或文件。
- 独立活动状态、经过时间、首段等待与已显示字符；准备、实际设备 ready、停止中和终态区分。
- 麦克风/TTS 准备阶段停止、同角色旧 ready 过滤、朗读气泡偏好及错误来源隔离。
- 开发经验、用户说明、设计/执行记录及实际 Qt 离屏截图同步更新。

## 本地最终结果

运行环境：Linux、Python **3.12.14**、PySide6 **6.8.3**、PyOpenGL **3.1.10**。Qt 使用 `offscreen`；依赖位于临时测试运行时，不向仓库增加生产依赖。

```bash
QT_QPA_PLATFORM=offscreen PYTHONFAULTHANDLER=1 \
PYTHONPATH=/tmp/dyberpet-qt-runtime \
python -m unittest discover -s tests -v
```

最终结果：**673 tests / 668 passed / 5 skipped / 0 failures**，29.799 秒，进程退出码 0。

| 关键覆盖 | 最终套件中的范围 |
| --- | --- |
| Qt 控件与事件循环 | 74 项；包含本批 16 项活动/取消用例、既有助手和任务审阅回归 |
| 可取消 HTTP | 11 项真实回环合约：请求前、响应头、SSE/JSON 正文、注册竞态、解析期间取消、PPL 链路、重试和网络边界 |
| 结构化草案 HTTP | 既有 9 项真实回环合约继续通过 |
| Qt 与实际 HTTP 联动 | 一个用例分别运行聊天 SSE 与草案 JSON 两种真实连接；点击停止后服务端观察到断开，UI 恢复且无历史/草案发布 |
| 语音生命周期 | 新增 14 项受控驱动回归：加载/打开/初始化时停止、ready 时机和所属线程清理 |
| 原生桥接 | 6 项回归，包含助手气泡关闭后仍保留朗读状态及已解锁动作 |
| 语法和差异 | 10 个修改/新增 Python 文件通过 Python 3.9 grammar 解析；assistant compileall 与 git diff --check 通过 |

上述 HTTP 服务是协议 fixture，不是 LLM；受控语音驱动不是实机。Python 3.9 grammar 检查仅证明语法兼容，实际 Python 3.9/3.11 与 Windows Qt 6.5.2 结果由对应 CI 提供。

### 五个明确跳过项

1. `test_http_session_event_idempotency_and_sqlite_restart`：本地没有独立检出的 PPL 源码；远端有单独固定版本的真实 PPL 合约作业。
2. `test_actual_qt_interaction_worker_plays_then_resumes`：完整 Qt 桌面依赖不可用。
3. `test_real_live_pet_widget_receives_normalized_canvas`：完整 DyberPet GUI 依赖不可用。
4. `test_qt_mouse_jitter_stays_pat_no_worker_pause`：完整原生桌面 Qt 依赖不可用。
5. `test_qt_qualified_drag_starts_exactly_one_original_drag_interaction`：同上。

这些跳过未被算作通过，也未用上一批绿色 CI 自动补成本批结论。

## 审阅与实际发现的问题

1. **取消竞态：** 用户停止时成功信号可能已在 Qt 队列中；UI 立即设置本次取消标志，后续不保存、朗读或展示草案。新增回归先在旧实现缺少停止能力时失败，集成后通过。
2. **准备失败留在忙碌状态：** 独立审阅用损坏的真实 SQLite 复现，读取上下文抛错时没有 worker 却已启动计时并清空输入。现改为先读取并捕获 SQLite 错误，再启动活动；保留输入与附件。生成后的历史写入故障也保留完整回复和可见警告。
3. **无关错误丢失麦克风控制：** 手动文件操作报错会清空仍工作的音频停止事件。现在只有当前 worker 自身失败/结束能收尾其控件；回归验证无关错误后停止按钮仍有效。
4. **完整套件 native 崩溃：** 最初完整运行在后续 Qt 事件循环发生段错误，不能算通过。缩小到三项取消/语音测试与主线程 GC 后，native 栈定位到已关闭无父窗口的 QLabel 析构和父布局通知。仅将设备 ready 回调中的强窗口引用改为弱引用，同一复现通过；新增回归也证明保留设备回调不会继续保留已关闭窗口。未禁用 GC、未调整测试顺序、未更改 fixture 清理来取得最终通过。随后重新运行完整套件得到上面的最终结果。

独立审阅复核了准备失败、旁路错误和弱回调修复。保留的诊断日志不作为用户交付物；可复用结论已写入 [开发经验](../DEVELOPMENT_EXPERIENCE.md) 第 16–17 条。

## 界面证据与能力边界

[实际 Qt 截图](../images/assistant-activity.png) 为 1000×1050，使用合成演示文字和临时工作区。它证明控件和活动状态呈现，不证明真实模型生成速度。

取消会关闭客户端连接并拒绝结果，不能保证 LM Studio 后端立刻停止 GPU 推理，也不回滚已送达 PPL 的会话创建。每次 TCP 连接尝试使用最多 3 秒超时，DNS/多地址尝试不等于总过程 3 秒保证。音频驱动内部阻塞需返回后才能检查停止。

实机麦克风/TTS、真实本地模型质量和延迟、CPU/GPU/FPS、长时间运行与完整用户设备流程仍需独立验收。本批不合并、不发布，也没有增加 shell、任意路径或模型自动执行权限。

## 远端记录规则

本地验证完成后一次同步到既有分支。远端树必须与本地暂存树一致；分支更新使用原 head 租约。对应新 SHA 的助手 CI 与 Windows 构建完成后，在 PR 登记运行、作业和产物证据，避免为回填运行 ID 再提交一次并重复触发构建。
