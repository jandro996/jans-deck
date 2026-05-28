from datetime import datetime
from pathlib import Path

from rich.style import Style
from rich.text import Text
from textual import events
from textual.app import ComposeResult
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, Static

from jans.models import SESSION_ICON, Session, SessionState

_HOVER_BG = "#313244"
_STATE_BG = {
    SessionState.WAITING:     "#1a2d1a",  # subtle green
    SessionState.PROCESSING:  "#2d2a1a",  # subtle yellow
    SessionState.NEEDS_INPUT: "#2d1a1a",  # subtle red - needs your attention
}


class _OrchestratorHeader(Widget, can_focus=False):
    """Combined header + orchestrator button. Click anywhere to go to Claude."""

    DEFAULT_CSS = """
    _OrchestratorHeader {
        width: 100%;
        height: 3;
        background: $accent-darken-2;
        border-bottom: solid #313244;
        content-align: center middle;
    }
    _OrchestratorHeader:hover {
        background: $accent-darken-1;
    }
    """

    def render(self):
        from rich.text import Text
        return Text(" jans ", justify="center", style="bold white")

    def on_click(self, event: events.Click) -> None:
        self.post_message(SessionList.OrchestratorClicked())
        event.stop()


class _SessionBody(Widget, can_focus=False):
    """Renders the session list and handles clicks with local coordinates."""

    DEFAULT_CSS = """
    _SessionBody {
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
        self._hover_y: int = -1
        self._text = Text()

    def refresh_sessions(self, sessions: list[Session]) -> None:
        self._sessions = sessions
        self._text = _render_sessions(sessions, self._hover_y)
        self.refresh()

    def hovered_session(self) -> Session | None:
        return _session_at_line(self._sessions, self._hover_y)

    def render(self):
        return self._text

    def on_click(self, event: events.Click) -> None:
        session = _session_at_line(self._sessions, event.y)
        if session is not None:
            self.post_message(SessionList.SessionClicked(session))
        event.stop()

    def on_mouse_move(self, event: events.MouseMove) -> None:
        session = _session_at_line(self._sessions, event.y)
        new_hover = event.y if session is not None else -1
        if new_hover != self._hover_y:
            self._hover_y = new_hover
            self._text = _render_sessions(self._sessions, self._hover_y)
            self.refresh()

    def on_leave(self, _: events.Leave) -> None:
        if self._hover_y != -1:
            self._hover_y = -1
            self._text = _render_sessions(self._sessions, -1)
            self.refresh()


class SessionList(Widget, can_focus=False):

    class SessionClicked(Message):
        def __init__(self, session: Session):
            super().__init__()
            self.session = session

    class SessionDeleteRequested(Message):
        def __init__(self, session: Session):
            super().__init__()
            self.session = session

    class OrchestratorClicked(Message):
        pass

    DEFAULT_CSS = """
    SessionList {
        width: 38;
        background: $surface;
        padding: 0;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._sessions: list[Session] = []
        self._hover_y: int = -1

    def compose(self) -> ComposeResult:
        yield _OrchestratorHeader(id="orchestrator-btn")
        yield _SessionBody(id="body")

    def update_sessions(self, sessions: list[Session]) -> None:
        self._sessions = sessions
        self._refresh_body()

    def _refresh_body(self) -> None:
        body = self.query_one("#body", _SessionBody)
        body.refresh_sessions(self._sessions)

    def _hovered_session(self) -> Session | None:
        return self.query_one("#body", _SessionBody).hovered_session()

def _render_sessions(sessions: list[Session], hover_y: int = -1) -> Text:
    text = Text(no_wrap=True, overflow="crop")
    paused = [s for s in sessions if s.state == SessionState.PAUSED]
    active = [s for s in sessions if s.state != SessionState.PAUSED]
    line = 0

    def append_session(s: Session) -> None:
        nonlocal line
        icon, color = SESSION_ICON[s.state]
        delta = int((datetime.now() - s.last_activity).total_seconds())
        age = f"{delta}s" if delta < 60 else (f"{delta // 60}m" if delta < 3600 else f"{delta // 3600}h")
        short_cwd = s.cwd.replace(str(Path.home()), "~")
        hovered = hover_y in (line, line + 1, line + 2)
        bg = _HOVER_BG if hovered else _STATE_BG.get(s.state)
        dim_style = Style(dim=True, bgcolor=bg)
        cwd_style = Style(color="#585b70", bgcolor=bg)

        text.append(f" {icon} ", style=Style(color=color, bgcolor=bg))
        name = s.name if len(s.name) <= 16 else "…" + s.name[-15:]
        text.append(name, style=Style(bold=True, bgcolor=bg))
        text.append(f" {age.rjust(4)}\n", style=dim_style)
        text.append(f"   {short_cwd}\n", style=cwd_style)
        text.append("\n", style=Style(bgcolor=bg))
        line += 3

    if paused:
        text.append("── paused ──\n", style="dim")
        line += 1
        for s in paused:
            append_session(s)

    if active:
        if paused:
            text.append("\n")
            line += 1
        text.append("── active ──\n", style="dim")
        line += 1
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
            if y in (line, line + 1, line + 2):
                return s
            line += 3

    if paused and active:
        if y == line:
            return None
        line += 1

    if active:
        if y == line:
            return None
        line += 1
        for s in active:
            if y in (line, line + 1, line + 2):
                return s
            line += 3

    return None
