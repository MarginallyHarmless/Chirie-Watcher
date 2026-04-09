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
            is_new INTEGER DEFAULT 1,
            removed_at DATETIME DEFAULT NULL,
            source TEXT DEFAULT 'imobiliare',
            possible_duplicate_of TEXT DEFAULT NULL
        )
    """)
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
    # Migrate: add removed_at if missing (existing DBs)
    try:
        conn.execute("ALTER TABLE listings ADD COLUMN removed_at DATETIME DEFAULT NULL")
    except sqlite3.OperationalError:
        pass  # column already exists
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
    # Migrate: add per-source counts to scrape_logs if missing
    for col in ("new_imobiliare", "new_storia"):
        try:
            conn.execute(f"ALTER TABLE scrape_logs ADD COLUMN {col} INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
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


def get_listings(page=1, per_page=50, filter_type="all", sort="newest"):
    conn = _connect()
    if filter_type == "new":
        where = "WHERE is_new = 1 AND removed_at IS NULL"
    elif filter_type == "removed":
        where = "WHERE removed_at IS NOT NULL"
    elif filter_type == "all":
        where = "WHERE removed_at IS NULL"
    else:
        where = "WHERE removed_at IS NULL"

    count_row = conn.execute(f"SELECT COUNT(*) as cnt FROM listings {where}").fetchone()
    total = count_row["cnt"]

    order_clauses = {
        "newest": "first_seen DESC",
        "oldest": "first_seen ASC",
        "price_high": "CAST(REPLACE(REPLACE(REPLACE(price, ' EUR', ''), ' RON', ''), '.', '') AS INTEGER) DESC",
        "price_low": "CAST(REPLACE(REPLACE(REPLACE(price, ' EUR', ''), ' RON', ''), '.', '') AS INTEGER) ASC",
    }
    order = order_clauses.get(sort, "first_seen DESC")

    offset = (page - 1) * per_page
    rows = conn.execute(
        f"SELECT * FROM listings {where} ORDER BY {order} LIMIT ? OFFSET ?",
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
        "SELECT MAX(finished_at) as last FROM scrape_logs WHERE status = 'success'"
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


def insert_scrape_log(started_at, finished_at, mode, new_listings, total_found,
                      status, error_message, duration_seconds,
                      new_imobiliare=0, new_storia=0):
    conn = _connect()
    conn.execute(
        """INSERT INTO scrape_logs
           (started_at, finished_at, mode, new_listings, total_found, status, error_message, duration_seconds,
            new_imobiliare, new_storia)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (started_at, finished_at, mode, new_listings, total_found, status, error_message, duration_seconds,
         new_imobiliare, new_storia),
    )
    # Prune to keep only the most recent 200 entries
    conn.execute("""
        DELETE FROM scrape_logs WHERE id NOT IN (
            SELECT id FROM scrape_logs ORDER BY started_at DESC LIMIT 200
        )
    """)
    conn.commit()
    conn.close()


def get_scrape_logs():
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM scrape_logs ORDER BY started_at DESC LIMIT 200"
    ).fetchall()
    logs = [dict(row) for row in rows]
    conn.close()
    return logs


def get_active_ids():
    """Return set of IDs for all non-removed listings."""
    conn = _connect()
    cursor = conn.execute("SELECT id FROM listings WHERE removed_at IS NULL")
    result = {row["id"] for row in cursor.fetchall()}
    conn.close()
    return result


def get_removed_ids():
    """Return set of IDs for all removed listings."""
    conn = _connect()
    cursor = conn.execute("SELECT id FROM listings WHERE removed_at IS NOT NULL")
    result = {row["id"] for row in cursor.fetchall()}
    conn.close()
    return result


def mark_removed(ids):
    """Set removed_at = now for the given listing IDs."""
    if not ids:
        return
    conn = _connect()
    now = datetime.now(timezone.utc).isoformat()
    placeholders = ",".join("?" for _ in ids)
    conn.execute(
        f"UPDATE listings SET removed_at = ? WHERE id IN ({placeholders})",
        [now] + list(ids),
    )
    conn.commit()
    conn.close()


def relist(ids):
    """Clear removed_at and mark as new for relisted listings."""
    if not ids:
        return
    conn = _connect()
    placeholders = ",".join("?" for _ in ids)
    conn.execute(
        f"UPDATE listings SET removed_at = NULL, is_new = 1 WHERE id IN ({placeholders})",
        list(ids),
    )
    conn.commit()
    conn.close()


def find_possible_duplicate(price, details, location, exclude_source):
    """Find a listing from another source with matching price and overlapping location.

    Returns the ID of the first match, or None.
    """
    if not price or not location:
        return None
    conn = _connect()
    rows = conn.execute(
        "SELECT id, location FROM listings WHERE source != ? AND price = ? AND removed_at IS NULL",
        (exclude_source, price),
    ).fetchall()
    conn.close()

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
