# Day Timeline Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the "new" badge with day-grouped listings and a side timeline on the dashboard.

**Architecture:** Pure frontend change in `dashboard.html`. Listings are grouped by `first_seen` date in the `renderListings` function. A sticky side timeline with clickable date dots provides orientation. An IntersectionObserver tracks which day is in view. The "New" filter tab and acknowledge mechanic are removed.

**Tech Stack:** Vanilla HTML/CSS/JS (same as existing dashboard).

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `dashboard.html` | Modify | All changes: CSS (timeline, day headers, layout), HTML (filter tabs, layout wrapper), JS (grouping, timeline, observer, remove acknowledge) |

---

### Task 1: CSS and HTML structure changes

**Files:**
- Modify: `dashboard.html`

- [ ] **Step 1: Add timeline and day-header CSS**

Add these styles before the `/* === RESPONSIVE === */` comment (around line 582):

```css
        /* === TIMELINE LAYOUT === */
        .content-area {
            display: flex;
            max-width: 1400px;
            margin: 0 auto;
            padding: 8px 32px 48px;
            gap: 0;
        }

        .timeline {
            width: 80px;
            flex-shrink: 0;
            position: sticky;
            top: 80px;
            align-self: flex-start;
            padding: 8px 0;
            height: fit-content;
        }

        .timeline-entry {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 0;
            cursor: pointer;
            position: relative;
            transition: color 0.2s;
            color: var(--text-muted);
            font-size: 12px;
            font-weight: 500;
        }

        .timeline-entry:hover { color: var(--text-secondary); }
        .timeline-entry.active { color: var(--accent); }

        .timeline-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            border: 2px solid var(--border);
            background: transparent;
            flex-shrink: 0;
            transition: all 0.2s;
        }

        .timeline-entry.active .timeline-dot {
            border-color: var(--accent);
            background: var(--accent);
        }

        .timeline-line {
            position: absolute;
            left: 3px;
            top: 24px;
            bottom: -8px;
            width: 2px;
            background: var(--border-light);
        }

        .timeline-entry:last-child .timeline-line { display: none; }

        .listings-column {
            flex: 1;
            min-width: 0;
        }

        /* === DAY HEADER === */
        .day-header {
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            color: var(--text-muted);
            padding: 24px 0 12px;
            border-bottom: 1px solid var(--border-light);
            margin-bottom: 16px;
        }

        .day-header:first-child { padding-top: 8px; }

        .day-group {
            margin-bottom: 8px;
        }

        .day-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(480px, 1fr));
            gap: 20px;
        }
```

- [ ] **Step 2: Update the responsive media query**

Find the existing `@media (max-width: 768px)` block and replace it with:

```css
        @media (max-width: 768px) {
            .header { padding: 16px 20px; }
            .controls { padding: 12px 20px; }
            .content-area { padding: 8px 16px 40px; }
            .timeline { display: none; }
            .day-grid { grid-template-columns: 1fr; }
            .header h1 { font-size: 20px; }
            .card-photos.photos-many,
            .card-photos.photos-5 { grid-template-rows: 100px 100px; }
            .card-photos.photos-4 { grid-template-rows: 110px 110px; }
            .card-photos.photos-3 { grid-template-rows: 130px; }
        }
```

- [ ] **Step 3: Remove old `.listings` grid padding**

Find and update the `.listings` CSS rule (around line 229):

```css
        .listings {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(480px, 1fr));
            gap: 20px;
        }
```

Remove the `padding`, `max-width`, and `margin` properties — those are now on `.content-area`.

- [ ] **Step 4: Remove `.badge-new` and `.btn-ack` CSS**

Delete the `.badge-new` block (lines 363-376) and the `.btn-ack` / `.btn-ack:hover` blocks (lines 474-491). Also remove `.card.seen` / `.card.seen:hover` (lines 255-256).

- [ ] **Step 5: Update filter tabs HTML**

Replace the filter-toggle div (lines 621-624):

```html
            <div class="filter-toggle">
                <button class="filter-btn active" data-filter="new" onclick="setFilter('new')">New</button>
                <button class="filter-btn" data-filter="all" onclick="setFilter('all')">All</button>
                <button class="filter-btn" data-filter="removed" onclick="setFilter('removed')">Removed</button>
            </div>
```

With:

```html
            <div class="filter-toggle">
                <button class="filter-btn active" data-filter="all" onclick="setFilter('all')">Active</button>
                <button class="filter-btn" data-filter="removed" onclick="setFilter('removed')">Removed</button>
            </div>
```

- [ ] **Step 6: Replace the listings div with content-area layout**

Replace:

```html
    <div class="listings" id="listings"></div>
```

With:

```html
    <div class="content-area">
        <div class="timeline" id="timeline"></div>
        <div class="listings-column" id="listingsColumn"></div>
    </div>
```

- [ ] **Step 7: Commit**

```bash
git add dashboard.html
git commit -m "feat: add timeline/day-header CSS and layout structure"
```

---

### Task 2: JavaScript — day grouping, timeline, and cleanup

**Files:**
- Modify: `dashboard.html`

- [ ] **Step 1: Update initial state**

Change `let currentFilter = 'new';` to `let currentFilter = 'all';`.

- [ ] **Step 2: Replace the renderListings function**

Replace the entire `renderListings` function with this version that groups listings by day and renders both the timeline and the day-grouped cards:

```javascript
        function formatDayLabel(dateStr) {
            const date = new Date(dateStr + 'T00:00:00');
            const today = new Date();
            today.setHours(0,0,0,0);
            const yesterday = new Date(today);
            yesterday.setDate(yesterday.getDate() - 1);
            const d = new Date(date);
            d.setHours(0,0,0,0);
            if (d.getTime() === today.getTime()) {
                return 'Today, ' + date.toLocaleDateString('en-GB', { day: 'numeric', month: 'long' });
            }
            if (d.getTime() === yesterday.getTime()) {
                return 'Yesterday, ' + date.toLocaleDateString('en-GB', { day: 'numeric', month: 'long' });
            }
            return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'long' });
        }

        function shortDayLabel(dateStr) {
            const date = new Date(dateStr + 'T00:00:00');
            const today = new Date();
            today.setHours(0,0,0,0);
            const yesterday = new Date(today);
            yesterday.setDate(yesterday.getDate() - 1);
            const d = new Date(date);
            d.setHours(0,0,0,0);
            if (d.getTime() === today.getTime()) return 'Today';
            if (d.getTime() === yesterday.getTime()) return 'Yest.';
            return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
        }

        function groupByDay(listings) {
            const groups = new Map();
            for (const l of listings) {
                const d = new Date(l.first_seen);
                const key = d.getFullYear() + '-' +
                    String(d.getMonth() + 1).padStart(2, '0') + '-' +
                    String(d.getDate()).padStart(2, '0');
                if (!groups.has(key)) groups.set(key, []);
                groups.get(key).push(l);
            }
            return groups;
        }

        function renderListings(data) {
            const column = document.getElementById('listingsColumn');
            const timelineEl = document.getElementById('timeline');

            if (!data.listings.length) {
                column.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-state-icon">&#9675;</div>
                        <div>No listings found</div>
                    </div>`;
                timelineEl.innerHTML = '';
                return;
            }

            const groups = groupByDay(data.listings);
            let html = '';
            let timelineHtml = '';

            for (const [dateKey, listings] of groups) {
                html += `<div class="day-group" id="day-${dateKey}">`;
                html += `<div class="day-header">${formatDayLabel(dateKey)}</div>`;
                html += `<div class="day-grid">`;

                for (const l of listings) {
                    html += renderCard(l);
                }

                html += `</div></div>`;

                timelineHtml += `
                    <div class="timeline-entry" data-day="${dateKey}" onclick="scrollToDay('${dateKey}')">
                        <div class="timeline-dot"></div>
                        <span>${shortDayLabel(dateKey)}</span>
                        <div class="timeline-line"></div>
                    </div>`;
            }

            column.innerHTML = html;
            timelineEl.innerHTML = timelineHtml;
            setupDayObserver();
        }

        function renderCard(l) {
            const hasPhotos = l.photo_urls && l.photo_urls.length;
            const photoCount = hasPhotos ? l.photo_urls.length : 0;
            const maxVisible = 6;
            const remaining = photoCount - maxVisible;
            const dateStr = new Date(l.first_seen).toLocaleDateString('en-GB', {
                day: 'numeric', month: 'short', year: 'numeric'
            });

            let gridClass = 'photos-1';
            if (photoCount === 2) gridClass = 'photos-2';
            else if (photoCount === 3) gridClass = 'photos-3';
            else if (photoCount === 4) gridClass = 'photos-4';
            else if (photoCount === 5) gridClass = 'photos-5';
            else if (photoCount >= 6) gridClass = 'photos-many';

            const visiblePhotos = hasPhotos ? l.photo_urls.slice(0, maxVisible) : [];

            return `
            <div class="card ${l.removed_at ? 'removed' : ''}" id="card-${l.id}">
                <div class="card-photos ${hasPhotos ? gridClass : ''}" data-photos='${hasPhotos ? JSON.stringify(l.photo_urls) : "[]"}'>
                    ${l.removed_at ? `<span class="badge-removed">${durationLabel(l.first_seen, l.removed_at)}</span>` : ''}
                    ${l.possible_duplicate_of ? '<span class="badge-duplicate">Possible duplicate</span>' : ''}
                    ${hasPhotos ? visiblePhotos.map((url, i) => {
                        const isLast = i === maxVisible - 1 && remaining > 0;
                        return `<${isLast ? 'div class="photo-more"' : 'div'} ${isLast ? `data-remaining="+${remaining}"` : ''}>
                            <img src="${esc(url)}" alt="photo" loading="lazy" onclick="openLightbox(JSON.parse(this.closest('.card-photos').dataset.photos), ${i})">
                        </div>`;
                    }).join('') : '<div class="no-photo">No photos</div>'}
                </div>
                <div class="card-body">
                    <div class="card-price">${esc(l.price || 'No price')}</div>
                    <a class="card-title" href="${esc(l.url)}" target="_blank">${esc(l.title || 'Untitled')}</a>
                    <div class="card-info">
                        ${l.location ? `<span>${esc(l.location)}</span>` : ''}
                        ${l.details ? `<span>${esc(l.details)}</span>` : ''}
                    </div>
                    <div class="card-meta">
                        <span class="card-date">${dateStr} · <span class="card-source">${esc(l.source || 'imobiliare')}</span></span>
                    </div>
                </div>
            </div>`;
        }
```

- [ ] **Step 3: Add scrollToDay and IntersectionObserver**

Add after `renderCard`:

```javascript
        function scrollToDay(dateKey) {
            const el = document.getElementById('day-' + dateKey);
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }

        let dayObserver = null;
        function setupDayObserver() {
            if (dayObserver) dayObserver.disconnect();
            const headers = document.querySelectorAll('.day-group');
            if (!headers.length) return;

            dayObserver = new IntersectionObserver((entries) => {
                // Find the topmost visible day group
                let topDay = null;
                let topY = Infinity;
                for (const entry of entries) {
                    if (entry.isIntersecting) {
                        const y = entry.boundingClientRect.top;
                        if (y < topY) {
                            topY = y;
                            topDay = entry.target.id.replace('day-', '');
                        }
                    }
                }
                if (topDay) {
                    document.querySelectorAll('.timeline-entry').forEach(te => {
                        te.classList.toggle('active', te.dataset.day === topDay);
                    });
                }
            }, { rootMargin: '-80px 0px -60% 0px' });

            headers.forEach(h => dayObserver.observe(h));
        }
```

- [ ] **Step 4: Remove the acknowledge function**

Delete the entire `acknowledge` function (lines 849-863 in the original).

- [ ] **Step 5: Update setFilter default**

In the `setFilter` function, no changes needed — it already works with the new data-filter attributes. Just verify `currentFilter` starts as `'all'` (done in step 1).

- [ ] **Step 6: Remove animation-delay from cards**

The old renderListings had `style="animation-delay: ${Math.min(idx * 40, 600)}ms"` on each card. The new `renderCard` doesn't include this — cards appear immediately. The `@keyframes cardIn` and `.card { animation: cardIn ... }` CSS can stay (it still looks nice as a fade-in, just without staggering).

- [ ] **Step 7: Verify manually in browser**

1. Run: `pm2 restart imobiliare-dashboard`
2. Open http://localhost:5000
3. Verify:
   - Listings grouped by day with date headers
   - Side timeline shows dates with dots
   - Clicking a timeline entry scrolls to that day
   - The active day's dot is filled orange as you scroll
   - "Active" and "Removed" filter tabs work
   - No "New" badge or "Mark seen" button on cards
   - Sort dropdown still works within day groups
   - Pagination still works
   - Mobile (<768px): timeline hidden, day headers remain
   - Lightbox still works

- [ ] **Step 8: Commit**

```bash
git add dashboard.html
git commit -m "feat: replace new badge with day-grouped listings and side timeline"
```
