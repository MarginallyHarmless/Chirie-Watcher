# Settings Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a dashboard settings page to edit scraper config (neighborhoods, price, rooms, hours) at runtime, plus a "run now" button.

**Architecture:** Settings move from hardcoded `config.py` constants to a `settings` table in SQLite. A new `url_builder.py` module builds search URLs from those settings. The scraper reads settings from DB on each run. The server exposes GET/PUT `/api/settings` and POST `/api/scrape` endpoints. A new `settings.html` page provides the UI.

**Tech Stack:** Python 3, SQLite, Flask, vanilla HTML/CSS/JS (same as existing dashboard).

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `db.py` | Modify | Add `settings` table creation in `init_db`, add `get_settings()`, `update_settings()`, `start_scrape_log()`, `finish_scrape_log()`, `is_scrape_running()` |
| `url_builder.py` | Create | Build imobiliare and storia URLs from settings dict |
| `server.py` | Modify | Add `/settings` route, `GET/PUT /api/settings`, `POST /api/scrape`, `GET /api/scrape/status` |
| `scraper.py` | Modify | Read settings from DB, use url_builder, pass neighborhoods to storia_scraper, use start/finish scrape log |
| `storia_scraper.py` | Modify | Accept `neighborhoods` parameter instead of reading `config.STORIA_NEIGHBORHOODS` |
| `settings.html` | Create | Settings page UI |
| `dashboard.html` | Modify | Add Settings nav link to header |
| `log.html` | Modify | Add Settings nav link to header |
| `tests/test_db.py` | Modify | Tests for settings and scrape log functions |
| `tests/test_url_builder.py` | Create | Tests for URL building |
| `tests/test_server.py` | Modify | Tests for settings and scrape API endpoints |
| `tests/test_storia_scraper.py` | Modify | Update tests for neighborhoods parameter |

---

### Task 1: Settings table and DB functions

**Files:**
- Modify: `db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write failing tests for get_settings and update_settings**

Add to the end of `tests/test_db.py`:

```python
def test_init_db_creates_settings_table():
    """init_db should create the settings table."""
    import sqlite3
    conn = sqlite3.connect(db._get_db_path())
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
    assert cursor.fetchone() is not None
    conn.close()


def test_get_settings_returns_defaults():
    """get_settings returns default values on fresh DB."""
    settings = db.get_settings()
    assert settings["neighborhoods"] == ["decebal", "alba iulia", "unirii", "calea calarasilor", "calarasilor"]
    assert settings["price_min"] == 300
    assert settings["price_max"] == 800
    assert settings["rooms"] == [2, 3]
    assert settings["scraper_start_hour"] == 8
    assert settings["scraper_end_hour"] == 23


def test_update_settings_writes_and_reads():
    """update_settings persists changes that get_settings returns."""
    db.update_settings({
        "neighborhoods": ["militari", "drumul taberei"],
        "price_min": 200,
        "price_max": 600,
        "rooms": [1, 2],
        "scraper_start_hour": 9,
        "scraper_end_hour": 22,
    })
    settings = db.get_settings()
    assert settings["neighborhoods"] == ["militari", "drumul taberei"]
    assert settings["price_min"] == 200
    assert settings["price_max"] == 600
    assert settings["rooms"] == [1, 2]
    assert settings["scraper_start_hour"] == 9
    assert settings["scraper_end_hour"] == 22


def test_get_settings_called_twice_returns_same():
    """get_settings is idempotent — no duplicate row issues."""
    s1 = db.get_settings()
    s2 = db.get_settings()
    assert s1 == s2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_db.py::test_init_db_creates_settings_table tests/test_db.py::test_get_settings_returns_defaults tests/test_db.py::test_update_settings_writes_and_reads tests/test_db.py::test_get_settings_called_twice_returns_same -v`
Expected: FAIL with `AttributeError: module 'db' has no attribute 'get_settings'`

- [ ] **Step 3: Implement settings table and functions in db.py**

Add the settings table creation at the end of `init_db()` (after the existing migration blocks, before `conn.commit()`):

```python
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            neighborhoods TEXT NOT NULL,
            price_min INTEGER NOT NULL,
            price_max INTEGER NOT NULL,
            rooms TEXT NOT NULL,
            scraper_start_hour INTEGER NOT NULL,
            scraper_end_hour INTEGER NOT NULL
        )
    """)
```

Add two new functions after `set_possible_duplicate()`:

```python
def get_settings():
    """Return current settings as a dict, creating defaults if needed."""
    conn = _connect()
    row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    if not row:
        conn.execute(
            """INSERT INTO settings (id, neighborhoods, price_min, price_max, rooms,
               scraper_start_hour, scraper_end_hour)
               VALUES (1, ?, ?, ?, ?, ?, ?)""",
            (
                json.dumps(config.STORIA_NEIGHBORHOODS),
                300,
                800,
                json.dumps([2, 3]),
                config.SCRAPER_START_HOUR,
                config.SCRAPER_END_HOUR,
            ),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    conn.close()
    return {
        "neighborhoods": json.loads(row["neighborhoods"]),
        "price_min": row["price_min"],
        "price_max": row["price_max"],
        "rooms": json.loads(row["rooms"]),
        "scraper_start_hour": row["scraper_start_hour"],
        "scraper_end_hour": row["scraper_end_hour"],
    }


def update_settings(data):
    """Write all settings fields. Caller is responsible for validation."""
    conn = _connect()
    # Ensure the row exists
    get_settings()
    conn.execute(
        """UPDATE settings SET
           neighborhoods = ?, price_min = ?, price_max = ?,
           rooms = ?, scraper_start_hour = ?, scraper_end_hour = ?
           WHERE id = 1""",
        (
            json.dumps(data["neighborhoods"]),
            data["price_min"],
            data["price_max"],
            json.dumps(data["rooms"]),
            data["scraper_start_hour"],
            data["scraper_end_hour"],
        ),
    )
    conn.commit()
    conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_db.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add db.py tests/test_db.py
git commit -m "feat: add settings table with get/update functions"
```

---

### Task 2: Scrape log start/finish and running detection

**Files:**
- Modify: `db.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_db.py`:

```python
def test_start_scrape_log_returns_id():
    """start_scrape_log creates a running entry and returns its ID."""
    log_id = db.start_scrape_log(mode="normal")
    assert isinstance(log_id, int)
    logs = db.get_scrape_logs()
    assert len(logs) == 1
    assert logs[0]["status"] == "running"
    assert logs[0]["finished_at"] is None


def test_finish_scrape_log_updates_entry():
    """finish_scrape_log sets final fields on a running entry."""
    log_id = db.start_scrape_log(mode="normal")
    db.finish_scrape_log(
        log_id=log_id,
        status="success",
        new_listings=3,
        total_found=50,
        error_message=None,
        new_imobiliare=2,
        new_storia=1,
    )
    logs = db.get_scrape_logs()
    assert logs[0]["status"] == "success"
    assert logs[0]["new_listings"] == 3
    assert logs[0]["total_found"] == 50
    assert logs[0]["finished_at"] is not None
    assert logs[0]["duration_seconds"] is not None


def test_is_scrape_running_true():
    """is_scrape_running returns True when a scrape is in progress."""
    db.start_scrape_log(mode="normal")
    assert db.is_scrape_running() is True


def test_is_scrape_running_false_after_finish():
    """is_scrape_running returns False after scrape completes."""
    log_id = db.start_scrape_log(mode="normal")
    db.finish_scrape_log(log_id=log_id, status="success", new_listings=0,
                         total_found=0, error_message=None,
                         new_imobiliare=0, new_storia=0)
    assert db.is_scrape_running() is False


def test_is_scrape_running_false_when_empty():
    """is_scrape_running returns False with no logs."""
    assert db.is_scrape_running() is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_db.py::test_start_scrape_log_returns_id tests/test_db.py::test_finish_scrape_log_updates_entry tests/test_db.py::test_is_scrape_running_true tests/test_db.py::test_is_scrape_running_false_after_finish tests/test_db.py::test_is_scrape_running_false_when_empty -v`
Expected: FAIL with `AttributeError: module 'db' has no attribute 'start_scrape_log'`

- [ ] **Step 3: Implement start_scrape_log, finish_scrape_log, is_scrape_running in db.py**

Add after `update_settings()`:

```python
def start_scrape_log(mode):
    """Insert a 'running' scrape log entry and return its ID."""
    conn = _connect()
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        """INSERT INTO scrape_logs
           (started_at, mode, status, new_listings, total_found,
            new_imobiliare, new_storia)
           VALUES (?, ?, 'running', 0, 0, 0, 0)""",
        (now, mode),
    )
    log_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return log_id


def finish_scrape_log(log_id, status, new_listings, total_found,
                      error_message, new_imobiliare=0, new_storia=0):
    """Update a running scrape log entry with final results."""
    conn = _connect()
    now = datetime.now(timezone.utc).isoformat()
    row = conn.execute("SELECT started_at FROM scrape_logs WHERE id = ?", (log_id,)).fetchone()
    duration = None
    if row and row["started_at"]:
        started = datetime.fromisoformat(row["started_at"])
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        duration = (datetime.now(timezone.utc) - started).total_seconds()
    conn.execute(
        """UPDATE scrape_logs SET
           finished_at = ?, status = ?, new_listings = ?, total_found = ?,
           error_message = ?, duration_seconds = ?,
           new_imobiliare = ?, new_storia = ?
           WHERE id = ?""",
        (now, status, new_listings, total_found, error_message, duration,
         new_imobiliare, new_storia, log_id),
    )
    # Prune to keep only the most recent 200 entries
    conn.execute("""
        DELETE FROM scrape_logs WHERE id NOT IN (
            SELECT id FROM scrape_logs ORDER BY started_at DESC LIMIT 200
        )
    """)
    conn.commit()
    conn.close()


def is_scrape_running():
    """Check if a scrape is currently in progress."""
    conn = _connect()
    row = conn.execute(
        """SELECT id FROM scrape_logs
           WHERE status = 'running'
           AND started_at > datetime('now', '-30 minutes')
           LIMIT 1"""
    ).fetchone()
    conn.close()
    return row is not None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_db.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add db.py tests/test_db.py
git commit -m "feat: add start/finish scrape log and running detection"
```

---

### Task 3: URL builder module

**Files:**
- Create: `url_builder.py`
- Create: `tests/test_url_builder.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_url_builder.py`:

```python
import pytest


def test_build_imobiliare_urls_basic():
    """build_imobiliare_urls generates one URL per neighborhood."""
    from url_builder import build_imobiliare_urls
    settings = {
        "neighborhoods": ["decebal", "alba iulia"],
        "price_min": 300,
        "price_max": 800,
        "rooms": [2, 3],
    }
    urls = build_imobiliare_urls(settings)
    assert len(urls) == 2
    assert urls[0] == "https://www.imobiliare.ro/inchirieri-apartamente/bucuresti/decebal?rooms=2,3&price=300-800"
    assert urls[1] == "https://www.imobiliare.ro/inchirieri-apartamente/bucuresti/alba-iulia?rooms=2,3&price=300-800"


def test_build_imobiliare_urls_slugifies():
    """build_imobiliare_urls converts spaces to hyphens in neighborhood names."""
    from url_builder import build_imobiliare_urls
    settings = {
        "neighborhoods": ["calea calarasilor"],
        "price_min": 400,
        "price_max": 700,
        "rooms": [1],
    }
    urls = build_imobiliare_urls(settings)
    assert urls[0] == "https://www.imobiliare.ro/inchirieri-apartamente/bucuresti/calea-calarasilor?rooms=1&price=400-700"


def test_build_imobiliare_urls_empty():
    """build_imobiliare_urls returns empty list for no neighborhoods."""
    from url_builder import build_imobiliare_urls
    settings = {"neighborhoods": [], "price_min": 300, "price_max": 800, "rooms": [2]}
    assert build_imobiliare_urls(settings) == []


def test_build_storia_urls_basic():
    """build_storia_urls generates a single city-level URL."""
    from url_builder import build_storia_urls
    settings = {
        "price_min": 300,
        "price_max": 800,
        "rooms": [2, 3],
    }
    urls = build_storia_urls(settings)
    assert len(urls) == 1
    url = urls[0]
    assert "priceMin=300" in url
    assert "priceMax=800" in url
    assert "roomsNumber=" in url
    # Should contain encoded TWO and THREE
    assert "TWO" in url
    assert "THREE" in url


def test_build_storia_urls_single_room():
    """build_storia_urls handles single room count."""
    from url_builder import build_storia_urls
    settings = {"price_min": 200, "price_max": 500, "rooms": [1]}
    urls = build_storia_urls(settings)
    assert len(urls) == 1
    assert "ONE" in urls[0]


def test_build_storia_urls_five_rooms():
    """build_storia_urls maps 5 to FIVE_OR_MORE."""
    from url_builder import build_storia_urls
    settings = {"price_min": 200, "price_max": 500, "rooms": [5]}
    urls = build_storia_urls(settings)
    assert "FIVE_OR_MORE" in urls[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_url_builder.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'url_builder'`

- [ ] **Step 3: Implement url_builder.py**

Create `url_builder.py`:

```python
from urllib.parse import quote


IMOBILIARE_BASE = "https://www.imobiliare.ro/inchirieri-apartamente/bucuresti"
STORIA_BASE = "https://www.storia.ro/ro/rezultate/inchiriere/apartament/bucuresti"

ROOM_MAP_STORIA = {1: "ONE", 2: "TWO", 3: "THREE", 4: "FOUR", 5: "FIVE_OR_MORE"}


def build_imobiliare_urls(settings):
    """Build one imobiliare.ro search URL per neighborhood."""
    rooms_str = ",".join(str(r) for r in sorted(settings["rooms"]))
    price_str = f"{settings['price_min']}-{settings['price_max']}"
    urls = []
    for neighborhood in settings["neighborhoods"]:
        slug = neighborhood.lower().strip().replace(" ", "-")
        urls.append(f"{IMOBILIARE_BASE}/{slug}?rooms={rooms_str}&price={price_str}")
    return urls


def build_storia_urls(settings):
    """Build a single storia.ro city-level search URL."""
    storia_rooms = [ROOM_MAP_STORIA[r] for r in sorted(settings["rooms"]) if r in ROOM_MAP_STORIA]
    rooms_param = quote("[" + ",".join(storia_rooms) + "]")
    return [
        f"{STORIA_BASE}?priceMin={settings['price_min']}&priceMax={settings['price_max']}&roomsNumber={rooms_param}"
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_url_builder.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add url_builder.py tests/test_url_builder.py
git commit -m "feat: add url_builder module for dynamic search URLs"
```

---

### Task 4: Settings API endpoints

**Files:**
- Modify: `server.py`
- Test: `tests/test_server.py`

- [ ] **Step 1: Write failing tests**

Add to the end of `tests/test_server.py`:

```python
def test_get_settings_returns_defaults(client):
    """GET /api/settings returns default settings."""
    resp = client.get("/api/settings")
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["neighborhoods"] == ["decebal", "alba iulia", "unirii", "calea calarasilor", "calarasilor"]
    assert data["price_min"] == 300
    assert data["price_max"] == 800
    assert data["rooms"] == [2, 3]


def test_put_settings_valid(client):
    """PUT /api/settings with valid data updates settings."""
    resp = client.put("/api/settings", json={
        "neighborhoods": ["militari"],
        "price_min": 200,
        "price_max": 600,
        "rooms": [1, 2],
        "scraper_start_hour": 9,
        "scraper_end_hour": 22,
    })
    assert resp.status_code == 200
    # Verify it persisted
    resp2 = client.get("/api/settings")
    data = resp2.get_json()
    assert data["neighborhoods"] == ["militari"]
    assert data["price_min"] == 200


def test_put_settings_empty_neighborhoods(client):
    """PUT /api/settings rejects empty neighborhoods."""
    resp = client.put("/api/settings", json={
        "neighborhoods": [],
        "price_min": 300,
        "price_max": 800,
        "rooms": [2],
        "scraper_start_hour": 8,
        "scraper_end_hour": 23,
    })
    assert resp.status_code == 400


def test_put_settings_invalid_price_range(client):
    """PUT /api/settings rejects min >= max price."""
    resp = client.put("/api/settings", json={
        "neighborhoods": ["decebal"],
        "price_min": 800,
        "price_max": 300,
        "rooms": [2],
        "scraper_start_hour": 8,
        "scraper_end_hour": 23,
    })
    assert resp.status_code == 400


def test_put_settings_invalid_rooms(client):
    """PUT /api/settings rejects rooms outside 1-5."""
    resp = client.put("/api/settings", json={
        "neighborhoods": ["decebal"],
        "price_min": 300,
        "price_max": 800,
        "rooms": [0, 6],
        "scraper_start_hour": 8,
        "scraper_end_hour": 23,
    })
    assert resp.status_code == 400


def test_put_settings_invalid_hours(client):
    """PUT /api/settings rejects start >= end hour."""
    resp = client.put("/api/settings", json={
        "neighborhoods": ["decebal"],
        "price_min": 300,
        "price_max": 800,
        "rooms": [2],
        "scraper_start_hour": 23,
        "scraper_end_hour": 8,
    })
    assert resp.status_code == 400
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_server.py::test_get_settings_returns_defaults tests/test_server.py::test_put_settings_valid tests/test_server.py::test_put_settings_empty_neighborhoods tests/test_server.py::test_put_settings_invalid_price_range tests/test_server.py::test_put_settings_invalid_rooms tests/test_server.py::test_put_settings_invalid_hours -v`
Expected: FAIL with 404

- [ ] **Step 3: Implement settings endpoints in server.py**

Add the following routes to `server.py` (before the `if __name__` block):

```python
@app.route("/settings")
def settings_page():
    return send_file("settings.html")


@app.route("/api/settings", methods=["GET"])
def get_settings():
    settings = db.get_settings()
    return jsonify(settings)


@app.route("/api/settings", methods=["PUT"])
def put_settings():
    data = request.get_json(force=True)
    errors = []

    # Validate neighborhoods
    neighborhoods = data.get("neighborhoods")
    if not isinstance(neighborhoods, list) or len(neighborhoods) == 0:
        errors.append("neighborhoods must be a non-empty list")
    elif not all(isinstance(n, str) and n.strip() for n in neighborhoods):
        errors.append("each neighborhood must be a non-empty string")

    # Validate price
    price_min = data.get("price_min")
    price_max = data.get("price_max")
    if not isinstance(price_min, int) or not isinstance(price_max, int):
        errors.append("price_min and price_max must be integers")
    elif price_min <= 0 or price_max <= 0:
        errors.append("prices must be positive")
    elif price_min >= price_max:
        errors.append("price_min must be less than price_max")

    # Validate rooms
    rooms = data.get("rooms")
    if not isinstance(rooms, list) or len(rooms) == 0:
        errors.append("rooms must be a non-empty list")
    elif not all(isinstance(r, int) and 1 <= r <= 5 for r in rooms):
        errors.append("each room count must be an integer between 1 and 5")

    # Validate hours
    start_hour = data.get("scraper_start_hour")
    end_hour = data.get("scraper_end_hour")
    if not isinstance(start_hour, int) or not isinstance(end_hour, int):
        errors.append("hours must be integers")
    elif not (0 <= start_hour <= 23) or not (0 <= end_hour <= 23):
        errors.append("hours must be between 0 and 23")
    elif start_hour >= end_hour:
        errors.append("scraper_start_hour must be less than scraper_end_hour")

    if errors:
        return jsonify({"errors": errors}), 400

    db.update_settings(data)
    return jsonify({"ok": True})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_server.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_server.py
git commit -m "feat: add GET/PUT /api/settings endpoints with validation"
```

---

### Task 5: Scrape trigger API endpoints

**Files:**
- Modify: `server.py`
- Test: `tests/test_server.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_server.py`:

```python
from unittest.mock import patch


def test_post_scrape_starts_subprocess(client):
    """POST /api/scrape starts a scraper subprocess."""
    with patch("server.subprocess.Popen") as mock_popen:
        resp = client.post("/api/scrape")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "started"
        mock_popen.assert_called_once()


def test_post_scrape_conflict_when_running(client):
    """POST /api/scrape returns 409 when a scrape is already running."""
    db.start_scrape_log(mode="normal")
    resp = client.post("/api/scrape")
    assert resp.status_code == 409
    assert "already running" in resp.get_json()["error"]


def test_get_scrape_status_not_running(client):
    """GET /api/scrape/status returns running=false when idle."""
    resp = client.get("/api/scrape/status")
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["running"] is False


def test_get_scrape_status_running(client):
    """GET /api/scrape/status returns running=true during a scrape."""
    db.start_scrape_log(mode="normal")
    resp = client.get("/api/scrape/status")
    data = resp.get_json()
    assert data["running"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_server.py::test_post_scrape_starts_subprocess tests/test_server.py::test_post_scrape_conflict_when_running tests/test_server.py::test_get_scrape_status_not_running tests/test_server.py::test_get_scrape_status_running -v`
Expected: FAIL with 404

- [ ] **Step 3: Implement scrape trigger endpoints in server.py**

Add `import subprocess` to the top of `server.py`, then add these routes:

```python
@app.route("/api/scrape", methods=["POST"])
def trigger_scrape():
    if db.is_scrape_running():
        return jsonify({"error": "Scrape already running"}), 409
    project_dir = os.path.dirname(os.path.abspath(__file__))
    subprocess.Popen(
        ["python3", "scraper.py"],
        cwd=project_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return jsonify({"status": "started"})


@app.route("/api/scrape/status")
def scrape_status():
    running = db.is_scrape_running()
    result = {"running": running}
    if not running:
        result["last_completed"] = db.get_last_scrape_time()
    return jsonify(result)
```

Also add `import os` and `import subprocess` to the imports at the top of `server.py` if not already present.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_server.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_server.py
git commit -m "feat: add POST /api/scrape and GET /api/scrape/status endpoints"
```

---

### Task 6: Update storia_scraper to accept neighborhoods parameter

**Files:**
- Modify: `storia_scraper.py`
- Test: `tests/test_storia_scraper.py`

- [ ] **Step 1: Write failing tests**

Update the existing neighborhood tests in `tests/test_storia_scraper.py` to pass an explicit neighborhoods list. Also add a test for the new parameter in `scrape_storia_search_results`.

Replace the existing `_matches_neighborhood` tests:

```python
def test_matches_neighborhood_hit():
    """_matches_neighborhood returns True when location contains a configured neighborhood."""
    from storia_scraper import _matches_neighborhood
    neighborhoods = ["decebal", "alba iulia", "calea calarasilor", "calarasilor"]
    assert _matches_neighborhood({"location": "Decebal, Sectorul 3, Bucuresti"}, neighborhoods) is True
    assert _matches_neighborhood({"location": "Alba Iulia, Sectorul 2"}, neighborhoods) is True
    assert _matches_neighborhood({"location": "Calea Calarasilor, Sectorul 3"}, neighborhoods) is True


def test_matches_neighborhood_via_title():
    """_matches_neighborhood matches against title text."""
    from storia_scraper import _matches_neighborhood
    neighborhoods = ["unirii"]
    assert _matches_neighborhood({
        "location": "Bucuresti, Sectorul 3, Centrul Civic",
        "title": "2 Camere | Splaiul Unirii | Decomandat",
    }, neighborhoods) is True


def test_matches_neighborhood_via_description():
    """_matches_neighborhood matches against short_description text."""
    from storia_scraper import _matches_neighborhood
    neighborhoods = ["alba iulia"]
    assert _matches_neighborhood({
        "location": "Bucuresti, Sectorul 4, Vacaresti",
        "title": "Apartament modern 2 camere",
        "short_description": "Situat langa Piata Alba Iulia, zona linistita",
    }, neighborhoods) is True


def test_matches_neighborhood_miss():
    """_matches_neighborhood returns False when no field matches."""
    from storia_scraper import _matches_neighborhood
    neighborhoods = ["decebal", "alba iulia", "unirii"]
    assert _matches_neighborhood({
        "location": "Militari, Sectorul 6, Bucuresti",
        "title": "Apartament 2 camere Militari",
        "short_description": "Bloc nou in Militari Residence",
    }, neighborhoods) is False
    assert _matches_neighborhood({"location": "Drumul Taberei"}, neighborhoods) is False


def test_matches_neighborhood_empty_location():
    """_matches_neighborhood returns False for empty fields."""
    from storia_scraper import _matches_neighborhood
    neighborhoods = ["decebal"]
    assert _matches_neighborhood({"location": ""}, neighborhoods) is False
    assert _matches_neighborhood({"location": "", "title": "", "short_description": ""}, neighborhoods) is False


def test_matches_neighborhood_empty_list():
    """_matches_neighborhood returns True when neighborhoods list is empty (no filter)."""
    from storia_scraper import _matches_neighborhood
    assert _matches_neighborhood({"location": "Anywhere"}, []) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_storia_scraper.py -v`
Expected: FAIL with `TypeError: _matches_neighborhood() takes 1 positional argument but 2 were given`

- [ ] **Step 3: Update _matches_neighborhood and scrape_storia_search_results signatures**

In `storia_scraper.py`, change `_matches_neighborhood` to accept the neighborhoods list:

```python
def _matches_neighborhood(listing, neighborhoods):
    """Check if a listing matches any configured neighborhood.

    Searches location, title, and short_description since storia.ro
    often puts specific neighborhood names in the title or description
    rather than the structured location field.
    """
    if not neighborhoods:
        return True
    text = " ".join([
        listing.get("location", ""),
        listing.get("title", ""),
        listing.get("short_description", ""),
    ]).lower()
    return any(n in text for n in neighborhoods)
```

Update `scrape_storia_search_results` to accept `search_urls` and `neighborhoods` parameters instead of reading from config:

```python
def scrape_storia_search_results(page, search_urls, neighborhoods, max_pages):
    """Scrape storia.ro search results using __NEXT_DATA__ JSON.

    Uses a single city-level URL (neighborhood filtering doesn't work on storia.ro).
    Paginates with &page=N. Filters results by configured neighborhoods.
    """
    all_listings = []
    seen_ids = set()

    for search_url in search_urls:
        log.info(f"Scraping storia: {search_url[:80]}...")
        page_num = 0
        total_pages = None

        while page_num < max_pages:
            page_num += 1
            current_url = search_url if page_num == 1 else f"{search_url}&page={page_num}"

            try:
                page.goto(current_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_selector("script#__NEXT_DATA__", state="attached", timeout=15000)
            except Exception as e:
                if page_num == 1:
                    log.warning(f"Could not load storia page: {e}. Skipping.")
                break

            data = _parse_next_data(page)
            if not data:
                log.warning(f"No __NEXT_DATA__ on storia page {page_num}")
                break

            if total_pages is None:
                total_pages = _get_total_pages(data)
                log.info(f"  Storia: {total_pages} total pages")

            listings = _extract_listings_from_json(data)
            # Filter by neighborhood
            listings = [l for l in listings if _matches_neighborhood(l, neighborhoods)]
            new_listings = [l for l in listings if l["id"] not in seen_ids]
            for l in new_listings:
                seen_ids.add(l["id"])
            all_listings.extend(new_listings)
            log.info(f"  Storia page {page_num}: {len(listings)} in neighborhoods, {len(new_listings)} new")

            if len(new_listings) == 0:
                break

            if total_pages and page_num >= total_pages:
                break

            if page_num < max_pages:
                time.sleep(random.uniform(*config.PAGINATION_DELAY))

        time.sleep(random.uniform(*config.PAGINATION_DELAY))

    return all_listings
```

Remove the `import config` at the top of `storia_scraper.py` if it is no longer needed. Check: `config.PAGINATION_DELAY` is still used, so keep the import.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_storia_scraper.py -v`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add storia_scraper.py tests/test_storia_scraper.py
git commit -m "refactor: pass neighborhoods and URLs to storia_scraper as parameters"
```

---

### Task 7: Wire scraper to use DB settings and new scrape log flow

**Files:**
- Modify: `scraper.py`

- [ ] **Step 1: Update scraper.py imports**

Add at the top of `scraper.py`:

```python
import url_builder
```

- [ ] **Step 2: Update scrape_search_results to accept URLs parameter**

Change the `scrape_search_results` function signature from:

```python
def scrape_search_results(page, max_pages):
```

to:

```python
def scrape_search_results(page, search_urls, max_pages):
```

And change line 298 from `for search_url in config.SEARCH_URLS:` to `for search_url in search_urls:`.

- [ ] **Step 3: Rewrite run_normal to use DB settings and new scrape log**

Replace the `run_normal()` function body to:

1. Call `db.get_settings()` at the start
2. Build URLs with `url_builder`
3. Use `db.start_scrape_log()` / `db.finish_scrape_log()` instead of `db.insert_scrape_log()`
4. Pass `search_urls` to `scrape_search_results`
5. Pass `storia_urls` and `neighborhoods` to `storia_scraper.scrape_storia_search_results`

```python
def run_normal():
    """Normal mode: scrape search results, fetch photos for new listings only."""
    db.init_db()
    settings = db.get_settings()
    search_urls = url_builder.build_imobiliare_urls(settings)
    storia_urls = url_builder.build_storia_urls(settings)
    neighborhoods = settings["neighborhoods"]

    log_id = db.start_scrape_log(mode="normal")
    new_count = 0
    new_imobiliare_count = 0
    new_storia_count = 0
    total_count = 0
    try:
        with sync_playwright() as pw:
            browser, page = _launch_browser(pw)
            try:
                all_listings = scrape_search_results(page, search_urls, config.MAX_PAGES)
                total_count = len(all_listings)
                if not all_listings:
                    log.info("No listings found on search page.")
                else:
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
                        new_imobiliare_count = len(new_listings)
                        new_count = new_imobiliare_count
                        log.info(f"Scraper complete: {new_imobiliare_count} new listings added")
                        telegram_notify.notify_new_listings(new_listings)
                    else:
                        log.info("Scraper complete: no new listings")

                    # --- Storia scraping ---
                    log.info("Starting storia.ro scrape...")
                    storia_listings = storia_scraper.scrape_storia_search_results(
                        page, storia_urls, neighborhoods, config.MAX_PAGES)
                    storia_total = len(storia_listings)
                    total_count += storia_total

                    if storia_listings:
                        storia_ids = [l["id"] for l in storia_listings]
                        existing_storia_ids = db.get_existing_ids(storia_ids)
                        new_storia = [l for l in storia_listings if l["id"] not in existing_storia_ids]
                        log.info(f"Storia: {storia_total} total, {len(new_storia)} new")

                        if new_storia:
                            db.insert_listings(new_storia, source="storia")
                            new_storia_count = len(new_storia)
                            new_count += new_storia_count

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

                            # Tag source for telegram notification
                            for l in new_storia:
                                l["source"] = "storia"
                            telegram_notify.notify_new_listings(new_storia)
                            log.info(f"Storia complete: {len(new_storia)} new listings added")
                        else:
                            log.info("Storia complete: no new listings")

                        # Add storia IDs to scraped_ids for removal detection
                        all_ids.extend(storia_ids)

                    # Detect removed listings
                    scraped_ids = set(all_ids)
                    active_ids = db.get_active_ids()
                    disappeared_ids = active_ids - scraped_ids
                    if disappeared_ids:
                        db.mark_removed(disappeared_ids)
                        log.info(f"Marked {len(disappeared_ids)} listings as removed")

                    # Detect relisted listings
                    removed_ids = db.get_removed_ids()
                    relisted_ids = removed_ids & scraped_ids
                    if relisted_ids:
                        db.relist(relisted_ids)
                        log.info(f"Relisted {len(relisted_ids)} previously removed listings")
            finally:
                browser.close()

        db.finish_scrape_log(
            log_id=log_id,
            status="success",
            new_listings=new_count,
            total_found=total_count,
            error_message=None,
            new_imobiliare=new_imobiliare_count,
            new_storia=new_storia_count,
        )
    except Exception as e:
        db.finish_scrape_log(
            log_id=log_id,
            status="error",
            new_listings=new_count,
            total_found=total_count,
            error_message=str(e),
            new_imobiliare=new_imobiliare_count,
            new_storia=new_storia_count,
        )
        raise
```

- [ ] **Step 4: Update run_seed similarly**

Update `run_seed()` to use `db.get_settings()`, `url_builder.build_imobiliare_urls()`, and `start_scrape_log`/`finish_scrape_log`:

```python
def run_seed():
    """Seed mode: scrape all pages, no photo fetching."""
    db.init_db()
    settings = db.get_settings()
    search_urls = url_builder.build_imobiliare_urls(settings)

    log_id = db.start_scrape_log(mode="seed")
    new_count = 0
    total_count = 0
    try:
        with sync_playwright() as pw:
            browser, page = _launch_browser(pw)
            try:
                all_listings = scrape_search_results(page, search_urls, config.SEED_MAX_PAGES)
                total_count = len(all_listings)
                if not all_listings:
                    log.info("No listings found.")
                else:
                    all_ids = [l["id"] for l in all_listings]
                    existing_ids = db.get_existing_ids(all_ids)
                    new_listings = [l for l in all_listings if l["id"] not in existing_ids]
                    log.info(f"Seed: {len(all_listings)} total scraped, {len(new_listings)} new to insert")

                    if new_listings:
                        db.insert_listings(new_listings)
                        new_count = len(new_listings)
                        log.info(f"Seed complete: {new_count} listings inserted (no photos)")
                    else:
                        log.info("Seed complete: all listings already in DB")
            finally:
                browser.close()

        db.finish_scrape_log(
            log_id=log_id, status="success", new_listings=new_count,
            total_found=total_count, error_message=None,
        )
    except Exception as e:
        db.finish_scrape_log(
            log_id=log_id, status="error", new_listings=new_count,
            total_found=total_count, error_message=str(e),
        )
        raise
```

- [ ] **Step 5: Update server.py health check to use DB settings**

In `server.py`, in the `get_listings` function, replace the hardcoded config hour references:

Change:
```python
        local_hour = (now_utc + config.LOCAL_UTC_OFFSET).hour
        if config.SCRAPER_START_HOUR <= local_hour <= config.SCRAPER_END_HOUR:
```

To:
```python
        settings = db.get_settings()
        local_hour = (now_utc + config.LOCAL_UTC_OFFSET).hour
        if settings["scraper_start_hour"] <= local_hour <= settings["scraper_end_hour"]:
```

- [ ] **Step 6: Run all tests to verify nothing broke**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add scraper.py server.py
git commit -m "feat: wire scraper and server to use DB settings and new scrape log flow"
```

---

### Task 8: Navigation links on existing pages

**Files:**
- Modify: `dashboard.html`
- Modify: `log.html`

- [ ] **Step 1: Add Settings link to dashboard.html header**

In `dashboard.html`, find the header-right div (around line 612-614):

```html
        <div class="header-right">
            <a class="log-link" href="/log">Scrape log</a>
        </div>
```

Replace with:

```html
        <div class="header-right">
            <a class="log-link" href="/log">Scrape log</a>
            <a class="log-link" href="/settings">Settings</a>
        </div>
```

- [ ] **Step 2: Add Settings link to log.html header**

In `log.html`, find the back link (around line 163):

```html
        <a class="back-link" href="/">← Back to dashboard</a>
```

Replace with:

```html
        <div style="display: flex; gap: 16px;">
            <a class="back-link" href="/">← Dashboard</a>
            <a class="back-link" href="/settings">Settings</a>
        </div>
```

- [ ] **Step 3: Commit**

```bash
git add dashboard.html log.html
git commit -m "feat: add Settings navigation link to dashboard and log pages"
```

---

### Task 9: Settings page HTML

**Files:**
- Create: `settings.html`

- [ ] **Step 1: Create settings.html**

Create `settings.html` with the same dark theme, fonts, and CSS variables as `dashboard.html` and `log.html`. Include neighborhoods tag list, price/room/hour inputs, Save button, and Run Now button.

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Settings — Imobiliare Watcher</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Libre+Franklin:wght@300;400;500;600&family=Fraunces:ital,opsz,wght@0,9..144,400;0,9..144,600;1,9..144,400&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg: #141416;
            --bg-card: #1c1c1f;
            --text-primary: #e8e6e3;
            --text-secondary: #9a9590;
            --text-muted: #5f5b56;
            --accent: #e8793a;
            --accent-light: rgba(232, 121, 58, 0.12);
            --border: #2a2a2d;
            --border-light: #222224;
            --radius: 12px;
            --radius-sm: 8px;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            background: var(--bg);
            color: var(--text-primary);
            font-family: 'Libre Franklin', -apple-system, sans-serif;
            font-size: 15px;
            line-height: 1.5;
            -webkit-font-smoothing: antialiased;
        }

        .header {
            padding: 20px 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            position: sticky;
            top: 0;
            z-index: 100;
            background: rgba(20, 20, 22, 0.85);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-bottom: 1px solid var(--border-light);
        }

        .header h1 {
            font-family: 'Fraunces', Georgia, serif;
            font-size: 24px;
            font-weight: 400;
            font-style: italic;
            color: var(--text-primary);
            letter-spacing: -0.02em;
        }

        .nav-links { display: flex; gap: 16px; }

        .nav-link {
            color: var(--text-muted);
            font-size: 13px;
            text-decoration: none;
            font-weight: 500;
            transition: color 0.2s;
        }
        .nav-link:hover { color: var(--accent); }

        .container {
            max-width: 640px;
            margin: 0 auto;
            padding: 32px;
        }

        .section {
            background: var(--bg-card);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            padding: 24px;
            margin-bottom: 20px;
        }

        .section-title {
            font-size: 13px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: var(--text-muted);
            margin-bottom: 16px;
        }

        .tags {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-bottom: 12px;
        }

        .tag {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            background: var(--accent-light);
            color: var(--accent);
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 500;
        }

        .tag-remove {
            cursor: pointer;
            opacity: 0.6;
            font-size: 15px;
            line-height: 1;
        }
        .tag-remove:hover { opacity: 1; }

        .add-row {
            display: flex;
            gap: 8px;
        }

        input[type="text"], input[type="number"] {
            background: var(--bg);
            border: 1px solid var(--border);
            border-radius: var(--radius-sm);
            color: var(--text-primary);
            padding: 8px 12px;
            font-size: 14px;
            font-family: inherit;
            outline: none;
            transition: border-color 0.2s;
        }
        input:focus { border-color: var(--accent); }

        input[type="text"] { flex: 1; }
        input[type="number"] { width: 100px; }

        .inline-fields {
            display: flex;
            gap: 16px;
            align-items: center;
        }

        .field-label {
            font-size: 13px;
            color: var(--text-secondary);
            margin-bottom: 6px;
        }

        .field-group { display: flex; flex-direction: column; }

        .room-checks {
            display: flex;
            gap: 12px;
        }

        .room-check {
            display: flex;
            align-items: center;
            gap: 4px;
            cursor: pointer;
            font-size: 14px;
            color: var(--text-secondary);
        }

        .room-check input { accent-color: var(--accent); cursor: pointer; }

        .actions {
            display: flex;
            gap: 12px;
            align-items: center;
            margin-top: 4px;
        }

        .btn {
            padding: 10px 24px;
            border-radius: var(--radius-sm);
            border: none;
            font-family: inherit;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }

        .btn-primary {
            background: var(--accent);
            color: #fff;
        }
        .btn-primary:hover { filter: brightness(1.1); }
        .btn-primary:disabled { opacity: 0.5; cursor: default; }

        .btn-secondary {
            background: var(--bg-card);
            color: var(--text-secondary);
            border: 1px solid var(--border);
        }
        .btn-secondary:hover { color: var(--text-primary); border-color: var(--text-muted); }
        .btn-secondary:disabled { opacity: 0.5; cursor: default; }

        .status-msg {
            font-size: 13px;
            color: var(--text-muted);
            min-height: 20px;
        }
        .status-msg.ok { color: #4ade80; }
        .status-msg.err { color: #f87171; }

        .btn-add {
            padding: 8px 16px;
            border-radius: var(--radius-sm);
            border: 1px solid var(--border);
            background: var(--bg-card);
            color: var(--text-secondary);
            font-family: inherit;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
        }
        .btn-add:hover { color: var(--text-primary); border-color: var(--text-muted); }

        @media (max-width: 768px) {
            .header { padding: 16px 20px; }
            .container { padding: 16px 20px; }
            .header h1 { font-size: 20px; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>Settings</h1>
        <div class="nav-links">
            <a class="nav-link" href="/">Dashboard</a>
            <a class="nav-link" href="/log">Scrape log</a>
        </div>
    </div>

    <div class="container">
        <div class="section">
            <div class="section-title">Neighborhoods</div>
            <div class="tags" id="neighborhoodTags"></div>
            <div class="add-row">
                <input type="text" id="newNeighborhood" placeholder="Add neighborhood..." onkeydown="if(event.key==='Enter')addNeighborhood()">
                <button class="btn-add" onclick="addNeighborhood()">Add</button>
            </div>
        </div>

        <div class="section">
            <div class="section-title">Filters</div>
            <div class="inline-fields" style="margin-bottom: 16px;">
                <div class="field-group">
                    <div class="field-label">Price min (EUR)</div>
                    <input type="number" id="priceMin" min="0">
                </div>
                <span style="color: var(--text-muted); padding-top: 20px;">—</span>
                <div class="field-group">
                    <div class="field-label">Price max (EUR)</div>
                    <input type="number" id="priceMax" min="0">
                </div>
            </div>
            <div>
                <div class="field-label">Rooms</div>
                <div class="room-checks">
                    <label class="room-check"><input type="checkbox" value="1"> 1</label>
                    <label class="room-check"><input type="checkbox" value="2"> 2</label>
                    <label class="room-check"><input type="checkbox" value="3"> 3</label>
                    <label class="room-check"><input type="checkbox" value="4"> 4</label>
                    <label class="room-check"><input type="checkbox" value="5"> 5+</label>
                </div>
            </div>
        </div>

        <div class="section">
            <div class="section-title">Schedule</div>
            <div class="inline-fields">
                <div class="field-group">
                    <div class="field-label">Start hour</div>
                    <input type="number" id="startHour" min="0" max="23">
                </div>
                <span style="color: var(--text-muted); padding-top: 20px;">—</span>
                <div class="field-group">
                    <div class="field-label">End hour</div>
                    <input type="number" id="endHour" min="0" max="23">
                </div>
            </div>
        </div>

        <div class="section" style="background: transparent; border: none; padding: 0;">
            <div class="actions">
                <button class="btn btn-primary" id="saveBtn" onclick="saveSettings()">Save</button>
                <button class="btn btn-secondary" id="runBtn" onclick="runNow()">Run now</button>
                <div class="status-msg" id="statusMsg"></div>
            </div>
        </div>
    </div>

    <script>
        let neighborhoods = [];

        function renderTags() {
            const container = document.getElementById('neighborhoodTags');
            container.innerHTML = neighborhoods.map((n, i) =>
                `<span class="tag">${esc(n)}<span class="tag-remove" onclick="removeNeighborhood(${i})">&#10005;</span></span>`
            ).join('');
        }

        function addNeighborhood() {
            const input = document.getElementById('newNeighborhood');
            const val = input.value.trim().toLowerCase();
            if (val && !neighborhoods.includes(val)) {
                neighborhoods.push(val);
                renderTags();
                input.value = '';
            }
            input.focus();
        }

        function removeNeighborhood(index) {
            neighborhoods.splice(index, 1);
            renderTags();
        }

        function esc(str) {
            const div = document.createElement('div');
            div.textContent = str;
            return div.innerHTML;
        }

        function showStatus(msg, type) {
            const el = document.getElementById('statusMsg');
            el.textContent = msg;
            el.className = 'status-msg' + (type ? ' ' + type : '');
            if (type === 'ok') {
                setTimeout(() => { el.textContent = ''; el.className = 'status-msg'; }, 3000);
            }
        }

        function getFormData() {
            const rooms = [];
            document.querySelectorAll('.room-checks input:checked').forEach(cb => {
                rooms.push(parseInt(cb.value));
            });
            return {
                neighborhoods: neighborhoods,
                price_min: parseInt(document.getElementById('priceMin').value) || 0,
                price_max: parseInt(document.getElementById('priceMax').value) || 0,
                rooms: rooms,
                scraper_start_hour: parseInt(document.getElementById('startHour').value) || 0,
                scraper_end_hour: parseInt(document.getElementById('endHour').value) || 0,
            };
        }

        function populateForm(data) {
            neighborhoods = data.neighborhoods || [];
            renderTags();
            document.getElementById('priceMin').value = data.price_min;
            document.getElementById('priceMax').value = data.price_max;
            document.getElementById('startHour').value = data.scraper_start_hour;
            document.getElementById('endHour').value = data.scraper_end_hour;
            // Set room checkboxes
            document.querySelectorAll('.room-checks input').forEach(cb => {
                cb.checked = (data.rooms || []).includes(parseInt(cb.value));
            });
        }

        async function loadSettings() {
            try {
                const resp = await fetch('/api/settings');
                const data = await resp.json();
                populateForm(data);
            } catch (e) {
                showStatus('Failed to load settings', 'err');
            }
        }

        async function saveSettings() {
            const btn = document.getElementById('saveBtn');
            btn.disabled = true;
            try {
                const resp = await fetch('/api/settings', {
                    method: 'PUT',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(getFormData()),
                });
                const data = await resp.json();
                if (resp.ok) {
                    showStatus('Settings saved', 'ok');
                } else {
                    showStatus((data.errors || ['Save failed']).join(', '), 'err');
                }
            } catch (e) {
                showStatus('Save failed: ' + e.message, 'err');
            } finally {
                btn.disabled = false;
            }
        }

        async function runNow() {
            const btn = document.getElementById('runBtn');
            btn.disabled = true;
            btn.textContent = 'Running...';
            showStatus('Scrape started...', '');
            try {
                const resp = await fetch('/api/scrape', { method: 'POST' });
                const data = await resp.json();
                if (resp.status === 409) {
                    showStatus('A scrape is already running', 'err');
                    btn.disabled = false;
                    btn.textContent = 'Run now';
                    return;
                }
                // Poll for completion
                pollScrapeStatus();
            } catch (e) {
                showStatus('Failed to start scrape: ' + e.message, 'err');
                btn.disabled = false;
                btn.textContent = 'Run now';
            }
        }

        function pollScrapeStatus() {
            const interval = setInterval(async () => {
                try {
                    const resp = await fetch('/api/scrape/status');
                    const data = await resp.json();
                    if (!data.running) {
                        clearInterval(interval);
                        const btn = document.getElementById('runBtn');
                        btn.disabled = false;
                        btn.textContent = 'Run now';
                        showStatus('Scrape finished', 'ok');
                    }
                } catch (e) {
                    clearInterval(interval);
                    document.getElementById('runBtn').disabled = false;
                    document.getElementById('runBtn').textContent = 'Run now';
                }
            }, 3000);
        }

        // Load on page open
        loadSettings();
    </script>
</body>
</html>
```

- [ ] **Step 2: Manually verify in browser**

1. Run: `python3 server.py`
2. Open http://localhost:5000/settings
3. Verify: neighborhoods tags render, inputs populate with defaults, Save works, nav links work

- [ ] **Step 3: Commit**

```bash
git add settings.html
git commit -m "feat: add settings page with neighborhoods, filters, schedule, and run-now"
```

---

### Task 10: End-to-end verification and cleanup

**Files:**
- All modified files

- [ ] **Step 1: Run full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Verify settings flow end-to-end**

1. Start server: `python3 server.py`
2. Open http://localhost:5000/settings
3. Change a neighborhood (add "militari")
4. Change price range to 200-900
5. Click Save — should show "Settings saved"
6. Refresh page — new values should persist
7. Click "Run now" — should show "Running..." then poll until "Scrape finished"
8. Check http://localhost:5000/log — new scrape log entry should appear with `running` briefly then `success`
9. Navigate between pages via header links

- [ ] **Step 3: Update run_backfill to use start/finish scrape log**

The `run_backfill()` function still uses the old `db.insert_scrape_log()`. Update it to use `db.start_scrape_log()` / `db.finish_scrape_log()` for consistency, so the "running" status indicator works for backfill runs too. Follow the same pattern as `run_seed()` in Task 7 Step 4.

- [ ] **Step 4: Final commit with any fixes found during verification**

```bash
git add -A
git commit -m "fix: adjustments from end-to-end verification"
```

(Skip this commit if no fixes were needed.)

- [ ] **Step 5: Restart PM2 processes**

```bash
pm2 restart imobiliare-dashboard imobiliare-scraper
```
