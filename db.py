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
