import os
from datetime import timedelta

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

# Scraper schedule (local time)
SCRAPER_START_HOUR = 8         # first run at 08:00
SCRAPER_END_HOUR = 23          # last run at 23:00
LOCAL_UTC_OFFSET = timedelta(hours=3)  # EEST (Romania)

# Dashboard
CLEAR_TOKEN = "v45kWTa9pBx6iUvmuAb9pA"      # token required for /api/clear endpoint

# Telegram notifications
TELEGRAM_BOT_TOKEN = "7916818431:AAFYSGfYv9QZgjcnN-5Hf8Wd1RjhtAsNlkQ"
TELEGRAM_CHAT_ID = "933530616"
