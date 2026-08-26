# socialdrop

**Drop a video and a markdown file into a folder. Every platform publishes itself.**

socialdrop is an open-source, local-first publishing pipeline for short-form and
long-form video. It watches a folder, reads a markdown sidecar for metadata and
scheduling, publishes to every configured platform through official APIs, and
writes results plus consolidated performance insights back into the same file.

```markdown
---
title: My launch video
schedule: 2026-08-30 10:00 America/New_York
platforms:
  youtube: { visibility: public }
  tiktok:  { privacy: PUBLIC_TO_EVERYONE, duet: true }
  x:       { caption: "Different hook for X" }
  bluesky: {}
hashtags: [buildinpublic]
---
```

Drop `my-launch-video.mp4` next to it and run `socialdrop watch`. The md file
fills itself in with per-platform links, then a live Insights table:

| Platform | Views | Likes | Comments | Shares |
|---|---|---|---|---|
| youtube | 12.4k | 890 | 45 | — |
| tiktok | 45k | 3.1k | 210 | 890 |

## Install

```bash
pipx install socialdrop            # core
pipx inject socialdrop socialdrop[youtube,bluesky,watch]   # optional extras
```

## Quickstart (no accounts needed)

```bash
socialdrop demo
```

Creates `demo/`, generates a sample video, "publishes" it to the built-in
mock platform, and writes the Published + Insights tables back into the md file.

## Connect real platforms

| Platform | How auth works | Notes before first publish |
|---|---|---|
| YouTube | OAuth (`socialdrop auth login youtube`) | Unaudited apps upload as private; request a compliance audit to go public |
| TikTok | OAuth | Direct Post requires an audited client; otherwise private-only |
| Instagram | OAuth via Meta | Needs an IG Business/Creator account + Meta app review |
| X | OAuth PKCE | Pay-per-use credits on your own account |
| LinkedIn | OAuth (`w_member_social`) | Personal posts work self-serve; Company Pages need partner approval |
| Bluesky | App password only | Fully open, no review; never your main password |

Passwords are **never** stored or transmitted. Tokens live in your OS keyring
(fallback: 0600 file) and are refreshed automatically.

## CLI

```
socialdrop doctor              # what is set up, what is missing
socialdrop auth login <p>      # connect a platform
socialdrop publish [folder]    # publish everything due now
socialdrop watch [folder]      # live folder watching
socialdrop stats [folder]      # refresh Insights tables
socialdrop demo                # end-to-end mock run
```

## Markdown sidecar schema

Frontmatter keys:

- `title` (required): default title everywhere.
- `schedule` (optional): `YYYY-MM-DD HH:MM TZ`, e.g. `2026-08-30 10:00 Europe/Berlin`.
- `platforms` (required): map of platform → config. Per-platform keys:
  - `caption`: overrides title/description for that platform.
  - `url`: public video URL (Instagram requires this unless rupload succeeds).
  - `hashtags`: platform-specific tags; falls back to global list.
  - platform extras: `visibility` (youtube), `privacy`/`duet` (tiktok), etc.
- `hashtags` (optional): global tags merged into captions.

The body of the file is the fallback description.

After publishing, socialdrop appends idempotent `Published` and `Insights`
sections (marked with HTML comments) so re-runs update rather than duplicate.

## Agents welcome

socialdrop is built agent-first: thin deterministic CLIs any LLM can drive.

- Claude Code skills live in [`skills/`](skills/) — copy into `~/.claude/skills/`.
- MCP server in [`mcp/`](mcp/) exposing `list_drops`, `publish`, `get_stats`.
- GPT Actions OpenAPI spec in [`gpt-actions/openapi.yaml`](gpt-actions/openapi.yaml).

## Why official APIs only

Browser automation gets accounts banned. Every adapter here uses the platform's
sanctioned OAuth APIs, so worst case is a delayed feature while an audit is
pending — never a banned account.

## License

MIT
