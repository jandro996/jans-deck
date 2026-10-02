# Jans app analysis (partial 01)

Scope: the Jans session manager in `~/research/jans` (branch `main`, commit `e5f9f49`). All facts come from the code. Line numbers refer to that commit. The `web/` directory named in the task does not exist on `main`: it exists only on the `web-app` branch (an abandoned FastAPI experiment, see `DEVELOPMENT.md:28`).

## 1. Summary

- Jans is a macOS tool that lists many Claude Code sessions, shows their live state, and opens them in iTerm2. The tool in daily use is the tkinter window `jans/gui.py` (1816 lines).
- A Claude Code session in `~/research/jans` is the "orchestrator". It controls Jans through `jans-ctl`, which talks to the GUI with two JSON files in `~/.jans/`.
- Jans has no database. State is `~/.jans/state.json`, Claude's own files (`~/.claude/sessions`, `~/.claude/projects/*.jsonl`) and a hook marker (`~/.claude/executing`).
- Three older front ends (Textual TUI, menu bar, `web-app` branch) remain in the tree. They are stale and support fewer commands than the GUI.
- The code is tied to macOS, iTerm2, AppleScript and Claude Code internals. Migration to another tool needs a rewrite of the detector, the launcher and the IPC.

## 2. Components

### 2.1 Entry points and packaging (`pyproject.toml`, `__main__.py`, `make_app.py`, `jans-menu.sh`)

- Purpose: start the right front end.
- `pyproject.toml:5-20`: Python >= 3.12, build backend hatchling. Dependencies: `textual`, `pyte`, `ptyprocess`, `watchfiles`, `rumps`. Scripts: `jans` = `jans.__main__:main` (Textual TUI), `jans-ctl` = `jans.ctl:main`, `jans-menu` = `jans.menubar:main`, `jans-gui` = `jans.gui:main`. tkinter is not listed (it ships with Python). `pyte`, `ptyprocess` and `watchfiles` are imported nowhere in `jans/`.
- `jans/__main__.py:10-40`: sets the tab title, builds `HelmApp`, saves sessions on SIGTERM and SIGINT, runs the Textual app.
- `make_app.py:10-52`: builds `~/Applications/jans.app`. The launcher script runs `~/research/jans/.venv-menu/bin/python3 ~/research/jans/jans/gui.py`. Paths are hard coded (`make_app.py:10-12`). `LSUIElement` is false, so the app shows in the Dock.
- `jans-menu.sh:3`: runs `menubar.py` with the same venv.
- Inputs: none. Outputs: the `.app` bundle. Files read: `jans.icns` (`make_app.py:55`). `make_icon.py` builds the icon (not analysed).

### 2.2 GUI (`jans/gui.py`) - the production front end

- Purpose: one narrow tkinter window with five tabs (`features`, `research`, `tasks`, `tools`, `reviews`; `gui.py:69-70`). Each row is a session: state icon, name, age, cwd, last progress line, user colour chip.
- Loop: `_tick` every 3000 ms (`gui.py:495`, `1138-1148`): reload feature manifests, merge external edits of `state.json`, `_refresh` (state detection, iTerm2 side effects, IPC command), save `state.json`. A second loop `_focus_poll` runs every 1000 ms and raises the window when iTerm2 comes to the front (`gui.py:1788-1793`).
- Inputs: `~/.jans/state.json`, `~/.jans/pending_cmd.json`, `~/.claude/sessions/*.json`, `~/.claude/projects/<key>/<id>.jsonl`, `~/.claude/executing/*`, `<cwd>/progress.md`, `~/.claude/knowledge/_meta/features/*.md`, `~/.claude/knowledge/_meta/skills-quickref.md` (help window, `gui.py:805`).
- Outputs: `state.json`, `cmd_result.json`, `~/.jans/jans.log`, session directories and scaffold files, git worktrees, iTerm2 tabs, escape sequences written to the tty of each Claude process (tab colour, badge, title; `gui.py:376-396`).
- External commands: `osascript` (iTerm2 control, frontmost app), `ps -o tty=`, `git` (fetch, worktree add, clone), `gh pr view`.
- Session classification (`_session_kind`, `gui.py:73-84`): the stored `kind` wins; otherwise the cwd prefix decides (`~/reviews`, `~/tools`, `~/tasks`, else `research`).
- Opening a session (`_open_session`, `gui.py:333-365`): it asks iTerm2 to create a tab and to type `cd '<cwd>' && claude [--continue]`. `--continue` is used only when `~/.claude/projects/<key>` exists. Nothing else is passed to `claude` (no model flag, no session id, no system prompt).
- Click on a row (`gui.py:973-988`): if the Claude process has a tty that is in an open iTerm2 tab, focus that tab; otherwise open a new tab.
- Delete from the GUI (right-click, `gui.py:990-996`, `1152-1169`): removes the session and runs `shutil.rmtree(session.cwd)` after a confirm dialog.
- Unread marker (`gui.py:1020-1037`): a session whose iTerm2 tab disappeared while Claude is still alive gets `◎`. It lives in memory only.
- Dependencies: `core/*`, `models.py`, tkinter, macOS, iTerm2.

### 2.3 CLI (`jans/ctl.py`) and IPC (`jans/core/commands.py`)

- Purpose: let a Claude session (or a human) control the running GUI.
- Mechanism (`commands.py:11-23`): `send_command` deletes `~/.jans/cmd_result.json`, writes `{"action": ..., **args}` to `~/.jans/pending_cmd.json`, polls for the result file every 50 ms and gives up after 5 s with `jans is not running or not responding`. The GUI reads the command inside `_refresh` (`gui.py:1080-1082`), so latency is up to one tick (3 s) plus the time of the refresh. The GUI deletes the command file, runs the action and writes the result (`commands.py:26-39`).
- Output: the result dict printed as indented JSON. An `error` key prints `Error: ...` on stderr and exits 1 (`ctl.py:128-132`). No arguments prints usage and exits 1. An unknown command prints `Unknown command: X` plus usage and exits 1.
- Name rule (`ctl.py:13-19`, `features.py:6-18`): `name`, `repo` and `ticket` must match `^[A-Za-z0-9._-]+$` for `new-research`, `new-task`, `new-tool`, `new-feature` (ticket only). Other commands are not validated by the CLI.

Reference table. Source of truth is `usage()` (`ctl.py:22-40`); the GUI handler is `JansApp._execute_command` (`gui.py:1635-1761`).

| Command | Arguments | CLI checks | Side effects in the GUI handler |
|---|---|---|---|
| `list` | none | none | Returns `{"sessions": [{name, state}]}` (`gui.py:1637-1638`). No cwd. |
| `new-research` | `<name> [ticket]` | name and ticket valid | Creates `~/research/<name>/`, scaffold (see 2.6), a feature manifest if `ticket` is set, links the session to it, opens an iTerm2 tab (`claude`, no `--continue`), switches the GUI tab, saves state. Returns `{"ok": true}` before the work runs (`gui.py:1639-1654`, `1602-1633`). |
| `new-task` | `<repo> <name> [ticket]` | repo, name, ticket valid | Registers session `<repo>-<name>` (kind `tasks`) at once. In a thread: `git fetch origin`, `git worktree add ~/tasks/<repo>-<name> -b <name> origin/HEAD` in `~/repos/<repo>` (fallback `~/tasks/<repo>`), scaffold, iTerm2 tab. Creates and links the feature manifest if `ticket` is set (`gui.py:1464-1518`). |
| `new-tool` | `<name>` | name valid | Creates `~/tools/<name>/`, scaffold, iTerm2 tab (`gui.py:1639-1654`). |
| `new-feature` | `<ticket> <nickname> [desc]` | ticket valid; `desc` is the rest of the words joined by spaces | Writes `~/.claude/knowledge/_meta/features/<ticket>.md` if absent (`features.py:76-100`), reloads features, expands the entry (`gui.py:1667-1680`). |
| `feature-status` | `<ticket>` | none | Returns `{ticket, description, sessions: [{name, state}]}`. A linked session not loaded in Jans has state `not_loaded`. Error `feature not found: <ticket>` (`gui.py:1741-1760`). |
| `new-review` | `<url>` | none | Parses `https://github.com/<owner>/<repo>/pull/<n>` (`gui.py:91-101`). In a thread: `gh pr view` for the head ref, `git fetch pull/<n>/head`, `git worktree add --detach ~/reviews/<repo>-PR-<n>`; writes `session.md` only; registers the session only if the checkout worked (`gui.py:1544-1577`). Without a local clone it makes a plain directory. |
| `load` | `<path> [name]` | none | Adds a session for an existing directory. Name defaults to the folder name; a duplicate name is ignored but still returns ok. It does not open a terminal (`gui.py:1725-1740`). |
| `rename` | `<current> <new>` | none | Renames the session in memory. Returns ok even if `current` does not exist (`gui.py:1706-1714`). |
| `delete` | `<name>` | none | Removes the session from the list and sends SIGTERM to the Claude process of that cwd. Files stay. Returns ok even if the name does not exist (`gui.py:1690-1705`). |
| `color` | `<name> <color>` | none (the `COLORS` list at `ctl.py:10` is used only in help text) | Stores the colour string; applied to the iTerm2 tab on the next tick (`gui.py:1715-1724`). |
| `home` | none | none | The GUI has no handler: result is `{"error": "unknown: home"}` (`gui.py:1761`). Only the Textual app implements it (`app.py:435`). |
| `switch` | `<name>` | none | Same: `unknown: switch` in the GUI; Textual only (`app.py:438`). |
| `state` | none | none | Alias of `list` (`ctl.py:121-122`). |

### 2.4 State, persistence and logging (`core/persistence.py`, `models.py`, `core/log.py`)

- `models.py:5-33`: `SessionState` = `processing`, `waiting`, `needs_input`, `terminated`, `paused`. `Session` fields: `name`, `cwd`, `session_id`, `state`, `last_activity`, `pid`, `terminal_id`, `color`, `kind`.
- File `~/.jans/state.json` is a JSON list (`persistence.py:36-51`). Each entry has `name`, `cwd`, `session_id`, `last_activity` (ISO string), and, only when set, `color` and `kind` (`tasks`, `research`, `tools`, `reviews`). `pid` and `terminal_id` are never saved. Sessions in state `terminated` are dropped on save. The task text says the shape is `{name, cwd, session_id}`: that is the minimum other tools can rely on, but `last_activity` is required by the reader (`persistence.py:73`).
- Read (`persistence.py:56-81`): every entry becomes `paused`. An entry whose `pid` value is not null is skipped as "external" (`persistence.py:65-67`, test `d.get("pid") is not None`); an entry with no `pid` key or `pid: null` is loaded. `save_sessions` never writes `pid`. Any exception returns an empty list.
- Write: `Path.write_text` (not atomic) at startup of each tick, on close and after every list change (`gui.py:1086-1095`, `1145`). The GUI stores the file mtime after each write. On every tick `_merge_external_sessions` (`gui.py:1097-1136`) compares the mtime; if it is newer, it adds sessions that appear only on disk, applies cwd changes (and renames `~/.claude/projects/<key>`, `persistence.py:21-33`), and removes in-memory sessions that vanished from disk unless they are active. Identity is the session `name`.
- Other writers: skills such as `/finish-pr` edit `state.json` directly to drop sessions (README `Persistence`). The GUI then reconciles by name.
- `core/log.py`: one `FileHandler` at DEBUG level to `~/.jans/jans.log`, created at import time (`log.py:23`). No rotation.

### 2.5 State detection (`core/state_detector.py`)

- Purpose: classify each session without hooks inside Claude, using files Claude writes.
- Steps for each session (`detect_state`, `state_detector.py:91-129`):
  1. If a `pid` is set and dead: `terminated`.
  2. Find the live Claude session for the cwd: scan every `~/.claude/sessions/*.json`, match `cwd` case-insensitively after `resolve()`, skip dead pids, take the newest file (`state_detector.py:169-190`). Fields used: `cwd`, `pid`, `sessionId`.
  3. No live process and the cwd directory is gone: `terminated` (so `save_sessions` drops it).
  4. Find `~/.claude/projects/<cwd with / and . replaced by ->/<sessionId>.jsonl`. No file: `waiting` if a live process exists, else `paused`.
  5. File mtime younger than 5 s (`PROCESSING_THRESHOLD_SECS`, line 12): `processing`.
  6. Read the whole JSONL. If the last assistant message has a `tool_use` with no later `tool_result`: `processing` when a marker `~/.claude/executing/<cwd with / as __>` is younger than 15 min, else `needs_input` (`state_detector.py:121-124`).
  7. Last message type `assistant`: `waiting`. Anything else: `processing`.
- The GUI wraps this (`gui.py:1007-1084`): a session with no iTerm2 tab whose tty matches the Claude pid is forced to `paused`. The tty comes from `ps -o tty=` and the open ttys from AppleScript.
- Last progress line (`_read_last_progress`, `gui.py:295-313`): reads `<cwd>/progress.md`, takes the last line that starts with `[`. Green if it contains `done` and no arrow; blue if it contains `next →`; dim otherwise. Shown as the row subtitle (the "session subtitle" described in the integration guide).

### 2.6 Session types and scaffolds (`_bootstrap_planning_files`, `gui.py:176-291`)

Files are written only if absent (`gui.py:187-190`).

| Type (CLI / tab) | Directory | `session.md` frontmatter | Other files |
|---|---|---|---|
| research (`new-research`, `research`) | `~/research/<name>/` | `type: research`, `related_projects` (list or `[]`), `investigation: <name>`, `feature: "<ticket>"` or `"standalone"`, `contribution_targets: []` | `task_plan.md` (workflow reference, no TODOs), `findings.md` (headings: Invariants discovered, Patterns and non-obvious behavior, PR review rules, Open questions), `progress.md` (`# Progress: <name>`) |
| task (`new-task`, `tasks`) | `~/tasks/<repo>-<name>/` (git worktree) | `type: task`, `related_projects: []`, `feature: "<ticket>"` or `""`, `contribution_targets: []` | `task_plan.md` (phase 0 to 6 reference), `progress.md` |
| tool (`new-tool`, `tools`) | `~/tools/<name>/` | `type: tooling`, `related_projects: [_meta]`, `contribution_targets: [_meta/workflow.md]` | `task_plan.md`, `findings.md` (`# Findings: <name>`), `progress.md` |
| review (`new-review`, `reviews`) | `~/reviews/<repo>-PR-<n>/` (detached worktree) | `type: pr-review-incoming`, `repo: <owner/repo>`, `pr: <n>` | none. This is on purpose: no `task_plan.md` means the hook injector is a no-op. |
| load (`load`, GUI "Load") | any existing directory | none | none. Kind is guessed from the cwd prefix. |

- `decisions.md`, `task_coding_rules.md`, `.claude-invariants.md` and `.session-model` are not created by Jans. `/pre-code` and the hook create them.
- Each new session gets a colour: the first unused colour of the eight (`_next_color`, `gui.py:1594-1600`).
- The session name is the directory name for research and tool, and `<repo>-<name>` for tasks. For reviews it is `<repo>-PR-<n>` (the integration guide uses `pr-<n>` in places).

### 2.7 Feature manifests (`core/features.py`)

- Purpose: group sessions of several repos under one ticket. Files: `~/.claude/knowledge/_meta/features/<TICKET>.md`.
- `create_feature` (`features.py:76-100`): validates the ticket, creates the directory, writes `ticket`, `nickname`, `description`, `sessions: []` and a title. It never overwrites an existing file. An empty nickname becomes the ticket id.
- `link_session` (`features.py:105-122`): appends `  - <session name>` under `sessions:`. It is called by `new-research` and `new-task` when a ticket is given. It returns False silently when the manifest is missing, which is why the creators call `create_feature` first.
- `load_features` (`features.py:55-72`) reads `ticket`, `nickname`, `description`, `sessions` with a hand-made frontmatter parser (`features.py:28-52`). It ignores all other keys, including `related_features`, `sub_features` and `type`, which other layers use.
- The GUI Features tab shows `n_active/total` per feature and, when expanded, each linked session with its state or `load` for sessions not in Jans (`gui.py:612-690`, `769-783`).
- The hook `inject-plan.sh:48-55` reads `feature:` from `session.md` and injects the same manifest, so `session.md` and the manifest `sessions:` list are two halves of one link, written by Jans at creation time.

### 2.8 Legacy Textual TUI (`app.py`, `widgets/`) and menu bar (`menubar.py`)

- `app.py` (`HelmApp`, 703 lines): Textual TUI with an embedded terminal per session. `widgets/terminal_widget.py` runs each Claude inside a tmux session and polls `tmux capture-pane`. `app.py:360` starts the orchestrator as `claude` in the Jans directory. Resume uses `claude --continue` (`app.py:541`). New research sessions pass `--append-system-prompt "You are a research agent..."` (`app.py:581`). It polls the command file every 0.5 s (`app.py:369`) and supports only `list`, `new-research`, `new-task`, `load`, `rename`, `delete`, `home`, `switch` (`app.py:386-448`). A `new-task` there creates a plain research-style directory with no worktree and no scaffold (`app.py:560-588`).
- `menubar.py` (`JansMenuBar`, rumps): a menu bar list of sessions grouped by state. It supports `list`, `new-research`, `new-task`, `delete`, `rename` (`menubar.py:270-296`). `new-task` creates `~/research/<name>`.
- Both write the same `state.json` and `cmd` files, so running one of them at the same time as the GUI creates a second consumer of the same IPC files.
- `JANS.md` documents this TUI as the current design. `README.md` and `DEVELOPMENT.md` document the tkinter GUI. `main` contains all three.

### 2.9 Orchestrator and channel rule (`CLAUDE.md`, `ORCHESTRATOR.md`, `JANS.md`, `DEVELOPMENT.md`)

- `CLAUDE.md` (auto-loaded by Claude Code in `~/research/jans`) is the orchestrator prompt: run `jans-ctl list` at start, execute session actions at once, ask only before `delete`, kebab-case names, a Spanish dictation table, and the command list. It imports the integration guide with `@/Users/alejandro.gonzalez/research/manus/claude-integration-guide.md`.
- The GUI header opens the orchestrator: `_open_jans_session` (`gui.py:1763-1786`) opens or focuses the session with cwd `_JANS_CWD = ~/research/jans` (`gui.py:63`), which is the production checkout. The orchestrator session is hidden from the list (`gui.py:854`).
- `ORCHESTRATOR.md` and `JANS.md` are older orchestrator and design texts (see findings).
- Channel rule (`CLAUDE.md`, "Changing Jans itself"): `~/research/jans` on `main` is production. Work happens in `~/research/jans-impl` on `dev`, then `dev` is merged into `main` with a real merge. State on 2026-10-02: `main` is `e5f9f49`, `dev` is `05e08ff`. They hold the same commit message ("gui: force window to front on startup") under two hashes. `git merge-base` is `cd9d41b`. `git log dev..main` lists `ca9c0ae`, `94afd5e` and `e5f9f49`; `git log main..dev` lists `05e08ff`. `git diff main dev` shows only a rewording of the channel rule in `CLAUDE.md` (8 lines).

### 2.10 Dependencies on Claude Code

| Dependency | Where | Use |
|---|---|---|
| `claude` CLI, `claude --continue` | `gui.py:338`, `app.py:541` | Start or resume a session in a cwd. No `--resume <id>`, because Jans session ids are synthetic UUIDs (`app.py:538-540`). |
| `~/.claude/sessions/*.json` (`cwd`, `pid`, `sessionId`) | `state_detector.py:9,137-190` | Find the live process and the real session id. |
| `~/.claude/projects/<cwd with / and . as ->/<id>.jsonl` | `state_detector.py:41-48`, `persistence.py:12-14` | Transcript for state detection; directory renamed when a cwd changes (`persistence.py:21-33`). |
| JSONL record schema (`type`, `message.content[]`, `tool_use`, `tool_result`) | `state_detector.py:51-88` | Pending permission detection. |
| `~/.claude/executing/<cwd>` marker | `state_detector.py:11,18-30` | Written by hook `inject-plan.sh pretool`, removed by posttool and stop. Separates "tool running" from "tool waits for approval". |
| `CLAUDE.md` auto-load | `~/research/jans/CLAUDE.md` | Makes the orchestrator. |
| `~/.claude/knowledge/_meta/features/`, `skills-quickref.md` | `features.py:7`, `gui.py:805` | Feature manifests and help window. |
| Planning files (`task_plan.md`, `progress.md`, `session.md`) | `gui.py:176-291` | Created so hooks and skills have files to work on. |
| `[skill] Step N` / `next →` / `done` markers | `gui.py:295-313` | Contract with `skills/CONVENTIONS.md` for the subtitle. |

## 3. Interactions with the other layers

- Hooks: Jans reads one hook artefact, `~/.claude/executing/<cwd>`. The hook writes it in `pretool` mode for every session, before the `task_plan.md` check (`inject-plan.sh:14-23`), so it also works for review sessions. Jans creates `task_plan.md` for research, task and tool sessions, which turns the injector on for them. It does not create `task_plan.md` for reviews, which keeps the injector off. The injector reads `feature:` from `session.md` (`inject-plan.sh:51`); an empty value, as in a task scaffold without a ticket, is treated as no feature.
- Knowledge base: Jans reads and writes `~/.claude/knowledge/_meta/features/*.md` and reads `skills-quickref.md`. It does not read any other KB file. `~/.claude` is a git repo with an auto-commit hook, so every manifest Jans writes is committed there.
- Skills: skills own the files Jans only scaffolds (`decisions.md`, `.claude-invariants.md`, `task_coding_rules.md`, `.session-model`) and own the `progress.md` markers Jans displays. `/finish-pr` and `/link-feature` edit `state.json` and manifests directly, so Jans must accept outside edits (the mtime merge). `task_plan.md` text in `_task_plan_content` is kept byte-identical by hand with `/start-research` and `/link-feature` (`gui.py:272-273`).
- Orchestrator: the Claude session in `~/research/jans` turns Spanish dictation into `jans-ctl` calls. It is the only consumer of the CLI that the design expects.

## 4. Findings

| type | item | evidence (file:line) | impact |
|---|---|---|---|
| drift | `switch` and `home` are documented in `CLAUDE.md`, `README.md`, `ORCHESTRATOR.md` and `JANS.md`, and in `usage()`, but the GUI has no handler. The orchestrator gets `unknown: switch` and `unknown: home`. | `CLAUDE.md:34-35`, `ctl.py:37-38`, `gui.py:1761`, `app.py:435-447` | A dictated "go to session X" fails every time. README promises iTerm2 focus (`README.md:139-140`). |
| drift | `delete` is documented as "never kills Claude" (README) and "never deletes files" (CLAUDE.md). The GUI handler sends SIGTERM to the Claude process of the cwd. | `README.md:137`, `CLAUDE.md:57`, `gui.py:1696-1701` | Deleting a session from the orchestrator ends a live Claude run, possibly with unsaved work. |
| defect | The right-click delete in the GUI runs `shutil.rmtree` on the session cwd. For a task this is a git worktree: the directory is removed and the worktree entry stays in the origin repo. For a `load`ed directory it can be a real project. | `gui.py:1152-1169` | Data loss. Contradicts "delete never removes files" in all docs. |
| defect | `load_saved_sessions` returns `[]` on any exception, including one entry without `last_activity`. In `_merge_external_sessions` an empty disk list removes every non-active session from memory. The next save then writes the shortened list. Writes are not atomic. | `persistence.py:73,79-81`, `persistence.py:51`, `gui.py:1124-1134` | One bad entry (for example from a hand or skill edit) can erase the paused sessions. |
| defect | IPC uses one fixed command file and one fixed result file with no lock or request id. Two `jans-ctl` calls at once overwrite each other; a caller can read the result of another call. After a timeout the CLI deletes the command, but the GUI may already have run it. | `commands.py:11-23` | Parallel orchestrator calls (several Bash calls in one turn) can drop or mix results. |
| defect | `new-task` registers the session and returns ok before the worktree exists. The `fetch` and `worktree add` results are not checked (`capture_output` only). If `worktree add` fails (branch name exists, no `origin/HEAD`), `mkdir` makes a plain directory and Claude starts in a non-git folder. | `gui.py:1478-1518` | Silent wrong state. The user sees a task session with no branch. |
| defect | Session names are not unique. `_create_session`, `_create_task_session` and `load` do not check for an existing name, yet name is the key for `rename`, `delete`, `color`, the state merge and the manifests. The live `state.json` has no duplicates today. | `gui.py:1602-1633`, `1725-1733`, `1097-1136` | Duplicate names make delete or rename hit several sessions and break the merge. |
| defect | `rename`, `delete` and `color` return ok for a name that does not exist, and `rename` and `color` do not validate the new value. A rename does not update the `sessions:` list in manifests or the `session.md`. | `gui.py:1706-1724`, `1690-1705` | The orchestrator reports success on a typo. Features keep the old name and show `not_loaded`. |
| defect | `link_session` treats a session as linked if the text `- <name>` appears anywhere in the file, so `foo` is "already linked" when `foo-bar` is. If the manifest has no `sessions:` line, the regex changes nothing and it still returns True. | `features.py:111-122` | Missing links in the Features tab and in hook injection. |
| defect | The manifest parser keeps trailing comments in list items. The integration guide's own example uses `- sca-reachability     # Jans name, not ...`, which gives a session name that matches nothing. | `features.py:35-36`, guide "Example 3" | A manifest written as documented shows every session as `not_loaded`. The parser also drops `related_features` and `sub_features`. |
| defect | `create_feature` silently ignores a second call for the same ticket, so `jans-ctl new-feature T nick desc` on an existing ticket returns ok and keeps the old nickname and description. `load_features` swallows all parse errors. | `features.py:84`, `features.py:70-71` | The user believes the manifest changed. A broken manifest disappears from the GUI with no log line. |
| defect | The launcher builds shell and AppleScript text from names and paths with single and double quotes and no escaping. `load` and the GUI "Load" accept any path. | `gui.py:338-364`, `ctl.py:92-98` | A path or name with `'` or `"` breaks the command or runs unintended text in the iTerm2 tab. |
| defect | `_pid_tty` compares with `"??"` twice; the second test was meant for another value. | `gui.py:430` | Cosmetic. |
| drift | State threshold: docs say 15 s, code uses 5 s. | `README.md:63-65`, `JANS.md:59-60`, `state_detector.py:12` | Docs mislead tuning and bug reports. |
| drift | `kind` comment lists `research \| task \| tool \| review`; the code stores `tasks`, `tools`, `reviews`. | `models.py:33`, `gui.py:1481,1572,1624` | Another tool reading `state.json` must accept the plural forms. 11 of 43 live entries have no `kind` at all. |
| drift | README says `log.py` is a "rotating file logger". It is a plain `FileHandler`. The live `jans.log` is 117 MB with about 960,000 lines. | `README.md:199`, `log.py:23` | Unbounded growth. |
| drift | README says the GUI saves state "every 3 seconds" and reads a command "on the next tick (3 s)". The tick does both, but the command also waits for the whole refresh, and the CLI timeout is 5 s. | `README.md:125,168`, `gui.py:1138-1148`, `commands.py:8` | Slow ticks make `jans-ctl` fail with a timeout while the command still runs later. |
| drift | `ORCHESTRATOR.md` and `JANS.md` list `new-task <name>` (one argument), no `new-tool`, `new-feature`, `feature-status`, `new-review`, `color`. They describe the Textual TUI. `CLAUDE.md` is the current prompt. `README.md` lists the CLI correctly but omits `state`. `CLAUDE.md` omits `new-review` and `state`. | `ORCHESTRATOR.md:12`, `JANS.md:84`, `ctl.py:22-40`, `CLAUDE.md:25-36` | An agent that reads the older files calls `new-task` with the wrong arguments. The orchestrator cannot discover `new-review` from its prompt. |
| obsolete | `DEVELOPMENT.md` says `main` is the TUI and `menu-bar` is the active tkinter branch. In fact `main` holds the GUI and the current work. Its backlog item "implement handler `load`" is done. | `DEVELOPMENT.md:26-28,79`, `gui.py:1725` | Wrong map of the branches. |
| obsolete | Textual TUI (`app.py`, `widgets/`, `__main__.py`), `menubar.py`, `jans-menu.sh`, the `jans` script and the dependencies `textual`, `pyte`, `ptyprocess`, `watchfiles`, `rumps` are not used by the GUI. `pyte`, `ptyprocess`, `watchfiles` are imported nowhere.  `app.py` creates no scaffold files. | `pyproject.toml:11-15`, `app.py:560-588`, `menubar.py:257-268` | Dead weight; the `jans` command still starts the old TUI, and `jans.app` starts the GUI. A user can run two front ends on the same IPC files. |
| obsolete | `web/` (named in the task) does not exist on `main`. | `git ls-files`, `DEVELOPMENT.md:28` | None; recorded so later partials do not search for it. |
| drift | The channel rule is broken now: the same fix exists on `main` (`e5f9f49`) and on `dev` (`05e08ff`) under two hashes, and `main` was not merged into `dev`. `dev` lacks three `main` commits. The rule text differs by branch. | rule: `CLAUDE.md:60-67` on `main` and `~/research/jans-impl/CLAUDE.md:60-67` on `dev` (rule text, "If a fix ever lands directly on `main` ... merging `main` into `dev`"); code: `jans/gui.py:1795-1798` (`_raise_window`, the duplicated fix); history: `git log dev..main` lists `ca9c0ae`, `94afd5e`, `e5f9f49`, `git log main..dev` lists `05e08ff` | History divergence of the kind that `95c09f3` had to repair. The orchestrator prompt differs by branch. |
| drift | The task scaffold writes `feature: ""` when no ticket is given; research writes `"standalone"`. The guide says `standalone` skips injection. Both work in the hook, but the two values differ. | `gui.py:205,232`, `inject-plan.sh:51-54` | Tools that read `session.md` must handle both. |
| drift | The guide says hooks are no-ops without `task_plan.md`. The `pretool` and `posttool` modes write and remove the executing marker before that check, for every session. | `inject-plan.sh:14-23`, guide "Key invariants" | Jans relies on this marker, so the guide's claim hides a real coupling. |
| drift | Review session name is `<repo>-PR-<n>` in code; README says `<repo>-pr-<n>`. | `gui.py:1545`, `README.md:20` | Case matters on `sessions:` lists and on Linux file systems. |
| performance | Each tick, for every session, the detector scans and parses all `~/.claude/sessions/*.json` up to 3 times (`_refresh`, `detect_state`, click handlers), runs `ps`, and `_analyze_last_messages` reads the whole JSONL line by line with `json.loads`. Largest transcript on this machine: 70 MB. | `gui.py:1013,1049,1054`, `state_detector.py:97,116,59-79,176-189` | CPU and I/O grow with sessions times transcript size, every 3 s, on the UI thread. |
| performance | `osascript` runs on the Tk main thread: once per tick (2 s timeout) and once per second in `_focus_poll` with no timeout. A hung iTerm2 freezes the window. | `gui.py:399-421,324-330,1788-1793` | UI freezes; slow IPC answers. |
| performance | Every tick destroys and rebuilds all widgets of all tabs. `progress.md` is read once per row per render. | `gui.py:852-905,950` | Flicker and wasted work; scroll position of the row list is not kept by design. |
| performance | `jans.log` writes at DEBUG with no size limit; one line per session per change. | `log.py:19-23`, `persistence.py:52-53` | 117 MB file now. |
| claude-specific | State detection depends on three internal, undocumented Claude Code artefacts: the `~/.claude/sessions` registry, the project directory key rule (`/` and `.` become `-`), and the JSONL record schema. | `state_detector.py:9-10,41-48,51-88`, `persistence.py:12-14` | Any change in Claude Code breaks the states; another tool needs its own detector. |
| claude-specific | The "needs input" signal needs a hook marker in `~/.claude/executing`. Without the hook the session shows `needs_input` for any running tool after 5 s. | `state_detector.py:11,121-124` | Couples Jans to `inject-plan.sh`. |
| claude-specific | Launch and resume use `claude` and `claude --continue` only; resume picks the latest conversation of the cwd, not a chosen session id. | `gui.py:338`, `app.py:538-541` | Cannot resume a named conversation; a different CLI needs a different launcher. |
| claude-specific | The orchestrator is a Claude session that reads `CLAUDE.md` from `~/research/jans`; the cwd is a constant. The prompt imports a file by absolute path. | `gui.py:63`, `CLAUDE.md` | Blocks moving the checkout and using another agent runtime. `make_app.py:10-12` and `jans-menu.sh:3` also fix `~/research/jans`. |
| claude-specific | The `progress.md` subtitle depends on the `[skill] Step N` and `next →` marker text from the skill conventions. | `gui.py:295-313` | A change of the marker format blanks the subtitle. |
| claude-specific | macOS only: iTerm2 and AppleScript for open, focus, tty list, frontmost app; `ps`; ANSI escape codes to a tty for colour, badge and title (iTerm2 proprietary `OSC 6` and `OSC 1337`); `rumps` for the menu bar. | `gui.py:333-453`, `menubar.py` | No Linux or other terminal support. |
