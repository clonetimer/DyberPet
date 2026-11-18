# 语音设备、角色音色与完整朗读

## 主线与目标

接续已验收的 `6b9bcbc` / Draft PR #99。用户要求记录经验并整批持续推进；本批沿 P2 双向语音日常使用主线补齐三个现有缺口：麦克风只能使用默认设备、系统音色和语速不可选、成功回复被静默截到前 500 字符。沿用现有 PySide6、Vosk、sounddevice 与 pyttsx3，不更换桌宠引擎或增加云端语音服务。

## 实施选择

实施者比较了三个方向：立即引入全双工/回声消除需要新的音频架构和实机证据；并行生成与 TTS 会改变已验证的单 worker 编排；本批选择设备与角色音色设置、完整回复分段播放，可以直接覆盖现有全部语音入口并保留可控停止。该选择由实施者在用户已授权连续执行的范围内作出，不声称用户逐项选择过参数。

## 用户行为

- 新增紧凑的“麦克风与朗读”设置区，可展开选择输入设备、当前角色的系统音色与语速（100–230，默认 170），默认仍为系统设备/音色。
- “刷新设备与音色”只在点击后查询设备和初始化系统 TTS 读取音色；不录音、不播放、不加载 Vosk。分别展示输入设备和音色的可用结果，一侧失败不隐藏另一侧。
- 音色试听复用现有受控播放，并提供可见的停止入口。试听、手动朗读、自动朗读、轮流对话使用同一音色与语速；听写、兼容单次识别、轮流对话使用同一麦克风选择。
- 输入设备设置全局保存；音色与语速按角色保存，仍由“保存助手设置”落盘，切换角色恢复本角色设置。旧 schema v1 配置没有新字段时使用原默认行为。
- 保存的设备或音色暂不可用时仍保留选择并提示重新选择；实际使用会重新验证，不能悄悄回退到别的麦克风或音色。
- 回复最多 2000 字符，与现有聊天成功回复上限一致；按自然标点分成不超过 500 字符的段落，完整排队并逐段确认完成，不再静默截断。分段保留原文；纯空白段不交给会忽略它且不产生完成事件的 TTS，UI 仅统计可播报段，停止取消未播出的所有段落。
- 单次朗读保持一个引擎、一个 worker、一次 ready/finished 生命周期和一个总时限，最长 300 秒；超过上限明确失败，不把已播出的前缀记为整条播放完成。语音会话原 10 分钟/20 轮边界继续生效。

## 设备与驱动边界

sounddevice 没有公开的跨平台持久设备 UID。本批保存精确设备名与 host API 名，每次捕获前从当前设备列表唯一匹配到索引；缺失/重复匹配失败，不持久化索引，也不使用模糊名称匹配。默认选择仍交给系统。刷新仅反映库当前可见列表，不承诺自动发现所有 USB 热插拔；列表未更新时提示重启，禁止私下终止/重新初始化 PortAudio。

系统音色保存 pyttsx3 voice ID。使用前从引擎当前 voices 校验；设置属性和播放队列的错误通过 error 事件记录，在 worker 主循环处理，不能在回调抛异常后期待其传播。每段使用唯一 utterance name，忽略上一段或上一场迟到的结束事件。只在所有段完成后返回 True；取消返回 False；驱动错误、未完成、超时均明确失败。

所有查询、加载、录音与 TTS 保持 worker 所有权。只返回不可变设备/音色元数据到 GUI，不跨线程传递引擎。配置变化撤销在途音频和排队后继，旧 ready/progress/result 不得恢复旧会话。设备名/voice ID 只保存于本机设置，不进入诊断报告白名单。

## 接口

- `voice_devices.py`: frozen `MicrophoneInfo(name, host_api, index)`、`SystemVoiceInfo(id, name, languages)`、`AudioOptions(microphones, voices, microphone_message, voice_message)`；`inspect_audio_options(stop_event=None) -> AudioOptions | None`；`resolve_microphone(selection, sounddevice_module) -> int | None`，selection 为 None 或 `{name: str, host_api: str}`。
- `voice_errors.py`: 移动既有 VoiceUnavailable 定义，`voice.py` 继续兼容导出同一类型。
- `speech.py`: `split_speech_text(text: str) -> tuple[str, ...]`；`speak_interruptible(text, stop_event, *, rate=170, voice_id="", on_ready=None, on_progress=None, max_seconds=300.0) -> bool`，progress 仅 `(completed_chunks, total_chunks)`；`speak_once` 作为兼容入口复用同一完整播放路径。
- `voice.py` 三个识别入口（包括 `voice_turn.py` 的 listen）增加可选 `microphone=None` 关键字，捕获前解析实际设备；默认行为不主动枚举设备。
- `audio_settings.py`: 独立轻量 Qt 设置控件，只管理目录、选择、摘要与刷新/试听/停止信号，不初始化驱动。宿主集中调度 worker 与保存。
- preferences 增加 `microphone=None`、`voice_profiles={}`；后者映射角色到 `{voice_id: str, rate: int}`。设备名最多 256 字符、host API 最多 128、voice ID 最多 512；最多 100 个角色；保留总 16 KiB 配置限制与未知字段剔除。

## 验证和交付

用真实捕获/播放循环配合设备边界替身验证重新编号、设备缺失/歧义、音色失效、属性错误、分段完整性、迟到回调、第二段取消/失败及总时限。Qt 检查设置持久化/角色恢复、所有入口参数传递、配置变化撤销、语音会话仅在最后一段完成和 worker 退出后重新监听；保持固定控制条可见。至少一条 Qt 测试贯穿真实播放实现与受控驱动，而非仅替换整个 speak 函数。

完成一次整批独立审阅、三套已有 Python/Qt 完整回归、实际窗口截图；沿原分支更新 PR，核验同一新 head 的 Windows 失败门禁和新候选包。不把受控驱动、系统音色目录或 headless smoke 当作物理音频质量证据。

## 参考

- [sounddevice 0.5.2 查询设备](https://python-sounddevice.readthedocs.io/en/0.5.2/api/checking-hardware.html)
- [pyttsx3 引擎属性、命名 utterance 与事件](https://pyttsx3.readthedocs.io/en/latest/engine.html)
- 实际 pyttsx3 2.99 driver/engine 实现用于核对队列错误与回调异常处理。
