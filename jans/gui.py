"""jans GUI - native macOS window using tkinter."""
import dataclasses
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import simpledialog

from jans.core.commands import read_pending_command, write_result
from jans.core.log import log
from jans.core.persistence import load_saved_sessions, save_sessions
from jans.core.state_detector import detect_state, find_real_session_id
from jans.models import Session, SessionState

# ── Colors (Catppuccin-inspired) ──────────────────────────────
BG         = "#1e1e2e"
BG_SURFACE = "#313244"
BG_HOVER   = "#45475a"
FG         = "#cdd6f4"
FG_DIM     = "#6c7086"
ORANGE     = "#e07a3e"
YELLOW     = "#f9e2af"
GREEN      = "#a6e3a1"
RED        = "#f38ba8"
BLUE       = "#89b4fa"
PURPLE     = "#cba6f7"

STATE_COLOR = {
    SessionState.PROCESSING:  YELLOW,
    SessionState.WAITING:     GREEN,
    SessionState.NEEDS_INPUT: RED,
    SessionState.TERMINATED:  FG_DIM,
    SessionState.PAUSED:      BLUE,
}
STATE_ICON = {
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


def _active_app() -> str:
    script = 'tell application "System Events" to get name of first application process whose frontmost is true'
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    name = r.stdout.strip().lower()
    if "iterm" in name:    return "iterm2"
    if "intellij" in name: return "intellij"
    return "other"


def _open_session(session: Session) -> None:
    cwd, name = session.cwd, session.name
    cmd = f"cd '{cwd}' && claude --continue"
    terminal = _active_app()
    if terminal == "intellij":
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
        script = f'''
tell application "iTerm2"
    activate
    if (count of windows) = 0 then create window with default profile
    tell current window
        create tab with default profile
        tell current session of current tab
            set name to "{name}"
            write text "{cmd}"
        end tell
    end tell
end tell'''
    subprocess.run(["osascript", "-e", script], capture_output=True)


def _focus_session(session: Session) -> None:
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


class JansApp:
    def __init__(self):
        self._sessions: list[Session] = load_saved_sessions()
        self._lock = threading.Lock()

        self._root = tk.Tk()
        self._root.title("jans")
        self._root.configure(bg=BG)
        self._root.geometry("300x500")
        self._root.minsize(240, 300)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._build_ui()
        self._refresh()
        self._root.after(3000, self._tick)

    # ── UI ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Header
        hdr = tk.Frame(self._root, bg=ORANGE, cursor="hand2")
        hdr.pack(fill="x")
        tk.Label(hdr, text="  jans  ", bg=ORANGE, fg="white",
                 font=("SF Pro Display", 15, "bold"), pady=8).pack()

        # Status bar
        self._status_var = tk.StringVar(value="loading…")
        tk.Label(self._root, textvariable=self._status_var,
                 bg=BG_SURFACE, fg=FG_DIM, font=("SF Mono", 10),
                 anchor="w", padx=10, pady=3).pack(fill="x")

        # Session list (scrollable)
        container = tk.Frame(self._root, bg=BG)
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, bg=BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self._session_frame = tk.Frame(canvas, bg=BG)

        self._session_frame.bind("<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self._session_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Toolbar
        toolbar = tk.Frame(self._root, bg=BG_SURFACE, pady=6)
        toolbar.pack(fill="x", side="bottom")
        for text, cmd in [
            ("＋ Research", self._new_research),
            ("＋ Task",     self._new_task),
            ("⤴ Load",     self._load_dir),
        ]:
            tk.Button(toolbar, text=text, command=cmd,
                      bg=BG_HOVER, fg=FG, relief="flat",
                      font=("SF Pro Text", 11), padx=8, pady=4,
                      cursor="hand2", activebackground=PURPLE,
                      activeforeground=BG).pack(side="left", padx=4, pady=2)

    def _render_sessions(self) -> None:
        for w in self._session_frame.winfo_children():
            w.destroy()

        with self._lock:
            sessions = list(self._sessions)

        paused  = [s for s in sessions if s.state == SessionState.PAUSED]
        active  = [s for s in sessions if s.state != SessionState.PAUSED]

        def add_section(label: str, group: list) -> None:
            if not group:
                return
            tk.Label(self._session_frame, text=label, bg=BG,
                     fg=FG_DIM, font=("SF Pro Text", 10), anchor="w",
                     padx=10, pady=2).pack(fill="x")
            for s in group:
                self._add_session_row(s)

        add_section("── paused ──", paused)
        add_section("── active ──", active)

        if not sessions:
            tk.Label(self._session_frame, text="No sessions yet",
                     bg=BG, fg=FG_DIM, font=("SF Pro Text", 12),
                     pady=20).pack()

        # Status bar
        ni = sum(1 for s in sessions if s.state == SessionState.NEEDS_INPUT)
        wt = sum(1 for s in sessions if s.state == SessionState.WAITING)
        pr = sum(1 for s in sessions if s.state == SessionState.PROCESSING)
        parts = []
        if ni: parts.append(f"⚡ {ni} needs input")
        if wt: parts.append(f"● {wt} waiting")
        if pr: parts.append(f"▶ {pr} processing")
        self._status_var.set("  " + "   ".join(parts) if parts else "  no active sessions")

    def _add_session_row(self, session: Session) -> None:
        color = STATE_COLOR.get(session.state, FG)
        icon  = STATE_ICON.get(session.state, "?")
        name  = session.name if len(session.name) <= 18 else "…" + session.name[-17:]
        cwd   = session.cwd.replace(str(Path.home()), "~")
        age   = _age(session)

        row = tk.Frame(self._session_frame, bg=BG, cursor="hand2")
        row.pack(fill="x", padx=4, pady=1)

        top = tk.Frame(row, bg=BG)
        top.pack(fill="x")
        tk.Label(top, text=f" {icon} ", bg=BG, fg=color,
                 font=("SF Mono", 13)).pack(side="left")
        tk.Label(top, text=name, bg=BG, fg=FG,
                 font=("SF Pro Text", 12, "bold")).pack(side="left")
        tk.Label(top, text=age, bg=BG, fg=FG_DIM,
                 font=("SF Pro Text", 10)).pack(side="right", padx=6)

        tk.Label(row, text=f"   {cwd}", bg=BG, fg=FG_DIM,
                 font=("SF Mono", 10)).pack(fill="x", anchor="w")

        # Hover and click
        def on_enter(e, r=row): r.configure(bg=BG_HOVER)
        def on_leave(e, r=row): r.configure(bg=BG)
        def on_click(e, s=session):
            if s.state == SessionState.PAUSED:
                _open_session(s)
                with self._lock:
                    for i, x in enumerate(self._sessions):
                        if x.session_id == s.session_id:
                            self._sessions[i] = dataclasses.replace(x, state=SessionState.PROCESSING)
            else:
                _focus_session(s)

        for widget in [row, top] + list(row.winfo_children()) + list(top.winfo_children()):
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
            widget.bind("<Button-1>", on_click)

    # ── Refresh ───────────────────────────────────────────────

    def _refresh(self) -> None:
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

        cmd = read_pending_command()
        if cmd:
            write_result(self._execute_command(cmd))

        self._render_sessions()

    def _tick(self) -> None:
        try:
            self._refresh()
        except Exception as e:
            log.error("GUI refresh error: %s", e)
        self._root.after(3000, self._tick)

    # ── Actions ───────────────────────────────────────────────

    def _new_research(self) -> None:
        name = simpledialog.askstring("New research session", "Name:", parent=self._root)
        if name and name.strip():
            self._create_session("research", name.strip())

    def _new_task(self) -> None:
        name = simpledialog.askstring("New task session", "Name:", parent=self._root)
        if name and name.strip():
            self._create_session("task", name.strip())

    def _load_dir(self) -> None:
        from tkinter import filedialog
        path = filedialog.askdirectory(title="Select directory", parent=self._root)
        if path:
            name = Path(path).name
            s = Session(name=name, cwd=path,
                        session_id=__import__("uuid").uuid4().__str__())
            with self._lock:
                self._sessions.append(s)
            _open_session(s)
            self._render_sessions()

    def _create_session(self, mode: str, name: str) -> None:
        import uuid
        cwd = str(Path.home() / "research" / name)
        Path(cwd).mkdir(parents=True, exist_ok=True)
        s = Session(name=name, cwd=cwd, session_id=str(uuid.uuid4()))
        with self._lock:
            self._sessions.append(s)
        _open_session(s)
        self._render_sessions()

    def _execute_command(self, cmd: dict) -> dict:
        action = cmd.get("action", "")
        if action == "list":
            return {"sessions": [{"name": s.name, "state": s.state.value} for s in self._sessions]}
        elif action in ("new-research", "new-task"):
            self._root.after(0, lambda: self._create_session(action.replace("new-", ""), cmd.get("name", "session")))
            return {"ok": True}
        elif action == "delete":
            name = cmd.get("name")
            with self._lock:
                self._sessions = [s for s in self._sessions if s.name != name]
            self._root.after(0, self._render_sessions)
            return {"ok": True}
        elif action == "rename":
            current, new = cmd.get("current"), cmd.get("new")
            with self._lock:
                self._sessions = [
                    dataclasses.replace(s, name=new) if s.name == current else s
                    for s in self._sessions
                ]
            self._root.after(0, self._render_sessions)
            return {"ok": True}
        return {"error": f"unknown: {action}"}

    def _on_close(self) -> None:
        with self._lock:
            save_sessions(self._sessions)
        log.info("jans GUI closed")
        self._root.destroy()

    def run(self) -> None:
        self._root.mainloop()


def main():
    log.info("jans GUI starting")
    JansApp().run()


if __name__ == "__main__":
    main()
