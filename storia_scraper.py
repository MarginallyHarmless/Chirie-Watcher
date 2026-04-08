import json
import logging
import random
import re
import time

import config

log = logging.getLogger("storia_scraper")

STORIA_BASE_URL = "https://www.storia.ro"


def extract_storia_listing_id(url):
    """Extract listing ID from storia.ro URL.

    Storia URLs end with -ID{publicId}, e.g.:
    /ro/oferta/apartament-modern-IDGGhy -> IDGGhy
    """
    if not url:
        return None
    match = re.search(r'-(ID[A-Za-z0-9]+)(?:\?|$)', url)
    return match.group(1) if match else None


def build_storia_url(path):
    """Prepend base URL to relative paths."""
    if path.startswith("http"):
        return path
    return STORIA_BASE_URL + path


def _parse_next_data(page):
    """Extract __NEXT_DATA__ JSON from the page."""
    try:
        script = page.query_selector("script#__NEXT_DATA__")
        if not script:
            return None
        text = script.inner_text()
        return json.loads(text)
    except Exception as e:
        log.warning(f"Failed to parse __NEXT_DATA__: {e}")
        return None


def _extract_listings_from_json(data):
    """Extract listing dicts from parsed __NEXT_DATA__.

    Returns list of listing dicts in our standard format.
    """
    listings = []
    try:
        items = data["props"]["pageProps"]["data"]["searchAds"]["items"]
    except (KeyError, TypeError):
        return listings

    for item in items:
        try:
            listing_id = str(item.get("id", ""))
            if not listing_id:
                continue

            title = item.get("title", "")
            slug = item.get("slug", "")
            href = item.get("href", f"/ro/oferta/{slug}")
            url = build_storia_url(href)

            # Price
            price = ""
            total_price = item.get("totalPrice") or item.get("rentPrice")
            if total_price and total_price.get("value"):
                price = f"{total_price['value']} {total_price.get('currency', 'EUR')}"

            # Location — extract from reverseGeocoding
            location = ""
            loc_data = item.get("location", {})
            geo = loc_data.get("reverseGeocoding", {})
            locations = geo.get("locations", [])
            # Build location string from most specific to least
            loc_parts = [l.get("name", "") for l in locations if l.get("name")]
            location = ", ".join(loc_parts) if loc_parts else ""

            # Details
            detail_parts = []
            rooms = item.get("roomsNumber", "")
            if rooms:
                room_map = {"ONE": "1", "TWO": "2", "THREE": "3", "FOUR": "4", "FIVE_OR_MORE": "5+"}
                detail_parts.append(f"{room_map.get(rooms, rooms)} camere")
            area = item.get("areaInSquareMeters")
            if area:
                detail_parts.append(f"{area} mp")
            floor = item.get("floorNumber")
            if floor is not None:
                detail_parts.append(f"etaj {floor}")
            details = " | ".join(detail_parts)

            # Photos from search results (medium size)
            photo_urls = []
            for img in item.get("images", []):
                large_url = img.get("large") or img.get("medium") or ""
                if large_url:
                    photo_urls.append(large_url)

            listings.append({
                "id": listing_id,
                "title": title,
                "url": url,
                "price": price,
                "location": location,
                "details": details,
                "photo_urls": photo_urls,
            })
        except Exception as e:
            log.warning(f"Failed to extract storia listing: {e}")
            continue

    return listings


def _get_total_pages(data):
    """Extract total page count from __NEXT_DATA__."""
    try:
        return data["props"]["pageProps"]["tracking"]["listing"]["page_count"]
    except (KeyError, TypeError):
        return 1


def _matches_neighborhood(listing):
    """Check if a listing's location matches any configured neighborhood."""
    neighborhoods = getattr(config, "STORIA_NEIGHBORHOODS", [])
    if not neighborhoods:
        return True
    location_lower = listing.get("location", "").lower()
    return any(n in location_lower for n in neighborhoods)


def scrape_storia_search_results(page, max_pages):
    """Scrape storia.ro search results using __NEXT_DATA__ JSON.

    Uses a single city-level URL (neighborhood filtering doesn't work on storia.ro).
    Paginates with &page=N. Filters results by configured neighborhoods.
    """
    all_listings = []
    seen_ids = set()

    for search_url in config.STORIA_SEARCH_URLS:
        log.info(f"Scraping storia: {search_url[:80]}...")
        page_num = 0
        total_pages = None

        while page_num < max_pages:
            page_num += 1
            current_url = search_url if page_num == 1 else f"{search_url}&page={page_num}"

            try:
                page.goto(current_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_selector("script#__NEXT_DATA__", timeout=15000)
            except Exception as e:
                if page_num == 1:
                    log.warning(f"Could not load storia page: {e}. Skipping.")
                break

            data = _parse_next_data(page)
            if not data:
                log.warning(f"No __NEXT_DATA__ on storia page {page_num}")
                break

            if total_pages is None:
                total_pages = _get_total_pages(data)
                log.info(f"  Storia: {total_pages} total pages")

            listings = _extract_listings_from_json(data)
            # Filter by neighborhood
            listings = [l for l in listings if _matches_neighborhood(l)]
            new_listings = [l for l in listings if l["id"] not in seen_ids]
            for l in new_listings:
                seen_ids.add(l["id"])
            all_listings.extend(new_listings)
            log.info(f"  Storia page {page_num}: {len(listings)} in neighborhoods, {len(new_listings)} new")

            if len(new_listings) == 0:
                break

            if total_pages and page_num >= total_pages:
                break

            if page_num < max_pages:
                time.sleep(random.uniform(*config.PAGINATION_DELAY))

        time.sleep(random.uniform(*config.PAGINATION_DELAY))

    return all_listings


def fetch_storia_photos(page, url, max_photos):
    """Visit a storia detail page and extract full-size photo URLs.

    Usually not needed since search results include photos,
    but available for backfill or higher-res images.
    """
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        data = _parse_next_data(page)
        if not data:
            return []

        ad = data.get("props", {}).get("pageProps", {}).get("ad", {})
        photos = []
        for img in ad.get("images", []):
            large_url = img.get("large") or img.get("medium") or ""
            if large_url:
                photos.append(large_url)
                if len(photos) >= max_photos:
                    break
        return photos
    except Exception as e:
        log.warning(f"Failed to fetch storia photos from {url}: {e}")
        return []
