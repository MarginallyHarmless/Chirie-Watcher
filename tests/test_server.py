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


def test_get_listings_filter_removed(client):
    """GET /api/listings?filter=removed returns only removed listings."""
    db.insert_listings([_make_listing(id="rm1"), _make_listing(id="rm2")])
    db.mark_removed({"rm1"})
    resp = client.get("/api/listings?filter=removed")
    data = resp.get_json()
    assert data["total"] == 1
    assert data["listings"][0]["id"] == "rm1"
    assert data["listings"][0]["removed_at"] is not None


def test_get_listings_all_excludes_removed(client):
    """GET /api/listings?filter=all excludes removed listings."""
    db.insert_listings([_make_listing(id="ax1"), _make_listing(id="ax2")])
    db.mark_removed({"ax1"})
    resp = client.get("/api/listings?filter=all")
    data = resp.get_json()
    assert data["total"] == 1
    assert data["listings"][0]["id"] == "ax2"


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
