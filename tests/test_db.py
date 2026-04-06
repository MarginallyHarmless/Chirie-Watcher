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
