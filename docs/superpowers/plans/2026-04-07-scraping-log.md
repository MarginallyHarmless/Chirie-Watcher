# Scraping Log Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent scrape run log (new DB table, API endpoint, dashboard UI section) so every scraper run is recorded and visible on the dashboard.

**Architecture:** New `scrape_logs` SQLite table stores one row per scraper run. A new Flask endpoint serves the logs. The dashboard gets a collapsible log section toggled by a button in the controls bar. The scraper's three run functions are wrapped to record timing, counts, and errors.

**Tech Stack:** Python/Flask, SQLite, vanilla HTML/CSS/JS (matches existing stack)

---

### Task 1: Add `scrape_logs` table and DB functions

**Files:**
- Modify: `db.py:20-38` (init_db) and append new functions
- Test: `tests/test_db.py` (append new tests)

- [ ] **Step 1: Write failing tests for scrape log DB functions**

Append to `tests/test_db.py`:

```python
def test_init_db_creates_scrape_logs_table():
    """init_db should create the scrape_logs table."""
    import sqlite3
    conn = sqlite3.connect(db._get_db_path())
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scrape_logs'")
    assert cursor.fetchone() is not None
    conn.close()


def test_insert_scrape_log_success():
    """insert_scrape_log stores a success entry."""
    db.insert_scrape_log(
        started_at="2026-04-07T14:00:00+00:00",
        finished_at="2026-04-07T14:02:13+00:00",
        mode="normal",
        new_listings=5,
        total_found=48,
        status="success",
        error_message=None,
        duration_seconds=133.2,
    )
    logs = db.get_scrape_logs()
    assert len(logs) == 1
    assert logs[0]["mode"] == "normal"
    assert logs[0]["new_listings"] == 5
    assert logs[0]["total_found"] == 48
    assert logs[0]["status"] == "success"
    assert logs[0]["error_message"] is None
    assert logs[0]["duration_seconds"] == 133.2


def test_insert_scrape_log_error():
    """insert_scrape_log stores an error entry."""
    db.insert_scrape_log(
        started_at="2026-04-07T14:00:00+00:00",
        finished_at="2026-04-07T14:00:05+00:00",
        mode="normal",
        new_listings=0,
        total_found=0,
        status="error",
        error_message="TimeoutError: page load timed out",
        duration_seconds=5.0,
    )
    logs = db.get_scrape_logs()
    assert len(logs) == 1
    assert logs[0]["status"] == "error"
    assert "TimeoutError" in logs[0]["error_message"]


def test_get_scrape_logs_ordered_newest_first():
    """get_scrape_logs returns most recent first."""
    db.insert_scrape_log(
        started_at="2026-04-07T10:00:00+00:00",
        finished_at="2026-04-07T10:01:00+00:00",
        mode="normal", new_listings=1, total_found=10,
        status="success", error_message=None, duration_seconds=60.0,
    )
    db.insert_scrape_log(
        started_at="2026-04-07T12:00:00+00:00",
        finished_at="2026-04-07T12:01:00+00:00",
        mode="seed", new_listings=50, total_found=100,
        status="success", error_message=None, duration_seconds=60.0,
    )
    logs = db.get_scrape_logs()
    assert len(logs) == 2
    assert logs[0]["mode"] == "seed"  # most recent
    assert logs[1]["mode"] == "normal"


def test_scrape_logs_pruned_to_200():
    """insert_scrape_log prunes old entries beyond 200."""
    for i in range(205):
        db.insert_scrape_log(
            started_at=f"2026-04-07T{i:05d}",
            finished_at=f"2026-04-07T{i:05d}",
            mode="normal", new_listings=0, total_found=0,
            status="success", error_message=None, duration_seconds=1.0,
        )
    logs = db.get_scrape_logs()
    assert len(logs) == 200


def test_get_scrape_logs_empty():
    """get_scrape_logs returns empty list when no logs exist."""
    logs = db.get_scrape_logs()
    assert logs == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python -m pytest tests/test_db.py -v -k "scrape_log"`
Expected: FAIL — `AttributeError: module 'db' has no attribute 'insert_scrape_log'`

- [ ] **Step 3: Add scrape_logs table to init_db**

In `db.py`, inside `init_db()`, after the existing `CREATE TABLE IF NOT EXISTS listings` block (after line 36, before `conn.commit()`), add:

```python
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scrape_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at DATETIME NOT NULL,
            finished_at DATETIME,
            mode TEXT NOT NULL,
            new_listings INTEGER DEFAULT 0,
            total_found INTEGER DEFAULT 0,
            status TEXT NOT NULL,
            error_message TEXT,
            duration_seconds REAL
        )
    """)
```

- [ ] **Step 4: Add insert_scrape_log function**

Append to `db.py`:

```python
def insert_scrape_log(started_at, finished_at, mode, new_listings, total_found,
                      status, error_message, duration_seconds):
    conn = _connect()
    conn.execute(
        """INSERT INTO scrape_logs
           (started_at, finished_at, mode, new_listings, total_found, status, error_message, duration_seconds)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (started_at, finished_at, mode, new_listings, total_found, status, error_message, duration_seconds),
    )
    # Prune to keep only the most recent 200 entries
    conn.execute("""
        DELETE FROM scrape_logs WHERE id NOT IN (
            SELECT id FROM scrape_logs ORDER BY started_at DESC LIMIT 200
        )
    """)
    conn.commit()
    conn.close()
```

- [ ] **Step 5: Add get_scrape_logs function**

Append to `db.py`:

```python
def get_scrape_logs():
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM scrape_logs ORDER BY started_at DESC LIMIT 200"
    ).fetchall()
    logs = [dict(row) for row in rows]
    conn.close()
    return logs
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python -m pytest tests/test_db.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
cd "/Users/bmacmini/Documents/vibes/Imobiliare bot"
git add db.py tests/test_db.py
git commit -m "feat: add scrape_logs table and DB functions"
```

---

### Task 2: Add `/api/scrape-logs` endpoint

**Files:**
- Modify: `server.py` (add new route)
- Test: `tests/test_server.py` (append new tests)

- [ ] **Step 1: Write failing tests for the scrape-logs endpoint**

Append to `tests/test_server.py`:

```python
def test_get_scrape_logs_empty(client):
    """GET /api/scrape-logs with no logs returns empty list."""
    resp = client.get("/api/scrape-logs")
    data = resp.get_json()
    assert resp.status_code == 200
    assert data["logs"] == []


def test_get_scrape_logs_returns_data(client):
    """GET /api/scrape-logs returns stored log entries."""
    db.insert_scrape_log(
        started_at="2026-04-07T14:00:00+00:00",
        finished_at="2026-04-07T14:02:13+00:00",
        mode="normal",
        new_listings=5,
        total_found=48,
        status="success",
        error_message=None,
        duration_seconds=133.2,
    )
    resp = client.get("/api/scrape-logs")
    data = resp.get_json()
    assert len(data["logs"]) == 1
    assert data["logs"][0]["mode"] == "normal"
    assert data["logs"][0]["new_listings"] == 5
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python -m pytest tests/test_server.py -v -k "scrape_log"`
Expected: FAIL — 404 Not Found

- [ ] **Step 3: Add the endpoint to server.py**

In `server.py`, add this route before the `if __name__` block:

```python
@app.route("/api/scrape-logs")
def get_scrape_logs():
    logs = db.get_scrape_logs()
    return jsonify({"logs": logs})
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python -m pytest tests/test_server.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
cd "/Users/bmacmini/Documents/vibes/Imobiliare bot"
git add server.py tests/test_server.py
git commit -m "feat: add GET /api/scrape-logs endpoint"
```

---

### Task 3: Wrap scraper run functions to record log entries

**Files:**
- Modify: `scraper.py:319-404` (wrap run_normal, run_seed, run_backfill)

- [ ] **Step 1: Modify run_normal to return counts and record log**

Replace `run_normal()` in `scraper.py` (lines 319-354) with:

```python
def run_normal():
    """Normal mode: scrape search results, fetch photos for new listings only."""
    db.init_db()
    started_at = datetime.now(timezone.utc)
    new_count = 0
    total_count = 0
    try:
        with sync_playwright() as pw:
            browser, page = _launch_browser(pw)
            try:
                all_listings = scrape_search_results(page, config.MAX_PAGES)
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
                        new_count = len(new_listings)
                        log.info(f"Scraper complete: {new_count} new listings added")
                    else:
                        log.info("Scraper complete: no new listings")
            finally:
                browser.close()

        finished_at = datetime.now(timezone.utc)
        db.insert_scrape_log(
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            mode="normal",
            new_listings=new_count,
            total_found=total_count,
            status="success",
            error_message=None,
            duration_seconds=(finished_at - started_at).total_seconds(),
        )
    except Exception as e:
        finished_at = datetime.now(timezone.utc)
        db.insert_scrape_log(
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            mode="normal",
            new_listings=new_count,
            total_found=total_count,
            status="error",
            error_message=str(e),
            duration_seconds=(finished_at - started_at).total_seconds(),
        )
        raise
```

- [ ] **Step 2: Add datetime imports to scraper.py**

At the top of `scraper.py`, add to the existing imports:

```python
from datetime import datetime, timezone
```

- [ ] **Step 3: Modify run_seed to return counts and record log**

Replace `run_seed()` in `scraper.py` (lines 357-379) with:

```python
def run_seed():
    """Seed mode: scrape all pages, no photo fetching."""
    db.init_db()
    started_at = datetime.now(timezone.utc)
    new_count = 0
    total_count = 0
    try:
        with sync_playwright() as pw:
            browser, page = _launch_browser(pw)
            try:
                all_listings = scrape_search_results(page, config.SEED_MAX_PAGES)
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

        finished_at = datetime.now(timezone.utc)
        db.insert_scrape_log(
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            mode="seed",
            new_listings=new_count,
            total_found=total_count,
            status="success",
            error_message=None,
            duration_seconds=(finished_at - started_at).total_seconds(),
        )
    except Exception as e:
        finished_at = datetime.now(timezone.utc)
        db.insert_scrape_log(
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            mode="seed",
            new_listings=new_count,
            total_found=total_count,
            status="error",
            error_message=str(e),
            duration_seconds=(finished_at - started_at).total_seconds(),
        )
        raise
```

- [ ] **Step 4: Modify run_backfill to record log**

Replace `run_backfill()` in `scraper.py` (lines 382-404) with:

```python
def run_backfill():
    """Backfill mode: fetch photos for listings that have none."""
    db.init_db()
    started_at = datetime.now(timezone.utc)
    total_count = 0
    try:
        listings = db.get_listings_without_photos(limit=config.BACKFILL_BATCH_SIZE)
        total_count = len(listings)
        if not listings:
            log.info("Backfill: no listings need photos")
        else:
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

        finished_at = datetime.now(timezone.utc)
        db.insert_scrape_log(
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            mode="backfill",
            new_listings=0,
            total_found=total_count,
            status="success",
            error_message=None,
            duration_seconds=(finished_at - started_at).total_seconds(),
        )
    except Exception as e:
        finished_at = datetime.now(timezone.utc)
        db.insert_scrape_log(
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            mode="backfill",
            new_listings=0,
            total_found=total_count,
            status="error",
            error_message=str(e),
            duration_seconds=(finished_at - started_at).total_seconds(),
        )
        raise
```

- [ ] **Step 5: Commit**

```bash
cd "/Users/bmacmini/Documents/vibes/Imobiliare bot"
git add scraper.py
git commit -m "feat: wrap scraper run functions to record log entries"
```

---

### Task 4: Add scrape log section to dashboard

**Files:**
- Modify: `dashboard.html` (add CSS, HTML section, and JS)

- [ ] **Step 1: Add CSS for the scrape log section**

In `dashboard.html`, add the following styles before the `.empty-state` rule (before line 276):

```css
        .log-toggle-btn {
            background: #1a1a1a;
            color: #c0c0c0;
            border: 1px solid #333;
            padding: 6px 12px;
            font-family: inherit;
            font-size: 12px;
            cursor: pointer;
            border-radius: 4px;
        }

        .log-toggle-btn:hover {
            border-color: #00ff41;
            color: #00ff41;
        }

        .scrape-log {
            display: none;
            padding: 0 24px 16px;
            max-height: 350px;
            overflow-y: auto;
            scrollbar-width: thin;
            scrollbar-color: #333 transparent;
        }

        .scrape-log.visible {
            display: block;
        }

        .scrape-log table {
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }

        .scrape-log th {
            text-align: left;
            color: #555;
            font-weight: 400;
            padding: 6px 12px 6px 0;
            border-bottom: 1px solid #222;
        }

        .scrape-log td {
            padding: 6px 12px 6px 0;
            border-bottom: 1px solid #1a1a1a;
        }

        .scrape-log tr.error-row {
            border-left: 3px solid #ff4141;
        }

        .scrape-log tr.error-row td {
            color: #ff4141;
        }

        .scrape-log .error-msg {
            color: #ff4141;
            font-size: 11px;
            padding: 2px 0 6px 0;
        }

        .log-badge {
            display: inline-block;
            padding: 1px 6px;
            border-radius: 3px;
            font-size: 11px;
        }

        .log-badge.ok {
            background: #002200;
            color: #00ff41;
        }

        .log-badge.err {
            background: #220000;
            color: #ff4141;
        }
```

- [ ] **Step 2: Add the toggle button to the controls bar**

In `dashboard.html`, find the line with `<span class="total-count" id="totalCount"></span>` (in the controls div) and add the toggle button right before it:

```html
        <button class="log-toggle-btn" id="logToggleBtn" onclick="toggleLog()">Scrape log</button>
```

- [ ] **Step 3: Add the scrape log HTML section**

In `dashboard.html`, between the closing `</div>` of the controls div and `<div class="listings" id="listings">`, add:

```html
    <div class="scrape-log" id="scrapeLog"></div>
```

- [ ] **Step 4: Add the JavaScript for fetching and rendering the log**

In `dashboard.html`, add the following functions inside the `<script>` tag, after the `esc()` function and before the `// Initial load` comment:

```javascript
        let logVisible = false;

        function toggleLog() {
            logVisible = !logVisible;
            const el = document.getElementById('scrapeLog');
            const btn = document.getElementById('logToggleBtn');
            el.classList.toggle('visible', logVisible);
            btn.textContent = logVisible ? 'Hide log' : 'Scrape log';
            if (logVisible) fetchScrapeLogs();
        }

        async function fetchScrapeLogs() {
            try {
                const resp = await fetch('/api/scrape-logs');
                const data = await resp.json();
                renderScrapeLogs(data.logs);
            } catch (e) {
                console.error('Failed to fetch scrape logs:', e);
            }
        }

        function formatDuration(seconds) {
            if (seconds == null) return '--';
            const m = Math.floor(seconds / 60);
            const s = Math.round(seconds % 60);
            return m > 0 ? `${m}m ${s}s` : `${s}s`;
        }

        function renderScrapeLogs(logs) {
            const container = document.getElementById('scrapeLog');
            if (!logs.length) {
                container.innerHTML = '<div class="empty-state" style="padding:24px">No scrape logs yet</div>';
                return;
            }
            container.innerHTML = `
                <table>
                    <thead>
                        <tr>
                            <th>Time</th>
                            <th>Mode</th>
                            <th>Result</th>
                            <th>Duration</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${logs.map(log => `
                            <tr class="${log.status === 'error' ? 'error-row' : ''}">
                                <td>${new Date(log.started_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</td>
                                <td>${esc(log.mode)}</td>
                                <td>${log.new_listings} new / ${log.total_found} total</td>
                                <td>${formatDuration(log.duration_seconds)}</td>
                                <td>${log.status === 'success'
                                    ? '<span class="log-badge ok">OK</span>'
                                    : '<span class="log-badge err">ERROR</span>'}</td>
                            </tr>
                            ${log.error_message ? `
                            <tr class="error-row">
                                <td colspan="5" class="error-msg">${esc(log.error_message)}</td>
                            </tr>` : ''}
                        `).join('')}
                    </tbody>
                </table>
            `;
        }
```

- [ ] **Step 5: Refresh the log on auto-refresh when visible**

In `dashboard.html`, inside the `fetchListings()` function, after the existing `updatePagination(data);` line, add:

```javascript
                if (logVisible) fetchScrapeLogs();
```

- [ ] **Step 6: Manually verify the dashboard**

Run the server: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python server.py`
Open `http://127.0.0.1:5000` in a browser. Verify:
1. "Scrape log" button is visible in the controls bar
2. Clicking it shows the log section (empty state: "No scrape logs yet")
3. Clicking again hides it, button text toggles

- [ ] **Step 7: Commit**

```bash
cd "/Users/bmacmini/Documents/vibes/Imobiliare bot"
git add dashboard.html
git commit -m "feat: add scrape log section to dashboard"
```

---

### Task 5: Run full test suite and verify

**Files:**
- All modified files

- [ ] **Step 1: Run the full test suite**

Run: `cd "/Users/bmacmini/Documents/vibes/Imobiliare bot" && python -m pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 2: Fix any failures and re-run**

If any tests fail, fix the issue and re-run until all pass.

- [ ] **Step 3: Final commit if any fixes were needed**

```bash
cd "/Users/bmacmini/Documents/vibes/Imobiliare bot"
git add -A
git commit -m "fix: address test failures from scraping log feature"
```
