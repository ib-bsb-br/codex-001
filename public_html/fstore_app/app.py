import datetime as dt
import fcntl
import hashlib
import json
import os
import secrets
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from flask import (
    Flask,
    Response,
    abort,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)

APP_ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = APP_ROOT / "data"
STATIC_DIR = APP_ROOT / "static"
TEMPLATE_DIR = APP_ROOT / "templates"

os.makedirs(DEFAULT_DATA_DIR, exist_ok=True)

app = Flask(__name__, template_folder=str(TEMPLATE_DIR), static_folder=str(STATIC_DIR))
app.json.ensure_ascii = False
app.config.setdefault("DATA_DIR", str(DEFAULT_DATA_DIR))
app.config.setdefault("MAX_CONTENT_LENGTH", 512 * 1024 * 1024)  # 512 MiB uploads

MAX_TEXT_LEN = 2000
MAX_TITLE_LEN = 200
DEFAULT_TITLE = "My Todo"
RECENT_HISTORY_LIMIT = 10
IDEMPOTENCY_TTL = 7 * 24 * 3600


def compute_asset_version() -> str:
    digest = hashlib.sha256()
    if STATIC_DIR.exists():
        for path in sorted(STATIC_DIR.rglob("*")):
            if path.is_file():
                try:
                    digest.update(path.name.encode("utf-8"))
                    with path.open("rb") as handle:
                        digest.update(handle.read())
                except OSError:
                    continue
    return digest.hexdigest()[:16] or str(int(time.time()))


app.config.setdefault("ASSET_VERSION", compute_asset_version())


@app.context_processor
def inject_globals() -> Dict[str, Any]:
    return {"asset_version": app.config["ASSET_VERSION"]}


@app.before_request
def apply_security_headers() -> None:
    request.environ.setdefault("wsgi.url_scheme", request.headers.get("X-Forwarded-Proto", request.scheme))


@app.after_request
def finalize_headers(response: Response) -> Response:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    if request.is_secure or request.headers.get("X-Forwarded-Proto") == "https":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


def data_dir() -> Path:
    directory = Path(app.config.get("DATA_DIR", DEFAULT_DATA_DIR))
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def files_dir() -> Path:
    directory = data_dir() / "files"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def boards_dir() -> Path:
    directory = data_dir() / "boards"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def idempotency_dir() -> Path:
    directory = boards_dir() / "_idempotency"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


class IdempotencyStore:
    def __init__(self, base: Path):
        self.base = base

    def _file_for(self, slug: str) -> Path:
        safe = safe_slug(slug)
        return self.base / f"{safe}.json"

    def _load(self, slug: str) -> Dict[str, Any]:
        path = self._file_for(slug)
        if not path.exists():
            return {}
        try:
            with path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            return {}

    def _save(self, slug: str, data: Dict[str, Any]) -> None:
        path = self._file_for(slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)

    def get(self, slug: str, key: str) -> Optional[Dict[str, Any]]:
        data = self._load(slug)
        record = data.get(key)
        if not record:
            return None
        if time.time() - record.get("ts", 0) > IDEMPOTENCY_TTL:
            data.pop(key, None)
            self._save(slug, data)
            return None
        return record

    def put(self, slug: str, key: str, board: Dict[str, Any], etag: str) -> None:
        data = self._load(slug)
        snapshot = json.loads(json.dumps(board, ensure_ascii=False))
        data[key] = {"ts": time.time(), "etag": etag, "board": snapshot}
        self._save(slug, data)


def safe_slug(candidate: str) -> str:
    clean = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in candidate)
    clean = clean[:64]
    return clean or "public"


def safe_name(name: str) -> Optional[str]:
    if not name or any(part in name for part in ("..", "/", "\\")):
        return None
    return name


def utc_timestamp() -> int:
    return int(dt.datetime.now(dt.timezone.utc).timestamp())


def _generate_id() -> str:
    return secrets.token_urlsafe(12)


def _board_path(slug: str) -> Path:
    return boards_dir() / f"{slug}.json"


def _load_sample_board(slug: str) -> Optional[Dict[str, Any]]:
    sample = boards_dir() / "sample-board.json"
    if not sample.exists():
        bundled = APP_ROOT / "data" / "boards" / "sample-board.json"
        if bundled.exists():
            sample.parent.mkdir(parents=True, exist_ok=True)
            sample.write_text(bundled.read_text(encoding="utf-8"), encoding="utf-8")
    if slug == "public" and sample.exists():
        try:
            with sample.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except (OSError, json.JSONDecodeError):
            return None
    return None


def _empty_board() -> Dict[str, Any]:
    now = utc_timestamp()
    return {"title": DEFAULT_TITLE, "tasks": [], "created": now, "updated": now}


def load_board(slug: str) -> Dict[str, Any]:
    path = _board_path(slug)
    if not path.exists():
        sample = _load_sample_board(slug)
        if sample is not None:
            save_board(slug, sample)
            return sample
        return _empty_board()
    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = handle.read().strip()
    except OSError:
        return _empty_board()
    if not raw:
        return _empty_board()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _empty_board()
    return data if isinstance(data, dict) else _empty_board()


def save_board(slug: str, board: Dict[str, Any]) -> None:
    path = _board_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    board["updated"] = utc_timestamp()
    with path.open("w", encoding="utf-8") as handle:
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
    if path.exists():
        timestamp = int(path.stat().st_mtime)
    if not timestamp:
        timestamp = utc_timestamp()
    return dt.datetime.fromtimestamp(timestamp, dt.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")


def current_origin() -> str:
    scheme = request.headers.get("X-Forwarded-Proto") or ("https" if request.is_secure else request.scheme)
    return f"{scheme}://{request.host}"


def _list_files() -> List[Dict[str, Any]]:
    listing: List[Dict[str, Any]] = []
    for entry in sorted(files_dir().iterdir()):
        if entry.is_file():
            stat = entry.stat()
            listing.append(
                {
                    "name": entry.name,
                    "mod_time": stat.st_mtime,
                    "mod_time_str": dt.datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                }
            )
    listing.sort(key=lambda item: item["mod_time"], reverse=True)
    return listing


def _unique_filename(name: str) -> str:
    base, ext = os.path.splitext(name)
    candidate = name
    counter = 1
    while (files_dir() / candidate).exists():
        candidate = f"{base} ({counter}){ext}"
        counter += 1
    return candidate


def _read_note(name: str) -> str:
    try:
        with (files_dir() / name).open("r", encoding="utf-8") as handle:
            return handle.read()
    except OSError:
        return ""


def _write_note(name: str, content: str) -> None:
    path = files_dir() / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(content)
    os.chmod(path, 0o644)


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
    sw_path = STATIC_DIR / "sw.js"
    if not sw_path.exists():
        abort(404)
    content = sw_path.read_text(encoding="utf-8").replace("__APP_VERSION__", app.config["ASSET_VERSION"])
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


@app.route("/")
def dashboard() -> Response:
    slug_raw = request.args.get("b", "public")
    slug = safe_slug(slug_raw)
    quick_add = request.args.get("add")
    if quick_add:
        text = quick_add.strip()[:MAX_TEXT_LEN]
        if text:
            board = load_board(slug)
            board.setdefault("tasks", []).append(
                {"id": _generate_id(), "text": text, "done": False, "ts": utc_timestamp()}
            )
            save_board(slug, board)
        return redirect(url_for("dashboard", b=slug), code=303)

    context = {
        "board_slug": slug,
        "origin": current_origin(),
        "files": _list_files(),
    }
    response = render_template("dashboard.html", **context)
    final = Response(response)
    final.headers["Cache-Control"] = "no-cache"
    return final


@app.route("/files/<path:filename>")
def download_file(filename: str) -> Response:
    safe = safe_name(filename)
    if not safe:
        abort(400)
    path = files_dir() / safe
    if not path.exists():
        abort(404)
    return send_from_directory(str(files_dir()), safe, as_attachment=False)


@app.route("/files/editor/<path:filename>")
def edit_note(filename: str) -> Response:
    safe = safe_name(filename)
    if not safe or not safe.endswith(".note"):
        abort(403)
    content = _read_note(safe)
    context = {"filename": safe, "content": content, "origin": current_origin()}
    response = render_template("note.html", **context)
    final = Response(response)
    final.headers["Cache-Control"] = "no-cache"
    return final


@app.route("/api/files", methods=["GET"])
def api_files_list() -> Response:
    payload = jsonify(_list_files())
    payload.headers["Cache-Control"] = "no-cache"
    return payload


@app.route("/api/files/upload", methods=["POST"])
def api_files_upload() -> Response:
    if "file" not in request.files:
        return jsonify({"error": "missing file"}), 400
    file = request.files["file"]
    filename = safe_name(file.filename or "")
    if not filename:
        return jsonify({"error": "invalid filename"}), 400
    unique = _unique_filename(filename)
    target = files_dir() / unique
    file.save(str(target))
    os.chmod(target, 0o644)
    return jsonify({"name": unique, "status": "success"})


@app.route("/api/files/upload-data", methods=["POST"])
def api_files_upload_data() -> Response:
    data = request.get_json(silent=True) or {}
    filename = safe_name(data.get("filename", ""))
    content = data.get("content", "")
    if not filename:
        return jsonify({"error": "invalid filename"}), 400
    _write_note(filename, content)
    return jsonify({"status": "success", "filename": filename})


@app.route("/api/files/rename", methods=["POST"])
def api_files_rename() -> Response:
    data = request.get_json(silent=True) or {}
    old_name = safe_name(data.get("old_name", ""))
    new_name = safe_name(data.get("new_name", ""))
    if not old_name or not new_name:
        return jsonify({"error": "invalid filename"}), 400
    src = files_dir() / old_name
    dst = files_dir() / new_name
    if not src.exists():
        return jsonify({"error": "not found"}), 404
    if dst.exists():
        return jsonify({"error": "target exists"}), 409
    src.rename(dst)
    return jsonify({"status": "success", "name": new_name})


@app.route("/api/files/delete/<path:filename>", methods=["POST"])
def api_files_delete(filename: str) -> Response:
    safe = safe_name(filename)
    if not safe:
        return jsonify({"error": "invalid filename"}), 400
    path = files_dir() / safe
    if not path.exists():
        return jsonify({"error": "not found"}), 404
    path.unlink()
    return jsonify({"status": "success"})


def _require_if_match(slug: str, current_etag: str) -> Optional[Response]:
    if_match = request.headers.get("If-Match")
    if not if_match:
        return jsonify({"error": "missing If-Match"}), 428
    if if_match != current_etag:
        return jsonify({"error": "conflict", "etag": current_etag}), 409
    return None


def _require_idempotency(store: IdempotencyStore, slug: str, board: Dict[str, Any], etag: str) -> Tuple[str, Optional[Response]]:
    key = request.headers.get("Idempotency-Key")
    if not key:
        raise ValueError("missing idempotency key")
    record = store.get(slug, key)
    if record and record.get("etag") == etag:
        stored_board = record.get("board") or board
        response = jsonify(stored_board)
        response.headers["ETag"] = record.get("etag", etag)
        response.headers["Last-Modified"] = board_last_modified(slug, stored_board)
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return key, response
    return key, None


@app.route("/api/boards/<slug>", methods=["GET", "POST"])
def board_api(slug: str) -> Response:
    safe = safe_slug(slug)
    board = load_board(safe)
    etag = board_etag(board)
    last_modified = board_last_modified(safe, board)

    if request.method == "GET":
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

    header_check = _require_if_match(safe, etag)
    if header_check is not None:
        return header_check

    store = IdempotencyStore(idempotency_dir())

    try:
        key, cached = _require_idempotency(store, safe, board, etag)
    except ValueError:
        return jsonify({"error": "missing Idempotency-Key"}), 428
    if cached is not None:
        return cached

    data = request.get_json(silent=True) or {}
    op = data.get("op")
    board.setdefault("tasks", [])

    def find_task(task_id: str) -> Optional[Dict[str, Any]]:
        for task in board["tasks"]:
            if task.get("id") == task_id:
                return task
        return None

    mutated = False

    if op == "add":
        text = (data.get("text") or "").strip()[:MAX_TEXT_LEN]
        if text:
            board["tasks"].append(
                {"id": _generate_id(), "text": text, "done": False, "ts": utc_timestamp()}
            )
            mutated = True
    elif op == "toggle":
        task = find_task(data.get("id", ""))
        if task is not None:
            task["done"] = not task.get("done", False)
            mutated = True
    elif op == "edit":
        task = find_task(data.get("id", ""))
        if task is not None:
            task["text"] = (data.get("text") or "").strip()[:MAX_TEXT_LEN]
            mutated = True
    elif op == "del":
        original = len(board["tasks"])
        board["tasks"] = [t for t in board["tasks"] if t.get("id") != data.get("id")]
        mutated = len(board["tasks"]) != original
    elif op == "title":
        title = (data.get("title") or "").strip()[:MAX_TITLE_LEN]
        board["title"] = title or DEFAULT_TITLE
        mutated = True
    elif op == "clear_done":
        new_tasks = [t for t in board["tasks"] if not t.get("done")]
        mutated = len(new_tasks) != len(board["tasks"])
        board["tasks"] = new_tasks
    elif op == "set_all":
        done = bool(data.get("done"))
        for task in board["tasks"]:
            task["done"] = done
        mutated = True
    elif op == "clear_all":
        if board["tasks"]:
            board["tasks"] = []
            mutated = True
    elif op == "reorder":
        order = data.get("order") or []
        if isinstance(order, list):
            positions = {str(task_id): idx for idx, task_id in enumerate(order)}
            board["tasks"].sort(key=lambda item: positions.get(str(item.get("id")), len(board["tasks"])))
            mutated = True
    else:
        return jsonify({"error": "unknown op"}), 400

    if mutated:
        save_board(safe, board)
        board = load_board(safe)
        etag = board_etag(board)
        store.put(safe, key, board, etag)

    payload = jsonify(board)
    payload.headers["ETag"] = etag
    payload.headers["Last-Modified"] = board_last_modified(safe, board)
    payload.headers["Cache-Control"] = "no-cache, must-revalidate"
    return payload


@app.route("/boards/new")
def new_board() -> Response:
    slug = safe_slug(_generate_id())
    return redirect(url_for("dashboard", b=slug))


@app.route("/fs")
def api_reference() -> Response:
    base = current_origin()
    files_examples = {
        "list": f"curl -s {base}/api/files | jq",
        "upload": (
            "curl -s -X POST "
            f"{base}/api/files/upload -F file=@example.txt"
        ),
        "rename": (
            f"curl -s -X POST {base}/api/files/rename "
            "-H 'Content-Type: application/json' "
            "-d '{\"old_name\":\"example.txt\",\"new_name\":\"renamed.txt\"}'"
        ),
        "delete": f"curl -s -X POST {base}/api/files/delete/example.txt",
        "python_put": (
            "python - <<'PY'\n"
            "import requests\n"
            f"files = {{'file': ('example.txt', open('example.txt','rb'))}}\n"
            f"print(requests.post('{base}/api/files/upload', files=files).json())\n"
            "PY\n"
        ),
    }

    public_board = load_board("public")
    public_etag = board_etag(public_board)
    board_payload = json.dumps({"op": "add", "text": "Buy milk"}, ensure_ascii=False)
    board_examples = {
        "fetch": f"curl -s {base}/api/boards/public",
        "add": (
            "curl -s -X POST "
            f"{base}/api/boards/public "
            "-H 'Content-Type: application/json' "
            f"-H 'If-Match: {public_etag}' "
            "-H 'Idempotency-Key: demo-add' "
            f"-d '{board_payload}'"
        ),
        "python_add": (
            "python - <<'PY'\n"
            "import json, uuid, requests\n"
            f"base = '{base}'\n"
            f"headers = {{'Content-Type': 'application/json', 'If-Match': '{public_etag}', 'Idempotency-Key': str(uuid.uuid4())}}\n"
            "payload = {'op': 'toggle', 'id': 'alpha'}\n"
            "resp = requests.post(f'{base}/api/boards/public', headers=headers, data=json.dumps(payload))\n"
            "print(resp.json())\n"
            "PY\n"
        ),
    }
    context = {
        "base": base,
        "files_examples": files_examples,
        "board_examples": board_examples,
        "public_etag": public_etag,
    }
    html = render_template("fs.html", **context)
    response = Response(html, mimetype="text/html")
    response.headers["Cache-Control"] = "no-cache"
    return response


@app.route("/fs_client.py")
def fs_client_source() -> Response:
    client_path = APP_ROOT.parent / "fs_client.py"
    if not client_path.exists():
        abort(404)
    body = client_path.read_text(encoding="utf-8")
    base = current_origin().rstrip("/")
    body = body.replace('TARGET_URL = "http://127.0.0.1:5000"', f'TARGET_URL = "{base}"')
    response = Response(body, mimetype="text/x-python")
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Content-Disposition"] = "attachment; filename=fs_client.py"
    return response


if __name__ == "__main__":
    app.run(debug=True)
