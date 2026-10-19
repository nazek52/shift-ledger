# Domain and storage design

## Ownership is a handshake
Requesting a handoff sets pending_owner but leaves owner unchanged. Only that recipient can accept; acceptance replaces owner and clears pending_owner in a single transaction. The original owner may cancel. A pending handoff blocks resolution to avoid silently discarding responsibility.

## Compare-and-swap through version checks
Every command carries the incident version the user saw. A BEGIN IMMEDIATE transaction reads the incident, compares the version, validates authorization and transition, increments version, and appends exactly one event. A stale version returns 409 before any mutation. The browser preserves the user's note but requires reviewing the updated timeline and choosing an action again.

## Audit atomicity
The incident and its event live in the same database transaction. UNIQUE(incident_id,version) prevents duplicate event versions. A rolled-back command changes neither state nor audit. Read detail uses a read transaction so incident state and its event list form one snapshot. The API has no audit-edit route; a database administrator can still alter data.

## Identity and permissions
Operator-generated tokens map to unique responder/viewer names. The server supplies the actor; clients cannot impersonate actors by posting a name. Only owners change status or request/cancel handoffs; only the named recipient accepts. Responders can add evidence to any incident. Viewers are read-only. Same-origin fetch plus bearer authorization avoids ambient-cookie CSRF; XSS remains a risk, mitigated by escaping rendered data and a restrictive CSP.

## Deployment boundaries
Single team, single database file, local token identities, and manual refresh. SQLite is appropriate for this lab's low write concurrency, not a claim of globally distributed service. An internet deployment needs TLS, a real identity provider, quotas/body limits, backup/restore drills, secret rotation, and operational monitoring. The shipped service listens on loopback through scripts/run.py.
