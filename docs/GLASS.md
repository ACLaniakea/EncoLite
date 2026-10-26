# Windows 玻璃背景

## 原生表面

Windows 11 22H2 及以上使用官方 DWMWA_SYSTEMBACKDROP_TYPE=DWMSBT_TRANSIENTWINDOW，由 DWM 同时处理 Acrylic、圆角、描边和阴影。保留必要的系统边框样式，使用 WM_NCCALCSIZE 将客户区延伸至标题栏；不显示系统标题栏按钮，继续使用自己的标题栏和控件。

移除 WS_EX_LAYERED 与手工窗口区域，不再尝试用 SetWindowRgn 裁切系统 Acrylic。QML 的窗口底色画满客户区，不另画外圆角和描边，最终外轮廓交给 DWM，避免两套曲线或裁切层产生三角形底色。最大化时客户区匹配屏幕工作区，系统决定直角、圆角及吸附行为。

原生轮廓在玻璃开关、极速模式和拖动中保持不变；Acrylic 使用官方系统背景，不再在拖动时关闭。旧于 Windows 11 22H2 的系统仍可使用客户端，采用实色和原来的 QML 圆角，玻璃开关不可用。

## 控件与动画

卡片、电量块、普通按钮、选择状态与输入框从 Theme.surface 获取半透明背景；菜单和对话框使用较浓底色保证可读。强调色按钮、颜色样本和拖动手柄保留清晰色块。关闭玻璃、极速模式或系统透明策略禁用时使用实色。文字与图标不降低 opacity。

原生窗口不做会重新启用分层标志的整体 opacity 动画，而是在稳定外轮廓内让内容淡入、轻微缩放和位移；旧系统保留原窗口动画。极速模式及系统减少动态效果设置关闭这些过渡。没有新增图形库、着色器、截图轮询或后台图形进程常驻。原生客户区事件处理只在有窗口时存在，是隐藏系统标题栏所必需的部分。

## 验证与参考

preview.15 的 Acrylic 叠加在 Qt 分层窗口上，手工区域与 QML 轮廓不足以保证裁切背景。preview.16 虽通过几何测试，用户仍确认有方形或三角形底色，因此未发布其安装附件。改为原生表面后，用户明确确认“这次没有了”；正式界面使用相同机制。

自动检查读取 DWM 原生背景和圆角属性，确认非客户区渲染启用、没有分层标志和手工区域，并取得实际合成截图。检查包括控件透明度、动画连续帧、最大化工作区、关闭和置顶行为。原型的目视确认与正式界面的自动检查分别记录。

参考窗口背景、原生边缘与前景内容的分工；未引入额外原生库或复制项目代码。

- [QWindowKit 原生窗口与 Acrylic](https://github.com/stdware/qwindowkit/blob/main/src/core/contexts/win32windowcontext.cpp)
- [PyQt-Frameless-Window 窗口效果](https://github.com/zhiyiYo/PyQt-Frameless-Window/blob/master/qframelesswindow/windows/window_effect.py)
- [Qt Windows 分层窗口处理](https://github.com/qt/qtbase/blob/6.12/src/plugins/platforms/windows/qwindowswindow.cpp)
- [Microsoft 圆角限制](https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/ui/apply-rounded-corners)
- [Microsoft 系统背景类型](https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwm_systembackdrop_type)
