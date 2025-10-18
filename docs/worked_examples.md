# Worked Examples

## Example 1: Uploading Meeting Notes and Sharing via CLI
**Scenario**: A collaborator needs to upload `meeting.note`, edit it inline, and hand the link to a teammate who prefers the CLI.
**Steps**:
1. Drag `meeting.note` onto the Files panel; verify the status banner flashes “Uploaded”.
2. Click “Edit note” to open `/files/editor/meeting.note`, type updates, and confirm the autosave badge cycles `Pending → Saving → Current`.
3. Visit `/fs` and copy the `curl -O …/fs_client.py` command; teammate downloads the CLI, runs `python fs_client.py ls`, and sees `meeting.note` listed.
**Checks**: Filename sanitisation succeeds (no traversal), `/api/files/upload-data` responds `200`, CLI resolves the live `TARGET_URL`.

## Example 2: Conflict-Free Task Reorder with Keyboard Shortcuts
**Scenario**: Two operators reorder tasks simultaneously; one uses keyboard shortcuts while offline, the other edits online.
**Steps**:
1. Operator A (online) focuses a task, presses `Ctrl+↓`, and observes the toast “Reordered”.
2. Operator B (offline) presses `j/k` to focus another task, hits `Ctrl+↑`, and sees “Queued (offline)”.
3. After reconnect, Operator B’s queue flushes. The backend compares `If-Match` + `Idempotency-Key`; stale headers return `409`, triggering an automatic refresh before retrying.
**Checks**: Keyboard reorder triggers `POST /api/boards/<slug>` with correct headers, conflicts surface with `409`, offline queue flushes after `fetchBoard(true)` updates the ETag.

## Example 3: Automating File Lifecycle with curl
**Scenario**: DevOps wants to script an artefact upload, rename, download, and delete purely via shell commands.
**Steps**:
1. Use `curl -F file=@build.zip $BASE/api/files/upload` to upload.
2. Rename: `curl -X POST $BASE/api/files/rename -H 'Content-Type: application/json' -d '{"old_name":"build.zip","new_name":"release.zip"}'`.
3. Download: `curl -O $BASE/files/release.zip` (URL-encoded if needed).
4. Delete: `curl -X POST $BASE/api/files/delete/release.zip`.
**Checks**: Each call returns `200`, `GET /api/files` reflects state transitions, and filenames containing spaces succeed when URL encoded.

## Example 4: Automation Script Respecting Idempotency
**Scenario**: A cron job adds tasks nightly but must avoid duplicates after transient failures.
**Steps**:
1. Fetch `/api/boards/nightly` and capture `ETag`.
2. POST with payload `{"op":"add","text":"Rotate logs"}` plus headers `If-Match: <etag>`, `Idempotency-Key: <uuid>`.
3. If the job reruns with the same key (retry), the API returns the stored response without duplicating tasks.
**Checks**: The idempotency store persists entries under `data/boards/_idempotency/nightly.json`; repeated calls with the same key return identical JSON and `ETag`.

