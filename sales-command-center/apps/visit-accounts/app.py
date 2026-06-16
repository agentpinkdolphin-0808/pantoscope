import os
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request

ENGINE_DIR = Path(__file__).parent.parent.parent / "engine"
sys.path.insert(0, str(ENGINE_DIR))

import data as D  # noqa: E402

app = Flask(__name__)


@app.route("/")
def index():
    username = request.headers.get("X-SCC-User", "unknown")
    return render_template("index.html", username=username)


@app.route("/api/practices")
def api_practices():
    return jsonify([D.practice_detail(p["practice_id"]) for p in D.get_practices()])


@app.route("/api/practices/<practice_id>")
def api_practice_detail(practice_id):
    detail = D.practice_detail(practice_id)
    if detail is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(detail)


@app.route("/healthz")
def healthz():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5202))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
