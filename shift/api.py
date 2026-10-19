import json
import os
from pathlib import Path
import secrets
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from shift.store import DomainError, Store


class NewIncident(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    title: str = Field(min_length=3, max_length=160)
    service: str = Field(min_length=1, max_length=64)
    severity: Literal["SEV1", "SEV2", "SEV3"]
    note: str = Field(min_length=3, max_length=2000)


class Command(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    version: int = Field(ge=1, strict=True)
    action: Literal["note", "transition", "handoff", "accept", "cancel"]
    note: str = Field(min_length=3, max_length=2000)
    target: str | None = Field(default=None, max_length=64)


def create_app(path=None, users=None):
    users = users or json.loads(os.environ.get("SHIFT_USERS", "{}"))
    if not users or any(len(token) < 16 for token in users):
        raise RuntimeError(
            "SHIFT_USERS must map random tokens (16+ characters) to name/role objects; run scripts/bootstrap.py"
        )
    names = [u.get("name") for u in users.values()]
    if any(not isinstance(n, str) or not n.strip() or len(n) > 64 for n in names) or len(
        set(names)
    ) != len(names):
        raise RuntimeError("User names must be nonempty and unique")
    if any(u.get("role") not in ("viewer", "responder") for u in users.values()):
        raise RuntimeError("Roles must be viewer or responder")
    store = Store(path or os.getenv("SHIFT_DB", "shift.db"))
    app = FastAPI(title="Shift Ledger", version="1.0.0")

    @app.exception_handler(DomainError)
    async def domain_error(request, exc):
        return JSONResponse({"detail": exc.message}, exc.status)

    @app.middleware("http")
    async def headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; script-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    def user(authorization: str = Header(default="")):
        for token, profile in users.items():
            if secrets.compare_digest(authorization.encode(), ("Bearer " + token).encode()):
                return profile
        raise HTTPException(401, "Sign in with a configured access token")

    def responder(profile=Depends(user)):
        if profile["role"] != "responder":
            raise HTTPException(403, "Viewer access is read-only")
        return profile

    @app.get("/health")
    def health():
        store.list()
        return {"status": "ready"}

    @app.get("/api/me")
    def me(profile=Depends(user)):
        return profile

    @app.get("/api/responders", dependencies=[Depends(user)])
    def responders():
        return sorted(u["name"] for u in users.values() if u["role"] == "responder")

    @app.get("/api/incidents", dependencies=[Depends(user)])
    def list_incidents(before: int | None = Query(default=None, ge=1)):
        return store.list(before)

    @app.get("/api/incidents/{ident}", dependencies=[Depends(user)])
    def incident(ident: int):
        return store.detail(ident)

    @app.post("/api/incidents", status_code=201)
    def create(body: NewIncident, profile=Depends(responder)):
        return store.create(body.title, body.service, body.severity, profile["name"], body.note)

    @app.post("/api/incidents/{ident}/commands")
    def command(ident: int, body: Command, profile=Depends(responder)):
        if body.action == "handoff" and body.target not in [
            u["name"] for u in users.values() if u["role"] == "responder"
        ]:
            raise HTTPException(422, "Recipient must be a configured responder")
        return store.command(
            ident, body.version, body.action, profile["name"], body.note, body.target
        )

    app.mount(
        "/", StaticFiles(directory=Path(__file__).parent.parent / "web", html=True), name="web"
    )
    return app
