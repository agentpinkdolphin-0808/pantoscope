from __future__ import annotations

import json
import os
import time
import requests
from pathlib import Path

CACHE_PATH = Path(__file__).parent.parent / ".tmp" / "geocode_cache.json"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
ORS_GEOCODE_URL = "https://api.openrouteservice.org/geocode/search"
HEADERS = {"User-Agent": "RouteDiscoveryDashboard/1.0 (justin.skinner.business@gmail.com)"}

_cache: dict | None = None


def _load_cache() -> dict:
    global _cache
    if _cache is None:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        if CACHE_PATH.exists():
            with open(CACHE_PATH) as f:
                _cache = json.load(f)
        else:
            _cache = {}
    return _cache


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def _cache_key(address: str) -> str:
    return address.lower().strip()


def geocode_address(address: str) -> dict:
    """
    Returns {"lat": float, "lon": float, "display_name": str}
    Raises ValueError if address cannot be geocoded.
    """
    cache = _load_cache()
    key = _cache_key(address)
    if key in cache:
        return cache[key]

    result = _nominatim_geocode(address)
    if result is None:
        api_key = os.getenv("ORS_API_KEY", "")
        if api_key and api_key != "your_openrouteservice_key_here":
            result = _ors_geocode(address, api_key)

    if result is None:
        raise ValueError(f"Could not geocode address: {address!r}")

    cache[key] = result
    _save_cache(cache)
    return result


def _nominatim_geocode(address: str) -> dict | None:
    time.sleep(1)  # Nominatim ToS: max 1 req/sec
    try:
        resp = requests.get(
            NOMINATIM_URL,
            params={"q": address, "format": "json", "limit": 1},
            headers=HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        if not data:
            return None
        hit = data[0]
        return {
            "lat": float(hit["lat"]),
            "lon": float(hit["lon"]),
            "display_name": hit.get("display_name", address),
        }
    except Exception:
        return None


def _ors_geocode(address: str, api_key: str) -> dict | None:
    try:
        resp = requests.get(
            ORS_GEOCODE_URL,
            params={"api_key": api_key, "text": address, "size": 1},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        if not features:
            return None
        coords = features[0]["geometry"]["coordinates"]
        props = features[0].get("properties", {})
        return {
            "lat": float(coords[1]),
            "lon": float(coords[0]),
            "display_name": props.get("label", address),
        }
    except Exception:
        return None
