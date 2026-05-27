import json
from datetime import datetime
from pathlib import Path

from jans.models import Session, SessionState

JANS_DIR = Path.home() / ".jans"
STATE_FILE = JANS_DIR / "state.json"


def save_sessions(sessions: list[Session]) -> None:
    JANS_DIR.mkdir(exist_ok=True)
    # Only save jans-created sessions (pid=None means created via F2/F3/F4,
    # not detected from external ~/.claude/sessions/)
    data = [
        {
            "name": s.name,
            "cwd": s.cwd,
            "session_id": s.session_id,
            "last_activity": s.last_activity.isoformat(),
        }
        for s in sessions
        if s.state != SessionState.TERMINATED and s.pid is None
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
            ))
        return sessions
    except Exception:
        return []
