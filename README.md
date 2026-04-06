# Imobiliare.ro Apartment Watcher

Monitors apartment listings on imobiliare.ro and serves a local dashboard.

## Setup

1. Install Python dependencies:

```bash
pip install -r requirements.txt
playwright install chromium
```

2. Edit `config.py`:
   - Paste your imobiliare.ro search URL into `SEARCH_URL`
   - Change `CLEAR_TOKEN` to a random string

3. Run the initial seed (imports all existing listings without photos):

```bash
python3 scraper.py --seed
```

4. Start the dashboard and hourly scraper via PM2:

```bash
pm2 start ecosystem.config.js
```

5. Open the dashboard: http://localhost:5000

## Scraper Modes

| Command | Purpose |
|---|---|
| `python3 scraper.py` | Normal mode — scrape search results, fetch photos for new listings |
| `python3 scraper.py --seed` | Seed mode — bulk import all listings, no photos |
| `python3 scraper.py --backfill` | Backfill mode — fetch photos for 10 listings that have none |

## Useful Commands

```bash
pm2 logs imobiliare-scraper     # View scraper logs
pm2 logs imobiliare-dashboard   # View dashboard logs
pm2 restart imobiliare-scraper  # Trigger a scrape now
pm2 stop all                    # Stop everything
```

## Reset Database

```bash
curl -X POST "http://localhost:5000/api/clear?token=YOUR_TOKEN"
```

Or delete the DB file directly:

```bash
rm ~/.local/share/imobiliare-watcher/listings.db
```

## Running Tests

```bash
python -m pytest tests/ -v
```
