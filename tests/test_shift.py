from concurrent.futures import ThreadPoolExecutor
import pytest
from fastapi.testclient import TestClient
from shift.api import create_app
from shift.store import DomainError, Store

USERS = {
    "a" * 24: {"name": "Alex", "role": "responder"},
    "s" * 24: {"name": "Sam", "role": "responder"},
    "v" * 24: {"name": "Observer", "role": "viewer"},
}


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "test.db")


def incident(store):
    return store.create("API latency spike", "gateway", "SEV2", "Alex", "p95 above budget")


def test_acknowledged_handoff_preserves_owner_until_accept(store):
    row = incident(store)
    pending = store.command(row["id"], 1, "handoff", "Alex", "Check connection pool", "Sam")
    assert pending["owner"] == "Alex" and pending["pending_owner"] == "Sam"
    with pytest.raises(DomainError) as exc:
        store.command(row["id"], 2, "accept", "Alex", "Taking ownership")
    assert exc.value.status == 403
    accepted = store.command(row["id"], 2, "accept", "Sam", "Context reviewed")
    assert accepted["owner"] == "Sam" and accepted["pending_owner"] is None
    assert [e["version"] for e in accepted["events"]] == [1, 2, 3]


def test_concurrent_writers_one_wins_and_audit_is_atomic(store):
    row = incident(store)

    def write(_):
        try:
            store.command(row["id"], 1, "note", "Alex", "New evidence")
            return 200
        except DomainError as exc:
            return exc.status

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(write, range(8)))
    assert results.count(200) == 1 and results.count(409) == 7
    detail = store.detail(row["id"])
    assert detail["version"] == 2 and len(detail["events"]) == 2


def test_status_flow_and_reopen(store):
    row = incident(store)
    with pytest.raises(DomainError):
        store.command(row["id"], 1, "transition", "Alex", "Premature resolve", "resolved")
    for version, status in enumerate(
        ("investigating", "monitoring", "resolved", "investigating"), 1
    ):
        updated = store.command(
            row["id"], version, "transition", "Alex", "Evidence recorded", status
        )
        assert updated["status"] == status


def test_resolve_blocked_by_handoff_and_cancel(store):
    row = incident(store)
    store.command(row["id"], 1, "transition", "Alex", "Looking now", "investigating")
    store.command(row["id"], 2, "transition", "Alex", "Metrics recovered", "monitoring")
    store.command(row["id"], 3, "handoff", "Alex", "Watch recovery", "Sam")
    with pytest.raises(DomainError):
        store.command(row["id"], 4, "transition", "Alex", "Resolved now", "resolved")
    store.command(row["id"], 4, "cancel", "Alex", "Remaining on shift")
    assert (
        store.command(row["id"], 5, "transition", "Alex", "Stable metrics", "resolved")["status"]
        == "resolved"
    )


def test_pagination_no_duplicate_ids(store):
    for _ in range(55):
        incident(store)
    first = store.list()
    second = store.list(first["next_cursor"])
    assert len(first["items"]) == 50 and len(second["items"]) == 5
    assert not {r["id"] for r in first["items"]} & {r["id"] for r in second["items"]}


def test_api_role_validation_and_conflict(tmp_path):
    client = TestClient(create_app(tmp_path / "api.db", USERS))
    auth = lambda token: {"Authorization": "Bearer " + token * 24}
    body = {
        "title": "Elevated latency",
        "service": "api",
        "severity": "SEV2",
        "note": "Started after deploy",
    }
    assert client.get("/api/incidents").status_code == 401
    assert client.post("/api/incidents", json=body, headers=auth("v")).status_code == 403
    assert (
        client.post("/api/incidents", json={**body, "title": "   "}, headers=auth("a")).status_code
        == 422
    )
    row = client.post("/api/incidents", json=body, headers=auth("a")).json()
    path = f"/api/incidents/{row['id']}/commands"
    cmd = {"version": 1, "action": "note", "note": "Evidence collected"}
    assert client.post(path, json=cmd, headers=auth("a")).status_code == 200
    assert client.post(path, json=cmd, headers=auth("a")).status_code == 409
    assert (
        client.post(
            path,
            json={**cmd, "version": 2, "action": "handoff", "target": "Unknown"},
            headers=auth("a"),
        ).status_code
        == 422
    )
    assert client.get("/").status_code == 200
    assert client.get("/api/me", headers=auth("s")).json()["name"] == "Sam"
