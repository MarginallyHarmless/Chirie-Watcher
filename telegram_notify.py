import logging
import time

import requests

import config

log = logging.getLogger("telegram")

API_BASE = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"


def _send_request(method, data, files=None):
    """Send a request to the Telegram Bot API."""
    try:
        resp = requests.post(f"{API_BASE}/{method}", data=data, files=files, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        log.error(f"Telegram API error ({method}): {e}")
        return None


def _format_listing_text(listing):
    """Format a listing into a Telegram message with HTML."""
    parts = []
    parts.append(f"<b>{listing.get('price', 'No price')}</b>")
    if listing.get("title"):
        parts.append(listing["title"])
    if listing.get("location"):
        parts.append(f"📍 {listing['location']}")
    if listing.get("details"):
        parts.append(listing["details"])
    source = listing.get("source", "imobiliare")
    if source == "storia":
        parts.append(f"\n<a href=\"{listing['url']}\">View on storia.ro</a>")
    else:
        parts.append(f"\n<a href=\"{listing['url']}\">View on imobiliare.ro</a>")
    return "\n".join(parts)


def send_listing(listing):
    """Send a single listing notification via Telegram.

    If the listing has photos, sends them as a media group with the caption
    on the first photo. Otherwise sends a text message.
    """
    photos = listing.get("photo_urls", [])
    text = _format_listing_text(listing)

    if photos:
        # Telegram media groups support up to 10 items
        import json
        media = []
        for i, url in enumerate(photos[:10]):
            item = {"type": "photo", "media": url}
            if i == 0:
                item["caption"] = text
                item["parse_mode"] = "HTML"
            media.append(item)

        result = _send_request("sendMediaGroup", {
            "chat_id": config.TELEGRAM_CHAT_ID,
            "media": json.dumps(media),
        })
        if result and result.get("ok"):
            return True

        # Fallback: if media group fails (e.g. bad photo URLs), send text only
        log.warning("Media group failed, falling back to text message")

    _send_request("sendMessage", {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    })
    return True


def notify_new_listings(listings):
    """Send Telegram notifications for a list of new listings."""
    if not listings:
        return

    log.info(f"Sending Telegram notifications for {len(listings)} listings")
    for i, listing in enumerate(listings):
        send_listing(listing)
        # Small delay between messages to avoid rate limits
        if i < len(listings) - 1:
            time.sleep(1)
    log.info("Telegram notifications sent")
