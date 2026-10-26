# Windows 玻璃背景

## 背景与控件

窗口使用原生 Acrylic，QML 只画浅色或深色半透明底。卡片、电量块、普通按钮、选择状态和输入框统一从 Theme.surface 取背景；菜单和对话框使用较高的不透明度保证可读。主操作的强调色、颜色样本和拖动手柄保留明确的色块。关闭玻璃、打开极速模式或系统策略禁用透明时，全部回到原来的实色。

之前只降低了窗口底色透明度，电量块和按钮仍为实色，部分卡片和菜单的底色又过厚，多层叠加后几乎遮住模糊背景。本次修正这些层级，不将整个控件设置 opacity，文字、图标和边框保持清晰。

## 圆角

QML 外轮廓与原生裁切统一为 12 DIP，最大化为直角；不再在玻璃和拖动回退时切换 8 / 12 两套半径。原生区域用对称的物理像素行生成，不扩大到窗口外，按当前 DPI 更新。此前 CreateRoundRectRgn 向外扩展的补偿会使原生模糊底与描边轮廓不同。测试同时检查可见描边没有被截断、四角对称和区域不溢出。

Qt 的分层透明窗口不能只依靠 DWMWA_WINDOW_CORNER_PREFERENCE 保证系统圆角，因此保留与 QML 一致的窗口区域。拖动时暂时禁用 Acrylic 的兼容处理继续保留，圆角尺寸不变。

## 参考

参考其窗口背景、前景色层与系统边缘的分工；未引入额外原生库或复制项目代码。

- [QWindowKit 原生材质实现](https://github.com/stdware/qwindowkit/blob/main/src/core/contexts/win32windowcontext.cpp)
- [PyQt-Frameless-Window 窗口效果](https://github.com/zhiyiYo/PyQt-Frameless-Window/blob/master/qframelesswindow/windows/window_effect.py)
- [Qt 6.12 Windows 分层窗口处理](https://github.com/qt/qtbase/blob/6.12/src/plugins/platforms/windows/qwindowswindow.cpp)
- [Microsoft 圆角限制：逐像素透明与窗口区域](https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/ui/apply-rounded-corners)

自动检查可验证原生请求、QML 透明度和区域几何；最终合成的模糊、阴影及边角观感需人工确认，不将 API 返回成功作为完整视觉验证。
