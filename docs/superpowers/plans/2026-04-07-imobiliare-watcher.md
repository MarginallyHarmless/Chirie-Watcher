# Imobiliare.ro Apartment Watcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Playwright-based scraper that monitors imobiliare.ro apartment listings and serves them via a local Flask dashboard.

**Architecture:** PM2 triggers `scraper.py` hourly, which writes to SQLite. Flask serves a dark-themed dashboard on localhost:5000. Three scraper modes: normal (hourly), seed (initial bulk import), backfill (photo fetching).

**Tech Stack:** Python 3, Playwright + playwright-stealth, SQLite (stdlib), Flask, PM2, single-file HTML/CSS/JS dashboard.

---

## File Map

| File | Responsibility |
|---|---|
| `config.py` | All configuration constants |
| `db.py` | SQLite connection, schema, all queries |
| `scraper.py` | Playwright browser automation, 3 modes, photo extraction |
| `server.py` | Flask API + static file serving |
| `dashboard.html` | Single-file frontend UI |
| `requirements.txt` | Python dependencies |
| `ecosystem.config.js` | PM2 process definitions |
| `README.md` | Setup and usage instructions |
| `tests/test_db.py` | Database layer tests |
| `tests/test_server.py` | Flask API tests |
| `tests/test_scraper.py` | Scraper parsing/extraction tests |

---

### Task 1: Project Setup and Configuration

**Files:**
- Create: `config.py`
- Create: `requirements.txt`

- [ ] **Step 1: Create `requirements.txt`**

```
playwright==1.52.0
playwright-stealth==1.0.6
flask==3.1.1
pytest==8.3.5
```

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && cat requirements.txt`

- [ ] **Step 2: Create `config.py`**

```python
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
```

- [ ] **Step 3: Install dependencies**

Run:
```bash
cd "/Users/bmacmini/Documents/vibes/Imobiliare bot"
pip install -r requirements.txt
playwright install chromium
```

- [ ] **Step 4: Commit**

```bash
git add config.py requirements.txt
git commit -m "feat: add project config and dependencies"
```

---

### Task 2: Database Layer

**Files:**
- Create: `db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write failing tests for `init_db` and `insert_listings`**

Create `tests/__init__.py` (empty) and `tests/test_db.py`:

```python
import os
import json
import tempfile
import pytest

# Override DB_PATH before importing db
_tmp_dir = tempfile.mkdtemp()
os.environ["IMOBILIARE_DB_PATH"] = os.path.join(_tmp_dir, "test.db")

import db


@pytest.fixture(autouse=True)
def fresh_db():
    """Recreate the DB before each test."""
    path = db._get_db_path()
    if os.path.exists(path):
        os.remove(path)
    db.init_db()
    yield
    if os.path.exists(path):
        os.remove(path)


def _make_listing(id="123", title="Nice apt", price="500 EUR/luna",
                  location="Sector 1", details="2 rooms", url="https://example.com/123",
                  photo_urls=None):
    return {
        "id": id,
        "title": title,
        "price": price,
        "location": location,
        "details": details,
        "url": url,
        "photo_urls": photo_urls or [],
    }


def test_init_db_creates_table():
    """init_db should create the listings table."""
    import sqlite3
    conn = sqlite3.connect(db._get_db_path())
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='listings'")
    assert cursor.fetchone() is not None
    conn.close()


def test_insert_and_get_listings():
    """insert_listings should store listings retrievable via get_listings."""
    listings = [_make_listing(id="1"), _make_listing(id="2")]
    db.insert_listings(listings)
    result = db.get_listings(page=1, per_page=50, filter_type="all")
    assert result["total"] == 2
    assert len(result["listings"]) == 2
    # newest first
    assert result["listings"][0]["is_new"] == 1


def test_get_existing_ids():
    """get_existing_ids should return IDs that are already in the DB."""
    db.insert_listings([_make_listing(id="aaa"), _make_listing(id="bbb")])
    existing = db.get_existing_ids(["aaa", "bbb", "ccc"])
    assert existing == {"aaa", "bbb"}


def test_get_existing_ids_empty():
    """get_existing_ids with no matches returns empty set."""
    assert db.get_existing_ids(["xyz"]) == set()


def test_acknowledge():
    """acknowledge should set is_new to 0."""
    db.insert_listings([_make_listing(id="ack1")])
    db.acknowledge("ack1")
    result = db.get_listings(page=1, per_page=50, filter_type="all")
    assert result["listings"][0]["is_new"] == 0


def test_clear_all():
    """clear_all should remove all listings."""
    db.insert_listings([_make_listing(id="c1"), _make_listing(id="c2")])
    db.clear_all()
    result = db.get_listings(page=1, per_page=50, filter_type="all")
    assert result["total"] == 0


def test_get_last_scrape_time_empty():
    """get_last_scrape_time returns None when DB is empty."""
    assert db.get_last_scrape_time() is None


def test_get_last_scrape_time():
    """get_last_scrape_time returns most recent first_seen."""
    db.insert_listings([_make_listing(id="t1"), _make_listing(id="t2")])
    result = db.get_last_scrape_time()
    assert result is not None


def test_filter_new_only():
    """get_listings with filter 'new' returns only is_new=1 listings."""
    db.insert_listings([_make_listing(id="n1"), _make_listing(id="n2")])
    db.acknowledge("n1")
    result = db.get_listings(page=1, per_page=50, filter_type="new")
    assert result["total"] == 1
    assert result["listings"][0]["id"] == "n2"


def test_pagination():
    """get_listings should paginate correctly."""
    listings = [_make_listing(id=str(i)) for i in range(5)]
    db.insert_listings(listings)
    page1 = db.get_listings(page=1, per_page=2, filter_type="all")
    assert len(page1["listings"]) == 2
    assert page1["total"] == 5
    page3 = db.get_listings(page=3, per_page=2, filter_type="all")
    assert len(page3["listings"]) == 1


def test_photo_urls_stored_as_json():
    """photo_urls should round-trip as a list."""
    urls = ["https://cdn.example.com/1.jpg", "https://cdn.example.com/2.jpg"]
    db.insert_listings([_make_listing(id="p1", photo_urls=urls)])
    result = db.get_listings(page=1, per_page=50, filter_type="all")
    assert result["listings"][0]["photo_urls"] == urls


def test_get_listings_without_photos():
    """get_listings_without_photos returns listings with empty photo_urls."""
    db.insert_listings([
        _make_listing(id="wp1", photo_urls=[]),
        _make_listing(id="wp2", photo_urls=["https://cdn.example.com/a.jpg"]),
    ])
    result = db.get_listings_without_photos(limit=10)
    assert len(result) == 1
    assert result[0]["id"] == "wp1"


def test_update_photos():
    """update_photos should set photo_urls for a listing."""
    db.insert_listings([_make_listing(id="up1")])
    new_urls = ["https://cdn.example.com/x.jpg"]
    db.update_photos("up1", new_urls)
    result = db.get_listings(page=1, per_page=50, filter_type="all")
    assert result["listings"][0]["photo_urls"] == new_urls
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python -m pytest tests/test_db.py -v`

Expected: ModuleNotFoundError for `db`

- [ ] **Step 3: Implement `db.py`**

```python
import os
import json
import sqlite3
from datetime import datetime, timezone

import config


def _get_db_path():
    return os.environ.get("IMOBILIARE_DB_PATH", os.path.expanduser(config.DB_PATH))


def _connect():
    path = _get_db_path()
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    path = _get_db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = _connect()
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
            is_new INTEGER DEFAULT 1
        )
    """)
    conn.commit()
    conn.close()


def get_existing_ids(ids):
    if not ids:
        return set()
    conn = _connect()
    placeholders = ",".join("?" for _ in ids)
    cursor = conn.execute(
        f"SELECT id FROM listings WHERE id IN ({placeholders})", list(ids)
    )
    result = {row["id"] for row in cursor.fetchall()}
    conn.close()
    return result


def insert_listings(listings):
    if not listings:
        return
    conn = _connect()
    now = datetime.now(timezone.utc).isoformat()
    for listing in listings:
        conn.execute(
            """INSERT OR IGNORE INTO listings
               (id, title, price, location, details, url, photo_urls, first_seen, is_new)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)""",
            (
                listing["id"],
                listing.get("title", ""),
                listing.get("price", ""),
                listing.get("location", ""),
                listing.get("details", ""),
                listing.get("url", ""),
                json.dumps(listing.get("photo_urls", [])),
                now,
            ),
        )
    conn.commit()
    conn.close()


def get_listings(page=1, per_page=50, filter_type="all"):
    conn = _connect()
    where = "WHERE is_new = 1" if filter_type == "new" else ""

    count_row = conn.execute(f"SELECT COUNT(*) as cnt FROM listings {where}").fetchone()
    total = count_row["cnt"]

    offset = (page - 1) * per_page
    rows = conn.execute(
        f"SELECT * FROM listings {where} ORDER BY first_seen DESC LIMIT ? OFFSET ?",
        (per_page, offset),
    ).fetchall()

    listings = []
    for row in rows:
        listing = dict(row)
        listing["photo_urls"] = json.loads(listing["photo_urls"])
        listings.append(listing)

    conn.close()
    return {"listings": listings, "total": total, "page": page, "per_page": per_page}


def acknowledge(listing_id):
    conn = _connect()
    conn.execute("UPDATE listings SET is_new = 0 WHERE id = ?", (listing_id,))
    conn.commit()
    conn.close()


def clear_all():
    conn = _connect()
    conn.execute("DELETE FROM listings")
    conn.commit()
    conn.close()


def get_last_scrape_time():
    conn = _connect()
    row = conn.execute(
        "SELECT MAX(first_seen) as last FROM listings"
    ).fetchone()
    conn.close()
    if row and row["last"]:
        return row["last"]
    return None


def get_listings_without_photos(limit=10):
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM listings WHERE photo_urls = '[]' LIMIT ?", (limit,)
    ).fetchall()
    result = [dict(row) for row in rows]
    conn.close()
    return result


def update_photos(listing_id, photo_urls):
    conn = _connect()
    conn.execute(
        "UPDATE listings SET photo_urls = ? WHERE id = ?",
        (json.dumps(photo_urls), listing_id),
    )
    conn.commit()
    conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python -m pytest tests/test_db.py -v`

Expected: All 13 tests PASS

- [ ] **Step 5: Commit**

```bash
git add db.py tests/__init__.py tests/test_db.py
git commit -m "feat: add database layer with full test coverage"
```

---

### Task 3: Flask API Server

**Files:**
- Create: `server.py`
- Create: `tests/test_server.py`

- [ ] **Step 1: Write failing tests for all API endpoints**

Create `tests/test_server.py`:

```python
import os
import json
import tempfile
import pytest

_tmp_dir = tempfile.mkdtemp()
os.environ["IMOBILIARE_DB_PATH"] = os.path.join(_tmp_dir, "test_server.db")

import db
import server


@pytest.fixture(autouse=True)
def fresh_db():
    path = db._get_db_path()
    if os.path.exists(path):
        os.remove(path)
    db.init_db()
    yield
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def client():
    server.app.config["TESTING"] = True
    with server.app.test_client() as c:
        yield c


def _make_listing(id="123", title="Nice apt", price="500 EUR/luna",
                  location="Sector 1", details="2 rooms", url="https://example.com/123",
                  photo_urls=None):
    return {
        "id": id, "title": title, "price": price, "location": location,
        "details": details, "url": url, "photo_urls": photo_urls or [],
    }


def test_get_listings_empty(client):
    """GET /api/listings with empty DB returns empty list."""
    resp = client.get("/api/listings")
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["listings"] == []
    assert data["total"] == 0
    assert data["scraper_healthy"] is False
    assert data["last_scrape"] is None


def test_get_listings_returns_data(client):
    """GET /api/listings returns inserted listings."""
    db.insert_listings([_make_listing(id="a1"), _make_listing(id="a2")])
    resp = client.get("/api/listings?page=1&per_page=50&filter=all")
    data = resp.get_json()
    assert data["total"] == 2
    assert len(data["listings"]) == 2


def test_get_listings_filter_new(client):
    """GET /api/listings?filter=new returns only new listings."""
    db.insert_listings([_make_listing(id="f1"), _make_listing(id="f2")])
    db.acknowledge("f1")
    resp = client.get("/api/listings?filter=new")
    data = resp.get_json()
    assert data["total"] == 1
    assert data["listings"][0]["id"] == "f2"


def test_get_listings_pagination(client):
    """GET /api/listings with pagination params works."""
    db.insert_listings([_make_listing(id=str(i)) for i in range(5)])
    resp = client.get("/api/listings?page=1&per_page=2&filter=all")
    data = resp.get_json()
    assert len(data["listings"]) == 2
    assert data["total"] == 5


def test_acknowledge(client):
    """POST /api/listings/<id>/acknowledge sets is_new=0."""
    db.insert_listings([_make_listing(id="ack1")])
    resp = client.post("/api/listings/ack1/acknowledge")
    assert resp.status_code == 200
    assert resp.get_json() == {"ok": True}
    result = db.get_listings(page=1, per_page=50, filter_type="all")
    assert result["listings"][0]["is_new"] == 0


def test_clear_requires_token(client):
    """POST /api/clear without valid token returns 403."""
    resp = client.post("/api/clear")
    assert resp.status_code == 403


def test_clear_with_wrong_token(client):
    """POST /api/clear with wrong token returns 403."""
    resp = client.post("/api/clear?token=WRONG")
    assert resp.status_code == 403


def test_clear_with_valid_token(client):
    """POST /api/clear with correct token wipes DB."""
    db.insert_listings([_make_listing(id="cl1")])
    import config
    resp = client.post(f"/api/clear?token={config.CLEAR_TOKEN}")
    assert resp.status_code == 200
    result = db.get_listings(page=1, per_page=50, filter_type="all")
    assert result["total"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python -m pytest tests/test_server.py -v`

Expected: ModuleNotFoundError for `server`

- [ ] **Step 3: Implement `server.py`**

```python
import os
from datetime import datetime, timezone, timedelta

from flask import Flask, jsonify, request, send_file

import config
import db

app = Flask(__name__)


@app.before_request
def ensure_db():
    db.init_db()


@app.route("/")
def index():
    return send_file("dashboard.html")


@app.route("/api/listings")
def get_listings():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 50, type=int)
    filter_type = request.args.get("filter", "new")

    result = db.get_listings(page=page, per_page=per_page, filter_type=filter_type)

    last_scrape = db.get_last_scrape_time()
    scraper_healthy = False
    if last_scrape:
        last_dt = datetime.fromisoformat(last_scrape)
        if last_dt.tzinfo is None:
            last_dt = last_dt.replace(tzinfo=timezone.utc)
        scraper_healthy = (datetime.now(timezone.utc) - last_dt) < timedelta(hours=2)

    result["last_scrape"] = last_scrape
    result["scraper_healthy"] = scraper_healthy
    return jsonify(result)


@app.route("/api/listings/<listing_id>/acknowledge", methods=["POST"])
def acknowledge_listing(listing_id):
    db.acknowledge(listing_id)
    return jsonify({"ok": True})


@app.route("/api/clear", methods=["POST"])
def clear():
    token = request.args.get("token", "")
    if token != config.CLEAR_TOKEN:
        return jsonify({"error": "forbidden"}), 403
    db.clear_all()
    return jsonify({"ok": True})


if __name__ == "__main__":
    db.init_db()
    app.run(host="127.0.0.1", port=5000, debug=True)
```

- [ ] **Step 4: Create a minimal `dashboard.html` placeholder** (so `send_file` doesn't crash during testing)

```html
<!DOCTYPE html>
<html><body><p>Dashboard placeholder</p></body></html>
```

This is a temporary placeholder — the full dashboard is built in Task 5.

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python -m pytest tests/test_server.py -v`

Expected: All 8 tests PASS

- [ ] **Step 6: Commit**

```bash
git add server.py tests/test_server.py dashboard.html
git commit -m "feat: add Flask API server with test coverage"
```

---

### Task 4: Scraper Core

**Files:**
- Create: `scraper.py`
- Create: `tests/test_scraper.py`

The scraper has two parts that can be tested without a real browser:
1. **Parsing logic** — extracting listing data from HTML
2. **Photo extraction logic** — finding image URLs in page content

Browser automation itself is tested manually (it requires a real site).

- [ ] **Step 1: Write failing tests for parsing and photo extraction helpers**

Create `tests/test_scraper.py`:

```python
import json
import pytest


def test_extract_listing_id():
    """extract_listing_id pulls numeric ID from DOM id attribute."""
    from scraper import extract_listing_id
    assert extract_listing_id("listing-link-275384395") == "275384395"
    assert extract_listing_id("listing-link-12345") == "12345"
    assert extract_listing_id("") is None
    assert extract_listing_id(None) is None


def test_extract_photos_from_json():
    """extract_photos_from_json finds CDN image URLs in script content."""
    from scraper import extract_photos_from_json
    script_content = '''
    {"images": [
        {"url": "https://cdn.imobiliare.ro/foto/1.jpg"},
        {"url": "https://cdn.imobiliare.ro/foto/2.jpg"},
        {"url": "https://cdn.imobiliare.ro/foto/3.jpg"}
    ]}
    '''
    urls = extract_photos_from_json(script_content, max_photos=10)
    assert len(urls) == 3
    assert all("cdn.imobiliare.ro" in u for u in urls)


def test_extract_photos_from_json_caps_at_max():
    """extract_photos_from_json respects max_photos limit."""
    from scraper import extract_photos_from_json
    script_content = json.dumps({
        "images": [{"url": f"https://cdn.imobiliare.ro/foto/{i}.jpg"} for i in range(20)]
    })
    urls = extract_photos_from_json(script_content, max_photos=10)
    assert len(urls) == 10


def test_extract_photos_from_json_deduplicates():
    """extract_photos_from_json removes duplicate URLs."""
    from scraper import extract_photos_from_json
    script_content = '''
    {"images": [
        {"url": "https://cdn.imobiliare.ro/foto/1.jpg"},
        {"url": "https://cdn.imobiliare.ro/foto/1.jpg"},
        {"url": "https://cdn.imobiliare.ro/foto/2.jpg"}
    ]}
    '''
    urls = extract_photos_from_json(script_content, max_photos=10)
    assert len(urls) == 2


def test_extract_photos_from_json_no_match():
    """extract_photos_from_json returns empty list when no CDN URLs found."""
    from scraper import extract_photos_from_json
    assert extract_photos_from_json("no images here", max_photos=10) == []
    assert extract_photos_from_json("", max_photos=10) == []


def test_build_full_url():
    """build_full_url prepends base domain to relative paths."""
    from scraper import build_full_url
    assert build_full_url("/ro/inchiriere/123") == "https://www.imobiliare.ro/ro/inchiriere/123"
    assert build_full_url("https://www.imobiliare.ro/ro/123") == "https://www.imobiliare.ro/ro/123"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python -m pytest tests/test_scraper.py -v`

Expected: ImportError

- [ ] **Step 3: Implement `scraper.py`**

```python
import argparse
import json
import logging
import random
import re
import sys
import time

from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

import config
import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("scraper")

BASE_URL = "https://www.imobiliare.ro"
LISTING_SELECTOR = 'a[data-cy="listing-information-link"]'


# --- Pure helper functions (testable without browser) ---

def extract_listing_id(dom_id):
    """Extract numeric listing ID from DOM id like 'listing-link-275384395'."""
    if not dom_id:
        return None
    match = re.search(r"(\d+)$", dom_id)
    return match.group(1) if match else None


def extract_photos_from_json(text, max_photos=10):
    """Find CDN image URLs in page text (script tags, inline JSON, etc).

    Searches for URLs matching common imobiliare.ro CDN patterns.
    Deduplicates and caps at max_photos.
    """
    if not text:
        return []
    pattern = r'https?://[^"\'\\s]*?imobiliare\.ro[^"\'\\s]*?\.(?:jpg|jpeg|png|webp)'
    urls = re.findall(pattern, text, re.IGNORECASE)
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique[:max_photos]


def build_full_url(path):
    """Prepend base URL to relative paths."""
    if path.startswith("http"):
        return path
    return BASE_URL + path


# --- Browser-dependent functions ---

def _random_delay(delay_range):
    time.sleep(random.uniform(*delay_range))


def _launch_browser(pw):
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    )
    page = context.new_page()
    stealth_sync(page)
    return browser, page


def _load_search_page(page, url, retry=True):
    """Load a search page, retry once on failure."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_selector(LISTING_SELECTOR, timeout=15000)
        return True
    except Exception as e:
        if retry:
            log.warning(f"Page load failed: {e}. Retrying in 30s...")
            time.sleep(30)
            return _load_search_page(page, url, retry=False)
        log.error(f"Page load failed after retry: {e}")
        return False


def _extract_listings_from_page(page):
    """Extract listing data from the current search results page."""
    listings = []
    cards = page.query_selector_all(LISTING_SELECTOR)
    for card in cards:
        dom_id = card.get_attribute("id")
        listing_id = extract_listing_id(dom_id)
        if not listing_id:
            continue

        href = card.get_attribute("href") or ""
        url = build_full_url(href)

        # Extract text content from card and surrounding elements
        parent = card.evaluate_handle("el => el.closest('.listing-card, [class*=listing], [class*=card], article') || el.parentElement.parentElement")

        title = ""
        price = ""
        location = ""
        details = ""

        try:
            title = card.inner_text().strip()
        except Exception:
            pass

        try:
            parent_text = parent.evaluate("el => el.innerText")
            lines = [l.strip() for l in parent_text.split("\n") if l.strip()]
            # Heuristic: price usually contains EUR or lei or €
            for line in lines:
                if not price and re.search(r'(EUR|€|lei|luna)', line, re.IGNORECASE):
                    price = line
                elif not location and re.search(r'(sector|bucuresti|zona|cartier)', line, re.IGNORECASE):
                    location = line
            # Details: anything with rooms/sqm/floor info
            for line in lines:
                if re.search(r'(camer|mp|etaj|suprafata|room)', line, re.IGNORECASE):
                    if line != price and line != location:
                        details = line
                        break
        except Exception:
            pass

        listings.append({
            "id": listing_id,
            "title": title,
            "url": url,
            "price": price,
            "location": location,
            "details": details,
            "photo_urls": [],
        })

    return listings


def _find_next_page(page):
    """Find and return the next page URL, or None if no next page."""
    try:
        next_btn = page.query_selector('a[rel="next"], .pagination a:has-text("Urm"), .pagination a:has-text("next"), [aria-label="Next"]')
        if next_btn:
            href = next_btn.get_attribute("href")
            if href:
                return build_full_url(href)
    except Exception:
        pass
    return None


def _fetch_photos(page, url, max_photos):
    """Visit a listing detail page and extract photo URLs."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        # Try JSON extraction first (more reliable)
        page_content = page.content()
        photos = extract_photos_from_json(page_content, max_photos)
        if photos:
            return photos

        # Fallback: extract from img tags
        imgs = page.query_selector_all("img")
        urls = []
        seen = set()
        for img in imgs:
            src = img.get_attribute("src") or ""
            if "imobiliare" in src and re.search(r'\.(jpg|jpeg|png|webp)', src, re.IGNORECASE):
                if src not in seen:
                    seen.add(src)
                    urls.append(src)
                    if len(urls) >= max_photos:
                        break
        return urls
    except Exception as e:
        log.warning(f"Failed to fetch photos from {url}: {e}")
        return []


def scrape_search_results(page, max_pages):
    """Scrape all pages of search results. Returns list of listing dicts."""
    all_listings = []
    current_url = config.SEARCH_URL
    page_num = 0

    while current_url and page_num < max_pages:
        page_num += 1
        if not _load_search_page(page, current_url):
            if page_num == 1:
                log.error("Could not load first page. Exiting.")
                sys.exit(1)
            break

        listings = _extract_listings_from_page(page)
        log.info(f"Page {page_num}: found {len(listings)} listings")
        all_listings.extend(listings)

        current_url = _find_next_page(page)
        if current_url and page_num < max_pages:
            _random_delay(config.PAGINATION_DELAY)

    return all_listings


def run_normal():
    """Normal mode: scrape search results, fetch photos for new listings only."""
    db.init_db()
    with sync_playwright() as pw:
        browser, page = _launch_browser(pw)
        try:
            all_listings = scrape_search_results(page, config.MAX_PAGES)
            if not all_listings:
                log.info("No listings found on search page.")
                return

            all_ids = [l["id"] for l in all_listings]
            existing_ids = db.get_existing_ids(all_ids)
            new_listings = [l for l in all_listings if l["id"] not in existing_ids]
            log.info(f"Found {len(all_listings)} total, {len(new_listings)} new")

            for listing in new_listings:
                log.info(f"Fetching photos for {listing['id']}: {listing['url']}")
                listing["photo_urls"] = _fetch_photos(page, listing["url"], config.MAX_PHOTOS)
                log.info(f"  Got {len(listing['photo_urls'])} photos")
                _random_delay(config.DETAIL_PAGE_DELAY)

            if new_listings:
                db.insert_listings(new_listings)
                log.info(f"Scraper complete: {len(new_listings)} new listings added")

                # PHASE 2: Send Telegram notification for new listings
                # TODO: implement when scraping is verified working
                # - Use sendMessage for listing details (title, price, location, url)
                # - Use sendMediaGroup to send up to 10 photos per listing (from photo_urls)
                # - Bot token and chat ID go in config.py
                # def notify_telegram(listings): ...
            else:
                log.info("Scraper complete: no new listings")
        finally:
            browser.close()


def run_seed():
    """Seed mode: scrape all pages, no photo fetching."""
    db.init_db()
    with sync_playwright() as pw:
        browser, page = _launch_browser(pw)
        try:
            all_listings = scrape_search_results(page, config.SEED_MAX_PAGES)
            if not all_listings:
                log.info("No listings found.")
                return

            all_ids = [l["id"] for l in all_listings]
            existing_ids = db.get_existing_ids(all_ids)
            new_listings = [l for l in all_listings if l["id"] not in existing_ids]
            log.info(f"Seed: {len(all_listings)} total scraped, {len(new_listings)} new to insert")

            if new_listings:
                db.insert_listings(new_listings)
                log.info(f"Seed complete: {len(new_listings)} listings inserted (no photos)")
            else:
                log.info("Seed complete: all listings already in DB")
        finally:
            browser.close()


def run_backfill():
    """Backfill mode: fetch photos for listings that have none."""
    db.init_db()
    listings = db.get_listings_without_photos(limit=config.BACKFILL_BATCH_SIZE)
    if not listings:
        log.info("Backfill: no listings need photos")
        return

    log.info(f"Backfill: fetching photos for {len(listings)} listings")
    with sync_playwright() as pw:
        browser, page = _launch_browser(pw)
        try:
            for listing in listings:
                url = listing["url"]
                log.info(f"Backfill photos for {listing['id']}: {url}")
                photos = _fetch_photos(page, url, config.MAX_PHOTOS)
                db.update_photos(listing["id"], photos)
                log.info(f"  Got {len(photos)} photos")
                _random_delay(config.DETAIL_PAGE_DELAY)
        finally:
            browser.close()

    log.info("Backfill complete")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Imobiliare.ro apartment scraper")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--seed", action="store_true", help="Seed mode: bulk import, no photos")
    group.add_argument("--backfill", action="store_true", help="Backfill mode: fetch missing photos")
    args = parser.parse_args()

    if args.seed:
        run_seed()
    elif args.backfill:
        run_backfill()
    else:
        run_normal()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python -m pytest tests/test_scraper.py -v`

Expected: All 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add scraper.py tests/test_scraper.py
git commit -m "feat: add scraper with normal, seed, and backfill modes"
```

---

### Task 5: Dashboard Frontend

**Files:**
- Modify: `dashboard.html` (replace placeholder)

- [ ] **Step 1: Implement the full `dashboard.html`**

Replace the placeholder with the full single-file dashboard:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Imobiliare Watcher</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            background: #0a0a0a;
            color: #c0c0c0;
            font-family: 'IBM Plex Mono', 'Courier New', monospace;
            font-size: 14px;
            line-height: 1.5;
        }

        .header {
            background: #111;
            border-bottom: 1px solid #222;
            padding: 16px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
            position: sticky;
            top: 0;
            z-index: 100;
        }

        .header h1 {
            color: #00ff41;
            font-size: 18px;
            font-weight: 600;
        }

        .header-info {
            display: flex;
            align-items: center;
            gap: 16px;
            font-size: 12px;
        }

        .health-dot {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            margin-right: 6px;
        }

        .health-dot.healthy { background: #00ff41; }
        .health-dot.unhealthy { background: #ff4141; }

        .warning-banner {
            background: #1a1000;
            border: 1px solid #ff4141;
            color: #ff4141;
            padding: 8px 24px;
            font-size: 12px;
            display: none;
        }

        .controls {
            padding: 16px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #1a1a1a;
        }

        .filter-toggle {
            display: flex;
            gap: 0;
        }

        .filter-btn {
            background: #1a1a1a;
            color: #888;
            border: 1px solid #333;
            padding: 6px 16px;
            font-family: inherit;
            font-size: 12px;
            cursor: pointer;
        }

        .filter-btn:first-child { border-radius: 4px 0 0 4px; }
        .filter-btn:last-child { border-radius: 0 4px 4px 0; border-left: none; }

        .filter-btn.active {
            background: #00ff41;
            color: #0a0a0a;
            border-color: #00ff41;
        }

        .pagination {
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 12px;
        }

        .pagination button {
            background: #1a1a1a;
            color: #c0c0c0;
            border: 1px solid #333;
            padding: 4px 12px;
            font-family: inherit;
            font-size: 12px;
            cursor: pointer;
            border-radius: 4px;
        }

        .pagination button:disabled {
            opacity: 0.3;
            cursor: default;
        }

        .pagination button:hover:not(:disabled) {
            border-color: #00ff41;
            color: #00ff41;
        }

        .listings {
            padding: 16px 24px;
            display: flex;
            flex-direction: column;
            gap: 16px;
        }

        .card {
            background: #111;
            border: 1px solid #222;
            border-radius: 6px;
            padding: 16px;
            transition: opacity 0.3s;
        }

        .card.seen {
            opacity: 0.5;
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 12px;
            margin-bottom: 8px;
        }

        .card-title {
            color: #e0e0e0;
            font-weight: 600;
            text-decoration: none;
        }

        .card-title:hover {
            color: #00ff41;
        }

        .badge-new {
            background: #00ff41;
            color: #0a0a0a;
            font-size: 10px;
            font-weight: 600;
            padding: 2px 8px;
            border-radius: 3px;
            white-space: nowrap;
        }

        .card-details {
            font-size: 13px;
            margin-bottom: 12px;
        }

        .card-details .price {
            color: #00ff41;
            font-weight: 600;
            font-size: 16px;
        }

        .card-details .location,
        .card-details .info {
            color: #888;
            margin-top: 4px;
        }

        .photo-strip {
            display: flex;
            gap: 8px;
            overflow-x: auto;
            padding: 8px 0;
            scrollbar-width: thin;
            scrollbar-color: #333 transparent;
        }

        .photo-strip::-webkit-scrollbar {
            height: 6px;
        }

        .photo-strip::-webkit-scrollbar-thumb {
            background: #333;
            border-radius: 3px;
        }

        .photo-strip img {
            height: 100px;
            border-radius: 4px;
            cursor: pointer;
            border: 1px solid #222;
            flex-shrink: 0;
        }

        .photo-strip img:hover {
            border-color: #00ff41;
        }

        .photo-count {
            font-size: 11px;
            color: #666;
            margin-top: 4px;
        }

        .card-actions {
            margin-top: 12px;
        }

        .btn-ack {
            background: transparent;
            color: #00ff41;
            border: 1px solid #00ff41;
            padding: 4px 12px;
            font-family: inherit;
            font-size: 12px;
            cursor: pointer;
            border-radius: 4px;
        }

        .btn-ack:hover {
            background: #00ff41;
            color: #0a0a0a;
        }

        .empty-state {
            text-align: center;
            padding: 48px;
            color: #555;
        }

        .total-count {
            font-size: 12px;
            color: #555;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>// imobiliare watcher</h1>
        <div class="header-info">
            <span id="lastScrape">Last scrape: --</span>
            <span><span class="health-dot" id="healthDot"></span><span id="healthText">--</span></span>
        </div>
    </div>
    <div class="warning-banner" id="warningBanner">Scraper may be down - last successful run was over 2 hours ago</div>
    <div class="controls">
        <div class="filter-toggle">
            <button class="filter-btn active" data-filter="new" onclick="setFilter('new')">New only</button>
            <button class="filter-btn" data-filter="all" onclick="setFilter('all')">All</button>
        </div>
        <span class="total-count" id="totalCount"></span>
        <div class="pagination">
            <button id="prevBtn" onclick="prevPage()" disabled>&lt; Prev</button>
            <span id="pageInfo">--</span>
            <button id="nextBtn" onclick="nextPage()" disabled>Next &gt;</button>
        </div>
    </div>
    <div class="listings" id="listings"></div>

    <script>
        let currentPage = 1;
        let currentFilter = 'new';
        const perPage = 50;
        let totalPages = 1;
        let refreshTimer = null;

        async function fetchListings() {
            try {
                const resp = await fetch(`/api/listings?page=${currentPage}&per_page=${perPage}&filter=${currentFilter}`);
                const data = await resp.json();
                renderListings(data);
                updateHeader(data);
                updatePagination(data);
            } catch (e) {
                console.error('Fetch failed:', e);
            }
        }

        function renderListings(data) {
            const container = document.getElementById('listings');
            if (!data.listings.length) {
                container.innerHTML = '<div class="empty-state">No listings found</div>';
                return;
            }
            container.innerHTML = data.listings.map(l => `
                <div class="card ${l.is_new ? '' : 'seen'}" id="card-${l.id}">
                    <div class="card-header">
                        <a class="card-title" href="${l.url}" target="_blank">${esc(l.title || 'Untitled')}</a>
                        ${l.is_new ? '<span class="badge-new">NEW</span>' : ''}
                    </div>
                    <div class="card-details">
                        <div class="price">${esc(l.price || 'No price')}</div>
                        <div class="location">${esc(l.location || '')}</div>
                        <div class="info">${esc(l.details || '')}</div>
                    </div>
                    ${l.photo_urls && l.photo_urls.length ? `
                        <div class="photo-strip">
                            ${l.photo_urls.map(url => `<img src="${esc(url)}" onclick="window.open('${esc(url)}', '_blank')" alt="photo" loading="lazy">`).join('')}
                        </div>
                        <div class="photo-count">${l.photo_urls.length} photo${l.photo_urls.length !== 1 ? 's' : ''}</div>
                    ` : ''}
                    ${l.is_new ? `
                        <div class="card-actions">
                            <button class="btn-ack" onclick="acknowledge('${l.id}')">Mark as seen</button>
                        </div>
                    ` : ''}
                </div>
            `).join('');
        }

        function updateHeader(data) {
            const lastScrape = data.last_scrape
                ? new Date(data.last_scrape).toLocaleString()
                : 'Never';
            document.getElementById('lastScrape').textContent = `Last scrape: ${lastScrape}`;

            const dot = document.getElementById('healthDot');
            const text = document.getElementById('healthText');
            const banner = document.getElementById('warningBanner');

            if (data.last_scrape === null) {
                dot.className = 'health-dot unhealthy';
                text.textContent = 'No data';
                banner.style.display = 'block';
            } else if (data.scraper_healthy) {
                dot.className = 'health-dot healthy';
                text.textContent = 'Healthy';
                banner.style.display = 'none';
            } else {
                dot.className = 'health-dot unhealthy';
                text.textContent = 'Stale';
                banner.style.display = 'block';
            }
        }

        function updatePagination(data) {
            totalPages = Math.max(1, Math.ceil(data.total / perPage));
            document.getElementById('pageInfo').textContent = `${currentPage} / ${totalPages}`;
            document.getElementById('prevBtn').disabled = currentPage <= 1;
            document.getElementById('nextBtn').disabled = currentPage >= totalPages;
            document.getElementById('totalCount').textContent = `${data.total} listings`;
        }

        function setFilter(f) {
            currentFilter = f;
            currentPage = 1;
            document.querySelectorAll('.filter-btn').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.filter === f);
            });
            fetchListings();
        }

        function prevPage() {
            if (currentPage > 1) { currentPage--; fetchListings(); }
        }

        function nextPage() {
            if (currentPage < totalPages) { currentPage++; fetchListings(); }
        }

        async function acknowledge(id) {
            try {
                await fetch(`/api/listings/${id}/acknowledge`, { method: 'POST' });
                const card = document.getElementById(`card-${id}`);
                if (card) {
                    card.classList.add('seen');
                    const badge = card.querySelector('.badge-new');
                    if (badge) badge.remove();
                    const actions = card.querySelector('.card-actions');
                    if (actions) actions.remove();
                }
            } catch (e) {
                console.error('Acknowledge failed:', e);
            }
        }

        function esc(str) {
            const div = document.createElement('div');
            div.textContent = str;
            return div.innerHTML;
        }

        // Initial load
        fetchListings();

        // Auto-refresh every 60 seconds
        refreshTimer = setInterval(fetchListings, 60000);
    </script>
</body>
</html>
```

- [ ] **Step 2: Manually verify the dashboard**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python server.py`

Open `http://localhost:5000` in a browser. Verify:
- Dark theme with green accents renders
- "No listings found" empty state shows
- Header shows "Last scrape: Never" and red health dot
- Stop the server with Ctrl+C

- [ ] **Step 3: Commit**

```bash
git add dashboard.html
git commit -m "feat: add dark-themed monitoring dashboard with pagination and filters"
```

---

### Task 6: PM2 Configuration and README

**Files:**
- Create: `ecosystem.config.js`
- Create: `README.md`

- [ ] **Step 1: Create `ecosystem.config.js`**

```javascript
module.exports = {
  apps: [
    {
      name: "imobiliare-dashboard",
      script: "python3",
      args: "server.py",
      cwd: __dirname,
      autorestart: true,
      max_restarts: 10,
    },
    {
      name: "imobiliare-scraper",
      script: "python3",
      args: "scraper.py",
      cwd: __dirname,
      cron_restart: "0 * * * *",
      autorestart: false,
    },
  ],
};
```

- [ ] **Step 2: Create `README.md`**

```markdown
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
```

- [ ] **Step 3: Commit**

```bash
git add ecosystem.config.js README.md
git commit -m "feat: add PM2 config and README with setup instructions"
```

---

### Task 7: Integration Smoke Test

This task verifies everything works end-to-end before the user pastes their real URL.

- [ ] **Step 1: Run the full test suite**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python -m pytest tests/ -v`

Expected: All tests pass (db: 13, server: 8, scraper: 7 = 28 total)

- [ ] **Step 2: Verify the dashboard starts**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && timeout 5 python server.py || true`

Expected: Flask starts on 127.0.0.1:5000 without errors

- [ ] **Step 3: Verify scraper argument parsing**

Run:
```bash
cd "/Users/bmacmini/Documents/vibes/Imobiliare bot"
python scraper.py --help
```

Expected: Shows help text with `--seed` and `--backfill` options

- [ ] **Step 4: Final commit (if any fixes were needed)**

```bash
git add -A
git commit -m "fix: address issues found during integration smoke test"
```

Only commit if changes were made. If all passed cleanly, skip this step.
