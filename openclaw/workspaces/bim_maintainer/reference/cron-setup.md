# Cron Setup - Bonsai AI Maintainer

## Overview

The maintainer runs once daily on a cron schedule to keep the codebase knowledge graph current. It checks recent git history, updates stale knowledge files, maintains the codebase state snapshot, and looks for new improvement backlog items.

## Cron Job

### Add the job

```bash
openclaw cron add \
  --name "bim_maintainer_daily" \
  --agent bim_maintainer \
  --at "6:00 AM" \
  --tz "America/Denver" \
  --session isolated \
  --thinking high \
  --timeout-seconds 300 \
  --message "Daily maintenance run. Follow the daily knowledge maintenance checklist:

1. Run git -C /Users/alanknudson/Applications/Bonsai_ai log --oneline -20 to see recent changes since your last run.
2. Read your most recent memory/YYYY-MM-DD.md to know what was already reviewed.
3. For each changed file: read it, then update the corresponding knowledge/modules/*.md or knowledge/patterns/*.md entry. Update the 'Last reviewed' date.
4. Update knowledge/index.md if any modules were added, removed, or renamed.
5. Update reference/codebase-state.md with any changes to module sizes, architecture, or key findings.
6. Check reference/improvement-backlog.md -- if you spot new bugs, tech debt, or gaps during your review, add them. If any existing items have been resolved, check them off.
7. Write a compact summary to memory/YYYY-MM-DD.md (today's date) covering: files reviewed, knowledge files updated, new backlog items added, anything notable.

Stay focused on knowledge maintenance. Do not make code changes. Do not propose refactors unless adding them to the backlog. Keep the memory entry under 30 lines."
```

### Why this schedule

- **Once daily at 6:00 AM** -- runs before the user starts working, so knowledge is fresh when the day begins.
- **Isolated session** -- does not pollute the main session's context or memory.
- **High thinking** -- the maintainer needs to reason about code changes and decide which knowledge files are stale.
- **5-minute timeout** -- enough time for a thorough scan of recent changes without risk of runaway sessions.

The codebase changes only when the user actively works on it, so once daily is sufficient. If the project enters a heavy development phase, a second run can be added in the evening.

## Managing the Cron Job

### List all jobs

```bash
openclaw cron list
```

### List including disabled jobs

```bash
openclaw cron list --all
```

### Check scheduler status

```bash
openclaw cron status
```

### View run history

```bash
openclaw cron runs
```

### View runs for this specific job

```bash
openclaw cron runs --id <job-id>
```

### Temporarily disable

```bash
openclaw cron disable <job-id>
```

### Re-enable

```bash
openclaw cron enable <job-id>
```

### Remove entirely

```bash
openclaw cron rm <job-id>
```

### Test run (execute now without waiting for schedule)

```bash
openclaw cron run <job-id>
```

## Adjusting the Schedule

To change the time, edit the existing job:

```bash
openclaw cron edit <job-id> --at "7:00 AM" --tz "America/Denver"
```

To switch to a cron expression for more control:

```bash
openclaw cron edit <job-id> --cron "0 6 * * *" --tz "America/Denver"
```

## Adding a Second Daily Run (Optional)

If the codebase is changing rapidly (e.g., during a multi-day feature build), add an evening catchup:

```bash
openclaw cron add \
  --name "bim_maintainer_evening" \
  --agent bim_maintainer \
  --at "6:00 PM" \
  --tz "America/Denver" \
  --session isolated \
  --thinking high \
  --timeout-seconds 300 \
  --message "Evening maintenance catchup. Same checklist as the morning run -- see reference/cron-setup.md for details. Focus on changes made today that the morning run did not cover."
```
