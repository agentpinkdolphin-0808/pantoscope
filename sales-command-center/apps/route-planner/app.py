import os
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, g, jsonify, render_template, request

load_dotenv()

app = Flask(__name__)

UPLOAD_DIR = Path(".tmp")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {"csv", "xlsx", "xls", "pdf"}


def _ext(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


@app.before_request
def _load_scc_user():
    g.username = request.headers.get("X-SCC-User", "unknown")


@app.errorhandler(Exception)
def handle_exception(e):
    return jsonify({"error": str(e)}), 500


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/api/search", methods=["POST"])
def search():
    start = time.time()

    # --- Parse inputs (supports both JSON and multipart/form-data) ---
    if request.content_type and "multipart/form-data" in request.content_type:
        origin = request.form.get("origin", "").strip()
        destination = request.form.get("destination", "").strip()
        corridor_miles = float(request.form.get("corridor_miles", 10))
        query = request.form.get("query", "").strip()
        keywords_raw = request.form.get("criteria_keywords", "")
        gsheet_url = request.form.get("document_url", "").strip()
        uploaded_file = request.files.get("document_file")
    else:
        data = request.get_json(force=True) or {}
        origin = data.get("origin", "").strip()
        destination = data.get("destination", "").strip()
        corridor_miles = float(data.get("corridor_miles", 10))
        query = data.get("query", "").strip()
        keywords_raw = data.get("criteria_keywords", "")
        gsheet_url = (data.get("document_url") or "").strip()
        uploaded_file = None

    if isinstance(keywords_raw, list):
        keywords = [k.strip() for k in keywords_raw if k.strip()]
    else:
        keywords = [k.strip() for k in keywords_raw.split(",") if k.strip()]

    if not origin or not destination:
        return jsonify({"error": "origin and destination are required"}), 400
    if not query:
        return jsonify({"error": "query is required (e.g. 'ophthalmologists')"}), 400

    api_key = os.getenv("ORS_API_KEY", "")
    if not api_key or api_key == "your_openrouteservice_key_here":
        return jsonify({
            "error": "ORS_API_KEY not set. Get a free key at https://openrouteservice.org and add it to your .env file."
        }), 400

    # --- Imports deferred so startup is fast even if deps missing ---
    from tools.geocode import geocode_address
    from tools.routing import fetch_route_polyline
    from tools.corridor_filter import filter_by_corridor
    from tools.overpass_search import search_overpass, expand_bbox_for_corridor

    try:
        origin_geo = geocode_address(origin)
        dest_geo = geocode_address(destination)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    try:
        route = fetch_route_polyline(
            (origin_geo["lat"], origin_geo["lon"]),
            (dest_geo["lat"], dest_geo["lon"]),
            api_key,
        )
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502

    route_coords = route["coordinates"]

    # --- Candidate discovery ---
    doc_path = None
    doc_type = None
    candidates = []

    if uploaded_file and uploaded_file.filename:
        ext = _ext(uploaded_file.filename)
        if ext not in ALLOWED_EXTENSIONS:
            return jsonify({"error": f"Unsupported file type: .{ext}"}), 400
        doc_path = UPLOAD_DIR / f"upload_{uuid.uuid4().hex}.{ext}"
        uploaded_file.save(str(doc_path))
        doc_type = ext if ext in ("csv", "pdf") else "excel"

    if doc_path or gsheet_url:
        from tools.document_parser import parse_document
        source = gsheet_url if gsheet_url else str(doc_path)
        dtype = "gsheet" if gsheet_url else doc_type
        try:
            raw_entries = parse_document(source, dtype)
        except Exception as e:
            return jsonify({"error": f"Document parse error: {e}"}), 400

        from tools.geocode import geocode_address as geo
        geocoded = []
        for entry in raw_entries:
            addr = entry.get("address", "")
            if not addr:
                continue
            try:
                coords = geo(addr)
                entry["lat"] = coords["lat"]
                entry["lon"] = coords["lon"]
                entry["source"] = "document"
                geocoded.append(entry)
            except ValueError:
                pass  # skip ungeocodable entries
        candidates = geocoded
    else:
        expanded_bbox = expand_bbox_for_corridor(route["bbox"], corridor_miles)
        candidates = search_overpass(query, expanded_bbox)

    # --- Corridor filter ---
    total_candidates = len(candidates)
    filtered = filter_by_corridor(candidates, route_coords, corridor_miles)
    after_filter = len(filtered)

    # --- Website scraping ---
    scrape_attempted = 0
    if keywords:
        from tools.result_builder import enrich_with_scraping
        top_candidates = filtered[:20]  # cap at 20 to stay within time budget
        top_candidates = enrich_with_scraping(top_candidates, keywords)
        scrape_attempted = sum(1 for r in top_candidates if r.get("scraped") is not False)
        # Merge back: top 20 enriched + remainder un-enriched
        filtered = top_candidates + filtered[20:]

    # Clean up uploaded file
    if doc_path and doc_path.exists():
        doc_path.unlink()

    route_geojson = {
        "type": "LineString",
        "coordinates": route_coords,
    }

    return jsonify({
        "route_geojson": route_geojson,
        "bbox": route["bbox"],
        "origin": {"lat": origin_geo["lat"], "lon": origin_geo["lon"], "label": origin_geo["display_name"]},
        "destination": {"lat": dest_geo["lat"], "lon": dest_geo["lon"], "label": dest_geo["display_name"]},
        "results": filtered,
        "meta": {
            "total_candidates": total_candidates,
            "after_corridor_filter": after_filter,
            "scrape_attempted": scrape_attempted,
            "route_distance_km": round(route["distance_km"], 1),
            "duration_seconds": round(time.time() - start, 1),
        },
    })


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5201))
    app.run(host="0.0.0.0", debug=True, port=port)
