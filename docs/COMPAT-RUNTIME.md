# Slint 旧版兼容候选

2026-10-23。此路线保留现有 Python 协议层与界面，使用 Slint 1.17.1b2 和 Python Software Foundation 原版 CPython 3.13.17 嵌入式运行库。**最终安装验证失败：安装后的 slint.pyd 仍被应用控制阻止。** 它是独立失败候选，不替换当前源码的 1.18 依赖，也未晋升到 `release/`。

安装后的开始菜单快捷方式直接指向 `runtime/pythonw.exe`，参数为本机安装目录内的 `run.py`。没有重新编译或修改 Python EXE/DLL，没有新增自制启动器、证书信任或安全策略例外。Slint 组件本身仍未签名；当前机器允许其加载不代表所有电脑、后续系统策略或其他构建都会允许。

兼容适配包括 ScrollView 的 `viewport-width` 属性，以及用 TouchArea 和 Windows 标准标题栏拖动消息替代 1.18 新增的 WindowMoveArea。最小化、最大化仍使用 1.17 已支持的窗口属性，真实协议代码保持原样。主窗口和快捷窗拖动需要在解锁桌面后进一步实测；这一拖动兼容实现限 Windows。

依赖原始归档通过 SHA-256 验证：

| 文件 | SHA-256 |
| --- | --- |
| python-3.13.17-embed-amd64.zip | `9e35319bffedab8b36ad44d8f377cb4f1733bcec257a0b6d04d94f01486ddb38` |
| slint-1.17.1b2-cp311-abi3-win_amd64.whl | `68cbb5365a69b28b70e354e98fdc541f6584f3a41be79b336b4b70e8f280db29` |

使用 Windows Python 3.12 构建安装器（msilib 不支持 Python 3.13）：

```text
python tools/build_compat_release.py
python tools/verify_compat_install.py
```

原始依赖归档放在 `.tools/` 的对应目录；脚本不会默认下载安装器或更改系统配置。候选目录为 `dist/EncoLite-compat/`，setup.exe、MSI 和应用源码归档放在 `.tools/compat-release/`。当前归档用于本地私有验证；公开分发前还需整理所用 Slint 二进制对应的完整第三方源码材料。

验证记录位于 `verification/older-slint.json`、`old-app-1.17.1b2-run.json`、`old-runtime.json`、`compat-installer.json`。较早失败记录予以保留，不用成功记录覆盖历史失败。

已确认 1.16、1.14、1.12 的 Slint 扩展在正常 Windows 文件复制后分别连续加载三次成功，但这些版本不能直接编译当前界面。1.17 完成兼容适配后通过无托盘的七页面、降噪/音效/功能开关及快捷窗会话检查。完整复制环境的普通/最大化窗口位置记忆四个跨进程检查通过。

本轮完整托盘与前台检查期间，Windows WTS 会话返回锁定标志，GetForegroundWindow 返回空；因此前台检查尚未通过，不能据此宣称前台功能回归。X3 只读握手另报 10060 超时，真实耳机控制尚需在耳机连接后复测。最终安装、重装与卸载结果以 `compat-installer.json` 为准。

## 安装后的最终结果

1.17 的 setup.exe 能完成隔离安装、创建两个开始菜单快捷方式；安装后的首次 pythonw 启动在导入 slint 时被应用控制拒绝。已通过系统 MSI 卸载清理测试注册和快捷方式，未作为可用版交付。

随后将 1.16、1.14、1.12 放入另一个隔离 MSI，直接验证安装后的模块加载。1.16 被拦截；1.14 和 1.12 各成功一次，但其后完整应用副本启动又在同一扩展导入阶段被拦截。这些结果记录在 `verification/older-slint-msi.json` 及对应版本的 `old-app-*-run.json`。因此本轮没有找到可靠的旧 Slint 安装路线；单次加载成功不足以判断可分发。

## Avalonia 替代路线

另行构建了与原版相同版本的 Avalonia 12.0.5 最小双窗口程序，使用原始 Microsoft .NET 10.0.10 运行库及 dotnet.exe，不新增自制 EXE 启动器。代码在 `.tools/avalonia-probe/`，检查脚本为 `tools/probe_avalonia_runtime.py`。复制后连续三次、MSI 安装后连续两次均成功创建主窗和第二窗口；报告为 `verification/avalonia-runtime.json`。这验证的是当前机器上的框架运行与安装，不是完整 Enco Lite，不含蓝牙、托盘和已有 UI 的迁移，也未验证 NativeAOT 发布。

未优化的 .NET 版本双窗口工作集约 145–157 MiB，私有内存约 85–88 MiB。测量在窗口创建约四秒时进行，不能与旧版仅托盘的 47 MiB 直接比较，也不代表连接耳机后的最终占用。后续需要单独验证裁剪或 NativeAOT 的占用与启动信任；现阶段不能承诺替换为 Avalonia 就达到更低内存或在所有电脑免签运行。
