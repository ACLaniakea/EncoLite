# Windows 玻璃背景

Windows 11 22H2+ 保留原生非客户区表面，DWM 统一处理圆角、描边与阴影。WM_NCCALCSIZE 将内容延伸到标题栏，不显示第二套系统标题栏。移除分层标志与手工窗口区域；QML 不再重复画外圆角或描边。最大化使用屏幕工作区，旧系统使用实色和原有 QML 轮廓。

Acrylic 使用任务栏式 Accent Policy，固定轻量底色，在稳定的原生轮廓内合成。此前官方系统背景属性虽然设置成功，用户仍看到实色；这次加入蓝橙条纹对照，已验证能透出背景且边缘被模糊，用户确认“现在可以”。不以 API 成功作为可见效果的证明。

“设置 → 外观 → 透明度”支持 0–100%。拖动通过 Qt 背景覆盖层实时调整，松手后只提交一次偏好，不反复重建原生材质，不改变文字与图标透明度。0% 为实色，100% 为最高透明度，仍保留 Acrylic 的模糊与底色。极速模式禁用玻璃与滑块，保留所选数值，退出后恢复。跟随系统透明策略和高对比度设置。

卡片、电量、普通按钮、输入框和菜单采用统一色层。内容动画在固定外轮廓内运行，避免整体窗口 opacity 再次触发分层；极速模式关闭过渡。没有新增图形库或着色器，也没有持续截图和后台图形进程常驻。

验证工具 `tools/verify_qt_composition.py` 使用自有背景与窗口范围的最终屏幕合成像素，检查透出、模糊和 0% 实色，并检查实际滑块预览与松手保存。窗口 DC 可能返回旧的重定向缓存图，不能用于判断透明度变化。测试截图只在显式运行验证时生成，正式客户端不截图。

参考：

- [QWindowKit 原生窗体](https://github.com/stdware/qwindowkit/blob/main/src/core/contexts/win32windowcontext.cpp)
- [PyQt-Frameless-Window 窗口效果](https://github.com/zhiyiYo/PyQt-Frameless-Window/blob/master/qframelesswindow/windows/window_effect.py)
- [Qt Windows 分层处理](https://github.com/qt/qtbase/blob/6.12/src/plugins/platforms/windows/qwindowswindow.cpp)
- [Microsoft 圆角限制](https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/ui/apply-rounded-corners)

参考其背景、非客户区与内容层的分工，未引入额外原生库或复制项目代码。
