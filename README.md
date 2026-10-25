# Enco Lite

面向 Windows 的 OPPO / 一加蓝牙耳机控制客户端，基于 [OppoPodsManager](https://github.com/Zhaoyi-ya/OppoPodsManager) 的协议与型号适配，使用 **Qt Quick / PySide6** 界面。

界面与托盘、蓝牙后台分为独立进程。默认关闭最后一个窗口后退出图形进程，继续保留托盘与耳机连接；需要更快打开时，可在设置中开启“快速唤出”。

## 下载

**[当前预览版 v0.5.0-preview.15](https://github.com/ACLaniakea/EncoLite/releases/tag/v0.5.0-preview.15)** · [全部发行版本](https://github.com/ACLaniakea/EncoLite/releases)

- **安装版**：下载并双击 `EncoLite-0.5.0-preview.15-win-x64.msi`，按向导选择位置和桌面快捷方式，完成时可直接打开程序。
- **便携版**：下载同版本 `win-x64-portable.zip`，解压后运行“启动 Enco Lite.cmd”。
- 运行包已包含 Python 和 Qt，无需另装运行环境。SHA-256 校验值随发行附件提供。

系统要求为 Windows 10 1809+ / Windows 11 x64，实际测试环境为 Windows 11 x64。当前蓝牙与托盘后端仅支持 Windows。

## 功能

- 降噪、通透及型号支持的强度、子模式与原厂音效。
- 自定义 EQ，使用竖向频段推子与 dB 网格。
- 电量、充电状态、佩戴状态、固件信息、编解码器及型号图片。
- 型号支持的佩戴检测、双设备、游戏、低音、空间音效与多设备管理。
- 托盘快捷控制、连接提示、全局快捷键和窗口位置记忆。
- 跟随系统深浅色、自选 / Windows 强调色、可选玻璃效果、可选玻璃效果、窗口动态过渡与极速模式。
- 快捷控制可选置顶、可设置闲置自动收起时间；支持可选的登录自启动。

自启动默认关闭，在“设置 → 启动与性能”开启。登录后先在托盘运行，主窗口按需打开。便携版移动目录后，请重新开启自启动。

更多行为说明见 [功能说明](docs/FEATURES.md)。

## 适配与验证范围

保留上游 **88 条 OPPO / 一加型号配置**（56 条 OPPO、32 条一加）。具体功能由耳机的产品 ID、协议能力和实际回读决定。

**目前真实硬件验证限 OPPO Enco X3，固件 143.143.39。** 其他型号有协议、配置与模拟测试覆盖，尚未逐一实机验证；不表示每个型号的全部功能均可使用。上游未实现的固件升级、完整听力校准和触控映射也不属于本项目已完成功能。

如果 Windows 音频连接正常，但控制会话持续超时，可先在 Windows 蓝牙设置中断开耳机后重连。该方法在 X3 上验证有效，尚未确定内部根因。

版本验证记录见 [VALIDATION.md](docs/VALIDATION.md)。报告中的模拟、真实设备、窗口和安装测试范围分别注明。

## 从源码运行

建议在 Windows 使用 Python 3.12 准备本地依赖；应用使用固定版本的官方嵌入式 Python 3.13.17，不改动系统 Python。

```powershell
python tools/prepare_python.py
python tools/prepare_qt.py
.\launch.cmd
```

只运行后台可使用 `launch.cmd --tray-only`，打开快捷控制可使用 `launch.cmd --quick`。依赖下载会校验固定 SHA-256。

## 构建安装包

构建 MSI 需要 **Windows Python 3.12**（包含 `msilib`）：

```powershell
python -m pip install --target .build-deps pefile==2024.8.26
python tools/prepare_python.py
python tools/prepare_qt.py
python tools/prepare_qt_licenses.py
python tools/build_desktop_release.py
```

输出位于本地 `release/`：MSI、便携 ZIP、源码 ZIP 和校验值。详细构建、许可证收集及检查命令见 [BUILD.md](docs/BUILD.md)。图形依赖动态链接，保留官方二进制与原始签名，不修改系统安全策略。

协议与状态测试不访问真实耳机：

```powershell
python -m unittest discover -s tests
```

当前有 83 项单元检查。`tools/verify_qt_live.py` 等真机工具会操作耳机设置，使用前请阅读构建说明。

## 许可证与来源

本项目代码采用 **GPL-3.0-or-later**。保留上游 OppoPodsManager 的版权与协议来源，感谢 Zhaoyi-ya 及上游贡献者。

Python、Qt / PySide6 等使用各自的许可证，相关文本与来源见 [第三方说明](THIRD_PARTY_NOTICES.md) 和 [licenses/](licenses/)。耳机产品图片保留各自权利人的权利，来源记录在 [图片清单](ui/assets/models/manifest.json)，不随软件代码重新授权。

本项目不隶属于 OPPO、一加或其关联公司。
