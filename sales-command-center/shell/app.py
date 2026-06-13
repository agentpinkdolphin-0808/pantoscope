import os
import json
import re
import sys
from datetime import datetime, date
from pathlib import Path
from functools import wraps
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, jsonify, send_from_directory, abort
)
from flask_session import Session

ROOT = Path(__file__).parent.parent
CONFIG_DIR = ROOT / "config"
AUTH_FILE = ROOT / "auth" / "credentials.md"
VAULT_DIR = ROOT / "vault" / "users"
ENGINE_DIR = ROOT / "engine"

sys.path.insert(0, str(ENGINE_DIR))

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = str(ROOT / ".tmp" / "sessions")
app.config["SESSION_PERMANENT"] = False
app.config["PERMANENT_SESSION_LIFETIME"] = 28800  # 8 hours
Path(app.config["SESSION_FILE_DIR"]).mkdir(parents=True, exist_ok=True)
Session(app)


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def load_credentials():
    creds = {}
    text = AUTH_FILE.read_text()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("|---") or line.startswith("| username"):
            continue
        if line.startswith("|"):
            parts = [p.strip() for p in line.strip("|").split("|")]
            if len(parts) >= 4:
                username, password, role, states = parts[0], parts[1], parts[2], parts[3]
                creds[username] = {"password": password, "role": role, "states": states}
    return creds


def load_user_config(username):
    cfg_file = VAULT_DIR / username / "config.md"
    if not cfg_file.exists():
        return {}
    text = cfg_file.read_text()
    cfg = {}
    in_front = False
    for line in text.splitlines():
        if line.strip() == "---":
            in_front = not in_front
            continue
        if in_front and ":" in line:
            k, v = line.split(":", 1)
            cfg[k.strip()] = v.strip()
    return cfg


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "username" not in session:
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Vault / memory helpers
# ---------------------------------------------------------------------------

def vault_log(username, category, entry):
    log_dir = VAULT_DIR / username / category
    log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H%M%SZ")
    log_file = log_dir / f"{ts}.md"
    content = f"---\ntimestamp: {ts}\ncategory: {category}\n---\n\n{entry}\n"
    log_file.write_text(content)


def vault_read_dream_history(username):
    dream_dir = VAULT_DIR / username / "dreams"
    if not dream_dir.exists():
        return []
    entries = []
    for f in sorted(dream_dir.glob("*.json"), reverse=True)[:12]:
        try:
            data = json.loads(f.read_text())
            entries.append(data)
        except Exception:
            pass
    return entries


def vault_save_dream(username, report):
    dream_dir = VAULT_DIR / username / "dreams"
    dream_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H%M%SZ")
    fname = dream_dir / f"dream-{ts}.json"
    report["saved_at"] = ts
    fname.write_text(json.dumps(report, indent=2))
    # Prune to 12
    all_dreams = sorted(dream_dir.glob("*.json"))
    if len(all_dreams) > 12:
        for old in all_dreams[:-12]:
            old.unlink()


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------

def load_apps_config():
    return json.loads((CONFIG_DIR / "apps.json").read_text())


def load_dream_config():
    return json.loads((CONFIG_DIR / "dream.json").read_text())


def save_apps_config(data):
    (CONFIG_DIR / "apps.json").write_text(json.dumps(data, indent=2))


def save_dream_config(data):
    (CONFIG_DIR / "dream.json").write_text(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# Routes: Auth
# ---------------------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")
        creds = load_credentials()
        if username in creds and creds[username]["password"] == password:
            user_cfg = load_user_config(username)
            session["username"] = username
            session["display_name"] = user_cfg.get("display_name", username)
            session["role"] = user_cfg.get("role", creds[username]["role"])
            session["states"] = user_cfg.get("states_covered", creds[username]["states"])
            session["avatar_initials"] = user_cfg.get("avatar_initials", username[:2].upper())
            vault_log(username, "activity", f"Login at {datetime.utcnow().isoformat()}")
            next_page = request.form.get("next") or url_for("home")
            return redirect(next_page)
        error = "Invalid username or password."
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    username = session.get("username")
    if username:
        vault_log(username, "activity", f"Logout at {datetime.utcnow().isoformat()}")
    session.clear()
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Routes: Shell
# ---------------------------------------------------------------------------

@app.route("/")
@login_required
def home():
    apps_cfg = load_apps_config()
    user = {
        "username": session["username"],
        "display_name": session["display_name"],
        "role": session["role"],
        "avatar_initials": session["avatar_initials"],
    }
    return render_template("shell.html", user=user, apps_config=apps_cfg)


# ---------------------------------------------------------------------------
# Routes: API
# ---------------------------------------------------------------------------

@app.route("/api/config/apps")
@login_required
def api_apps_config():
    return jsonify(load_apps_config())


@app.route("/api/config/apps", methods=["POST"])
@login_required
def api_apps_config_save():
    data = request.get_json()
    save_apps_config(data)
    return jsonify({"ok": True})


@app.route("/api/config/dream")
@login_required
def api_dream_config():
    return jsonify(load_dream_config())


@app.route("/api/config/dream", methods=["POST"])
@login_required
def api_dream_config_save():
    data = request.get_json()
    save_dream_config(data)
    return jsonify({"ok": True})


@app.route("/api/dream/run", methods=["POST"])
@login_required
def api_dream_run():
    from dream import run_dream
    username = session["username"]
    role = session["role"]
    states = session["states"]
    cfg = load_dream_config()
    try:
        report = run_dream(username, role, states, cfg)
        vault_save_dream(username, report)
        vault_log(username, "api_credits", f"Dream run: {report.get('tokens_used', 0)} tokens")
        return jsonify({"ok": True, "report": report})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/dream/history")
@login_required
def api_dream_history():
    username = session["username"]
    history = vault_read_dream_history(username)
    return jsonify(history)


@app.route("/api/activity/log", methods=["POST"])
@login_required
def api_activity_log():
    username = session["username"]
    data = request.get_json()
    event_type = data.get("type", "interaction")
    detail = data.get("detail", "")
    vault_log(username, "activity", f"{event_type}: {detail}")
    return jsonify({"ok": True})


@app.route("/api/user")
@login_required
def api_user():
    return jsonify({
        "username": session["username"],
        "display_name": session["display_name"],
        "role": session["role"],
        "states": session["states"],
        "avatar_initials": session["avatar_initials"],
    })


# ---------------------------------------------------------------------------
# Static assets
# ---------------------------------------------------------------------------

@app.route("/static/icons/<path:filename>")
def serve_icon(filename):
    return send_from_directory(ROOT / "shell" / "static" / "icons", filename)


@app.route("/static/heroes/<path:filename>")
def serve_hero(filename):
    return send_from_directory(ROOT / "heroes", filename)


# ---------------------------------------------------------------------------
# App proxy passthrough (dev: redirect; prod: nginx handles)
# ---------------------------------------------------------------------------

@app.route("/apps/<app_name>/")
@app.route("/apps/<app_name>/<path:rest>")
@login_required
def app_passthrough(app_name, rest=""):
    # In dev mode without nginx, serve a placeholder page
    apps_cfg = load_apps_config()
    all_apps = []
    for section in apps_cfg.get("sections", []):
        all_apps.extend(section.get("apps", []))
    app_info = next((a for a in all_apps if a["path"] == app_name), None)
    if not app_info:
        abort(404)
    return render_template("app_placeholder.html", app=app_info, user={
        "username": session["username"],
        "display_name": session["display_name"],
        "role": session["role"],
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
