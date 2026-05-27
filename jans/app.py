import dataclasses
import traceback
import uuid
from pathlib import Path

from textual import events, on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widget import Widget
from textual.widgets import Button, ContentSwitcher, DirectoryTree, Input, Label, ListItem, ListView

from jans.core.log import log
from jans.core.persistence import load_saved_sessions, save_sessions
from jans.core.state_detector import detect_state, find_real_session_id
from jans.models import Session, SessionState
from jans.widgets.session_list import SessionList
from jans.widgets.terminal_widget import TerminalWidget

RESEARCH_DIR = Path.home() / "research"
ORCHESTRATOR_ID = "orchestrator"


class NewSessionScreen(ModalScreen):
    DEFAULT_CSS = """
    NewSessionScreen {
        align: center middle;
    }
    NewSessionScreen > * {
        width: 60;
        background: $surface;
        border: solid $accent;
        padding: 1 2;
    }
    NewSessionScreen Label {
        margin-bottom: 1;
    }
    NewSessionScreen Input {
        margin-bottom: 1;
    }
    NewSessionScreen #buttons {
        layout: horizontal;
        height: 3;
        align: right middle;
    }
    """

    def __init__(self, mode: str, **kwargs):
        super().__init__(**kwargs)
        self.mode = mode

    def compose(self) -> ComposeResult:
        label = "New research" if self.mode == "research" else "New task"
        from textual.containers import Vertical
        with Vertical():
            yield Label(f"[bold]{label}[/bold]")
            yield Label("Name:")
            yield Input(placeholder="e.g. grpc-timeout-investigation", id="name")
            with Horizontal(id="buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Create", variant="primary", id="create")

    def on_mount(self) -> None:
        self.query_one("#name", Input).focus()

    @on(Button.Pressed, "#cancel")
    def cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#create")
    def create(self) -> None:
        name = self.query_one("#name", Input).value.strip()
        if name:
            self.dismiss((self.mode, name))

    @on(Input.Submitted)
    def submitted(self) -> None:
        self.query_one("#create", Button).press()


class LoadSessionScreen(ModalScreen):
    DEFAULT_CSS = """
    LoadSessionScreen {
        align: center middle;
    }
    LoadSessionScreen > Vertical {
        width: 70;
        height: 30;
        background: $surface;
        border: solid $accent;
        padding: 1 2;
    }
    LoadSessionScreen #path-input {
        margin-bottom: 1;
    }
    LoadSessionScreen DirectoryTree {
        height: 1fr;
        border: solid $accent-darken-2;
        margin-bottom: 1;
    }
    LoadSessionScreen #buttons {
        height: 3;
        align: right middle;
    }
    """

    def compose(self) -> ComposeResult:
        from textual.containers import Vertical
        with Vertical():
            yield Label("[bold]Load directory[/bold]")
            yield Input(str(Path.home()), id="path-input", placeholder="Directory path")
            yield DirectoryTree(Path.home(), id="tree")
            with Horizontal(id="buttons"):
                yield Button("Cancel", variant="default", id="cancel")
                yield Button("Load", variant="primary", id="load")

    def on_mount(self) -> None:
        self.query_one("#path-input", Input).focus()

    @on(DirectoryTree.DirectorySelected)
    def dir_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        self.query_one("#path-input", Input).value = str(event.path)

    @on(Input.Changed, "#path-input")
    def path_changed(self, event: Input.Changed) -> None:
        path = Path(event.value)
        if path.is_dir():
            try:
                self.query_one("#tree", DirectoryTree).path = path
            except Exception:
                pass

    @on(Button.Pressed, "#cancel")
    def cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#load")
    def load(self) -> None:
        path = self.query_one("#path-input", Input).value.strip()
        if Path(path).is_dir():
            self.dismiss(path)

    @on(Input.Submitted, "#path-input")
    def submitted(self) -> None:
        self.query_one("#load", Button).press()


class HelpScreen(ModalScreen):
    DEFAULT_CSS = """
    HelpScreen { align: center middle; }
    HelpScreen > Vertical {
        width: 58;
        height: auto;
        background: #1e1e2e;
        border: solid #cba6f7;
        padding: 1 2;
    }
    """

    BINDINGS = [Binding("escape", "dismiss", show=False),
                Binding("f1", "dismiss", show=False)]

    def compose(self) -> ComposeResult:
        from rich.table import Table
        from textual.containers import Vertical
        from textual.widgets import Static

        table = Table(box=None, padding=(0, 2, 0, 0), show_header=False)
        table.add_column("key", style="yellow", no_wrap=True)
        table.add_column("desc", style="white")

        def section(title):
            table.add_row(f"[bold cyan]{title}[/bold cyan]", "")

        section("Navigation")
        table.add_row("ctrl+h", "Go to orchestrator (home)")
        table.add_row("click", "Open session in right panel")
        table.add_row("F1", "Show / close this help")
        section("Sessions")
        table.add_row("F2", "New research session")
        table.add_row("F3", "New task session")
        table.add_row("F4", "Load existing directory")
        table.add_row("D", "Delete hovered session")
        section("Panel resize")
        table.add_row("F5", "Narrow left panel")
        table.add_row("F6", "Widen left panel")
        section("App")
        table.add_row("ctrl+q", "Save and quit")

        with Vertical():
            yield Label("[bold]jans  shortcuts[/bold]\n")
            yield Static(table)
            yield Label("\n[dim]Escape or F1 to close[/dim]")

    def action_dismiss(self) -> None:
        self.dismiss()


class ResizableDivider(Widget, can_focus=False):
    DEFAULT_CSS = """
    ResizableDivider {
        width: 3;
        height: 100%;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._hovered = False

    def on_enter(self, _: events.Enter) -> None:
        self._hovered = True
        self.refresh()

    def on_leave(self, _: events.Leave) -> None:
        self._hovered = False
        self.refresh()

    def render_line(self, y: int):
        from textual.strip import Strip
        from rich.segment import Segment
        from rich.style import Style
        if self._hovered:
            style = Style(color="#1e1e2e", bgcolor="#cba6f7")
            char = " ◀ "
        else:
            style = Style(color="#585b70", bgcolor="#313244")
            char = " ⋮ "
        return Strip([Segment(char, style)], 3)

    def on_mouse_scroll_up(self, event: events.MouseScrollUp) -> None:
        sl = self.app.query_one("#session-list")
        sl.styles.width = max(20, sl.size.width - 2)
        log.debug("divider scroll up: new width %d", sl.size.width - 2)
        event.stop()

    def on_mouse_scroll_down(self, event: events.MouseScrollDown) -> None:
        sl = self.app.query_one("#session-list")
        sl.styles.width = min(80, sl.size.width + 2)
        log.debug("divider scroll down: new width %d", sl.size.width + 2)
        event.stop()


class HelmApp(App):
    CSS = """
    Screen {
        layout: horizontal;
    }

    SessionList {
        width: 38;
    }

    #right-panel {
        width: 1fr;
    }

    ContentSwitcher {
        height: 100%;
        width: 100%;
    }

    TerminalWidget {
        height: 100%;
        width: 100%;
    }

    #status-bar {
        dock: bottom;
        height: 1;
        background: $accent-darken-2;
        color: $text;
        padding: 0 1;
        content-align: left middle;
    }
    """

    BINDINGS = [
        Binding("f1", "show_help", "F1 Help", show=True),
        Binding("ctrl+h", "go_home", "Home", show=True),
        Binding("f2", "new_research", "F2 Research", show=True),
        Binding("f3", "new_task", "F3 Task", show=True),
        Binding("f4", "load_dir", "F4 Load", show=True),
        Binding("f5", "panel_narrow", "F5 ←", show=False),
        Binding("f6", "panel_widen", "F6 →", show=False),
        Binding("ctrl+q", "quit_app", "Quit", show=True),
    ]

    def __init__(self):
        super().__init__()
        self._sessions: list[Session] = []
        self._active_terminal_id: str = ORCHESTRATOR_ID


    def compose(self) -> ComposeResult:
        yield SessionList(id="session-list")
        yield ResizableDivider(id="divider")
        with Horizontal(id="right-panel"):
            with ContentSwitcher(initial=ORCHESTRATOR_ID, id="switcher"):
                yield TerminalWidget(["claude"], id=ORCHESTRATOR_ID)
        yield Label(self._status_text(), id="status-bar")

    def on_mount(self) -> None:
        try:
            self._sessions = load_saved_sessions()
            log.info("loaded %d saved sessions", len(self._sessions))
            self._update_list()
            self.set_interval(3.0, self._refresh_states)
            self.query_one(f"#{ORCHESTRATOR_ID}", TerminalWidget).focus()
            log.info("app mounted successfully")
        except Exception:
            log.error("error in on_mount:\n%s", traceback.format_exc())

    def _refresh_states(self) -> None:
        new_sessions = []
        for s in self._sessions:
            try:
                if s.state == SessionState.PAUSED:
                    new_sessions.append(s)
                    continue

                real_id = find_real_session_id(s.cwd)
                if real_id and real_id != s.session_id:
                    log.debug("syncing %s session_id -> %s", s.name, real_id[:8])
                    s = dataclasses.replace(s, session_id=real_id)

                new_state, last_activity = detect_state(s)
                if new_state != s.state or last_activity != s.last_activity:
                    log.debug("session %s: %s -> %s", s.name, s.state.value, new_state.value)
                    s = dataclasses.replace(s, state=new_state, last_activity=last_activity)
                new_sessions.append(s)
            except Exception:
                log.error("error refreshing session %s:\n%s", s.name, traceback.format_exc())
                new_sessions.append(s)  # keep it even if refresh failed
        self._sessions = new_sessions
        try:
            self._update_list()
        except Exception:
            log.error("error updating list:\n%s", traceback.format_exc())

    def _update_list(self) -> None:
        sl = self.query_one("#session-list", SessionList)
        sl.update_sessions(self._sessions)
        self.query_one("#status-bar", Label).update(self._status_text())

    def _status_text(self) -> str:
        waiting = sum(1 for s in self._sessions if s.state == SessionState.WAITING)
        processing = sum(1 for s in self._sessions if s.state == SessionState.PROCESSING)
        parts = []
        if waiting:
            parts.append(f"[green]●[/green] {waiting} waiting")
        if processing:
            parts.append(f"[yellow]▶[/yellow] {processing} processing")
        summary = "  ".join(parts) if parts else "[dim]no active sessions[/dim]"
        return f"  {summary}   [dim]F1 help  F2 research  F3 task  F4 load  F5/F6 resize  ctrl+q quit[/dim]"

    @on(SessionList.SessionClicked)
    def session_clicked(self, event: SessionList.SessionClicked) -> None:
        session = event.session
        if session.state == SessionState.PAUSED:
            self._resume_session(session)
        else:
            self._switch_to(session)

    @on(SessionList.SessionDeleteRequested)
    def session_delete_requested(self, event: SessionList.SessionDeleteRequested) -> None:
        session = event.session
        log.info("deleting session %s", session.name)
        if session.terminal_id:
            try:
                widget = self.query_one(f"#{session.terminal_id}", TerminalWidget)
                widget.cleanup()
                widget.remove()
            except Exception:
                pass
        self._sessions = [s for s in self._sessions if s.session_id != session.session_id]
        if self._active_terminal_id == session.terminal_id:
            self.action_go_home()
        self._update_list()

    def _switch_to(self, session: Session) -> None:
        if session.terminal_id is None:
            return
        switcher = self.query_one("#switcher", ContentSwitcher)
        switcher.current = session.terminal_id
        self._active_terminal_id = session.terminal_id
        try:
            self.query_one(f"#{session.terminal_id}", TerminalWidget).focus()
        except Exception:
            pass

    def _resume_session(self, session: Session) -> None:
        log.info("resuming session %s (id=%s)", session.name, session.session_id)
        try:
            tid = f"term-{session.session_id[:8]}"
            session = dataclasses.replace(session, terminal_id=tid, state=SessionState.PROCESSING, pid=None)

            # --continue resumes the most recent conversation in the cwd.
            # We don't use --resume <id> because jans-created sessions have
            # synthetic UUIDs, not real Claude session IDs.
            cmd = ["claude", "--continue"]

            widget = TerminalWidget(cmd, cwd=session.cwd, id=tid)
            switcher = self.query_one("#switcher", ContentSwitcher)
            switcher.mount(widget)
            switcher.current = tid
            self._active_terminal_id = tid
            self.app.call_after_refresh(widget.focus)

            # Update the session in the list with new terminal_id and state
            self._sessions = [
                dataclasses.replace(s, terminal_id=tid, state=SessionState.PROCESSING)
                if s.session_id == session.session_id else s
                for s in self._sessions
            ]
            self._update_list()
        except Exception:
            log.error("error resuming session %s:\n%s", session.name, traceback.format_exc())

    def _create_session(self, mode: str, name: str) -> None:
        log.info("creating %s session: %s", mode, name)
        session_id = str(uuid.uuid4())
        if mode == "research":
            cwd = str(RESEARCH_DIR / name)
        else:
            cwd = str(Path.home() / "research" / name)

        Path(cwd).mkdir(parents=True, exist_ok=True)

        tid = f"term-{session_id[:8]}"
        session = Session(
            name=name,
            cwd=cwd,
            session_id=session_id,
            state=SessionState.PROCESSING,
            terminal_id=tid,
        )

        cmd = ["claude"]
        if mode == "research":
            cmd += ["--append-system-prompt",
                    "You are a research agent. The working directory is your sandbox."]

        widget = TerminalWidget(cmd, cwd=cwd, id=tid)
        self.query_one("#switcher", ContentSwitcher).mount(widget)

        self._sessions.append(session)
        self._update_list()

    def action_go_home(self) -> None:
        switcher = self.query_one("#switcher", ContentSwitcher)
        switcher.current = ORCHESTRATOR_ID
        self._active_terminal_id = ORCHESTRATOR_ID
        self.query_one(f"#{ORCHESTRATOR_ID}", TerminalWidget).focus()

    def action_new_research(self) -> None:
        self._show_new_session_dialog("research")

    def action_new_task(self) -> None:
        self._show_new_session_dialog("task")

    def action_load_dir(self) -> None:
        def handle_result(path: str | None) -> None:
            if path:
                self._load_session(path)
        self.push_screen(LoadSessionScreen(), handle_result)

    def _load_session(self, cwd: str) -> None:
        log.info("loading session from %s", cwd)
        session_id = str(uuid.uuid4())
        name = Path(cwd).name or "loaded"
        tid = f"term-{session_id[:8]}"

        session = Session(
            name=name,
            cwd=cwd,
            session_id=session_id,
            state=SessionState.PROCESSING,
            terminal_id=tid,
        )

        widget = TerminalWidget(["claude", "--continue"], cwd=cwd, id=tid)
        self.query_one("#switcher", ContentSwitcher).mount(widget)

        self._sessions.append(session)
        self._update_list()

    def _show_new_session_dialog(self, mode: str) -> None:
        def handle_result(result):
            if result:
                mode_str, name = result
                self._create_session(mode_str, name)

        self.push_screen(NewSessionScreen(mode), handle_result)

    def action_show_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_panel_narrow(self) -> None:
        sl = self.query_one("#session-list")
        sl.styles.width = max(20, sl.size.width - 2)

    def action_panel_widen(self) -> None:
        sl = self.query_one("#session-list")
        sl.styles.width = min(80, sl.size.width + 2)

    def action_quit_app(self) -> None:
        save_sessions(self._sessions)
        for widget in self.query(TerminalWidget):
            widget.cleanup()
        self.exit()

    def on_unmount(self) -> None:
        save_sessions(self._sessions)
