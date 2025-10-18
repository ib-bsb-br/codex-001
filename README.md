# Overview
- **Repository**: `ib-bsb-br/codex-001` is organized for deployment on CooliceHost shared hosting with application code under `public_html/` and WSGI entry point `passenger_wsgi.py` exposing `fstore_app.app:app` as `application`. [doc]
- **Purpose**: deliver a public, authentication-free Flask-based file and note server (`FStore`) supporting browser and CLI workflows at the domain root (`/`). [summary][doc]
- **Environment Alignment**: Stack flows Nginx → Apache/Passenger → Flask app managed through DirectAdmin Python Selector within CloudLinux isolation. [doc]

# Roles
- **Platform Maintainer**: provisions Passenger app, installs dependencies, ensures `fstore_app/data/` write permissions, and monitors logs via hosting panel. [doc]
- **Browser Collaborator**: uses overview UI for drag-and-drop uploads, context menu operations, and `.note` editing with autosave. [doc]
- **CLI User**: downloads `fs_client.py` from `/fs`, interacts using `ls/get/put/edit/mv/rm`, and respects overwrite prompts and `$EDITOR`. [doc]

# Data Flow
1. HTTP requests terminate at Nginx, forward to Apache/Passenger, which imports `passenger_wsgi.py` to obtain the Flask `application`. Static assets served from `fstore_app/static/`, dynamic routes handled by Flask. [doc]
2. Browser UI retrieves `/` (overview), `/list` for JSON file listings, `/f/<fn>` and `/e/<fn>` for open/edit flows, and posts to `/upload`, `/upload_data`, `/rename`, `/delete/<fn>`. [doc]
3. CLI fetches `/fs` to obtain host-patched client, then issues HTTP calls to the same CRUD endpoints (`/list`, `/f/`, `/upload`, `/rename`, `/delete`). [doc]
4. All file mutations operate on `fstore_app/data/`; autosave writes note HTML to disk, and rename/delete update filesystem entries with guarded filename checks. [doc]

# Instructions Hierarchy
1. **Documentation Baseline** (`history_outputs_doc`): canonical architecture, routing contract, UX expectations, deployment checklist, and testing criteria. [doc]
2. **First Approach Additions**: enforce conflict resolution priority on user constraints, ensure chat output is single canonical surface, and reiterate full removal of authentication and dependency sanitization. [first]
3. **Second Approach Clarifications**: reinforce repo layout under `public_html/`, provide code scaffolding parity, and highlight optional tightening (`secure_filename`) for future work. [second]
4. **Third Approach Reinforcement**: mirror structural directives and smoke-test expectations confirming `/fs` rewriting and WSGI readiness. [third]
5. Apply precedence in descending order: Documentation → First Approach → Second Approach → Third Approach when resolving ambiguities. [instruction]

# Constraints
- **No Authentication**: remove decorators, token issuance, credential caches, and cookie expectations across server, templates, and CLI. [summary][doc]
- **Filename Safety**: reject names containing `..`, `/`, or `\`; respond with `400/403/404` per invalid/missing cases. [summary][doc]
- **Public Domain Root Routing**: host app at `/` with normalized endpoints; eliminate subpath assumptions. [summary][doc]
- **Passenger/WSGI Compliance**: no `app.run()`, ensure cold import via `python -c "import passenger_wsgi"`, and maintain `requirements.txt` limited to Flask until validated. [summary][doc][first]
- **Separation of Concerns**: templates reside in `fstore_app/templates/`, static assets in `fstore_app/static/`, writable storage in `fstore_app/data/`. [doc]
- **Security Trade-off Disclosure**: document public-write implications and potential XSS from `.note` HTML; rely on HTTPS for transport integrity. [doc]
- **Output Discipline**: deliver canonical content in chat-equivalent artifacts without extraneous sections; avoid duplication across surfaces. [first]

# Examples
- **Typical Upload Workflow**: User drags files onto overview, JS deduplicates filenames, uploads via `/upload`, displays progress, and refreshed `/list` shows updated entries. [doc]
- **Conflict Resolution Scenario**: When conflicting filenames appear, suffix `(n)` is auto-generated in UI; renames via context menu issue `/rename` post, guarded by name validation from highest precedence instructions. [doc][first]
- **Sparse CLI Interaction**: CLI executed on clean environment downloads `fs_client.py` from `/fs`, auto-configures `TARGET_URL`, and performs `ls` followed by `get` streaming to stdout without authentication headers. [doc]

## Generation Policy
- Verify every change preserves no-auth posture and avoids introducing credential dependencies before merge. [doc]
- Validate filename inputs against traversal patterns (`..`, `/`, `\`) and return correct HTTP status codes on rejection. [doc]
- Ensure Passenger entry point remains `passenger_wsgi.py` exposing `application` with no runtime `app.run()` usage. [doc][first]
- Maintain repo layout under `public_html/` with templates/static/data segregation to satisfy hosting expectations. [doc][second]
- Keep chat output as single authoritative surface, matching any parallel artifacts byte-for-byte if produced. [first]
- Document public-write and potential XSS trade-offs whenever communicating deployment risks. [doc]

## Worked Examples
1. **Browser CRUD Happy Path**
   - Precondition: fresh deployment with writable `fstore_app/data/`.
   - Action: upload `report.pdf`, rename to `report-final.pdf`, delete after download.
   - Outcome: `/list` reflects operations; HTTP responses follow 200 → 200 → 200; no auth prompts encountered. [doc]

2. **Instruction Conflict Case**
   - Situation: a developer attempts to add Basic Auth middleware.
   - Resolution: Instructions Hierarchy prohibits auth (Documentation + First Approach). Developer must reject change and document rationale referencing no-auth constraint. [summary][doc][first]

3. **Minimal CLI Usage**
   - Scenario: CLI user with limited bandwidth invokes `fs_client.py cat notes.note > backup.note`.
   - Expected: Client streams content without intermediate buffering, honors existing file creation, and respects traversal protections. [doc]

```json
{"repo_name":"ib-bsb-br/codex-001","artifacts":[{"path":"README.md","type":"spec","generated":true},{"path":"README.md","type":"policy","generated":true},{"path":"README.md","type":"example","generated":true},{"path":"README.md","type":"schema","generated":true}],"metrics":["format_adherence","consistency","task_success","rule_conflict_free"]}
```
