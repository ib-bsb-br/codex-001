# Worked Examples

## Example 1: Typical Feature Update
**Scenario**: A maintainer asks for a public `/health` endpoint that reports storage usage without altering auth posture.
**Approach**:
1. Consult the framework spec to confirm the repository layout and no-auth constraint.
2. Implement the route inside `public_html/fstore_app/app.py`, returning JSON with disk metrics sourced from `fstore_app/data/`.
3. Keep dependency footprint minimal (no new packages) and expose documentation in `README.md`.
4. Run the documented smoke tests (`python -c "import passenger_wsgi"`, manual `GET /health`) to validate WSGI integrity.
**Compliance Checks**: Ensure filename validation logic is reused, no auth artifacts are introduced, and deployment alignment remains intact.

## Example 2: Instruction Conflict Resolution
**Scenario**: A request arrives to password-protect uploads while another directive reiterates the “public, no auth” mandate.
**Approach**:
1. Apply the instructions hierarchy: documentation forbids authentication, so decline the password requirement.
2. Offer alternative mitigations (e.g., rate limiting) that respect the no-auth policy.
3. Document the decision in project notes or PR description referencing the hierarchy rationale.
**Compliance Checks**: Confirm that no code or dependency changes introduce auth, and responses clearly cite the precedence order.

## Example 3: Sparse Bug Report
**Scenario**: User reports “note autosave feels slow” without further detail.
**Approach**:
1. Review `templates/note.html` to understand autosave intervals (`update_interval = 2000` ms).
2. Replicate by editing a `.note` file, watching state transitions, and capturing timing metrics.
3. If adjustment is justified, expose the interval as a configurable constant in `app.py` or front-end script, preserving UX parity.
4. Document the change and advise retesting via browser and CLI flows to ensure no regression.
**Compliance Checks**: Maintain autosave status banner semantics, keep file validation intact, and avoid expanding dependencies.
