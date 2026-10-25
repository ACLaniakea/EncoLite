# 安装与卸载界面

布局参考 WiX UI 的通用窗口尺寸、标题区、固定底部按钮及独立卸载确认结构，使用本项目自行编写的 msilib 页面定义，未引入新的安装运行库。

参考来源：

- [WiX InstallDirDlg](https://github.com/wixtoolset/wix/blob/main/src/ext/UI/wixlib/InstallDirDlg.wxs)
- [WiX MaintenanceTypeDlg](https://github.com/wixtoolset/wix/blob/main/src/ext/UI/wixlib/MaintenanceTypeDlg.wxs)
- [Windows Installer 控件与键盘导航](https://learn.microsoft.com/en-us/windows/win32/msi/control-table)

完整安装流程为欢迎 → 安装选项 → 安装进度 → 完成。目录选项允许首次安装选择位置，升级保留原目录。完整向导默认创建桌面快捷方式，用户可取消；静默安装仍需显式 CREATE_DESKTOP_SHORTCUT=1。已有同版本时显示修复与卸载选择；Windows 应用设置的卸载入口直接进入卸载确认。卸载保留个人设置。

`tools/verify_msi_ui.py` 检查控件引用、键盘导航循环、条件、全新安装/升级路径与原生页面创建。`tools/verify_msi_launch.py` 复制 MSI 并仅在临时副本的完成页启动命令添加模拟参数，再调用同一组 MSI 动作，验证实际启动入口；不会写入真实耳机设置。
