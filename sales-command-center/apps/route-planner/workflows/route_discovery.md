# Workflow: Route Discovery

## Objective
Find businesses/practices of a specified type along a driving route within a user-defined corridor, optionally filtering by content found on each practice's website.

## Required Inputs
- `origin`: Starting address or place name
- `destination`: Ending address or place name
- `corridor_miles`: How far off the route to search (set by user, default 10)
- `query`: What to find (e.g. "ophthalmologists", "pharmacies")
- `criteria_keywords`: Optional list of terms to look for on each website
- `document`: Optional CSV/Excel/PDF/Google Sheet of known locations

## Tools Used
| Tool | Purpose |
|------|---------|
| `tools/geocode.py` | Convert addresses to lat/lon |
| `tools/routing.py` | Fetch driving route polyline from ORS |
| `tools/overpass_search.py` | Discover places via OpenStreetMap |
| `tools/document_parser.py` | Load candidates from uploaded files |
| `tools/corridor_filter.py` | Filter candidates by distance to route |
| `tools/url_finder.py` | Find practice website URLs via DuckDuckGo |
| `tools/website_scraper.py` | Scrape websites and check for keywords |
| `tools/result_builder.py` | Orchestrate URL lookup + scraping |

## Execution Steps

1. **Geocode** origin and destination using `geocode_address()`.
   - Uses Nominatim first (1 req/sec, no key needed).
   - Falls back to ORS geocoding if Nominatim returns nothing.
   - Results cached in `.tmp/geocode_cache.json`.

2. **Fetch route** using `fetch_route_polyline()`.
   - Calls OpenRouteService `/v2/directions/driving-car/geojson`.
   - Returns route coordinates + bounding box.
   - Usage logged to `.tmp/ors_usage.json`.

3. **Discover candidates** — two paths:

   **Path A: Document provided**
   - Parse with `parse_document(path, type)`.
   - Geocode each address (cached).
   - Use these as candidates.

   **Path B: No document**
   - Expand route bbox by `corridor_miles × 1.1` via `expand_bbox_for_corridor()`.
   - Query Overpass API with OSM tags matching the query type.
   - Use returned nodes/ways as candidates.

4. **Filter by corridor** using `filter_by_corridor()`.
   - Projects each candidate onto the route polyline using haversine math.
   - Keeps candidates within `corridor_miles` of the polyline.
   - Annotates each with `distance_off_route_miles` and `route_position_t`.
   - Sorts ascending by `t` (drive order, origin=0 → destination=1).

5. **Scrape websites** (only if keywords provided) via `enrich_with_scraping()`.
   - Capped at 20 candidates to keep total search time under ~60 seconds.
   - For each candidate:
     a. Use existing website URL from OSM/document if available.
     b. Otherwise, search DuckDuckGo for the practice website (2s delay, cached).
     c. Scrape the page with `requests` + `lxml`.
     d. Check each keyword as case-insensitive substring.
     e. If `requests` fails (JS-rendered, Cloudflare), try Firecrawl fallback (requires `FIRECRAWL_API_KEY` in `.env`).

6. **Return results** as JSON to the frontend.

## Edge Cases & Notes

### Geocoding
- Always include the state/city in the input for better Nominatim accuracy.
- If Nominatim returns a wrong city, add the state abbreviation (e.g. "Austin, TX" not just "Austin").
- ORS geocoding fallback requires `ORS_API_KEY` in `.env`.

### Overpass API
- Timeout set to 30 seconds in queries. If it times out, the query returns an empty list gracefully.
- OSM data is community-maintained — small practices may be missing or have outdated info.
- OSM often includes `website`, `contact:website` tags — check these before DuckDuckGo.

### Website Scraping
- Many practice websites are simple HTML and scrape cleanly.
- Sites behind Cloudflare or that require JS will fail with `requests`; set `FIRECRAWL_API_KEY` for those.
- SSL errors are retried without verification as a last resort.
- "No website URL found" is a normal outcome for small practices with no online presence.

### DuckDuckGo URL Lookup
- Results are cached in `.tmp/url_cache.json` — re-runs are instant.
- DuckDuckGo's HTML structure can change; the parsing is in `tools/url_finder.py:_ddg_search()`.
- Blocklist in `_is_plausible_website()` filters out Yelp, Healthgrades, social media, etc.

### Rate Limits
| Service | Limit | Where Enforced |
|---------|-------|----------------|
| Nominatim | 1 req/sec | `time.sleep(1)` in `geocode.py` |
| ORS routing | 2000/day | Logged to `.tmp/ors_usage.json` |
| ORS geocoding | 40/min | Nominatim used first to avoid this |
| DuckDuckGo | Informal | `time.sleep(2)` in `url_finder.py` |
| Overpass | Polite use | `[timeout:30]` in queries |

### Document Parsing
- Column names are fuzzy-matched (e.g. "Practice Name", "PROVIDER", "clinic" all map to `name`).
- If a document has separate city/state/zip columns with no combined address column, they are concatenated.
- PDF parsing is best-effort (regex heuristic). Well-structured directory PDFs work best; scanned PDFs will not.
- Google Sheets requires `credentials.json` for OAuth. Set up at: https://docs.gspread.org/en/latest/oauth2.html

## Required Environment Variables
```
ORS_API_KEY         # Required. Free signup: https://openrouteservice.org
FLASK_SECRET_KEY    # Required. Any random string.
FIRECRAWL_API_KEY   # Optional. Enables scraping of JS-heavy/Cloudflare sites.
```

## Running the App
```bash
cd "AI HOME/Office Finder"
pip install -r requirements.txt
python app.py
# Open http://localhost:5001
```

## Self-Improvement Notes
- If Overpass returns no results for a query type, add new tag pairs to `OSM_TAG_MAP` in `tools/overpass_search.py`.
- If DuckDuckGo stops returning URLs (HTML structure change), update `_ddg_search()` in `tools/url_finder.py`.
- If a specific practice type consistently fails scraping, add its domain to the blocklist in `_is_plausible_website()` or investigate the HTML structure.
