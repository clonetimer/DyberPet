# 个人本地使用：DyberPet 角色快速导入

此流程服务于**在自己电脑上使用角色**，不是 GitHub Release、商业发布或重新分发角色包。DyberPet 不自动下载游戏图片、角色配音或模之屋模型。个人、非商业使用并不自动意味着任意图片、模型或音乐都可以修改或再传播；请遵守具体作者的许可条款。

## 不会写代码也能完成的方式（建议）

1. 从合法可用的来源，在自己电脑上准备 **单个主桌宠 ZIP / 已解压主角色文件夹 / Codex 图集文件夹 / GIF、PNG 动作帧文件夹**。
2. 在 DyberPet 中进入 **系统 → 角色管理 → 添加角色**。
3. 选择“**个人本地导入：原生角色 ZIP**”或者“**个人本地导入：角色文件夹 / Codex / GIF / PNG**”。
4. 本地导入器会检查 DyberPet 角色配置、资源布局或 GIF/PNG 动作。重复角色自动创建不冲突的安装目录；完成后可查看动作预览、切换角色。
5. 如果缺少所需的素材，不要把 30 个原神模板误认为内置 30 个可播放角色。可以先安装免费的**原创程序绘制角色星芽**，用于验证安装流程（参见 [星芽教程](original_chibi_starter.md)）。

本机安装**不需要**逐个填写用于公开发布的版权审核单；现有 UI 本来就支持这些本地导入途径。导入器不会证明素材作者身份或授权，也不会为个人文件自动生成公开的素材包。

## 已登记的真实来源线索

仓库现有[角色合集目录](https://github.com/clonetimer/DyberPet/blob/main/docs/collection.md)列出了**魈**、**流浪者**、**纳西妲**等主角色的原始发布者与资源入口，也单独列出了**派蒙**等迷你宠物。点击目录中的具体作者/资源地址，**自行获取单个角色资源**，先确认该页面对个人下载、修改、录音及分享的规定；本软件只提供浏览链接，不会代替用户下载百度网盘文件。

- 魈、流浪者：已有单主角色发布线索，可把合法取得的 `res/role/<角色名>` 文件夹或单角色 ZIP 本地导入。
- 纳西妲：同样有历史主角色模组线索。
- 派蒙：合集的原始资源是**迷你宠物** `res/pet`，不能把这个包直接作为主角色导入。若想做主桌宠，应使用适配的图集/动作帧流程。
- 其余原神模板：目前没有核实到可直接安装的逐角色资源。**模板选项多不等于可玩的角色包多**。

## 批量角色库关联的快速路径（可选）

当你已有合法取得的**魈**原生角色 ZIP，或者人物对应的 GIF/PNG 动作帧文件夹，可以直接从项目根目录运行：

```powershell
# 先做只读预检，不写入或安装
python tools/personal_role_import.py inspect --asset "D:/PetAssets/XiaoRole.zip"

# 指定一个模板，将本地素材装到个人电脑（不做公开发布）
python tools/genshin_batch.py personal-install --role xiao --asset "D:/PetAssets/XiaoRole.zip" --personal-use
```

指定的 `--role` 仅控制**显示与对话 Q 版模板**；软件不会凭文件名或图片自动识别角色，不会宣称图片是对应的魈。GIF/PNG 应至少包含 `idle.gif`、`idle.png` 或 `idle_0.png`；也可带 `wave_0.png`、`left_walk_0.png` 等动作。已安装角色会留在本机 `res/role` 中；没有远程上传动作、不会自动生成公开发行 ZIP。

对其他来源，可以不选择游戏模板：

```powershell
python tools/personal_role_import.py install --asset "D:/PetAssets/MyOwnSprites" --personal-use
```

若角色目录中已有 `pet_conf.json`、`act_conf.json` 和 `action/`，直接安全复制主角色文件而非重画图像；对 GIF/PNG 则执行本机透明帧转换。3D PMX/VRM/GLB 不能直接按图片文件夹导入，需先使用相应的 3D 工具渲染透明动作帧。

## 与严格审核流水线的区别

| 场景 | 默认操作 | 授权和验收 |
|---|---|---|
| 本地尝试或个人使用 | GUI「添加角色」或 `personal-install --personal-use` | 本机保留素材；用户自行核对对应作品使用条件 |
| 整理可重复构建、留档的角色候选 | `genshin_batch.py seed-missing`、`character_pipeline.py attach` | 可以保存来源、内容哈希与质量记录 |
| 准备公开分享/发布角色包 | `character_pipeline.py rights/build/qa/package` | 必须记录逐件的可再分发与衍生使用条件，通过真实角色验收 |

`personal-install` 明确写入 `PERSONAL_IMPORT.json`，其中 `source_rights_verified=false`、`visual_identity_verified=false` 和 `redistribution_allowed_by_tool=false`；不会改变已有的 `cases/`、`reviews/` 或授权记录。重复安装自动选择新名称，失败时不会覆盖已有资源。**如果将来需要公开分发角色包，不允许凭本地使用记录直接通过发布审核。**
