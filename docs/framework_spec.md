# Overview
FStore is a minimalist Flask application deployed under Passenger at the domain root of a CooliceHost shared-hosting environment. The `ib-bsb-br/codex-001` repository must mirror the deployment tree: `public_html/passenger_wsgi.py` exposes the WSGI `application`, the Flask code lives in `public_html/fstore_app/app.py`, HTML templates are stored under `public_html/fstore_app/templates/`, static assets under `public_html/fstore_app/static/`, persisted uploads in the writable `public_html/fstore_app/data/` directory, and the redistributable CLI client at `public_html/fs_client.py`. All browser and CLI interactions are intentionally unauthenticated while preserving drag-and-drop uploads, inline `.note` editing with autosave, and CLI parity.

# Roles
- **Browser Collaborator**: Uses the overview dashboard for uploads, downloads, context-menu rename/delete, and launches inline `.note` editing. Relies on responsive status indicators and unique filename de-duplication.
- **CLI Operator**: Downloads `/fs` to obtain `fs_client.py`, performs file CRUD commands (`ls`, `cat`, `get`, `put`, `edit`, `mv`, `rm`), honours overwrite prompts, streams large payloads, and respects the `EDITOR` environment variable.
- **Hosting Administrator**: Configures DirectAdmin’s Python Selector (App Root `public_html/`, Startup File `passenger_wsgi.py`), installs dependencies from `requirements.txt`, ensures HTTPS termination, and keeps `fstore_app/data/` writable within CloudLinux limits.
- **Repository Maintainer**: Aligns code structure with Passenger expectations, keeps dependencies minimal, validates cold imports (`python -c "import passenger_wsgi"`), documents trade-offs (public write surface, `.note` HTML risk), and plans future extensibility.

# Data Flow
1. **Overview Rendering**: `GET /` renders `overview.html` with a sorted listing from `_files_list`; drag-and-drop uses `/upload`, and manual form posts target the same endpoint.
2. **Metadata API**: `GET /list` exposes JSON entries `{name, mod_time, mod_time_str}` for UI refresh polling and CLI listings.
3. **File Retrieval**: `GET /f/<fn>` streams stored files inline via `send_from_directory`; note editing uses `GET /e/<fn>` restricted to `.note` files, injecting current HTML into `note.html`.
4. **Mutations**: Uploads use `/upload` (multipart) and `/upload_data` (autosave), renames hit `/rename`, deletions post to `/delete/<fn>`; each route enforces filename validation before disk operations and replies with JSON/HTTP status aligned to success or error semantics.
5. **CLI Distribution**: `GET /fs` serves `fs_client.py` with `TARGET_URL` rewritten to the requesting host, enabling stateless CLI sessions without credential flow.
6. **Persistence & Safety**: All data operations target `fstore_app/data/`; filenames containing `..`, `/`, `\`, or empty strings trigger `400/403` responses, and missing resources return `404`.

# Instructions Hierarchy
1. **Repository Documentation (`history_outputs_doc`)**: Canonical reference for architecture, routing, deployment, UX guarantees, and testing expectations.
2. **First Approach Guidance**: Supplies conflict-resolution strategy (chat-surface parity, section constraints) and detailed scaffolding; apply when it reinforces documentation.
3. **Second Approach Guidance**: Reinforces layout, code snippets, and deployment checklists; consult when documentation and first approach are silent.
4. **Third Approach Guidance**: Mirrors earlier advice and fills operational gaps; defer to it only if higher-precedence sources lack specifics.
5. **Explicit System/User Directives**: Always override prior material when new instructions arrive.

# Constraints
- **Authentication-Free Operation**: Remove and forbid auth middleware, credential stores, or token issuance across server, templates, and CLI.
- **Filename Safety**: Reject traversal or separator characters (`..`, `/`, `\\`) and empty names with explicit `400/403/404` responses before touching the filesystem.
- **Passenger Compatibility**: Avoid `app.run()`, expose `application` via `passenger_wsgi.py`, and maintain a clean cold import (`python -c "import passenger_wsgi"`).
- **Separation of Concerns**: Keep templates, static assets, and data segregated; ensure `fstore_app/data/` remains writable at runtime.
- **Dependency Minimalism**: Limit `requirements.txt` to `Flask>=2.2,<3.0`; remove unused authentication libraries or tooling.
- **UX Preservation**: Retain drag-and-drop uploads, autosave status banners, context-menu actions, filename de-duplication, and CLI feature parity despite auth removal.
- **Deployment Alignment**: Operate from the domain root, document DirectAdmin Python Selector settings, and note HTTPS and permissions prerequisites.

# Examples
- **Browser Upload Cycle**: A collaborator drops `report.pdf` onto the overview, the client de-duplicates the filename, posts to `/upload`, updates the table via DOM manipulation, and `/f/report.pdf` becomes immediately available for download.
- **Note Editing Loop**: A user opens `/e/meeting.note`, edits inline content, observes autosave transitions (`Pending` → `Current`), and refresh confirms persistence via `/upload_data` handling.
- **CLI Round Trip**: An operator fetches `/fs`, executes `python fs_client.py put README.md notes/README.md`, confirms overwrite prompts, and validates success with `python fs_client.py ls` reflecting updated modification timestamps.
