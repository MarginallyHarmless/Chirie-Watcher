# Scraping Log — Design Spec

## Overview

Add a persistent scrape run log visible on the dashboard. Each scraper run (normal, seed, backfill) records a summary entry. The dashboard shows the last 200 runs in a collapsible section. Error runs are highlighted.

## Database

New table `scrape_logs`:

```sql
CREATE TABLE IF NOT EXISTS scrape_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at DATETIME NOT NULL,
    finished_at DATETIME,
    mode TEXT NOT NULL,           -- "normal", "seed", "backfill"
    new_listings INTEGER DEFAULT 0,
    total_found INTEGER DEFAULT 0,
    status TEXT NOT NULL,         -- "success" or "error"
    error_message TEXT,           -- null on success
    duration_seconds REAL
);
```

**Pruning:** After each insert, delete rows where `id NOT IN (SELECT id FROM scrape_logs ORDER BY started_at DESC LIMIT 200)`. This keeps the table bounded at ~200 entries.

## API

### `GET /api/scrape-logs`

Returns the last 200 log entries, most recent first.

Response:
```json
{
  "logs": [
    {
      "id": 42,
      "started_at": "2026-04-07T14:00:00+00:00",
      "finished_at": "2026-04-07T14:02:13+00:00",
      "mode": "normal",
      "new_listings": 5,
      "total_found": 48,
      "status": "success",
      "error_message": null,
      "duration_seconds": 133.2
    }
  ]
}
```

## Scraper Changes

Wrap the three run functions (`run_normal`, `run_seed`, `run_backfill`) to:

1. Record `started_at` before execution
2. Run the existing logic inside a try/except
3. On success: log entry with status "success", counts, and duration
4. On error: log entry with status "error", the exception message, and duration
5. Re-raise the exception after logging so PM2 still sees the failure

The existing run functions need minor changes to return their counts (`new_listings`, `total_found`) so the wrapper can record them.

## Dashboard UI

### Layout

A collapsible "Scrape log" section placed between the controls bar and the listings grid. Collapsed by default. Toggle via a button in the controls area.

### Table Columns

| Column | Content |
|--------|---------|
| Time | `started_at` formatted as "7 Apr, 14:00" |
| Mode | "normal" / "seed" / "backfill" |
| Result | new_listings count + total_found (e.g. "5 new / 48 total") |
| Duration | formatted as "2m 13s" |
| Status | green "OK" or red "ERROR" badge |

### Styling

- Matches existing dark theme (#111 background, #c0c0c0 text, monospace font)
- Error rows: red-tinted left border (`border-left: 3px solid #ff4141`)
- Error message shown as a second line within the row when status is "error"
- Table is compact (small font, tight padding) to not dominate the page
- Max height with scroll if many entries visible

### Toggle Button

A "Scrape log" button added to the controls bar (next to the sort dropdown). Clicking toggles visibility of the log section. Text changes to "Hide log" when expanded.

## Files Modified

1. **db.py** — Add `scrape_logs` table creation in `init_db()`, add `insert_scrape_log()` and `get_scrape_logs()` and `prune_scrape_logs()` functions
2. **scraper.py** — Wrap run functions to record log entries, return counts
3. **server.py** — Add `GET /api/scrape-logs` endpoint
4. **dashboard.html** — Add log section, toggle button, styles, fetch logic
