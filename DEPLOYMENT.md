# Deployment Guide

Deploy the full stack to free-tier cloud services. Total time: ~30 minutes.

| Service | Purpose | Cost |
|---|---|---|
| [Neon](https://neon.tech) | PostgreSQL database | Free, persistent, serverless |
| [Render](https://render.com) | FastAPI backend + Redis | Free (sleeps after 15 min) |
| [Vercel](https://vercel.com) | React frontend | Free, always-on |

---

## Step 1: Neon PostgreSQL

1. Go to [neon.tech](https://neon.tech) → create a free account.
2. New project → name it `protein-intelligence`.
3. Copy the **Connection string**. It looks like:
   ```
   postgresql://user:password@ep-xxx.us-east-1.aws.neon.tech/neondb?sslmode=require
   ```
4. Save it — you'll need it in Step 2.

> **Why not Render Postgres?** Render's free PostgreSQL is deleted after 90 days. Neon is persistent indefinitely and has no cold-start issues.

---

## Step 2: Render Backend + Redis

### 2a. Create Redis

1. Render dashboard → New → Redis.
2. Name: `protein-intelligence-redis`, plan: Free.
3. Copy the **Internal Redis URL** (looks like `redis://red-xxx:6379`).

### 2b. Create Web Service

1. Render dashboard → New → Web Service.
2. Connect your GitHub repo.
3. Settings:
   - **Root directory:** `backend`
   - **Runtime:** Python 3
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Health check path:** `/api/v1/health`
4. Environment variables (add all of these):

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | Your Neon connection string (the `postgresql://...` one — it auto-converts to asyncpg) |
   | `REDIS_URL` | Internal Redis URL from Step 2a |
   | `ALLOWED_ORIGINS` | `https://YOUR_VERCEL_URL` (fill in after Step 3, then redeploy) |
   | `DEBUG` | `false` |
   | `PYTHON_VERSION` | `3.11.0` |

5. Deploy. First deploy runs Alembic migrations automatically.
6. Note your backend URL: `https://protein-intelligence-api.onrender.com` (or similar).

---

## Step 3: Vercel Frontend

1. Go to [vercel.com](https://vercel.com) → New Project → Import GitHub repo.
2. Settings:
   - **Framework preset:** Vite
   - **Root directory:** `frontend`
   - **Build command:** `npm run build`
   - **Output directory:** `dist`
3. Environment variable:

   | Key | Value |
   |---|---|
   | `VITE_API_URL` | Your Render backend URL from Step 2 |

4. Deploy. Vercel gives you a URL like `https://protein-intelligence.vercel.app`.

---

## Step 4: Update CORS on Render

1. Go to Render dashboard → your backend service → Environment.
2. Update `ALLOWED_ORIGINS` to your actual Vercel URL:
   ```
   https://protein-intelligence.vercel.app
   ```
   (comma-separated if you need multiple: `https://your-vercel-url.vercel.app,http://localhost:3000`)
3. Render auto-redeploys.

---

## Step 5: Update README

In `README.md`, replace:
- `GITHUB_USERNAME` → your GitHub username
- `YOUR_VERCEL_URL` → your actual Vercel URL
- `YOUR_RENDER_URL` → your actual Render URL

Commit and push. The build badge will then be live.

---

## Step 6: Verify Deployment

Run these commands to confirm everything works end-to-end:

```bash
# Replace YOUR_RENDER_URL with your actual Render backend URL

# 1. System health (DB + Redis + FAISS status)
curl https://YOUR_RENDER_URL/api/v1/health

# 2. Protein fetch from UniProt
curl https://YOUR_RENDER_URL/api/v1/protein/TP53

# 3. Mutation analysis with ClinVar
curl https://YOUR_RENDER_URL/api/v1/mutation/TP53/R175H

# 4. Protein comparison (Smith-Waterman + ESM2)
curl https://YOUR_RENDER_URL/api/v1/compare/TP53/TP63

# 5. Sequence alignment
curl https://YOUR_RENDER_URL/api/v1/align/TP53/BRCA1

# 6. API docs (opens in browser)
open https://YOUR_RENDER_URL/docs
```

All should return JSON. If any fail:
- Check Render logs: dashboard → your service → Logs tab
- Confirm `DATABASE_URL` starts with `postgresql://` or `postgresql+asyncpg://` (both work — the backend auto-converts)
- Confirm `ALLOWED_ORIGINS` matches your exact Vercel URL (no trailing slash)

---

## Render Free Tier Note

The free tier spins down after 15 minutes of inactivity. The first request after sleep takes ~30 seconds (cold start). Before recording a demo video, warm up the backend:

```bash
curl https://YOUR_RENDER_URL/api/v1/health
```

Wait for a response, then start recording. To avoid cold starts permanently, upgrade to Render Starter ($7/month).

---

## Environment Variables Reference

**Render backend:**

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | Neon connection string |
| `REDIS_URL` | Yes | Render Redis internal URL |
| `ALLOWED_ORIGINS` | Yes | Comma-separated frontend URL(s) |
| `DEBUG` | No | Default: `false` |
| `PYTHON_VERSION` | No | Default: `3.11.0` |
| `NCBI_API_KEY` | No | Increases ClinVar rate limits. Free at ncbi.nlm.nih.gov |

**Vercel frontend:**

| Variable | Required | Description |
|---|---|---|
| `VITE_API_URL` | Yes | Your Render backend URL (no trailing slash) |
