# AirPriceX — Airfare Price Index (APIx)

Government-facing Indian airfare intelligence. **This repo is standalone.** It does not depend on Port Sense or Citewell.

Two published series:

- **Real-time market index** — high-frequency route prices and D+1…D+60 fare curves
- **CPI-compatible index** — 21-day domestic / 60-day international specs, Jevons elementary index, weighted aggregation

Architecture: layered modules, pipeline data flow, hub-and-spoke adapters, hierarchical aggregation, adaptive scheduler hook. The index engine never talks to Playwright. Missing prices are skipped, never zeroed. OTAs cannot enter the CPI sample. Live booking-page HTTP is off.

```text
python -m pip install -e ".[dev]"
python -m pytest
python scripts/bootstrap.py   # skip if data/apix.db already exists
python scripts/run_api.py
```

Then open http://127.0.0.1:8000

The published dashboard is **fixture data** (deterministic quotes as of 2026-09-14), not live airline/OTA scrapes. HTTP booking-page collection is off.

Hosted on Vercel as a FastAPI app. SQLite is bundled read-mostly (`/tmp` copy on the function). Do not expect the collector to run in production.

| Path | Role |
|---|---|
| `/` | Dashboard |
| `/api/v1/health` | Engine health |
| `/api/v1/index/current` | National APIx |
| `/api/v1/realtime/routes/DEL-BOM` | Fare curve |
| `/api/v1/analytics/overview` | Full dashboard payload |
