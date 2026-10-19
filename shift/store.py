from contextlib import contextmanager
from datetime import datetime, timezone
import sqlite3


class DomainError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


TRANSITIONS = {
    "open": {"investigating"},
    "investigating": {"monitoring"},
    "monitoring": {"investigating", "resolved"},
    "resolved": {"investigating"},
}


class Store:
    def __init__(self, path):
        self.path = str(path)
        with self.db() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS incidents (
                    id INTEGER PRIMARY KEY, title TEXT NOT NULL, service TEXT NOT NULL,
                    severity TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
                    owner TEXT NOT NULL, pending_owner TEXT,
                    version INTEGER NOT NULL DEFAULT 1, updated TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY, incident_id INTEGER NOT NULL,
                    kind TEXT NOT NULL, actor TEXT NOT NULL, note TEXT NOT NULL,
                    version INTEGER NOT NULL, at TEXT NOT NULL,
                    FOREIGN KEY(incident_id) REFERENCES incidents(id),
                    UNIQUE(incident_id,version)
                );
            """)

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            yield db
        finally:
            if db.in_transaction:
                db.rollback()
            db.close()

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat()

    def create(self, title, service, severity, actor, note):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            now = self.now()
            cursor = db.execute(
                "INSERT INTO incidents(title,service,severity,owner,updated) VALUES(?,?,?,?,?)",
                (title, service, severity, actor, now),
            )
            ident = cursor.lastrowid
            db.execute(
                "INSERT INTO events(incident_id,kind,actor,note,version,at) VALUES(?,'created',?,?,1,?)",
                (ident, actor, note, now),
            )
            result = self._detail(db, ident)
            db.commit()
            return result

    def _detail(self, db, ident):
        row = db.execute("SELECT * FROM incidents WHERE id=?", (ident,)).fetchone()
        if row is None:
            raise DomainError(404, "Incident not found")
        return {
            **dict(row),
            "events": [
                dict(e)
                for e in db.execute(
                    "SELECT * FROM events WHERE incident_id=? ORDER BY version", (ident,)
                )
            ],
        }

    def detail(self, ident):
        with self.db() as db:
            db.execute("BEGIN")
            return self._detail(db, ident)

    def list(self, before=None):
        with self.db() as db:
            rows = db.execute(
                "SELECT * FROM incidents WHERE (? IS NULL OR id<?) ORDER BY id DESC LIMIT 51",
                (before, before),
            ).fetchall()
            return {
                "items": [dict(r) for r in rows[:50]],
                "next_cursor": rows[49]["id"] if len(rows) > 50 else None,
            }

    def command(self, ident, version, action, actor, note, target=None):
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            row = self._detail(db, ident)
            if row["version"] != version:
                raise DomainError(409, "Incident changed. Reload before applying your update.")
            updates = {}
            if action == "note":
                pass
            elif action == "transition":
                if row["owner"] != actor:
                    raise DomainError(403, "Only the current owner can change status")
                if target not in TRANSITIONS[row["status"]]:
                    raise DomainError(422, "Invalid status transition")
                if row["pending_owner"] and target == "resolved":
                    raise DomainError(422, "Cancel or complete the handoff before resolving")
                updates["status"] = target
            elif action == "handoff":
                if row["owner"] != actor:
                    raise DomainError(403, "Only the current owner can request handoff")
                if row["status"] == "resolved" or target == actor or row["pending_owner"]:
                    raise DomainError(
                        422,
                        "Handoff requires an active incident and a different recipient; only one may be pending",
                    )
                updates["pending_owner"] = target
            elif action == "accept":
                if row["pending_owner"] != actor:
                    raise DomainError(403, "Only the requested recipient can accept")
                updates.update(owner=actor, pending_owner=None)
            elif action == "cancel":
                if row["owner"] != actor or not row["pending_owner"]:
                    raise DomainError(403, "Only the owner can cancel a pending handoff")
                updates["pending_owner"] = None
            else:
                raise DomainError(422, "Unknown command")
            updates.update(version=version + 1, updated=self.now())
            # Column names come exclusively from this function, never request input.
            db.execute(
                "UPDATE incidents SET " + ",".join(f"{key}=?" for key in updates) + " WHERE id=?",
                (*updates.values(), ident),
            )
            event_note = f"{target}: {note}" if action in ("handoff", "transition") else note
            db.execute(
                "INSERT INTO events(incident_id,kind,actor,note,version,at) VALUES(?,?,?,?,?,?)",
                (ident, action, actor, event_note, version + 1, updates["updated"]),
            )
            result = self._detail(db, ident)
            db.commit()
            return result
