# Overview
The repository hosts a Passenger-served Flask rewrite of the memor.ia.br task-board application. The deployment tree mirrors CooliceHost shared hosting: `public_html/passenger_wsgi.py` exposes the WSGI `application`, the Flask package lives under `public_html/fstore_app/`, templates render the HTML UI from `public_html/fstore_app/templates/`, static assets (CSS, JavaScript, service worker) reside in `public_html/fstore_app/static/`, and persisted boards are JSON files stored in the writable `public_html/fstore_app/data/` directory. The experience preserves the PHP build’s frictionless UX—inline editing, drag-and-drop reordering, undo flows, filters, offline/PWA support—while remaining unauthenticated by design.

# Roles
- **Board Collaborator**: Navigates `/`, manages tasks with keyboard shortcuts, drag-and-drop reorder, filters, and undo, and shares boards via generated URLs. Expects autosave feedback, offline queuing, and fast switching between slugs.
- **Automation Integrator**: Consumes `/api/boards/<slug>` for JSON reads/writes and references `/fs` for curl samples. Relies on stable schema, conditional requests (ETag/Last-Modified), and unauthenticated access for scripts.
- **Hosting Administrator**: Deploys under DirectAdmin’s Python Selector (App Root `public_html/`, Application URL `/`, Startup File `passenger_wsgi.py`), installs `requirements.txt`, registers the service worker assets, and ensures `fstore_app/data/` remains writable and backed up.
- **Repository Maintainer**: Keeps code Passenger-compatible (no `app.run()`), sustains slug safety, maintains static asset parity with the PHP baseline, executes automated tests, and documents behavioral trade-offs (public write surface, offline cache scope).

# Data Flow
1. **HTML Shell**: `GET /` renders `app.html`, embedding the active slug and origin, while linking to `app.css`, `app.js`, `sw.js`, and the manifest/favicons.
2. **Board Fetch**: `GET /api/boards/<slug>` returns the current board JSON with ETag/Last-Modified validators and `no-cache` semantics. Requests honoring the validators receive a `304` to enable stale-while-revalidate in the service worker.
3. **Mutations**: `POST /api/boards/<slug>` accepts `op` values (`add`, `toggle`, `edit`, `del`, `title`, `clear_done`, `set_all`, `clear_all`, `reorder`) mirroring the PHP operations. Payloads update JSON, persist to disk with advisory locks, and return the updated board.
4. **Board Lifecycle**: `GET /boards/new` redirects to a freshly generated slug. `GET /?b=<slug>&add=<text>` supports quick adds before rendering.
5. **Assets & PWA**: `/manifest.json`, `/sw.js`, and `/favicon.svg` reproduce the PHP headers (cache-control, content types). `sw.js` caches shell assets, falls back offline, and caches API reads using stale-while-revalidate.
6. **Automation Reference**: `GET /fs` emits a JSON guide with sample curl invocations for automation scripts.
7. **Persistence & Safety**: Board JSON files live beneath `fstore_app/data/` with slug-based filenames. Slugs are filtered to `[A-Za-z0-9_-]`, truncated to 64 chars, defaulting to `public`. Advisory locks guard concurrent writes.

# Instructions Hierarchy
1. **Repository Documentation**: This spec, the generation policy, and worked examples are authoritative for architecture, UX guarantees, and test expectations.
2. **Approach Artifacts**: Apply first-, second-, then third-approach guidance when documentation is silent or ambiguous.
3. **System/User Prompts**: Obey the most recent explicit instructions when conflicts arise with historical material.

# Constraints
- **Unauthenticated Surface**: No auth middleware, credential stores, or CSRF layers. All routes must remain public.
- **Slug Hygiene**: Sanitize board slugs via `safe_slug`, reject traversal, and keep filenames inside `fstore_app/data/`.
- **Passenger Compatibility**: Export `application` via `passenger_wsgi.py`, avoid `app.run()`, and guarantee `python -c "import passenger_wsgi"` succeeds.
- **UX Parity**: Preserve inline editing, undo timers (10 seconds), drag-and-drop reorder (disabled while filtering/searching), keyboard shortcuts, localStorage filters/search, offline outbox syncing, and PWA caching.
- **Headers & Caching**: Emit `X-Content-Type-Options`, conditional HSTS, `Cache-Control` directives, and validator headers that match the PHP implementation.
- **Dependency Minimalism**: Keep `requirements.txt` limited to `Flask>=2.2,<3.0` unless new functionality mandates additions.
- **Testing**: Maintain automated tests that exercise slug safety, CRUD flows, and conditional requests.

# Examples
- **Typical Session**: A collaborator opens `/`, adds a task, toggles completion with the spacebar, drags items to reorder, and observes undo prompts and updated counts.
- **Automation Script**: A cron job reads `/api/boards/public`, appends tasks via `POST` JSON payloads, and leverages `If-None-Match` to avoid redundant transfers.
- **Offline Recovery**: A user edits tasks while offline; the UI queues changes locally, displays the offline banner, and syncs queued operations when connectivity returns.
