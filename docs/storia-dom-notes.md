# Storia.ro DOM Structure Notes

Discovered 2026-04-07 via Playwright headless Chromium.

## Best Extraction Method: `__NEXT_DATA__` JSON

Storia.ro is a Next.js app. The **most reliable** way to extract data is from the
`<script id="__NEXT_DATA__">` tag embedded in every page. This avoids fragile CSS
selectors entirely.

### Search Results Page

**Path:** `props.pageProps.data.searchAds.items` -- array of listing objects.

Each item has these keys (37 items per page):

| Key | Type | Example |
|-----|------|---------|
| `id` | int | `10231131` |
| `title` | str | `"Apartament de Inchiriat - 2 Camere - Zona Berceni/..."` |
| `slug` | str | `"apartament-de-inchiriat-2-camere-zona-berceni-...-IDGWAf"` |
| `estate` | str | `"FLAT"` |
| `transaction` | str | `"RENT"` |
| `totalPrice` | obj | `{"value": 499, "currency": "EUR"}` (assumed from DOM) |
| `rentPrice` | obj | rent-specific price |
| `pricePerSquareMeter` | obj | price/m2 |
| `areaInSquareMeters` | num | `50` |
| `roomsNumber` | str | `"TWO"` / `"THREE"` |
| `floorNumber` | int | floor number |
| `dateCreated` | str | ISO datetime |
| `createdAtFirst` | str | first publish datetime |
| `pushedUpAt` | str/null | bump datetime |
| `isPromoted` | bool | promoted listing flag |
| `isPrivateOwner` | bool | owner vs agency |
| `isExclusiveOffer` | bool | exclusive flag |
| `shortDescription` | str | truncated description |
| `href` | str | relative URL path |
| `images` | list | each has `medium` and `large` keys (CDN URLs) |
| `location` | obj | nested: `reverseGeocoding.locations[]` with `id`, `fullName`, `name`, `locationLevel` |
| `agency` | obj/null | agency info |

**Listing ID:** The `id` field (e.g. `10231131`). Also extractable from the slug suffix: `IDGWAf` is the `publicId`.

**Listing URL pattern:** `/ro/oferta/{slug}` where slug ends with `-ID{publicId}`

### Pagination

From `props.pageProps.tracking.listing`:

| Key | Example |
|-----|---------|
| `page_nb` | `1` |
| `page_count` | `182` |
| `result_count` | `6527` |
| `results_per_page` | `36` |

**URL pattern:** Append `&page=2`, `&page=3`, etc. Verified that `?...&page=2` returns different listings.

### Detail Page

**Path:** `props.pageProps.ad` -- single ad object.

Key fields:

| Key | Type | Notes |
|-----|------|-------|
| `id` | int | `10231131` |
| `title` | str | full title |
| `description` | str | HTML description |
| `price` | obj | `{"type": "...", "__typename": "AdvertPrice"}` |
| `slug` | str | URL slug |
| `createdAt` | str | ISO datetime with timezone |
| `modifiedAt` | str | last modified |
| `images` | list | **4 sizes**: `thumbnail` (184x138), `small` (314x236), `medium` (655x491), `large` (1280x1024) |
| `characteristics` | list | key-value pairs: `price`, `m` (area), `rooms_num`, `floor`, `building_type`, etc. |
| `topInformation` | list | labeled info: area, rooms, floor, etc. |
| `additionalInformation` | list | extra details |
| `featuresByCategory` | list | grouped features (facilities, extras, etc.) |
| `features` | list | flat list of feature strings |
| `target` | obj | structured data: `Area`, `Build_year`, `Building_material`, `Floor_no`, `Heating`, `Equipment_types`, `Extras_types`, etc. |
| `location` | obj | coordinates (lat/lng), address with district/province |
| `owner` | obj | name, phones, imageUrl |
| `agency` | obj | name, id, phones, address, url |
| `url` | str | canonical URL |
| `status` | str | `"active"` |

## Detail Page Photos

**CDN domain:** `ireland.apollo.olxcdn.com`

**URL pattern:** `https://ireland.apollo.olxcdn.com/v1/files/{base64-hash}/image;s={width}x{height};q={quality}`

**Image sizes available in `ad.images[]`:**

| Key | Dimensions | Quality |
|-----|-----------|---------|
| `thumbnail` | 184x138 | q=80 |
| `small` | 314x236 | q=80 |
| `medium` | 655x491 | q=80 |
| `large` | 1280x1024 | q=80 |

To get full-size: use `large` URL from `__NEXT_DATA__`, or strip the `;s=...;q=...` suffix from any URL.

On search results pages, images only include `medium` and `large` keys.

## DOM Selectors (Fallback)

If DOM scraping is needed instead of JSON extraction:

### Search Results Page

| Element | Selector | Notes |
|---------|----------|-------|
| Listing card | `article` | 37 per page (36 organic + 1 promoted) |
| Promoted section | `[data-cy='search.listing.promoted']` | container for promoted listings |
| Organic section | `[data-cy='search.listing.organic']` | container for organic listings |
| Title | `[data-cy='listing-item-title']` | `<p>` tag with title text |
| Link | `[data-cy='listing-item-link']` | `<a>` with href to detail page |
| Image | `[data-cy='listing-item-image-source']` | `<img>` with CDN src |
| Save button | `[data-cy='save-ad-button']` | bookmark button |
| Listing link (alt) | `a[href*='/ro/oferta/']` | 145 per page (multiple per card due to carousel) |
| Pagination | `[data-cy='search-list-pagination']` | pagination container |
| Page heading | `[data-cy='search-listing.heading']` | `<h1>` |

**Price:** Rendered as `<span>` with CSS class `css-6t3bie` containing e.g. `"499 EUR"`. No `data-cy` attribute on price.

**Location:** Rendered as `<p>` with CSS class `css-oxb2ca` containing e.g. `"IMGB, Sectorul 4, Bucuresti"`. No `data-cy`.

**Details (rooms, area, floor):** Rendered as `<dt>` / `<span>` pairs inside a definition list. Labels like "Numarul de camere", "Pretul pe metru patrat", "Etaj".

### Detail Page

| Element | Selector |
|---------|----------|
| Title | `[data-cy='adPageAdTitle']` (`<h1>`) |
| Price | `[data-cy='adPageHeaderPrice']` (`<strong>`) |
| Description | `[data-cy='adPageAdDescription']` (`<div>`) |
| Gallery | `[data-cy='mosaic-gallery-main-view']` |
| Seller info | `[data-cy='seller-info']` |
| Contact form | `[data-cy='contact-form']` |
| Share button | `[data-cy='share-ad-button']` |
| Save button | `[data-cy='save-ad-button']` |
| Breadcrumbs | `[data-cy='breadcrumb']` |

## Working Search URL Format

**Base pattern:**
```
https://www.storia.ro/ro/rezultate/{transaction}/{estate}/{location}?{params}
```

**Verified working:**
```
https://www.storia.ro/ro/rezultate/inchiriere/apartament/bucuresti?priceMin=300&priceMax=800&roomsNumber=%5BTWO%2CTHREE%5D
```
- Returns 6527 results, 182 pages, 36 per page.
- Page 2: append `&page=2`

**Non-working (neighborhood-level URLs):**
```
.../bucuresti/decebal?...   -> 0 results
.../bucuresti/unirii?...    -> 0 results
```
Neighborhood filtering does NOT work via URL path segments. Use the city-level URL and filter results by `location.reverseGeocoding.locations[]` in the JSON data instead.

**Room filter values:** `ONE`, `TWO`, `THREE`, `FOUR`, `FIVE_OR_MORE` (URL-encoded as `%5BTWO%2CTHREE%5D` for `[TWO,THREE]`).

## Recommended Scraping Strategy

1. **Use `__NEXT_DATA__` JSON** -- parse the script tag, extract `props.pageProps.data.searchAds.items`
2. **Paginate** with `&page=N` up to `page_count` from tracking data
3. **No need to visit detail pages** for basic listing data (title, price, area, rooms, location, images are all in search results JSON)
4. **Visit detail pages only** if you need: full description, features/amenities, owner phone, all 4 image sizes, or build year
5. **Listing ID** is the `id` field (integer); use for deduplication across scrape runs
