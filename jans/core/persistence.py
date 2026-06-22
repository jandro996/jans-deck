import json
from datetime import datetime
from pathlib import Path

from jans.models import Session, SessionState

JANS_DIR = Path.home() / ".jans"
STATE_FILE = JANS_DIR / "state.json"
CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"


def _claude_project_key(cwd: str) -> str:
    """Convert a cwd path to the Claude project directory name."""
    return cwd.replace("/", "-").replace(".", "-")


def migrate_claude_project_dir(old_cwd: str, new_cwd: str) -> bool:
    """Rename Claude's project directory when a session's cwd changes.

    Returns True if renamed, False if skipped (src missing or dst already exists).
    """
    from jans.core.log import log
    old_dir = CLAUDE_PROJECTS / _claude_project_key(old_cwd)
    new_dir = CLAUDE_PROJECTS / _claude_project_key(new_cwd)
    if not old_dir.exists():
        log.debug("migrate_claude_project_dir: src missing %s", old_dir.name)
        return False
    if new_dir.exists():
        log.debug("migrate_claude_project_dir: dst already exists %s", new_dir.name)
        return False
    old_dir.rename(new_dir)
    log.info("renamed Claude project dir: %s -> %s", old_dir.name, new_dir.name)
    return True


def save_sessions(sessions: list[Session]) -> None:
    from jans.core.log import log
    JANS_DIR.mkdir(exist_ok=True)
    data = [
        {
            "name": s.name,
            "cwd": s.cwd,
            "session_id": s.session_id,
            "last_activity": s.last_activity.isoformat(),
            **({"color": s.color} if s.color else {}),
            **({"kind": s.kind} if s.kind else {}),
        }
        for s in sessions
        if s.state != SessionState.TERMINATED
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
                color=d.get("color"),
                kind=d.get("kind"),
            ))
        log.info("loaded %d sessions from state.json", len(sessions))
        return sessions
    except Exception as e:
        log.error("failed to load state.json: %s", e)
        return []
