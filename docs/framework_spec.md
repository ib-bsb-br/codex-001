# Overview
The CooliceHost deployment (`ib-bsb-br/codex-001`) now delivers a unified FStore hub: the unauthenticated file drop and the memor.ia.br task boards live inside a single Passenger-hosted Flask app. The layout must mirror production under `public_html/`, exposing `passenger_wsgi.py`, the Flask package (`fstore_app/`), static assets, templates, a writable `data/` tree with `files/` and `boards/`, and a downloadable CLI at `fs_client.py`. All browser and automation entry points are intentionally public, prioritising frictionless collaboration over access controls.

# Roles
- **File Collaborator** – uploads, renames, downloads, deletes, and edits `.note` documents through the Files panel. Drag-and-drop uploads, keyboard confirmation, and contextual actions must remain instant and URL-safe.
- **Board Collaborator** – manages tasks within the Boards panel using keyboard shortcuts (`/`, `j/k`, `Ctrl+↑/↓`, `Space`, `Esc`), undo, search/filter, offline queueing, and drag-and-drop or keyboard reorder.
- **Automation Operator** – consumes `/fs` and `/fs_client.py` for scripted workflows. Must observe `If-Match` + `Idempotency-Key` on board writes and URL encoding on file endpoints.
- **Hosting Administrator** – deploys under DirectAdmin’s Python Selector (App Root `public_html/`, Startup File `passenger_wsgi.py`), keeps `requirements.txt` minimal (Flask only), ensures `fstore_app/data/` is writable, and monitors Passenger/WSGI cold imports.

# Data Flow
1. **Dashboard Rendering** – `GET /` renders `dashboard.html` with both panels. Context includes `board_slug`, `origin`, and initial file listing. Navigation tabs switch panels without a page reload.
2. **File APIs** – `GET /api/files` returns `{name, mod_time, mod_time_str}`. Mutations: `POST /api/files/upload`, `POST /api/files/upload-data`, `POST /api/files/rename`, and `POST /api/files/delete/<name>` (names validated against `..`, `/`, `\`). Downloads stream from `GET /files/<name>`. Notes edit at `GET /files/editor/<name>.note` and autosave via JSON payloads.
3. **Board APIs** – `GET /api/boards/<slug>` honours `If-None-Match` / `If-Modified-Since` headers. `POST /api/boards/<slug>` expects `If-Match` (optimistic concurrency) and `Idempotency-Key` (replay safety). Supported ops: `add`, `toggle`, `edit`, `del`, `title`, `clear_done`, `set_all`, `clear_all`, `reorder`.
4. **Idempotency Store** – processed mutation responses persist under `data/boards/_idempotency/` for seven days, enabling safe retries after network loss.
5. **Sample Content** – `data/boards/sample-board.json` seeds the `public` board on first load. `data/files/` starts empty apart from `.gitkeep`.
6. **Static Assets & SW** – `ASSET_VERSION` hashes `static/` contents; templates append `?v=<version>` to asset URLs, and `sw.js` injects the same token before caching shell resources.
7. **Automation Docs** – `/fs` renders HTML instructions including Bash/dash/Pwsh/cURL/Python samples. `/fs_client.py` rewrites the embedded `TARGET_URL` placeholder before returning the Python CLI source.

# Instructions Hierarchy
1. **Repository Documentation (`docs/`)** – primary reference for architecture, routing contracts, concurrency semantics, keyboard shortcuts, and deployment/testing workflows.
2. **Historical approaches (first/second/third)** – apply only when they extend, not contradict, the documentation; newer instructions supersede older ones.
3. **Runtime directives (README, inline comments)** – clarify operational expectations for maintainers and contributors.
4. **System/User overrides** – always obey the latest user or system-level command when conflicts arise.

# Constraints
- **Authentication-free surface** – no credentials, sessions, or tokens; rely solely on filename sanitisation and idempotency safeguards.
- **Filename safety** – reject traversal (`..`), slash, or backslash before touching the filesystem. `.note` editing restricted to `.note` suffixes.
- **Passenger compatibility** – expose `application` from `passenger_wsgi.py`; never call `app.run()` on import; ensure `python -c "import passenger_wsgi"` succeeds.
- **Data segregation** – maintain `data/files/` and `data/boards/` structure; store idempotency metadata under `data/boards/_idempotency/` with rolling TTL.
- **Dependency minimalism** – `requirements.txt` stays at `Flask>=2.2,<3.0`. Testing and tooling dependencies belong in developer setup notes, not runtime pins.
- **Offline-first semantics** – service worker, optimistic concurrency, and idempotency must cooperate so queued mutations replay safely without data loss or duplication.

# Examples
- **File cycle** – a collaborator drags `proposal.pdf` onto the Files panel → `/api/files/upload` saves and auto-refreshes the table → rename prompts call `/api/files/rename` → delete posts to `/api/files/delete/proposal.pdf`.
- **Board mutation** – client fetches `/api/boards/public`, caches ETag `"abc"`, then posts `{op:'toggle', id:'alpha'}` with `If-Match: "abc"` and a UUID `Idempotency-Key`. Replays with the same key return cached JSON; conflicting ETags yield `409`.
- **Automation** – scripting via curl: `curl -X POST $BASE/api/boards/public -H 'Content-Type: application/json' -H "If-Match: $ETAG" -H "Idempotency-Key: $(uuidgen)" -d '{"op":"add","text":"Task"}'`. Files scripted with `curl -F file=@asset.png $BASE/api/files/upload`.
