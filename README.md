# FStore Collaborative Hub (Passenger + Flask)

This repository mirrors the CooliceHost deployment tree for the integrated FStore hub. The application merges the original unauthenticated file drop with the memor.ia.br task boards, delivering drag-and-drop file sharing, `.note` editing, keyboard-first task management, offline queueing, and automation guidance—all from a single Passenger-hosted Flask service.

## Highlights
- **Unified workspace** – Files and boards share the same dashboard with quick navigation, shared automation docs, and consistent theming.
- **Keyboard centric workflows** – Borrowed from the Checkvist cheatsheet: `/` focuses search, `j/k` move between tasks, `Ctrl+↑/↓` reorders tasks, `Space` toggles completion, `Shift+Tab/Tab` indents notes, and Undo remains available for 10 seconds.
- **Resilient offline mode** – Service worker caches the shell while optimistic concurrency (`If-Match`) and idempotency keys keep mutations safe during reconnects.
- **File extras** – Drag-and-drop uploads, rename/delete context actions, instant `.note` creation, and a downloadable Python CLI with URL-safe handling.
- **Automation-first** – `/fs` bundles Bash/dash/PowerShell/cURL/Python snippets for both file and board APIs, plus a ready-to-run CLI at `/fs_client.py`.

## Repository Layout
```
public_html/
├── passenger_wsgi.py              # Passenger entry point exposing `application`
├── fs_client.py                   # Automation helper (downloadable via /fs_client.py)
├── fstore_app/
│   ├── __init__.py
│   ├── app.py                     # Flask app: routing, headers, persistence, idempotency
│   ├── data/
│   │   ├── boards/sample-board.json
│   │   └── files/.gitkeep
│   ├── static/
│   │   ├── app.css                # Shared styling for files/boards/notes/docs
│   │   ├── app.js                 # Task board logic, concurrency, keyboard shortcuts
│   │   ├── files.js               # File overview, uploads, context actions
│   │   ├── dashboard.js           # Panel navigation & persistence
│   │   └── sw.js                  # Service worker (versioned via ASSET_VERSION)
│   └── templates/
│       ├── dashboard.html         # Combined UI shell
│       ├── fs.html                # Automation documentation surface
│       └── note.html              # `.note` editor
├── requirements.txt               # Runtime dependency pin (Flask only)
└── tests/
    ├── conftest.py                # Live server fixture for browser tests
    ├── test_app.py                # Flask client unit tests
    └── playwright/                # Playwright regression tests for boards/files
```

## Deployment on CooliceHost (DirectAdmin + Passenger)
1. Upload or clone this repository to `~/domains/<domain>/public_html/`.
2. In **DirectAdmin → Python Selector** configure:
   - **App Root:** `public_html/`
   - **Application URL:** `/`
   - **Startup File:** `passenger_wsgi.py`
3. Create/activate the virtualenv and install runtime deps:
   ```bash
   pip install -r requirements.txt
   ```
4. Ensure `public_html/fstore_app/data/` (and subdirectories) are writable by the Passenger user.
5. Perform a cold import to confirm Passenger can load the WSGI entry:
   ```bash
   python -c "import passenger_wsgi"
   ```
6. Smoke-test the live site:
   - `/` should show both **Files** and **Boards** panels.
   - `/api/files` returns JSON; `/api/boards/public` respects ETags.
   - `/fs` renders automation help; `/fs_client.py` downloads the CLI with the correct base URL.

### Remote transfers & SSH
Follow CooliceHost’s guidance (see docs/coolice_documentation excerpt) to manage SSH keys and use `sftp`, `scp`, or `rsync` for deployments. The Passenger process runs as the domain user, so no extra sudo steps are required once keys are in place.

## Local Development & Testing
1. **Environment:** Python 3.10+, Flask ≥ 2.2,<3.0. Install additional dev dependencies:
   ```bash
   pip install pytest pytest-playwright playwright requests
   playwright install
   ```
2. **Run tests:**
   ```bash
   python -m pytest                     # Flask unit tests
   python -m pytest -m playwright       # Browser flows (requires Playwright browsers)
   ```
   The unit suite exercises slug safety, file CRUD, concurrency conflicts, and automation surfaces. Playwright verifies drag-and-drop-style interactions, keyboard shortcuts, and file operations end-to-end.
3. **Data paths:** tests and local runs write to `public_html/fstore_app/data/boards` and `.../files`. Delete contents between runs if you need a clean slate.

## Automation & CLI
- `/fs` serves an HTML manual with Bash/dash/PowerShell/cURL/Python examples for both files and boards, highlighting the required `If-Match` and `Idempotency-Key` headers.
- `/fs_client.py` delivers a Python CLI wrapping file operations (`ls`, `get`, `put`, `cat`, `edit`, `mv`, `rm`) with URL-safe handling. Download with `curl -O https://<host>/fs_client.py` and run `python fs_client.py --help`.

## Keyboard Reference (excerpt)
- `/` – focus board search.
- `j` / `k` – move between tasks.
- `Ctrl + ↑/↓` – reorder focused task (follows Checkvist’s move commands).
- `Space` – toggle completion for focused task.
- `Shift + Tab / Tab` – adjust indent during inline editing.
- `Shift + Shift` (double tap `Shift`) – use browser shortcut find (native) while the toolbar remains accessible.
- `Esc` – cancel inline edits or uploads.

## Troubleshooting
- **Passenger 500s:** re-run `python -c "import passenger_wsgi"`; inspect `~/passenger_wsgi.log` for import errors or permission issues.
- **Static asset caching:** service worker caches are versioned via `ASSET_VERSION`. Changing files in `static/` recomputes the hash; reload with `Ctrl+Shift+R` or unregister the worker via DevTools.
- **File permissions:** ensure uploaded files inherit `0644`. The app enforces safe filenames (rejects `..`, `/`, `\`).
- **Conflicts on board writes:** a `409` response indicates the client used a stale ETag. Re-fetch the board before retrying or rely on the offline queue, which refreshes automatically when the network returns.
- **Playwright artifacts:** reports live in `playwright-report/` and `test-results/` (ignored by git).

## Smoke-Test Checklist
- `python -c "import passenger_wsgi"` succeeds on the server.
- `/` loads with both panels; `Files` supports drag-and-drop uploads and `.note` creation.
- `/api/boards/<slug>` returns JSON with `ETag`/`Last-Modified`; POST mutations succeed with matching `If-Match` + unique `Idempotency-Key`.
- Offline browser session queues updates and syncs after reconnect (observe status banner changes).
- `/fs` and `/fs_client.py` respond with HTML and Python sources tailored to the live host.

