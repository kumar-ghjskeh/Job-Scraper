# Deploying Job Scraper

Architecture: **Vercel** hosts the React frontend, **Render** hosts the Python
backend (FastAPI + APScheduler) and a managed **Postgres** database. The backend
auto-scrapes the verified company APIs 4× per day and the frontend reads from it.

```
 Browser ──> Vercel (frontend)  ──HTTPS──>  Render (FastAPI + scheduler) ──> Postgres
```

---

## 1. Push to GitHub

```bash
cd "D:\Job Scraper\rtl-dv-job-radar"
git init
git add .
git commit -m "Job Scraper: verified API scraping + LinkedIn-grade UI"
git branch -M main
git remote add origin https://github.com/<you>/job-scraper.git
git push -u origin main
```

## 2. Backend + Database on Render

1. Go to <https://render.com> → **New → Blueprint** → connect this repo.
2. Render reads `render.yaml` and creates:
   - `job-scraper-db` (free Postgres)
   - `job-scraper-api` (free web service) with `DATABASE_URL` wired in.
3. After it deploys, open the service URL (e.g. `https://job-scraper-api.onrender.com/health`)
   — it should return `{"status":"ok"}`.
4. In the service's **Environment**, set:
   - `CORS_ORIGINS=https://<your-project>.vercel.app`
   - `RUN_SCRAPE_ON_STARTUP=true` (populates the DB on first boot)

> Free Render web services sleep after 15 min idle, which pauses the scheduler.
> To keep scrapes running, add a free uptime pinger (e.g. cron-job.org) hitting
> `https://job-scraper-api.onrender.com/health` every 10 min, and optionally
> `POST /scrape/run-now` on a schedule.

## 3. Frontend on Vercel

1. Go to <https://vercel.com> → **Add New → Project** → import this repo.
2. Set **Root Directory** to `frontend`.
3. Add an environment variable:
   - `VITE_API_BASE = https://job-scraper-api.onrender.com`
4. Deploy. Vercel auto-detects Vite (`frontend/vercel.json`).

## 4. Verify

- Open the Vercel URL → the dashboard loads jobs from Render.
- Click **Run Scrape** → new jobs appear within a minute.
- Check `scripts/verify_sources.py` locally any time to confirm every enabled
  company API is still live.

---

## Local development

```bash
# Backend
cd backend
py -m pip install -r requirements.txt
py -m uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev   # http://localhost:5173
```
