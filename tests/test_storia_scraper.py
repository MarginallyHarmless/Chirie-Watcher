import json
import pytest


def test_extract_storia_listing_id():
    """extract_storia_listing_id pulls ID from storia URL."""
    from storia_scraper import extract_storia_listing_id
    assert extract_storia_listing_id("https://www.storia.ro/ro/oferta/apartament-modern-IDGGhy") == "IDGGhy"
    assert extract_storia_listing_id("/ro/oferta/test-apt-IDabc123") == "IDabc123"
    assert extract_storia_listing_id("") is None
    assert extract_storia_listing_id(None) is None


def test_extract_storia_listing_id_no_match():
    """extract_storia_listing_id returns None for URLs without ID pattern."""
    from storia_scraper import extract_storia_listing_id
    assert extract_storia_listing_id("https://www.storia.ro/ro/rezultate/inchiriere") is None


def test_build_storia_url():
    """build_storia_url prepends base domain to relative paths."""
    from storia_scraper import build_storia_url
    assert build_storia_url("/ro/oferta/test-123") == "https://www.storia.ro/ro/oferta/test-123"
    assert build_storia_url("https://www.storia.ro/ro/oferta/test-123") == "https://www.storia.ro/ro/oferta/test-123"


def test_extract_listings_from_json():
    """_extract_listings_from_json parses __NEXT_DATA__ structure."""
    from storia_scraper import _extract_listings_from_json
    data = {
        "props": {
            "pageProps": {
                "data": {
                    "searchAds": {
                        "items": [
                            {
                                "id": 12345,
                                "title": "Nice apartment",
                                "slug": "nice-apartment-IDabc",
                                "href": "/ro/oferta/nice-apartment-IDabc",
                                "totalPrice": {"value": 500, "currency": "EUR"},
                                "roomsNumber": "TWO",
                                "areaInSquareMeters": 55,
                                "floorNumber": 3,
                                "location": {
                                    "reverseGeocoding": {
                                        "locations": [
                                            {"name": "Decebal"},
                                            {"name": "Sectorul 3"},
                                            {"name": "Bucuresti"},
                                        ]
                                    }
                                },
                                "images": [
                                    {"medium": "https://cdn/photo1_med.jpg", "large": "https://cdn/photo1_lg.jpg"},
                                    {"medium": "https://cdn/photo2_med.jpg", "large": "https://cdn/photo2_lg.jpg"},
                                ],
                            }
                        ]
                    }
                }
            }
        }
    }
    listings = _extract_listings_from_json(data)
    assert len(listings) == 1
    l = listings[0]
    assert l["id"] == "12345"
    assert l["title"] == "Nice apartment"
    assert l["url"] == "https://www.storia.ro/ro/oferta/nice-apartment-IDabc"
    assert l["price"] == "500 EUR"
    assert "Decebal" in l["location"]
    assert "2 camere" in l["details"]
    assert "55 mp" in l["details"]
    assert "etaj 3" in l["details"]
    assert len(l["photo_urls"]) == 2
    assert l["photo_urls"][0] == "https://cdn/photo1_lg.jpg"


def test_extract_listings_from_json_empty():
    """_extract_listings_from_json handles missing data gracefully."""
    from storia_scraper import _extract_listings_from_json
    assert _extract_listings_from_json({}) == []
    assert _extract_listings_from_json({"props": {}}) == []


def test_get_total_pages():
    """_get_total_pages extracts page count from tracking data."""
    from storia_scraper import _get_total_pages
    data = {
        "props": {
            "pageProps": {
                "tracking": {
                    "listing": {
                        "page_count": 42
                    }
                }
            }
        }
    }
    assert _get_total_pages(data) == 42


def test_get_total_pages_missing():
    """_get_total_pages returns 1 when data is missing."""
    from storia_scraper import _get_total_pages
    assert _get_total_pages({}) == 1


def test_matches_neighborhood_hit():
    """_matches_neighborhood returns True when location contains a configured neighborhood."""
    from storia_scraper import _matches_neighborhood
    assert _matches_neighborhood({"location": "Decebal, Sectorul 3, Bucuresti"}) is True
    assert _matches_neighborhood({"location": "Alba Iulia, Sectorul 2"}) is True
    assert _matches_neighborhood({"location": "Calea Calarasilor, Sectorul 3"}) is True


def test_matches_neighborhood_via_title():
    """_matches_neighborhood matches against title text."""
    from storia_scraper import _matches_neighborhood
    assert _matches_neighborhood({
        "location": "Bucuresti, Sectorul 3, Centrul Civic",
        "title": "2 Camere | Splaiul Unirii | Decomandat",
    }) is True


def test_matches_neighborhood_via_description():
    """_matches_neighborhood matches against short_description text."""
    from storia_scraper import _matches_neighborhood
    assert _matches_neighborhood({
        "location": "Bucuresti, Sectorul 4, Vacaresti",
        "title": "Apartament modern 2 camere",
        "short_description": "Situat langa Piata Alba Iulia, zona linistita",
    }) is True


def test_matches_neighborhood_miss():
    """_matches_neighborhood returns False when no field matches."""
    from storia_scraper import _matches_neighborhood
    assert _matches_neighborhood({
        "location": "Militari, Sectorul 6, Bucuresti",
        "title": "Apartament 2 camere Militari",
        "short_description": "Bloc nou in Militari Residence",
    }) is False
    assert _matches_neighborhood({"location": "Drumul Taberei"}) is False


def test_matches_neighborhood_empty_location():
    """_matches_neighborhood returns False for empty fields."""
    from storia_scraper import _matches_neighborhood
    assert _matches_neighborhood({"location": ""}) is False
    assert _matches_neighborhood({"location": "", "title": "", "short_description": ""}) is False
