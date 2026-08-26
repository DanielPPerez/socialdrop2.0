---
name: socialdrop-analytics
description: Pull consolidated per-video performance metrics from all connected platforms into the markdown sidecars. Use when a user asks how their videos are performing across YouTube, TikTok, Instagram, X, LinkedIn, Bluesky.
---

# socialdrop analytics

1. Refresh metrics: `socialdrop stats <folder>`.
   This writes/updates an `## Insights` table inside each `<video>.md` with views,
   likes, comments, shares and watch % per platform plus a sync timestamp.
2. Read the md files and summarize results for the user. Highlight:
   - best performing platform per video (by views),
   - videos where one platform dramatically over/under-performs the others,
   - total cross-platform views across the folder.
3. For deeper questions, read raw numbers from the Insights tables rather than guessing.
4. If metrics are missing for a platform, check that the video actually published there
   (see the Published table / `.socialdrop/<stem>.state.json`) before reporting zeros.
5. Offer a recurring sync suggestion: cron `socialdrop stats <folder>` daily.
