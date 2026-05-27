import json
from datetime import datetime
from pathlib import Path

from jans.models import Session, SessionState

JANS_DIR = Path.home() / ".jans"
STATE_FILE = JANS_DIR / "state.json"


def save_sessions(sessions: list[Session]) -> None:
    from jans.core.log import log
    JANS_DIR.mkdir(exist_ok=True)
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
    log.info("saved %d sessions to state.json (total in memory: %d, skipped terminated/external: %d)",
             len(data), len(sessions), len(sessions) - len(data))


def load_saved_sessions() -> list[Session]:
    from jans.core.log import log
    if not STATE_FILE.exists():
        log.info("state.json not found, starting fresh")
        return []
    try:
        data = json.loads(STATE_FILE.read_text())
        sessions = []
        for d in data:
            if d.get("pid") is not None:
                log.debug("skipping external session %s (has pid)", d.get("name"))
                continue
            sessions.append(Session(
                name=d["name"],
                cwd=d["cwd"],
                session_id=d["session_id"],
                state=SessionState.PAUSED,
                last_activity=datetime.fromisoformat(d["last_activity"]),
            ))
        log.info("loaded %d sessions from state.json", len(sessions))
        return sessions
    except Exception as e:
        log.error("failed to load state.json: %s", e)
        return []
