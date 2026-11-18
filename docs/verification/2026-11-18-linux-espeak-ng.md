# Linux eSpeak NG 语音后端验证记录

日期：2026-11-18  
PR：[#99 feat(assistant): streaming AI, local memory, voice and approved actions](https://github.com/clonetimer/DyberPet/pull/99)  
当前分支最终 head：`d80fcc75eea81ad2697cbe38c1ed19e2d3a803d3`

## 实施范围

Linux 使用 `espeak-ng` 子进程播放语音；Windows/macOS 保留 pyttsx3 原生路径。Linux 子进程通过 UTF-8 stdin 接收文本，不使用 shell、不把文本拼入命令行参数；语速和角色音色通过参数传入。每个不超过 500 字符的段落独立启动、等待并回收子进程；用户停止或 300 秒总时限到达时终止当前进程，不再启动后续段落。

Linux 被动就绪检查同时检查 Python 端 pyttsx3 音色目录组件和系统 `espeak-ng` 命令。缺少命令时提示 Ubuntu/Debian 安装 `sudo apt install espeak-ng`。Linux 便携包不捆绑该系统命令。

## 自动化证据

### Linux eSpeak NG 专项

[Linux X11 acceptance and portable candidate](https://github.com/clonetimer/DyberPet/actions/runs/44275562721)，运行对应 PR 源 head `158db675efb3cb9de37a91b6e0ecbc932b58bae7`：

- 系统命令发现：`/usr/bin/espeak-ng`
- 运行版本：eSpeak NG 1.51，数据目录 `/usr/lib/x86_64-linux-gnu/espeak-ng-data`
- `test_assistant_linux_tts.py`：6/6 PASS，覆盖 UTF-8 分段、音色/语速参数、单次 ready、逐段进度、停止时终止子进程、非零退出和缺少命令。
- `test_assistant_linux_tts_readiness.py`：2/2 PASS，覆盖缺少/存在 eSpeak NG 时的就绪状态。
- 实际合成冒烟：通过 `espeak-ng --stdin -w` 生成非空 WAV 文件。
- Linux 源码 X11 Qt/助手/角色界面门禁：PASS。
- Linux 冻结 onedir EXE 从无关目录启动：PASS；日志包含 `DYBERPET_ASSISTANT_SMOKE_OK`、`DYBERPET_LINUX_GUI_SMOKE_OK`、`LINUX_FROZEN_X11_ACCEPTED` 和 `LINUX_USER_ART_POLICY_VERIFIED_NO_GENERATED_DEMOS`。

注意：WAV 冒烟证明本机 eSpeak NG 能完成合成，不证明真实声卡输出或用户实际听感。Xvfb 没有验证物理麦克风、扬声器、中文发音质量或长期音频设备稳定性。

### 跨平台助手回归

[Desktop pet assistant](https://github.com/clonetimer/DyberPet/actions/runs/44275562681)：

- Windows Python 3.9：PASS
- Windows Python 3.11：PASS
- Ubuntu 24.04 Python 3.9：PASS
- Ubuntu 24.04 Python 3.11：PASS
- Qt GUI smoke：PASS
- PPL real contract：PASS

[Windows portable candidate](https://github.com/clonetimer/DyberPet/actions/runs/44275562759)：

- 实际 Windows onedir EXE、资源目录和助手对话框自检：PASS。
- 日志确认 `voice_settings_available=true`、`complete_speech_segmentation_verified=true`。
- 用户个人包生成策略检查：`WINDOWS_USER_ART_POLICY_VERIFIED_NO_GENERATED_DEMOS`。
- Windows 仍走 pyttsx3 原生驱动；Linux eSpeak NG 命令不会进入 Windows 包。

## 可试用工件

### Linux

- 工件：[DyberPet-Linux-Personal-x86_64](https://github.com/clonetimer/DyberPet/actions/runs/44275562721/artifacts/14414287836)
- Artifact ID：`14414287836`
- 大小：114,218,244 bytes
- Actions 外层归档 SHA-256：`f989e9e2cafc4d08487161c45f346a81188a3182961e8d01a23d7728f5a0e310`
- 过期：2026-12-02 17:26:53（北京时间）
- 目标机器需自行安装 `espeak-ng`；该系统命令不包含在个人便携包中。

### Windows

- 工件：[DyberPet-Windows-Personal-PR5](https://github.com/clonetimer/DyberPet/actions/runs/44275562759/artifacts/14415060564)
- Artifact ID：`14415060564`
- 大小：107,976,773 bytes
- Actions 外层归档 SHA-256：`43d33fb29d1379f01ddd6259d62ff3727ae187a8c8e64a58b1238854333dfff6`
- 过期：2026-12-02 17:26:55（北京时间）

两份工件均由源 head `158db675` 的产品代码构建。最终分支 head `d80fcc75` 仅补充了测试夹具的平台隔离，没有修改上述产品代码。

## 尚未完成的人工验收

1. Linux 实机安装系统包后，检查所选中文音色能否真实发声。
2. 试听长回复分段、暂停/停止响应和连续多轮轮流对话。
3. 检查 PulseAudio/PipeWire/ALSA 不同系统音频栈下的兼容性。
4. 验证麦克风实际采集和语音识别；本批没有宣称识别链路已通过实机验收。

因此，本批结论是：**Linux eSpeak NG 子进程后端、停止/分段合约、源码 X11 和冻结程序门禁已通过；物理音频设备与语音质量仍待实机验收。**
