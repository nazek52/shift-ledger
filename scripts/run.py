import json
import os
from pathlib import Path
import sys

import uvicorn

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
os.environ.setdefault("SHIFT_USERS", (root / ".local-users.json").read_text(encoding="utf-8"))
os.environ.setdefault("SHIFT_DB", str(root / "shift.db"))
uvicorn.run("shift.api:create_app", factory=True, host="127.0.0.1", port=8012)
