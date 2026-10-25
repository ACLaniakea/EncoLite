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
