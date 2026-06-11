"""jans GUI - native macOS window using tkinter."""
import dataclasses
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import simpledialog, ttk

from jans.core.commands import read_pending_command, write_result
from jans.core.features import Feature, create_feature, link_session, load_features
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
_JANS_CWD    = str(Path.home() / "research" / "jans")
_TOOLS_DIR   = Path.home() / "tools"
_REVIEWS_DIR = Path.home() / "reviews"
_TASKS_DIR   = Path.home() / "IdeaProjects"

_SESSION_TABS = ("research", "tasks", "tools", "reviews")
_ALL_TABS     = ("features",) + _SESSION_TABS


def _session_kind(s: "Session") -> str:  # returns one of _SESSION_TABS
    """Classify a session into one of the four tabs."""
    if s.kind:
        return s.kind
    cwd = s.cwd
    if cwd.startswith(str(_REVIEWS_DIR)):
        return "reviews"
    if cwd.startswith(str(_TOOLS_DIR)):
        return "tools"
    if cwd.startswith(str(_TASKS_DIR)):
        return "tasks"
    return "research"


def _parse_github_pr_url(url: str) -> tuple[str, str, str] | None:
    """Parse a GitHub PR URL into (full_repo, short_name, pr_number).
    Accepts: https://github.com/Owner/repo/pull/1234
    Returns: ('Owner/repo', 'repo', '1234') or None if not parseable.
    """
    import re
    m = re.match(r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)", url.strip())
    if not m:
        return None
    owner, repo, pr = m.group(1), m.group(2), m.group(3)
    return f"{owner}/{repo}", repo, pr


def _bootstrap_planning_files(
    cwd: str,
    mode: str,
    name: str,
    repo: str | None = None,
    pr: str | None = None,
) -> None:
    base = Path(cwd)

    def _write(filename: str, content: str) -> None:
        p = base / filename
        if not p.exists():
            p.write_text(content)

    if mode == "research":
        _write("session.md", (
            "---\n"
            "type: research\n"
            "related_projects: []\n"
            f"investigation: {name}\n"
            "contribution_targets: []\n"
            "---\n"
        ))
        _write("task_plan.md", _task_plan_content(name))
        _write("findings.md", f"# Findings: {name}\n")
        _write("progress.md", f"# Progress: {name}\n")

    elif mode == "task":
        _write("session.md", (
            "---\n"
            "type: task\n"
            "related_projects: []\n"
            'feature: ""\n'
            "contribution_targets: []\n"
            "---\n"
        ))
        _write("task_plan.md", _task_plan_content(name))
        _write("findings.md", f"# Findings: {name}\n")
        _write("progress.md", f"# Progress: {name}\n")

    elif mode == "tool":
        _write("session.md", (
            "---\n"
            "type: tooling\n"
            "related_projects:\n"
            "  - _meta\n"
            "contribution_targets:\n"
            "  - _meta/workflow.md\n"
            "---\n"
        ))
        _write("task_plan.md", _task_plan_content(name))
        _write("findings.md", f"# Findings: {name}\n")
        _write("progress.md", f"# Progress: {name}\n")

    elif mode == "review":
        _write("session.md", (
            "---\n"
            "type: pr-review-incoming\n"
            f"repo: {repo or ''}\n"
            f"pr: {pr or ''}\n"
            "related_projects: []\n"
            "---\n"
        ))


def _task_plan_content(name: str) -> str:
    return (
        f"# Task plan: {name}\n\n"
        "## Phases\n\n"
        "- [ ] Phase 0: Pre-code analysis (/pre-code)\n"
        "- [ ] Phase 1: Implementation\n"
        "- [ ] Phase 2: Pre-PR review (/pre-pr)\n"
        "- [ ] Phase 3: Open PR (/pr-describe)\n"
        "- [ ] Phase 4: Address review comments\n"
        "- [ ] Phase 5: Merge and close (/finish-pr)\n"
    )


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


def _open_session(session: Session, resume: bool = True) -> None:
    cwd, name = session.cwd, session.name
    cmd = f"cd '{cwd}' && claude" + (" --continue" if resume else "")
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
        self._features: list[Feature] = load_features()
        self._features_expanded: set[str] = set()
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

        # Toolbar (bottom, packed before content so it doesn't get pushed off)
        toolbar = tk.Frame(self._root, bg=BG_SURFACE, pady=5)
        toolbar.pack(fill="x", side="bottom")

        btn_kw = dict(bg=BG_HOVER, fg=FG, relief="flat",
                      font=("SF Pro Text", 10), padx=7, pady=3,
                      cursor="hand2", activebackground=PURPLE, activeforeground=BG)
        self._new_btn  = tk.Button(toolbar, text="＋", **btn_kw)
        self._load_btn = tk.Button(toolbar, text="⤴ Load", command=self._load_dir, **btn_kw)
        self._new_btn.pack(side="left", padx=3, pady=2)
        self._load_btn.pack(side="left", padx=3, pady=2)

        # Tab bar
        tab_bar = tk.Frame(self._root, bg=BG_SURFACE)
        tab_bar.pack(fill="x")

        self._active_tab: str = "research"
        self._tab_buttons: dict[str, tk.Label] = {}
        self._tab_containers: dict[str, tk.Frame] = {}
        self._tab_frames: dict[str, tk.Frame] = {}

        # Content area (fills remaining space)
        content_area = tk.Frame(self._root, bg=BG)
        content_area.pack(fill="both", expand=True)

        for tab_name in _ALL_TABS:
            lbl = tk.Label(tab_bar, text=tab_name.capitalize(),
                           bg=BG_SURFACE, fg=FG_DIM,
                           font=("SF Pro Text", 10), padx=12, pady=5,
                           cursor="hand2")
            lbl.pack(side="left")
            lbl.bind("<Button-1>", lambda e, t=tab_name: self._switch_tab(t))
            self._tab_buttons[tab_name] = lbl

            container = tk.Frame(content_area, bg=BG)
            canvas = tk.Canvas(container, bg=BG, highlightthickness=0)
            scrollbar = tk.Scrollbar(container, orient="vertical", command=canvas.yview)
            inner = tk.Frame(canvas, bg=BG)
            inner.bind("<Configure>",
                lambda e, c=canvas: c.configure(scrollregion=c.bbox("all")))
            canvas.create_window((0, 0), window=inner, anchor="nw", tags="inner")
            canvas.bind("<Configure>",
                lambda e, c=canvas: c.itemconfig("inner", width=e.width))
            canvas.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side="right", fill="y")
            canvas.pack(side="left", fill="both", expand=True)

            self._tab_containers[tab_name] = container
            self._tab_frames[tab_name] = inner

        self._switch_tab("features")

    _TAB_NEW_ACTION = {
        "features": ("＋ Feature",  "_new_feature"),
        "research": ("＋ Research", "_new_research"),
        "tasks":    ("＋ Task",     "_new_task"),
        "tools":    ("＋ Tool",     "_new_tool"),
        "reviews":  ("＋ Review",   "_new_review"),
    }

    def _switch_tab(self, name: str) -> None:
        self._active_tab = name
        for t, container in self._tab_containers.items():
            if t == name:
                container.pack(fill="both", expand=True)
            else:
                container.pack_forget()
        for t, btn in self._tab_buttons.items():
            if t == name:
                btn.configure(bg=BG, fg=FG, font=("SF Pro Text", 10, "bold"))
            else:
                btn.configure(bg=BG_SURFACE, fg=FG_DIM, font=("SF Pro Text", 10))

        label, method = self._TAB_NEW_ACTION.get(name, ("＋ New", "_new_research"))
        self._new_btn.configure(text=label, command=getattr(self, method))
        if name == "features":
            self._load_btn.pack_forget()
        else:
            self._load_btn.pack(side="left", padx=3, pady=2)

    def _add_section_header(self, label: str, frame: tk.Frame) -> None:
        hdr = tk.Frame(frame, bg=BG, pady=3)
        hdr.pack(fill="x", padx=10, pady=(4, 0))
        tk.Frame(hdr, bg=BG_SURFACE, height=1).pack(side="left", fill="x", expand=True, pady=5)
        tk.Label(hdr, text=f"  {label}  ", bg=BG, fg=FG_DIM,
                 font=("SF Pro Text", 9)).pack(side="left")
        tk.Frame(hdr, bg=BG_SURFACE, height=1).pack(side="left", fill="x", expand=True, pady=5)

    _INACTIVE = {SessionState.PAUSED, SessionState.TERMINATED}

    # ── Features tab ─────────────────────────────────────────────

    def _render_features_tab(self) -> None:
        frame = self._tab_frames["features"]
        for w in frame.winfo_children():
            w.destroy()

        features = self._features
        with self._lock:
            sessions_by_name = {s.name: s for s in self._sessions}

        # Update features tab button
        btn = self._tab_buttons["features"]
        is_active = (self._active_tab == "features")
        btn.configure(text="Features",
                      font=("SF Pro Text", 10, "bold") if is_active else ("SF Pro Text", 10))

        if not features:
            tk.Label(frame, text="No features yet",
                     bg=BG, fg=FG_DIM, font=("SF Pro Text", 12), pady=20).pack()
            return

        for feat in features:
            expanded = feat.ticket_id in self._features_expanded
            # Header row
            hdr = tk.Frame(frame, bg=BG_SURFACE, cursor="hand2")
            hdr.pack(fill="x")

            toggle_lbl = tk.Label(hdr, text="▼ " if expanded else "▶ ",
                                  bg=BG_SURFACE, fg=ORANGE,
                                  font=("SF Mono", 10), padx=6, pady=6)
            toggle_lbl.pack(side="left")

            display_name = feat.nickname if feat.nickname else feat.ticket_id
            tid_lbl = tk.Label(hdr, text=display_name,
                               bg=BG_SURFACE, fg=FG,
                               font=("SF Pro Text", 11, "bold"), pady=6)
            tid_lbl.pack(side="left")

            if feat.nickname:
                ticket_meta = tk.Label(hdr, text=f"  {feat.ticket_id}",
                                       bg=BG_SURFACE, fg=FG_DIM,
                                       font=("SF Mono", 9), pady=6)
                ticket_meta.pack(side="left")
            else:
                ticket_meta = None

            desc_lbl = tk.Label(hdr, text=f"  {feat.description}" if feat.description else "",
                                bg=BG_SURFACE, fg=FG_DIM,
                                font=("SF Pro Text", 10), pady=6)
            desc_lbl.pack(side="left")

            n_active = sum(1 for sn in feat.sessions
                           if sn in sessions_by_name
                           and sessions_by_name[sn].state not in self._INACTIVE)
            count_lbl = tk.Label(hdr,
                                 text=f"{n_active}/{len(feat.sessions)}" if feat.sessions else "0",
                                 bg=BG_SURFACE, fg=FG_DIM,
                                 font=("SF Pro Text", 10), padx=8, pady=6)
            count_lbl.pack(side="right")

            toggle_targets = [hdr, toggle_lbl, tid_lbl, desc_lbl, count_lbl]
            if ticket_meta:
                toggle_targets.append(ticket_meta)
            for w in toggle_targets:
                w.bind("<Button-1>", lambda e, t=feat.ticket_id: self._toggle_feature(t))

            tk.Frame(frame, bg=BG, height=1).pack(fill="x")

            if expanded:
                sess_frame = tk.Frame(frame, bg=BG)
                sess_frame.pack(fill="x")
                if not feat.sessions:
                    tk.Label(sess_frame, text="No sessions linked",
                             bg=BG, fg=FG_DIM, font=("SF Pro Text", 10),
                             pady=6, padx=24).pack(anchor="w")
                else:
                    for sname in feat.sessions:
                        self._add_feature_session_row(sess_frame, sname,
                                                       sessions_by_name.get(sname))
                tk.Frame(frame, bg=BG_SURFACE, height=1).pack(fill="x")

    def _add_feature_session_row(self, parent: tk.Frame,
                                  name: str, session: "Session | None") -> None:
        row = tk.Frame(parent, bg=BG, cursor="hand2" if session else "arrow")
        row.pack(fill="x", padx=(24, 0))

        if session:
            color = STATE_COLOR.get(session.state, FG)
            icon  = STATE_ICON.get(session.state, "?")
            age   = _age(session)
            fg    = FG
        else:
            color, icon, age, fg = FG_DIM, "·", "—", FG_DIM

        icon_lbl = tk.Label(row, text=f"{icon} ", bg=BG, fg=color,
                            font=("SF Mono", 10))
        icon_lbl.pack(side="left", pady=3)
        name_lbl = tk.Label(row, text=name, bg=BG, fg=fg,
                            font=("SF Pro Text", 11))
        name_lbl.pack(side="left")
        age_lbl = tk.Label(row, text=age, bg=BG, fg=FG_DIM,
                           font=("SF Pro Text", 9))
        age_lbl.pack(side="right", padx=8)

        if session:
            hw = [row, icon_lbl, name_lbl, age_lbl]

            def on_click(e, s=session):
                claude = find_claude_session_for_cwd(s.cwd)
                if claude and claude[1]:
                    tty = _pid_tty(claude[1])
                    if tty:
                        _focus_session_by_tty(tty)
                        return
                _open_session(s)

            for w in hw:
                w.bind("<Button-1>", on_click)
                w.bind("<Enter>", lambda e, ww=hw: [x.configure(bg=BG_HOVER) for x in ww])
                w.bind("<Leave>", lambda e, ww=hw: [x.configure(bg=BG) for x in ww])

        tk.Frame(parent, bg=BG_SURFACE, height=1).pack(fill="x", padx=(24, 0))

    def _toggle_feature(self, ticket_id: str) -> None:
        if ticket_id in self._features_expanded:
            self._features_expanded.discard(ticket_id)
        else:
            self._features_expanded.add(ticket_id)
        self._render_sessions()

    def _new_feature(self) -> None:
        ticket = simpledialog.askstring("New feature", "Ticket ID (e.g. JIRA-1234):",
                                        parent=self._root)
        if not ticket or not ticket.strip():
            return
        nickname = simpledialog.askstring("New feature", "Nickname (short display name):",
                                          parent=self._root)
        if nickname is None:
            return
        description = simpledialog.askstring("New feature", "Description (optional):",
                                             parent=self._root)
        create_feature(ticket.strip(), nickname.strip(), (description or "").strip())
        self._features = load_features()
        self._features_expanded.add(ticket.strip())
        self._switch_tab("features")
        self._render_sessions()

    def _render_sessions(self) -> None:
        with self._lock:
            sessions = [s for s in self._sessions if s.cwd != _JANS_CWD]

        # Features tab
        self._render_features_tab()

        # Categorize into session tabs
        by_tab: dict[str, list] = {t: [] for t in _SESSION_TABS}
        for s in sessions:
            by_tab[_session_kind(s)].append(s)

        for tab_name, tab_sessions in by_tab.items():
            frame = self._tab_frames[tab_name]
            for w in frame.winfo_children():
                w.destroy()

            active   = [s for s in tab_sessions if s.state not in self._INACTIVE]
            inactive = [s for s in tab_sessions if s.state in self._INACTIVE]

            for s in active:
                self._add_session_row(s, frame)
            if inactive:
                self._add_section_header("paused", frame)
                for s in inactive:
                    self._add_session_row(s, frame)

            if not tab_sessions:
                tk.Label(frame, text="No sessions",
                         bg=BG, fg=FG_DIM, font=("SF Pro Text", 12),
                         pady=20).pack()

            # Update tab button label with active count badge
            active_count = len(active)
            label = tab_name.capitalize()
            if active_count:
                label += f"  {active_count}"
            btn = self._tab_buttons[tab_name]
            is_active_tab = (tab_name == self._active_tab)
            btn.configure(text=label,
                          font=("SF Pro Text", 10, "bold") if is_active_tab else ("SF Pro Text", 10))

        # Status bar (global counts)
        ni = sum(1 for s in sessions if s.state == SessionState.NEEDS_INPUT)
        wt = sum(1 for s in sessions if s.state == SessionState.WAITING)
        pr = sum(1 for s in sessions if s.state == SessionState.PROCESSING)
        parts = []
        if ni: parts.append(f"⚡ {ni}")
        if wt: parts.append(f"● {wt}")
        if pr: parts.append(f"▶ {pr}")
        self._status_var.set("  " + "  ".join(parts) if parts else "  all paused")

    def _add_session_row(self, session: Session, frame: tk.Frame) -> None:
        color = STATE_COLOR.get(session.state, FG)
        icon  = STATE_ICON.get(session.state, "?")
        name  = session.name if len(session.name) <= 22 else "…" + session.name[-21:]
        cwd   = session.cwd.replace(str(Path.home()), "~")
        age   = _age(session)

        # Outer wrapper (full width, no horizontal padding so border touches edge)
        row = tk.Frame(frame, bg=BG, cursor="hand2")
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
        tk.Frame(frame, bg=BG_SURFACE, height=1).pack(fill="x")

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

        def on_right_click(e, s=session):
            menu = tk.Menu(self._root, tearoff=0, bg=BG_SURFACE, fg=FG,
                           activebackground=RED, activeforeground=BG,
                           font=("SF Pro Text", 11), bd=0)
            menu.add_command(label=f"Delete \"{s.name}\"",
                             command=lambda: self._confirm_delete(s))
            menu.tk_popup(e.x_root, e.y_root)

        for widget in hover_widgets:
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
            widget.bind("<Button-1>", on_click)
            widget.bind("<Button-2>", on_right_click)
            widget.bind("<Button-3>", on_right_click)

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
                            _set_iterm_title(tty, f"{s.name} {icon}")
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
            self._features = load_features()
            self._refresh()
            with self._lock:
                save_sessions(self._sessions)
        except Exception as e:
            log.error("GUI refresh error: %s", e)
        self._root.after(3000, self._tick)

    # ── Actions ───────────────────────────────────────────────

    def _confirm_delete(self, session: Session) -> None:
        import shutil
        from tkinter import messagebox
        ok = messagebox.askyesno(
            "Delete session",
            f"Delete \"{session.name}\"?\n\n{session.cwd}\n\nThe directory will be removed from disk.",
            icon="warning",
            parent=self._root,
        )
        if ok:
            with self._lock:
                self._sessions = [s for s in self._sessions if s.session_id != session.session_id]
            try:
                shutil.rmtree(session.cwd)
            except Exception as e:
                from tkinter import messagebox as mb
                mb.showerror("Error", f"Could not remove directory:\n{e}", parent=self._root)
            self._render_sessions()

    def _new_research(self) -> None:
        name = simpledialog.askstring("New research session", "Name:", parent=self._root)
        if name and name.strip():
            self._create_session("research", name.strip())

    def _new_task(self) -> None:
        repo = simpledialog.askstring("New task session", "Repo (e.g. dd-trace-java):",
                                      parent=self._root)
        if not repo or not repo.strip():
            return
        name = simpledialog.askstring("New task session", "Branch / task name:",
                                      parent=self._root)
        if not name or not name.strip():
            return
        ticket = simpledialog.askstring("New task session",
                                        "Feature ticket ID (optional, leave empty to skip):",
                                        parent=self._root)
        self._create_task_session(repo.strip(), name.strip(),
                                  ticket.strip() if ticket and ticket.strip() else None)

    def _create_task_session(self, repo: str, name: str,
                             ticket_id: str | None = None) -> None:
        import uuid
        cwd = str(_TASKS_DIR / f"{repo}-{name}")
        Path(cwd).mkdir(parents=True, exist_ok=True)
        _bootstrap_planning_files(cwd, "task", name)

        main_repo = _TASKS_DIR / repo
        if main_repo.exists():
            subprocess.run(
                ["git", "-C", str(main_repo), "worktree", "add", cwd, "-b", name],
                capture_output=True,
            )

        with self._lock:
            color = self._next_color()
        session_name = f"{repo}-{name}"
        s = Session(name=session_name, cwd=cwd,
                    session_id=str(uuid.uuid4()), color=color, kind="tasks")
        with self._lock:
            self._sessions.append(s)

        if ticket_id:
            link_session(ticket_id, session_name)
            self._features = load_features()

        _open_session(s, resume=False)
        self._switch_tab("tasks")
        self._render_sessions()

    def _new_tool(self) -> None:
        name = simpledialog.askstring("New tool session", "Name:", parent=self._root)
        if name and name.strip():
            self._create_session("tool", name.strip(), cwd=str(_TOOLS_DIR / name.strip()))

    def _new_review(self) -> None:
        from tkinter import messagebox
        url = simpledialog.askstring("New review session", "GitHub PR URL:", parent=self._root)
        if not url or not url.strip():
            return
        parsed = _parse_github_pr_url(url.strip())
        if not parsed:
            messagebox.showerror("Invalid URL",
                                 "Could not parse URL.\nExpected: https://github.com/Owner/repo/pull/1234",
                                 parent=self._root)
            return
        full_repo, short_name, pr_number = parsed
        self._create_review_session(full_repo, short_name, pr_number)

    def _create_review_session(self, full_repo: str, short_name: str, pr_number: str) -> None:
        import uuid
        name = f"{short_name}-PR-{pr_number}"
        cwd  = str(_REVIEWS_DIR / name)
        Path(cwd).mkdir(parents=True, exist_ok=True)
        _bootstrap_planning_files(cwd, "review", name, repo=full_repo, pr=pr_number)

        local_repo = Path.home() / "IdeaProjects" / short_name
        if local_repo.exists():
            subprocess.run(
                ["git", "-C", str(local_repo), "worktree", "add", cwd,
                 "--detach"],
                capture_output=True,
            )

        with self._lock:
            color = self._next_color()
        s = Session(name=name, cwd=cwd, session_id=str(uuid.uuid4()), color=color, kind="reviews")
        with self._lock:
            self._sessions.append(s)
        _open_session(s, resume=False)
        self._switch_tab("reviews")
        self._render_sessions()

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
            self._switch_tab(_session_kind(s))
            self._render_sessions()

    def _next_color(self) -> str:
        palette = list(USER_COLORS.keys())
        used = {s.color for s in self._sessions if s.color}
        for c in palette:
            if c not in used:
                return c
        return palette[len(self._sessions) % len(palette)]

    def _create_session(self, mode: str, name: str,
                        cwd: str | None = None,
                        repo: str | None = None,
                        pr: str | None = None) -> None:
        import uuid
        if cwd is None:
            cwd = str(Path.home() / "research" / name)
        Path(cwd).mkdir(parents=True, exist_ok=True)
        _bootstrap_planning_files(cwd, mode, name, repo=repo, pr=pr)
        with self._lock:
            color = self._next_color()
        kind = "tasks" if mode == "task" else (mode + "s" if not mode.endswith("s") else mode)
        s = Session(name=name, cwd=cwd, session_id=str(uuid.uuid4()), color=color, kind=kind)
        with self._lock:
            self._sessions.append(s)
        _open_session(s, resume=False)
        self._switch_tab(kind)
        self._render_sessions()

    def _execute_command(self, cmd: dict) -> dict:
        action = cmd.get("action", "")
        if action == "list":
            return {"sessions": [{"name": s.name, "state": s.state.value} for s in self._sessions]}
        elif action in ("new-research", "new-tool"):
            mode = action.replace("new-", "")
            name = cmd.get("name", "session")
            cwd = str(_TOOLS_DIR / name) if mode == "tool" else None
            self._root.after(0, lambda m=mode, n=name, c=cwd: self._create_session(m, n, cwd=c))
            return {"ok": True}
        elif action == "new-task":
            repo = cmd.get("repo")
            name = cmd.get("name")
            if not repo or not name:
                return {"error": "repo and name required"}
            ticket = cmd.get("ticket")
            self._root.after(0, lambda r=repo, n=name, t=ticket:
                             self._create_task_session(r, n, t))
            return {"ok": True}
        elif action == "new-feature":
            ticket = cmd.get("ticket")
            nickname = cmd.get("nickname", "")
            description = cmd.get("description", "")
            if not ticket:
                return {"error": "ticket required"}
            create_feature(ticket, nickname, description)
            self._features = load_features()
            self._features_expanded.add(ticket)
            self._root.after(0, lambda: (self._switch_tab("features"), self._render_sessions()))
            return {"ok": True}
        elif action == "new-review":
            url = cmd.get("url", "")
            parsed = _parse_github_pr_url(url)
            if not parsed:
                return {"error": f"invalid GitHub PR URL: {url}"}
            full_repo, short_name, pr_number = parsed
            self._root.after(0, lambda f=full_repo, s=short_name, p=pr_number:
                             self._create_review_session(f, s, p))
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
                    kind = _session_kind(s)
                else:
                    kind = None
            if kind:
                self._root.after(0, lambda k=kind: self._switch_tab(k))
            self._root.after(0, self._render_sessions)
            return {"ok": True}
        elif action == "feature-status":
            ticket = cmd.get("ticket")
            if not ticket:
                return {"error": "ticket required"}
            feat = next((f for f in self._features if f.ticket_id == ticket), None)
            if not feat:
                return {"error": f"feature not found: {ticket}"}
            with self._lock:
                sessions_by_name = {s.name: s for s in self._sessions}
            return {
                "ticket": feat.ticket_id,
                "description": feat.description,
                "sessions": [
                    {
                        "name": sn,
                        "state": sessions_by_name[sn].state.value if sn in sessions_by_name else "not_loaded",
                    }
                    for sn in feat.sessions
                ],
            }
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
            _open_session(s, resume=False)

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
