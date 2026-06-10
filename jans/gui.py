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
from jans.core.state_detector import detect_state, find_claude_session_for_cwd
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

USER_COLORS = {
    "red":    ("#f38ba8", (243, 139, 168)),
    "orange": ("#e07a3e", (224, 122,  62)),
    "yellow": ("#f9e2af", (249, 226, 175)),
    "green":  ("#a6e3a1", (166, 227, 161)),
    "blue":   ("#89b4fa", (137, 180, 250)),
    "purple": ("#cba6f7", (203, 166, 247)),
    "pink":   ("#f5c2e7", (245, 194, 231)),
    "teal":   ("#94e2d5", (148, 226, 213)),
}

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
_JANS_CWD = str(Path.home() / "research" / "jans")


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


def _write_tty(tty: str, seq: str) -> None:
    try:
        with open(tty, "w") as f:
            f.write(seq)
    except Exception:
        pass


def _set_iterm_tab_color(tty: str, rgb: tuple[int, int, int] | None) -> None:
    if rgb:
        r, g, b = rgb
        seq = (
            f"\033]6;1;bg;red;brightness;{r}\a"
            f"\033]6;1;bg;green;brightness;{g}\a"
            f"\033]6;1;bg;blue;brightness;{b}\a"
        )
    else:
        seq = "\033]6;1;bg;*;default\a"
    _write_tty(tty, seq)


def _set_iterm_badge(tty: str, name: str) -> None:
    import base64
    b64 = base64.b64encode(name.encode()).decode()
    _write_tty(tty, f"\033]1337;SetBadgeFormat={b64}\a")


def _set_iterm_title(tty: str, name: str) -> None:
    _write_tty(tty, f"\033]0;{name}\a")


def _iterm_open_ttys() -> set[str]:
    """Return the set of tty paths for all sessions currently open in iTerm2."""
    script = '''\
tell application "iTerm2"
    set ttys to {}
    repeat with w in windows
        repeat with t in tabs of w
            repeat with s in sessions of t
                set end of ttys to tty of s
            end repeat
        end repeat
    end repeat
    set AppleScript's text item delimiters to ","
    return ttys as text
end tell'''
    try:
        r = subprocess.run(["osascript", "-e", script],
                           capture_output=True, text=True, timeout=2)
        if r.returncode != 0 or not r.stdout.strip():
            return set()
        return {t.strip() for t in r.stdout.strip().split(",") if t.strip()}
    except Exception:
        return set()


def _pid_tty(pid: int) -> str | None:
    """Return the /dev/ttysXXX path for a process, or None if it has no tty."""
    try:
        r = subprocess.run(["ps", "-o", "tty=", "-p", str(pid)],
                           capture_output=True, text=True)
        tty = r.stdout.strip()
        if tty and tty != "??" and tty != "??":
            return f"/dev/{tty}"
    except Exception:
        pass
    return None


def _focus_session_by_tty(tty: str) -> None:
    script = f'''
tell application "iTerm2"
    activate
    repeat with w in windows
        repeat with t in tabs of w
            repeat with s in sessions of t
                if tty of s = "{tty}" then
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
        self._tab_colors_applied: dict[str, str] = {}   # name -> color applied
        self._badge_applied: set[str] = set()           # names with badge set
        self._title_state: dict[str, SessionState] = {} # name -> state when title was last set

        self._root = tk.Tk()
        self._root.title("jans")
        self._root.configure(bg=BG)
        self._root.geometry("280x520")
        self._root.minsize(240, 300)
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        _icon = _JANS_DIR / "jans.iconset" / "icon_512x512.png"
        if _icon.exists():
            img = tk.PhotoImage(file=str(_icon))
            self._root.iconphoto(True, img)
            self._icon_ref = img  # prevent GC

        self._iterm_was_front = False

        self._build_ui()
        self._refresh()
        self._root.after(3000, self._tick)
        self._root.after(1000, self._focus_poll)

    # ── UI ────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        # Header (clickable - opens jans orchestrator session)
        hdr = tk.Frame(self._root, bg=ORANGE, cursor="hand2")
        hdr.pack(fill="x")
        hdr_lbl = tk.Label(hdr, text="jans", bg=ORANGE, fg="white",
                           font=("SF Pro Display", 14, "bold"), pady=7,
                           cursor="hand2")
        hdr_lbl.pack()
        hdr.bind("<Button-1>", lambda e: self._open_jans_session())
        hdr_lbl.bind("<Button-1>", lambda e: self._open_jans_session())

        # Status bar (under header)
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
        canvas.create_window((0, 0), window=self._session_frame, anchor="nw", tags="inner")
        canvas.bind("<Configure>",
            lambda e: canvas.itemconfig("inner", width=e.width))
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        # Toolbar
        toolbar = tk.Frame(self._root, bg=BG_SURFACE, pady=5)
        toolbar.pack(fill="x", side="bottom")
        for text, cmd in [
            ("＋ Research", self._new_research),
            ("＋ Task",     self._new_task),
            ("⤴ Load",     self._load_dir),
        ]:
            tk.Button(toolbar, text=text, command=cmd,
                      bg=BG_HOVER, fg=FG, relief="flat",
                      font=("SF Pro Text", 10), padx=7, pady=3,
                      cursor="hand2", activebackground=PURPLE,
                      activeforeground=BG).pack(side="left", padx=3, pady=2)

    def _add_section_header(self, label: str) -> None:
        hdr = tk.Frame(self._session_frame, bg=BG, pady=3)
        hdr.pack(fill="x", padx=10, pady=(4, 0))
        tk.Frame(hdr, bg=BG_SURFACE, height=1).pack(side="left", fill="x", expand=True, pady=5)
        tk.Label(hdr, text=f"  {label}  ", bg=BG, fg=FG_DIM,
                 font=("SF Pro Text", 9)).pack(side="left")
        tk.Frame(hdr, bg=BG_SURFACE, height=1).pack(side="left", fill="x", expand=True, pady=5)

    def _render_sessions(self) -> None:
        for w in self._session_frame.winfo_children():
            w.destroy()

        with self._lock:
            sessions = [s for s in self._sessions if s.cwd != _JANS_CWD]

        paused  = [s for s in sessions if s.state == SessionState.PAUSED]
        active  = [s for s in sessions if s.state != SessionState.PAUSED]

        if paused:
            self._add_section_header("paused")
            for s in paused:
                self._add_session_row(s)

        if active:
            self._add_section_header("active")
            for s in active:
                self._add_session_row(s)

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
        self._status_var.set("  " + "   ".join(parts) if parts else "  all paused")

    def _add_session_row(self, session: Session) -> None:
        color = STATE_COLOR.get(session.state, FG)
        icon  = STATE_ICON.get(session.state, "?")
        name  = session.name if len(session.name) <= 22 else "…" + session.name[-21:]
        cwd   = session.cwd.replace(str(Path.home()), "~")
        age   = _age(session)

        # Outer wrapper (full width, no horizontal padding so border touches edge)
        row = tk.Frame(self._session_frame, bg=BG, cursor="hand2")
        row.pack(fill="x", pady=0)

        # Left color accent
        accent = tk.Frame(row, bg=color, width=3)
        accent.pack(side="left", fill="y")

        # Content
        content = tk.Frame(row, bg=BG)
        content.pack(side="left", fill="both", expand=True, padx=(8, 6), pady=4)

        top = tk.Frame(content, bg=BG)
        top.pack(fill="x")
        icon_lbl = tk.Label(top, text=f"{icon} ", bg=BG, fg=color,
                            font=("SF Mono", 11))
        icon_lbl.pack(side="left")
        name_lbl = tk.Label(top, text=name, bg=BG, fg=FG,
                            font=("SF Pro Text", 12, "bold"))
        name_lbl.pack(side="left")
        user_color = USER_COLORS.get(session.color or "")
        color_dot = None
        if user_color:
            color_dot = tk.Frame(top, bg=user_color[0], width=10, height=14)
            color_dot.pack(side="left", padx=(5, 0))
            color_dot.pack_propagate(False)
        age_lbl = tk.Label(top, text=age, bg=BG, fg=FG_DIM,
                           font=("SF Pro Text", 10))
        age_lbl.pack(side="right")

        cwd_lbl = tk.Label(content, text=cwd, bg=BG, fg=FG_DIM,
                           font=("SF Mono", 10), anchor="w")
        cwd_lbl.pack(fill="x")

        # Bottom separator
        tk.Frame(self._session_frame, bg=BG_SURFACE, height=1).pack(fill="x")

        # Hover: propagate bg to all content widgets (not the accent border)
        hover_widgets = [row, content, top, icon_lbl, name_lbl, age_lbl, cwd_lbl]

        def on_enter(e):
            for w in hover_widgets:
                w.configure(bg=BG_HOVER)

        def on_leave(e):
            for w in hover_widgets:
                w.configure(bg=BG)

        def on_click(e, s=session):
            if s.state == SessionState.PAUSED:
                _open_session(s)
                with self._lock:
                    for i, x in enumerate(self._sessions):
                        if x.session_id == s.session_id:
                            self._sessions[i] = dataclasses.replace(x, state=SessionState.PROCESSING)
            else:
                claude = find_claude_session_for_cwd(s.cwd)
                if claude and claude[1]:
                    tty = _pid_tty(claude[1])
                    if tty:
                        _focus_session_by_tty(tty)
                        return
                _open_session(s)

        for widget in hover_widgets:
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
            widget.bind("<Button-1>", on_click)

    # ── Refresh ───────────────────────────────────────────────

    def _refresh(self) -> None:
        open_ttys = _iterm_open_ttys()

        with self._lock:
            new_sessions = []
            for s in self._sessions:
                claude = find_claude_session_for_cwd(s.cwd)
                has_iterm_tab = (
                    claude is not None
                    and claude[1] is not None
                    and _pid_tty(claude[1]) in open_ttys
                )

                if not has_iterm_tab:
                    if s.state not in (SessionState.PAUSED, SessionState.TERMINATED):
                        s = dataclasses.replace(s, state=SessionState.PAUSED)
                    self._tab_colors_applied.pop(s.name, None)
                    self._badge_applied.discard(s.name)
                    self._title_state.pop(s.name, None)
                    new_sessions.append(s)
                    continue

                session_id, pid = claude
                if session_id and session_id != s.session_id:
                    s = dataclasses.replace(s, session_id=session_id)
                new_state, last_activity = detect_state(s)
                if new_state != s.state or last_activity != s.last_activity:
                    s = dataclasses.replace(s, state=new_state, last_activity=last_activity)

                tty = _pid_tty(pid) if pid else None
                if tty:
                    # Color: apply once (or when changed)
                    if s.color and self._tab_colors_applied.get(s.name) != s.color:
                        user_color = USER_COLORS.get(s.color)
                        if user_color:
                            _set_iterm_tab_color(tty, user_color[1])
                            self._tab_colors_applied[s.name] = s.color

                    # Badge: set once on activation
                    if s.name not in self._badge_applied:
                        _set_iterm_badge(tty, s.name)
                        self._badge_applied.add(s.name)

                    # Title: show state icon when idle, release when processing
                    if new_state != SessionState.PROCESSING:
                        if self._title_state.get(s.name) != new_state:
                            icon = STATE_ICON.get(new_state, "")
                            _set_iterm_title(tty, f"{icon} {s.name}")
                            self._title_state[s.name] = new_state
                    else:
                        self._title_state.pop(s.name, None)

                new_sessions.append(s)
            self._sessions = new_sessions

        cmd = read_pending_command()
        if cmd:
            write_result(self._execute_command(cmd))

        self._render_sessions()

    def _tick(self) -> None:
        try:
            self._refresh()
            with self._lock:
                save_sessions(self._sessions)
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
            with self._lock:
                color = self._next_color()
            s = Session(name=name, cwd=path,
                        session_id=__import__("uuid").uuid4().__str__(), color=color)
            with self._lock:
                self._sessions.append(s)
            _open_session(s)
            self._render_sessions()

    def _next_color(self) -> str:
        palette = list(USER_COLORS.keys())
        used = {s.color for s in self._sessions if s.color}
        for c in palette:
            if c not in used:
                return c
        return palette[len(self._sessions) % len(palette)]

    def _create_session(self, mode: str, name: str) -> None:
        import uuid
        cwd = str(Path.home() / "research" / name)
        Path(cwd).mkdir(parents=True, exist_ok=True)
        with self._lock:
            color = self._next_color()
        s = Session(name=name, cwd=cwd, session_id=str(uuid.uuid4()), color=color)
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
        elif action == "color":
            name, color = cmd.get("name"), cmd.get("color")
            with self._lock:
                self._sessions = [
                    dataclasses.replace(s, color=color) if s.name == name else s
                    for s in self._sessions
                ]
            self._tab_colors_applied.pop(name, None)
            self._root.after(0, self._render_sessions)
            return {"ok": True}
        elif action == "load":
            import uuid
            path = cmd.get("path", "")
            name = cmd.get("name") or Path(path).name
            with self._lock:
                if not any(s.name == name for s in self._sessions):
                    color = self._next_color()
                    s = Session(name=name, cwd=path, session_id=str(uuid.uuid4()), color=color)
                    self._sessions.append(s)
            self._root.after(0, self._render_sessions)
            return {"ok": True}
        return {"error": f"unknown: {action}"}

    def _open_jans_session(self) -> None:
        with self._lock:
            jans_session = next((s for s in self._sessions if s.cwd == _JANS_CWD), None)

        if jans_session is not None and jans_session.state != SessionState.PAUSED:
            claude = find_claude_session_for_cwd(jans_session.cwd)
            if claude and claude[1]:
                tty = _pid_tty(claude[1])
                if tty:
                    _focus_session_by_tty(tty)
                    return

        if jans_session is not None:
            _open_session(jans_session)
            with self._lock:
                for i, s in enumerate(self._sessions):
                    if s.cwd == _JANS_CWD:
                        self._sessions[i] = dataclasses.replace(s, state=SessionState.PROCESSING)
        else:
            import uuid
            s = Session(name="jans", cwd=_JANS_CWD, session_id=str(uuid.uuid4()))
            with self._lock:
                self._sessions.append(s)
            _open_session(s)

    def _focus_poll(self) -> None:
        iterm_front = _active_app() == "iterm2"
        if iterm_front and not self._iterm_was_front:
            self._root.lift()
        self._iterm_was_front = iterm_front
        self._root.after(1000, self._focus_poll)

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
