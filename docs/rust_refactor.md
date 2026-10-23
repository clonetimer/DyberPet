# DyberPet Rust Refactor R1/R2 — 批量资源索引和 Windows 原生实验包

**目标：在不打断 Python 版使用和发布的前提下，验证 Rust 原生模块是否有实际收益。**

GitHub 分支：`refactor/rust-core-isolated-20261023`。本分支从 Python 桌宠助手 PR #2 的 `5f747c7055745a807516d5010579cebdeeda3b8e` 提交创建。对应的 **PR #3 指向 Python PR #2 的开发分支**，不是 `main`。Python 旧版本与用户现有的 Windows Portable ZIP 不因本实验而改变。角色素材导入 PR #1 继续暂停。

## 架构边界

| 层级 | 当前实现 | 本实验处理范围 |
|---|---|---|
| 桌宠主窗口、透明动画与托盘 | PySide6/Python | 不迁移 |
| PPL、LM Studio、Vosk、pyttsx3 | 当前 Python 接口 | 不迁移 |
| 文件创建/可恢复删除/恢复与授权 | Python PetWorkspace | **不迁移**：先保护既有用户数据 |
| 动画素材静态审计 | Python PNG IHDR | 新增等价 Rust PNG IHDR 可选加速 |
| 本地短音效资源哈希 | Python hashlib SHA256 | 新增等价 Rust 流式 SHA256 可选加速 |

Rust 实现位于 `rust/pet_core`，采用 PyO3 `abi3-py39` 与 maturin 生成 Windows/Linux wheel，要求 Rust 稳定工具链，Python >=3.9。Rust 不调用网络、不创建/删除文件、不打开麦克风、不嵌入任何角色图像和原声。Rust 核心和 Python 项目共同遵守现有素材来源/授权审核规则。

## 用户如何切换

默认直接运行 Python 版（没有 Rust wheel 时完全可用），无需安装任何 Rust 工具：

```powershell
python run_DyberPet.py
```

仅开发/对照实验时，先安装 Rust 工具链与 maturin，在仓库根目录执行：

```powershell
python -m pip install "maturin>=1.7,<2"
maturin build --release --manifest-path rust/pet_core/Cargo.toml --interpreter python --out wheelhouse
python -m pip install --no-index --find-links wheelhouse dyberpet-native-core
$env:DYBERPET_NATIVE_BACKEND="rust"
python -m unittest discover -s tests -p "test_rust_bridge.py" -v
```

回退：

```powershell
$env:DYBERPET_NATIVE_BACKEND="python"
python run_DyberPet.py
```

仅请求 Rust 但 wheel 不存在时，自动使用 Python 基线；可以调用 `from DyberPet.assistant.native_bridge import backend_status; print(backend_status())` 看实际选择。**若 Rust 模块存在但校验本身报错，会直接拒绝数据，不会静默跳过验证。** 对应的哈希内容与 PNG 元数据返回结构必须与 Python 完全一致。

## 自动验收与性能门槛

GitHub Actions `Rust Core Isolated` 分别在 Windows、Linux × Python 3.9、3.11 构建 wheel，并运行 Rust 单元测试、Rust/Python PNG 和 SHA256 等价性、已有的桌宠助手测试（在 Python 默认模式和 Rust 模式各运行一次）。额外的 `Windows portable candidate` 和 `Desktop pet assistant` 是原 Python 体系回归检查，**其通过不意味着二进制中已经捆绑 Rust 插件**。

建议只有满足以下条件才考虑迁移更多模块：既有功能没有回归；Rust 扩展可按需打包和关闭；经过重复测量，端到端性能、内存或启动成本有足够收益；安全数据操作仍有完整的恢复、回滚和损坏注入测试。PNG 只读取 33 字节，Python 本来就可能很快；没有基准数据前不宣称 Rust 更快。

## R1/R2：批量动作资源索引与性能验证（已实现）

本分支增加 `dyberpet_native.batch_png_headers(paths)`。给出经过原生角色审计入口筛选的帧路径列表，Rust 每次只读取 33 字节 PNG 头，通过**一次 PyO3 调用**批量返回 `(width,height,bit_depth,color_type)` 或“无效帧”标记；遇到真实文件 I/O 错误直接报错，不将不可读取的文件伪装为有效。一次调用限制最多 10000 条路径。仍由 Python 审核前缀、过滤符号链接与可疑文件名，最多检查每组前 100 帧；角色动作名与输出 JSON 结构没有变化。

当多个动作引用同一图片前缀时，`inspect_character_role` 只在**同一次检查**内复用结果。没有磁盘常驻缓存、没有跨次检查的状态，因此用户替换图片后的下一次检查仍能识别损坏、尺寸变化和文件缺失。

`tests/test_rust_frame_index.py` 使用合成帧验证 Python/Rust 结果一致，包括错误尺寸、坏帧、相同前缀、符号链接和读取后文件发生变化。独立 CI 在 Windows/Linux + Python 3.9/3.11 对双后端进行全量测试。整角色基准可自行复现：

```powershell
python tools/benchmark_frame_index.py --frames 100 --rounds 5
```

**一组 CI 示范（100 帧/动作、3 个前缀、5 轮中位数，非真实性能保证）**：

| 系统 | Python 审计 | Rust 批量索引 | 适用解释 |
|---|---:|---:|---|
| Windows Python 3.11 | 42.023 ms | 34.574 ms | 本合成任务快约 18%，不代表动画帧率提升 |
| Ubuntu Python 3.11 | 8.007 ms | 7.047 ms | 本合成任务快约 12%，小负载收益有限 |

两者报告完全相同。实际用户资源的磁盘/压缩格式、缓存、杀毒软件和角色包规模可能不同；性能数据不应被当作正式体验声明。

## R3：Windows 可选 Rust 原生打包（独立试验）

保持原有 `tools/build_windows_portable.ps1` 默认功能不变。想构建**独立实验包**时先安装 Windows 上编好的 `dyberpet-native-core` wheel，再运行：

```powershell
powershell -ExecutionPolicy Bypass -File tools/build_windows_portable.ps1 -IncludeRust
```

这会让 PyInstaller 显式包含 `dyberpet_native.pyd`，另行输出 `DyberPet-Windows-Rust-Experimental.zip`。新建的 `Windows Rust Portable (Experimental)` GitHub Actions 从零编译 wheel 并实际运行打包好的 EXE，要求 `native_backend.active == rust`，否则判失败，不能用 Python 静默回退冒充 Rust 构建。Python 默认便携包仍为 `DyberPet-Windows-Portable-PR2.zip`，不会因此带入原生扩展。安装包尚未签名，不能当作正式 Release。

## 后续里程碑

R0：纯读取校验与 SHA256 + PyO3，Python 默认为稳定实现；R1：建立真实性能基线与资源索引基准；R2：仅当有可重复收益时研究批量素材索引、缓存或音频数据处理；R3：Windows 便携 EXE 原生扩展可选打包；R4：长期运行、崩溃恢复、安全回归门禁。任何阶段都不强制切换到 Rust，不实施大爆炸式 Tauri/Go UI 改写。

**本 PR 保持 Draft，不合并 Python 功能 PR #2 或 main。**
