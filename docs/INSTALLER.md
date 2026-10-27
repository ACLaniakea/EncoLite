# 安装与卸载界面

布局参考 WiX UI 的通用窗口尺寸、标题区、固定底部按钮及独立卸载确认结构，使用本项目自行编写的 msilib 页面定义，未引入新的安装运行库。

参考来源：

- [WiX InstallDirDlg](https://github.com/wixtoolset/wix/blob/main/src/ext/UI/wixlib/InstallDirDlg.wxs)
- [WiX MaintenanceTypeDlg](https://github.com/wixtoolset/wix/blob/main/src/ext/UI/wixlib/MaintenanceTypeDlg.wxs)
- [Windows Installer 控件与键盘导航](https://learn.microsoft.com/en-us/windows/win32/msi/control-table)

完整安装流程为欢迎 → 安装选项 → 安装进度 → 完成。目录选项允许首次安装选择位置，升级保留原目录。完整向导默认创建桌面快捷方式，用户可取消；静默安装仍需显式 CREATE_DESKTOP_SHORTCUT=1。已有同版本时显示修复与卸载选择；Windows 应用设置的卸载入口直接进入卸载确认。卸载保留个人设置。

`tools/verify_msi_ui.py` 检查控件引用、键盘导航循环、条件、全新安装/升级路径与原生页面创建。`tools/verify_msi_launch.py` 复制 MSI 并仅在临时副本的完成页启动命令添加模拟参数，再调用同一组 MSI 动作，验证实际启动入口；不会写入真实耳机设置。

标题区使用白色背景、细分隔线和小面积应用强调色。应用图标从现有 256 × 256 PNG 无缩放导出到 24 位 BMP，绕过 MSI Icon 控件默认选用 16 像素子图的问题。生成过程由 tools/prepare_installer_assets.py 使用已有 Qt 构建依赖完成，MSI 仅嵌入图片数据。

应用图标以抽象耳机弧线为标记。矢量源为 ui/assets/app-icon.svg，tools/prepare_icon.py 直接渲染 16、20、24、32、48、64、128、256 像素图像并组成 ICO，小尺寸加粗线条。构建发行包前自动更新 PNG / ICO，安装器再使用完整 256 像素图像导出 BMP。

## 中文卸载入口

包语言与摘要均为 2052，安装和卸载共用微软雅黑、高清图标摘要及白色标题区。ActionText 提供中文进度。默认 MSI 的应用列表入口可能请求基础 UI，绕过自定义中文页面，因此隐藏默认项，并由当前用户的 MSI 注册组件发布唯一入口，命令显式使用 `/x {ProductCode} /qf /norestart`。该入口随卸载清理，不添加自定义卸载 EXE；原系统 MSI 引擎仍负责修复和卸载。测试产品按 UpgradeCode 使用独立键，避免触碰正式安装。


## 一次运行完成跨版本升级

preview.24 修复旧包将所有文件记为无版本文件的问题。Windows Installer 曾把已安装的 Python/DLL 判为“版本更高”而跳过，随后早期旧版移除又删掉运行库，造成第一次安装返回成功但程序不可运行、第二次才能补齐。现在通过 MsiGetFileVersionW 为具有版本资源的 EXE、DLL、PYD 写入真实版本和语言，不给无版本资源的文件伪造版本；当前包有 89 个带版本资源的文件。

包同时声明压缩和仅当前用户权限（摘要 Word Count = 10）。文件位于 LocalAppData、注册项位于 HKCU，避免按需要管理员权限的包执行用户目录更新。

使用标准事务升级顺序：InstallInitialize（1500）→ RemoveExistingProducts（1510）→ 安装新版文件 → InstallFinalize（6600）。准确的文件版本信息保证成本计算不再错误跳过运行库；先移除旧版也避开本机正式目录的原地覆盖失败。每个文件的组件 GUID 按原相对路径保持稳定。保留原目录，升级不清除登录启动项或个人设置。普通卸载仅在启动辅助程序组件实际已安装时执行清理，避免部分安装状态下引用不存在的文件。

`tools/verify_msi_upgrade.py --full --local-programs` 使用独立产品标识和完整运行包，验证旧式包到新版只调用一次 msiexec，不传 REINSTALL 或 REINSTALLMODE；逐项核对文件哈希、增删文件、文件版本字段、目录与卸载入口，并检查降级拦截、维护及升级后的界面。故障注入位于移除旧版之前，验证预检失败不会破坏旧程序。未声称在所有机器上都完成了移除旧版之后的完整注册回滚。

参考：[文件版本规则](https://learn.microsoft.com/en-us/windows/win32/msi/file-versioning-rules)、[MsiGetFileVersionW](https://learn.microsoft.com/en-us/windows/win32/api/msi/nf-msi-msigetfileversionw)、[RemoveExistingProducts 的事务顺序](https://learn.microsoft.com/en-us/windows/win32/msi/removeexistingproducts-action)。
