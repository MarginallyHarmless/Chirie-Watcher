import os
import json
import tempfile
import pytest
from unittest.mock import patch

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
