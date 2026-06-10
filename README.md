# Job Scraper — RTL & Design Verification Jobs

Automated semiconductor job discovery for RTL Design, Design Verification, ASIC, SoC, CPU/GPU,
DFT, Formal, and FPGA roles. Scrapes **verified public ATS JSON APIs** (Greenhouse, Lever,
Ashby, Workday CXS) 4× per day and surfaces accurate, unambiguous openings in a LinkedIn-grade
dashboard.

- **Accurate by design** — only live-verified company endpoints are enabled (zero scraping
  errors). Run `py scripts/verify_sources.py` to re-check, `discover_sources.py` to add more.
- **Precise relevance** — a title-first RTL/DV classifier keeps software/sales/analog noise out.
- **Deploy:** Vercel (frontend) + Render (backend + Postgres). See [DEPLOYMENT.md](DEPLOYMENT.md).

---

## Setup

### 1. Prerequisites

- Python 3.11+
- Node.js 18+
- Git (optional)

### 2. Clone / extract the project

```
cd "D:\Job Scraper\rtl-dv-job-radar"
```

### 3. Install Python dependencies

```
py -m pip install -r backend/requirements.txt
py -m playwright install chromium
```

### 4. Configure environment

```
copy .env.example .env
```

Edit `.env` if you want Notion sync, Discord/Telegram alerts, or email alerts.
The default works out of the box — no API keys needed for scraping.

### 5. Install frontend dependencies

```
cd frontend
npm install
cd ..
```

---

## Running the system

### Start the backend API + scheduler

```
cd backend
py -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The scheduler starts automatically and will scrape at 6:00 AM, 11:30 AM, 3:30 PM, 8:30 PM (ET).

### Start the frontend dashboard

In a separate terminal:

```
cd frontend
npm run dev
```

Open **http://localhost:5173** in your browser.

---

## Running a manual scrape

```
py scripts/run_scrape.py
```

Or click **"Run Scrape Now"** in the dashboard (top-right button).

You can also trigger it via the API:

```
curl -X POST http://localhost:8000/scrape/run-now
```

---

## Scheduled automatic scraping

The scheduler is built into the FastAPI app using APScheduler. It runs automatically
when the backend is running. Times and timezone are configurable in `config/schedule.yaml`.

To change scrape times, edit `config/schedule.yaml`:

```yaml
timezone: "America/New_York"
scrape_times:
  - "06:00"
  - "11:30"
  - "15:30"
  - "20:30"
```

Restart the backend after changing the schedule.

---

## Adding a new company

Edit `config/companies.yaml` and add an entry:

```yaml
- name: "New Company"
  category: "AI Accelerator"         # S-Tier | Hyperscaler | Tier1 | EDA | Networking | etc.
  priority: "A"                       # S | A | B | C
  careers_url: "https://boards.greenhouse.io/newcompany"
  ats_platform: "greenhouse"          # greenhouse | lever | ashby | workday | generic
  greenhouse_board: "newcompany"      # for greenhouse
  search_keywords: ["verification", "rtl", "asic"]
  locations_of_interest: ["San Jose", "Remote"]
  enabled: true
```

For Workday companies, use:
```yaml
  ats_platform: "workday"
  workday_tenant: "companyname"
  workday_instance: "wd1"             # wd1, wd3, or wd5
  workday_career_site: "External"
```

Then restart the backend (it auto-seeds new companies on startup).

---

## How removed-job detection works

1. Each scrape run records which job IDs were found for each company.
2. Jobs not seen in a scrape have their `missed_scrapes` counter incremented.
3. After **1 missed scrape** → status becomes `possibly_removed`.
4. After **2 missed scrapes** (configurable in `config/schedule.yaml`) → status becomes `removed` and `removed_at` timestamp is recorded.
5. Jobs are **never deleted** from the database — they remain as history.

The threshold is configurable:
```yaml
removed_job_threshold: 2  # in config/schedule.yaml
```

---

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /jobs | List jobs with filters |
| GET | /jobs/new | New jobs in last N hours |
| GET | /jobs/best | Jobs with score ≥ 70 |
| GET | /jobs/removed | Removed jobs |
| GET | /jobs/{id} | Single job detail |
| POST | /jobs/{id}/status | Update status / notes |
| GET | /companies | All companies |
| GET | /scrape-runs | Recent scrape history |
| POST | /scrape/run-now | Trigger manual scrape |
| GET | /stats | Dashboard stats |
| GET | /scrape-errors | Recent errors |

API docs: http://localhost:8000/docs

---

## Match scoring

Scores range from 0–100:

| Signal | Points |
|--------|--------|
| Title: Design Verification / UVM / SystemVerilog | +30 |
| Title: RTL / ASIC / SoC / CPU / GPU / FPGA | +25 |
| Description: SystemVerilog, UVM, SVA, coverage, assertions | +20 |
| Entry-level / New Grad / 0-3 years | +15 |
| S or A priority company | +10 |
| USA / Remote location | +10 |
| Requires 5+ years | −30 |
| Senior / Staff / Principal in title | −20 |
| Pure software (no HW overlap) | −20 |
| Pure analog / RF | −20 |

---

## Limitations and next improvements

**Current limitations:**
- Apple, Google, Microsoft, Meta, and custom career portals use a generic HTML scraper that may miss jobs or break if site layouts change.
- Workday scraper uses an undocumented API endpoint — tenant paths need to be verified per company.
- No resume parsing or auto-apply functionality.
- Single-user, local-only — not designed for multi-user deployment.

**Planned improvements:**
- LinkedIn Easy Apply integration (unofficial)
- Eightfold / Phenom scraper for companies using those ATS platforms
- Job description full-text indexing and semantic search
- Email digest summarizing new jobs from last 24h
- Auto-apply status sync from email inbox parsing
- Notion two-way sync (apply status back to DB)
- Docker Compose for one-command startup
