# End-to-end usage

## Prerequisites

- Docker + Docker Compose
- `ffmpeg` installed locally (for demo video generation)

## 1. Start the stack

```bash
cd vendor/socialdrop
docker compose up --build
```

Wait for:
- Frontend at `http://localhost:3000`
- API docs at `http://localhost:8001/docs`

## 2. Connect a platform (optional)

Go to **Platforms** and click **Conectar** for YouTube (or any other).
Complete the OAuth flow. For the demo, you can skip this step.

## 3. Create a drop

1. Open **New Drop**
2. Drag a video file (`.mp4`, `.mov`, `.webm`)
3. Fill title and description
4. (Optional) Click **Sugerir con IA** to auto-generate metadata from the video
5. Select platforms
6. Review the sidecar preview
7. Click **Create Drop**

## 4. Publish

- Click **Publicar ahora** in the drop detail page
- Watch the live status update via SSE
- After publish, the **Published** table shows per-platform URLs

## 5. Insights

- Click **Refresh insights**
- The **Insights** table fills with views, likes, comments, shares

## Automation with Drive / n8n

If you store videos in Google Drive:

1. Use a Drive trigger in n8n to watch a folder
2. On new file, call `POST /api/v1/drops` with the video and metadata
3. n8n can read a JSON sidecar from Drive and forward it as `drop_create`

Example n8n HTTP Request node body (form-data):
- `video`: binary from Drive
- `drop_create`: JSON string with title, platforms, hashtags
