# Storia.ro Integration — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add storia.ro as a second listing source, with source labels on cards and heuristic duplicate detection.

**Architecture:** New `storia_scraper.py` module handles storia-specific DOM parsing. The existing `scraper.py` orchestrates both sources in `run_normal()`. Two new DB columns (`source`, `possible_duplicate_of`) with migrations. Dashboard shows source labels and duplicate badges.

**Tech Stack:** Python/Playwright (storia_scraper.py), SQLite (db.py), Flask (server.py), vanilla HTML/JS/CSS (dashboard.html)

**Important note:** Storia.ro blocks non-browser requests (403), so the DOM structure cannot be known ahead of time. Task 3 is a manual discovery step where the implementer must load storia.ro in Playwright, inspect the DOM, and document the selectors before writing the scraper. The selectors shown in Task 4 are best-guess placeholders that MUST be replaced with the real selectors discovered in Task 3.

---

### Task 1: Add `source` and `possible_duplicate_of` columns to schema

**Files:**
- Modify: `db.py:20-57` (init_db function)
- Modify: `db.py:73-95` (insert_listings function)
- Modify: `tests/test_db.py`

- [ ] **Step 1: Write failing test for source column**

In `tests/test_db.py`, add:

```python
def test_init_db_creates_source_column():
    """init_db should create listings table with source column."""
    import sqlite3
    conn = sqlite3.connect(db._get_db_path())
    cursor = conn.execute("PRAGMA table_info(listings)")
    columns = {row[1] for row in cursor.fetchall()}
    conn.close()
    assert "source" in columns
    assert "possible_duplicate_of" in columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python3 -m pytest tests/test_db.py::test_init_db_creates_source_column -v`
Expected: FAIL — `source` not in columns

- [ ] **Step 3: Update schema and add migrations**

In `db.py`, update the CREATE TABLE for listings to include the new columns:

```python
conn.execute("""
    CREATE TABLE IF NOT EXISTS listings (
        id TEXT PRIMARY KEY,
        title TEXT,
        price TEXT,
        location TEXT,
        details TEXT,
        url TEXT,
        photo_urls TEXT DEFAULT '[]',
        first_seen DATETIME,
        is_new INTEGER DEFAULT 1,
        removed_at DATETIME DEFAULT NULL,
        source TEXT DEFAULT 'imobiliare',
        possible_duplicate_of TEXT DEFAULT NULL
    )
""")
```

Add migrations after the existing `removed_at` migration (before `conn.commit()`):

```python
# Migrate: add source if missing (existing DBs)
try:
    conn.execute("ALTER TABLE listings ADD COLUMN source TEXT DEFAULT 'imobiliare'")
except sqlite3.OperationalError:
    pass
# Migrate: add possible_duplicate_of if missing (existing DBs)
try:
    conn.execute("ALTER TABLE listings ADD COLUMN possible_duplicate_of TEXT DEFAULT NULL")
except sqlite3.OperationalError:
    pass
```

- [ ] **Step 4: Update `insert_listings` to accept source**

In `db.py`, update `insert_listings`:

```python
def insert_listings(listings, source="imobiliare"):
    if not listings:
        return
    conn = _connect()
    now = datetime.now(timezone.utc).isoformat()
    for listing in listings:
        conn.execute(
            """INSERT OR IGNORE INTO listings
               (id, title, price, location, details, url, photo_urls, first_seen, is_new, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (
                listing["id"],
                listing.get("title", ""),
                listing.get("price", ""),
                listing.get("location", ""),
                listing.get("details", ""),
                listing.get("url", ""),
                json.dumps(listing.get("photo_urls", [])),
                now,
                source,
            ),
        )
    conn.commit()
    conn.close()
```

- [ ] **Step 5: Write test for insert with source**

In `tests/test_db.py`, add:

```python
def test_insert_listings_with_source():
    """insert_listings stores the source field."""
    db.insert_listings([_make_listing(id="s1")], source="storia")
    result = db.get_listings(page=1, per_page=50, filter_type="all")
    assert result["listings"][0]["source"] == "storia"


def test_insert_listings_default_source():
    """insert_listings defaults source to imobiliare."""
    db.insert_listings([_make_listing(id="s2")])
    result = db.get_listings(page=1, per_page=50, filter_type="all")
    assert result["listings"][0]["source"] == "imobiliare"
```

- [ ] **Step 6: Run all tests**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python3 -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add db.py tests/test_db.py
git commit -m "feat: add source and possible_duplicate_of columns to listings"
```

---

### Task 2: Add duplicate detection DB function

**Files:**
- Modify: `db.py` (add function)
- Modify: `tests/test_db.py`

- [ ] **Step 1: Write failing test for find_possible_duplicate**

In `tests/test_db.py`, add:

```python
def test_find_possible_duplicate_match():
    """find_possible_duplicate finds a listing with same price and overlapping location."""
    db.insert_listings([_make_listing(id="imo1", price="500 EUR", location="Decebal", details="2 camere")], source="imobiliare")
    result = db.find_possible_duplicate(price="500 EUR", details="2 camere", location="Decebal", exclude_source="storia")
    assert result == "imo1"


def test_find_possible_duplicate_no_match():
    """find_possible_duplicate returns None when no match."""
    db.insert_listings([_make_listing(id="imo2", price="500 EUR", location="Decebal")], source="imobiliare")
    result = db.find_possible_duplicate(price="700 EUR", details="", location="Decebal", exclude_source="storia")
    assert result is None


def test_find_possible_duplicate_same_source_excluded():
    """find_possible_duplicate does not match listings from the same source."""
    db.insert_listings([_make_listing(id="st1", price="500 EUR", location="Decebal")], source="storia")
    result = db.find_possible_duplicate(price="500 EUR", details="", location="Decebal", exclude_source="storia")
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python3 -m pytest tests/test_db.py::test_find_possible_duplicate_match tests/test_db.py::test_find_possible_duplicate_no_match tests/test_db.py::test_find_possible_duplicate_same_source_excluded -v`
Expected: FAIL

- [ ] **Step 3: Implement find_possible_duplicate**

In `db.py`, add:

```python
def find_possible_duplicate(price, details, location, exclude_source):
    """Find a listing from another source with matching price and overlapping location.

    Returns the ID of the first match, or None.
    """
    if not price or not location:
        return None
    conn = _connect()
    # Find listings from the other source with the same price
    rows = conn.execute(
        "SELECT id, location FROM listings WHERE source != ? AND price = ? AND removed_at IS NULL",
        (exclude_source, price),
    ).fetchall()
    conn.close()

    # Check for overlapping location words (at least one significant word in common)
    location_words = {w.lower() for w in location.split() if len(w) > 2}
    for row in rows:
        other_words = {w.lower() for w in row["location"].split() if len(w) > 2}
        if location_words & other_words:
            return row["id"]
    return None


def set_possible_duplicate(listing_id, duplicate_of_id):
    """Set the possible_duplicate_of field for a listing."""
    conn = _connect()
    conn.execute(
        "UPDATE listings SET possible_duplicate_of = ? WHERE id = ?",
        (duplicate_of_id, listing_id),
    )
    conn.commit()
    conn.close()
```

- [ ] **Step 4: Run tests**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python3 -m pytest tests/test_db.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add db.py tests/test_db.py
git commit -m "feat: add duplicate detection function"
```

---

### Task 3: Discover storia.ro DOM structure

**Files:**
- Create: `docs/storia-dom-notes.md` (temporary reference)

This is a manual exploration task. You must load storia.ro in Playwright and document the actual DOM structure.

- [ ] **Step 1: Write a discovery script**

Create a temporary script `discover_storia.py`:

```python
"""Temporary script to explore storia.ro DOM structure.
Run: python3 discover_storia.py
Delete after documenting findings in docs/storia-dom-notes.md
"""
import time
from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync


def discover():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=False)  # headless=False to see the page
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        )
        page = context.new_page()
        stealth_sync(page)

        # Load a search results page
        url = "https://www.storia.ro/ro/rezultate/inchiriere/apartament/bucuresti/decebal?priceMin=300&priceMax=800&roomsNumber=%5BTWO%2CTHREE%5D"
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(5)  # let JS render

        # Dump page structure for analysis
        # 1. Find listing card elements
        print("=== LOOKING FOR LISTING CARDS ===")
        for selector in [
            "[data-cy='search.listing']",
            "[data-cy='listing-item']",
            "article",
            "[data-testid]",
            "a[href*='/ro/oferta/']",
            "li[data-cy]",
        ]:
            elements = page.query_selector_all(selector)
            if elements:
                print(f"\n>>> Found {len(elements)} elements matching: {selector}")
                # Print first element's outer HTML (truncated)
                html = elements[0].evaluate("el => el.outerHTML")
                print(html[:2000])

        # 2. Check for pagination
        print("\n=== LOOKING FOR PAGINATION ===")
        for selector in [
            "nav[data-cy='pagination']",
            "[data-cy='pagination']",
            "nav[role='navigation']",
            ".pagination",
            "a[href*='page=']",
        ]:
            elements = page.query_selector_all(selector)
            if elements:
                print(f"\n>>> Found {len(elements)} elements matching: {selector}")
                html = elements[0].evaluate("el => el.outerHTML")
                print(html[:2000])

        # 3. Get full page HTML for searching
        content = page.content()
        # Look for JSON data
        import re
        json_scripts = re.findall(r'<script[^>]*type="application/(?:ld\+)?json"[^>]*>(.*?)</script>', content, re.DOTALL)
        for i, script in enumerate(json_scripts):
            print(f"\n=== JSON SCRIPT {i} ===")
            print(script[:1000])

        # 4. Now load a detail page to find photo structure
        print("\n=== LOOKING FOR DETAIL PAGE PHOTOS ===")
        # Find first listing link
        links = page.query_selector_all("a[href*='/ro/oferta/']")
        if links:
            href = links[0].get_attribute("href")
            if href:
                detail_url = href if href.startswith("http") else f"https://www.storia.ro{href}"
                print(f"Loading detail page: {detail_url}")
                page.goto(detail_url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(3)

                # Look for photo URLs
                detail_content = page.content()
                photo_patterns = re.findall(r'https?://[^"\s]*?\.(?:jpg|jpeg|png|webp)', detail_content)
                cdn_photos = [u for u in set(photo_patterns) if any(cdn in u for cdn in ['ireland', 'apollo', 'img', 'cdn', 'static'])]
                print(f"Found {len(cdn_photos)} potential photo URLs:")
                for u in cdn_photos[:10]:
                    print(f"  {u}")

        input("Press Enter to close browser...")
        browser.close()


if __name__ == "__main__":
    discover()
```

- [ ] **Step 2: Run the discovery script**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python3 discover_storia.py`

Observe the output. The browser will open visibly so you can also use DevTools.

- [ ] **Step 3: Document findings**

Create `docs/storia-dom-notes.md` with the actual findings:

```markdown
# Storia.ro DOM Structure Notes

## Search Results Page

- Listing card selector: [FILL IN - e.g., "article[data-cy='listing-item']"]
- Listing ID: [FILL IN - where the unique ID comes from (URL, data attribute, etc.)]
- Title selector: [FILL IN]
- Price selector: [FILL IN]
- Location selector: [FILL IN]
- Details (rooms, sqm): [FILL IN]
- Listing URL: [FILL IN - href pattern]

## Pagination

- Next page selector: [FILL IN]
- URL pattern: [FILL IN - e.g., "?page=2"]

## Detail Page Photos

- Photo CDN pattern: [FILL IN - e.g., "ireland.apollo.olxcdn.com"]
- Photo selector or extraction method: [FILL IN]

## Working Search URL Format

- Verified URL: [FILL IN - the URL format that actually works for neighborhood searches]
- If neighborhoods need place IDs instead of slugs, document the mapping here
```

- [ ] **Step 4: If search URLs need adjustment, note the correct format**

The spec assumes URLs like `https://www.storia.ro/ro/rezultate/inchiriere/apartament/bucuresti/decebal?priceMin=300&priceMax=800&roomsNumber=%5BTWO%2CTHREE%5D`. If storia.ro uses a different format (e.g., place IDs, different path structure), document the correct URLs in the notes file.

- [ ] **Step 5: Delete the discovery script, commit the notes**

```bash
rm discover_storia.py
git add docs/storia-dom-notes.md
git commit -m "docs: document storia.ro DOM structure from discovery"
```

---

### Task 4: Create storia_scraper.py

**Files:**
- Create: `storia_scraper.py`
- Create: `tests/test_storia_scraper.py`

**IMPORTANT:** This task depends on Task 3's findings. The selectors below are best guesses. Replace them with the actual selectors documented in `docs/storia-dom-notes.md`.

- [ ] **Step 1: Write test for extract_storia_listing_id**

Create `tests/test_storia_scraper.py`:

```python
import pytest


def test_extract_storia_listing_id():
    """extract_storia_listing_id pulls ID from storia URL or data attribute."""
    from storia_scraper import extract_storia_listing_id
    # Update these test cases based on Task 3 findings
    assert extract_storia_listing_id("https://www.storia.ro/ro/oferta/apartament-modern-IDGGhy") == "IDGGhy"
    assert extract_storia_listing_id("") is None
    assert extract_storia_listing_id(None) is None


def test_build_storia_url():
    """build_storia_url prepends base domain to relative paths."""
    from storia_scraper import build_storia_url
    assert build_storia_url("/ro/oferta/test-123") == "https://www.storia.ro/ro/oferta/test-123"
    assert build_storia_url("https://www.storia.ro/ro/oferta/test-123") == "https://www.storia.ro/ro/oferta/test-123"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python3 -m pytest tests/test_storia_scraper.py -v`
Expected: FAIL

- [ ] **Step 3: Create storia_scraper.py with pure helper functions**

Create `storia_scraper.py`:

```python
import logging
import re

STORIA_BASE_URL = "https://www.storia.ro"

log = logging.getLogger("storia_scraper")


def extract_storia_listing_id(url):
    """Extract listing ID from storia.ro URL.

    Storia URLs look like: /ro/oferta/some-title-IDXXX
    The ID is the last segment after the last dash, starting with 'ID'.
    Update this based on actual URL patterns found in Task 3.
    """
    if not url:
        return None
    match = re.search(r'-(ID[A-Za-z0-9]+)(?:\?|$)', url)
    return match.group(1) if match else None


def build_storia_url(path):
    """Prepend base URL to relative paths."""
    if path.startswith("http"):
        return path
    return STORIA_BASE_URL + path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python3 -m pytest tests/test_storia_scraper.py -v`
Expected: PASS

- [ ] **Step 5: Add browser-dependent scraping functions**

Add to `storia_scraper.py`. **Replace all selectors with findings from `docs/storia-dom-notes.md`:**

```python
import random
import time

import config


def _random_delay(delay_range):
    time.sleep(random.uniform(*delay_range))


def extract_storia_listings_from_page(page):
    """Extract listing data from a storia.ro search results page.

    IMPORTANT: The selectors below must match the actual DOM structure
    documented in docs/storia-dom-notes.md. Update them accordingly.
    """
    listings = []

    # UPDATE THIS SELECTOR based on Task 3 findings
    cards = page.query_selector_all("article[data-cy='listing-item']")

    for card in cards:
        try:
            # UPDATE: Extract URL and ID
            link = card.query_selector("a[href*='/ro/oferta/']")
            if not link:
                continue
            href = link.get_attribute("href") or ""
            url = build_storia_url(href)
            listing_id = extract_storia_listing_id(url)
            if not listing_id:
                continue

            # UPDATE: Extract title
            title_el = card.query_selector("h3")
            title = title_el.inner_text().strip() if title_el else ""

            # UPDATE: Extract price
            price_el = card.query_selector("[data-cy='listing-item-price']")
            price = price_el.inner_text().strip() if price_el else ""

            # UPDATE: Extract location
            location_el = card.query_selector("[data-cy='listing-item-location']")
            location = location_el.inner_text().strip() if location_el else ""

            # UPDATE: Extract details (rooms, sqm, etc.)
            details = ""
            detail_els = card.query_selector_all("[data-cy='listing-item-detail']")
            if detail_els:
                details = " | ".join(el.inner_text().strip() for el in detail_els)

            listings.append({
                "id": listing_id,
                "title": title,
                "url": url,
                "price": price,
                "location": location,
                "details": details,
                "photo_urls": [],
            })
        except Exception as e:
            log.warning(f"Failed to extract storia listing: {e}")
            continue

    return listings


def find_storia_next_page(page):
    """Find and return the next page URL for storia.ro pagination.

    UPDATE: Replace selector based on Task 3 findings.
    """
    try:
        # UPDATE THIS SELECTOR
        next_btn = page.query_selector("[data-cy='pagination.next-page']")
        if next_btn:
            href = next_btn.get_attribute("href")
            if href:
                return build_storia_url(href)
    except Exception:
        pass
    return None


def scrape_storia_search_results(page, max_pages):
    """Scrape all pages of storia.ro search results.

    Iterates over config.STORIA_SEARCH_URLS, paginates each one,
    and deduplicates by listing ID.
    """
    all_listings = []
    seen_ids = set()

    for search_url in config.STORIA_SEARCH_URLS:
        log.info(f"Scraping storia: {search_url[:80]}...")
        current_url = search_url
        page_num = 0

        while current_url and page_num < max_pages:
            page_num += 1
            try:
                page.goto(current_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_selector("article", timeout=15000)
            except Exception as e:
                if page_num == 1:
                    log.warning(f"Could not load storia page: {e}. Skipping.")
                break

            listings = extract_storia_listings_from_page(page)
            new_listings = [l for l in listings if l["id"] not in seen_ids]
            for l in new_listings:
                seen_ids.add(l["id"])
            all_listings.extend(new_listings)
            log.info(f"  Storia page {page_num}: {len(listings)} cards, {len(new_listings)} new")

            if len(new_listings) == 0:
                log.info(f"  No new storia listings on page {page_num}, moving on")
                break

            current_url = find_storia_next_page(page)
            if current_url and page_num < max_pages:
                _random_delay(config.PAGINATION_DELAY)

        _random_delay(config.PAGINATION_DELAY)

    return all_listings


def fetch_storia_photos(page, url, max_photos):
    """Visit a storia detail page and extract photo URLs.

    UPDATE: The CDN pattern and extraction method based on Task 3 findings.
    """
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        content = page.content()

        # UPDATE: Use the actual CDN domain found in Task 3
        pattern = r'https?://[^"\'\s]*?\.(?:jpg|jpeg|png|webp)'
        urls = re.findall(pattern, content, re.IGNORECASE)

        seen = set()
        unique = []
        for u in urls:
            # UPDATE: Filter to storia's CDN and skip thumbnails
            if u not in seen and ("apollo" in u or "ireland" in u or "cdn" in u):
                seen.add(u)
                unique.append(u)
        return unique[:max_photos]
    except Exception as e:
        log.warning(f"Failed to fetch storia photos from {url}: {e}")
        return []
```

- [ ] **Step 6: Run all tests**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python3 -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add storia_scraper.py tests/test_storia_scraper.py
git commit -m "feat: add storia.ro scraper module"
```

---

### Task 5: Add STORIA_SEARCH_URLS to config

**Files:**
- Modify: `config.py`

- [ ] **Step 1: Add storia search URLs**

In `config.py`, after the existing `SEARCH_URLS` list, add:

```python
# Storia.ro search URLs — same neighborhoods as imobiliare.ro
# UPDATE: Verify these URLs work based on Task 3 findings
STORIA_SEARCH_URLS = [
    "https://www.storia.ro/ro/rezultate/inchiriere/apartament/bucuresti/decebal?priceMin=300&priceMax=800&roomsNumber=%5BTWO%2CTHREE%5D",
    "https://www.storia.ro/ro/rezultate/inchiriere/apartament/bucuresti/alba-iulia?priceMin=300&priceMax=800&roomsNumber=%5BTWO%2CTHREE%5D",
    "https://www.storia.ro/ro/rezultate/inchiriere/apartament/bucuresti/unirii?priceMin=300&priceMax=800&roomsNumber=%5BTWO%2CTHREE%5D",
    "https://www.storia.ro/ro/rezultate/inchiriere/apartament/bucuresti/calea-calarasilor?priceMin=300&priceMax=800&roomsNumber=%5BTWO%2CTHREE%5D",
]
```

- [ ] **Step 2: Commit**

```bash
git add config.py
git commit -m "feat: add storia.ro search URLs to config"
```

---

### Task 6: Integrate storia scraping into run_normal

**Files:**
- Modify: `scraper.py` (run_normal function)
- Modify: `telegram_notify.py` (update link text for storia)

- [ ] **Step 1: Add storia import to scraper.py**

At the top of `scraper.py`, add:

```python
import storia_scraper
```

- [ ] **Step 2: Update run_normal to scrape storia**

In `scraper.py`, inside `run_normal()`, after the imobiliare scraping + insertion block (after line 353 `log.info("Scraper complete: no new listings")`), and BEFORE the removal detection block, add storia scraping:

```python
                # --- Storia scraping ---
                log.info("Starting storia.ro scrape...")
                storia_listings = storia_scraper.scrape_storia_search_results(page, config.MAX_PAGES)
                storia_total = len(storia_listings)
                total_count += storia_total

                if storia_listings:
                    storia_ids = [l["id"] for l in storia_listings]
                    existing_storia_ids = db.get_existing_ids(storia_ids)
                    new_storia = [l for l in storia_listings if l["id"] not in existing_storia_ids]
                    log.info(f"Storia: {storia_total} total, {len(new_storia)} new")

                    for listing in new_storia:
                        log.info(f"Fetching storia photos for {listing['id']}: {listing['url']}")
                        listing["photo_urls"] = storia_scraper.fetch_storia_photos(page, listing["url"], config.MAX_PHOTOS)
                        log.info(f"  Got {len(listing['photo_urls'])} photos")
                        _random_delay(config.DETAIL_PAGE_DELAY)

                    if new_storia:
                        db.insert_listings(new_storia, source="storia")
                        new_count += len(new_storia)

                        # Duplicate detection
                        for listing in new_storia:
                            dup_id = db.find_possible_duplicate(
                                price=listing.get("price", ""),
                                details=listing.get("details", ""),
                                location=listing.get("location", ""),
                                exclude_source="storia",
                            )
                            if dup_id:
                                db.set_possible_duplicate(listing["id"], dup_id)
                                log.info(f"  Possible duplicate: {listing['id']} ~ {dup_id}")

                        telegram_notify.notify_new_listings(new_storia)
                        log.info(f"Storia complete: {len(new_storia)} new listings added")
                    else:
                        log.info("Storia complete: no new listings")

                    # Add storia IDs to scraped_ids for removal detection
                    all_ids.extend(storia_ids)
```

- [ ] **Step 3: Update removal detection to include storia IDs**

No code change needed — the `all_ids.extend(storia_ids)` line above ensures storia listings aren't falsely marked as removed. The existing removal detection block uses `set(all_ids)` which will now include both sources.

- [ ] **Step 4: Update telegram_notify.py for storia links**

In `telegram_notify.py`, update `_format_listing_text` to handle both sources:

```python
def _format_listing_text(listing):
    """Format a listing into a Telegram message with HTML."""
    parts = []
    parts.append(f"<b>{listing.get('price', 'No price')}</b>")
    if listing.get("title"):
        parts.append(listing["title"])
    if listing.get("location"):
        parts.append(f"📍 {listing['location']}")
    if listing.get("details"):
        parts.append(listing["details"])
    source = listing.get("source", "imobiliare")
    if source == "storia":
        parts.append(f"\n<a href=\"{listing['url']}\">View on storia.ro</a>")
    else:
        parts.append(f"\n<a href=\"{listing['url']}\">View on imobiliare.ro</a>")
    return "\n".join(parts)
```

Note: `listing` dicts from the scraper don't have a `source` field — it's only in the DB. We need to add it before passing to telegram. In the storia scraping block above, add after `db.insert_listings(new_storia, source="storia")`:

```python
                        # Tag source for telegram notification
                        for l in new_storia:
                            l["source"] = "storia"
```

- [ ] **Step 5: Run all tests**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python3 -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add scraper.py telegram_notify.py
git commit -m "feat: integrate storia.ro scraping into run_normal with duplicate detection"
```

---

### Task 7: Add source label and duplicate badge to dashboard

**Files:**
- Modify: `dashboard.html`

- [ ] **Step 1: Add CSS for source label and duplicate badge**

In `dashboard.html`, after the `.badge-removed` CSS block, add:

```css
.card-source {
    font-size: 11px;
    color: var(--text-muted);
    font-weight: 500;
    text-transform: lowercase;
}

.badge-duplicate {
    position: absolute;
    top: 10px;
    left: 10px;
    background: #b45309;
    color: #fff;
    font-size: 11px;
    font-weight: 600;
    padding: 3px 10px;
    border-radius: 20px;
    z-index: 3;
    letter-spacing: 0.03em;
}
```

- [ ] **Step 2: Add source label to card meta row**

In the `renderListings` function, find the card-meta div:

```javascript
<div class="card-meta">
    <span class="card-date">${dateStr}</span>
    ${l.is_new && !l.removed_at ? `<button class="btn-ack" onclick="acknowledge('${l.id}')">Mark seen</button>` : ''}
</div>
```

Replace with:

```javascript
<div class="card-meta">
    <span class="card-date">${dateStr}${l.source && l.source !== 'imobiliare' ? ` · <span class="card-source">${esc(l.source)}</span>` : ''}</span>
    ${l.is_new && !l.removed_at ? `<button class="btn-ack" onclick="acknowledge('${l.id}')">Mark seen</button>` : ''}
</div>
```

- [ ] **Step 3: Add duplicate badge to card photos area**

In the badge rendering section, find:

```javascript
${l.is_new ? '<span class="badge-new">New</span>' : ''}
${l.removed_at ? `<span class="badge-removed">${durationLabel(l.first_seen, l.removed_at)}</span>` : ''}
```

Replace with:

```javascript
${l.is_new ? '<span class="badge-new">New</span>' : ''}
${l.removed_at ? `<span class="badge-removed">${durationLabel(l.first_seen, l.removed_at)}</span>` : ''}
${!l.is_new && l.possible_duplicate_of ? '<span class="badge-duplicate">Possible duplicate</span>' : ''}
```

- [ ] **Step 4: Run server tests**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python3 -m pytest tests/test_server.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add dashboard.html
git commit -m "feat: add source label and duplicate badge to dashboard cards"
```

---

### Task 8: Add server tests for new fields

**Files:**
- Modify: `tests/test_server.py`

- [ ] **Step 1: Add test for source field in API response**

In `tests/test_server.py`, add:

```python
def test_get_listings_includes_source(client):
    """GET /api/listings returns source field for each listing."""
    db.insert_listings([_make_listing(id="src1")], source="storia")
    resp = client.get("/api/listings?filter=all")
    data = resp.get_json()
    assert data["listings"][0]["source"] == "storia"


def test_get_listings_includes_possible_duplicate(client):
    """GET /api/listings returns possible_duplicate_of field."""
    db.insert_listings([_make_listing(id="d1")], source="imobiliare")
    db.insert_listings([_make_listing(id="d2", price="500 EUR/luna", location="Decebal")], source="storia")
    db.set_possible_duplicate("d2", "d1")
    resp = client.get("/api/listings?filter=all")
    data = resp.get_json()
    storia_listing = [l for l in data["listings"] if l["id"] == "d2"][0]
    assert storia_listing["possible_duplicate_of"] == "d1"
```

- [ ] **Step 2: Run tests**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python3 -m pytest tests/test_server.py -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_server.py
git commit -m "test: add server tests for source and duplicate fields"
```

---

### Task 9: Final integration verification

- [ ] **Step 1: Run full test suite**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python3 -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 2: Manual smoke test**

Start the server: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python3 server.py`

Verify:
1. Dashboard loads at http://localhost:5000
2. Existing listings show normally (source defaults to `imobiliare`)
3. API response includes `source` and `possible_duplicate_of` fields: `curl http://localhost:5000/api/listings?filter=all | python3 -m json.tool | head -30`

- [ ] **Step 3: Test storia scraping manually (optional)**

Run the scraper once to verify storia.ro integration works end-to-end:
`cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python3 scraper.py`

Check logs for storia scraping output and verify new listings appear in the dashboard.

- [ ] **Step 4: Commit any fixups**

```bash
git add -A
git commit -m "feat: complete storia.ro integration"
```
