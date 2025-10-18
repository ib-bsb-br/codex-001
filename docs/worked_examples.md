# Worked Examples

## Example 1: Typical Feature Update
**Scenario**: Add a public `/health` endpoint reporting disk usage without introducing authentication.
**Approach**:
1. Consult the framework spec for deployment layout and no-auth constraint.
2. Implement the route inside `public_html/fstore_app/app.py`, reuse `_reject_name` or equivalent safeguards for any filename inputs, and return JSON with disk metrics sourced from `fstore_app/data/`.
3. Preserve UX expectations by documenting the new endpoint in `README.md` and verifying `/` still renders correctly.
4. Run smoke tests (`python -c "import passenger_wsgi"`, manual `GET /health`) to ensure WSGI integrity.
**Compliance Checks**: Confirm no new dependencies, no auth artifacts, and filenames remain validated.

## Example 2: Instruction Conflict Resolution
**Scenario**: A stakeholder requests password-protected uploads while business requirements reiterate “public, no auth.”
**Approach**:
1. Apply the instructions hierarchy: documentation and system directives forbid authentication.
2. Decline the password request, citing the hierarchy, and propose acceptable mitigations (e.g., rate limiting) consistent with no-auth policy.
3. Record the decision in project notes or PR descriptions, referencing the relevant instruction tiers.
**Compliance Checks**: Ensure no code introduces auth, dependencies stay minimal, and communication documents the rationale.

## Example 3: Sparse Bug Report
**Scenario**: A user reports “note autosave feels slow” without detail.
**Approach**:
1. Review `public_html/fstore_app/templates/note.html` to confirm the autosave cadence (`update_interval = 2000` ms).
2. Reproduce by editing a `.note` file, observing state transitions (`Pending`, `Current`, failure states) and timing.
3. If adjustment is justified, expose the interval as a configurable constant while retaining autosave banner semantics and filename safety.
4. Validate via browser regression checks and CLI uploads to ensure no new regressions.
**Compliance Checks**: Maintain UX guarantees, keep dependencies unchanged, and preserve deployment alignment.
