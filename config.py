import os

# Search URL — paste your imobiliare.ro search URL here
SEARCH_URL = "PASTE_YOUR_SEARCH_URL_HERE"

# Database
DB_PATH = os.path.expanduser("~/.local/share/imobiliare-watcher/listings.db")

# Scraper settings
MAX_PHOTOS = 10                # max photos to store per listing
DETAIL_PAGE_DELAY = (1, 3)     # random seconds between detail page visits
PAGINATION_DELAY = (1, 2)      # random seconds between search result pages
MAX_PAGES = 10                 # safety cap on pagination (normal mode)
SEED_MAX_PAGES = 200           # safety cap on pagination (seed mode)
BACKFILL_BATCH_SIZE = 10       # listings to backfill photos for per run

# Dashboard
CLEAR_TOKEN = "CHANGE_ME"      # token required for /api/clear endpoint
