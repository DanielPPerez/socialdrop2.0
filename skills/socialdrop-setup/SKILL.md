---
name: socialdrop-setup
description: Connect social media platform accounts for the socialdrop publishing tool. Use when a user wants to authenticate YouTube, TikTok, Instagram, X, LinkedIn, or Bluesky for video publishing, or asks what is set up.
---

# socialdrop setup

socialdrop must be installed (`pipx install socialdrop`) before running any command.

1. Run `socialdrop doctor` in the user's drop folder. Report the table it prints.
2. For each platform the user wants:
   - **Bluesky**: ask for their handle and an app password (create at bsky.app settings).
     Never accept or store their main password. Set env vars `SOCIALDROP_BLUESKY_HANDLE`
     and `SOCIALDROP_BLUESKY_APP_PASSWORD`, then run one publish to cache the session.
   - **YouTube / TikTok / Instagram / X / LinkedIn**: these use browser OAuth.
     The user needs developer-app credentials first. Tell them which env var to set
     (`SOCIALDROP_<PLATFORM>_CLIENT_ID`, optionally `_CLIENT_SECRET`), then run
     `socialdrop auth login <platform>` — it opens the browser and stores the token
     in the OS keyring. Never ask for platform passwords; they are never stored.
3. Warn about audit gates that apply before approval:
   - YouTube uploads are private until Google's compliance audit passes.
   - TikTok direct posts are private-only until the client audit passes.
   - Instagram requires a Business/Creator account and Meta App Review.
4. Re-run `socialdrop doctor` and confirm every requested platform shows ✅.
