# Worked Examples

## Example 1: Feature – Add board archival toggle
**Scenario**: Introduce an “archive board” flag that hides a board from recent history while keeping the slug valid.
**Approach**:
1. Update the framework spec to confirm the new metadata lives inside each board JSON (e.g., `archived: bool`).
2. Extend `public_html/fstore_app/app.py` to accept a new `op` (`archive`) that toggles the flag and persists the board.
3. Teach the UI (`static/app.js`) to hide archived slugs from the datalist while still allowing direct navigation.
4. Document the workflow in README and add unit tests covering the new operation.
**Compliance Checks**: Ensure JSON schema remains backward compatible, caching headers persist, and automated tests pass.

## Example 2: Conflict – Request for authentication
**Scenario**: A stakeholder asks to password-protect boards.
**Approach**:
1. Consult the instructions hierarchy: documentation and user mandates require a public, no-auth surface.
2. Decline the change, referencing the “Unauthenticated Surface” constraint, and propose mitigations (rate limiting, monitoring) that respect the policy.
3. Capture the decision in project notes or PR commentary for transparency.
**Compliance Checks**: Verify no authentication libraries or middleware are introduced; dependencies remain minimal.

## Example 3: Bug – Offline queue not flushing
**Scenario**: Users report queued operations never sync after regaining connectivity.
**Approach**:
1. Reproduce by disabling the network, creating tasks, then reconnecting; observe logs in `static/app.js`.
2. Inspect `flushOutbox()` for early returns (e.g., missing `navigator.onLine` checks) and adjust logic to retry until success.
3. Add a regression test (browser automation or unit test with mocked fetch) ensuring queued ops flush and the offline banner hides.
4. Update documentation to reflect troubleshooting steps and confirm `sw.js` still caches shell assets correctly.
**Compliance Checks**: Confirm headers and tests pass, and that data files stay confined to `fstore_app/data/`.
