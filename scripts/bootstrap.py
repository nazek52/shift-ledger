"""Generate local identities once. Existing configuration is never overwritten."""

import json
from pathlib import Path
import secrets

path = Path(".local-users.json")
try:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(
            {
                secrets.token_urlsafe(32): {"name": name, "role": role}
                for name, role in [
                    ("Alex", "responder"),
                    ("Sam", "responder"),
                    ("Observer", "viewer"),
                ]
            },
            stream,
            indent=2,
        )
    print("Created .local-users.json. Keep it private; its keys are login tokens.")
except FileExistsError:
    print("Existing .local-users.json preserved.")
