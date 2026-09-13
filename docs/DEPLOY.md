# Deploy public demo

We use **Railway** for the public demo because it runs Docker Compose natively,
gives us a public URL in minutes, and fits the portfolio use-case.

## Prerequisites

- Railway CLI installed
- `railway login`
- A project created in Railway

## Steps

```bash
cd vendor/socialdrop
railway init
railway up
```

Railway detects `docker-compose.yml` and deploys both services.

## Environment variables

Set in Railway dashboard:

- `SOCIALDROP_API_KEY` — required, any random string
- `SOCIALDROP_API_DROPS_FOLDER` — `/drops`
- `FRONTEND_ORIGIN` — your public frontend URL
- `SOCIALDROP_DISCORD_WEBHOOK` — optional, for notifications

## Volumes

- `drops` -> `/drops` (persisted videos and sidecars)
- `tokens` -> `/root/.config/socialdrop` (persisted keyring fallback)

## Custom domain

Railway provides a `*.railway.app` domain. You can add a custom domain in
**Settings > Domains**.
