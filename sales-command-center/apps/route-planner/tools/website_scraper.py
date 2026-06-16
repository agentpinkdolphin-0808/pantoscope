from __future__ import annotations

import os

import requests
from lxml import html

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def scrape_keywords(url: str, keywords: list, timeout: int = 10) -> dict:
    """
    Fetches the page at url and checks for each keyword in the visible text.
    Returns:
        {
            "url": str,
            "scraped": bool,
            "keyword_matches": [str, ...],
            "keyword_misses": [str, ...],
            "error": str | None,
        }
    """
    text = _fetch_page_text(url, timeout)

    if text is None:
        # Try Firecrawl if available
        text = _firecrawl_fallback(url)

    if text is None:
        return {
            "url": url,
            "scraped": False,
            "keyword_matches": [],
            "keyword_misses": list(keywords),
            "error": "Could not fetch page",
        }

    matches = []
    misses = []
    for kw in keywords:
        if kw.lower() in text:
            matches.append(kw)
        else:
            misses.append(kw)

    return {
        "url": url,
        "scraped": True,
        "keyword_matches": matches,
        "keyword_misses": misses,
        "error": None,
    }


def _fetch_page_text(url: str, timeout: int) -> str | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        if resp.status_code >= 400:
            return None

        content_type = resp.headers.get("content-type", "")
        if "html" not in content_type and "text" not in content_type:
            return None

        tree = html.fromstring(resp.content)

        # Remove script and style elements
        for el in tree.xpath("//script | //style | //noscript | //head"):
            el.getparent().remove(el)

        # Extract all visible text
        text = " ".join(tree.xpath("//body//text()"))
        return text.lower()

    except requests.exceptions.SSLError:
        # Try without SSL verification as last resort
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout,
                                allow_redirects=True, verify=False)
            if resp.status_code >= 400:
                return None
            tree = html.fromstring(resp.content)
            for el in tree.xpath("//script | //style | //noscript | //head"):
                el.getparent().remove(el)
            return " ".join(tree.xpath("//body//text()")).lower()
        except Exception:
            return None

    except Exception:
        return None


def _firecrawl_fallback(url: str) -> str | None:
    """Uses Firecrawl to scrape JS-rendered or protected pages if API key is set."""
    api_key = os.getenv("FIRECRAWL_API_KEY", "")
    if not api_key or api_key == "optional_only_needed_for_js_heavy_sites":
        return None
    try:
        from firecrawl import FirecrawlApp
        app = FirecrawlApp(api_key=api_key)
        result = app.scrape_url(url, formats=["markdown"])
        md = result.get("markdown", "") or ""
        return md.lower()
    except Exception:
        return None
