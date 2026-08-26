---
name: socialdrop-schedule
description: Plan or adjust the publishing calendar for socialdrop drop folders. Use when a user asks when videos will go out, wants to stagger posts across days/platforms, or asks about timezones in schedules.
---

# socialdrop scheduling

- Schedule lives in each md frontmatter as `schedule:` with an explicit timezone:
  `schedule: "2026-08-30 10:00 America/New_York"`. No timezone = validation error.
- Empty string `schedule: ""` means publish immediately on next scan/watch cycle.
- To see what is queued, read the `platforms:` keys of each md file and its
  `.socialdrop/<stem>.state.json` status.
- Best practice for cross-posting: jitter times a few minutes apart per platform batch
  to avoid spam-signal correlation. Suggest this proactively when the user schedules
  many videos at the same instant.
- After editing schedules, run `socialdrop doctor <folder>` to validate.
