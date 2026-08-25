# A426 Research Workbench

这是 A426 上经过提炼的科研工具开发仓库。它集中维护已经跨任务复用或准备长期维护的效率应用、科研分析工具、自动化流程、Codex Skills 和全局协作规则源码；科研资料和课题专用探索代码保存在相邻的 `每日实验总结/library/`，不进入本仓库 Git。

## 目录

```text
apps/
  daily-record-dashboard/       每日自由画布记录
  conference-recorder/          Android 会议采集 App
  network-assistant/            电脑诊断服务与 Android 组件
research/
  analysis/                     通用科研分析和可视化工具
workflows/                      日、周、月及会议整理自动化
skills/
  AGENTS.md                     Skill 开发规则
  _template/                    新 Skill 的最小模板
  <skill-name>/                 Skill 源码、参考资料、脚本和测试
codex-config/
  global-agent/AGENTS.md        全局协作规则的唯一源码
```

这里的 `workflows/` 指“把已有记录加工成某种输出的自动化程序”，而不是总结正文。比如周六在科研资料库项目中发起周总结，程序源码在本仓库 `workflows/`，结果写到 `每日实验总结/library/summaries/weekly/`。

## 资料边界

- 科研资料根：`../每日实验总结/library/`
- 每日画布数据：`../每日实验总结/library/daily-records/`
- W 盘及其同源映射只读。
- 原始数据、图片、录音、报告正文、生成结果、缓存、密钥和本机配置不得提交。
- 每个工具必须使用显式输出路径或环境变量；缺失时清晰报错，不得默认把产物写进仓库。

群晖同步完成后，推荐环境变量：

```powershell
DAILY_NOTE_DATA_ROOT   = E:\higs\实验记录\新时代\每日实验总结\library
DAILY_DRAFT_DATA_ROOT = E:\higs\实验记录\新时代\每日实验总结\library\daily-records
```

在新的 `library/` 同步任务完成验证前，不要切换现有环境变量。

## 常用入口

- 每日记录：`apps/daily-record-dashboard/start_daily_record_dashboard.bat`
- 网络诊断：`apps/network-assistant/desktop-service/start_network_diagnostics.bat`
- 交互数据查看：`research/analysis/interactive-plot-viewer/start_interactive_plot_viewer.bat`
- 每日草稿：`workflows/daily-summary/run_nightly_daily_draft.bat`
- 会议记录 App：见 `apps/conference-recorder/README.md`

## Skill 与全局规则

- `skills/` 是开发位置；经过真实任务验证后，再安装到 Codex 的全局 Skills 目录。
- 一次性或课题专用分析代码先留在科研资料库对应任务目录；确认跨任务复用后再提升到本仓库。
- `skills/AGENTS.md` 约束 Skill 的拆分、描述、测试和维护。
- `skills/_template/` 只提供最小骨架，不会被识别为已安装 Skill。
- `codex-config/global-agent/AGENTS.md` 是全局规则源码；用户目录中的安装副本不是维护入口。
- 使用中发现 Skill 需要改进时，回到本仓库修改源码并测试，再更新安装副本；不要直接维护两份漂移的内容。
