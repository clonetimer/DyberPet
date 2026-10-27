# DyberPet Personal65：在自己的 Windows 电脑一键生成角色已内置的离线版

**目标：本地一次性下载/安装，在你电脑上生成新的完整离线 ZIP。** 之后使用该 ZIP，不必再逐个下载角色。官方/作者形象与声线是否符合用户预期仍需视觉/听觉验收。

> 65 = 原神 123 个模板里有固定来源的 65 位角色，并不等于可以自动下载成功 65 位，更不等于已验收 65 套原作形象。咕嘎和 Doro 是另外 2 位桌宠，具有独立的创作者二创素材来源。源素材的个人使用和再分发权限由对应创作者分别决定。

## 用户只操作一次

1. 到 GitHub Actions 的 `Personal65 Python and Rust hybrid Release` 构建页下载 **personal65-python** 或 **personal65-rust**，选择一种即可。先解压 Actions ZIP，再解压其中的 Windows 软件 ZIP。不要直接修改压缩包。
2. 将解压后的整个程序目录放在可写位置（例如 `D:\Apps\DyberPetPersonal65\`），不要放入 `Program Files`。
3. 双击 **`Make-My-Offline-DyberPet.cmd`**。程序先显示 123 / 65 / 58 角色状态、咕嘎和 Doro 来源状态，以及创作者使用条件提示。
4. 审核创作者条款，允许用于自己电脑时输入 `INSTALL`。工具会尝试对所有可自动获取且尚未安装的来源进行下载、固定哈希校验、动画转换和本地登记。即使个别下载失败，也会继续执行并保留报告。也可以输入 `PACK`，仅使用已安装素材生成离线 ZIP，不联网下载新素材。
5. 离线 ZIP 会出现在软件文件夹的**上一级目录**，文件名类似 `DyberPet-Personal65-Python-LocalOffline-YYYYMMDD-HHMMSS.zip` 或 `DyberPet-Personal65-RustHybrid-LocalOffline-*.zip`。**不需要 Python/Rust 开发环境即可运行打包出的 Windows 便携应用**。
6. 解压这个个人离线 ZIP 到新目录，双击 `Run-DyberPet.cmd`，进入角色管理，检查实际可播放的作者素材角色。

**无需反复下载：** 如果你需要继续使用角色，始终从这个离线 ZIP 重新解压/复制，而不是最初不含原画的 CI ZIP。新的 ZIP 含本机真正装进去的角色文件。

## 离线打包的防误交付检查

运行 `Make-My-Offline-DyberPet.cmd` 时，现在会在生成 ZIP **之前**拒绝以下情况：

- 一个真实的原神/咕嘎/Doro 创作者角色都未安装，只有基础 Kitty：拒绝生成虚假的“65 角色离线包”；
- 存在扫描到的无效角色目录：先修复或移除错误目录后再打包；
- 仍混有旧版本程序生成的 `BUILTIN_CHIBI_DEMO.json` / `BUILTIN_MASCOT_DEMO.json` 占位人物：先备份后移除旧低保真演示角色。

失败不会创建成功 ZIP，也不会改动原有角色素材。成功打包可以少于 65 位，但 `LOCAL_OFFLINE_BUILD.json` 会如实标明实际数量与是否达到 65。素材结构验证通过仍不等于原设还原、完整动画、语音或授权验收。


## 怎么确认 65 个都在

ZIP 中 `LOCAL_OFFLINE_BUILD.json` 会报告：
- `genshin_installed_distinct_profiles`：已经装入有效来源素材的不同原神角色数量，不会把演示图或登记信息冒充成实物；
- `genshin_65_source_target_reached`：是否真正达到 65 位；
- `mascot_creator_art_installed`：咕嘎、Doro 的作者素材已装入数量（0–2）；
- `invalid_genshin_folders` / `invalid_mascot_folders`：异常素材目录数；
- `author_rights_verified_by_tool`、`game_likeness_verified_by_tool` 和 `voice_fidelity_verified_by_tool` 一律为 `false`；这些需要手工判断。

本机程序目录下的 `data\personal65-source-install.json` 与 `data\personal65-mascots-install.json` 是安装结果。报告只保存在你本机，不跟随离线 ZIP 复制（保护个人数据）。如部分来源失效、需要人工导入或存在许可限制，只能标记为未完成，不生成简笔画替代，也不声称全 65 已安装。

## 关于版权、隐私和备份

本模式不会把角色画面、角色声音上传到 GitHub、CI Artifacts 或公开 Release；真正包含第三方素材的 ZIP 只产生在你的 Windows 电脑上。程序会排除 `data/` 用户存档、私密配置、日志等内容。**请不要将该 ZIP 上传到 GitHub Release**，即使仓库是 Private；私有仓库不能替代素材原作者的再分发授权。需要保留个人资料时，应单独使用 DyberPet 的存档备份/恢复功能。

固定哈希证明下载的文件符合预期，不能证明素材真实还原了咕嘎、Doro 或原神角色，也不能证明配音来自原作者。

## 开发验收

```powershell
python -m unittest discover -s tests -p "test_local_offline_bundle.py" -v
python -m unittest discover -s tests -p "test_personal_source_batch.py" -v
```

该测试使用合成临时文件，不下载第三方美术资源。打包程序的最终 EXE 与 CMD 入口则由 `tools/build_personal65_windows.ps1` 验收和复制到 Python/RustHybrid 两种发行目录。
