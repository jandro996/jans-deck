from datetime import datetime
from pathlib import Path

from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, Static

from jans.models import SESSION_ICON, Session, SessionState


class SessionList(Widget, can_focus=False):

    class SessionClicked(Message):
        def __init__(self, session: Session):
            super().__init__()
            self.session = session

    DEFAULT_CSS = """
    SessionList {
        width: 38;
        background: $surface;
        padding: 0;
    }
    SessionList #header {
        text-align: center;
        background: $accent-darken-2;
        color: $text;
        width: 100%;
        padding: 0 1;
        text-style: bold;
    }
    SessionList #body {
        width: 100%;
        height: 1fr;
        padding: 0 1;
        background: transparent;
        border: none;
        overflow: hidden hidden;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._sessions: list[Session] = []

    def compose(self) -> ComposeResult:
        yield Label(" jans ", id="header")
        yield Static("", id="body", markup=False)

    def update_sessions(self, sessions: list[Session]) -> None:
        self._sessions = sessions
        body = self.query_one("#body", Static)
        body.update(_render_sessions(sessions))

    def on_click(self, event: events.Click) -> None:
        # y=0 is the header label; subtract 1 to get body-relative y
        body_y = event.y - 1
        session = _session_at_line(self._sessions, body_y)
        if session is not None and (session.terminal_id is not None or session.state == SessionState.PAUSED):
            self.post_message(self.SessionClicked(session))


def _render_sessions(sessions: list[Session]) -> Text:
    text = Text(no_wrap=True, overflow="crop")
    paused = [s for s in sessions if s.state == SessionState.PAUSED]
    active = [s for s in sessions if s.state != SessionState.PAUSED]

    def append_session(s: Session) -> None:
        icon, color = SESSION_ICON[s.state]
        delta = int((datetime.now() - s.last_activity).total_seconds())
        age = f"{delta}s" if delta < 60 else (f"{delta // 60}m" if delta < 3600 else f"{delta // 3600}h")
        short_cwd = s.cwd.replace(str(Path.home()), "~")
        external = s.terminal_id is None and s.state != SessionState.PAUSED
        name_style = "dim" if external else "bold"
        name = s.name if len(s.name) <= 16 else "…" + s.name[-15:]
        text.append(f" {icon} ", style=color)
        text.append(name, style=name_style)
        if external:
            text.append(" ext", style="dim")
        text.append(f" {age.rjust(4)}\n", style="dim")
        text.append(f"   {short_cwd}\n", style="color(8)")

    if paused:
        text.append("── paused ──\n", style="dim")
        for s in paused:
            append_session(s)

    if active:
        if paused:
            text.append("\n")
        text.append("── active ──\n", style="dim")
        for s in active:
            append_session(s)

    return text


def _session_at_line(sessions: list[Session], y: int) -> Session | None:
    paused = [s for s in sessions if s.state == SessionState.PAUSED]
    active = [s for s in sessions if s.state != SessionState.PAUSED]
    line = 0

    if paused:
        if y == line:
            return None
        line += 1
        for s in paused:
            if y in (line, line + 1):
                return s
            line += 2

    if paused and active:
        if y == line:
            return None
        line += 1

    if active:
        if y == line:
            return None
        line += 1
        for s in active:
            if y in (line, line + 1):
                return s
            line += 2

    return None
