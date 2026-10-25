# 不购买证书的分发路线

核查日期：2026-10-22。没有关闭智能应用控制、修改应用控制策略、安装信任证书或上传程序。

## 推荐：Microsoft Store 的 MSIX 私有内测

微软已取消个人开发者注册费。使用个人微软账户注册，需要由账户本人完成身份证明和自拍验证。MSIX 通过商店认证后，微软免费签名；这不适用于以 MSI/EXE 方式上传的安装器。

可以在首次提交时选择 Private audience，只把自己的个人微软账户加入用户组。应用不对其他人公开，也不需要别人能搜索到。私有内测仍要经过商店认证；不是本地生成 MSIX 就自动取得微软签名。

需要先在 Partner Center 注册、预留应用名称，并取得 Identity Name、Publisher 和 PublisherDisplayName，才能生成与该账户匹配的最终商店包。上述账户与发布操作尚未进行。

官方说明：

- [个人注册免费及身份验证](https://blogs.windows.com/windowsdeveloper/2025/09/10/free-developer-registration-for-individual-developers-on-microsoft-store/)
- [MSIX 免费签名；MSI/EXE 由发行者签名](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/code-signing-options)
- [私有受众及指定微软账户](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/visibility-options)

## 若要保留独立 setup.exe：SignPath Foundation

符合条件的开源项目可申请免费代码签名。需要公开、维护中的项目、可验证的源码构建、项目信誉、维护者双重验证、签名策略及人工审批。不是任何新建仓库都会获批。

当前已有把 Slint Python 绑定从源码静态编入主程序的候选实现，避免给第三方原始 PYD 代签。但基金会对修改的上游代码另有限制，不能据此声称已经满足其要求；需要由基金会确认构建范围和资格。没有申请或提交过。

[申请条件](https://signpath.org/terms.html) · [申请入口](https://signpath.org/apply.html)

## 微软文件复核

可以向微软提交被 Smart App Control 拦截的确切文件，申请分析；免费，不保证放行和完成时间。每次修改生成的新文件也不能自动继承上一版结论。

[文件提交入口](https://www.microsoft.com/en-us/wdsi/filesubmission)

## 已验证的技术边界

- 原项目主 EXE 没有签名，几个原生图形依赖分别有微软和 Avalonia 的有效签名。
- 原 PyInstaller 安装版被拦截的文件为 `slint.pyd`，卸载器另有 WinError 4551。
- 更换相邻 Slint 版本、随应用复制 Python 运行时都没有稳定解决安装目录加载问题。
- 新候选版把 Slint 1.18.0 源码静态编入约 15 MiB 的主 EXE，使用原始签名的 Python Software Foundation CPython 3.13.17 运行库；发行目录约 44 MiB，没有独立 `slint.pyd`。
- 原生候选版曾在构建目录和一次真实 MSI 安装后通过 7 页面冒烟测试；MSI 安装和系统卸载也曾成功。
- 同一 SHA-256 的 EXE 在后续复制/重装测试中被 Smart App Control 拒绝执行。Code Integrity 3077/3033 仍指向策略 `{0283ac0f-fff1-49ae-ada1-8a933130cad6}`。因此不能把一次通过当作可稳定使用，原生候选版尚未达到可用发行标准。
- 稳定的解决目标是获得微软商店或合格免费签名服务的信任；自签名、便携版、管理员运行或换扩展名不是已经验证的解决办法。

原生候选程序和中间产物保存在 `.tools/preview2-candidates/`，没有作为可用发行版交付。源码启动入口恢复到原先的依赖，未改变安全设置。
