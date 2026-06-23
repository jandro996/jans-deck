# jans-deck

A macOS sidebar GUI for managing multiple concurrent Claude Code sessions. Tracks live state, organizes sessions by type, integrates with iTerm2, and lets any Claude session control the others via CLI.

---

## What it does

You run many Claude Code sessions in parallel - one per task, research investigation, tool, or code review. jans-deck gives you a single sidebar that shows all of them at a glance: what each one is doing right now, which ones need your attention, which ones finished while you were looking elsewhere. One click brings any session to the front in iTerm2.

---

## Why

Generic session managers and terminal multiplexers give you panes and tabs. That is not the problem. The problem is that Claude Code sessions have structure that no generic tool understands:

- A session has a **state** — not just running/stopped, but processing, waiting for your reply, waiting for tool approval, or finished-but-you-haven't-looked-yet. That state lives in `~/.claude/sessions/` and the JSONL transcript, not in the terminal.
- A task session should create a **git worktree and branch** automatically, not just a directory.
- Sessions belong to **features** that span multiple repos. A ticket may have a dd-trace-java task, a system-tests task, and a research session — you want to see them grouped.
- Each session needs **scaffolding files** bootstrapped on creation: `task_plan.md`, `session.md`, `progress.md`. These are what hooks inject into Claude on every tool call.
- When a session closes, it should clean up the worktree, update the KB, and remove itself from the session list — a lifecycle, not just a tab.

jans-deck exists because these are Claude Code-specific concepts. A generic tool would need the same integration work added on top — at that point you are building jans-deck anyway.

> **Personal tool.** Built for one person's specific workflow on macOS + iTerm2 + Claude Code. It assumes a fixed directory layout (`~/tasks`, `~/repos`, `~/research`), a companion hooks and skills system, and opinionated conventions. It works well for that setup and will need adaptation for anything else.

---

## Session tabs

Sessions are organized into five tabs:

| Tab | Directory | Created by |
|-----|-----------|------------|
| **Features** | `~/.claude/knowledge/_meta/features/` | Groups sessions under a ticket ID |
| **Tasks** | `~/tasks/<repo>-<name>/` | git worktree off a repo in `~/repos/` |
| **Research** | `~/research/<name>/` | standalone dir |
| **Tools** | `~/tools/<name>/` | standalone dir |
| **Reviews** | `~/reviews/<repo>-pr-<n>/` | from a GitHub PR URL |

Each tab header shows the count of active sessions (processing + waiting + needs_input). If sessions in that tab finished while you were not looking, an unread badge appears: `◎2`.

---

## Session states

| Icon | Color | State | Meaning |
|------|-------|-------|---------|
| ▶ | yellow | `processing` | Claude is actively running |
| ● | green | `waiting` | Claude finished, waiting for your next message |
| ⚡ | red | `needs_input` | Tool use is pending your approval |
| ◎ | orange | `unread` | Finished since you last focused it - click to clear |
| ◉ | blue | `paused` | No active Claude process for this session |
| ✗ | grey | `terminated` | Process exited |

State is detected every 3 seconds by reading `~/.claude/sessions/` (live process + session ID) and the JSONL transcript at `~/.claude/projects/<key>/<session-id>.jsonl`. No hooks or modifications to Claude's config are needed.

**How state detection works:**

1. Find the live Claude process for this session's `cwd` in `~/.claude/sessions/*.json`
2. Locate the JSONL transcript using the live session ID (not the one stored in state.json, which may be stale)
3. Classify:
   - JSONL modified < 15s ago: `processing`
   - Last message is `assistant` with a pending `tool_use` and no `tool_result`: `needs_input`
   - Last message is `assistant`, quiet > 15s: `waiting`
   - No JSONL but live process found: `waiting` (tab is open, no message sent yet)
   - No live process: `paused`

---

## Unread indicator

When a session transitions from an active state (`processing`, `waiting`, `needs_input`) to `paused` while its iTerm2 tab is not in focus, it is marked as unread. The session row shows `◎` in orange instead of its normal icon, and the tab header shows `◎N` next to the count.

Clicking the session in jans clears the unread mark. Restarting jans clears all unread state (it is not persisted to disk).

---

## Features tab

The Features tab groups sessions by ticket ID. Each feature is a Markdown file in `~/.claude/knowledge/_meta/features/<TICKET>.md` with YAML frontmatter:

```yaml
---
ticket: APPSEC-63000
nickname: My Feature
description: What this feature does
sessions:
  - dd-trace-java-my-feature-impl
  - system-tests-my-feature
---
```

Clicking a feature row expands it to show its linked sessions with live state indicators. Sessions that are not currently loaded in jans (e.g. already finished and removed) can be reloaded from the feature panel - jans will locate the session directory and add it back.

Creating a new feature from the GUI or via `jans-ctl new-feature` writes this file. Linking a session to a feature (at task creation time or later) appends its name to the `sessions` list.

---

## Creating sessions

### From the GUI

Click **+ New** in any session tab. A dialog opens:

- **Task**: pick a repo from `~/repos/` (or paste a GitHub clone URL to clone it first), enter a name, optionally link to a feature ticket (pick from existing features or create a new one inline). Creates a git worktree at `~/tasks/<repo>-<name>/` and bootstraps `session.md`, `task_plan.md`, `progress.md`.
- **Research**: enter a name. Creates `~/research/<name>/` with the same scaffolding files.
- **Review**: paste a GitHub PR URL. Clones or locates the repo, creates `~/reviews/<repo>-pr-<n>/`.
- **Tool**: enter a name. Creates `~/tools/<name>/`.

### Via jans-ctl

```bash
jans-ctl new-task <repo> <name> [ticket]
jans-ctl new-research <name>
jans-ctl new-tool <name>
jans-ctl new-review <github-pr-url>
jans-ctl new-feature <ticket> <nickname> [description]
```

---

## jans-ctl — full command reference

`jans-ctl` sends commands to the running jans instance via `~/.jans/pending_cmd.json`. The GUI reads it on the next tick (≤3s) and writes the result to `~/.jans/cmd_result.json`.

```bash
jans-ctl list                                    # list all sessions and their states
jans-ctl new-research <name>                     # ~/research/<name>/
jans-ctl new-task <repo> <name> [ticket]         # ~/tasks/<repo>-<name>/ (git worktree)
jans-ctl new-tool <name>                         # ~/tools/<name>/
jans-ctl new-review <github-pr-url>              # ~/reviews/<repo>-pr-<n>/
jans-ctl new-feature <ticket> <nick> [desc]      # feature manifest in KB
jans-ctl feature-status <ticket>                 # show sessions linked to a ticket
jans-ctl load <path> [name]                      # add an existing directory as a session
jans-ctl rename <current> <new>                  # rename a session
jans-ctl delete <name>                           # remove from jans (never deletes files or kills Claude)
jans-ctl color <name> <color>                    # set color tag (red orange yellow green blue purple pink teal)
jans-ctl switch <name>                           # bring session to front in iTerm2
jans-ctl home                                    # focus the orchestrator session
```

---

## iTerm2 integration

- **Tab color**: each session's iTerm2 tab is colored to match its state (yellow/green/red/blue). If the session has a user-defined color tag, that takes priority.
- **Tab badge**: the session name is set as the iTerm2 badge when the tab is first focused.
- **Focus on click**: clicking a session in jans brings its iTerm2 tab to the front. Matching is done by tty device (not tab title, which Claude Code overwrites dynamically).
- **Paused detection**: a session is considered paused when its Claude process's tty is not found in any open iTerm2 tab.

---

## Color tags

Each session can have a persistent color tag that overrides the state color on the iTerm2 tab:

```
red  orange  yellow  green  blue  purple  pink  teal
```

Set via right-click context menu in the GUI or `jans-ctl color <name> <color>`.

---

## Persistence

- State is saved to `~/.jans/state.json` every 3 seconds.
- External edits to `state.json` (e.g. from a `/finish-pr` script removing a session) are detected by file mtime and merged into memory within one tick - jans never overwrites external changes.
- Sessions deleted from `state.json` externally are removed from the GUI. Safety guard: active sessions (`processing`, `waiting`, `needs_input`) are never auto-removed even if they temporarily disappear from disk during a write race.
- When a session's `cwd` changes externally, jans renames the corresponding `~/.claude/projects/` directory automatically to preserve conversation history.

---

## Orchestrator pattern

jans runs a Claude Code session in `~/research/jans/` that acts as orchestrator. It has `jans-ctl` available and a `CLAUDE.md` that explains how to use it. You can dictate to it (e.g. via Wispr Flow) and it will create sessions, check status, and route work across all your other sessions on your behalf.

Example: say "open a task for dd-trace-java on the gRPC timeout fix linked to APPSEC-99001" and the orchestrator runs:

```bash
jans-ctl new-task dd-trace-java grpc-timeout-fix APPSEC-99001
```

---

## Architecture

```
jans/
├── gui.py              # tkinter main window (JansApp) - 3s tick loop
├── ctl.py              # jans-ctl CLI entry point
├── models.py           # Session dataclass, SessionState enum
└── core/
    ├── state_detector.py   # reads ~/.claude/sessions/ + JSONL to classify state
    ├── persistence.py      # save/load ~/.jans/state.json, mtime-based merge, project dir migration
    ├── commands.py         # IPC: write/read ~/.jans/pending_cmd.json + cmd_result.json
    ├── features.py         # read/write ~/.claude/knowledge/_meta/features/*.md
    └── log.py              # rotating file logger at ~/.jans/jans.log
```

**Directory layout at runtime:**

```
~/
├── research/jans/          # jans source + orchestrator session cwd
├── repos/                  # bare or full git repos (sources for worktrees)
├── tasks/<repo>-<name>/    # task worktrees
├── research/<name>/        # research sessions
├── tools/<name>/           # tooling sessions
├── reviews/<repo>-pr-<n>/  # PR review sessions
└── .jans/
    ├── state.json           # persisted session list
    ├── pending_cmd.json     # IPC: jans-ctl -> GUI
    ├── cmd_result.json      # IPC: GUI -> jans-ctl
    └── jans.log             # debug log
```

---

## Installation

Requirements: macOS, Python 3.12+, iTerm2.

> tkinter is not included in Homebrew Python. Use python.org or pyenv with framework build:
> ```bash
> env PYTHON_CONFIGURE_OPTS="--enable-framework" pyenv install 3.12
> ```

```bash
git clone git@github.com:jandro996/jans-deck.git ~/research/jans
cd ~/research/jans
python3 -m venv .venv-menu
source .venv-menu/bin/activate
pip install -e .
```

Start jans:

```bash
~/research/jans/.venv-menu/bin/python3 -m jans.gui &
```

Restart after code changes:

```bash
pkill -f "python.*jans.gui"; sleep 1
~/research/jans/.venv-menu/bin/python3 -m jans.gui &
```
