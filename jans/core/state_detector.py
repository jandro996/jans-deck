import json
import os
from datetime import datetime
from pathlib import Path

from jans.models import Session, SessionState

CLAUDE_SESSIONS = Path.home() / ".claude" / "sessions"
CLAUDE_PROJECTS = Path.home() / ".claude" / "projects"
PROCESSING_THRESHOLD_SECS = 8


def _is_pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _find_jsonl(session_id: str, cwd: str) -> Path | None:
    # Try both the stored cwd and the resolved (real) path to handle case differences
    for c in {cwd, str(Path(cwd).resolve())}:
        project_key = c.replace("/", "-").replace(".", "-")
        path = CLAUDE_PROJECTS / project_key / f"{session_id}.jsonl"
        if path.exists():
            return path
    return None


def _analyze_last_messages(jsonl: Path) -> tuple[str | None, bool]:
    """Returns (last_type, has_pending_tool_use).
    has_pending_tool_use=True means the last assistant message has tool_use
    with no subsequent tool_result - Claude is waiting for permission.
    """
    last_type = None
    last_assistant_content = None
    try:
        with open(jsonl) as f:
            for line in f:
                try:
                    msg = json.loads(line)
                    t = msg.get("type")
                    if t == "assistant":
                        last_type = "assistant"
                        content = msg.get("message", {}).get("content", [])
                        last_assistant_content = content
                    elif t == "user":
                        last_type = "user"
                        # If user sent tool_result, the pending tool_use is resolved
                        content = msg.get("message", {}).get("content", [])
                        if isinstance(content, list):
                            if any(isinstance(b, dict) and b.get("type") == "tool_result"
                                   for b in content):
                                last_assistant_content = None
                except Exception:
                    pass
    except Exception:
        pass

    has_pending_tool_use = False
    if last_type == "assistant" and isinstance(last_assistant_content, list):
        has_pending_tool_use = any(
            isinstance(b, dict) and b.get("type") == "tool_use"
            for b in last_assistant_content
        )

    return last_type, has_pending_tool_use


def detect_state(session: Session) -> tuple[SessionState, datetime]:
    if session.pid and not _is_pid_alive(session.pid):
        return SessionState.TERMINATED, session.last_activity

    jsonl = _find_jsonl(session.session_id, session.cwd)
    if not jsonl:
        return SessionState.PROCESSING, session.last_activity

    mtime = datetime.fromtimestamp(jsonl.stat().st_mtime)
    age = (datetime.now() - mtime).total_seconds()

    last_type, has_pending_tool_use = _analyze_last_messages(jsonl)

    # NEEDS_INPUT takes priority over the time threshold -
    # a pending tool_use is always urgent regardless of when the JSONL was modified.
    if has_pending_tool_use:
        return SessionState.NEEDS_INPUT, mtime

    if age < PROCESSING_THRESHOLD_SECS:
        return SessionState.PROCESSING, mtime

    if last_type == "assistant":
        return SessionState.WAITING, mtime

    return SessionState.PROCESSING, mtime


def load_active_claude_sessions() -> list[Session]:
    sessions = []
    if not CLAUDE_SESSIONS.exists():
        return sessions

    for f in CLAUDE_SESSIONS.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            pid = data.get("pid")
            if pid and not _is_pid_alive(pid):
                continue
            sessions.append(Session(
                name=Path(data.get("cwd", "")).name or "unknown",
                cwd=data.get("cwd", ""),
                session_id=data.get("sessionId", ""),
                pid=pid,
            ))
        except Exception:
            pass

    return sessions


def _norm(path: str) -> str:
    """Normalize path for case-insensitive comparison on macOS."""
    try:
        return str(Path(path).resolve()).lower()
    except Exception:
        return path.lower()


def find_real_session_id(cwd: str) -> str | None:
    """Find the most recent active Claude session ID for a given cwd."""
    if not CLAUDE_SESSIONS.exists():
        return None
    cwd_norm = _norm(cwd)
    best = None
    best_mtime = 0.0
    for f in CLAUDE_SESSIONS.glob("*.json"):
        try:
            data = json.loads(f.read_text())
            if _norm(data.get("cwd", "")) != cwd_norm:
                continue
            pid = data.get("pid")
            if pid and not _is_pid_alive(pid):
                continue
            mtime = f.stat().st_mtime
            if mtime > best_mtime:
                best_mtime = mtime
                best = data.get("sessionId")
        except Exception:
            pass
    return best
