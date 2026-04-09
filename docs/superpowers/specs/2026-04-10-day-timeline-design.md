# Day Timeline Dashboard Design

## Overview

Replace the "new" badge and new/acknowledged mechanic on the dashboard with day-grouped listings and a side timeline. Listings are visually separated by date headers, with a sticky timeline on the left for orientation and quick navigation.

## Layout

The listing area becomes a two-column layout:

- **Left: Timeline** — narrow column (~80px) with date dots stacked vertically. Sticky-positioned so it stays visible while scrolling. The day currently in the viewport gets a filled/highlighted dot. Clicking a date scrolls to that day's section. Hidden on mobile (<768px).
- **Right: Listings** — the existing card grid, but now broken into sections by day. Each section starts with a full-width date header bar.

## Day Headers

Full-width separator bars inserted between day groups:

- **Today** — "Today, April 10"
- **Yesterday** — "Yesterday, April 9"  
- **Older** — "April 8", "April 7", etc.

Styled as a subtle horizontal line with the date label, using `--text-muted` color, uppercase small text — consistent with section headers on the settings page.

## Side Timeline

A vertical list of date entries, one per day present on the current page:

- Each entry: a dot (circle) and a short date label ("Today", "Apr 9", "Apr 8")
- Connected by a thin vertical line
- The dot for the day currently scrolled into view is filled with `--accent` color; others are hollow with `--border` color
- Clicking a timeline entry scrolls the corresponding day header into view (smooth scroll)
- Uses `position: sticky; top: <header-height>` so it stays visible while scrolling the listing area
- On mobile (<768px): hidden entirely via `display: none`. Day headers alone provide grouping.

## Scroll Tracking

An `IntersectionObserver` watches all day header elements. When a header enters/exits the viewport, the timeline updates which dot is highlighted. This is lightweight and doesn't require scroll event listeners.

## Filter Tabs

Change from: **New | All | Removed**  
Change to: **Active | Removed**

- "Active" (default) — shows all non-removed listings, equivalent to the old "all" filter
- "Removed" — same as before

The API `filter` param: send `filter=all` for Active tab, `filter=removed` for Removed tab. No API changes needed.

## Acknowledge Removal

- Remove the "New" badge from cards
- Remove the `is_new`-based highlighting
- Remove the onclick acknowledge call (`POST /api/listings/<id>/acknowledge`)
- Remove the "New" filter tab
- The `is_new` column remains in the DB schema (harmless dead column)
- The acknowledge API endpoint remains in server.py (harmless, avoids migration)

## Card Changes

- Remove the "NEW" badge element
- Keep everything else: photo carousel, price, location, details, source label, duplicate badge

## Sorting

- Day groups are always ordered newest-first (most recent day at top)
- Within each day group, cards follow the selected sort order (newest, oldest, price high, price low)
- The sort dropdown remains unchanged

## Pagination

- Pagination stays as-is (50 per page)
- Each page may contain listings from multiple days — the timeline shows only days present on the current page
- Page 1 will typically show "Today" and maybe "Yesterday"; deeper pages show older days

## Grouping Logic (JavaScript)

In `renderListings`, after receiving the API response:

1. Parse `first_seen` for each listing into a date string (YYYY-MM-DD in local time)
2. Group listings into an ordered map: `{ "2026-04-10": [...], "2026-04-09": [...], ... }`
3. For each group, render: a day header element (with a data attribute for scroll targeting) + the cards grid
4. Render the timeline from the same group keys

## Files Changed

- `dashboard.html` — all changes are here (CSS + JS). No API or backend changes.

## Non-goals

- Infinite scroll (keep pagination)
- Collapsible day sections
- Date range filtering
- Removing `is_new` from DB schema or removing the acknowledge endpoint
