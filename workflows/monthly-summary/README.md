# 月度工作总结

`write_monthly_work_summary.py` 从显式指定的 campaign、周报和其他外部记录中生成月度 Markdown。所有输入和输出路径都必须通过参数给出。

```powershell
python workflows\monthly-summary\write_monthly_work_summary.py `
  --campaign-root "<campaign-root>" `
  --weekly-report "<weekly-report.md>" `
  --photoacoustic-root "<photoacoustic-root>" `
  --month 2026-08 `
  --output "<external-output.md>"
```

默认拒绝覆盖已有输出；只有明确传入 `--force` 才会覆盖。
