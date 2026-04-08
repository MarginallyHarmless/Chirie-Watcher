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
            removed_at DATETIME DEFAULT NULL
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
