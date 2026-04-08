# Storia.ro Integration — Design Spec

## Goal

Add storia.ro as a second listing source alongside imobiliare.ro, showing all apartments in one unified feed with source labels and duplicate detection hints.

## Motivation

Apartments often appear on only one platform. Monitoring both storia.ro and imobiliare.ro in a single dashboard means fewer missed listings and a more complete picture of the market — without having to check multiple sites manually.

## Schema Changes

### Listings table — new columns

- `source TEXT DEFAULT 'imobiliare'` — which site the listing came from. Values: `imobiliare`, `storia`. Existing rows default to `imobiliare`.
- `possible_duplicate_of TEXT DEFAULT NULL` — ID of a listing from the other source that looks like the same apartment. NULL if no suspected duplicate.

Migration: `ALTER TABLE` with try/except for both columns (same pattern as `removed_at`).

## Scraper Architecture

### New file: `storia_scraper.py`

A storia-specific scraper module containing:

- `scrape_storia_search_results(page, max_pages)` — analogous to `scrape_search_results` in `scraper.py`. Navigates storia.ro search result pages, extracts listing cards.
- `extract_storia_listings_from_page(page)` — parses storia.ro DOM structure to extract listing data (id, title, price, location, details, url, photo_urls). The exact selectors need to be discovered at implementation time using Playwright, since storia.ro blocks non-browser requests.
- `find_storia_next_page(page)` — pagination logic for storia.ro.
- `fetch_storia_photos(page, url, max_photos)` — visit a storia detail page and extract photo URLs.

### Config: `STORIA_SEARCH_URLS`

Add to `config.py`:
```
STORIA_SEARCH_URLS = [
    "https://www.storia.ro/ro/rezultate/inchiriere/apartament/bucuresti/decebal?priceMin=300&priceMax=800&roomsNumber=%5BTWO%2CTHREE%5D",
    "https://www.storia.ro/ro/rezultate/inchiriere/apartament/bucuresti/alba-iulia?priceMin=300&priceMax=800&roomsNumber=%5BTWO%2CTHREE%5D",
    "https://www.storia.ro/ro/rezultate/inchiriere/apartament/bucuresti/unirii?priceMin=300&priceMax=800&roomsNumber=%5BTWO%2CTHREE%5D",
    "https://www.storia.ro/ro/rezultate/inchiriere/apartament/bucuresti/calea-calarasilor?priceMin=300&priceMax=800&roomsNumber=%5BTWO%2CTHREE%5D",
]
```

Note: The exact URL format needs to be validated during implementation. Storia.ro may use different path patterns for neighborhoods or may require place IDs instead of slugs. The implementer should navigate to these URLs in Playwright and verify they load results, adjusting the URLs if needed.

### Scraper orchestration

`run_normal()` in `scraper.py` is updated to:

1. Scrape imobiliare.ro (existing logic, unchanged)
2. Scrape storia.ro using `storia_scraper.scrape_storia_search_results()`
3. For new storia listings, run duplicate detection before inserting
4. Insert new storia listings with `source='storia'`
5. Run removal detection across both sources (existing logic works — `get_active_ids` already returns all active IDs regardless of source)

The storia scrape reuses the same browser instance to avoid launching a second browser.

## Duplicate Detection

Heuristic-based, runs when inserting new storia listings:

1. For each new storia listing, query imobiliare listings with the same price AND same room count (extracted from details)
2. If any match also shares at least one location word (e.g., "Decebal", "Unirii"), flag as `possible_duplicate_of = <imobiliare_listing_id>`
3. This is intentionally loose — false positives are acceptable since it's just a visual hint, not a merge

### DB function

`find_possible_duplicate(price, details, location, exclude_source)` — returns the ID of a potential duplicate from the other source, or None.

## Dashboard Changes

### Source label

In the card meta row (bottom of each card, next to the date), show the source:

- Small text label: "imobiliare" or "storia" in `var(--text-muted)` color
- Positioned left side of the meta row, before the date

### Duplicate tag

If `possible_duplicate_of` is set, show a "Possible duplicate" badge:

- Styled similar to `.badge-removed` but with a different color (e.g., `#b45309` amber)
- Positioned in the photo grid area (top-left, same spot as New/Listed badges)
- Not shown simultaneously with "New" badge — "New" takes priority, duplicate badge shown for non-new listings only

### No new filter tabs

Storia listings appear in the existing New/All/Removed tabs alongside imobiliare listings. No separate tab for storia.

## What Is NOT In Scope

- No storia-specific Telegram notifications (the existing notification system will naturally pick up new storia listings since they go through the same `insert_listings` + `notify_new_listings` flow)
- No filtering by source on the dashboard
- No cross-source merging (just flagging)
- No storia backfill mode (photo backfill can be added later if needed)
- No storia seed mode

## Testing Strategy

- `storia_scraper.py` pure helper functions (ID extraction, URL building) get unit tests
- DB functions (`find_possible_duplicate`, source column queries) get unit tests
- Integration testing of the actual storia.ro scraping requires manual verification since the DOM structure is unknown until implementation
- Server endpoint tests verify source and duplicate fields are returned in API responses
