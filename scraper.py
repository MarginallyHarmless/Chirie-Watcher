import argparse
import json
import logging
import random
import re
import sys
import time
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright
from playwright_stealth import stealth_sync

import config
import db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("scraper")

BASE_URL = "https://www.imobiliare.ro"
LISTING_SELECTOR = 'a[data-cy="listing-information-link"]'


# --- Pure helper functions (testable without browser) ---

def extract_listing_id(dom_id):
    """Extract numeric listing ID from DOM id like 'listing-link-275384395'."""
    if not dom_id:
        return None
    match = re.search(r"(\d+)$", dom_id)
    return match.group(1) if match else None


def extract_photos_from_json(text, max_photos=10):
    """Find listing photo URLs in page text.

    Listing photos are hosted on i.roamcdn.net (the CDN).
    Filters out thumbnails (listing-thumb) and keeps full-size images.
    Deduplicates and caps at max_photos.
    """
    if not text:
        return []
    pattern = r'https?://i\.roamcdn\.net/[^"\'\s]*?\.(?:jpg|jpeg|png|webp)'
    urls = re.findall(pattern, text, re.IGNORECASE)
    # Deduplicate while preserving order, skip small thumbnails
    seen = set()
    unique = []
    for url in urls:
        # Normalize: skip if we already have this image in a different size
        # The URL path contains the image hash which is the same across sizes
        if url not in seen and "listing-thumb" not in url:
            seen.add(url)
            unique.append(url)
    return unique[:max_photos]


def build_full_url(path):
    """Prepend base URL to relative paths."""
    if path.startswith("http"):
        return path
    return BASE_URL + path



# --- Browser-dependent functions ---

def _random_delay(delay_range):
    time.sleep(random.uniform(*delay_range))


def _launch_browser(pw):
    browser = pw.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    )
    page = context.new_page()
    stealth_sync(page)
    return browser, page


def _load_search_page(page, url, retry=True):
    """Load a search page, retry once on failure."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_selector(LISTING_SELECTOR, timeout=15000)
        return True
    except Exception as e:
        if retry:
            log.warning(f"Page load failed: {e}. Retrying in 30s...")
            time.sleep(30)
            return _load_search_page(page, url, retry=False)
        log.error(f"Page load failed after retry: {e}")
        return False


def _extract_listings_from_page(page):
    """Extract listing data from the current search results page.

    imobiliare.ro card structure:
      div.listing-card
        a[data-cy="listing-information-link"]  ← invisible overlay (ID + href)
        div[data-bi]                           ← inner div with all data in attributes:
          data-name, data-bi-listing-price, data-bi-listing-currency,
          data-area, data-location-id
        h3 (optional)                          ← title text (only on some cards)

    Primary extraction uses data-bi attributes (reliable, always present).
    Falls back to h3/text parsing if data-bi is missing.
    """
    listings = []
    card_divs = page.query_selector_all("div.listing-card")
    for card_div in card_divs:
        # Get the anchor for ID and URL
        anchor = card_div.query_selector(LISTING_SELECTOR)
        if not anchor:
            continue

        dom_id = anchor.get_attribute("id")
        listing_id = extract_listing_id(dom_id)
        if not listing_id:
            continue

        href = anchor.get_attribute("href") or ""
        url = build_full_url(href)

        title = ""
        price = ""
        location = ""
        details = ""

        # Primary: extract from data-bi attributes (most reliable)
        data_div = card_div.query_selector("[data-bi]")
        if data_div:
            try:
                attrs = data_div.evaluate("""el => ({
                    name: el.getAttribute('data-name') || '',
                    price: el.getAttribute('data-bi-listing-price') || '',
                    currency: el.getAttribute('data-bi-listing-currency') || '',
                    area: el.getAttribute('data-area') || '',
                    location: el.getAttribute('data-location-id') || '',
                })""")
                title = attrs["name"]
                if attrs["price"]:
                    price = f"{attrs['price']} {attrs['currency']} / lună"
                location = attrs["location"].replace("Bucuresti ", "")
            except Exception:
                pass

        # Fallback: h3 for title if data-bi didn't provide one
        if not title:
            try:
                h3 = card_div.query_selector("h3")
                if h3:
                    title = h3.inner_text().strip()
            except Exception:
                pass

        # Details: extract room count, sqm, floor from card text
        try:
            card_text = card_div.inner_text()
            lines = [l.strip() for l in card_text.split("\n") if l.strip()]
            detail_parts = []
            for line in lines:
                if line == title or "€" in line or "lun" in line.lower():
                    continue
                if re.search(r'(\d+\s*camer|\d+\s*mp|[Ee]taj|mp\b)', line):
                    detail_parts.append(line)
            details = " | ".join(detail_parts) if detail_parts else ""
        except Exception:
            pass

        listings.append({
            "id": listing_id,
            "title": title,
            "url": url,
            "price": price,
            "location": location,
            "details": details,
            "photo_urls": [],
        })

    return listings


def _find_next_page(page):
    """Find and return the next page URL, or None if no next page.

    imobiliare.ro renders pagination as:
      <ul class="... pagination-page-nav ...">
        <li class="page-item 1"><p>1</p></li>   ← current page: a <p>, not an <a>
        <li class="page-item "><a href="...?page=2...">2</a></li>
        ...
      </ul>
    There is also a standalone "next page" arrow link rendered as an <a> with
    class "flex h-10 w-10 ... no-underline" that appears after the numbered
    items and whose href contains "page=N" where N is current+1.

    Strategy: find the current active page number, then return the href of the
    very next <a> sibling inside the same pagination <ul>.  As a fallback,
    grab the last anchor in the pagination nav whose href contains "page=".
    """
    try:
        # Locate the pagination list
        nav_ul = page.query_selector("ul.pagination-page-nav")
        if not nav_ul:
            return None

        items = nav_ul.query_selector_all("li")
        if not items:
            return None

        # Find the active (current) page item — it renders as a <p> not an <a>
        current_idx = None
        for idx, li in enumerate(items):
            # Active page has a <p> child (not an <a>)
            p = li.query_selector("p")
            a = li.query_selector("a")
            if p and not a:
                current_idx = idx
                break

        if current_idx is not None and current_idx + 1 < len(items):
            next_li = items[current_idx + 1]
            next_a = next_li.query_selector("a")
            if next_a:
                href = next_a.get_attribute("href")
                if href and "page=" in href:
                    return build_full_url(href)

        # Fallback: look for the dedicated "next arrow" link that appears after
        # the numbered items — it has a distinct class that includes "no-underline"
        # and its href contains "page="
        all_links = nav_ul.query_selector_all("a[href]")
        for link in reversed(list(all_links)):
            href = link.get_attribute("href") or ""
            cls = link.get_attribute("class") or ""
            if "page=" in href and "no-underline" in cls:
                return build_full_url(href)

    except Exception:
        pass
    return None


def _fetch_photos(page, url, max_photos):
    """Visit a listing detail page and extract photo URLs."""
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=20000)
        # Try JSON extraction first (more reliable)
        page_content = page.content()
        photos = extract_photos_from_json(page_content, max_photos)
        if photos:
            return photos

        # Fallback: extract from img tags on the CDN
        imgs = page.query_selector_all("img")
        urls = []
        seen = set()
        for img in imgs:
            src = img.get_attribute("src") or ""
            if "roamcdn.net" in src and "listing-thumb" not in src:
                if src not in seen:
                    seen.add(src)
                    urls.append(src)
                    if len(urls) >= max_photos:
                        break
        return urls
    except Exception as e:
        log.warning(f"Failed to fetch photos from {url}: {e}")
        return []


def scrape_search_results(page, max_pages):
    """Scrape all pages of search results across all configured URLs.

    Iterates over config.SEARCH_URLS, paginates each one, and deduplicates
    by listing ID.
    """
    all_listings = []
    seen_ids = set()

    for search_url in config.SEARCH_URLS:
        log.info(f"Scraping: {search_url[:80]}...")
        current_url = search_url
        page_num = 0

        while current_url and page_num < max_pages:
            page_num += 1
            if not _load_search_page(page, current_url):
                if page_num == 1:
                    log.warning(f"Could not load first page for {search_url[:60]}. Skipping.")
                break

            listings = _extract_listings_from_page(page)
            # Deduplicate across neighborhoods
            new_listings = [l for l in listings if l["id"] not in seen_ids]
            for l in new_listings:
                seen_ids.add(l["id"])
            all_listings.extend(new_listings)
            log.info(f"  Page {page_num}: {len(listings)} cards, {len(new_listings)} new")

            # Stop paginating if no new listings found (site recycles)
            if len(new_listings) == 0:
                log.info(f"  No new listings on page {page_num}, moving to next neighborhood")
                break

            current_url = _find_next_page(page)
            if current_url and page_num < max_pages:
                _random_delay(config.PAGINATION_DELAY)

        _random_delay(config.PAGINATION_DELAY)

    return all_listings


def run_normal():
    """Normal mode: scrape search results, fetch photos for new listings only."""
    db.init_db()
    started_at = datetime.now(timezone.utc)
    new_count = 0
    total_count = 0
    try:
        with sync_playwright() as pw:
            browser, page = _launch_browser(pw)
            try:
                all_listings = scrape_search_results(page, config.MAX_PAGES)
                total_count = len(all_listings)
                if not all_listings:
                    log.info("No listings found on search page.")
                else:
                    all_ids = [l["id"] for l in all_listings]
                    existing_ids = db.get_existing_ids(all_ids)
                    new_listings = [l for l in all_listings if l["id"] not in existing_ids]
                    log.info(f"Found {len(all_listings)} total, {len(new_listings)} new")

                    for listing in new_listings:
                        log.info(f"Fetching photos for {listing['id']}: {listing['url']}")
                        listing["photo_urls"] = _fetch_photos(page, listing["url"], config.MAX_PHOTOS)
                        log.info(f"  Got {len(listing['photo_urls'])} photos")
                        _random_delay(config.DETAIL_PAGE_DELAY)

                    if new_listings:
                        db.insert_listings(new_listings)
                        new_count = len(new_listings)
                        log.info(f"Scraper complete: {new_count} new listings added")
                    else:
                        log.info("Scraper complete: no new listings")
            finally:
                browser.close()

        finished_at = datetime.now(timezone.utc)
        db.insert_scrape_log(
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            mode="normal",
            new_listings=new_count,
            total_found=total_count,
            status="success",
            error_message=None,
            duration_seconds=(finished_at - started_at).total_seconds(),
        )
    except Exception as e:
        finished_at = datetime.now(timezone.utc)
        db.insert_scrape_log(
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            mode="normal",
            new_listings=new_count,
            total_found=total_count,
            status="error",
            error_message=str(e),
            duration_seconds=(finished_at - started_at).total_seconds(),
        )
        raise


def run_seed():
    """Seed mode: scrape all pages, no photo fetching."""
    db.init_db()
    started_at = datetime.now(timezone.utc)
    new_count = 0
    total_count = 0
    try:
        with sync_playwright() as pw:
            browser, page = _launch_browser(pw)
            try:
                all_listings = scrape_search_results(page, config.SEED_MAX_PAGES)
                total_count = len(all_listings)
                if not all_listings:
                    log.info("No listings found.")
                else:
                    all_ids = [l["id"] for l in all_listings]
                    existing_ids = db.get_existing_ids(all_ids)
                    new_listings = [l for l in all_listings if l["id"] not in existing_ids]
                    log.info(f"Seed: {len(all_listings)} total scraped, {len(new_listings)} new to insert")

                    if new_listings:
                        db.insert_listings(new_listings)
                        new_count = len(new_listings)
                        log.info(f"Seed complete: {new_count} listings inserted (no photos)")
                    else:
                        log.info("Seed complete: all listings already in DB")
            finally:
                browser.close()

        finished_at = datetime.now(timezone.utc)
        db.insert_scrape_log(
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            mode="seed",
            new_listings=new_count,
            total_found=total_count,
            status="success",
            error_message=None,
            duration_seconds=(finished_at - started_at).total_seconds(),
        )
    except Exception as e:
        finished_at = datetime.now(timezone.utc)
        db.insert_scrape_log(
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            mode="seed",
            new_listings=new_count,
            total_found=total_count,
            status="error",
            error_message=str(e),
            duration_seconds=(finished_at - started_at).total_seconds(),
        )
        raise


def run_backfill():
    """Backfill mode: fetch photos for listings that have none."""
    db.init_db()
    started_at = datetime.now(timezone.utc)
    total_count = 0
    try:
        listings = db.get_listings_without_photos(limit=config.BACKFILL_BATCH_SIZE)
        total_count = len(listings)
        if not listings:
            log.info("Backfill: no listings need photos")
        else:
            log.info(f"Backfill: fetching photos for {len(listings)} listings")
            with sync_playwright() as pw:
                browser, page = _launch_browser(pw)
                try:
                    for listing in listings:
                        url = listing["url"]
                        log.info(f"Backfill photos for {listing['id']}: {url}")
                        photos = _fetch_photos(page, url, config.MAX_PHOTOS)
                        db.update_photos(listing["id"], photos)
                        log.info(f"  Got {len(photos)} photos")
                        _random_delay(config.DETAIL_PAGE_DELAY)
                finally:
                    browser.close()

            log.info("Backfill complete")

        finished_at = datetime.now(timezone.utc)
        db.insert_scrape_log(
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            mode="backfill",
            new_listings=0,
            total_found=total_count,
            status="success",
            error_message=None,
            duration_seconds=(finished_at - started_at).total_seconds(),
        )
    except Exception as e:
        finished_at = datetime.now(timezone.utc)
        db.insert_scrape_log(
            started_at=started_at.isoformat(),
            finished_at=finished_at.isoformat(),
            mode="backfill",
            new_listings=0,
            total_found=total_count,
            status="error",
            error_message=str(e),
            duration_seconds=(finished_at - started_at).total_seconds(),
        )
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Imobiliare.ro apartment scraper")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--seed", action="store_true", help="Seed mode: bulk import, no photos")
    group.add_argument("--backfill", action="store_true", help="Backfill mode: fetch missing photos")
    args = parser.parse_args()

    if args.seed:
        run_seed()
    elif args.backfill:
        run_backfill()
    else:
        run_normal()
