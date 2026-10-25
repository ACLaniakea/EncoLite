# OPPO 协议移植记录

来源：相邻 `OppoPodsManager-upstream`，Copyright © 2026 Zhaoyi-ya，GPL-3.0-or-later。修改日期：2026-10-22。

## 会话与传输

Windows 通过系统已配对设备 API 发现 OPPO/Enco，使用 Winsock RFCOMM。优先查询 Melody 服务 `0000079A-D102-11E1-9B23-00025B00A5A5`，裸通道 1/15 是有界兼容回退，必须通过产品 ID 与能力握手。没有主动配对、注册表写入或常驻 PowerShell/.NET 辅助进程。

帧为 `AA length 00 00 commandLE F0 payloadLengthLE payload`，`length=7+payloadLength`，最大负载 248 字节。增量解码器处理分包、粘包、噪声及异常长度，残余缓冲区有界。正常响应命令为请求命令加 `0x8000`，状态 0 成功。

一个读取线程、一个串行工作队列。读线程只解析和更新状态，不发起请求。协议没有事务 ID，等待超时后关闭连接，防止迟到响应被误认为新请求结果。重连退避为 2～60 秒，手动断开停止重连；代次检查隔离旧连接通知。

## 控制入口

| 功能 | 查询 / 设置 | 上游依据 |
| --- | --- | --- |
| 产品/能力/固件 | 0103 / 0100 / 0105 | Managers/DeviceInfoManager.cs、CapabilityReader.cs |
| 电量/佩戴/编码 | 0106 / 0109 / 0114 | Features/Battery.cs、WearStatus.cs、DeviceInfoManager.cs |
| ANC | 010C / 0404 | Features/NoiseCancellation.cs、OppoManager.cs |
| 通用开关 | 010D / 0403 | Features/FeatureSwitches.cs 及各开关类 |
| 原厂 EQ | 010F / 0406 | Features/OppoEqualizerProfile.cs |
| 自定义 EQ | 0122 / 0418 | Features/CustomEqualizer.cs |
| 空间音频 | 012A / 0422 | Core/Features/SpatialAudio.cs、OppoManager.cs |
| 低音引擎 | 0124 / 041B | Features/BassEngine.cs |
| 游戏音效 | 012B / 0423 | Features/GameSound.cs、OppoManager.cs |
| 多设备 | 0112、0132 / 0429 | Features/MultiDevice.cs |
| 查找 | — / 0400 | Features/FindDevice.cs |
| 通知 | 0200 / 0205、0201 | Managers/Notifier.cs |

路径均相对于 `Control/Brands/Oppo`，另有明确标出的 Core 路径。

功能采用白名单与运行时能力位交集，未知产品不猜测控制能力。56 个 OPPO 配置由 `Assets/Oplus/Data/DeviceModels.json` 提取，支持三个兼容 EQ 配置字段、噪声父子分组、缺省 EQ 频段、游戏互斥项及旧产品 ID 别名。EQ 保留真实索引，例如 X3 是 0/1/2/3/7。

ANC 写入是 `[01 01 ...bitfield]`，写入索引与响应编码不同。X3 关闭0、通透8、人声通透9、智能7、轻6、中5、深4。kind=4 的实时智能强度通知保持主模式 Smart。ANC 不强制要求成功 ACK，而以回读为准；收到明确失败 ACK 则立即报告拒绝。X3 未佩戴时实测返回 0E。

电量 `0x80` 为充电，低七位为百分比；0 表示不在位。支持带数量、无数量及旧格式。功能查询必须带数量和功能 ID 列表；空查询在 X3 上不会返回开关。

自定义 EQ 读取频率、带符号增益范围、名称、ID 和选中状态；写入前校验型号频段、范围、名称及长度。新增/修改/删除后读取设备列表确认；保存后使用设备分配的 ID 启用。不会覆盖同名条目。试听是修改已有设备条目，并非本地音频 DSP。

空间音频为 0关闭、1固定、2头部跟踪；旧型号使用 1B 通用开关。游戏模式按设备状态选择 06 或 28。听力增强需同时声明 0115/040D 才开放已存设置的开关；不实现听力校准流程。低音引擎使用 `[min,max,current]` 专用负载；脊柱健康按上游规则不开放。

多设备地址解析与操作编码保持上游的方向规则；操作后回读确认。该写入路径尚无具备对应能力的真机验证，X3 不声明 0429，客户端只显示列表。

订阅实际消费的电量、佩戴、噪声、游戏与多设备事件；优先批量注册，不支持时逐项回退。0204、8202 和 0504 变更同步到共享会话，60 秒刷新补足其余状态。

## UI 与图片

托盘交互参考 `UI/Tray/TrayIcon.cs`、`UI/MiniWindow/SmallWindow.axaml`。0.5 使用自己的 Win32 托盘和按需启动的 Qt Quick 界面；主窗、快捷窗和托盘共享同一蓝牙会话，通过 UTF-8 JSON 管道交换状态与操作。Qt 无边框窗口使用 DWM 圆角和边线设置，无 HWND 子类钩子或常驻调整定时器。手动快捷窗持续显示，连接提示独立计时且不抢焦点；关闭最后一个窗口释放整个 Qt 进程。窗口位置、大小、最大化及页面合并保存到独立 `qt_main` / `qt_quick` 偏好，后台退出前等待位置回传。微软属性参考：[DWMWA_BORDER_COLOR](https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwmwindowattribute)。

图片按产品 ID 本地选择，当前含 31 个型号的官方图片，原始 URL 与型号关系在 `ui/assets/models/manifest.json`。缺图显示中性图标。官方示意色不代表读取到硬件配色；不查询或显示固定颜色文字。
