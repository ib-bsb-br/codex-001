# Overview
FStore is a minimalist Flask-based file and note server deployed as a Passenger-managed WSGI application at the domain root on CooliceHost. The repository `ib-bsb-br/codex-001` must mirror the hosting layout: `public_html/passenger_wsgi.py` exposes `application`, `public_html/fstore_app/app.py` provides the Flask routes, HTML templates reside under `public_html/fstore_app/templates/`, static assets live in `public_html/fstore_app/static/`, user content persists in the writable `public_html/fstore_app/data/` directory, and the distribution-friendly CLI is published as `public_html/fs_client.py`. All routes remain unauthenticated while preserving drag-and-drop uploads, inline note editing, and CLI parity, ensuring frictionless collaboration for non-sensitive data.

# Roles
- **Browser Collaborator**: Interacts with the overview dashboard, uploads files via drag-and-drop, edits `.note` files inline, and triggers rename/delete actions through the context menu.
- **CLI Operator**: Downloads the rewritten `fs_client.py` from `/fs`, executes file CRUD commands (`ls`, `get`, `put`, `edit`, `mv`, `rm`) against the public endpoints, and respects overwrite prompts plus local `EDITOR` usage.
- **Hosting Administrator**: Deploys the app under DirectAdmin’s Python Selector with App Root `public_html/`, Startup File `passenger_wsgi.py`, installs `requirements.txt`, and guarantees `fstore_app/data/` remains writable under CloudLinux constraints.
- **Repository Maintainer**: Aligns code structure, dependencies, and documentation with Passenger/WSGI norms, ensures cold imports succeed, and records trade-offs (public writes, potential `.note` XSS) for future extensibility.

# Data Flow
1. **Listing & Rendering**: `GET /` renders `overview.html` via `render_template`; `GET /list` returns JSON metadata sorted by modification time for both UI refresh and CLI listings.
2. **File Delivery**: `GET /f/<fn>` streams binary payloads inline using `send_from_directory`; `.note` files use `GET /e/<fn>` to load the editor template populated with current HTML content.
3. **Mutations**: Drag-and-drop uploads post to `/upload`; note autosave posts to `/upload_data`; context menu rename triggers `/rename`; deletion submits to `/delete/<fn>`; all use JSON responses for success/failure feedback.
4. **CLI Distribution**: `GET /fs` reads `fs_client.py`, rewrites `TARGET_URL` to the live host, and responds as `text/x-python`, allowing stateless CLI operations.
5. **Persistence**: Files reside under `fstore_app/data/`; filename validation rejects traversal patterns (`..`, `/`, `\`) and empty names before any filesystem touch.

# Instructions Hierarchy
1. **Repository Documentation (history_outputs_doc)**: Defines canonical architecture, endpoint contract, deployment checklist, testing expectations, and security posture.
2. **First Approach Guidance**: Supplements documentation with conflict-resolution priorities (chat-surface parity, section discipline) and detailed implementation scaffolding; apply when compatible with documentation.
3. **Second Approach Guidance**: Provides reinforcement on layout, code snippets, and deployment notes; leverage when not superseded by higher tiers.
4. **Third Approach Guidance**: Mirrors earlier directions and fills operational gaps; defer to it only when higher-precedence sources are silent.
5. **Emergent Instructions**: Explicit user/system directives (e.g., public no-auth, repository wiring) override prior material where conflicts arise.

# Constraints
- **Authentication-Free**: Remove and forbid all auth flows, tokens, or credential artifacts.
- **Path Safety**: Reject filenames containing `..`, `/`, `\`, or empty strings; respond with `400/403/404` as appropriate.
- **Passenger Compliance**: No `app.run()`; ensure `passenger_wsgi.py` imports `application` cleanly and cold imports (`python -c "import passenger_wsgi"`) succeed.
- **Static Separation**: Maintain dedicated `templates/`, `static/`, and writable `data/` directories within `fstore_app/`.
- **Dependency Minimalism**: Keep `requirements.txt` limited to Flask (`>=2.2,<3.0`); eliminate unused auth libraries.
- **UX Preservation**: Retain drag-and-drop uploads, note autosave banner states, context menu actions, and CLI workflows despite auth removal.
- **Deployment Alignment**: Operate from domain root (`/`), ensure HTTPS termination via hosting panel, and document required manual steps (Python Selector configuration, permissions).

# Examples
- **Browser Upload Cycle**: User drops `report.pdf` onto the overview; UI allocates a unique name, posts to `/upload`, updates the table, and permits immediate download via `/f/report.pdf`.
- **Note Editing Loop**: Collaborator opens `/e/meeting.note`, edits inline; autosave posts to `/upload_data`, state badge flips to “Current,” and refresh shows persisted HTML.
- **CLI Interaction**: Operator fetches `/fs`, runs `python fs_client.py put README.md notes/README.md`, observes overwrite prompt handling, and confirms listing via `python fs_client.py ls` reflecting new timestamps.
