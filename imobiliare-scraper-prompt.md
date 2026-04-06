# Imobiliare.ro Apartment Watcher — Claude Code Prompt

## What we're building

A Python scraper that monitors a saved apartment search on imobiliare.ro and notifies me of new listings. Built in two phases:

- **Phase 1 (now):** Scraper + local web dashboard to verify data extraction is working correctly
- **Phase 2 (later):** Telegram notifications (do not implement yet)

---

## Context

- **Target site:** imobiliare.ro — Romania's main real estate portal
- **Search:** 2–3 room apartments for rent in Bucharest, 300–800 €/month, specific map area
- **Runtime:** Mac Mini home server (macOS), already running PM2 + Caddy + Cloudflare Tunnel
- **Schedule:** Hourly via cron
- **Language:** Python

---

## Search URL

The full search URL with polygon map area is too long to embed. Store it in `config.py` as `SEARCH_URL`. The user will paste it there manually. Use this placeholder for now:

```python
SEARCH_URL = "PASTE_YOUR_SEARCH_URL_HERE"
```

---

## Tech stack

- **Playwright** (Python) with `playwright-stealth` — headless Chromium to handle JS rendering and Cloudflare
- **SQLite** via `sqlite3` (stdlib) — persist seen listing IDs
- **Flask** — minimal API server (`/api/listings`) + static file serving for the dashboard
- **HTML/CSS/JS** (single file) — dashboard UI, no build step, no frameworks

---

## DOM selectors (verified from DevTools)

The listing cards use these stable hooks:

- **Listing anchor:** `a[data-cy="listing-information-link"]`
- **Listing ID:** extracted from the `id` attribute of that anchor — format: `listing-link-275384395` → ID is `275384395`
- **Listing URL:** `href` attribute of that anchor (relative path, prepend `https://www.imobiliare.ro`)

For title, price, location, and details (rooms, sqft, floor, year): inspect siblings/children of the anchor. Use reasonable fallbacks if a field is missing — don't crash on incomplete cards.

---

## Data model

Each listing stored in SQLite:

| field | type | notes |
|---|---|---|
| `id` | TEXT PRIMARY KEY | extracted from DOM `id` attr |
| `title` | TEXT | listing heading |
| `price` | TEXT | e.g. "650 €/lună" |
| `location` | TEXT | neighborhood + sector |
| `details` | TEXT | rooms, sqft, floor, year (raw string) |
| `url` | TEXT | full URL |
| `photo_urls` | TEXT | JSON array of image URLs, e.g. `["https://...jpg", ...]` |
| `first_seen` | DATETIME | UTC timestamp |
| `is_new` | INTEGER | 1 until acknowledged, 0 after |

---

## Photos

Each listing card on the search results page shows one thumbnail and a badge with the total photo count (e.g. "17"). To get all photos, the scraper must visit each **new** listing's detail page once.

### Strategy

- **Search results page:** extract the thumbnail `src` from the `<img>` inside the card's photo area as a quick sanity check that images are loading
- **Detail page (per new listing only):** navigate to the listing URL and extract all full-size image URLs from the photo gallery
  - Look for `<img>` tags in the gallery/carousel area, or a JSON payload in a `<script>` tag (the site uses Alpine.js which often embeds data as JSON — check for an array of image objects)
  - Deduplicate and filter out icons/placeholders (check URL pattern — real photos are typically on a CDN like `cdn.imobiliare.ro` or similar)
  - Store as a JSON array in `photo_urls`

### Limits

- Cap at **10 photos per listing** (Telegram media groups max out at 10, and it's enough for preview purposes)
- If the detail page visit fails, store an empty array and continue — don't block the listing from being saved
- Only fetch detail pages for **new** listings (not on every run)

### Config

Add to `config.py`:

```python
MAX_PHOTOS = 10  # max photos to store per listing
```

---

## Scraper behavior

1. Launch headless Chromium with stealth plugin
2. Load `SEARCH_URL`, wait for listing cards to render
3. Extract all listings from the page (ID, title, price, location, details, URL, thumbnail)
4. Compare IDs against SQLite — anything not in DB is new
5. For each new listing: navigate to its detail page, extract up to `MAX_PHOTOS` full-size image URLs
6. Insert new listings with `is_new = 1`, `first_seen = now()`, `photo_urls = [...]`
7. Exit — no daemon, designed to be called by cron

Add a short random delay (1–3s) between detail page visits. Do not hammer the site — one run per hour is the intended frequency.

---

## Web dashboard (Phase 1)

A `server.py` Flask app that:
- Serves `dashboard.html` at `/`
- Exposes `/api/listings` — returns all listings as JSON, newest first
- Exposes `/api/listings/<id>/acknowledge` (POST) — sets `is_new = 0`
- Exposes `/api/clear` (POST, dev only) — wipes the DB, for testing resets

The `dashboard.html` should:
- Show listings as cards with title, price, location, details, and a link to the full listing
- Each card includes a **scrollable horizontal photo strip** — show thumbnails from `photo_urls`, clicking one opens the full image in a lightbox or new tab
- Show photo count badge on the strip (e.g. "4 / 17" if capped)
- Highlight new listings visually (badge or accent color)
- Have an "Acknowledge" button per card that marks it as seen (calls the API, updates UI without reload)
- Show a "last scraped" timestamp (pull from most recent `first_seen` in DB)
- Auto-refresh every 60 seconds

### Dashboard aesthetic

Dark theme, monospace font (IBM Plex Mono or similar), phosphor green accents on dark background. Minimal, utilitarian — looks like a monitoring tool, not a property portal. No frameworks, no build step.

---

## File structure

```
imobiliare-watcher/
├── config.py          # SEARCH_URL and other settings
├── scraper.py         # Playwright scraper, run by cron
├── server.py          # Flask dashboard server
├── dashboard.html     # Frontend UI
├── db.py              # SQLite helpers (init, insert, query)
├── requirements.txt
├── run_scraper.sh     # Convenience wrapper for cron
└── README.md          # Setup instructions
```

---

## README must cover

1. Install dependencies (`pip install -r requirements.txt`, `playwright install chromium`)
2. Paste search URL into `config.py`
3. Run server: `python server.py`
4. Run scraper manually: `python scraper.py`
5. Set up hourly cron: `0 * * * * /path/to/run_scraper.sh`
6. How to reset the DB for testing (`/api/clear` or delete the `.db` file)

---

## Phase 2 hook (do not implement)

Leave a clearly marked placeholder in `scraper.py`:

```python
# PHASE 2: Send Telegram notification for new listings
# TODO: implement when scraping is verified working
# - Use sendMessage for listing details (title, price, location, url)
# - Use sendMediaGroup to send up to 10 photos per listing (from photo_urls)
# - Bot token and chat ID go in config.py
# def notify_telegram(listings): ...
```

---

## Notes

- The site uses Alpine.js + Livewire (Laravel stack) — the page is JS-rendered, hence Playwright
- `playwright-stealth` is needed to avoid Cloudflare blocking headless Chromium
- Running from a Romanian residential IP (Mac Mini on home fiber) is favorable — Cloudflare is less aggressive
- Do not use `requests` + `BeautifulSoup` — won't work on this site
