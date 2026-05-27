# jans

Terminal dashboard for managing Claude Code sessions. Single-window TUI with session list on the left and an orchestrator Claude on the right.

## What it does

- **Left panel**: list of Claude sessions with state (processing / waiting / terminated / paused) and time since last activity
- **Right panel**: embedded Claude session (the orchestrator) running in a tmux pane
- **Session creation**: F2 for new research session, F3 for new task session
- **Persistence**: saves session state on exit, restores paused sessions on next open (`~/.jans/state.json`)
- **Tab title**: sets terminal tab to "jans" on launch

## Shortcuts

| Key | Action |
|-----|--------|
| `F2` | New research session (creates `~/research/<name>/`) |
| `F3` | New task session |
| `ctrl+h` | Go back to orchestrator (home) |
| `ctrl+q` | Save state and quit |
| click | Open/resume a session |

## Architecture

```
~/research/jans/
├── jans/
│   ├── __main__.py          # entry point, sets tab title
│   ├── app.py               # main Textual app (HelmApp)
│   ├── models.py            # Session dataclass, SessionState enum
│   ├── core/
│   │   ├── log.py           # persistent logging to ~/.jans/jans.log
│   │   ├── state_detector.py # reads ~/.claude/ to detect session state
│   │   └── persistence.py   # save/load ~/.jans/state.json
│   └── widgets/
│       ├── session_list.py  # left panel - Static-based, no DOM flicker
│       └── terminal_widget.py # right panel - tmux-backed terminal
└── pyproject.toml
```

**State detection** reads `~/.claude/sessions/<pid>.json` and `~/.claude/projects/<project>/<session-id>.jsonl`:
- Modified < 15s ago → `processing`
- Last message `assistant` + quiet > 15s → `waiting`
- PID dead → `terminated`
- Loaded from previous run → `paused`

Key bug fixed: Claude Code replaces both `/` and `.` with `-` in project directory names. Our path construction must do the same (`cwd.replace("/", "-").replace(".", "-")`).

**Terminal widget** uses tmux (`jans-<id>` sessions) + `tmux capture-pane -e` + `Text.from_ansi()` for rendering. Input via `tmux send-keys`.

**Session list** renders as a single `Static` with Rich text (no ListView DOM) to avoid flicker on 3s refresh.

## Known issues / decisions

- External Claude sessions (opened outside jans) appear in the list but can't be opened from jans (no tmux session for them)
- Clicking an external session does nothing useful - to be fixed (filter or mark as external)
- Terminal rendering ("rayas") - Claude Code's own separator lines are more visible inside jans than in a regular terminal. Not a rendering bug.
- The orchestrator Claude starts in `~/research/jans/` (default cwd). Consider starting it in `~/research/` instead.

## Backlog

### High priority
- [ ] Filter external sessions (not created by jans) from the list, or mark them clearly as read-only
- [ ] Clicking a session should focus the right panel on that session's terminal
- [ ] Resume paused sessions properly (currently calls `claude --resume <id>` but external sessions won't have a tmux pane)

### Medium priority
- [ ] Session branching: `claude --resume <id> --fork-session` to fork a session at its current point
- [ ] launchd hook to save state on system shutdown (not just on jans exit)
- [ ] Sound/visual notification when a session changes state (e.g. goes from processing to waiting)
- [ ] Session naming: allow renaming sessions from within jans
- [ ] Show session type badge (research vs task)

### Low priority / ideas
- [ ] Search/filter sessions by name or directory
- [ ] Session log view: show last N messages from a session's `.jsonl`
- [ ] Multi-repo support: sessions from different repos grouped visually
- [ ] Local model support (Ollama) for the orchestrator

## Installation

```bash
cd ~/research/jans
pip install -e .
jans
```

Dependencies: `textual`, `pyte` (unused now but installed), `ptyprocess` (unused now), `watchfiles` (unused now). Only `textual` and `tmux` are actually needed.

Requires tmux: `brew install tmux`

## State files

| Path | Purpose |
|------|---------|
| `~/.jans/state.json` | Saved sessions (persists across restarts) |
| `~/.jans/jans.log` | Application log (DEBUG level) |
| `~/.claude/sessions/*.json` | Claude Code session registry (read-only) |
| `~/.claude/projects/<key>/<id>.jsonl` | Conversation history per session (read-only) |
