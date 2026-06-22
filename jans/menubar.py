"""jans menu bar app - always-visible session dashboard for macOS."""
import dataclasses
import subprocess
import threading
from pathlib import Path

import rumps

from jans.core.commands import read_pending_command, write_result
from jans.core.log import log
from jans.core.persistence import load_saved_sessions, save_sessions
from jans.core.state_detector import detect_state, find_real_session_id
from jans.models import Session, SessionState

_ICONS = {
    SessionState.PROCESSING:  "▶",
    SessionState.WAITING:     "●",
    SessionState.NEEDS_INPUT: "⚡",
    SessionState.TERMINATED:  "✗",
    SessionState.PAUSED:      "◉",
}

_JANS_DIR = Path(__file__).parent.parent


def _age(session: Session) -> str:
    from datetime import datetime
    s = int((datetime.now() - session.last_activity).total_seconds())
    if s < 60:   return f"{s}s"
    if s < 3600: return f"{s // 60}m"
    return f"{s // 3600}h"


def _active_terminal() -> str:
    """Returns 'iterm2', 'intellij', or 'other'."""
    script = 'tell application "System Events" to get name of first application process whose frontmost is true'
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    name = result.stdout.strip().lower()
    if "iterm" in name:      return "iterm2"
    if "intellij" in name:   return "intellij"
    return "other"


def _open_in_terminal(session: Session) -> None:
    """Open a claude --continue session in the appropriate terminal."""
    cwd = session.cwd
    name = session.name
    cmd = f"cd '{cwd}' && claude --continue"
    terminal = _active_terminal()

    if terminal == "iterm2":
        script = f'''
tell application "iTerm2"
    activate
    tell current window
        create tab with default profile
        tell current session of current tab
            set name to "{name}"
            write text "{cmd}"
        end tell
    end tell
end tell'''
    elif terminal == "intellij":
        # Open a new terminal tab in IntelliJ via its REST API or shell command
        script = f'''
tell application "IntelliJ IDEA"
    activate
end tell
delay 0.3
tell application "System Events"
    tell process "IntelliJ IDEA"
        keystroke "F12" -- focus terminal
    end tell
end tell'''
        # Fallback: open in iTerm2
        subprocess.run(["osascript", "-e", script], capture_output=True)
        script = f'''
tell application "iTerm2"
    activate
    tell current window
        create tab with default profile
        tell current session of current tab
            set name to "{name}"
            write text "{cmd}"
        end tell
    end tell
end tell'''
    else:
        script = f'tell application "Terminal" to do script "{cmd}"'

    subprocess.run(["osascript", "-e", script], capture_output=True)


def _focus_session(session: Session) -> None:
    """Try to focus an existing terminal for this session."""
    name = session.name
    script = f'''
tell application "iTerm2"
    activate
    repeat with w in windows
        repeat with t in tabs of w
            repeat with s in sessions of t
                if name of s contains "{name}" then
                    tell w to select
                    select t
                    return
                end if
            end repeat
        end repeat
    end repeat
end tell'''
    subprocess.run(["osascript", "-e", script], capture_output=True)


class JansMenuBar(rumps.App):
    def __init__(self):
        super().__init__("jans", quit_button=None)
        self._sessions: list[Session] = load_saved_sessions()
        self._lock = threading.Lock()
        self._build_menu()
        # Start background refresh thread
        self._timer = rumps.Timer(self._refresh, 3)
        self._timer.start()

    # ── Menu building ──────────────────────────────────────────

    def _build_menu(self) -> None:
        with self._lock:
            self.menu.clear()
            sessions = list(self._sessions)

        needs_input = [s for s in sessions if s.state == SessionState.NEEDS_INPUT]
        waiting     = [s for s in sessions if s.state == SessionState.WAITING]
        processing  = [s for s in sessions if s.state == SessionState.PROCESSING]
        paused      = [s for s in sessions if s.state == SessionState.PAUSED]

        # Update icon to reflect most urgent state
        if needs_input:
            self.title = f"jans ⚡{len(needs_input)}"
        elif waiting:
            self.title = f"jans ●{len(waiting)}"
        elif processing:
            self.title = "jans ▶"
        else:
            self.title = "jans"

        # Sessions grouped by state
        for group_label, group in [
            ("⚡ needs input", needs_input),
            ("● waiting",      waiting),
            ("▶ processing",   processing),
            ("◉ paused",       paused),
        ]:
            if not group:
                continue
            self.menu.add(rumps.separator)
            self.menu.add(rumps.MenuItem(group_label, callback=None))
            for s in group:
                icon = _ICONS[s.state]
                label = f"  {icon}  {s.name}  ({_age(s)})"
                item = rumps.MenuItem(label, callback=self._make_session_callback(s))
                self.menu.add(item)

        # Actions
        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("＋ New research…",   callback=self._new_research))
        self.menu.add(rumps.MenuItem("＋ New task…",        callback=self._new_task))
        self.menu.add(rumps.MenuItem("⤴  Load directory…", callback=self._load_dir))
        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Quit jans", callback=self._quit))

    def _make_session_callback(self, session: Session):
        def callback(_):
            if session.state == SessionState.PAUSED:
                _open_in_terminal(session)
                with self._lock:
                    for i, s in enumerate(self._sessions):
                        if s.session_id == session.session_id:
                            self._sessions[i] = dataclasses.replace(s, state=SessionState.PROCESSING)
            else:
                _focus_session(session)
        return callback

    # ── Refresh ────────────────────────────────────────────────

    def _refresh(self, _=None) -> None:
        try:
            with self._lock:
                new_sessions = []
                for s in self._sessions:
                    if s.state == SessionState.PAUSED:
                        new_sessions.append(s)
                        continue
                    real_id = find_real_session_id(s.cwd)
                    if real_id and real_id != s.session_id:
                        s = dataclasses.replace(s, session_id=real_id)
                    new_state, last_activity = detect_state(s)
                    if new_state != s.state or last_activity != s.last_activity:
                        s = dataclasses.replace(s, state=new_state, last_activity=last_activity)
                    new_sessions.append(s)
                self._sessions = new_sessions

            # Handle jans-ctl commands
            cmd = read_pending_command()
            if cmd:
                result = self._execute_command(cmd)
                write_result(result)

            self._build_menu()
        except Exception as e:
            log.error("menu refresh error: %s", e)

    # ── Session actions ────────────────────────────────────────

    def _new_research(self, _) -> None:
        response = rumps.Window(
            message="Session name:",
            title="New research session",
            default_text="",
            ok="Create",
            cancel="Cancel",
            dimensions=(300, 20),
        ).run()
        if response.clicked and response.text.strip():
            self._create_session("research", response.text.strip())

    def _new_task(self, _) -> None:
        response = rumps.Window(
            message="Session name:",
            title="New task session",
            default_text="",
            ok="Create",
            cancel="Cancel",
            dimensions=(300, 20),
        ).run()
        if response.clicked and response.text.strip():
            self._create_session("task", response.text.strip())

    def _load_dir(self, _) -> None:
        response = rumps.Window(
            message="Directory path:",
            title="Load directory",
            default_text=str(Path.home() / "research"),
            ok="Load",
            cancel="Cancel",
            dimensions=(400, 20),
        ).run()
        if response.clicked and response.text.strip():
            cwd = response.text.strip()
            name = Path(cwd).name
            s = Session(name=name, cwd=cwd, session_id=__import__('uuid').uuid4().__str__())
            with self._lock:
                self._sessions.append(s)
            _open_in_terminal(s)
            self._build_menu()

    def _create_session(self, mode: str, name: str) -> None:
        import uuid
        if mode == "research":
            cwd = str(Path.home() / "research" / name)
        else:
            cwd = str(Path.home() / "research" / name)
        Path(cwd).mkdir(parents=True, exist_ok=True)
        s = Session(name=name, cwd=cwd, session_id=str(uuid.uuid4()))
        with self._lock:
            self._sessions.append(s)
        _open_in_terminal(s)
        self._build_menu()

    def _execute_command(self, cmd: dict) -> dict:
        action = cmd.get("action", "")
        if action == "list":
            return {"sessions": [
                {"name": s.name, "state": s.state.value, "cwd": s.cwd}
                for s in self._sessions
            ]}
        elif action in ("new-research", "new-task"):
            name = cmd.get("name", "session")
            self._create_session(action.replace("new-", ""), name)
            return {"ok": True}
        elif action == "delete":
            name = cmd.get("name")
            with self._lock:
                self._sessions = [s for s in self._sessions if s.name != name]
            self._build_menu()
            return {"ok": True}
        elif action == "rename":
            current, new = cmd.get("current"), cmd.get("new")
            with self._lock:
                self._sessions = [
                    dataclasses.replace(s, name=new) if s.name == current else s
                    for s in self._sessions
                ]
            self._build_menu()
            return {"ok": True}
        return {"error": f"unknown action: {action}"}

    def _quit(self, _) -> None:
        with self._lock:
            save_sessions(self._sessions)
        log.info("jans menu bar quit")
        rumps.quit_application()


def main():
    log.info("jans menu bar starting")
    JansMenuBar().run()


if __name__ == "__main__":
    main()
