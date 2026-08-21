# Network Assistant

网络助手由两个独立但配套的组件组成：

- `desktop-service/`：运行在 A426 上的网络状态与 Codex 任务诊断服务。
- `android-widget/`：运行在 vivo Android 手机上的查看与控制组件。

二者保留独立构建和测试入口，避免桌面端依赖与 Android 工程混杂。
