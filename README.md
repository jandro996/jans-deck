# jans-deck

A macOS GUI for managing multiple concurrent Claude Code sessions. Shows all sessions in a sidebar with live state indicators, lets you focus any session with one click, and integrates with iTerm2 for tab coloring and voice control.

---

## Features

**Session management**
- Session list organized in tabs: Tasks, Research, Tools, Reviews, Features
- Create sessions with scaffolding: `task_plan.md`, `progress.md`, `session.md` bootstrapped automatically
- Task sessions create a git worktree in `~/tasks/<repo>-<name>/`; research sessions create `~/research/<name>/`
- Feature manifests link related sessions to a ticket ID (e.g. `APPSEC-63000`)

**State indicators**

| State | Icon | Color | Meaning |
|-------|------|-------|---------|
| `processing` | ▶ | yellow | Claude is actively running |
| `waiting` | ● | green | Claude is waiting for user input |
| `needs_input` | ⚡ | red | Tool use requires approval |
| `unread` | ◎ | orange | Finished since you last looked — click to clear |
| `paused` | ◉ | blue | No active Claude process |
| `terminated` | ✗ | grey | Process ended |

The **unread** state persists until you click the session in jans. If you focus the session directly in iTerm2, the state clears on the next tick (≤3s).

**iTerm2 integration**
- Tab color matches the session's state color, updated every tick
- Focus any session via jans click → the correct iTerm2 tab comes to front (matched by tty, not tab title)
- User-defined color tags (red, orange, yellow, green, blue, purple, pink, teal) persist across restarts

**Persistence and external edits**
- State saved to `~/.jans/state.json` every 3s
- External edits to `state.json` (e.g. from scripts) are detected by mtime and merged within one tick — jans does not overwrite them
- Sessions deleted from `state.json` externally are removed from the GUI (with a safety guard: active sessions are never auto-removed during a concurrent write race)

**Voice control**
- Dictate to the orchestrator Claude session using Wispr Flow (paste mode)
- Claude calls `jans-ctl` commands based on what you say
- Example: "open a research session about gRPC timeouts" → `jans-ctl new-research grpc-timeouts`

---

## Installation

Requirements: macOS, Python 3.12+, iTerm2.

> **Important:** tkinter is not included in Homebrew's Python. Install Python from [python.org](https://www.python.org/downloads/) or via `pyenv` with the framework build:
> ```bash
> env PYTHON_CONFIGURE_OPTS="--enable-framework" pyenv install 3.12
> ```

```bash
git clone https://github.com/your-username/jans-deck ~/research/jans
cd ~/research/jans
python3 -m venv .venv-menu
source .venv-menu/bin/activate
pip install -e .
```

Add a launcher to your shell profile:

```bash
alias jans="cd ~/research/jans && source .venv-menu/bin/activate && python -m jans.gui"
```

---

## Usage

### jans-ctl — programmatic and voice control

```bash
jans-ctl list                                    # list all sessions and states
jans-ctl new-research <name>                     # ~/research/<name>/
jans-ctl new-task <repo> <name> [ticket]         # ~/tasks/<repo>-<name>/ (git worktree)
jans-ctl new-tool <name>                         # ~/tools/<name>/
jans-ctl new-review <github-pr-url>              # ~/reviews/<repo>-pr-<n>/
jans-ctl new-feature <ticket> <nickname> [desc]  # feature manifest in KB
jans-ctl feature-status <ticket>                 # show sessions linked to a ticket
jans-ctl rename <current> <new>                  # rename a session
jans-ctl delete <name>                           # remove from jans (never deletes files)
jans-ctl color <name> <color>                    # set color tag
jans-ctl switch <name>                           # bring session to front in GUI
```

### Orchestrator

jans runs a Claude Code session in `~/research/jans/` that acts as orchestrator. It reads `CLAUDE.md` (which explains `jans-ctl`) and can control all other sessions on your behalf via voice or text.

---

## Architecture

```
jans/
├── gui.py              # tkinter main window (JansApp)
├── ctl.py              # jans-ctl CLI — IPC via ~/.jans/pending_cmd.json
├── models.py           # Session dataclass, SessionState enum
└── core/
    ├── state_detector.py  # detects session state from ~/.claude/ files
    ├── persistence.py     # save/load ~/.jans/state.json with mtime-based merge
    └── commands.py        # IPC: write/read ~/.jans/pending_cmd.json + cmd_result.json
```

**IPC:** `jans-ctl` writes `~/.jans/pending_cmd.json`; the GUI reads it on the next 3s tick and writes the result to `~/.jans/cmd_result.json`.

**state.json format:** flat JSON list of `{name, cwd, session_id, color, kind}`.

---

## State detection

On each tick, `state_detector.py` finds the live Claude session for a given `cwd`:

1. Scans `~/.claude/sessions/*.json` for the entry whose `cwd` matches (case-insensitive, for macOS)
2. Reads the JSONL transcript at `~/.claude/projects/<project>/<session-id>.jsonl`
3. Classifies state:

| Criterion | State |
|-----------|-------|
| Last JSONL entry is `tool_use` with no matching `tool_result` | `needs_input` |
| Last JSONL entry is `assistant`, quiet > 15s | `waiting` |
| JSONL modified < 15s ago | `processing` |
| No live Claude process for this cwd | `paused` |

**iTerm2 tab detection:** a session is considered open (not paused) when its Claude process's tty appears in an iTerm2 tab. Detected via AppleScript + `ps`. This is more reliable than matching tab titles, which Claude Code overwrites dynamically.

**session_id sync:** jans stores session IDs in `state.json`. On each tick, the live session ID is resolved from `~/.claude/sessions/` by cwd and updated if it changed (e.g. after `claude --continue`).

**Unread tracking:** when a session transitions from `processing`/`waiting`/`needs_input` to `paused`, it is added to `self._unread` (in-memory set). Cleared on click. Not persisted — restarting jans clears all unread indicators.
