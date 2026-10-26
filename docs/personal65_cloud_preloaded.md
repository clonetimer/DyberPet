# Personal65：云端预装真实角色（加密个人包）

这是为“用户电脑无法连接创作者素材网站”的情况提供的预装路线。**与之前本地安装器不同，素材安装发生在 GitHub 的 Windows 运行器中；用户只需获取最终整包和个人解锁密钥。**

## 下载与解锁

1. 在 GitHub Actions 的 **Personal65 Cloud Preload (ENCRYPTED ONLY)** 成功运行页面，下载 `personal65-python-real-art-encrypted` 的 ZIP 并解压到新的文件夹。最新链接在该工作流运行页，以实际 `success` 产物为准。
2. 从本次 ChatGPT 对话获取专属 `DyberPet-Personal65-Private-Unlock-Key.pem`，保留原名，将其放到刚解压的 `DyberPet-Offline-Unlock.exe` 同级目录。**不要上传、推送或分享私钥；丢失私钥无法解锁包。**
3. 双击 `Unlock-My-Preloaded-DyberPet.cmd`。本机不访问艺术素材网站；程序使用 RSA-OAEP-SHA256 加密会话密钥和 AES-256-GCM 验证并解密，生成并解压 `DyberPet-Python-Preloaded-Ready.zip`。
4. 进入 `DyberPet-Python-Preloaded-Ready`，运行 `Run-DyberPet.cmd`，在“系统 → 角色管理”里选择实已安装的角色。
5. 如 Windows SmartScreen/企业防护阻止未知第三方程序，不应盲目关闭安全保护；先检查来源为本项目同一 CI 构建并通过 SHA-256 检验。

## 最重要的数量说明

仅有**65 位拥有登记的固定素材来源**，不等于 65 位实际完成。加密包是由构建运行器联网安装实际素材后生成。成功安装数量见解压后 `LOCAL_OFFLINE_BUILD.json` 中的：
- `genshin_installed_distinct_profiles`：本包真正包含素材的不同原神角色数量；
- `genshin_65_source_target_reached`：是否确实达到 65；
- `mascot_creator_art_installed`：咕嘎 / Doro 真正安装的作者素材数量（0–2）。

公开 Actions 的 `NO_ART_PUBLIC_SUMMARY.json` 只包含安装成功/失败数量，不含任何真实图片。所有图片、动画及角色目录都在经过用户公钥加密的独立文件内，GitHub 仓库不存储可直接查看的第三方原画。

## 保护措施及使用限制

- 加密包只能用聊天中对应的专属**私钥**解锁；GitHub 只存储**公钥**。公钥不能解锁包。
- CI 不在 Release 或上传的 Actions Artifacts 中放入明文原画、原声、图片目录或明文打包 ZIP；加密前的中间文件只存在于临时构建运行器中。
- 本方案仅面向当前用户自用。素材来源发布条款可能限制复制、分享和改编。**不应把解密后的软件或艺术素材公开传播。** 授权、版权和实际视觉相似度仍需人工判断。
- 建议为解密完成的个人版做本地备份。语音模仿、Guga 原声和 Doro 原声仍未包含。
- 以上不等于保证所有 65 位都可从第三方网站下载成功，也不等于每个角色都实现了全部专属互动。

如果 CI 因下载失败而无法获得任何角色，将直接失败；不会发布冒充“65 角色内置”的空包。
