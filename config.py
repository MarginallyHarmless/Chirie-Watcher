import os

# Search URLs — one per neighborhood, with shared filters
# The scraper iterates all of these and deduplicates by listing ID
SEARCH_URLS = [
    "https://www.imobiliare.ro/inchirieri-apartamente/bucuresti/decebal?rooms=2,3&price=300-800",
    "https://www.imobiliare.ro/inchirieri-apartamente/bucuresti/alba-iulia?rooms=2,3&price=300-800",
    "https://www.imobiliare.ro/inchirieri-apartamente/bucuresti/unirii?rooms=2,3&price=300-800",
    "https://www.imobiliare.ro/inchirieri-apartamente/bucuresti/calea-calarasilor?rooms=2,3&price=300-800",
]

# Database
DB_PATH = os.path.expanduser("~/.local/share/imobiliare-watcher/listings.db")

# Scraper settings
MAX_PHOTOS = 10                # max photos to store per listing
DETAIL_PAGE_DELAY = (1, 3)     # random seconds between detail page visits
PAGINATION_DELAY = (1, 2)      # random seconds between search result pages
MAX_PAGES = 10                 # safety cap on pagination per neighborhood (normal mode)
SEED_MAX_PAGES = 50            # safety cap per neighborhood (seed mode)
BACKFILL_BATCH_SIZE = 10       # listings to backfill photos for per run

# Dashboard
CLEAR_TOKEN = "v45kWTa9pBx6iUvmuAb9pA"      # token required for /api/clear endpoint
