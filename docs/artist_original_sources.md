# 使用真正公开的角色桌宠素材，而不是程序设计的替代形象

> 本项目只提供获取与本机安装代码；作者动画、图集、角色声音**不打包到 GitHub 源码或默认安装包**。实际形象质量需要用户预览和人工对照。非商业自用不等于自动取得转授权，此处不代替作品具体条款。

## 在桌宠界面直接安装

进入 **系统 → 角色管理 → 安装作者原画角色**。界面分为「完整原生动画」和「轻量创作者图集」两种来源；选角色，确认下载，安装成功后通过「快速选桌宠」搜索并使用。已有用户的存档、演示角色不会被覆盖。

### 已接入、固定提交的 15 项真实素材（含不同画师版本）

| 可选角色 | 动画作者资源 | 来源 | 安装特点 |
|---|---|---|---|
| 纳西妲 | DyberPet Genshin 原作者美术 | [原神桌宠仓库](https://github.com/ChaozhongLiu/DyberPet_GenshinImpact) | 完整原生动作约 763 文件/80MB；下载大型来源 ZIP |
| 魈 | 同上 | 同上 | 约 706 文件/69MB |
| 流浪者 | 同上 | 同上 | 约 1194 文件/109MB |
| 芙宁娜 | Codex pet `furina--lingxiaotian` | [Codex 来源](https://github.com/legeling/awesome-codex-pet/tree/main/pets/furina--lingxiaotian) | 单图集约 1.9MB，转成原生动画 |
| 胡桃 | Codex pet `hu-tao--lingxiaotian` | [Codex 来源](https://github.com/legeling/awesome-codex-pet/tree/main/pets/hu-tao--lingxiaotian) | 单图集约 2.3MB |
| 可莉 | Codex pet `klee--chenxin-dlut` | [Codex 来源](https://github.com/legeling/awesome-codex-pet/tree/main/pets/klee--chenxin-dlut) | 单图集约 2.3MB |
| 纳西妲 | Codex pet `nahida--lingxiaotian` | [Codex 来源](https://github.com/legeling/awesome-codex-pet/tree/main/pets/nahida--lingxiaotian) | 单图集约 2.5MB |
| 派蒙 | Codex pet `paimon--lingxiaotian` | [Codex 来源](https://github.com/legeling/awesome-codex-pet/tree/main/pets/paimon--lingxiaotian) | 单图集约 2.2MB |
| 雷电将军 | Codex pet `raiden-shogun--lingxiaotian` | [Codex 来源](https://github.com/legeling/awesome-codex-pet/tree/main/pets/raiden-shogun--lingxiaotian) | 单图集约 2.3MB |
| 阿蕾奇诺 | Codex pet `arlecchino--lingxiaotian` | [Codex 来源](https://github.com/legeling/awesome-codex-pet/tree/main/pets/arlecchino--lingxiaotian) | 单图集约 2.2MB |
| 甘雨 | Codex pet `ganyu--chenxin-dlut` | [Codex 来源](https://github.com/legeling/awesome-codex-pet/tree/main/pets/ganyu--chenxin-dlut) | 单图集约 2.1MB |
| 神里绫华 | Codex pet `kamisato-ayaka--lingxiaotian` | [Codex 来源](https://github.com/legeling/awesome-codex-pet/tree/main/pets/kamisato-ayaka--lingxiaotian) | 单图集约 2.3MB |
| 娜维娅 | Codex pet `navia--lingxiaotian` | [Codex 来源](https://github.com/legeling/awesome-codex-pet/tree/main/pets/navia--lingxiaotian) | 单图集约 2.6MB |
| 八重神子 | Codex pet `yae-miko--legeling` | [Codex 来源](https://github.com/legeling/awesome-codex-pet/tree/main/pets/yae-miko--legeling) | V2 图集约 3.1MB |
| 宵宫 | Codex pet `yoimiya--chenxin-dlut` | [Codex 来源](https://github.com/legeling/awesome-codex-pet/tree/main/pets/yoimiya--chenxin-dlut) | 单图集约 1.8MB |

另有既存的 **咕嘎/Doro** 一键下载来源：`tools/install_creator_mascots.py`，见 [既有安装说明](guga_doro_personal_install.md)。这些也是作者图集，不是程序通用颜色模板。

**版本固定**：
- DyberPet Genshin: `0789950b81802cc51ebeeecfc24be16aaee16e74`
- Codex: `db2f6306ce78f6559ab27155d7bfaf00bf43809d`

Codex 只下载 `pet.json` 与 `spritesheet.webp`，校验文件大小和 Git 内容哈希，使用图集的原有像素帧进行裁切转换。完整原生动画从固定版本 GitHub 源码 ZIP 中只抽取当前选中的角色目录，并验证动作配置与 PNG；绝不覆盖已有同名角色目录。

## 真实作者角色的显示与预览

安装完成后，「快速选桌宠」现在读取 `PERSONAL_IMPORT.json` 中的中文名称与来源标识，不再只显示 `SourceGenshinNahida` 这类内部目录名。作者动画被优先排列，程序批量生成的低保真演示默认折叠。缩略图优先取角色 `pet_conf.json` 所配置的待机动画首帧，避免误用技能特效图或道具图造成错误的第一印象。

从 **「安装作者原画角色」** 中选择时，完整原生动画来源为上游整个固定提交 ZIP，下载量可能达到数百 MB（安装时只保留所选角色）；Codex 来源单套通常约 2–4 MB，适合先快速试用。均不会自动重新绘制人物，也不会覆盖用户已安装角色。

## 原作者画面保真：不再按模板挪动角色像素

本次 P0 修复了一个真实保真度缺口：此前 Codex 原画虽然下载正确，但为匹配已经登记的 Q 版角色配置，转换器仍可能对多帧动画做**接地线平移**与**人物头像局部裁切**。这会让作者设计好的站姿、步幅、画面留白和头饰位置发生偏移。现在 **12 套 Codex 原神角色及咕嘎/Doro** 的创作者图集安装路径都显式开启 `preserve_source_frames`，保留原图集每个 192×208 单元格中的 RGBA 像素、透明背景与动画帧布局。

安装时不仅校验下载文件与固定来源哈希，还会逐帧比较导出的 PNG 像素与原始图集单元格：任意像素不一致就拒绝安装。成功时本机 `IMPORT_REPORT.json` 包含 `preserve_source_frames: true`、`source_pixel_integrity_verified: true`，且 `aligned_frames_per_action` 为空。**角色人设和对话文本不因保留原画而取消**。仍然只有创作者素材来源与像素完整性可自动证明，角色和游戏原设主观相似度需要用户人工观看。

**已安装旧角色不会被后台覆盖。** 如果角色来自旧版，会继续使用旧帧；请先备份你的个人素材和设置，再在“角色管理”移除需要更新的独立来源角色并重新选择安装。不要手动删除正在使用的角色。新版本不会擅自改写用户保存的已有角色图。

## 本机原画动作核对图

三套**原神原生动画**完成固定版本哈希校验后，安装器会在当前角色目录内生成 `ANIMATION_PREVIEW.png`：它只选取 `pet_conf.json` 指定的**待机、左行、右行、摸摸、拖动、跌倒与落地**等动作所对应的原始 PNG 帧，按固定比例拼成缩略图。不会修改、重绘、调色或替换下载的任何原画，预览文件与角色动作帧分开保存。Codex 角色也有既存图集转换预览。

安装成功时界面会询问是否打开这张核对图。请特别观察发型/发饰、服饰、标志性饰物以及动作是否符合**所选角色与具体画师版本**。看到原作者文件不等于视觉相似度已经通过：未人工核对前本地收据的 `likeness_manually_reviewed` 始终为 `false`。如不满意，应保留为个人资源候选而非高保真默认推荐。

## 身份与素材完整性门禁

原神原生动画安装不再只检查“有 PNG、有动作配置”。选择 **纳西妲／魈／流浪者** 时，安装器还将下载的角色 `pet_conf.json`、`act_conf.json` 及实际**待机 PNG 原画**分别与固定上游 Git 提交的 blob 内容哈希核对；校验在兼容旧动作配置之前进行。不一致或混入其他人物原画时，立即停止安装，且不会覆盖已安装的角色。安装收据记录通过的文件清单。

12 套 Codex 角色图集的 `pet.json` 和 `spritesheet.webp` 原已校验固定 Git 内容哈希及字节数，因此这 15 项来源的关键原画均可确认与指定的创作者版本一致。

**这只证明文件来源/角色文件未串包，不能自动证明人物还原程度。** 例如头身比例、服装时期、画师画风、动作节奏、语音还需要在真实 Windows 桌面查看。默认不会把 `likeness_manually_reviewed` 标为真；不要将“哈希通过”直接写作“形象相似度验收通过”。

## 与旧版本的区别

以前的「125 可玩演示」是 **125 个动作系统测试用程序生成形象**，既不是 125 份原作者美术，也不是角色本人。现在个人 Windows/Linux 候选包 **默认不包含这些程序合成形象**；125 只是可查找的角色身份/模板。打包 CI 会暂时生成演示帧验收原生动画功能，但在工件上传前逐项删除并验证。若需单独开发测试，才使用 `DYBERPET_QA_KEEP_ABSTRACT_ART=1` 明确保留低保真帧，切勿将这种 QA 包误当正常使用包。普通用户下载候选包后，可以安装上表中的真实作者素材。

也不会因上述素材文件能被解析而自动标注“保真验收通过”。特定画师对某角色的解释、美术版本、动态图真实帧质量和来源使用条件仍需逐个复核。**没有可核实来源的角色不得自动生成相似造型来冒充。**

## 真实设备验收仍需完成

1. 用户在 Windows 桌面下载至少一个 Codex 图集角色与一个完整版，确认正常显示、走路、休息、拍拍和切换。
2. 下载失败、不完整 ZIP、哈希不符或磁盘空间不足时保持原角色和存档完好。
3. 检查动作中的透明边缘、身体轮廓、锚点及高 DPI 视觉。
4. 盲测静态图/动作是否能认出角色（建议 80% 的第一轮验收目标）；声音另行评价。

CI 的无网模拟下载只证明软件安全安装链路，不代表上述 **真实素材网络下载与人工形象验收** 已完成。
