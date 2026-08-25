---
name: research-progress-summary
description: Generates concise, evidence-linked weekly, monthly, or yearly research progress summaries from daily records, experiments, research notes, meetings, and deliverables. Use for 周总结、月总结、年总结、阶段科研进展回顾 or research progress reports. Do not use for writing daily canvas entries, cleaning a single day's notes, summarizing one paper or meeting, or drafting a manuscript.
metadata:
  version: "1.0"
  skill-author: "Personal Research Workflow"
---

# Research Progress Summary

## 目的与边界

把分散的科研记录压缩成可追溯、便于复盘的周期总结。每日画布是原始输入之一，不在本 Skill 中生成日总结。

本 Skill 只形成周期性科研进展底稿，不替代单篇论文写作、单场会议总结、单篇文献解读或当天画布记录。评优、答辩和申请材料应在事实底稿形成后另行适配目标模板。

## 何时使用

- 应触发：周总结、月总结、年总结、阶段科研进展回顾，以及需要跨多类记录形成周期性证据链的请求。
- 不应触发：录入或润色当天画布、只整理一个实验/会议/文献、撰写论文正文，或仅列待办事项。

## 可复现工作流

1. 明确总结类型、起止日期、目标读者和是否需要落盘。用户未给日期时，根据“本周、本月、本年度”等自然语言推定，并明确写出范围。
2. 读取 [references/source-routing.md](references/source-routing.md)，根据用户明确资料、项目规则和数据根定位证据。
3. 只读取对应时间尺度的模式文件，按研究主线归并资料，而不是按文件夹或日期机械拼接。
4. 对关键进展核验事实、数字、状态和来源，区分完成、进行中、待验证和计划。
5. 生成简洁中文 Markdown，并保留代表性来源路径或链接。
6. 按“证据与验证”完成自查；用户只要求查看时在聊天中提供草稿，用户要求落盘时再遵循项目路由写入文件。

### 时间尺度路由

先确定用户要求的时间范围，只读取对应模式的参考文件：

- 周总结：读取 [references/weekly.md](references/weekly.md)。
- 月总结：读取 [references/monthly.md](references/monthly.md)。
- 年总结：读取 [references/yearly.md](references/yearly.md)。

不要因为存在多个模式就一次加载全部参考文件。

## 证据与验证

- 以用户明确提供的资料和项目 `AGENTS.md` 指定的数据根为准；找不到可靠资料时说明缺口，不从文件时间、运行日志或目录缺失反推科研事实。
- 区分事实/观察、用户判断、推导、AI 建议和待确认事项。推导必须标注依据，不能把计划写成已完成。
- 周报、月报、年报是不同压缩层级，不是逐级机械拼接。下一级总结可作为索引，但关键结论仍应回到代表性证据核验。
- 保留关键来源路径或文档链接，使成果、数字和判断可回溯；不要把全部文件清单堆进正文。
- 优先写实质进展、证据、问题、决策和下一步，压缩过程闲聊、重复尝试和无结论的工具操作。
- 篇幅随有效信息量变化；资料少时不要用模板制造空内容，资料多时按研究主线归并。
- 默认使用简洁中文 Markdown；表格只用于确有比较关系的数字、任务或证据。
- 用户要求落盘时，遵循当前科研资料库的项目路由，将成品写入对应的 weekly、monthly 或 yearly 目录，并保留来源索引。
- 生成后做一次证据检查：日期范围正确、完成与计划未混淆、关键数字有来源、没有把 AI 建议伪装成科研结论。

## 常见失败模式

- 把周报写成逐日流水账，或把月报、年报写成下一级总结的拼接。
- 只依据文件数量、修改时间或操作次数判断科研进展。
- 把计划、AI 建议、推测或尚未核验的数字写成已完成结论。
- 依赖已有总结而不回查代表性证据，导致错误逐级放大。
- 为填满固定模板制造空内容，或把完整文件清单堆进正文。
- 用户未要求落盘时擅自写文件，或覆盖已有成品而未核对项目规则。

## 参考资料

- [references/source-routing.md](references/source-routing.md)：定位资料、判断证据层级和生成来源索引时读取。
- [references/weekly.md](references/weekly.md)：仅在生成周总结时读取。
- [references/monthly.md](references/monthly.md)：仅在生成月总结时读取。
- [references/yearly.md](references/yearly.md)：仅在生成年总结时读取。
