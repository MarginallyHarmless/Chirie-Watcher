# Chirie Watcher — How to Use

## What's running

Your Mac Mini runs two background services automatically:

1. **Dashboard** — a website at `http://localhost:5000` showing your apartment listings
2. **Scraper** — checks for new listings every hour in Decebal, Alba Iulia, Unirii, and Calea Călărașilor

Both start automatically when your Mac Mini boots up. You don't need to do anything.

## Viewing listings

Open this in any browser on your Mac Mini:

    http://localhost:5000

- New listings have a green **NEW** badge
- Click the green title to open the listing on imobiliare.ro
- Click **Mark as seen** to dismiss the badge
- Use **New only / All** toggle to filter
- The page auto-refreshes every 60 seconds

## Common tasks (in Terminal)

### Check if everything is running

    pm2 list

You should see two services with status **online**.

### See recent scraper activity

    pm2 logs imobiliare-scraper --lines 20

### Force a scrape right now (don't wait for the hourly run)

    pm2 restart imobiliare-scraper

### Stop everything

    pm2 stop all

### Start everything back up

    pm2 start all

### After a computer restart

Everything should start automatically. If it doesn't:

    pm2 resurrect

## Troubleshooting

### Dashboard not loading

    pm2 restart imobiliare-dashboard

### Scraper seems stuck or not finding new listings

    pm2 logs imobiliare-scraper --lines 50

Look for error messages. Common causes:
- Internet is down
- imobiliare.ro changed their website structure

### Reset everything (nuclear option)

This deletes all saved listings and starts fresh:

    rm ~/.local/share/imobiliare-watcher/listings.db
    pm2 restart all

Then run the seed to re-import:

    cd "/Users/bmacmini/Documents/vibes/Imobiliare bot"
    python3 scraper.py --seed

### Completely remove Chirie Watcher

    pm2 stop all
    pm2 delete all
    pm2 save
    pm2 unstartup launchd
