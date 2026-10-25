# 界面优化与框架选择

**当前状态：0.5.0-preview.1 已完成 Qt Quick / PySide6 迁移。** 七页、快捷控制、连接提示和全部既有操作入口均已接入原后台，运行包按实际 DLL / QML 依赖裁剪，使用自定义 Basic 控件样式。X3 写入回读、原生窗口生命周期、Qt 控件及隔离 MSI 安装/重装/卸载均已通过；见 [VALIDATION.md](VALIDATION.md)。完整客户端内存见 [MEMORY-COMPARISON.md](MEMORY-COMPARISON.md)。以下为迁移前的方案比较与最小原型记录，99.02 MiB 不是最终客户端的数据。

2026-10-24，基于 [与原版的实测](MEMORY-COMPARISON.md) 和当前源码检查。

## 推荐

优先验证迁移到 **Qt Quick + PySide6**，保留现有 Python 协议、托盘和快捷键后台，继续让图形进程按需启动、关闭最后一个窗口时退出。当前真实连接 X3 的后台独占驻留约 13.40 MiB，主要内存成本在界面，现阶段重写协议后台不是优先项。

Qt Quick 使用自身场景图绘制，不依赖 WebView2；适合自定义卡片、过渡、竖向 EQ 和紧凑快捷窗。官方 FluentWinUI3 控件风格可作为按钮、开关、选单、浅深色的基础，产品布局和已有配色仍应按当前界面设计，并不直接采用框架默认排版。跨平台 GUI 与跨平台蓝牙是两项工作，换框架不会自动补齐 Linux/macOS 蓝牙实现。

## 已完成的隔离验证

使用官方 PyPI 的 PySide6-Essentials / shiboken6 6.12.0、现有官方 CPython 3.13.17，在项目内独立展开依赖；未替换生产入口、未连接或写入耳机、未修改系统安全策略。`tools/qt_probe.py` 加载代表性的侧栏、产品图、卡片、模式按钮、选单和开关，并由 Qt 自身导出窗口截图。窗口实际呈现，40 秒后正常退出。

25 秒预热后，间隔 0.5 秒采样 15 次：

| 对象 | 独占驻留 MiB | 私有提交 MiB | 工作集 MiB |
| --- | ---: | ---: | ---: |
| Qt Quick 代表性控件窗口 | 99.02 | 133.34 | 174.16 |

这是独立图形验证窗口，不含蓝牙后台，也不是已迁移的完整客户端，不能与完整版直接计算节省比例。QML 中的电量与型号为界面样例，不是此次读取的设备状态。EQ 页面代码仅作为候选控件，尚未完成真实交互或设备验证。当前完整 WebView2 客户端的 169.02 MiB USS 包含后台与全部浏览器子进程；后台 13.40 MiB 也只是另一次独立状态样本，不应机械相加后声称精确收益。

报告：`verification/qt-probe/report.json`；自身渲染截图：`verification/qt-probe/main.png`；依赖版本与哈希：`.tools/qt-probe/provenance.json`。依赖原始展开约 211.81 MiB，发行时需要分析并裁剪未使用模块、插件、工具及资源；不能把较低运行内存等同于更小安装包。仅验证了开发目录中的加载，尚未验证 MSI 安装后的应用控制兼容性和后续重复运行。

## 其他路线

| 路线 | 适用性与代价 | 结论 |
| --- | --- | --- |
| 继续优化 WebView2 | 最大限度保留 HTML/CSS；代码已共享 Environment、按需创建窗口、关闭全部窗口后退出图形进程，仍有浏览器基础开销 | 可做短期改善，但不预设大幅下降 |
| Qt Quick + PySide6 | 复用协议后台，界面需要 QML 重写；已通过代表性窗口运行验证；支持成熟动画与现代控件 | 首选进一步验证 |
| Avalonia + NativeAOT | 无浏览器；原版现有 AOT EXE 在本机确实能运行；此前 Enco Lite 的普通 DLL 安装候选被拦截，不能据此直接判断新 AOT 构建的结果 | 次选，先做构建与安装验证 |
| Tauri | Windows 上仍使用 WebView2；改为 Rust 宿主不能直接消除浏览器、渲染和 GPU 进程 | 不以降低这部分开销为理由迁移 |
| 原生 Win32 快捷窗/连接提示 + WebView2 主窗 | 常用短操作可避免启动浏览器；主窗继续复用，需维护两套绘制与交互实现，跨平台成本增加 | 若保留现有主界面，可优先考虑 |

## 当前代码可改的地方

- `encolite/web_desktop.py` 的 `Desktop.closed()` 将关闭后的 Window 放入 `retired`，当前没有移除路径；反复切换主窗和快捷窗会累计保留 Python 对象和回调。释放需要跟踪 COM 回调和事件订阅的真实生命周期，不能直接 `retired.clear()`，否则可能把仍被原生层引用的回调释放。应以反复切换后的对象可回收性、窗口及连接不失效作为验收，不能只看一次主窗口的内存。
- 当前 GUI 只有一个共享 Environment，视图也只渲染当前页；没有 React 等大型前端框架。继续削减少量 CSS/JS 不能保证显著降低浏览器基础内存。
- 后台到界面的状态可以进一步按变化推送，把型号列表、图片等静态数据与电量/忙碌状态分开；现有 `GuiChannel` 已合并队列末尾连续状态，新增优化要验证设备回读、开关确认、快捷键保存等状态不会被误丢弃。
- 连接提示和快捷控制目前同样会启动 WebView2；这是高频短操作更值得优化的入口。全量迁移 Qt 时应共享同一 QML 引擎与主题资源，关闭图形进程后保留现有轻量后台。
- 不使用工作集裁剪制造较小的表面数字；不把禁用 GPU 作为常规省内存方案。微软建议保留硬件加速，除非排查渲染问题。对隐藏 WebView 的低内存目标或暂停 API 更适用于保留隐藏实例的程序；本项目已经在关闭最后一个窗口后退出整个 GUI，收益不能直接套用。

## 迁移验收顺序

1. 先完成快捷控制与连接提示：对接现有 JSON 管道，验证真实状态、前台激活、窗口动画、位置记忆及关闭后完整释放。
2. 迁移主页、音效、EQ、设备、设置与全部已支持操作；保持主题、键盘操作、专业竖向 EQ 和同一设计尺度。保留原图形入口用于回归。
3. 用 X3 检查控制写入与状态回读、充电、电量、快捷键、断开重连；一加保持目录和模拟传输验证范围，不宣称完成其他型号真机验证。
4. 完整界面使用同样的真实连接与窗口状态复测，记录 USS、私有提交、共享工作集、启动时间、连续切换后的增长及动画表现；之后再验证实际安装目录的加载与卸载。通过后再切换默认入口。

## 官方资料

- [WebView2 性能建议](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/performance)：共享环境、避免不必要实例、轻量提示使用原生 UI、减少通信、保留 GPU 加速。
- [WebView2 进程模型](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/process-model)。
- [Tauri Windows WebView](https://v2.tauri.app/reference/webview-versions/)：仍为 WebView2。
- [Qt Quick 场景图](https://doc.qt.io/qt-6/qtquick-visualcanvas-scenegraph.html)。
- [Qt FluentWinUI3 风格](https://doc.qt.io/qt-6/qtquickcontrols-fluentwinui3.html)：现代 Windows 风格，可用于其他受支持平台，部分控件仍会回退到 Fusion。
- [Qt for Python 包与授权信息](https://pypi.org/project/PySide6-Essentials/6.12.0/)。
- [Avalonia Native AOT](https://docs.avaloniaui.net/docs/deployment/native-aot)。
