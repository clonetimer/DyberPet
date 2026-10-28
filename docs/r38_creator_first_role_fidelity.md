# R38：把 Doro 本轮认可的美术标准落实到所有 125 个角色

日期：2026-10-28 · **角色选型 / 开发能力增量，绝非 125 套美术已完成**

## 验收准则

这次用户认可的是 0x4682B4（六碳糖）制作的 Doro Live2D / MelanTech Dororo 同源形象与动态质感，而**不是让原神、咕嘎等所有角色照搬 Doro 的身体、配色**。每个角色的形象必须来自自己对应的作者/版本并通过具体视觉对比。

按下面顺序为每个角色选素材：

1. 优先找 **国内原画创作者直接发布的已有成熟动态**，并确认对应原始角色身份、画师、作品页、服装版本；直接能被 DyberPet 加载的原生 `pet_conf.json`、`act_conf.json`、`action/` 更值得优先处理。
2. 次选同一画师统一画风的完整 2D / Live2D/逐帧动作。不能拿不同作者、不同服装版本的正/侧/背拼接；Live2D 表情不自动等于真实三视图。
3. 3D / MMD 仅在**具体造型已达到审美标准**且具备本地使用/改编许可时选用；可下载、可打印、模型有几何结构都不是审美合格理由。
4. 逐角色检查**原设特征**（发饰、服装、配件、特殊体型）、动作完整性（待机、左右移动、摸头、拖拽、休息等）、在桌面按实际大小观察的可读性；同一角色同版形象必须在动作中连续。
5. **作者代码许可与角色原画/模型许可独立**。软件公开仓库仅保存来源链接、规则与测试；`ChatGPT-Download` 私有仓库也只保留许可允许复制存储的文件。不得将“私人可见”视为自动获得再分发权利。

## 已有**可直接定位到具体角色**的源（不是美术验收合格）

| 角色 | 原作者作品或原生源目录 | 风格状态 | 下一动作 |
|---|---|---|---|
| 咕嘎 | [氧化钙你五月 v0.3](https://www.bilibili.com/video/BV1MGLN6eEuh/) 和 [v0.2](https://www.bilibili.com/video/BV1UJoEBrE9J/) | DyberPet 原生角色，须视觉核对；不同于 wwj Codex 图集 | 核实授权的 ZIP 与原生动作实际完整性；优先 v0.3 |
| Doro | [0x4682B4 原作者 Live2D](https://www.bilibili.com/video/BV16z421B7HQ/)、[MelanTech/Dororo](https://github.com/MelanTech/Dororo) | **用户已认可该形象方向** | 保持其四足软萌外形；作者禁止模型再分发，需按条款处理 |
| 纳西妲 | [栎曦_Nuo 原作者视频](https://www.bilibili.com/video/BV1fd4y1W7ht/) | 有专属 2D 原画与原生桌宠关联 | 核对真实动作数量、游戏角色版本和作者许可 |
| 魈 | [栎曦_Nuo 角色作品](https://www.bilibili.com/video/BV1gv4y1a7Q7/) | 角色专属作品线索 | 检查文件实体与面具/枪等标志性造型 |
| 流浪者 | [旧版 DyberPet_GenshinImpact / res/role](https://github.com/ChaozhongLiu/DyberPet_GenshinImpact/tree/main/res/role) | 实际有「流浪者」角色文件夹，但需核实版本 | 先检查动画帧、发饰及版本 |
| 神里绫华 | [书呆儿原设 Live2D](https://www.bilibili.com/video/BV1ix4y117SK/) | 付费绫华猫猫，14 套动作/表情 | 仅作审美/动作密度参考，依作者许可本地使用；不能复制进公开或私有 Release |
| 胡桃 | [ZaytsevZY Codex v2 图集](https://github.com/ZaytsevZY/genshin-pets/tree/main/pets/hutao) | 像素风备选，未得到用户认可 | 对比胡桃原设和实际帧清晰度、动感 |
| 茜特菈莉 | [ZaytsevZY Codex v2 图集](https://github.com/ZaytsevZY/genshin-pets/tree/main/pets/citlali) | 像素风备选，未得到用户认可 | 检查坐垫、书本和角色五官、比例 |

这 8 位只是已检索到**单角色作品链接**，不是 8 位高保真完成，也不意味着已经下载/安装。当前 125 个模板中剩余 117 位只有**作者系列发现入口**，必须继续逐角色获取源资料，不能把“原神桌宠系列”算作 117 位已找到作品。

## 不可混淆的来源

- [栎曦_Nuo 《原神桌宠：全角色（2.8前）》](https://www.bilibili.com/video/BV1eY4y177tk/) 是中文创作者在 2022 年提供过的原画合集和网盘下载入口，**很适合先核查一批早期原神人物**；但旧 2.8 阵容与现今 123 模板不同。不能只看视频标题就把现有 123 位标成美术齐全，当前未取得、检查或上传该网盘包。
- 旧版 [DyberPet_GenshinImpact](https://github.com/ChaozhongLiu/DyberPet_GenshinImpact) 仓库自述不再维护。实际 `res/role` 目录含：兰纳罗、散猫猫、流浪者、纳西妲、蕈兽、魈、魈鸟，以及系统目录。这**不是 123 位全部角色的原画资源**。
- [ZaytsevZY/genshin-pets](https://github.com/ZaytsevZY/genshin-pets) 的 `pets/` 下当前确有 `citlali/` 和 `hutao/` 的 v2 图集，不能因仓库标题叫“原神桌宠合集”就声称有整个原神阵容。
- [MelanTech/Dororo](https://github.com/MelanTech/Dororo) 的美术源指向 0x4682B4；两条记录共用一条来源 lineage，不能据此增加独立原画数量。
- [氧化钙你五月 v0.3](https://www.bilibili.com/video/BV1MGLN6eEuh/) 视频页面注明使用 AI 合成内容且未经授权禁止转载；需要进一步确认实际所用的原画是谁创作的、如何授权、是否同版，不能仅看作者发布视频就认定全部美术是该人原创。

## 本机使用：无需会写代码

在 DyberPet 的 **系统 → 角色管理 → 全部角色库** 搜索任一中文名，选中角色后会出现该角色的作者来源列表和“打开作者作品页”。列表会分清 **角色专属线索** 与 **系列查找入口（非角色证据）**，不会自动下载任何二创素材。

希望批量查看机器可读的来源覆盖情况，也可以运行：

```powershell
py tools/character_art_source_index.py
py tools/character_art_source_index.py --id mascot_guga
py tools/character_art_source_index.py --id genshin_nahida
```

该命令只读，不创建软件包；显示 `specific_source_leads` 只代表找到单角色作品网址，不代表权利审核、三视图、可播放动作或 Windows 实机已通过。现有 `tools/character_progress.py` 保持独立，**不把来源数量伪装成角色完成数量**。

## 继续开发优先级

1. 咕嘎 v0.3 原生 `res/role` 动作检查与外观对照：它本身已经面向 DyberPet 制作，省去错误 3D 形象的风险。
2. 原版纳西妲、魈、流浪者：核实作者原生动画文件结构和动作质量，再以实机互动触发验证。
3. 胡桃、茜特菈莉像素版：先做审美 A/B，只有画风与用户期待匹配才考虑接入；不拿简化像素替代成熟 Q 版。
4. 其余 117 位继续逐人追踪中文画师作品与专属动作；每轮只将核实过的作者链接新增为角色专属候选。
5. Python/Rust 的用户端只显示**实装且合规可用**的角色素材，Q 版源、3D 权限和音效必须分别审核；在完成新美术和实机 QA 前不宣布更多“已完成角色”。
