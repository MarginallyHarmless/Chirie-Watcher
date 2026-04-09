from urllib.parse import quote


IMOBILIARE_BASE = "https://www.imobiliare.ro/inchirieri-apartamente/bucuresti"
STORIA_BASE = "https://www.storia.ro/ro/rezultate/inchiriere/apartament/bucuresti"

ROOM_MAP_STORIA = {1: "ONE", 2: "TWO", 3: "THREE", 4: "FOUR", 5: "FIVE_OR_MORE"}


def build_imobiliare_urls(settings):
    """Build one imobiliare.ro search URL per neighborhood."""
    rooms_str = ",".join(str(r) for r in sorted(settings["rooms"]))
    price_str = f"{settings['price_min']}-{settings['price_max']}"
    urls = []
    for neighborhood in settings["neighborhoods"]:
        slug = neighborhood.lower().strip().replace(" ", "-")
        urls.append(f"{IMOBILIARE_BASE}/{slug}?rooms={rooms_str}&price={price_str}")
    return urls


def build_storia_urls(settings):
    """Build a single storia.ro city-level search URL."""
    storia_rooms = [ROOM_MAP_STORIA[r] for r in sorted(settings["rooms"]) if r in ROOM_MAP_STORIA]
    rooms_param = quote("[" + ",".join(storia_rooms) + "]")
    return [
        f"{STORIA_BASE}?priceMin={settings['price_min']}&priceMax={settings['price_max']}&roomsNumber={rooms_param}"
    ]
