import json
import pytest


def test_extract_listing_id():
    """extract_listing_id pulls numeric ID from DOM id attribute."""
    from scraper import extract_listing_id
    assert extract_listing_id("listing-link-275384395") == "275384395"
    assert extract_listing_id("listing-link-12345") == "12345"
    assert extract_listing_id("") is None
    assert extract_listing_id(None) is None


def test_extract_photos_from_json():
    """extract_photos_from_json finds CDN image URLs in script content."""
    from scraper import extract_photos_from_json
    script_content = '''
    {"images": [
        {"url": "https://cdn.imobiliare.ro/foto/1.jpg"},
        {"url": "https://cdn.imobiliare.ro/foto/2.jpg"},
        {"url": "https://cdn.imobiliare.ro/foto/3.jpg"}
    ]}
    '''
    urls = extract_photos_from_json(script_content, max_photos=10)
    assert len(urls) == 3
    assert all("cdn.imobiliare.ro" in u for u in urls)


def test_extract_photos_from_json_caps_at_max():
    """extract_photos_from_json respects max_photos limit."""
    from scraper import extract_photos_from_json
    script_content = json.dumps({
        "images": [{"url": f"https://cdn.imobiliare.ro/foto/{i}.jpg"} for i in range(20)]
    })
    urls = extract_photos_from_json(script_content, max_photos=10)
    assert len(urls) == 10


def test_extract_photos_from_json_deduplicates():
    """extract_photos_from_json removes duplicate URLs."""
    from scraper import extract_photos_from_json
    script_content = '''
    {"images": [
        {"url": "https://cdn.imobiliare.ro/foto/1.jpg"},
        {"url": "https://cdn.imobiliare.ro/foto/1.jpg"},
        {"url": "https://cdn.imobiliare.ro/foto/2.jpg"}
    ]}
    '''
    urls = extract_photos_from_json(script_content, max_photos=10)
    assert len(urls) == 2


def test_extract_photos_from_json_no_match():
    """extract_photos_from_json returns empty list when no CDN URLs found."""
    from scraper import extract_photos_from_json
    assert extract_photos_from_json("no images here", max_photos=10) == []
    assert extract_photos_from_json("", max_photos=10) == []


def test_build_full_url():
    """build_full_url prepends base domain to relative paths."""
    from scraper import build_full_url
    assert build_full_url("/ro/inchiriere/123") == "https://www.imobiliare.ro/ro/inchiriere/123"
    assert build_full_url("https://www.imobiliare.ro/ro/123") == "https://www.imobiliare.ro/ro/123"
