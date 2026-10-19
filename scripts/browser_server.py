"""Isolated disposable database and deliberately test-only identities."""

from pathlib import Path
import sys
import tempfile
import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from shift.api import create_app

if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="shift-browser-") as directory:
        users = {
            "a" * 24: {"name": "Alex", "role": "responder"},
            "s" * 24: {"name": "Sam", "role": "responder"},
            "v" * 24: {"name": "Observer", "role": "viewer"},
        }
        uvicorn.run(create_app(Path(directory) / "test.db", users), host="127.0.0.1", port=8014)
