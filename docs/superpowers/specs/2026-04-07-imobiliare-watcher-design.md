# Imobiliare.ro Apartment Watcher — Design Spec

## Overview

A Python scraper that monitors apartment listings on imobiliare.ro (Romania's main real estate portal) and presents them via a localhost web dashboard. Designed to run on a Mac Mini home server via PM2.

**Phase 1 (this spec):** Scraper + local dashboard to verify data extraction.
**Phase 2 (future):** Telegram notifications for new listings.

---

## Architecture

```
PM2 (hourly cron)          PM2 (always-on)
      |                          |
  scraper.py               server.py (Flask)
      |                          |
      +--- writes to ----> SQLite DB <---- reads from ---+
                                                         |
                                                   dashboard.html
                                                   (localhost:5000)
```

**Data flow:**
1. PM2 triggers `scraper.py` every hour
2. Scraper writes new listings to SQLite at `~/.local/share/imobiliare-watcher/listings.db`
3. Flask serves the dashboard on `127.0.0.1:5000`, reading from the same DB

---

## File Structure

```
imobiliare-watcher/
├── config.py              # All configuration values
├── scraper.py             # Playwright scraper (3 modes: normal, --seed, --backfill)
├── server.py              # Flask dashboard server (localhost only)
├── dashboard.html         # Single-file frontend (HTML/CSS/JS)
├── db.py                  # SQLite helpers
├── requirements.txt       # playwright, playwright-stealth, flask
├── ecosystem.config.js    # PM2 config for dashboard + scraper
└── README.md              # Setup instructions
```

---

## Configuration (`config.py`)

```python
SEARCH_URL = "PASTE_YOUR_SEARCH_URL_HERE"
DB_PATH = "~/.local/share/imobiliare-watcher/listings.db"  # expanded at runtime
MAX_PHOTOS = 10           # max photos per listing (Telegram media group cap)
DETAIL_PAGE_DELAY = (1, 3)  # random seconds between detail page visits
PAGINATION_DELAY = (1, 2)   # random seconds between search result pages
MAX_PAGES = 10              # safety cap on pagination
BACKFILL_BATCH_SIZE = 10    # listings to backfill per run
CLEAR_TOKEN = "CHANGE_ME"   # token for /api/clear endpoint
```

---

## Data Model (SQLite)

| field | type | notes |
|---|---|---|
| `id` | TEXT PRIMARY KEY | from DOM `id` attr (e.g. `275384395`) |
| `title` | TEXT | listing heading |
| `price` | TEXT | raw string, e.g. "650 EUR/luna" |
| `location` | TEXT | neighborhood + sector |
| `details` | TEXT | rooms, sqft, floor, year (raw string) |
| `url` | TEXT | full URL to listing page |
| `photo_urls` | TEXT | JSON array of image URLs, or `"[]"` if not yet fetched |
| `first_seen` | DATETIME | UTC timestamp |
| `is_new` | INTEGER | 1 = new, 0 = acknowledged |

---

## Database Layer (`db.py`)

Functions:

- `init_db()` — creates table if not exists, ensures data directory exists
- `get_existing_ids(ids: list[str]) -> set[str]` — returns which IDs already exist in DB
- `insert_listings(listings: list[dict])` — bulk insert new listings
- `get_listings(page: int, per_page: int, filter: str) -> dict` — paginated query, newest first. `filter` is `"new"` or `"all"`
- `acknowledge(id: str)` — sets `is_new = 0`
- `clear_all()` — deletes all rows
- `get_last_scrape_time() -> datetime | None` — most recent `first_seen`
- `get_listings_without_photos(limit: int) -> list[dict]` — for backfill mode
- `update_photos(id: str, photo_urls: list[str])` — update photos for a listing

Each function opens and closes its own connection. Uses `check_same_thread=False` for Flask compatibility.

---

## Scraper (`scraper.py`)

### Three Modes

**Normal mode** (`python3 scraper.py`):
Intended for hourly cron. Scrapes search results, detects new listings, fetches photos only for new ones.

**Seed mode** (`python3 scraper.py --seed`):
For the initial run against ~6000 existing listings. Scrapes all search result pages to collect listing metadata, but skips detail page visits entirely. Stores listings with empty photo arrays. Gets a complete baseline quickly without being aggressive.

**Backfill mode** (`python3 scraper.py --backfill`):
Fetches photos for up to `BACKFILL_BATCH_SIZE` (10) listings that have empty `photo_urls`. Run manually or on a slower schedule until caught up.

### Scraper Flow (Normal Mode)

1. Launch headless Chromium via Playwright with `playwright-stealth`
2. Load `SEARCH_URL`, wait for listing cards (`a[data-cy="listing-information-link"]`)
3. If page load fails (timeout, Cloudflare challenge): wait 30s, retry once. If retry fails: log error, exit non-zero.
4. Extract all listings on the page (ID, title, price, location, details, URL)
5. Check for next page link/button. If found and page count < `MAX_PAGES`: random delay (`PAGINATION_DELAY`), navigate, repeat from step 4.
6. Log: `"Page {n}: found {x} listings"`
7. Collect all scraped IDs, query SQLite for existing ones. Difference = new listings.
8. Log: `"Found {total} total, {new} new"`
9. For each new listing:
   - Navigate to its detail page URL
   - Extract photos (see Photo Extraction below)
   - Random delay (`DETAIL_PAGE_DELAY`) before next
10. Insert new listings into SQLite with `is_new = 1`, `first_seen = utcnow()`, `photo_urls = [...]`
11. Log: `"Scraper complete: {new} new listings added, {total} total in DB"`
12. Exit

### Seed Mode Flow

Same as normal mode steps 1-6, but:
- `MAX_PAGES` cap raised to 200 (enough for ~6000 listings at ~30 per page)
- Skip steps 9 entirely (no detail page visits)
- Insert all with `photo_urls = "[]"`

### Backfill Mode Flow

1. Query DB for up to `BACKFILL_BATCH_SIZE` listings where `photo_urls = "[]"`
2. Launch browser
3. For each: visit detail page, extract photos, update DB
4. Random delay between visits
5. Log results and exit

### Photo Extraction (Detail Pages)

Priority order:
1. **JSON data in `<script>` tags** — Alpine.js `x-data` attributes or inline JSON containing arrays of image objects with CDN URLs. This is more reliable than DOM scraping.
2. **Fallback: `<img>` tags** in the gallery/carousel area, filtering for CDN URLs (e.g. `cdn.imobiliare.ro` or similar patterns). Exclude icons/placeholders.

- Deduplicate URLs
- Cap at `MAX_PHOTOS`
- If detail page visit fails: log warning, store empty array, continue to next listing

### Logging

Python `logging` module to stdout (PM2 captures this). Log:
- Each page scraped and listing count
- Total found vs new count
- Each detail page visit (success/fail)
- Errors with tracebacks
- Summary on completion

---

## Flask Dashboard (`server.py`)

Binds to `127.0.0.1:5000` (localhost only).

### Endpoints

**`GET /`**
Serves `dashboard.html`.

**`GET /api/listings?page=1&per_page=50&filter=new`**
Returns paginated listings, newest first.
```json
{
  "listings": [...],
  "total": 6000,
  "page": 1,
  "per_page": 50,
  "last_scrape": "2026-04-07T12:00:00Z",
  "scraper_healthy": true
}
```
- `filter`: `"new"` (default) or `"all"`
- `scraper_healthy`: `true` if `last_scrape` is within 2 hours, `false` otherwise

**`POST /api/listings/<id>/acknowledge`**
Sets `is_new = 0`. Returns `{"ok": true}`.

**`POST /api/clear?token=<CLEAR_TOKEN>`**
Wipes the DB. Returns 403 if token is wrong or missing. Restricted to requests from `127.0.0.1`.

---

## Dashboard UI (`dashboard.html`)

Single file, no frameworks, no build step.

### Visual Style

- Dark background (`#0a0a0a`)
- Monospace font: IBM Plex Mono (Google Fonts, system monospace fallback)
- Phosphor green (`#00ff41`) accents
- Minimal, utilitarian — monitoring tool aesthetic

### Layout

**Header bar:**
- App title
- Last scraped timestamp
- Scraper health indicator: green dot if healthy, red dot + "Scraper may be down" text if >2h stale

**Filter toggle:**
- "New only" / "All" — defaults to "New only"

**Listing cards** (single-column stack):
- Horizontal scrollable photo strip with thumbnails from `photo_urls`. Click opens full image in new tab. Badge showing photo count.
- Title (links to listing on imobiliare.ro, new tab)
- Price, location, details on separate lines
- Green "New" badge if `is_new = 1`
- "Mark as seen" button — calls acknowledge endpoint, removes badge and dims card without reload

**Pagination controls:**
- Previous / Next buttons
- 50 listings per page
- Current page / total pages indicator

### Behavior

- Auto-refreshes data every 60 seconds via `fetch()`
- New listings appear at top
- Preserves current page and filter on auto-refresh

---

## PM2 Configuration (`ecosystem.config.js`)

**Dashboard (always-on):**
- `name: "imobiliare-dashboard"`
- `script: "python3"`
- `args: "server.py"`
- Auto-restart on crash

**Scraper (hourly cron):**
- `name: "imobiliare-scraper"`
- `script: "python3"`
- `args: "scraper.py"`
- `cron_restart: "0 * * * *"`
- `autorestart: false`

---

## Phase 2 Placeholder (Telegram — not implemented)

A clearly marked placeholder in `scraper.py`:

```python
# PHASE 2: Send Telegram notification for new listings
# TODO: implement when scraping is verified working
# - Use sendMessage for listing details (title, price, location, url)
# - Use sendMediaGroup to send up to 10 photos per listing (from photo_urls)
# - Bot token and chat ID go in config.py
# def notify_telegram(listings): ...
```

---

## Setup Steps (README)

1. `pip install -r requirements.txt`
2. `playwright install chromium`
3. Paste search URL into `config.py`, set `CLEAR_TOKEN`
4. Initial seed: `python3 scraper.py --seed`
5. Start dashboard: `pm2 start ecosystem.config.js`
6. Verify at `http://localhost:5000`
7. Optional: run `python3 scraper.py --backfill` a few times to populate photos
8. Normal operation: PM2 handles hourly scraping automatically
9. Logs: `pm2 logs imobiliare-scraper`
10. DB reset: `curl -X POST "http://localhost:5000/api/clear?token=YOUR_TOKEN"`

---

## Tech Stack

- **Python 3** (system Python or venv)
- **Playwright** + `playwright-stealth` — headless Chromium for JS-rendered pages behind Cloudflare
- **SQLite** via `sqlite3` (stdlib)
- **Flask** — minimal API + static serving
- **PM2** — process management and cron scheduling
- HTML/CSS/JS (single file, no frameworks)
