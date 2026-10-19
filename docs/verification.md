# Verification record

Executed 2026-10-19 on Windows with Python 3.13.5, Node.js 24.19.0 and Chromium through Playwright.

- **6 backend tests passed**: acknowledged handoff, owner-only transitions, competing writers, audit atomicity, pagination, role enforcement, validation and stale versions.
- **3 browser tests passed**: two-user handoff; stale-tab update with preserved draft; read-only viewer and 390px viewport without horizontal overflow.
- The screenshot in README is an actual application screenshot from the synthetic browser scenario.
- The browser server uses a temporary database and test-only identities; normal local credentials/data are untouched.

Automated browser checks are Chromium-only, not a full accessibility or cross-browser certification. Production SSO, backup/restore, multi-tenancy and load testing are outside this release. The current cloud checks are visible in GitHub Actions.
