from tools.url_finder import find_website_url
from tools.website_scraper import scrape_keywords


def enrich_with_scraping(candidates: list, keywords: list) -> list:
    """
    For each candidate: find website URL (if not already known), scrape for keywords.
    Modifies candidates in-place and returns them.
    Caps scraping at len(candidates) — caller is responsible for passing at most 20.
    """
    for c in candidates:
        # Use URL from document/OSM if already present
        url = c.get("website") or None

        # Try DuckDuckGo lookup if no URL
        if not url:
            try:
                url = find_website_url(c.get("name", ""), c.get("address", ""))
            except Exception:
                url = None

        c["website_url"] = url

        if url:
            result = scrape_keywords(url, keywords)
            c["scraped"] = result["scraped"]
            c["keyword_matches"] = result["keyword_matches"]
            c["keyword_misses"] = result["keyword_misses"]
            c["scrape_error"] = result["error"]
        else:
            c["scraped"] = False
            c["keyword_matches"] = []
            c["keyword_misses"] = list(keywords)
            c["scrape_error"] = "No website URL found"

    return candidates
