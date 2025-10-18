import datetime as dt
import fcntl
import hashlib
import json
import os
import secrets
from typing import Any, Dict

from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

APP_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DATA_DIR = os.path.join(APP_ROOT, "data")
STATIC_DIR = os.path.join(APP_ROOT, "static")
TEMPLATE_DIR = os.path.join(APP_ROOT, "templates")

os.makedirs(DEFAULT_DATA_DIR, exist_ok=True)

app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.json.ensure_ascii = False

MAX_TEXT_LEN = 2000
MAX_TITLE_LEN = 200
DEFAULT_TITLE = "My Todo"
RECENT_HISTORY_LIMIT = 10


@app.before_request
def apply_security_headers() -> None:
    """Apply headers required for every response."""
    request.environ.setdefault("wsgi.url_scheme", "http")


@app.after_request
def finalize_headers(response: Response) -> Response:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    if request.is_secure or request.headers.get("X-Forwarded-Proto") == "https":
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
    return response


def data_dir() -> str:
    directory = app.config.get("DATA_DIR", DEFAULT_DATA_DIR)
    os.makedirs(directory, exist_ok=True)
    return directory


def _board_path(slug: str) -> str:
    return os.path.join(data_dir(), f"{slug}.json")


def _generate_id() -> str:
    return secrets.token_urlsafe(8)


def safe_slug(candidate: str) -> str:
    clean = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in candidate)
    clean = clean[:64]
    return clean or "public"


def utc_timestamp() -> int:
    return int(dt.datetime.now(dt.timezone.utc).timestamp())


def _empty_board() -> Dict[str, Any]:
    now = utc_timestamp()
    return {"title": DEFAULT_TITLE, "tasks": [], "created": now, "updated": now}


def load_board(slug: str) -> Dict[str, Any]:
    path = _board_path(slug)
    if not os.path.isfile(path):
        return _empty_board()
    with open(path, "r", encoding="utf-8") as handle:
        raw = handle.read().strip()
    if not raw:
        return _empty_board()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _empty_board()
    return data if isinstance(data, dict) else _empty_board()


def save_board(slug: str, board: Dict[str, Any]) -> None:
    path = _board_path(slug)
    board["updated"] = utc_timestamp()
    with open(path, "w", encoding="utf-8") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX)
            json.dump(board, handle, ensure_ascii=False, indent=2)
            handle.flush()
        finally:
            try:
                fcntl.flock(handle, fcntl.LOCK_UN)
            except OSError:
                pass
    os.chmod(path, 0o644)


def board_etag(board: Dict[str, Any]) -> str:
    payload = json.dumps(board, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return '"' + hashlib.md5(payload).hexdigest() + '"'


def board_last_modified(slug: str, board: Dict[str, Any]) -> str:
    path = _board_path(slug)
    timestamp = board.get("updated")
    if os.path.exists(path):
        timestamp = int(os.path.getmtime(path))
    if not timestamp:
        timestamp = utc_timestamp()
    return dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")


def current_origin() -> str:
    scheme = "https" if request.is_secure else request.headers.get(
        "X-Forwarded-Proto", request.scheme
    )
    return f"{scheme}://{request.host}"


@app.route("/manifest.json")
def web_manifest() -> Response:
    origin = current_origin()
    payload = {
        "name": "memor.ia.br — Todos",
        "short_name": "memor",
        "start_url": "/?b=public",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#111111",
        "icons": [
            {
                "src": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII=",
                "sizes": "192x192",
                "type": "image/png",
            },
            {
                "src": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGNgYAAAAAMAAWgmWQ0AAAAASUVORK5CYII=",
                "sizes": "512x512",
                "type": "image/png",
            },
            {
                "src": f"{origin}/favicon.svg",
                "sizes": "any",
                "type": "image/svg+xml",
                "purpose": "any maskable",
            },
        ],
        "scope": "/",
    }
    response = jsonify(payload)
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@app.route("/sw.js")
def service_worker() -> Response:
    sw_path = os.path.join(STATIC_DIR, "sw.js")
    if not os.path.exists(sw_path):
        abort(404)
    with open(sw_path, "r", encoding="utf-8") as handle:
        content = handle.read()
    response = Response(content, mimetype="application/javascript")
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response


@app.route("/favicon.svg")
def favicon() -> Response:
    payload = (
        "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 64 64\">"
        "<rect fill=\"#111\" width=\"64\" height=\"64\" rx=\"12\"/>"
        "<path d=\"M48 20L27 41l-11-9\" stroke=\"#fff\" stroke-width=\"6\" "
        "stroke-linecap=\"round\" stroke-linejoin=\"round\" fill=\"none\"/></svg>"
    )
    response = Response(payload, mimetype="image/svg+xml")
    response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@app.route("/boards/new")
def new_board() -> Response:
    slug = safe_slug(_generate_id())
    return redirect(url_for("index", b=slug))


@app.route("/")
def index() -> Response:
    slug_raw = request.args.get("b", "public")
    slug = safe_slug(slug_raw)
    quick_add = request.args.get("add")
    if quick_add:
        text = quick_add.strip()
        if text:
            text = text[:MAX_TEXT_LEN]
            board = load_board(slug)
            board.setdefault("tasks", []).append(
                {"id": _generate_id(), "text": text, "done": False, "ts": utc_timestamp()}
            )
            save_board(slug, board)
        return redirect(url_for("index", b=slug), code=303)

    context = {
        "board_slug": slug,
        "origin": current_origin(),
    }
    response = render_template("app.html", **context)
    final = Response(response)
    final.headers["Cache-Control"] = "no-cache"
    return final


@app.route("/api/boards/<slug>", methods=["GET", "POST"])
def board_api(slug: str) -> Response:
    safe = safe_slug(slug)
    board = load_board(safe)

    if request.method == "GET":
        etag = board_etag(board)
        last_modified = board_last_modified(safe, board)
        inm = request.headers.get("If-None-Match")
        ims = request.headers.get("If-Modified-Since")
        if inm == etag or ims == last_modified:
            response = Response(status=304)
            response.headers["ETag"] = etag
            response.headers["Last-Modified"] = last_modified
            return response
        payload = jsonify(board)
        payload.headers["ETag"] = etag
        payload.headers["Last-Modified"] = last_modified
        payload.headers["Cache-Control"] = "no-cache, must-revalidate"
        return payload

    data = request.get_json(silent=True) or {}
    op = data.get("op")
    board.setdefault("tasks", [])

    def find_task(task_id: str) -> Dict[str, Any]:
        for task in board["tasks"]:
            if task.get("id") == task_id:
                return task
        return {}

    if op == "add":
        text = (data.get("text") or "").strip()[:MAX_TEXT_LEN]
        if text:
            board["tasks"].append(
                {
                    "id": _generate_id(),
                    "text": text,
                    "done": False,
                    "ts": utc_timestamp(),
                }
            )
            save_board(safe, board)
        return jsonify(board)

    if op == "toggle":
        task = find_task(data.get("id", ""))
        if task:
            task["done"] = not task.get("done", False)
            save_board(safe, board)
        return jsonify(board)

    if op == "edit":
        task = find_task(data.get("id", ""))
        if task is not None:
            task["text"] = (data.get("text") or "").strip()[:MAX_TEXT_LEN]
            save_board(safe, board)
        return jsonify(board)

    if op == "del":
        task_id = data.get("id")
        board["tasks"] = [t for t in board["tasks"] if t.get("id") != task_id]
        save_board(safe, board)
        return jsonify(board)

    if op == "title":
        title = (data.get("title") or "").strip()[:MAX_TITLE_LEN]
        board["title"] = title or DEFAULT_TITLE
        save_board(safe, board)
        return jsonify(board)

    if op == "clear_done":
        board["tasks"] = [t for t in board["tasks"] if not t.get("done")]
        save_board(safe, board)
        return jsonify(board)

    if op == "set_all":
        done = bool(data.get("done"))
        for task in board["tasks"]:
            task["done"] = done
        save_board(safe, board)
        return jsonify(board)

    if op == "clear_all":
        board["tasks"] = []
        save_board(safe, board)
        return jsonify(board)

    if op == "reorder":
        order = data.get("order") or []
        positions = {str(task_id): idx for idx, task_id in enumerate(order)}
        board["tasks"].sort(key=lambda item: positions.get(str(item.get("id")), len(board["tasks"])))
        save_board(safe, board)
        return jsonify(board)

    return jsonify({"error": "unknown op"}), 400


@app.route("/fs")
def api_reference() -> Response:
    base = current_origin()
    add_example = json.dumps({"op": "add", "text": "Buy milk"}, ensure_ascii=False)
    toggle_example = json.dumps({"op": "toggle", "id": "TASK_ID"}, ensure_ascii=False)
    payload = {
        "overview": "Task board automation endpoints",
        "base_url": base,
        "examples": {
            "fetch": f"curl -s {base}/api/boards/public",
            "add": f"curl -X POST {base}/api/boards/public -H 'Content-Type: application/json' -d '{add_example}'",
            "toggle": f"curl -X POST {base}/api/boards/public -H 'Content-Type: application/json' -d '{toggle_example}'",
            "new": f"curl -I {base}/boards/new",
        },
    }
    response = jsonify(payload)
    response.headers["Cache-Control"] = "no-cache"
    return response


if __name__ == "__main__":
    app.run(debug=True)
