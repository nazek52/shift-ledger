# Local operations runbook

Run `scripts/bootstrap.py` once; preserve `.local-users.json`. `scripts/run.py` uses that file and `shift.db` next to the project. Never commit them. `/health` verifies a database read. Sign out clears the browser session token; operator-side revocation requires removing the token from configuration and restarting.

If an update returns 409, review the new timeline. The note is preserved, but the action must be selected again against current state. Do not blindly retry the old version. If a recipient is unavailable, the current owner can cancel a pending handoff; the original owner remains accountable until acceptance.

For a local file backup, stop the app cleanly and copy the database only after all writers have exited and WAL has checkpointed, or use the SQLite online backup API. Do not copy only the main database while WAL writers are active. The repository does not claim a tested automated backup/restore pipeline.

The UI refreshes on explicit actions and the Refresh button. Counts refer to loaded pages. If you need historical rows, use Load older incidents. On public deployment, replace token identities with an identity provider and add TLS, quotas, request limits, and monitored backups first.
