# Qt Windows 构建

0.5.0-preview.11 的后台入口为 `desktop_entry.py`，仅使用 Python 标准库和 Win32；按需启动 `qt_entry.py`。图形使用 Qt Quick / PySide6 6.12.0 和统一的自定义 Basic 控件，后台通过有界 UTF-8 JSON 管道传送状态，图形不直接访问蓝牙。默认关闭最后一个窗口后退出图形进程；显式开启快速唤出时保留界面进程，保留托盘与连接。

## 准备依赖

官方 CPython 3.13.17 Windows embeddable ZIP 放在 `.tools/python-3.13.17-embed-amd64.zip`，开发运行目录同名，构建校验固定 SHA-256。使用 Windows Python 3.12（带 msilib）执行：

```text
python tools/prepare_qt.py
python tools/prepare_qt_licenses.py
python tools/package_qt.py
python tools/verify_qt_bundle.py
python tools/build_desktop_release.py
```

`prepare_qt.py` 从官方 PyPI 下载固定 PySide6-Essentials 和 shiboken6 6.12.0 的 win_amd64 ABI3 wheels，校验版本和哈希后局部展开。不要改动系统 Python。开发 GUI 使用 `.tools/qt-probe/packages`，发行 GUI 使用包内 `qt/`。

打包选择 Qt Core、Gui、Network、Qml、OpenGL、Quick、QuickControls2 的 Python 绑定，所需 QtQml、QtQuick、Window、Layouts、Templates、Controls Basic/impl 模块及图像、Windows 平台插件，再以 PE 导入和延迟导入递归收集动态库。Python 绑定的跨模块依赖与 PE 依赖分别保留。剔除开发工具、其他样式和无关模块，不修改任何保留 DLL/PYD/EXE 的内容。

上游完整许可证和源码位置在 `licenses/Qt`，wheel 元数据与哈希保留。Qt 为动态链接，兼容库可替换；应用为 GPL-3.0-or-later。应用源码 ZIP 随运行包提供。

## 验证

```text
python -m unittest discover -s tests
python tools/verify_qt_ui.py
python tools/verify_qt_controls.py
python tools/verify_qt_navigation.py
python tools/verify_qt_windows.py
python tools/verify_qt_motion.py
python tools/verify_qt_autostart.py
python tools/verify_qt_corners.py
python tools/verify_qt_bundle.py
python tools/verify_qt_install.py
```

上述 Qt UI 工具需要 PySide6，可用官方开发嵌入式 Python 执行。安装与 PE 分析工具使用 Windows Python 3.12 与构建依赖 pefile。

`tools/verify_qt_live.py` 会真实连接 X3，并进行可恢复的降噪切换；运行前退出当前客户端并取出耳机。它会保存原档位、检查回读并恢复，不是只读检查。不要与原版或另一个耳机控制会话同时运行。

MSI 验证使用独立产品名称、UpgradeCode、安装目录和偏好目录，避免替换已有正式安装；验证安装、启动、重装保留偏好和卸载。正常发行 MSI 保留原 Enco Lite UpgradeCode。开始菜单和便携入口直接运行原始 `python/pythonw.exe desktop_entry.py`。

`tools/measure_qt_client.py` 顺序测量真实连接的完整主窗、快捷窗和托盘，各预热 25 秒、采样 15 次完整进程树。需退出其他控制会话；只读耳机状态，不写耳机设置。USS 采样依赖构建目录中的 psutil，不加入生产后台。

输出为 `dist/EncoLite-qt`、当前版本 MSI、便携 ZIP、源码 ZIP、校验值与 manifest。发行包不包含 WebView2、Qt WebEngine、Slint、Tk、Avalonia 或 .NET。旧的 Inno EXE 向导在本机被拦截，当前不交付 setup.exe。

## 平台和窗口

本次实际测试为 Windows 11 x64。真实蓝牙和托盘仍为 Windows 实现。Qt 界面可跨平台，但其他平台的硬件入口尚未移植。

窗口位置存为 `qt_main` / `qt_quick` 的 Qt 逻辑坐标，含正常窗口尺寸、最大化和页面；首次读取旧版 `web_*` 时按 DPI 迁移，超出可用屏幕的范围被校正。主窗为 Qt 无边框窗口，保留系统拖拽和缩放操作，不安装常驻非客户区钩子。

所有窗口关闭才结束 Qt 进程。退出后台时等待 Qt 保存位置及进程退出，超时有界回收；UI 通信或退出不阻塞托盘线程。旧 WebView2 代码只作为历史对照保留，不由当前入口加载。

窗口动态过渡只改变场景图缩放/位移与原生窗口透明度，不改变保存的窗口几何。主窗进入 320ms、退出 220ms，其他窗口 280/200ms；反向切换按剩余距离缩短，至少 90ms。没有新增常驻动画计时器、离屏缓存或渲染后端。极速与系统减少动画立即收敛至最终状态。`verify_qt_motion.py` 可额外传入打包目录，并用包内 Python 运行，检查实际运行库的中间帧、关闭反转、重复显示及减少动画。

## 登录启动与窗口描边

原生后台通过 `encolite/autostart.py` 管理 当前用户 Startup 文件夹内的 Enco Lite.lnk；默认不注册。用 Windows 命令行转义生成绝对 pythonw / desktop_entry.py / --tray-only，对较长路径进行检查，拒绝缺失文件；不用 JSON 偏好伪装实际状态。启动项读取在主窗打开及系统设置事件执行，日常电量推送不读取快捷方式。卸载使用包内官方 pythonw 的隐藏 `--remove-autostart` 入口，在 RemoveFiles 前清理自身项；重大升级跳过清理。隔离 MSI 验证临时测试本应用自己的启动快捷方式，并在 finally 恢复原文件。

Qt 表面背景、内层角和顶层描边使用同一半径；描边最后绘制，关闭像素整数对齐以适应分数 DPI。DWM 设为不做第二次圆角裁切，仍隐藏系统边框；不增加遮罩纹理或效果运行库。`verify_qt_corners.py` 检查实际像素弧线、透明角、原生属性、深浅色及最小/最大化状态，测试色描边仅用于隔离检查。

参考：[Microsoft 启动应用](https://support.microsoft.com/zh-cn/windows/experience/startup-boot/configure-startup-applications-in-windows)。
