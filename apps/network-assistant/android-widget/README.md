# 链路助手（Android）

本目录是一个无第三方运行时依赖的原生 Android 小工具，用于把 Tailscale 与 Clash Meta for Android 的状态检测和切换入口放在同一个界面，并提供桌面小组件。

## 当前能力

- 识别当前 Android VPN 是 Tailscale、Clash Meta、其他 VPN 或未启用。
- Tailscale 启用时，通过 A426 的只读诊断接口显示 IPv6/IPv4 直连、Peer Relay、DERP，以及到 A426 首段的 P50、P95、抖动和丢包。
- 提供群晖 UDP 40000 探针：显式绑定手机的 5G、Wi-Fi 或有线物理网络，绕过当前 Android VPN，向 Microcavities 连续发送三个带探针 ID 的测试包；应用只确认本机发送，是否抵达仍以群晖抓包为准。
- 在手机当前 VPN 路径上对 ChatGPT 网络入口进行三次 HTTPS 探测，避免把“到 A426 的延迟”误当作完整 Remote 链路；该探测只判断网络层可达性，不读取登录状态，也不能保证 Remote 会话本身已经建立。
- 读取 Clash 本机控制接口 `127.0.0.1:9090` 的运行模式、策略选择链、实际叶子节点和节点延迟。
- 从统一界面请求切换到 Tailscale（并选择 A426 Exit Node）或 Clash Meta。
- 默认在切换到 Clash 时，将外层 Selector 指向其中的 URL-Test 自动组、清除自动组残留的固定节点，并回读验证；可以在主界面关闭这一行为以保留上次手选节点。
- 桌面小组件显示最近一次检测结果；点按小组件进入应用并刷新。
- 提供独立的 Codex 任务 `4×2` 小组件，通过 A426 的 Tailnet 只读接口分行显示最多四项任务；超过四项时显示剩余数量。
- 任务状态分为“运行中、已完成、已停止”，接口不可达时保留最近一次成功结果。
- 点击 Codex 组件时，使用 ChatGPT Remote 的 HTTPS App Link 并显式指定 `com.openai.chatgpt`，直接进入 ChatGPT App；不再复用可能被系统解析到浏览器的通知入口。
- 当 A426 上的任务首次变为“已完成”时，链路助手生成“任务名 + A426”的独立高优先级通知，可由 vivo 健康通过蓝牙同步到 WATCH GT；同一完成事件重复刷新不会反复提醒。
- ChatGPT 通知到达后会在约 1、5、15 秒进行短时复查；只提醒五分钟内完成的新任务，恢复连接后不会补发很久以前的完成事件。
- A426 同步失败或状态超过两分钟时，组件会隐藏缓存中的旧任务并显示“状态待同步”，不再把过期状态误标为运行中。
- 主界面提供完成提醒总开关和“发送手表测试通知”按钮。首次升级只记录现有完成任务作为基线，不补发历史提醒。

## 隐私与边界

- Clash Secret 只写入 Android 应用私有的 `SharedPreferences`，不进入源码、APK 常量或 A426。
- 自动选择只通过手机回环地址上的 Mihomo API 修改当前运行策略，不改订阅文件，也不把 Secret 发给 A426。
- 应用不申请文件、通讯录、定位、相机或麦克风权限。
- Codex 状态组件通过 HTTPS 从 A426 获取短标题、状态与更新时间，不接收提示词、回答正文、路径或线程 ID。Android“通知使用权”只用于捕获 ChatGPT 的 Remote 入口和触发及时刷新；实现仍仅处理包名为 `com.openai.chatgpt` 的通知。
- 手表提醒由链路助手在手机本地生成；应用不直接访问手表、健康数据或蓝牙内容。是否转发到手表由 vivo 健康的应用通知开关控制。
- Android 同一用户空间只能有一个 `VpnService` 处于准备/活动状态；切换时目标应用仍可能弹出系统 VPN 授权。
- 由于目标应用升级后可能调整外部控制入口，失败时应回到 Tailscale 或 Clash 官方应用完成一次授权，再重试。

## 本地构建

需要 JDK 17、Android SDK Platform 35 和 Build Tools 35.0.0。当前版本为 `0.5.1`：

```powershell
gradle --no-daemon assembleDebug lintDebug
```

APK 输出位于 `app/build/outputs/apk/debug/app-debug.apk`，该目录被 Git 忽略。
