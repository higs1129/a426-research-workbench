# Nightly Daily Draft

Conservative helper for writing campaign-local daily drafts from file timestamps.

It scans:

```text
<DATA_ROOT>/experiments/
```

and writes or updates:

```text
<DATA_ROOT>/experiments/<campaign>/daily/YYYY-MM-DD.md
```

The generated content is an activity index only. It does not infer experimental
validity or conclusions from timestamps.

## Manual Run

```powershell
workflows\daily-summary\run_nightly_daily_draft.bat --data-root "$env:DAILY_NOTE_DATA_ROOT"
```

For a specific date:

```powershell
workflows\daily-summary\run_nightly_daily_draft.bat --data-root "$env:DAILY_NOTE_DATA_ROOT" --date 2026-06-21
```

Preview without writing:

```powershell
workflows\daily-summary\run_nightly_daily_draft.bat --data-root "$env:DAILY_NOTE_DATA_ROOT" --date 2026-06-21 --dry-run
```

## Install Windows Scheduled Task

After manual dry-runs look reasonable:

```powershell
workflows\daily-summary\install_nightly_daily_draft_task.bat
```

Defaults:

- task name: `DailyNoteNightlyDraft`
- time: `23:00`
- data root: `DAILY_NOTE_DATA_ROOT`

To override:

```powershell
workflows\daily-summary\install_nightly_daily_draft_task.bat -DataRoot "$env:DAILY_NOTE_DATA_ROOT" -At 23:00
```

## Safety Behavior

- Existing human-written content is preserved.
- The script only replaces its own block between:
  - `<!-- auto-daily-start -->`
  - `<!-- auto-daily-end -->`
- Files under `daily/` are ignored while scanning, so the script does not trigger
  itself.
- Raw data and generated figures are never modified.
