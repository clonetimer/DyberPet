# DyberPet 桌宠助手：交互文件、离线语音与 PPL 人设（P0）

右键桌宠 → Desktop Pet Assistant (Files / Voice / Persona)，打开独立对话框。不改变现有养成/动画/其他右键菜单。此分支与角色导入流水线 PR 独立。

## 文件：由用户手动确认的操作

专属目录为当前用户的 Documents/DyberPetAssistant。只有 .txt / .md / .json / .csv 文件可操作，最多 256 KiB，不允许覆盖，禁止跨目录、路径穿越和符号链接。
“创建文件”：明确填写文件名/内容，二次确认。 “删除到可恢复区”：选择文件并再次确认，仅移到目录内 .pet_trash，不是永久删除，也不是系统回收站。“恢复文件”：允许恢复，若同名目标已存在则拒绝覆盖。
聊天模型输出不会被解释为文件操作；语音识别只是填回文本框。现在不支持任意磁盘路径和自然语言直接删除。

## 语音：可选离线模块，不会常开麦克风

在运行桌宠的 Python 环境中执行：

    pip install vosk sounddevice pyttsx3

下载所需语言的 Vosk 离线识别模型：https://alphacephei.com/vosk/models ，将解压后的本地文件夹绝对路径输入“离线识别模型”。点击“录音识别（4秒）”后，麦克风采样约4秒（16kHz、单声道）；只在内存中转写，识别文字放回输入框，必须再次手动发送。
“朗读上一条回复”调用本机 pyttsx3，中文声线取决于系统已安装语音。缺少扩展依赖时给出提示，不影响原有桌宠运行。当前不提供常开监听、唤醒词或语音实时打断。

## PPL 人设分层

仓库：https://github.com/clonetimer/PPL 。Character Governance 提供关系状态、信任度、事件规则和审计，不是聊天模型。Persona DSL 是独立的编译/render 合同，生成 LLM-facing 的静态/动态提示词。不能把两者混为一谈。

可选启用 PPL Character Governance：在独立目录克隆 PPL 后安装 Node >=22.16；npm install；运行 node product/character-governance/bin/server.mjs。默认监听 http://127.0.0.1:8790 。为跨重启持久化配置 PPL_DB SQLite 文件（依 PPL 仓库说明）。在桌宠勾选“读取 PPL 关系状态”后会按当前角色创建或恢复独立 session。只有用户点击“向 PPL 发送安慰事件”才提交 COMFORT 事件，每条唯一 eventId；聊天文本不会自动影响角色状态。

要使用 PPL 0.3 完整人设，先在 PPL 项目中使用官方 CLI 对 .ppl 程序执行 resolve/render 并将输出重定向为 UTF-8 文本文件。示例在组件目录执行：

    node dist/src/cli.js render examples/zhuang_fangyi/persona.ppl --module-root modules --runtime examples/zhuang_fangyi/runtime.lover.json > persona.txt

然后点击桌宠窗口的“导入 PPL Persona DSL 渲染快照（文本）”，选择可信的本地文本并确认。人设快照最大16000字符，仅在本次应用进程内保存；它是某时刻的 PPL 渲染结果，不代表桌宠直接编译 .ppl 或提交 PPL Runtime 状态。

## 本地模型（LM Studio）

先在 LM Studio 启动 OpenAI-compatible 服务并加载模型；在桌宠助手中填写 http://127.0.0.1:1234 和所加载模型的准确 model ID。文本发送到本机 /v1/chat/completions；PPL 关系状态及可选渲染快照作为提示词上下文。
仅支持 loopback HTTP 服务，拒绝远程URL、代理、重定向；请求在 Qt 工作线程执行并有超时和响应大小限制。不配置本地模型时不会伪造回答；聊天内容默认不落盘。文件操作永远由 GUI 手动触发。

## 自动化与真实运行边界

tests/test_assistant_files.py、tests/test_assistant_persona_voice.py 覆盖文件隔离、删除恢复、PPL 会话/event 协议、语音输入保护和本地模型通信条件。tests/test_assistant_qt.py 验证 Qt 离屏 GUI 操作。GitHub Actions 提供 Windows/Linux Python3.9/3.11 及 Windows PySide6 冒烟。
实机麦克风、Vosk 中文准确度、pyttsx3 中文 TTS、真实 LM Studio/PPL 进程及 Windows EXE 安装仍需要独立验收。当前 PPL 连接使用已公开的 Character Governance HTTP API，并未自动启动、改写或内置 PPL 服务。
