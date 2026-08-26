---
name: socialdrop-publish
description: Publish videos to all social platforms by dropping video+markdown files into a folder. Use when a user wants to publish, cross-post, or schedule a video to YouTube, TikTok, Instagram Reels, X, LinkedIn, Bluesky using socialdrop.
---

# socialdrop publish

Workflow:

1. Identify the drop folder. Each video needs a sibling markdown file with the same stem,
   e.g. `launch.mp4` + `launch.md`.
2. If the md file does not exist, create it from this template and fill it in
   (draft captions per platform if the user gives you a brief):

   ```markdown
   ---
   title: Short punchy title
   schedule: "2026-08-30 10:00 America/New_York"
   platforms:
     youtube: { visibility: public }
     tiktok: { privacy: PUBLIC_TO_EVERYONE, duet: true }
     instagram: { share_to_feed: true }
     x: { caption: "Hook written for X" }
     linkedin: { caption: "Professional framing" }
     bluesky: {}
   hashtags: [buildinpublic]
   ---

   Fallback description body used by platforms without a caption override.
   ```

3. Validate first: `socialdrop doctor <folder>`.
4. Publish now: `socialdrop publish <folder>` (add `--now` to ignore future schedules),
   or start live watching: `socialdrop watch <folder>`.
5. Read back the md file and show the user the Published table that was written into it.
6. If a platform row shows ❌ failed, read `.socialdrop/<stem>.state.json` for the error,
   explain it in plain language, fix what is fixable (auth, missing url, quota) and re-run.

Rules:
- Never edit the HTML comment markers around Published/Insights sections.
- Never retry more than `socialdrop` itself does; state prevents double posting.
- Respect rate limits: do not force-republish failing platforms repeatedly.
