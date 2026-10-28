# R32 · Windows 41 成功、28 失败后的角色恢复与真实素材下载修复

## 当前基线

2026-10-28 的 Windows Python R28 批量安装控制台日志：69 位具有固定作者动画来源的角色中，**41 位 `installed_unreviewed`、28 位 `failed`（成功率约 59.4%）**。其余 54 位尚缺固定来源，和此处 28 个本地下载失败是不同问题。源材料真实性不等于角色外观、动作语义和语音已通过人工验收。

**此前 CI 的实际验证：** [R30 Windows 源码版 + 实际冻结 EXE 5 角色成功](https://github.com/clonetimer/DyberPet/actions/runs/40659954766)；R31 对 NanoPet/Shimeji 固定原图的多 HTTPS 主机回退已进入候选分支。该实验不能证明用户本机的网络代理、证书、权限与 GitHub-hosted runner 一致，也不能承诺所有 28 位立刻成功。

## 新修复

- 对 `legeling/awesome-codex-pet` 的精确 `pet.json` 和 `spritesheet.webp`，在原始 `raw.githubusercontent.com` 网络不可达时，可按**同一 40 位固定 Git 提交和路径**尝试 `media.githubusercontent.com`、`cdn.jsdelivr.net`。
- 单个来源仍**必须**通过已登记的原始 Git blob SHA-1 和真实字节长度核验；不接受不可信重定向、不生成假图、不执行陌生代码、不用其他人物替代。
- 这一修复覆盖的直接相关角色包括**神里绫华、茜特菈莉、胡桃、八重神子**（原来批量安装失败的 Codex 来源）。独立作者的 Codex 图集也复用该安全下载器，能否使用备用域名取决于其路径是否是安全的固定 Git 提交 URL。
- 角色管理的“**从旧版安装报告仅重试失败角色**”入口只提取旧报告 `status=failed` 的角色 ID，忽略旧报告中的 URL、下载来源键与可能注入的任意字符串，并按当前素材名录重新匹配；当前已存在并被角色库存验证的目录不会覆盖。
- 出错时直接展示 `failure_class`、具体异常与“是否还有同角色备用来源”；原始 JSON 报告仍保留。

## 对用户本机的安全操作

**务必先备份**原目录 `D:\Download\personal65-python_2\res\role`、`data` 和相关 `settings`。不要用新解压包覆盖这些目录，也不要删除现有 41 位成功素材。

建议优先使用 R32 发布成功后新版文件夹内的角色安装器，**指定旧目录作为角色根路径**，而不是重复 69 位：

```powershell
# 下方命令须在新版 R32 解压目录内执行
.\DyberPet-Role-Installer.exe `
  --retry-failed-from "D:\Download\personal65-python_2\data\personal65-install-report.json" `
  --role-root "D:\Download\personal65-python_2\res\role" `
  --install --accept-personal-use `
  --output "D:\Download\personal65-python_2\data\personal65-retry-report.json"
```

这会在旧目录中尝试仅未安装的失败角色，不覆盖成功的 41 个角色或原有存档；失败原因见新的 `personal65-retry-report.json`。

如果通过图形界面选择旧报告，而新 EXE 解压在另一个文件夹，务必理解：**GUI 的安装目标是新 EXE 自己的 `res/role`，不是报告所在的旧目录**。需要先安全地备份、合并旧角色目录，或使用上述命令指定旧目录。

R32 候选未完成之前，上述操作要用已包含 `--retry-failed-from` 和镜像回退的新版 EXE；不能直接用早期 R28 安装器执行该参数。

## 仍需证据

若你愿意继续完善真实设备兼容性，请提供**脱敏**的旧 `personal65-install-report.json` 或新重试报告。不同的失败类别（HTTP 404、代理超时、证书验证、SHA 不匹配、目录冲突）需要不同的修复，不能靠猜测批量绕过。此报告不需要上传任何角色原画。

## 发布与进度边界

- R32 CI 应验证 Windows/Linux Python 3.9/3.11 的原始 Git 哈希测试，以及 Windows 上实际下载四位 Codex 角色的原始 JSON/WebP。
- 只有经过 PR、Windows 双版本构建和 ZIP 校验后才能宣布 R32 候选包已交付。
- 安装包仍不内置任何未获再分发授权的第三方角色原画。GitHub 私有仓库的可见性也不会自动解决许可问题。
