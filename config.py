import os

# Search URL — paste your imobiliare.ro search URL here
SEARCH_URL = "https://www.imobiliare.ro/inchirieri-apartamente/bucuresti?map-zoom=16&map-latitude=44.425229507528&map-longitude=26.119801998138&map-area=min_ZZNLktwACEMvlJriIwRU7n-vyGO8Su_clkE8BPCDjK6MmtrM_hP88ahI61kfVOMvfkU1aA9W80T0SnBtipsn8nYzPbLyFUnNZY5JzVfkhejRx32FNqDOOa1Sb6FYIAuW3OCvKFX5Ke1EFU7k6lcRrnd4VRGctWIu6xVNRybUzBmnGW6HoWbnKjXI8WxLf31nTpactkEzviKirZnpFlcJuRq5vGW3X1EBMDQwN12KWtmYcMUNB-_wsDbRuW6ccvfdLT_fOSzG-EadBitBbBnOdbrmIsCJPY2va5Ei1311YmzC-Yx8oseJ_pb3qk-UGCGgycnhFhDTbkNIbv5QQEgtWKLDbbWlQcKRn2jN9G3MMZJfVY-kDSzON0U_U-NnXUoGwyifdD9GQuatx8EVUog0u3CqQ38gXQ5V_kvJg19IShHoLwAQSSo1lnPdYKUgyfV8jsB0xVjRis9SrJj4BFsdLgDPop599lEKOdhJuHLKA9BWuh3lEp_GFFPFSejsAjCypAatdJ3IdUfCEaMl35kENronjXZ3oh9_w6TTPM1_lyuqRogUv5OkYqMzEsjrlSv4MaPTjvoH&rooms=2,3&price=300-800"

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
CLEAR_TOKEN = "v45kWTa9pBx6iUvmuAb9pA"      # token required for /api/clear endpoint
