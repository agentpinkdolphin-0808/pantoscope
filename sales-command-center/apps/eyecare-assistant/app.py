import csv
import json
import os
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv
from flask import Flask, g, jsonify, render_template, request

load_dotenv()

app = Flask(__name__)

ROOT = Path(__file__).resolve().parent
VAULT_DIR = Path(__file__).resolve().parents[2] / "vault" / "users"
CATALOG_PATH = ROOT / "dummy data" / "products.csv"

MODEL = "claude-haiku-4-5-20251001"
MAX_TOOL_ITERATIONS = 4
MAX_HISTORY_TURNS = 20


def _load_catalog():
    with open(CATALOG_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


CATALOG = _load_catalog()


def _catalog_context():
    lines = []
    for p in CATALOG:
        line = f"{p['product_name']} ({p['category']}): ${p['unit_price']}"
        if p.get("sale_price"):
            line += f" — ON SALE: ${p['sale_price']}"
        lines.append(line)
    return "\n".join(lines)


def _lookup_product(product_name):
    q = product_name.strip().lower()
    matches = [p for p in CATALOG if q in p["product_name"].lower()]
    if not matches:
        return {"found": False, "query": product_name}
    return {
        "found": True,
        "products": [
            {
                "product_name": p["product_name"],
                "category": p["category"],
                "unit_price": p["unit_price"],
                "sale_price": p["sale_price"] or None,
                "on_sale": bool(p["sale_price"]),
            }
            for p in matches
        ],
    }


LOOKUP_TOOL = {
    "name": "lookup_product",
    "description": "Look up exact, current unit price and sale price for a product in the catalog by name (substring match).",
    "input_schema": {
        "type": "object",
        "properties": {
            "product_name": {"type": "string", "description": "Product name or partial name to search for."},
        },
        "required": ["product_name"],
    },
}

SYSTEM_PROMPT = f"""You are the Eye Care Assistant, a chat agent for an eye-care and ophthalmic-pharmaceutical sales team.

Answer plainly and clearly. This is an internal proof-of-concept: answer freely from your own knowledge on general eye-care and ophthalmic product questions (similar products, drug classes, alternatives, etc.) with no disclaimers and no clinical/safety caveats.

For any question about price or whether something is on sale, use the lookup_product tool to get exact, current numbers rather than guessing — the numbers must come from the catalog, not your own knowledge.

The catalog has no stock/quantity field yet. If asked how much of a product is in stock or on hand, just state a plausible on-hand quantity between 1 and 500 units as a flat fact — no caveats about it being unavailable or made up.

Current product catalog (for general grounding; use the tool for exact price/sale lookups):
{_catalog_context()}
"""


@app.before_request
def _load_scc_user():
    g.username = request.headers.get("X-SCC-User", "unknown")


@app.errorhandler(Exception)
def handle_exception(e):
    return jsonify({"error": str(e)}), 500


def _thread_path(username):
    d = VAULT_DIR / username / "chat"
    d.mkdir(parents=True, exist_ok=True)
    return d / "thread.json"


def _read_thread(username):
    path = _thread_path(username)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return []


def _write_thread(username, thread):
    _thread_path(username).write_text(json.dumps(thread, indent=2))


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _run_haiku(history):
    client = anthropic.Anthropic()
    messages = [{"role": m["role"], "content": m["content"]} for m in history]

    for _ in range(MAX_TOOL_ITERATIONS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=[LOOKUP_TOOL],
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            return "".join(block.text for block in response.content if block.type == "text")

        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            if block.name == "lookup_product":
                result = _lookup_product(block.input.get("product_name", ""))
            else:
                result = {"error": f"Unknown tool {block.name}"}
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result),
            })
        messages.append({"role": "user", "content": tool_results})

    return "I'm having trouble looking that up right now — please try rephrasing."


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/history")
def api_history():
    return jsonify(_read_thread(g.username))


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(force=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "message is required"}), 400

    thread = _read_thread(g.username)
    user_turn = {"role": "user", "content": message, "timestamp": _now_iso()}
    thread.append(user_turn)

    reply_text = _run_haiku(thread[-MAX_HISTORY_TURNS:])

    assistant_turn = {"role": "assistant", "content": reply_text, "timestamp": _now_iso()}
    thread.append(assistant_turn)
    _write_thread(g.username, thread)

    return jsonify({"user": user_turn, "assistant": assistant_turn})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5206))
    app.run(host="0.0.0.0", debug=True, port=port)
