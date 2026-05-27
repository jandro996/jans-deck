# jans

Terminal dashboard for managing Claude Code sessions. Single-window TUI: session list on the left, embedded Claude terminal on the right.

## What it does

- **Left panel**: session list with state indicators, time since last activity, and a `◈ jans Claude` button to return to the orchestrator
- **Right panel**: embedded tmux-backed terminals, scrollable (500 lines history), supports Wispr Flow via paste mode
- **Orchestrator**: Claude starts embedded in the right panel, reads `CLAUDE.md` automatically, controlled via `jans-ctl`
- **Voice control**: Wispr Flow works in paste mode — dictate to the orchestrator Claude which calls `jans-ctl` commands
- **Session creation**: F2 research, F3 task, F4 load existing directory (with nickname)
- **Persistence**: sessions saved on `ctrl+q` or SIGTERM; Claude processes keep running in background when jans closes; reconnects on reopen
- **Session naming**: give sessions a nickname on load (F4), rename anytime with F8

## Shortcuts

| Key | Action |
|-----|--------|
| `F1` | Help (all shortcuts) |
| `F2` | New research session (creates `~/research/<name>/`) |
| `F3` | New task session |
| `F4` | Load existing directory (with optional nickname) |
| `F5` / `F6` | Narrow / widen left panel |
| `F7` | Delete hovered session (kills process) |
| `F8` | Rename hovered session |
| `ctrl+h` | Go to orchestrator panel |
| `ctrl+q` | Save state and quit (keeps processes running) |
| click | Open / resume a session |
| `◈ jans Claude` | Click to go to orchestrator (same as ctrl+h) |

## Architecture

```
~/research/jans/
├── CLAUDE.md                # orchestrator system prompt (auto-loaded by Claude Code)
├── ORCHESTRATOR.md          # extended orchestrator context
├── jans/
│   ├── __main__.py          # entry point, tab title, signal handlers
│   ├── app.py               # main Textual app (HelmApp)
│   ├── models.py            # Session dataclass, SessionState enum
│   ├── ctl.py               # jans-ctl CLI for voice/programmatic control
│   ├── core/
│   │   ├── log.py           # persistent logging → ~/.jans/jans.log
│   │   ├── state_detector.py # reads ~/.claude/ to detect session states
│   │   ├── persistence.py   # save/load ~/.jans/state.json
│   │   └── commands.py      # IPC via ~/.jans/pending_cmd.json for jans-ctl
│   └── widgets/
│       ├── session_list.py  # left panel — Rich text Static, no DOM flicker
│       └── terminal_widget.py # right panel — tmux-backed, scrollable
└── pyproject.toml
```

## State detection

Reads `~/.claude/sessions/<pid>.json` and `~/.claude/projects/<project>/<session-id>.jsonl`:

| State | Criterion |
|-------|-----------|
| `processing` ▶ | JSONL modified < 15s ago |
| `waiting` ● | Last message = `assistant` + quiet > 15s |
| `terminated` ✗ | PID no longer alive |
| `paused` ◉ | Loaded from previous run, not yet resumed |

**cwd matching is case-insensitive** (macOS `IdeaProjects` vs `ideaProjects`) via `Path.resolve().lower()`.

**session_id sync**: jans stores synthetic UUIDs internally; on each refresh it finds the real Claude session ID by matching `cwd` in `~/.claude/sessions/` and updates accordingly.

## Session lifecycle

- **Create** (F2/F3/F4): starts Claude in a new tmux session (`jans-term-<uuid8>`)
- **Close jans**: tmux sessions keep running, state saved to `~/.jans/state.json`
- **Reopen jans**: sessions load as `paused`; clicking reconnects to the live tmux session if still running, or starts fresh with `claude --continue`
- **F7 delete**: kills the tmux session and removes from list (never deletes files on disk)

## Voice control (Wispr Flow)

1. Configure Wispr Flow to use **paste mode** (clipboard + Cmd+V)
2. Dictate to the `◈ jans Claude` orchestrator
3. Claude reads `CLAUDE.md` and calls `jans-ctl` automatically

```bash
jans-ctl list                          # list sessions
jans-ctl new-research <name>           # create research session
jans-ctl new-task <name>               # create task session
jans-ctl load <path> [nickname]        # load directory
jans-ctl rename <current> <new>        # rename session
jans-ctl delete <name>                 # remove from jans (no file deletion)
jans-ctl switch <name>                 # switch panel to session
jans-ctl home                          # return to orchestrator
```

## Known bugs / quirks

- Terminal rendering ("rayas"): Claude Code's separator lines are more visible in the embedded widget than in a real terminal — not a jans bug
- Scroll in embedded terminal: uses `tmux capture-pane -S -500` (500 lines history); very long sessions may lose earlier output

## Backlog

- [ ] Session branching: `claude --resume <id> --fork-session`
- [ ] launchd hook to save state on macOS shutdown
- [ ] Notification (sound/visual) when a session changes from processing → waiting
- [ ] Session type badge (research / task / loaded)
- [ ] Search/filter sessions by name
- [ ] Session log view: show last N messages from `.jsonl`

## Installation

```bash
cd ~/research/jans
pip install -e .
jans
```

Requires: `textual`, `tmux` (`brew install tmux`)

## State files

| Path | Purpose |
|------|---------|
| `~/.jans/state.json` | Saved sessions (persists across restarts) |
| `~/.jans/jans.log` | Application log (DEBUG level) |
| `~/.jans/pending_cmd.json` | IPC: jans-ctl → jans app |
| `~/.jans/cmd_result.json` | IPC: jans app → jans-ctl |
| `~/.claude/sessions/*.json` | Claude Code session registry (read-only) |
| `~/.claude/projects/<key>/<id>.jsonl` | Conversation history (read-only) |
