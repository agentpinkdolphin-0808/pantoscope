import json
import os
from datetime import date
from pathlib import Path

import requests

ORS_URL = "https://api.openrouteservice.org/v2/directions/driving-car/geojson"
USAGE_PATH = Path(__file__).parent.parent / ".tmp" / "ors_usage.json"


def fetch_route_polyline(
    origin_coords: tuple,   # (lat, lon)
    dest_coords: tuple,     # (lat, lon)
    api_key: str,
) -> dict:
    """
    Returns {
        "coordinates": [[lon, lat], ...],
        "bbox": [min_lon, min_lat, max_lon, max_lat],
        "distance_km": float,
        "duration_seconds": float,
    }
    """
    body = {
        "coordinates": [
            [origin_coords[1], origin_coords[0]],
            [dest_coords[1], dest_coords[0]],
        ]
    }
    headers = {
        "Authorization": api_key,
        "Content-Type": "application/json",
    }
    resp = requests.post(ORS_URL, json=body, headers=headers, timeout=30)

    if resp.status_code == 403:
        raise RuntimeError("ORS API key invalid or quota exceeded. Get a free key at openrouteservice.org.")
    if resp.status_code != 200:
        raise RuntimeError(f"ORS routing error {resp.status_code}: {resp.text[:300]}")

    _log_usage()

    data = resp.json()
    feature = data["features"][0]
    coords = feature["geometry"]["coordinates"]  # [[lon, lat], ...]
    props = feature["properties"]["summary"]

    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]

    return {
        "coordinates": coords,
        "bbox": [min(lons), min(lats), max(lons), max(lats)],
        "distance_km": props.get("distance", 0) / 1000,
        "duration_seconds": props.get("duration", 0),
    }


def _log_usage() -> None:
    USAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    today = str(date.today())
    usage = {}
    if USAGE_PATH.exists():
        with open(USAGE_PATH) as f:
            usage = json.load(f)
    usage[today] = usage.get(today, 0) + 1
    with open(USAGE_PATH, "w") as f:
        json.dump(usage, f, indent=2)
