# Deploy public demo

We support **Render** (free tier) and **Railway** (paid) for the public demo.

---

## Option A: Render (recommended — free tier)

### Prerequisites
- GitHub repo connected to Render
- Render account (free tier: 750 hrs/mes, auto-sleep)

### Steps

1. **Create a new Web Service** in Render Dashboard → "New +" → "Web Service"
2. **Connect repo**: `DanielPPerez/socialdrop2.0`
3. **Configure**:
   - **Build Command**: `docker build -t socialdrop-api -f Dockerfile .`
   - **Start Command**: `docker run -p $PORT:8000 socialdrop-api`
   - **Environment**: Docker
   - **Instance Type**: Free

4. **Add Environment Variables** in Render dashboard:
   - `SOCIALDROP_API_KEY` — any random string
   - `SOCIALDROP_API_DROPS_FOLDER` — `/drops`
   - `FRONTEND_ORIGIN` — your Render frontend URL (e.g., `https://socialdrop-frontend.onrender.com`)
   - `SOCIALDROP_DISCORD_WEBHOOK` — optional

5. **Add Persistent Disk** (for `/drops` and `/root/.config/socialdrop`):
   - Settings → Disks → "Add Disk"
   - Name: `drops`, Mount Path: `/drops`, Size: 1 GB
   - Name: `tokens`, Mount Path: `/root/.config/socialdrop`, Size: 100 MB

6. **Deploy** — Render gives you `https://<name>.onrender.com`

### Frontend on Render (separate Static Site)
1. "New +" → "Static Site"
2. Connect same repo, **Root Directory**: `web`
3. Build Command: `npm ci && npm run build`
4. Publish Directory: `out` (configure `next.config.js` for `output: 'export'`)
5. Add env var: `NEXT_PUBLIC_API_URL` = your API URL

---

## Option B: Railway (paid — only 1 month trial)

### Prerequisites
- Railway CLI installed
- `railway login`
- A project created in Railway

### Steps

```bash
cd vendor/socialdrop
railway init
railway up
```

Railway detects `docker-compose.yml` and deploys both services.

### Environment variables
Set in Railway dashboard:
- `SOCIALDROP_API_KEY` — required, any random string
- `SOCIALDROP_API_DROPS_FOLDER` — `/drops`
- `FRONTEND_ORIGIN` — your public frontend URL
- `SOCIALDROP_DISCORD_WEBHOOK` — optional, for notifications

### Volumes
- `drops` -> `/drops` (persisted videos and sidecars)
- `tokens` -> `/root/.config/socialdrop` (persisted keyring fallback)

### Custom domain
Railway provides a `*.railway.app` domain. You can add a custom domain in **Settings > Domains**.
