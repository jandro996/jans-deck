import json
from datetime import datetime
from pathlib import Path

from jans.models import Session, SessionState

JANS_DIR = Path.home() / ".jans"
STATE_FILE = JANS_DIR / "state.json"


def save_sessions(sessions: list[Session]) -> None:
    JANS_DIR.mkdir(exist_ok=True)
    data = [
        {
            "name": s.name,
            "cwd": s.cwd,
            "session_id": s.session_id,
            "state": s.state.value,
            "last_activity": s.last_activity.isoformat(),
            "pid": s.pid,
        }
        for s in sessions
        if s.state != SessionState.TERMINATED
    ]
    STATE_FILE.write_text(json.dumps(data, indent=2))


def load_saved_sessions() -> list[Session]:
    if not STATE_FILE.exists():
        return []
    try:
        data = json.loads(STATE_FILE.read_text())
        sessions = []
        for d in data:
            sessions.append(Session(
                name=d["name"],
                cwd=d["cwd"],
                session_id=d["session_id"],
                state=SessionState.PAUSED,
                last_activity=datetime.fromisoformat(d["last_activity"]),
                pid=d.get("pid"),
            ))
        return sessions
    except Exception:
        return []
