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
    """get_last_scrape_time returns most recent successful scrape time."""
    db.insert_scrape_log(
        started_at="2026-04-07T14:00:00+00:00",
        finished_at="2026-04-07T14:01:00+00:00",
        mode="normal", new_listings=0, total_found=10,
        status="success", error_message=None, duration_seconds=60.0,
    )
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


def test_init_db_creates_removed_at_column():
    """init_db should create listings table with removed_at column."""
    import sqlite3
    conn = sqlite3.connect(db._get_db_path())
    cursor = conn.execute("PRAGMA table_info(listings)")
    columns = {row[1] for row in cursor.fetchall()}
    conn.close()
    assert "removed_at" in columns


def test_get_active_ids():
    """get_active_ids returns IDs of listings that are not removed."""
    db.insert_listings([_make_listing(id="a1"), _make_listing(id="a2"), _make_listing(id="a3")])
    # Manually mark a3 as removed
    conn = db._connect()
    conn.execute("UPDATE listings SET removed_at = '2026-04-08T00:00:00' WHERE id = 'a3'")
    conn.commit()
    conn.close()
    active = db.get_active_ids()
    assert active == {"a1", "a2"}


def test_mark_removed():
    """mark_removed sets removed_at for given IDs."""
    db.insert_listings([_make_listing(id="r1"), _make_listing(id="r2"), _make_listing(id="r3")])
    db.mark_removed({"r1", "r3"})
    active = db.get_listings(page=1, per_page=50, filter_type="all")
    removed = db.get_listings(page=1, per_page=50, filter_type="removed")
    active_ids = {l["id"] for l in active["listings"]}
    removed_ids = {l["id"] for l in removed["listings"]}
    assert removed_ids == {"r1", "r3"}
    assert active_ids == {"r2"}


def test_mark_removed_empty():
    """mark_removed with empty set does nothing."""
    db.insert_listings([_make_listing(id="e1")])
    db.mark_removed(set())
    result = db.get_listings(page=1, per_page=50, filter_type="all")
    assert result["listings"][0]["removed_at"] is None


def test_relist():
    """relist clears removed_at and sets is_new=1 for given IDs."""
    db.insert_listings([_make_listing(id="rl1")])
    db.mark_removed({"rl1"})
    db.relist({"rl1"})
    result = db.get_listings(page=1, per_page=50, filter_type="all")
    listing = result["listings"][0]
    assert listing["removed_at"] is None
    assert listing["is_new"] == 1


def test_relist_empty():
    """relist with empty set does nothing."""
    db.insert_listings([_make_listing(id="re1")])
    db.mark_removed({"re1"})
    db.relist(set())
    result = db.get_listings(page=1, per_page=50, filter_type="removed")
    assert result["listings"][0]["removed_at"] is not None


def test_filter_removed():
    """get_listings with filter 'removed' returns only removed listings."""
    db.insert_listings([_make_listing(id="fr1"), _make_listing(id="fr2")])
    db.mark_removed({"fr1"})
    result = db.get_listings(page=1, per_page=50, filter_type="removed")
    assert result["total"] == 1
    assert result["listings"][0]["id"] == "fr1"
    assert result["listings"][0]["removed_at"] is not None


def test_filter_all_excludes_removed():
    """get_listings with filter 'all' excludes removed listings."""
    db.insert_listings([_make_listing(id="ae1"), _make_listing(id="ae2")])
    db.mark_removed({"ae1"})
    result = db.get_listings(page=1, per_page=50, filter_type="all")
    assert result["total"] == 1
    assert result["listings"][0]["id"] == "ae2"
