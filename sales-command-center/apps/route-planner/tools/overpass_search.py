from __future__ import annotations

import requests

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
HEADERS = {"User-Agent": "RouteDiscoveryDashboard/1.0 (justin.skinner.business@gmail.com)"}

# Each entry: (query_substring, [(tag_key, tag_val, name_regex_filter_or_None), ...])
# name_regex_filter is passed to Overpass ["name"~"...",i] to avoid broad tag pollution
OSM_TAG_MAP = [
    ("ophthalmolog", [
        ("amenity",            "doctors",       "eye|vision|ophthalm|optical|retina|cataract|ocular"),
        ("healthcare:speciality", "ophthalmology", None),
    ]),
    ("optometrist", [
        ("amenity",     "optometrist", None),
        ("healthcare",  "optometrist", None),
    ]),
    ("eye doctor", [
        ("amenity",    "optometrist", None),
        ("amenity",    "doctors",     "eye|vision|ophthalm|optical"),
    ]),
    ("eye care", [
        ("amenity",    "optometrist", None),
        ("amenity",    "doctors",     "eye|vision|ophthalm|optical"),
    ]),
    ("dentist", [
        ("amenity", "dentist", None),
    ]),
    ("dental", [
        ("amenity", "dentist", None),
    ]),
    ("pharmacy", [
        ("amenity", "pharmacy", None),
    ]),
    ("drug store", [
        ("amenity", "pharmacy", None),
    ]),
    ("hospital", [
        ("amenity", "hospital", None),
    ]),
    ("urgent care", [
        ("amenity",    "clinic",  None),
        ("healthcare", "clinic",  None),
    ]),
    ("clinic", [
        ("amenity",    "clinic",  None),
        ("healthcare", "clinic",  None),
    ]),
    ("physical therapy", [
        ("healthcare:speciality", "physiotherapy", None),
        ("amenity", "doctors", "physical therapy|physiotherapy|rehab"),
    ]),
    ("chiropractor", [
        ("healthcare", "chiropractor", None),
        ("amenity",    "doctors",      "chiro"),
    ]),
    ("dermatolog", [
        ("healthcare:speciality", "dermatology", None),
        ("amenity",               "doctors",     "derm|skin"),
    ]),
    ("cardiolog", [
        ("healthcare:speciality", "cardiology", None),
        ("amenity",               "doctors",    "cardio|heart"),
    ]),
    ("orthoped", [
        ("healthcare:speciality", "orthopaedics", None),
        ("amenity",               "doctors",      "ortho|bone|joint|spine|sport"),
    ]),
    ("pediatric", [
        ("healthcare:speciality", "paediatrics", None),
        ("amenity",               "doctors",     "pediatric|paediatric|children|kids"),
    ]),
    ("restaurant", [
        ("amenity", "restaurant", None),
    ]),
    ("gas station", [
        ("amenity", "fuel", None),
    ]),
    ("fuel", [
        ("amenity", "fuel", None),
    ]),
    ("hotel", [
        ("tourism", "hotel", None),
        ("tourism", "motel", None),
    ]),
    ("motel", [
        ("tourism", "motel", None),
    ]),
    ("coffee", [
        ("amenity", "cafe", None),
    ]),
    ("cafe", [
        ("amenity", "cafe", None),
    ]),
    ("grocery", [
        ("shop", "supermarket", None),
        ("shop", "grocery",     None),
    ]),
    ("supermarket", [
        ("shop", "supermarket", None),
    ]),
]

FALLBACK_TAGS = [("amenity", "doctors", None), ("healthcare", "doctor", None)]


def search_overpass(query: str, bbox: list) -> list:
    """
    bbox: [min_lon, min_lat, max_lon, max_lat]  (route bbox, already expanded by caller)
    Returns: [{"name", "lat", "lon", "address", "website", "source"}, ...]
    """
    ov_bbox = f"{bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]}"
    tags = _resolve_tags(query.lower())

    seen_ids = set()
    candidates = []

    for tag_key, tag_val, name_filter in tags:
        results = _run_overpass_query(tag_key, tag_val, ov_bbox, name_filter)
        for r in results:
            node_id = r.get("id")
            if node_id in seen_ids:
                continue
            seen_ids.add(node_id)
            candidate = _parse_element(r)
            if candidate:
                candidates.append(candidate)

    return candidates


def _resolve_tags(query: str) -> list:
    for keyword, tags in OSM_TAG_MAP:
        if keyword in query:
            return tags
    return FALLBACK_TAGS


def _run_overpass_query(tag_key: str, tag_val: str, ov_bbox: str, name_filter: str | None) -> list:
    name_clause = f'["name"~"{name_filter}",i]' if name_filter else '["name"]'
    ql = (
        f'[out:json][timeout:30];'
        f'('
        f'node["{tag_key}"="{tag_val}"]{name_clause}({ov_bbox});'
        f'way["{tag_key}"="{tag_val}"]{name_clause}({ov_bbox});'
        f'relation["{tag_key}"="{tag_val}"]{name_clause}({ov_bbox});'
        f');'
        f'out center;'
    )
    try:
        resp = requests.post(OVERPASS_URL, data={"data": ql}, headers=HEADERS, timeout=40)
        resp.raise_for_status()
        return resp.json().get("elements", [])
    except Exception as e:
        print(f"[overpass] query failed for {tag_key}={tag_val}: {e}")
        return []


def _parse_element(el: dict) -> dict | None:
    tags = el.get("tags", {})
    name = tags.get("name", "").strip()
    if not name:
        return None

    if el["type"] in ("way", "relation"):
        center = el.get("center", {})
        lat = center.get("lat")
        lon = center.get("lon")
    else:
        lat = el.get("lat")
        lon = el.get("lon")

    if lat is None or lon is None:
        return None

    addr_parts = []
    for key in ("addr:housenumber", "addr:street", "addr:city", "addr:state", "addr:postcode"):
        v = tags.get(key, "").strip()
        if v:
            addr_parts.append(v)
    address = ", ".join(addr_parts) if addr_parts else tags.get("addr:city", "")

    website = (
        tags.get("website")
        or tags.get("contact:website")
        or tags.get("url")
        or tags.get("contact:url")
        or None
    )
    if website and not website.startswith("http"):
        website = "https://" + website

    phone = tags.get("phone") or tags.get("contact:phone") or None

    return {
        "name": name,
        "lat": float(lat),
        "lon": float(lon),
        "address": address,
        "website": website,
        "phone": phone,
        "source": "overpass",
    }


def expand_bbox_for_corridor(bbox: list, corridor_miles: float) -> list:
    pad_lat = (corridor_miles * 1.1) / 69.0
    pad_lon = (corridor_miles * 1.1) / 54.6
    return [
        bbox[0] - pad_lon,
        bbox[1] - pad_lat,
        bbox[2] + pad_lon,
        bbox[3] + pad_lat,
    ]
