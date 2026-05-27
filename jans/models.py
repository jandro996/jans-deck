from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SessionState(Enum):
    PROCESSING = "processing"
    WAITING = "waiting"
    TERMINATED = "terminated"
    PAUSED = "paused"


SESSION_ICON = {
    SessionState.PROCESSING: ("▶", "yellow"),
    SessionState.WAITING:    ("●", "green"),
    SessionState.TERMINATED: ("✗", "red"),
    SessionState.PAUSED:     ("◉", "blue"),
}


@dataclass
class Session:
    name: str
    cwd: str
    session_id: str
    state: SessionState = SessionState.PROCESSING
    last_activity: datetime = field(default_factory=datetime.now)
    pid: int | None = None
    terminal_id: str | None = None  # None = external session (read-only)
