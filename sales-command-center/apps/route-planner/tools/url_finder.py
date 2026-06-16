from __future__ import annotations

import json
import re
import time
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import requests
from lxml import html

CACHE_PATH = Path(__file__).parent.parent / ".tmp" / "url_cache.json"
DDG_URL = "https://html.duckduckgo.com/html/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

_cache: dict | None = None


def _load_cache() -> dict:
    global _cache
    if _cache is None:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _cache = json.loads(CACHE_PATH.read_text()) if CACHE_PATH.exists() else {}
    return _cache


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2))


def _cache_key(name: str, address: str) -> str:
    return f"{name.lower().strip()}|{address.lower().strip()}"


def find_website_url(name: str, address: str) -> str | None:
    """
    Returns a website URL for the given business, or None if not found.
    Checks .tmp/url_cache.json first; uses DuckDuckGo HTML lite if not cached.
    """
    cache = _load_cache()
    key = _cache_key(name, address)
    if key in cache:
        return cache[key]

    city, state = _extract_city_state(address)
    query = f'"{name}" {city} {state} official website'
    url = _ddg_search(query)

    cache[key] = url
    _save_cache(cache)
    return url


def _ddg_search(query: str) -> str | None:
    time.sleep(2)  # polite rate limiting
    try:
        resp = requests.post(
            DDG_URL,
            data={"q": query},
            headers=HEADERS,
            timeout=15,
            allow_redirects=True,
        )
        if resp.status_code != 200:
            return None

        tree = html.fromstring(resp.content)
        # DuckDuckGo HTML lite result links
        links = tree.cssselect("a.result__a") or tree.cssselect("a.result__url")
        if not links:
            # Fallback: find any result links by href pattern
            links = tree.xpath('//a[contains(@href, "uddg=")]')

        for link in links:
            href = link.get("href", "")
            bare = _unwrap_ddg_redirect(href)
            if bare and _is_plausible_website(bare):
                return bare

        return None
    except Exception:
        return None


def _unwrap_ddg_redirect(href: str) -> str | None:
    """
    DuckDuckGo wraps result URLs like:
      //duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com&...
    Extracts the real URL.
    """
    if not href:
        return None
    if href.startswith("//"):
        href = "https:" + href
    try:
        parsed = urlparse(href)
        qs = parse_qs(parsed.query)
        if "uddg" in qs:
            return unquote(qs["uddg"][0])
        # Already a bare URL
        if parsed.scheme in ("http", "https"):
            return href
    except Exception:
        pass
    return None


def _is_plausible_website(url: str) -> bool:
    """Filters out search engines, social networks, and directories."""
    blocklist = (
        "duckduckgo.com", "google.com", "bing.com", "yahoo.com",
        "facebook.com", "twitter.com", "x.com", "instagram.com",
        "linkedin.com", "yelp.com", "healthgrades.com", "zocdoc.com",
        "vitals.com", "webmd.com", "doximity.com", "npiprofile.com",
        "wikipedia.org", "youtube.com",
    )
    try:
        domain = urlparse(url).netloc.lower().lstrip("www.")
        return not any(domain.endswith(b) for b in blocklist)
    except Exception:
        return False


def _extract_city_state(address: str) -> tuple:
    """Best-effort extraction of city and state from an address string."""
    parts = [p.strip() for p in address.split(",")]
    if len(parts) >= 2:
        city = parts[-2] if len(parts) >= 3 else parts[0]
        # State may be "TX 12345" — take just the two-letter part
        state_part = parts[-1].strip()
        state = re.match(r"[A-Z]{2}", state_part)
        state = state.group(0) if state else state_part[:2]
        return city, state
    return address, ""
