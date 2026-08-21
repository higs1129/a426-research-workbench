# A426 Research Workbench

这是 A426 上的科研工作台代码仓库。它集中保存个人效率应用、科研分析工具、总结 workflow 和 Codex skills；实验数据、图片、录音、报告正文和生成结果不进入 Git。

## 目录

```text
apps/
  daily-record-dashboard/       每日自由画布记录
  conference-recorder/          Android 会议采集 App
  network-assistant/            电脑诊断服务与 Android 组件
research/
  analysis/                     通用科研分析工具
workflows/
  daily-summary/                每日草稿与定时任务
  monthly-summary/              月度工作总结生成器
skills/                         Codex 协作与科研记录规则
```

每个应用和 workflow 都是独立子项目，保留自己的 README、测试和启动入口。它们只是集中存放，不共享隐含运行状态。

## 数据边界

- `DAILY_NOTE_DATA_ROOT` 指向外部科研资料根目录。
- `DAILY_DRAFT_DATA_ROOT` 指向每日自由画布的数据目录。
- W 盘及其别名只作为只读数据源。
- 本机配置使用被忽略的 `*.local.json`、环境变量或各工具声明的本地配置文件。
- `experiments/`、`notes/`、`reports/`、`literature/`、录音、图片和生成结果不得提交。

示例环境变量见 [config.local.example.json](config.local.example.json)。

## 常用入口

- 每日记录：`apps/daily-record-dashboard/start_daily_record_dashboard.bat`
- 网络诊断：`apps/network-assistant/desktop-service/start_network_diagnostics.bat`
- 交互数据查看：`research/analysis/interactive-plot-viewer/start_interactive_plot_viewer.bat`
- 每日草稿：`workflows/daily-summary/run_nightly_daily_draft.bat`

会议记录 App 是独立 Android 工程，构建说明见 `apps/conference-recorder/README.md`。
