# DyberPet：个人电脑上的固定来源角色批量安装（候选功能）

本文件适用于 `feat/personal-local-artist-batch-20261026` 分支。
**固定来源 65/123 ≠ 已安装 65 个桌宠，更不等于角色外观或声音验收通过。**
程序和公开 Release 不包含第三方原画。私有 GitHub 也不是第三方素材的授权替代。

## 先看清单，不下载

在项目根目录打开 Windows PowerShell：

```powershell
python tools/personal_source_batch.py --output personal-role-plan.json
```

这一步只读扫描 `res/role`，列出“已结构安装”“有固定来源待确认”“需要手动导入”“仍缺来源”的区别。原画 Demo 不会冒充本人已安装的创作者素材。JSON 中的 `original_likeness_verified=false` 不会因为有哈希或结构化动作就自动改为 true。

## 在本机自愿安装（先尝试两个）

确认来源页面的使用条件，并备份已有 `res/role` 与个人设置后，再运行：

```powershell
python tools/personal_source_batch.py --install --accept-personal-use --max-roles 2 --output personal-first-2.json
```

你也可以只选一个原神模板：

```powershell
python tools/personal_source_batch.py --profile genshin_nahida --install --accept-personal-use
```

查看首批两个角色的脸型、服饰、发饰、动作及缩放显示，若满足你的个人需求再执行：

```powershell
python tools/personal_source_batch.py --install --accept-personal-use --output personal-full-install.json
```

此命令会尝试尚未安装且有支持的固定来源的人物，各人物默认选已有优先级排序里第一个可以自动导入的来源。下载/转换采用项目现有的精确来源版本、内容哈希及原生动作审计。来源不能访问、数据损坏或超出大小限制时，逐项报告失败，不覆盖用户旧角色。部分只有本地 React LFS 源文件的人物需自行导入，不会绕过校验自动抓取。未找到来源的 58 个模板仍无作者动画。

**批量安装不会对作者许可作出判断。** 不要在不允许的情况下抓取或使用第三方素材。用户选择的来源必须符合各自的使用条件。安装完成也仅说明素材已通过程序结构校验，需要亲自进行人物视觉、动作和声线核对。

## 不要把个人素材推回 GitHub

脚本只把图片保存到本机指定的 `--role-root`（默认 `res/role`），不提供上传功能。仓库忽略 `/res/role/Source*/`，但其他手动导入目录未必被忽略；提交前执行 `git status --short`，检查是否有图片、音频、用户配置等文件。切勿执行 `git add -f` 将第三方素材强行提交。

这是源码操作入口，不是已经集成到 Windows Release 的一键 GUI。最终便携版/安装程序是否可直接调用批量入口仍须单独验证，包括 Windows 桌面实际播放及用户个人配置备份恢复。

## 回归测试

```powershell
python -m unittest discover -s tests -p "test_personal_source_batch.py" -v
```

测试不连接外网、不下载素材，验证无确认不执行、已安装与演示图分离、路径限制及失败处理。联网来源完整性仍由原有安装器工作流测试。

## R13：无需命令行的本机批量补齐入口

R13 将原有已验证的本机批量安装接口直接接入 **DyberPet → 角色管理 → 安装作者原画**。点选“批量补齐：本机尚未安装、具有固定作者来源的全部原神人物”，或先选择“先试装 2 位”检查网络与角色形象。明确阅读并确认第三方艺术作品的个人使用限制后，才允许下载；拒绝或取消会保持本机文件不变。此操作**不会把 65 套原画预先包含进 GitHub ZIP**。

安装过程在独立 QThread 中进行，界面显示当前人物编号、正在安装的身份和固定来源失败提示。按“完成当前人物后停止”不会杀死图像转换或留下半写入角色；只在**下一位人物开始前**生效。每一位人物只允许读取当前已固定校验的同身份来源，不会把 A 人物素材错挂 B 人物，也不会静默退回程序简笔演示。

批量完成后，程序对实际 `res/role` 目录进行角色库复核，显示「尝试 / 实际认可的本机原画 / 失败」三项数字，并把**每个人物和每个候选来源的详细结果**写在便携目录 `data/personal65-batch-YYYYMMDD-HHMMSS.json`。这份报告只存在用户本机；保存失败会在界面如实提示。新增角色需重启 DyberPet 才能被完整加载。可从角色库逐帧查看动作；下载、配置和文件结构校验成功并不等于人物外观或动作自然性已经人工确认。

原神角色模板数为 123，固定来源覆盖为 65，58 位仍缺；批量工具**只尝试**有固定来源而尚未安装的人物，不能凭这一按钮补全不存在的素材、原声音频或许可证。一次下载几十位角色可能耗时较久，并受第三方站点网络限制；因此建议首次先试装 2 位。
