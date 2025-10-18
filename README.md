# memor.ia.br Task Boards (Passenger Flask Edition)

This repository mirrors the production layout that runs the memor.ia.br task-board application on CooliceHost shared hosting. The Flask rewrite preserves the PHP build’s behaviors—inline task editing, drag-and-drop reorder, undo flows, filters, offline/PWA support—while fitting Passenger’s WSGI expectations.

## Features
- Keyboard-driven task management with inline editing, undo (10s), filters, and search persistence via localStorage.
- Drag-and-drop reorder (disabled when filtering or searching) with server-side persistence.
- Offline support with queued mutations and service-worker cached shell assets.
- REST-style JSON endpoint at `/api/boards/<slug>` with ETag/Last-Modified validators.
- Automation reference at `/fs` offering sample curl invocations.

## Repository Layout
```
public_html/
├── passenger_wsgi.py           # Passenger entry point exporting `application`
├── fstore_app/
│   ├── __init__.py
│   ├── app.py                  # Flask routes, JSON persistence, headers
│   ├── templates/
│   │   └── app.html            # HTML shell
│   ├── static/
│   │   ├── app.css             # UI styling
│   │   ├── app.js              # Front-end logic and offline queueing
│   │   └── sw.js               # Service worker
│   └── data/                   # JSON boards (writable at runtime)
├── requirements.txt
└── tests/
    └── test_app.py             # Flask client tests
```

## Deployment (CooliceHost DirectAdmin + Passenger)
1. Upload or clone the repository under `~/domains/<domain>/public_html/`.
2. In DirectAdmin → **Python Selector**:
   - App Root: `public_html/`
   - Application URL: `/`
   - Startup File: `passenger_wsgi.py`
3. Create/activate the virtual environment and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Ensure `public_html/fstore_app/data/` is writable by the web user (Passenger runs as the domain user by default).
5. Run a cold import check from SSH to confirm Passenger can load the app:
   ```bash
   python -c "import passenger_wsgi"
   ```
6. Visit `/` to verify the UI, then smoke-test `/api/boards/public`, `/boards/new`, `/fs`, and offline behavior.

## Development
- **Environment**: Python 3.10+, Flask >= 2.2,<3.0.
- **Testing**: run the automated suite with `pytest` or `python -m pytest` (tests rely on Flask’s built-in client).
- **Linting**: no repo-wide linters are enforced; follow existing style.
- **Data**: board JSON files created during development live under `public_html/fstore_app/data/`.

## Smoke-Test Checklist
- `python -c "import passenger_wsgi"` succeeds.
- `/` renders with active slug attributes and loads assets from `static/`.
- `/api/boards/public` returns JSON, respects ETag/Last-Modified, and supports POST mutations.
- Drag-and-drop reorder persists across reloads; undo prompts behave as expected.
- Offline edits queue and sync after reconnection (observe status banner).
- `/fs` returns automation guidance JSON.

## Troubleshooting
- **Passenger errors**: check `~/passenger_wsgi.log` and ensure virtualenv site-packages include Flask.
- **Permission issues**: run `chmod 755 public_html` and `chmod 755 public_html/fstore_app` if Passenger cannot access files; keep `data/` at least `755` so Passenger can write files.
- **Stale assets**: bump the cache key in `static/sw.js` (`CACHE_NAME`) when static files change significantly.
- **Service worker**: run `navigator.serviceWorker.getRegistrations().then(rs => rs.forEach(r => r.unregister()))` in the browser console when testing SW updates.
