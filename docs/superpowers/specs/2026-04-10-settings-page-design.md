# Settings Page Design

## Overview

Add a dashboard page to view and edit scraper configuration at runtime, plus a "Run now" button to trigger an immediate scrape. Settings move from hardcoded `config.py` constants to a database-backed store, editable via the dashboard.

## Editable Settings

| Key | Type | Default | UI Control |
|-----|------|---------|------------|
| `neighborhoods` | JSON string list | `["decebal", "alba iulia", "unirii", "calea calarasilor", "calarasilor"]` | Tag list with add/remove |
| `price_min` | int | 300 | Number input |
| `price_max` | int | 800 | Number input |
| `rooms` | JSON int list | `[2, 3]` | Checkboxes (1 through 5) |
| `scraper_start_hour` | int | 8 | Number input (0-23) |
| `scraper_end_hour` | int | 23 | Number input (0-23) |

Settings not exposed in the UI (remain in `config.py`): `MAX_PHOTOS`, `DETAIL_PAGE_DELAY`, `PAGINATION_DELAY`, `MAX_PAGES`, `SEED_MAX_PAGES`, `BACKFILL_BATCH_SIZE`, `LOCAL_UTC_OFFSET`, `CLEAR_TOKEN`, Telegram credentials, `DB_PATH`.

## Database

New `settings` table with a single-row design:

```sql
CREATE TABLE IF NOT EXISTS settings (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    neighborhoods TEXT NOT NULL,      -- JSON array of strings
    price_min INTEGER NOT NULL,
    price_max INTEGER NOT NULL,
    rooms TEXT NOT NULL,               -- JSON array of ints
    scraper_start_hour INTEGER NOT NULL,
    scraper_end_hour INTEGER NOT NULL
);
```

The `CHECK (id = 1)` constraint enforces a single row. On first access, if the row doesn't exist, insert it with defaults from `config.py`.

### DB functions (db.py)

- `get_settings() -> dict` — Returns the settings row as a dict. Creates the default row if the table is empty. JSON fields are parsed before returning.
- `update_settings(data: dict)` — Validates and writes all settings fields. JSON fields are serialized before storing.

## URL Building

New module `url_builder.py` with two functions:

- `build_imobiliare_urls(settings) -> list[str]` — One URL per neighborhood: `https://www.imobiliare.ro/inchirieri-apartamente/bucuresti/{slug}?rooms={rooms}&price={min}-{max}`. The neighborhood name is slugified (spaces to hyphens, lowercase).
- `build_storia_urls(settings) -> list[str]` — Single city-level URL: `https://www.storia.ro/ro/rezultate/inchiriere/apartament/bucuresti?priceMin={min}&priceMax={max}&roomsNumber={encoded}`. Room count encoded as storia expects (`TWO`, `THREE`, etc., URL-encoded JSON array).

Room number mapping for storia: `{1: "ONE", 2: "TWO", 3: "THREE", 4: "FOUR", 5: "FIVE_OR_MORE"}`.

## Scraper Changes

At the start of each `run_normal` (and `run_seed`):

1. Call `db.get_settings()` to load current settings.
2. Call `url_builder.build_imobiliare_urls(settings)` and `url_builder.build_storia_urls(settings)` to get URLs.
3. Use these URLs instead of `config.SEARCH_URLS` and `config.STORIA_SEARCH_URLS`.
4. Pass `settings["neighborhoods"]` to the storia scraper for neighborhood filtering instead of reading `config.STORIA_NEIGHBORHOODS`.
5. Use `settings["scraper_start_hour"]` and `settings["scraper_end_hour"]` for the night-hours skip check.

Fallback: if `get_settings()` fails (e.g., corrupt DB), log a warning and fall back to `config.py` values.

The scraper currently writes a single `scrape_logs` row at the end of each run. To support the "run now" status indicator, change this: insert a row with `status='running'` at the **start** of each run, then update that same row to `success` or `error` at the end. This lets the server detect an in-progress scrape.

The storia scraper's `_matches_neighborhood` currently reads `config.STORIA_NEIGHBORHOODS` directly. Change it to accept the neighborhoods list as a parameter, passed in from the caller using the DB settings.

## API Endpoints

### GET /api/settings

Returns current settings as JSON:

```json
{
  "neighborhoods": ["decebal", "alba iulia", "unirii", "calea calarasilor", "calarasilor"],
  "price_min": 300,
  "price_max": 800,
  "rooms": [2, 3],
  "scraper_start_hour": 8,
  "scraper_end_hour": 23
}
```

### PUT /api/settings

Accepts the same JSON shape. Validates:
- `neighborhoods`: non-empty list of non-empty strings
- `price_min`, `price_max`: positive integers, min < max
- `rooms`: non-empty list of ints in 1-5
- `scraper_start_hour`, `scraper_end_hour`: ints 0-23, start < end

Returns 200 on success, 400 with error message on validation failure.

### POST /api/scrape

Triggers an immediate scrape. Checks if a scrape is already running by looking for a `scrape_logs` row where `status = 'running'` with `started_at` in the last 30 minutes (stale-run protection). Returns:

- 200 `{"status": "started"}` — subprocess spawned
- 409 `{"error": "Scrape already running"}` — one is in progress

Implementation: `subprocess.Popen(["python3", "scraper.py"], cwd=project_dir)` — fire and forget. The scraper already writes its own scrape log entries.

### GET /api/scrape/status

Returns whether a scrape is currently running:

```json
{"running": true}
```

or

```json
{"running": false, "last_completed": "2026-04-10T14:00:00Z"}
```

Determined by checking `scrape_logs` for a `status = 'running'` row.

## Settings Page (settings.html)

New standalone HTML file following the same patterns as `dashboard.html` and `log.html`: embedded CSS and JavaScript, same dark theme, same CSS custom properties.

### Layout

- **Header** with navigation links: Listings | Scrape Log | Settings (added to all three pages)
- **Neighborhoods section**: List of tag chips, each with an X to remove. Text input + "Add" button below.
- **Filters section**: Price min/max as number inputs side by side. Room checkboxes (1-5) in a row.
- **Schedule section**: Start hour and end hour as number inputs side by side.
- **Actions bar**: "Save" button (PUTs settings), "Run now" button (POSTs to /api/scrape).
- **Status area**: Shows save confirmation, scrape running indicator, and last scrape result.

### Behavior

- On load: fetches `GET /api/settings` and populates the form.
- Save: PUTs the form data, shows success/error feedback inline.
- Run now: POSTs to `/api/scrape`. If 200, polls `GET /api/scrape/status` every 3 seconds until complete. Shows a spinner while running. If 409, shows "already running" message.
- No auth required.

## Navigation

Add a simple nav bar to all three pages (`dashboard.html`, `log.html`, `settings.html`):

```html
<nav>
  <a href="/">Listings</a>
  <a href="/log">Scrape Log</a>
  <a href="/settings">Settings</a>
</nav>
```

Styled consistently with the existing header. Current page link highlighted.

## Server Route

```python
@app.route("/settings")
def settings_page():
    return send_from_directory(".", "settings.html")
```

## Testing

### Unit tests (no browser needed)

- `test_db.py`: `get_settings` returns defaults on empty table; `update_settings` writes and reads back correctly; validation rejects bad input.
- `test_server.py`: `GET /api/settings` returns defaults; `PUT /api/settings` with valid data returns 200; `PUT` with invalid data returns 400; `POST /api/scrape` returns 200 (mock subprocess); `GET /api/scrape/status` returns running state.
- `test_url_builder.py`: URL building produces correct imobiliare and storia URLs for various inputs; neighborhood slugification works; room encoding for storia works.

## Non-goals

- Multi-user support or auth on the settings page
- Undo/history of settings changes
- Per-neighborhood filter overrides (price/rooms differ by neighborhood)
- Editing non-scraper settings (Telegram credentials, clear token, delays)
