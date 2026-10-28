# R30 Windows 本机安装失败专项整改

## 用户实测基线

2026-10-28 用户使用 R28 Windows Python 包尝试安装已有固定素材来源的 69 位角色，日志显示 **41 位 installed_unreviewed，28 位 failed**。这不影响另有 **54 位**尚无固定素材来源的角色；角色来源覆盖与本机安装成功率必须分开统计。R29 新增刻晴的另一套独立 92 帧原作者版本，但仍为同一位人物。

失败的角色：阿贝多、艾尔海森、神里绫华、白术、坎蒂丝、重云、茜特菈莉、赛诺、达莉娅、迪卢克、迪奥娜、杜林、菲谢尔、弗林斯、胡桃、嘉霍达、凯亚、枫原万叶、刻晴、雷泽、达达利亚、托马、空、荧、温迪、魈、八重神子、钟离。

**仅凭用户上传的控制台日志无法判断各项具体失败原因**，因为旧版本隐藏了异常文本。旧安装包目录下的 data/personal65-install-report.json 记录了每项 source_attempts 的原始 reason，可以据此区分 HTTP 404、SSL、超时、SHA 校验、文件夹冲突等。

## 已验证内容

- [真实 Windows 源码版联网验收](https://github.com/clonetimer/DyberPet/actions/runs/40659628280)：阿贝多、迪奥娜、菲谢尔、白术四位本机失败角色在 GitHub-hosted Windows 上**全部安装成功**；安柏对照也成功。这只能证明这些来源未普遍失效，不能证明用户所在设备网络或冻结 EXE 正常。
- R30 新增同等 PyInstaller 冻结 EXE 的真实 Windows 联网下载与安装任务，须分别检查其输出，不因源码版通过便宣称冻结包通过。

## 本轮改造

1. 安装控制台现在输出每个失败来源的异常文本和分类，而非笼统打印 failed。对于无下一来源的角色，会正确标注没有更多可尝试的固定来源。
2. JSON 安装报告追加失败角色 ID 列表和分类计数，原始异常仍保留。
3. 追加 --retry-failed-from 参数，读取旧报告中 status=failed 的**角色 ID**，绝不接受旧报告提供的下载 URL/来源键。安装器每次重新从可信名录取得素材固定版本，并检查本机是否已经安装，不会覆盖成功角色。
4. 新 Windows Python/RustHybrid 包内会带 Retry-Failed-Roles.cmd：在**同一解压目录**内可直接只重试失败项，保留之前的报告，另存 personal65-retry-report.json。
5. 不降低 Git SHA、原图哈希、图片来源域名、原画不入公共发布包等安全检查。

## 用户原有安装目录的安全使用方式

**先备份** D:\Download\personal65-python_2 的 res\role、data、settings。不要删掉或用空目录覆盖已成功的 41 位。

如果新 R30 包解压到了另外的目录，可以在新目录中打开 PowerShell，执行：

    .\DyberPet-Role-Installer.exe --retry-failed-from "D:\Download\personal65-python_2\data\personal65-install-report.json" --role-root "D:\Download\personal65-python_2\res\role" --install --accept-personal-use --output "D:\Download\personal65-python_2\data\personal65-retry-report.json"

上述命令沿用旧目录中的原画和存档，跳过已安装角色，只尝试 28 位失败角色。需要在执行前确认原作者素材个人使用条件；新 EXE 不会覆盖旧桌宠主程序。另一方式是将完整旧角色及旧 JSON 备份恢复到新版同一路径后点击 Retry-Failed-Roles.cmd。

截至本文件编写，R30 尚处测试候选阶段，不宣称已经解决全部 28 项，具体原因仍以 Windows 冻结程序复测及用户上传的脱敏 JSON 为准。
