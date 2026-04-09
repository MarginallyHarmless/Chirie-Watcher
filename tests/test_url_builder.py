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
