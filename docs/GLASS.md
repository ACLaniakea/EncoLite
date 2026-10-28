# Windows 玻璃背景与窗口过渡

Windows 11 22H2+ 保留用于原生轮廓和调整大小的窗口样式，由 DWM 处理小圆角、细描边和轻投影。WM_NCCALCSIZE 将整个窗口交给 Qt；原生非客户区绘制保持关闭，并拦截旧式框架与激活绘制，避免玻璃后出现第二套标题和内框。最大化使用屏幕工作区。旧系统使用实色和 QML 轮廓。

原生小圆角使用更紧的系统投影，代替此前延伸较远的底部阴影。Acrylic、透明覆盖色与原生轮廓在窗口可见期间保持稳定，界面内容单独淡入淡出、轻微缩放与位移。关闭时保留玻璃至窗口真正隐藏后再释放状态；最小化与恢复不反复重建原生框架。不对 HWND 设置整体透明度，不启用分层窗口或手工窗口区域，不截图实现动画。

Acrylic 使用任务栏式 Accent Policy，固定轻量底色。此前官方系统背景属性虽然设置成功，用户仍看到实色；已有蓝橙条纹对照验证真实透出和模糊，用户确认“现在可以”。当前版本继续通过最终屏幕合成像素检查保留模糊，不以 API 成功代替可见效果。

“设置 → 外观 → 透明度”支持 0–100%。拖动只改变 Qt 覆盖层，不反复重建材质，松手保存一次；文字和图标保持清晰。关闭玻璃、开启极速模式或系统关闭透明效果时隐藏滑块，保留原值。0% 为实色，100% 为最高透明度，仍保留 Acrylic 的模糊与底色。

主窗内容淡入约 190ms，快捷窗和连接提示约 170ms；关闭时内容淡出约 140ms。取消此前独立的玻璃混合动画和提前关闭原生材质的步骤，避免过渡中短暂变成实色。连续开关保留当前进度，关闭动画有独立释放保障。极速模式和系统减少动态效果时，从首个可见状态即使用完整内容尺寸。使用 Qt 的实际时间动画驱动；没有新增常驻图形进程、定时装饰动画、图形库或着色器。

`tools/verify_qt_chrome.py` 使用自有纯色背景测量阴影、圆角外露和意外标题像素；`tools/verify_qt_motion.py` 检查实际内容中间帧、稳定的玻璃表面、反向动画与减少动画；`tools/verify_qt_material_transitions.py` 连续采样三类窗口打开、关闭、最小化与恢复的材质状态和表面透明度；`tools/verify_qt_composition.py` 使用自有条纹背景验证最终模糊和透明度。材质状态缓存和 API 成功不等于每一帧最终屏幕模糊均经过像素验证，两类检查分别报告。取样时仅将自有测试窗口临时置顶，结束即销毁。窗口 DC 可能返回旧缓存，不能用于判断最终透明度。正式客户端不截图。

参考实现与文档：

- [QWindowKit 原生窗体](https://github.com/stdware/qwindowkit/blob/main/src/core/contexts/win32windowcontext.cpp)
- [PyQt-Frameless-Window 窗口效果](https://github.com/zhiyiYo/PyQt-Frameless-Window/blob/PySide6/qframelesswindow/windows/window_effect.py)
- [Qt 动画驱动与场景图](https://doc.qt.io/qt-6/qtquick-visualcanvas-scenegraph.html)
- [Qt Windows 分层处理](https://github.com/qt/qtbase/blob/6.12/src/plugins/platforms/windows/qwindowswindow.cpp)
- [Microsoft 圆角限制](https://learn.microsoft.com/en-us/windows/apps/desktop/modernize/ui/apply-rounded-corners)

参考其背景、非客户区与内容层的分工，未引入额外原生库或复制项目代码。
