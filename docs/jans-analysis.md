# Jans and the Claude Code workflow: consolidated analysis

## 1. Header

| Item | Value |
|------|-------|
| Date | 2026-10-02 |
| Scope | The Jans session manager (`jans/` in this repository), the Claude Code hook layer (`~/.claude/settings.json` `.hooks` and `~/.claude/hooks/*`), the knowledge base (KB) structure under `~/.claude/knowledge/`, the skill contract `~/.claude/skills/CONVENTIONS.md`, and 15 skills |
| The 15 skills | Development flow (10): `pre-code`, `implement`, `quality`, `pr-review`, `pre-pr`, `pr-describe`, `finish-pr`, `update-agents-md`, `pr-deep-review`, `codex-review`. Review, research and coordination (5): `review-pr`, `start-research`, `finish-research`, `link-feature`, `resume-status` |
| Out of scope | The other 8 skill directories (`appsec-escalation`, `crash-triage-java`, `error-triage-java`, `error-tracking-triage-java`, `jandro-skills`, `jandro-work-tree-review`, `jandro-workflow`, `performance-feedback`), except where a finding cites them. Hooks that the enabled plugins `trajectory` and `trajectory-security` register outside `settings.json` |
| Source commit, `jans` | Branch `main`. Code at `e5f9f49` ("gui: force window to front on startup"). The analysis branch starts at `b1e0471`, which adds only the partial analysis files. `dev` is at `05e08ff` |
| Source commit, `~/.claude` | `6bcf5e0da9b9bc83a69241eeaf31468f78582966` (`git -C ~/.claude rev-parse HEAD`, last commit 2026-10-01) |
| Integration guide | `~/research/manus/claude-integration-guide.md`, not under git. Modified 2026-08-07, 435 lines, SHA-256 prefix `8a5cd36e0569` |
| Method | Four partial analyses read the sources in full on 2026-10-02. This document merges them. Every finding was checked again against the sources at the commits above before the verdicts in sections 6 and 7 were written. Nothing under `~/.claude` was changed |

### How to read the evidence

Evidence is `file:line` or `file:start-end`. Line numbers refer to the commits above.

| Prefix | File |
|--------|------|
| `<skill>:N` (for example `pre-pr:230`) | `~/.claude/skills/<skill>/SKILL.md` |
| `conv:N` | `~/.claude/skills/CONVENTIONS.md` |
| `workflow:N` | `~/.claude/skills/jandro-workflow/SKILL.md` |
| `quickref:N` | `~/.claude/knowledge/_meta/skills-quickref.md` |
| `guide:N` | `~/research/manus/claude-integration-guide.md` |
| `inject-plan.sh:N`, `plan-lock.sh:N`, `kb-domains.sh:N`, `notepad-write-guard.sh:N`, `auto-commit-config.sh:N` | `~/.claude/hooks/<file>` |
| `settings.json:N` | `~/.claude/settings.json` |
| `kb:<path>` | `~/.claude/knowledge/<path>` |
| `gui.py:N`, `ctl.py:N`, `app.py:N`, `menubar.py:N`, `models.py:N` | `jans/<file>` in this repository |
| `commands.py:N`, `features.py:N`, `persistence.py:N`, `state_detector.py:N`, `log.py:N` | `jans/core/<file>` in this repository |
| `README.md:N`, `CLAUDE.md:N`, `JANS.md:N`, `ORCHESTRATOR.md:N`, `DEVELOPMENT.md:N`, `pyproject.toml:N`, `make_app.py:N`, `jans-menu.sh:N` | Files at the root of this repository |

Finding IDs: `D-nn` is a defect or a drift (section 7), `O-nn` is an obsolete item (section 6.2), `P-nn` is a performance item (section 8) and `C-nn` is a Claude-specific dependency (section 9). Finding types follow the shared template: `obsolete`, `drift` (a document says X, the code does Y), `defect`, `performance`, `claude-specific`. Appendix A records how findings of the four partial files were merged or corrected.

## 2. Executive summary

- **What the system is.** One person runs many Claude Code sessions in parallel on macOS. Jans is a tkinter window (`jans/gui.py`) that lists the sessions, shows their live state and opens them in iTerm2. A Claude session in `~/research/jans` is the "orchestrator": it turns Spanish dictation into `jans-ctl` calls. Hooks inject per-session planning files into every prompt. Skills drive a fixed flow (plan, implement, review, open PR, close) and grow a KB under `~/.claude/knowledge/`.
- **What works.** The design keeps durable knowledge out of the context: no hook loads the KB except the feature manifest. Skills read only the KB files they need through `kb-domains.sh`. Planning files survive compaction because the hook injects them on each prompt. The three-strikes gate, the plan lock and the write guard turn rules into mechanical checks. The progress-marker convention gives Jans a live subtitle at no cost.
- **Highest risks.** (1) Data loss: the GUI delete runs `rmtree` on the session directory (D-01), and one bad `state.json` entry can erase all paused sessions (D-02). (2) Self-termination: `jans-ctl delete` sends SIGTERM to the Claude process of the cwd, and `/finish-pr` and `/review-pr` can kill their own session before their last writes (D-03, D-04, D-05). (3) The three-strikes gate can be bypassed by any Bash command that contains the text `git stash`, and it does not cover `MultiEdit` or `NotebookEdit` (D-06, D-07). (4) Documentation drift: the orchestrator prompt documents `switch` and `home`, which the GUI does not implement (D-08), and the integration guide is wrong on at least ten points (D-07, D-20, D-21, D-22, D-23, D-25, D-37, D-45, D-58, D-59, D-61).
- **Cost.** The median per-prompt injection is about 1.4 KB (350-470 tokens). Heavy sessions reach 17-28 KB (4,000-9,300 tokens) because nothing caps the decisions tail or the feature manifest (P-01). Each `/pre-pr` pays two Opus sub-agents over the whole diff, which the guides do not count (D-20, P-07). `/quality` always runs Codex at `xhigh` effort (P-06).
- **Obsolescence.** Remove the `PreCompact` hook (it cannot reach the model), the Textual TUI, the menu bar and their dependencies, and the two superseded triage skills. Merge `pr-review` into `pre-pr`, `codex-review` into `quality` and `pr-deep-review` into `review-pr`. All other skills and hooks stay, but 16 of the 24 rows in section 6.1 need an update.
- **Migration.** The workflow depends on Claude Code in four places that another tool must provide: the hook protocol with `additionalContext` and exit-code blocking, sub-agents with a per-call model, slash-command skills with frontmatter, and undocumented internal files (`~/.claude/sessions`, `~/.claude/projects/*.jsonl`). Jans is also tied to macOS, iTerm2 and AppleScript (section 9).
- **Counts.** 80 defects and drifts, 16 obsolete items, 19 performance items and 23 Claude-specific dependencies. Thirteen entries merge duplicates of the partial files, and the verification corrected 35 details (Appendix A).

## 3. Architecture overview

The system has five layers. Each layer owns its files. The layers talk through files, not through APIs.

```
  user (voice dictation, keyboard)
     |
     v
+--------------------------+   jans-ctl <cmd>    +-----------------------------------+
| Orchestrator session     |-------------------->| Jans GUI (jans/gui.py, tkinter)   |
| claude in ~/research/jans|  ~/.jans/           |  3 s tick: detect state, run IPC, |
| CLAUDE.md + guide import |  pending_cmd.json   |  save ~/.jans/state.json          |
+--------------------------+  cmd_result.json    +-----------------------------------+
                                                   |  creates dirs, worktrees,      ^ reads
                                                   |  scaffold files, manifests     | sessions/*.json
                                                   |  opens iTerm2 tabs (osascript) | projects/*.jsonl
                                                   v                                | executing/*
+-------------------------------------------------------------------------------------+------+
| Session directories: ~/tasks/<repo>-<name>, ~/research/<name>, ~/tools/<name>,             |
|                      ~/reviews/<repo>-PR-<n>                                               |
| Planning files: session.md, task_plan.md, progress.md, findings.md, decisions.md,          |
|                 task_coding_rules.md, .claude-invariants.md, .session-model,               |
|                 .strike_count_*, .plan-lock*                                               |
+---------------------------------------------------------------------------------------------+
       ^ read and written by                      ^ read on every prompt, gated on task_plan.md
       |                                          |
+------+---------------------------+    +---------+-----------------------------------------+
| Skills (~/.claude/skills/*)      |    | Hooks (~/.claude/settings.json -> ~/.claude/hooks)|
| slash commands, SKILL.md text    |    | UserPromptSubmit: inject plan, progress, decisions|
| sub-agents (Agent tool), MCP     |    |   coding rules, feature manifest                  |
| progress markers -> progress.md  |    | PreToolUse: TODO reminder, 3-strikes gate,        |
| call plan-lock.sh, kb-domains.sh |    |   executing marker, Write guard                   |
+------+---------------------------+    | PostToolUse: progress reminder, marker removal,   |
       |                                |   auto-commit of ~/.claude                        |
       | read via kb-domains.sh,        | PreCompact: no effect. Stop: marker removal       |
       | write with Edit                +---------+-----------------------------------------+
       v                                          | reads _meta/features only
+-------------------------------------------------v-----------------------------------------+
| Knowledge base ~/.claude/knowledge/ (git repo, auto-commit)                               |
| _common/  _meta/ (features/, research/, quickref)  <repo>/ (pr-review.md, coding-rules.md,|
| domain/, prs/, research/, reviews/, *-metrics.log)                                        |
+-------------------------------------------------------------------------------------------+
```

Layer by layer:

1. **Orchestrator.** A Claude session with cwd `~/research/jans`. Claude Code loads `CLAUDE.md` there, which imports the integration guide by absolute path. It is the expected consumer of `jans-ctl` (section 5.1.9).
2. **Jans GUI.** It owns `~/.jans/state.json` and the IPC files. It creates sessions, scaffolds planning files, writes and reads feature manifests, and detects session state from Claude Code's own files and one hook marker (section 5.1).
3. **Session directories and planning files.** The shared medium. Jans creates the first files. Skills and hooks read and write them. Their presence switches behavior: no `task_plan.md` means no injection and no strike gate (section 5.4).
4. **Hooks.** Five Claude Code events call `inject-plan.sh` with a mode. Two more scripts guard writes and commit `~/.claude` (section 5.2).
5. **Skills and KB.** Skills are prompt text that the model follows. They spawn sub-agents, call MCP servers and helper scripts, and write the KB. The KB is never force-loaded (section 5.3, 5.5, 5.6).

The coupling points that every migration must keep are: the `feature:` line of `session.md` (selects the manifest the hook injects), the `task_plan.md` presence gate, the executing marker key rule (`/` replaced by `__`, shared by `inject-plan.sh:17` and `state_detector.py:11-30`), the progress-marker format (shared by `conv:7-33` and `gui.py:295-313`), and the Jans session `name` as the identity in `state.json` and in manifest `sessions:` lists.

## 4. End-to-end flows

Each table shows, per step, the skill or command that runs, what the hooks inject or do, and the files that change. Hook behavior that repeats on every step is stated once under each table.

### 4.1 New task (feature implementation)

| # | Step | Skill or command | Hook activity | Files that change |
|---|------|------------------|---------------|-------------------|
| 1 | Create the session | Orchestrator runs `jans-ctl new-task <repo> <name> [ticket]` | None. No Claude runs in the new cwd yet | Git worktree `~/tasks/<repo>-<name>/` on branch `<name>` from `origin/HEAD` (`gui.py:1464-1518`). `session.md` (`type: task`, `feature:` from the ticket or `""`), `task_plan.md` (numbered phase list, no checkboxes), `progress.md` (`gui.py:176-291`). With a ticket: `kb:_meta/features/<T>.md` created if absent, session name appended under `sessions:`. `~/.jans/state.json` |
| 2 | Open Claude | GUI opens an iTerm2 tab with `cd '<cwd>' && claude` (`gui.py:333-365`) | First prompt: `userprompt` injects the scaffold plan (about 300 bytes), the progress tail and the manifest when linked. The preamble stamps `.session-model` with `<settings.json model> effort:<CLAUDE_EFFORT>` | `.session-model` |
| 3 | Plan | `/pre-code` (Explore agents, one Opus Metis agent) | `pretool` sets the executing marker and checks the strike gate. No TODO reminder yet, because the scaffold has no `- [ ]` line. `notepad-write-guard.sh` forces `Edit` on an existing `decisions.md` or `progress.md`. `auto-commit-config.sh` commits KB edits | `.claude-invariants.md`, `task_coding_rules.md` (max 40 lines), `task_plan.md` (TODOs appended), `decisions.md`, `progress.md` checkpoint, `.session-model` (user choice, `pre-code:1259-1262`), four `.plan-lock*` files (`plan-lock.sh lock`, `pre-code:1217`), KB `domain/*.md` (Paso 6.5) |
| 4 | Implement, once per TODO | `/implement TODO-N [model]` (one `Agent` per TODO) | `pretool` adds `Current pending TODO: <first unchecked box>` to each Edit, Write and Bash call. At 3 strikes it blocks with exit 2 | Source code (by the agent), `[x]` in `task_plan.md`, `progress.md`, `.strike_count_<TODO-ID>` and a strike block in `decisions.md` on failure |
| 5 | Quality pass (optional) | `/quality` (passes A, B, C in the session, then Codex MCP Pass X) | `auto-commit-config.sh` commits `coding-rules.md` | Source fixes, `kb:<repo>/coding-rules.md`, `kb:<repo>/quality-metrics.log`, `progress.md`, optional candidate invariants appended to `.claude-invariants.md` (this trips the plan lock later, `quality:309-311`) |
| 6 | KB invariant check (optional) | `/pr-review` | None beyond the common hooks | None (conversation only) |
| 7 | Gate before the PR | `/pre-pr` (two parallel Opus sub-agents) | `decisions.md` content is already in context through `userprompt` | One commit `review: pre-PR checks`, `coding-rules.md`, manifest `## Key decisions` (Fase 8c), `pre-pr-metrics.log`, `progress.md`. `plan-lock.sh verify` reads the lock files |
| 8 | Open the PR | `/pr-describe`, called by `/pre-pr` Fase 8 (`pre-pr:475`) | None | Draft PR on GitHub with labels. `/pre-pr` Fase 8b posts `@codex review` (dd-trace-java only) |
| 9 | Review rounds | `/pre-pr --iteration [sha \| comment-url]` | Same as step 7 | One commit `address review comments` and `git push` per round, `coding-rules.md`, metrics |
| 10 | Repository notes (optional) | `/update-agents-md` | None | `AGENTS.md` files and code comments in the working tree (no commit) |
| 11 | Close after merge | `/finish-pr` | Same as step 3 | KB `domain/*.md`, `kb:<repo>/prs/pr-N/` archive, `prs/pr-N.md`, `prs/pr-N-invariants.md`, `<repo>/pr-review.md`, manifest `## Closed PRs`, `finish-pr-metrics.log`. Removes the worktree, the local branch, the Claude session file and the Jans session (`jans-ctl delete`, which sends SIGTERM) |

Every prompt from step 2 on gets the `userprompt` injection: `task_plan.md` (first 200 lines), the last 20 lines of `progress.md`, the last 80 lines of `decisions.md`, the whole `task_coding_rules.md`, and the whole feature manifest plus related manifests. Every Edit, Write and Bash call gets the `pretool` and `posttool` modes. While `progress.md` exists, `posttool` adds the reminder `progress.md may need updating with the change just made.` Every turn end runs `stop`, which removes the executing marker.

### 4.2 Review of another person's PR

| # | Step | Skill or command | Hook activity | Files that change |
|---|------|------------------|---------------|-------------------|
| 1 | Create the session | `jans-ctl new-review <url>` or the GUI `＋ Review` button. `new-review` is in `usage()` but not in `CLAUDE.md` (D-17) | None | Detached worktree `~/reviews/<repo>-PR-<n>/` (`gui.py:1544-1577`), `session.md` only (`type: pr-review-incoming`, `repo:`, `pr:`). `state.json` only if the checkout worked |
| 2 | Open Claude | GUI tab | `userprompt` exits at the plan gate: no injection, no `.session-model`. `pretool`, `posttool` and `stop` still write and remove the executing marker. `notepad-write-guard.sh` and `auto-commit-config.sh` still run | None |
| 3 | Review | `/review-pr` Phases 0 to 6 (normal or deep) | Same as step 2. `posttool` sends no reminder, because it runs after the plan gate | `progress.md` (Phase 0), `findings.md` (deep mode). Optional `gh pr review` |
| 4 | Close | `/review-pr` Phase 7 | Same as step 2 | Deep: KB `domain/*.md` (7a). `kb:<repo>/prs/pr-<n>/review-*.md` (7b), `kb:<repo>/reviews/pr-<n>.md` (7c), worktree removal and `jans-ctl delete` (7d), `review-metrics.log` (7e, after the delete, D-05) |

### 4.3 Research

| # | Step | Skill or command | Hook activity | Files that change |
|---|------|------------------|---------------|-------------------|
| 1 | Create the session | `jans-ctl new-research <name> [ticket]` | None | `~/research/<name>/` with `session.md` (`type: research`, `investigation:`, `feature:` or `"standalone"`), `task_plan.md` (workflow reference, no TODOs), `findings.md` (four headings), `progress.md`. Manifest link if a ticket is given |
| 2 | Load context | `/start-research` | `userprompt` injects the plan scaffold, the progress tail and the manifest if linked | Missing scaffold files (Phase 1), `related_projects:` edits in `session.md`, `findings.md` from a template. KB read through `kb-domains.sh list` and `kb-domains.sh research`. Jira through the Atlassian MCP |
| 3 | Investigate | Free work | `notepad-write-guard.sh` forces `Edit` on `findings.md` and `progress.md`. `posttool` reminds about `progress.md` after each Edit, Write and Bash call | `findings.md`, `progress.md` |
| 4 | Close | `/finish-research` | Same as step 3 | KB `domain/*.md`, `<repo>/pr-review.md`, `_meta/*.md`. `session.md` gets `closed:` and `contributed_to:`. Research cache `kb:<repo>/research/<session>.md` or `kb:_meta/research/`. Manifest narrative entry, `## Related research` row, `## Active sessions` row. `jans-ctl delete` as the last action. The directory stays on disk (D-14) |

### 4.4 Multi-session feature

| # | Step | Skill or command | Hook activity | Files that change |
|---|------|------------------|---------------|-------------------|
| 1 | Create the manifest | `jans-ctl new-feature <ticket> <nickname> [desc]` or `/link-feature <ticket>` | None | `kb:_meta/features/<ticket>.md` (`ticket`, `nickname`, `description`, `sessions: []`). `new-feature` never overwrites an existing file (D-47) |
| 2 | Create linked sessions | `jans-ctl new-task <repo> <name> <ticket>` in each repo, `new-research <name> <ticket>` | None | Each `session.md` gets `feature: "<ticket>"`. The manifest gets one `sessions:` row per session (`features.py:105-122`) |
| 3 | Work in parallel | Flows 4.1 and 4.3 in each session | Every prompt in every linked session injects the whole manifest and each `related_features:` manifest, one level deep (`inject-plan.sh:63-86,118-122`) | None from the hook |
| 4 | Share decisions | `/pre-pr` Fase 8c, `/finish-pr` Paso 5.8, `/finish-research` Phase 6 | The next prompt in a sibling session sees the edit | Manifest `## Key decisions`, `## Closed PRs`, `## Related research`, `## Active sessions` |
| 5 | Repair drift | `/link-feature` (no argument: sweep mode) | None | New or merged manifests, `feature:` and `related_sessions:` in `session.md`, missing `task_plan.md` and `progress.md` for research sessions |
| 6 | Watch status | GUI Features tab (`n_active/total`), `jans-ctl feature-status <ticket>` | None | None |
| 7 | Resume after a break | `/resume-status` (pinned to Haiku) | `userprompt` as usual | None (it appends its own markers to `progress.md`) |

## 5. Components

### 5.1 Jans app

Facts in this section come from the code at `e5f9f49`. The `web/` directory does not exist on `main`. It exists only on the `web-app` branch, an abandoned FastAPI experiment (`DEVELOPMENT.md:28`).

#### 5.1.1 Entry points and packaging

- `pyproject.toml:5-20`: Python >= 3.12, build backend hatchling. Dependencies: `textual`, `pyte`, `ptyprocess`, `watchfiles`, `rumps`. Scripts: `jans` (`jans.__main__:main`, the Textual TUI), `jans-ctl` (`jans.ctl:main`), `jans-menu` (`jans.menubar:main`), `jans-gui` (`jans.gui:main`). tkinter is not listed because it ships with Python. `pyte`, `ptyprocess` and `watchfiles` are imported nowhere in `jans/`.
- `jans/__main__.py:10-40` sets the tab title, builds `HelmApp`, saves sessions on SIGTERM and SIGINT and runs the Textual app.
- `make_app.py:10-52` builds `~/Applications/jans.app`. The launcher runs `~/research/jans/.venv-menu/bin/python3 ~/research/jans/jans/gui.py`. Paths are hard coded (`make_app.py:7-9`). `LSUIElement` is false, so the app shows in the Dock. `jans-menu.sh:3` runs `menubar.py` with the same venv.

#### 5.1.2 GUI (`jans/gui.py`, 1816 lines): the production front end

- One narrow tkinter window with five tabs: `features`, `research`, `tasks`, `tools`, `reviews` (`gui.py:69-70`). Each row is a session: state icon, name, age, cwd, last progress line and a colour chip.
- Loop: `_tick` runs every 3000 ms (`gui.py:495`, `1138-1148`). It reloads feature manifests, merges external edits of `state.json`, runs `_refresh` (state detection, iTerm2 side effects, IPC command) and saves `state.json`. A second loop, `_focus_poll`, runs every 1000 ms and raises the window when iTerm2 comes to the front (`gui.py:1788-1793`).
- Inputs: `~/.jans/state.json`, `~/.jans/pending_cmd.json`, `~/.claude/sessions/*.json`, `~/.claude/projects/<key>/<id>.jsonl`, `~/.claude/executing/*`, `<cwd>/progress.md`, `kb:_meta/features/*.md`, `kb:_meta/skills-quickref.md` (help window, `gui.py:805`).
- Outputs: `state.json`, `cmd_result.json`, `~/.jans/jans.log`, session directories and scaffold files, git worktrees, iTerm2 tabs, and escape sequences written to the tty of each Claude process for tab colour, badge and title (`gui.py:376-396`).
- External commands: `osascript` (iTerm2 control, frontmost app), `ps -o tty=`, `git` (fetch, worktree add, clone), `gh pr view`.
- Session kind (`_session_kind`, `gui.py:73-84`): the stored `kind` wins. Otherwise the cwd prefix decides: `~/reviews`, `~/tools`, `~/tasks`, else `research`.
- Open a session (`_open_session`, `gui.py:333-365`): iTerm2 creates a tab and types `cd '<cwd>' && claude [--continue]`. `--continue` is used only when `~/.claude/projects/<key>` exists. Nothing else is passed: no model flag, no session id, no system prompt.
- Click on a row (`gui.py:973-988`): if the Claude process has a tty in an open iTerm2 tab, focus that tab. Otherwise open a new tab.
- Right-click delete (`gui.py:990-996`, `1152-1169`): removes the session and runs `shutil.rmtree(session.cwd)` after a confirm dialog (D-01).
- Unread marker (`gui.py:1020-1037`): a session whose iTerm2 tab disappeared while Claude still runs gets `◎`. It lives in memory only.

#### 5.1.3 CLI (`jans/ctl.py`) and IPC (`jans/core/commands.py`)

- Purpose: let a Claude session or a human control the running GUI.
- Mechanism (`commands.py:11-23`): `send_command` deletes `~/.jans/cmd_result.json`, writes `{"action": ..., **args}` to `~/.jans/pending_cmd.json`, polls for the result every 50 ms and gives up after 5 s with `jans is not running or not responding`. The GUI reads the command inside `_refresh` (`gui.py:1080-1082`), so the latency is up to one tick (3 s) plus the refresh time. The GUI deletes the command file, runs the action and writes the result (`commands.py:26-39`).
- Output: the result dict as indented JSON. An `error` key prints `Error: ...` on stderr and exits 1 (`ctl.py:128-132`). No argument prints usage and exits 1. An unknown command prints `Unknown command: X` plus usage and exits 1.
- Name rule (`ctl.py:13-19`, `features.py:6-18`): `name`, `repo` and `ticket` must match `^[A-Za-z0-9._-]+$` for `new-research`, `new-task`, `new-tool` and `new-feature` (ticket only). The CLI does not validate the other commands.

Command reference. The source of truth is `usage()` (`ctl.py:22-40`). The GUI handler is `JansApp._execute_command` (`gui.py:1635-1761`).

| Command | Arguments | CLI checks | Effect in the GUI handler |
|---|---|---|---|
| `list` | none | none | Returns `{"sessions": [{name, state}]}` (`gui.py:1637-1638`). No cwd |
| `new-research` | `<name> [ticket]` | name, ticket | Creates `~/research/<name>/`, the scaffold (5.1.6), a manifest if `ticket` is set, links the session, opens an iTerm2 tab (`claude`, no `--continue`), switches the GUI tab, saves state. Returns `{"ok": true}` before the work runs (`gui.py:1639-1654`, `1602-1633`) |
| `new-task` | `<repo> <name> [ticket]` | repo, name, ticket | Registers `<repo>-<name>` (kind `tasks`) at once. In a thread: `git fetch origin`, `git worktree add ~/tasks/<repo>-<name> -b <name> origin/HEAD` in `~/repos/<repo>` (fallback `~/tasks/<repo>`), scaffold, iTerm2 tab. Creates and links the manifest if `ticket` is set (`gui.py:1464-1518`) |
| `new-tool` | `<name>` | name | Creates `~/tools/<name>/`, scaffold, iTerm2 tab (`gui.py:1639-1654`) |
| `new-feature` | `<ticket> <nickname> [desc]` | ticket; `desc` is the remaining words | Writes `kb:_meta/features/<ticket>.md` if absent (`features.py:76-100`), reloads features, expands the entry (`gui.py:1667-1680`) |
| `feature-status` | `<ticket>` | none | Returns `{ticket, description, sessions: [{name, state}]}`. A linked session that Jans does not load has state `not_loaded`. Error `feature not found: <ticket>` (`gui.py:1741-1760`) |
| `new-review` | `<url>` | none | Parses `https://github.com/<owner>/<repo>/pull/<n>` (`gui.py:91-101`). In a thread: `gh pr view` for the head ref, `git fetch pull/<n>/head`, `git worktree add --detach ~/reviews/<repo>-PR-<n>`. Writes `session.md` only. Registers the session only if the checkout worked (`gui.py:1544-1577`). Without a local clone it makes a plain directory |
| `load` | `<path> [name]` | none | Adds a session for an existing directory. The name defaults to the folder name. A duplicate name is ignored but returns ok. No terminal opens (`gui.py:1725-1740`) |
| `rename` | `<current> <new>` | none | Renames the session in memory. Returns ok even if `current` does not exist (`gui.py:1706-1714`) |
| `delete` | `<name>` | none | Removes the session from the list and sends SIGTERM to the Claude process of that cwd. Files stay. Returns ok even if the name does not exist (`gui.py:1690-1705`) |
| `color` | `<name> <color>` | none (`COLORS` at `ctl.py:10` is help text only) | Stores the colour string. The next tick applies it to the iTerm2 tab (`gui.py:1715-1724`) |
| `home` | none | none | No GUI handler: `{"error": "unknown: home"}` (`gui.py:1761`). Only the Textual app implements it (`app.py:435`) |
| `switch` | `<name>` | none | Same: `unknown: switch` in the GUI. Textual only (`app.py:438`) |
| `state` | none | none | Alias of `list` (`ctl.py:121-122`) |

#### 5.1.4 State, persistence and logging

- `models.py:5-33`: `SessionState` is `processing`, `waiting`, `needs_input`, `terminated` or `paused`. `Session` fields: `name`, `cwd`, `session_id`, `state`, `last_activity`, `pid`, `terminal_id`, `color`, `kind`.
- `~/.jans/state.json` is a JSON list (`persistence.py:36-51`). Each entry has `name`, `cwd`, `session_id`, `last_activity` (ISO string) and, only when set, `color` and `kind` (`tasks`, `research`, `tools`, `reviews`). `pid` and `terminal_id` are never saved. Sessions in state `terminated` are dropped on save. The guide calls the shape `{name, cwd, session_id}`. That is the minimum other tools can rely on, but the reader requires `last_activity` (`persistence.py:73`).
- Read (`persistence.py:56-81`): every entry becomes `paused`. An entry whose `pid` is not null is skipped as "external" (`persistence.py:65-67`). An entry without a `pid` key or with `pid: null` is loaded. Any exception returns an empty list (D-02).
- Write: `Path.write_text`, not atomic, on each tick, on close and after every list change (`gui.py:1086-1095`, `1145`). The GUI stores the file mtime after each write. On each tick `_merge_external_sessions` (`gui.py:1097-1136`) compares the mtime. If the file is newer, it adds sessions that exist only on disk, applies cwd changes (and renames `~/.claude/projects/<key>`, `persistence.py:21-33`), and removes in-memory sessions that vanished from disk unless they are active. Identity is the session `name`.
- Other writers: skills such as `/finish-pr` edit `state.json` directly (README "Persistence"). The GUI reconciles by name.
- `core/log.py`: one `FileHandler` at DEBUG level to `~/.jans/jans.log`, created at import time (`log.py:23`). No rotation.

#### 5.1.5 State detection (`core/state_detector.py`)

Jans classifies each session without hooks inside Claude, from files that Claude writes. Steps per session (`detect_state`, `state_detector.py:91-129`):

1. A `pid` is set and dead: `terminated`.
2. Find the live Claude session for the cwd: scan every `~/.claude/sessions/*.json`, match `cwd` case-insensitively after `resolve()`, skip dead pids, take the newest file (`state_detector.py:169-190`). Fields used: `cwd`, `pid`, `sessionId`.
3. No live process and the cwd is gone: `terminated`, so `save_sessions` drops it.
4. Find `~/.claude/projects/<cwd with / and . replaced by ->/<sessionId>.jsonl`. No file: `waiting` with a live process, else `paused`.
5. File mtime younger than 5 s (`PROCESSING_THRESHOLD_SECS`, `state_detector.py:12`): `processing`.
6. Read the whole JSONL. If the last assistant message has a `tool_use` with no later `tool_result`: `processing` when the marker `~/.claude/executing/<cwd with / as __>` is younger than 15 minutes, else `needs_input` (`state_detector.py:121-124`).
7. Last message type `assistant`: `waiting`. Anything else: `processing`.

The GUI wraps this (`gui.py:1007-1084`): a session with no iTerm2 tab whose tty matches the Claude pid is forced to `paused`. The tty comes from `ps -o tty=` and the open ttys from AppleScript.

Last progress line (`_read_last_progress`, `gui.py:295-313`): reads `<cwd>/progress.md` and takes the last line that starts with `[`. Green if it contains `done` and no arrow. Blue if it contains `next →`. Dim otherwise. This is the row subtitle.

#### 5.1.6 Session types and scaffolds (`_bootstrap_planning_files`, `gui.py:176-291`)

Files are written only if absent (`gui.py:187-190`).

| Type (CLI, tab) | Directory | `session.md` frontmatter | Other files |
|---|---|---|---|
| research (`new-research`, `research`) | `~/research/<name>/` | `type: research`, `related_projects` (list or `[]`), `investigation: <name>`, `feature: "<ticket>"` or `"standalone"`, `contribution_targets: []` | `task_plan.md` (workflow reference, no TODOs), `findings.md` (headings: Invariants discovered, Patterns and non-obvious behavior, PR review rules, Open questions), `progress.md` |
| task (`new-task`, `tasks`) | `~/tasks/<repo>-<name>/` (git worktree) | `type: task`, `related_projects: []`, `feature: "<ticket>"` or `""`, `contribution_targets: []` | `task_plan.md` (phases 0 to 6), `progress.md` |
| tool (`new-tool`, `tools`) | `~/tools/<name>/` | `type: tooling`, `related_projects: [_meta]`, `contribution_targets: [_meta/workflow.md]` | `task_plan.md`, `findings.md`, `progress.md` |
| review (`new-review`, `reviews`) | `~/reviews/<repo>-PR-<n>/` (detached worktree) | `type: pr-review-incoming`, `repo: <owner/repo>`, `pr: <n>` | None, on purpose: without `task_plan.md` the injector is a no-op |
| load (`load`, GUI "Load") | any existing directory | none | None. The kind comes from the cwd prefix |

- Jans does not create `decisions.md`, `task_coding_rules.md`, `.claude-invariants.md` or `.session-model`. `/pre-code` and the hook do.
- Each new session gets the first unused colour of eight (`_next_color`, `gui.py:1594-1600`).
- The session name is the directory name for research and tool sessions, `<repo>-<name>` for tasks and `<repo>-PR-<n>` for reviews.
- The task phase list (`gui.py:267-290`) is numbered text. It mentions only `/pre-code`, `/quality`, `/pre-pr`, `/pr-describe` and `/finish-pr` (`gui.py:284-290`). `/pre-code` appends its TODOs under `## Phases` (`pre-code:1114`).

#### 5.1.7 Feature manifests (`core/features.py`)

- Purpose: group sessions of several repos under one ticket. File: `kb:_meta/features/<TICKET>.md`.
- `create_feature` (`features.py:76-100`) validates the ticket, creates the directory and writes `ticket`, `nickname`, `description`, `sessions: []` and a title. It never overwrites a file. An empty nickname becomes the ticket id.
- `link_session` (`features.py:105-122`) appends `  - <session name>` under `sessions:`. `new-research` and `new-task` call it when a ticket is given. It returns False silently when the manifest is missing, so the creators call `create_feature` first.
- `load_features` (`features.py:55-72`) reads `ticket`, `nickname`, `description` and `sessions` with a hand-made frontmatter parser (`features.py:28-52`). It ignores all other keys, including `related_features`, `sub_features` and `type`, which other layers use.
- The Features tab shows `n_active/total` per feature. Expanded, it lists each linked session with its state, or `load` for sessions that Jans does not track (`gui.py:612-690`, `769-783`).
- `inject-plan.sh:48-55` reads `feature:` from `session.md` and injects the same manifest. `session.md` and the manifest `sessions:` list are two halves of one link, and Jans writes both at creation time.

#### 5.1.8 Legacy front ends: Textual TUI and menu bar

- `app.py` (`HelmApp`, 703 lines) is a Textual TUI with an embedded terminal per session. `widgets/terminal_widget.py` runs each Claude inside tmux and polls `tmux capture-pane`. `app.py:360` starts the orchestrator as `claude` in the Jans directory. Resume uses `claude --continue` (`app.py:541`). New research sessions pass `--append-system-prompt "You are a research agent..."` (`app.py:581`). It polls the command file every 0.5 s (`app.py:369`) and supports only `list`, `new-research`, `new-task`, `load`, `rename`, `delete`, `home` and `switch` (`app.py:386-448`). Its `new-task` creates a plain directory with no worktree and no scaffold (`app.py:560-588`).
- `menubar.py` (`JansMenuBar`, rumps) lists sessions grouped by state. It supports `list`, `new-research`, `new-task`, `delete` and `rename` (`menubar.py:270-296`). Its `new-task` creates `~/research/<name>`.
- Both write the same `state.json` and IPC files. A run next to the GUI adds a second consumer of the same command file.
- `JANS.md` documents the TUI as the current design. `README.md` and `DEVELOPMENT.md` document the GUI. `main` contains all three front ends.

#### 5.1.9 Orchestrator and the channel rule

- `CLAUDE.md`, auto-loaded by Claude Code in `~/research/jans`, is the orchestrator prompt: run `jans-ctl list` at start, run session actions at once, ask only before `delete`, use kebab-case names, follow a Spanish dictation table and a command list. It imports the integration guide with `@/Users/alejandro.gonzalez/research/manus/claude-integration-guide.md`.
- The GUI header opens the orchestrator: `_open_jans_session` (`gui.py:1763-1786`) opens or focuses the session with cwd `_JANS_CWD = ~/research/jans` (`gui.py:63`), the production checkout. The list hides the orchestrator session (`gui.py:854`).
- `ORCHESTRATOR.md` and `JANS.md` are older orchestrator and design texts (D-17, O-01).
- Channel rule (`CLAUDE.md`, "Changing Jans itself"): `~/research/jans` on `main` is production. Work happens in `~/research/jans-impl` on `dev`, then `dev` is merged into `main` with a real merge. On 2026-10-02 the rule is broken (D-18).

### 5.2 Hooks and settings

#### 5.2.1 Wiring in `settings.json`

Source: `settings.json:132-202`. No hook sets `timeout` or `async`, so the platform defaults apply. All commands are absolute paths. `settings.local.json` has no `hooks` key.

| Event | Matcher | Command (argument) | Lines |
|-------|---------|---------------------|------|
| `UserPromptSubmit` | none (every prompt) | `inject-plan.sh userprompt` | 193-201 |
| `PreToolUse` | `Edit\|Write\|Bash` | `inject-plan.sh pretool` | 164-172 |
| `PreToolUse` | `Write` | `notepad-write-guard.sh` | 173-181 |
| `PostToolUse` | `Edit\|Write\|Bash` | `inject-plan.sh posttool` | 134-142 |
| `PostToolUse` | `Edit\|Write` | `auto-commit-config.sh` | 143-151 |
| `PreCompact` | none | `inject-plan.sh precompact` | 153-161 |
| `Stop` | none | `inject-plan.sh stop` | 183-191 |

No matcher covers `MultiEdit`, `NotebookEdit`, `Read`, `Grep`, `Glob`, `Agent` or MCP tools. Hooks do not run for them.

Related settings: `env.CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR=1` (`settings.json:3`) resets the Bash cwd to the session root after each call. The hooks rely on this, because they read `task_plan.md` from `$PWD`. `model` is `"sonnet"` (`settings.json:131`), and the `.session-model` stamp reads it.

`plan-lock.sh` and `kb-domains.sh` live in the hooks directory but are not wired. Skills call them.

#### 5.2.2 `inject-plan.sh` (244 lines)

Purpose: put the session plan in front of the model, enforce the three-strikes gate and publish an "executing" marker for Jans. Input: the mode as first argument (default `userprompt`, line 6). The `pretool` mode also reads the hook JSON from stdin (lines 129-135). Environment: `HOME`, `PWD`, `CLAUDE_EFFORT`.

Common preamble (lines 6-61), in order:

1. **Executing marker** (lines 13-32). The key is `$PWD` with every `/` replaced by `__`. The file is `~/.claude/executing/<key>` and holds the cwd. `pretool` creates it. `posttool` and `stop` delete it. This runs before the plan check, so it applies to every session.
2. **Plan gate** (lines 34-36). `stop` has already exited at line 31. Without `task_plan.md` in `$PWD`, every other mode exits 0 here.
3. **`.session-model` stamp** (lines 38-46). If the file is missing, the script writes `"<settings.json .model> effort:<CLAUDE_EFFORT>"`. A failed `jq` gives `unknown`. An unset `CLAUDE_EFFORT` gives `effort:unknown`. `/pre-code` Paso 6 later overwrites the file with the real choice (`pre-code:1262`).
4. **Feature resolve** (lines 48-61). `grep "^feature:" session.md | head -1 | cut -d' ' -f2`, quotes stripped. Empty or `standalone` skips. Otherwise the manifest is `kb:_meta/features/<ID>.md`. A missing manifest skips silently.
5. **`inject_related_features`** (defined at lines 63-86, called only by `userprompt` at line 122). After a `related_features:` line it takes each following `- <id>` line, strips quotes and prints `=== RELATED FEATURE: <id> ===` plus the whole file. The block ends at the first line that is not a list item. Related manifests are not scanned in turn.

| Mode | Trigger | What reaches the model | Exit code | Side effects |
|------|---------|------------------------|-----------|--------------|
| `userprompt` (lines 89-124) | Every prompt | Plain stdout, in order: `=== TASK PLAN ===` (`head -200`, then a truncation note), `=== RECENT PROGRESS ===` (`tail -20`), `=== DECISIONS (last 80 lines ...) ===` (`tail -80`), `=== TASK CODING RULES ===` (whole file), `=== FEATURE CONTEXT: <id> ===` and `=== RELATED FEATURE: <id> ===` blocks (whole files). A section is omitted when its file is missing. No byte cap | Status of the last command. It never exits 2, so it cannot block a prompt | `.session-model` stamp |
| `pretool` (lines 126-219) | Before each `Edit`, `Write` or `Bash` call | When no TODO is blocked: JSON `hookSpecificOutput.additionalContext` = `Current pending TODO: <text>` from the first line that matches `^\s*- \[ \]` (lines 209-217). Nothing when no unchecked box exists | 0, or 2 with a stderr message when the strike gate blocks (line 197) | Creates the marker (line 22). Removes it before a block (line 196) |
| `posttool` (lines 221-231) | After each `Edit`, `Write` or `Bash` call | If `progress.md` exists: `additionalContext` = `progress.md may need updating with the change just made.` (56 characters). It fires for read-only Bash such as `ls` too | 0 | Deletes the marker (line 24) |
| `precompact` (lines 233-243) | Before compaction | Nothing. It echoes `[Pre-compact: flush any pending progress to progress.md before compacting]` to the debug log only. The comment at lines 234-241 says `PreCompact` supports no `additionalContext` and the author rejects exit 2 | 0 | `.session-model` stamp |
| `stop` (lines 25-32) | End of each assistant turn | Nothing | 0, before any other work | Deletes the marker. The comment at lines 26-29 says a blocked `pretool` or a denied permission prompt skips `posttool`, so without this Jans would see the cwd as executing forever |

An unknown mode matches no `case` branch and exits silently after the preamble. There is no usage message.

**Three-strikes gate** (`pretool`, lines 137-202):

- Strike files are `.strike_count_<TODO-ID>` in `$PWD`, each with an integer. `/implement` writes them (`implement:374`) and clears them (`implement:308`, `implement:393`).
- A count `>= 3` blocks (line 148). Every file at the threshold goes into `blocked_todos` and `blocked_files`. A non-numeric file prints an error on stderr and does not block (D-77).
- On a block, when the call is not allowlisted, stderr gets four required actions: `git stash push -m "strike-3 ..."`, document the attempts in `decisions.md`, launch one isolated Agent, ask the user one question. Then `rm -f <blocked files>` and "Do NOT attempt a 4th variation" (lines 186-193). Exit 2.
- Allowlist (lines 159-183): for `Bash`, any command that contains `git stash` (line 165, D-06), or an exact `rm -f <file>`, `rm <file>`, `rm -f ./<file>` or `rm ./<file>` for a blocked file. For `Write|Edit|MultiEdit|NotebookEdit`: a target whose basename is `decisions.md`. An allowlisted call exits 0 at line 201 and skips the TODO reminder.

#### 5.2.3 `notepad-write-guard.sh` (20 lines)

- Purpose: stop `Write` from replacing accumulated session memory. Caller: `PreToolUse`, matcher `Write` (`settings.json:174-178`).
- It reads `tool_name` and `tool_input.file_path` from stdin with `jq` (lines 6-8). If the tool is `Write`, the basename is `findings.md`, `progress.md` or `decisions.md` and the file exists, it writes `BLOCKED: ... use Edit` to stderr and exits 2 (lines 10-16). Otherwise it exits 0. A first creation stays allowed.
- It does not check `task_plan.md` and does not guard `MultiEdit`. `inject-plan.sh pretool` also runs for `Write`. Either script can block the call.

#### 5.2.4 `auto-commit-config.sh` (30 lines)

- Purpose: keep `~/.claude` recoverable. Caller: `PostToolUse`, matcher `Edit|Write` (`settings.json:144-148`). It runs after every Edit or Write in any session and repo, and does not check which file changed (lines 2-5).
- It exits 0 if `~/.claude` is not a git repo (line 10). It runs `git add skills/ knowledge/ hooks/ settings.json CLAUDE.md snowflake-mcp-setup.md .gitignore` with errors discarded (lines 13-21), exits 0 if nothing is staged (line 24), and else commits with `auto: <first 5 changed file names>` (lines 27-28).
- `git commit` has no redirect, so its stderr shows (for example when another session holds `index.lock`). The script still exits 0 (line 30).
- The repo has 1,306 commits, 186 of them since 2026-09-01. Subjects are file names only.

#### 5.2.5 Helper scripts

**`plan-lock.sh` (106 lines).** Detects scope drift between the approved plan and the PR. `/pre-code` runs `lock` at the end of Paso 5.5 (`pre-code:1217`). `/pre-pr` runs `verify` (`pre-pr:92`).

- `lock` (lines 29-48): SHA-256 of `.claude-invariants.md`, and SHA-256 of `task_plan.md` after `sed 's/- \[x\]/- [ ]/'` (lines 24-26). It writes `.plan-lock`, `.plan-lock-snapshot.md`, `.plan-lock-taskplan` and `.plan-lock-taskplan-snapshot.md`, all in `~/.gitignore_global`. A missing source file prints a warning and does not fail.
- `verify` (lines 50-99): compares both hashes. On a mismatch it prints `diff snapshot current | head -60` and `Continue with /pre-pr? (y/n)`. A missing lock prints a warning and skips. It always exits 0 (line 99): the caller must read the text. Other arguments print usage and exit 1.
- It uses `sha256sum` if present, else `shasum -a 256` (line 19).

**`kb-domains.sh` (441 lines).** A read-only inventory and resolver over the KB, so no skill keeps its own table of KB files. Callers: `/pre-code`, `/start-research`, `/pr-review`, `/pre-pr`, `/review-pr`, `/link-feature`, `/finish-research`, `/resume-status`.

| Command | Reads | Output |
|---------|-------|--------|
| `list <repo>` | `<repo>/*.md` and `<repo>/domain/*.md`, minus reserved names (`pr-review.md`, `coding-rules.md`, `README.md`, `*.log`) | One row per entry (path, domain, description, stability) from the frontmatter. Entries without `source_files:` go under `UNMATCHABLE` |
| `match <repo> <file>...` | Same files | Entries whose `source_files:` match a changed file (exact, path suffix or directory prefix), plus `UNMATCHABLE` |
| `research [<repo>]` | `<repo>/research/*.md`, `_meta/research/*.md` | One row per closed research session |
| `review [<repo>]` | `<repo>/reviews/*.md` | One row per review of another person's PR |
| `prs [<repo>]` | `<repo>/prs/pr-<n>.md` (flat files) | One row per closed PR. A `MISMATCH` block when `repo:` disagrees with the directory |

It exits 0, or 1 with usage text. It uses `set -u` only.

#### 5.2.6 Platform constraints that the scripts document

| Constraint | Where |
|------------|-------|
| Plain stdout of `PreToolUse` never reaches the model. Use JSON `hookSpecificOutput.additionalContext`, phrased as a fact | `inject-plan.sh:204-208` |
| Plain stdout of `PostToolUse` reaches only the debug log. Use the same JSON field | `inject-plan.sh:222-225` |
| `PreCompact` supports no `additionalContext`. Its only JSON fields are `decision` and `reason`. `additionalContext` exists for `SessionStart`, `Setup`, `SubagentStart`, `UserPromptSubmit`, `UserPromptExpansion`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch`, `Stop` and `SubagentStop` | `inject-plan.sh:234-241` |
| Exit 2 blocks a `PreToolUse` call and feeds stderr to the model | `inject-plan.sh:186-197`, `notepad-write-guard.sh:14-15` |
| A blocked `PreToolUse` call and a denied permission prompt skip `PostToolUse`, so cleanup needs `Stop` | `inject-plan.sh:26-29`, `194-196` |
| stdin can be read once. Guard with `-t 0` for manual runs | `inject-plan.sh:127-131` |
| Plain stdout of `UserPromptSubmit` becomes injected context. The script relies on this and does not document it | `inject-plan.sh:89-123` |

### 5.3 Knowledge base structure

Root: `~/.claude/knowledge/` (3.4 MB, 424 files). Reference documents: `kb:README.md` (Spanish, layer map and entry format), `kb:_meta/README.md` (ecosystem and hook overview) and `kb-domains.sh list <repo>` (live inventory).

```
knowledge/
  README.md                       layer map and entry frontmatter format (Spanish)
  _common/                        gh-cli.md, pr-review.md (rules for all repos)
  _meta/
    README.md tools.md workflow.md jira.md skills-quickref.md
    features/<TICKET>.md          feature manifests (9 on disk)
    research/<session>.md         research cache for multi-repo research
  <repo>/                         dd-trace-java, system-tests, libddwaf-java, dd-source,
    pr-review.md                  agentic-onboarding-evals, evalya, web-ui
    coding-rules.md               self-built rules with PR provenance
    <topic>.md                    flat domain layer (legacy)
    domain/<topic>.md             current domain layer
    prs/pr-<n>.md                 closed own-PR summary
    prs/pr-<n>-invariants.md      verbatim copy of .claude-invariants.md
    prs/pr-<n>/                   verbatim archives (invariants, coding-rules, progress,
                                  findings, decisions; review-*.md for reviews)
    research/<session>.md         research cache
    reviews/pr-<n>.md             review cache for other people's PRs
    quality-metrics.log pre-pr-metrics.log review-metrics.log finish-pr-metrics.log
```

Scale for `dd-trace-java`: 113 entries in `prs/` (37 flat summaries, 29 invariants copies, 47 archive directories), 33 files in `domain/`, 17 in `reviews/`, 3 in `research/`.

Who writes and who reads each layer (from a grep of the skills and the hooks; "hook" is `inject-plan.sh userprompt`):

| Layer | Kind | `kb-domains.sh` command | Written by | Read by |
|-------|------|-------------------------|------------|---------|
| Flat `<repo>/*.md` and `domain/` | Domain invariants | `list`, `match` | `/finish-pr` (consolidation), `/finish-research` Phase 5 (`domain/` only), `/review-pr` deep Phase 7a, `/pre-code` Paso 6.5 | `/pre-code`, `/start-research` (`list`), `/pr-review`, `/pre-pr`, `/review-pr` (`match`) |
| `coding-rules.md` | Rules | none (reserved) | `/quality`, `/pre-pr` (append findings with PR provenance) | `/pre-code`, `/quality`, `/pre-pr`, `/pr-describe` |
| `<repo>/pr-review.md` | Rules | none (reserved) | `/finish-pr` (confirmed checks), `/finish-research` Phases 4-5, `/review-pr` 7a | `/pr-review`, `/review-pr`, `/start-research`, `/pre-code`, `/pre-pr` |
| `_common/pr-review.md` | Shared rules | none | No skill. Edited by hand | `/review-pr`, `/pre-code`, `/finish-pr`, `/pre-pr` (`pre-pr:110-113`), `/pr-review` (`pr-review:70,74`), `/start-research` |
| `prs/` | Closed own PRs | `prs` | `/finish-pr` (Paso 4 archive, Paso 5 summary), `/review-pr` 7b (`review-*.md`) | `/pre-code` (`kb-domains.sh prs`), `/link-feature`, `/resume-status` Step 2c and 2e, `/finish-pr` |
| `research/` | Closed research | `research` | `/finish-research` Phase 6 | `/start-research` Phase 2, `/pre-code` Paso 1.5, `/link-feature` 2a, `/resume-status` Step 2d |
| `reviews/` | Reviews of other PRs | `review` | `/review-pr` 7c | `/resume-status` Step 2e, `/link-feature` 2a |
| `_meta/features/` | Feature manifests | none (read by path) | `/link-feature` Phase 4, `/finish-research` Phase 6, `/pre-pr` Fase 8c, `/finish-pr` Paso 5.8, Jans `create_feature` and `link_session` | Hook (every prompt with a `feature:`), `/pre-code`, `/start-research` Phase 3, `/link-feature`, Jans |
| `_common/`, `_meta/*.md` | Shared knowledge | none | By hand, `/finish-research` (`_meta/`) | Skills by path, Jans (`skills-quickref.md`) |
| `quality-metrics.log` | Metrics | none | `/quality` | `/finish-pr` (grep by PR), by hand |
| `pre-pr-metrics.log` | Metrics | none | `/pre-pr` Fase 6b and Fase 10 | `/finish-pr` (grep by PR), by hand |
| `review-metrics.log` | Metrics | none | `/review-pr` Phase 7e | `/resume-status` 2e.2, by hand |
| `finish-pr-metrics.log` | Metrics | none | `/finish-pr` | By hand |

No hook writes or loads the KB except the manifest read in `userprompt`. `auto-commit-config.sh` commits the tree after each Edit or Write. `pr-review`, `pr-describe`, `update-agents-md`, `pr-deep-review`, `codex-review`, `pre-code`, `start-research`, `finish-research`, `link-feature` and `resume-status` leave no metrics line.

### 5.4 Conventions and planning files

#### 5.4.1 `skills/CONVENTIONS.md`

The file is the contract for all skills, not a skill.

| Part | Lines | Rule |
|------|-------|------|
| Progress reporting | 7-33 | Each skill emits `[skill] Step\|Paso\|Fase\|Phase N - title` before a step, `[skill] next -> ...` after it, and `[skill] done` at the end. The line goes to the conversation and is appended to `progress.md` only if the file exists (`[ -f progress.md ] && echo ... >>`, never `tee -a`). The word must match the skill's own headings. Jans shows the last line as the subtitle |
| Recovery tools | 37-45 | Mention `/rewind` in skills that auto-fix, `/btw` in long-analysis skills |
| `/loop` for CI | 49-57 | Suggested after PR open (`/pre-pr` Fase 8b) |
| Language policy | 61-117 | Skill content in English, user communication in Spanish. Spanish skills migrate one at a time: backup, translation that changes no behavior, read check, smoke run, backup removal |
| Migration status table | 119-150 | One row per skill: language, stability, readiness |
| Adding a new skill | 154-176 | Template for the `Progress reporting` block, placed before the first step heading |

`jandro-skills` has no progress block (a pure index skill). The marker word differs per skill (`Step`, `Paso`, `Fase`, `Phase`). The Jans parser ignores the word.

#### 5.4.2 Planning files per session directory

Files live in the session cwd. `~/.gitignore_global` ignores all of them except `.strike_count_*` (D-33).

| File | Created by | Written by | Read by | Injected each prompt? |
|------|------------|------------|---------|------------------------|
| `task_plan.md` | Jans scaffold (`gui.py:209,236,249`). `/start-research` and `/link-feature` recreate it | `/pre-code` appends `- [ ] TODO-N`. `/implement` ticks boxes | Hook (all modes use it as the gate), `/implement`, `/resume-status`, `/pre-pr`, `plan-lock.sh` | Yes, `head -200` |
| `progress.md` | Jans scaffold (`gui.py:225,237,251`), `/review-pr` Phase 0 | Every skill (markers), the model | Hook, Jans (subtitle), `/resume-status` | Yes, `tail -20` |
| `decisions.md` | `/pre-code` (`pre-code:88-92`) | `/implement` (strike log), `/pre-code` | Hook, `/pre-pr` (propagates to the manifest), `/finish-pr` | Yes, `tail -80` |
| `task_coding_rules.md` | `/pre-code` | `/pre-code` | Hook, the `/implement` agent, `/pre-pr` Capa 3 | Yes, whole file |
| `.claude-invariants.md` | `/pre-code` | `/pre-code`. `/quality` appends `## §N - Candidate invariants` or creates the file (`quality:292-302`) | The `/implement` agent, `/quality`, `/pre-pr`, `/finish-pr`, `plan-lock.sh` | No |
| `session.md` | Jans scaffold (`gui.py:200-262`), `/start-research`, `/link-feature` | `/link-feature` (`feature:`, `related_sessions:`), `/start-research` (`related_projects:`), `/finish-research` (`closed:`, `contributed_to:`) | Hook (`feature:` line only), most skills | No |
| `findings.md` | Jans scaffold (research, tool), `/start-research`, `/review-pr` deep | The model, skills | `/finish-research`, `/resume-status` | No |
| `.session-model` | Hook stamp (default) | `/pre-code` Paso 6 (user choice), `/implement` Step 1 if missing | `/implement`, `/quality`, `/pre-pr`, `/finish-pr` | No |
| `.strike_count_<TODO-ID>` | `/implement` Step 7b | `/implement`, the user | Hook `pretool` | No |
| `.plan-lock*` (4 files) | `plan-lock.sh lock` | `plan-lock.sh lock` | `plan-lock.sh verify` | No |

Review sessions (`type: pr-review-incoming`) get `session.md` only (`gui.py:255-262`), so injection and the strike gate do not apply. `review-pr:56-63` is the table of who creates which file in a review session.

### 5.5 Development flow skills

The ten skills form one chain: `pre-code` -> `implement` (per TODO) -> `quality` -> `pre-pr` -> `pr-describe` -> reviewer loop (`pre-pr --iteration`) -> `finish-pr`. Four skills are side branches: `pr-review`, `pr-deep-review`, `codex-review` and `update-agents-md`. Each skill directory holds only `SKILL.md`. Only `pre-code`, `implement` and `pre-pr` spawn sub-agents. None of the ten sets `model:` in its frontmatter. Eight of the ten bodies are Spanish (`conv:121-131`).

Flow, in the order of `workflow:47-151`, merged with `quickref:5-16` and the calls inside each skill (`*` marks optional steps):

```
PHASE 0   /pre-code [prior-invariants.md | spec.md | text]
            |  writes .claude-invariants.md, task_coding_rules.md, task_plan.md (append),
            |  decisions.md, .session-model, .plan-lock*          (plan-lock.sh lock)
            v
PHASE 1   /implement [TODO-N] [model]      repeated once per TODO
            |  strike files .strike_count_TODO-N, decisions.md on failure
            v
PHASE 2   /quality *                        Passes A, B, C, then Pass X (Codex MCP)
            |  coding-rules.md, quality-metrics.log, may append to .claude-invariants.md
            v
          /pr-review *        (KB invariant check only; pre-pr Fase 2c repeats it)
          /pr-deep-review *   (interactive file-by-file walkthrough)
          /codex-review *     (interactive Codex MCP review)
            v
PHASE 3   /pre-pr                           Fase 1 plan-lock verify
            |  2b acceptance + scope, 2c domain check, 3+4 two Opus sub-agents,
            |  5 merge, 6 fixes, 6b coding-rules, 6c Gradle tests + muzzle, 7 ONE commit
            v
PHASE 4   Fase 8 of /pre-pr calls /pr-describe  (gh pr create --draft)
            |  Fase 8b: gh pr comment "@codex review"  (dd-trace-java only)
            |  Fase 8c: decisions.md -> feature manifest
            |  Fase 10: pre-pr-metrics.log
            v
PHASE 5   reviewer comments
            |  /pre-pr --iteration [sha | comment-url]   (loops, 1 commit + push per round)
            |  /update-agents-md *   (decide AGENTS.md changes while the PR is open)
            v
          merge (GitHub merge queue)
            v
PHASE 6   /finish-pr
               KB consolidation, prs/pr-N/ archive, metrics, worktree + branch + Jans session removal
```

The four sources that define the order disagree (D-21):

| Topic | `workflow` | `quickref` | Jans scaffold (`gui.py:284-290`) | Guide | The skill itself |
|-------|-----------|-----------|----------------------------------|-------|------------------|
| `/implement` | Phase 1 step 1.3 (`workflow:72`) | Listed (`quickref:24`), absent from the "when to use" table (`quickref:5-16`) | Phase 1 "Implementation", no command | Step 2 (`guide:248`) | Requires `/pre-code` first (`implement:55`) |
| `/quality` | Optional, "in parallel" (`workflow:84-88`) | "in parallel" (`quickref:25`) | Phase 2, optional | Step 3 "in parallel" | "sequential, independent passes" (`quality:3`, `quality:86`) |
| `/pr-review` | Quick reference only (`workflow:279`) | Not mentioned | Not mentioned | Step 4 and cheatsheet (`guide:420`) | `/pre-pr` "replaces" it (`pre-pr:3`). Fase 2c reuses its procedure (`pre-pr:214`) |
| `/pr-deep-review` | Optional before `/pre-pr` (`workflow:109`) | Not mentioned | Not mentioned | Not mentioned | Standalone |
| `/codex-review` | Phase 5.1 fallback (`workflow:129`) | Support list (`quickref:52`) | Not mentioned | Not mentioned | Redundant after `/pre-pr` Fase 8b (`codex-review:10`). `/quality` Pass X also runs Codex (`quality:154`) |
| `/pr-describe` | Separate Phase 4 step (`workflow:117`) | `/quality` -> `/pre-pr` -> `/pr-describe` (`quickref:8`) | Phase 4 | Step 6 | `/pre-pr` Fase 8 calls it (`pre-pr:475`). A manual run afterwards takes the "PR exists" branch `gh pr edit` (`pr-describe:189-194`) |
| `/update-agents-md` | Quick reference only (`workflow:283`) | "before merging" (`quickref:51`) | Not mentioned | "while the PR is still open" | `finish-pr` suggests it after the merge (`finish-pr:505-510`) |
| Review-round commit | `"fix: review comments round N"` (`workflow:132`) | n/a | n/a | n/a | `"address review comments"` (`pre-pr:718`) |

#### `pre-code` (1358 lines, 66,686 bytes)

- **Purpose and trigger.** Discover domain invariants and the canonical pattern before code is written. `/pre-code [arg]`: a prior `.claude-invariants.md` (extend it), a spec `.md`, or inline task text. Without an argument it reads the conversation (`pre-code:42-53`). A retroactive mode checks an existing PR diff against KB invariants (`pre-code:55-78`). `workflow:275` says "Always, before coding".
- **Steps.** Paso 0 task text, create `progress.md` and `decisions.md` (`pre-code:80-102`). Paso 0.5 detect the project from the git remote, check `docs/`, optional Google Doc through MCP (`pre-code:109-157`). Paso 0.6 fetch and offer a rebase (`pre-code:161-202`). Paso 1 classify the task (`pre-code:206-241`). Paso 1.5 load the KB: `kb-domains.sh list`, `_common/pr-review.md`, `<repo>/pr-review.md`, `coding-rules.md`, the manifest, closed PRs, the research cache, `kb-domains.sh prs` (`pre-code:245-426`). Paso 2 reference example through an Explore agent (`pre-code:430-459`). Paso 3 parallel Explore agents A to E (`pre-code:463-638`). Paso 4 synthesis with `ultrathink` (`pre-code:642-704`). Paso 4.9 Metis adversarial plan review (`pre-code:707-750`). Paso 4.5 checkpoint, the user confirms (`pre-code:754-833`). Paso 5 write `.claude-invariants.md` and `task_coding_rules.md` (max 40 lines) (`pre-code:837-1108`). Paso 5.5 append TODOs to `task_plan.md`, preview, confirm, `plan-lock.sh lock` (`pre-code:1112-1220`). Paso 6 summary and model choice into `.session-model` (`pre-code:1224-1278`). Paso 6.5 update the domain KB (`pre-code:1282-1346`).
- **Inputs.** The codebase, the repo `docs/` (dd-trace-java), the KB layers, `session.md`, `git`, `gh pr diff`, `kb-domains.sh`, the Datadog MCP (span check, `pre-code:283-297`), the Google Workspace MCP (`pre-code:150-155`), the `LSP` tool with the `jdtls-lsp` plugin (`pre-code:467`).
- **Outputs.** `.claude-invariants.md`, `task_coding_rules.md`, `task_plan.md` (append only), the `decisions.md` header, a `progress.md` checkpoint block (`pre-code:813-827`), `.session-model`, `.plan-lock*`, KB domain entries with frontmatter (`pre-code:1328-1340`). No metrics log.
- **Sub-agents and models.** Up to 5 parallel `Agent(Explore, ...)` calls for dd-trace-java and 4 for system-tests (`pre-code:473-637`). One `Agent(general-purpose, model: opus)` for Metis (`pre-code:718`). The model menu for `/implement` offers `sonnet-4.6`, `opus-4.8`, `sonnet-5`, `opus-5` and "other" (`pre-code:1248-1251`). The skill estimates 10 to 20 minutes and 4 to 6 agents (`pre-code:1353`).
- **Hooks and planning files.** Creates `decisions.md`, which the write guard protects later (`pre-code:102`). Locks the plan at the end of Paso 5.5 (`pre-code:1217`). The hook injects `task_coding_rules.md` whole and `task_plan.md` up to 200 lines (`pre-code:1118`, `inject-plan.sh:91-96`). Overwrites the default `.session-model` (`pre-code:1259-1262`). Marker word `Paso` (`pre-code:15`).
- **Position.** First step of a task session. Not for research sessions (`workflow:168`).
- **Signals of age.** Fixed model labels and no `haiku` or `fable` entry (O-11). Paso 4.9 asks for a draft checklist that no earlier step produces (D-27). `touch progress.md` runs unconditionally (`pre-code:85`) while the checkpoint says never to create it (`pre-code:829`); low impact because Jans scaffolds it. `Commit:`, `Blocks:` and `Blocked-by:` sub-bullets are not enforced (O-10). dd-trace-java and system-tests branches are hard coded (`pre-code:133-137`); other repos get a generic path with no agent prompts. Spanish body, "actively changing" (`conv:123`).

#### `implement` (427 lines, 15,971 bytes)

- **Purpose and trigger.** Run one TODO of `task_plan.md` in a focused sub-agent. `/implement`, `/implement TODO-1`, `/implement TODO-1 sonnet` (a one-shot model override: `sonnet`, `opus`, `haiku`, `fable`) (`implement:30-40`).
- **Steps.** Step 1 check that `task_plan.md` and `.claude-invariants.md` exist (with Glob) and resolve the model (`implement:44-117`). Step 2 select the TODO (`implement:121-141`). Step 3 read the strike count and stop at 3 (`implement:145-185`). Step 4 build a self-contained prompt from the verbatim TODO block, the full invariants, the full coding rules and past failures (`implement:189-250`). Step 5 launch `Agent(model, prompt)` (`implement:254-263`). Step 6 show the result; the user answers success, failure or review (`implement:267-284`). Step 7a on success set `[x]`, write progress, remove the strike file (`implement:288-324`). Step 7b on failure append to `decisions.md` first, then write the strike file (`implement:328-405`). Step 7c on review show `git diff` (`implement:409-418`).
- **Inputs and outputs.** Reads the planning files and `.strike_count_<TODO-ID>`. Writes code (through the agent), `[x]`, a status line in `progress.md` (`implement:302`, `380`), the strike file and the strike block. No commit, no metrics.
- **Sub-agents and models.** One `Agent` per TODO with no `subagent_type` (`implement:256-261`). Model map: `default` -> sonnet, `opusplan` -> opus, else the family substring, unknown -> sonnet (`implement:78-105`).
- **Hooks.** Uses Glob and Read instead of Bash in Steps 1 and 2 so the `pretool` gate does not trip before strike handling (`implement:46-48`, `123-126`). Writes `decisions.md` with Edit because only Write and Edit on `decisions.md` are allowlisted at 3 strikes (`implement:352-358`). The order rule is `decisions.md` before the counter (`implement:330-333`). `plan-lock.sh:24-26` ignores the checkbox flips.
- **Signals of age.** The "`.session-model` missing" branch is dead while hooks run (O-09). No Step 7 branch has an explicit command for `[implement] done`; only the general protocol asks for it (`implement:28`, `299-324`). Archived `progress.md` files contain 8 such lines, so the model writes it anyway. `implement:427` says `/pre-pr` runs "the full test suite" (D-49). `sed -i ''` is BSD-only (`implement:294-296`). `default` -> `sonnet` holds only while `settings.json` says `sonnet` (`implement:96`).

#### `quality` (431 lines, 20,028 bytes)

- **Purpose and trigger.** Review the own branch for tech debt, simplification and correctness, check each finding against domain invariants, apply valid fixes and grow `coding-rules.md`. `/quality [file]`; without an argument it reviews `origin/$DEFAULT_BRANCH..HEAD` (`quality:78-80`). Optional (`workflow:84-90`).
- **Steps.** Context guard: stop inside `~/reviews/` or a `pr-review-incoming` session (`quality:30-44`). Step 0 load context and KB (`quality:48-80`). Step 1 passes A (techdebt), B (simplify) and C (code review) plus a mandatory checkpoint (`quality:84-145`). Pass X: Codex MCP after the checkpoint (`quality:149-172`). Step 2 classify VALID, CONFLICTS, NEEDS-JUDGMENT against invariants (`quality:176-203`). Step 3 findings table and confirmation (`quality:207-233`). Step 4 apply fixes and run `./gradlew spotlessApply` (`quality:237-260`). Step 5 write `coding-rules.md`, exceptions and candidate invariants (`quality:264-363`). Step 6 metrics line and summary (`quality:368-431`).
- **Inputs and outputs.** Reads `.claude-invariants.md`, `kb:<repo>/coding-rules.md`, the first 100 lines of `kb:<repo>/pr-review.md` (`quality:74-75`), the diff, `gh pr view`, the Codex MCP and the `LSP` tool (`quality:88`). Writes source edits, `coding-rules.md`, an optional `## §N - Candidate invariants` section (`quality:288-311`) and one metrics line to `progress.md` and `kb:<repo>/quality-metrics.log` (`quality:395-410`), with `codex-findings`, `codex-valid` and `codex-conflicts` fields (`quality:385-391`).
- **Sub-agents and models.** No Agent calls. All passes share the session context. Codex parameters: `cwd`, `sandbox: read-only`, `approval-policy: never`, `model: gpt-5.6-sol`, `config: {model_reasoning_effort: xhigh, personality: pragmatic}` (`quality:156-163`). `quickref:65` recommends Sonnet.
- **Hooks.** Reads `.session-model` with `awk '{print $1}'` (`quality:375-381`). An append to `.claude-invariants.md` makes the next `plan-lock.sh verify` warn; the skill says so (`quality:309-311`). Pass X has no marker of its own.
- **Signals of age.** "Sequential" against "in parallel" in the guides (D-55). Passes B and C and `spotlessApply` are Java and Gradle specific (`quality:99-115`, `259`). Pass X is always on with no light mode (P-06). The Codex parameters exist in three skills (D-56). The context guard is copied into five skills (D-57).

#### `pr-review` (167 lines, 9,353 bytes)

- **Purpose and trigger.** A loader plus the "Knowledge Base Invariant Check": load `_common/pr-review.md` and `<repo>/pr-review.md`, resolve domain entries with `kb-domains.sh match`, check the diff against each invariant and print a table (`pr-review:57-167`). `/pr-review`, no arguments, own branch only (`pr-review:41-45`).
- **Steps.** Context guard (`pr-review:39-53`). KB loading (`pr-review:57-77`). Invariant check: Paso 1 diff and domain match, Paso 2 staleness through `last_verified_commit`, Paso 3 verify with `ultrathink`, Paso 4 report (`pr-review:81-167`).
- **Outputs.** A table in the conversation. No file, no KB write, no metrics. No sub-agents.
- **Position.** Optional between `/quality` and `/pre-pr`. `/pre-pr` Fase 2c runs the same procedure (`pre-pr:214`).
- **Signals of age.** The intro still describes a checklist with reviewer quotes (O-08). `pre-pr:3` says `/pre-pr` replaces it, yet `workflow:279` and the guide list it as a step and `quickref` omits it. `finish-pr` still calls the KB file "the `/pr-review` checklist" (`finish-pr:123`, `143`, `202`, `699`). Paso 3 examples are dd-trace-java specific and labelled (`pr-review:129-142`). Marker word `Step` against `Paso` headings (D-71).

#### `pre-pr` (742 lines, 30,773 bytes)

- **Purpose and trigger.** Gate before a PR: plan compliance, double review, batch fixes, one commit, draft PR. `/pre-pr`, `/pre-pr --iteration`, `/pre-pr --iteration <sha | comment-url>` (`pre-pr:35-38`, `596-598`). It never applies fixes without confirmation (`pre-pr:10-13`).
- **Steps, normal mode.** Context guard (`pre-pr:42-56`). Fase 1 snapshot, clean tree, `plan-lock.sh verify` (`pre-pr:60-95`). Fase 2 load KB and planning files (`pre-pr:99-118`). Fase 2b run every `verify:` command, then scope fidelity against `task_plan.md` (`pre-pr:122-208`). Fase 2c domain invariant check (`pre-pr:212-224`). Fase 3 and 4 two parallel Opus sub-agents, A (KB rules) and B (adversarial) (`pre-pr:228-247`). Fase 5 merge with the priority invariants > project rules > coding rules > adversarial (`pre-pr:251-284`). Fase 6 fixes and `./gradlew spotlessApply` (`pre-pr:288-303`). Fase 6b `coding-rules.md` and log (`pre-pr:307-330`). Fase 6c affected-module Gradle tests and muzzle (`pre-pr:334-438`). Fase 7 one commit `review: pre-PR checks` (`pre-pr:442-461`). Fase 8 call `/pr-describe` if no PR exists (`pre-pr:465-477`). Fase 8b `gh pr comment --body "@codex review"`, dd-trace-java only, and a `/loop 3m` suggestion (`pre-pr:481-506`). Fase 8c append `decisions.md` to the manifest (`pre-pr:510-543`). Fase 9 optional `arpcli review` (`pre-pr:547-559`). Fase 10 metrics (`pre-pr:563-588`).
- **Iteration mode.** I-1 scope (last review, SHA or comment, force-push detection), I-2 and I-2c KB, I-3 comment status, I-4 four passes A to D, I-5 merge, I-6 fixes, I-7 coding rules, I-8 commit `address review comments` and `git push`, I-9 metrics (`pre-pr:592-742`).
- **Inputs and outputs.** `git`, `gh` (`pr view`, `api`, `pr comment`), the planning files, KB `pr-review.md` and `domain/`, `plan-lock.sh`, `kb-domains.sh`, Gradle, `arpcli`. Writes one commit, the draft PR (through `/pr-describe`), the `@codex review` comment, `coding-rules.md`, the manifest `## Key decisions` block, and lines in `pre-pr-metrics.log` and `progress.md`.
- **Sub-agents and models.** `Agent(subagent_type: general-purpose, model: opus)` twice in one message (`pre-pr:230`). Each resolves the diff itself. `quickref:63` still lists "Fases 3+4: Opus" as a session-model recommendation.
- **Hooks.** `plan-lock.sh verify` at Fase 1; a mismatch asks the user and never blocks (`pre-pr:92-95`). Reads `.session-model` (`pre-pr:324-328`) and `verify:` lines (`pre-pr:128-145`). Skips scope analysis when `task_plan.md` has no real TODOs (`pre-pr:193`). Marker word `Fase` with letters (`pre-pr:25`).
- **Signals of age.** The guide's "cannot switch models" note for Fase 3 does not exist here (D-20). A stale Fase 9 reference (D-67). The header omits the SHA form (D-28). Iteration passes A to C repeat `/quality` text (`pre-pr:673-691`) and run in one context, unlike normal mode (`pre-pr:693-695`). `arpcli` (`pre-pr:549-557`) and `@codex review` (`pre-pr:488`) are Datadog-internal or bot-specific.

#### `pr-describe` (230 lines, 10,550 bytes)

- **Purpose and trigger.** Write a PR title and body in the dd-trace-java template and one author's style, then create or update the PR. `/pr-describe`, no arguments. Normally called by `/pre-pr` Fase 8 (`pre-pr:475`).
- **Steps.** Paso 1 context and Jira key from the branch or commits, stacked-branch handling (`pr-describe:32-70`). Paso 2 ask for the ticket (`pr-describe:74-80`). Paso 3 title rules (`pr-describe:84-112`). Paso 4 body template (`pr-describe:116-170`). Paso 5 publish: A `gh pr create --draft`, B `gh pr edit`, C markdown (`pr-describe:174-214`). Paso 5b labels (`pr-describe:218-222`). Paso 6 confirm (`pr-describe:224-230`).
- **Outputs.** A draft or edited PR, labels (`type:`, `comp:` or `inst:`), or markdown. No KB write, no metrics. It prints a reminder to run `/update-agents-md` (`pr-describe:214`).
- **Signals of age.** Hard coded to `DataDog/dd-trace-java` and one author (`pr-describe:3`, `86-112`, `118-145`), yet called for any repo (D-29). No push before `gh pr create` (D-19). Option B replaces the full body, manual edits included (`pr-describe:191-194`). Paso 5b has no step number in the progress sequence and comes after the "final" Paso 5 text.

#### `finish-pr` (737 lines, 31,349 bytes)

- **Purpose and trigger.** Close a merged PR: consolidate invariants into the KB, archive session context, update the PR cache, compute review metrics, remove the worktree, the branch and the Jans session. `/finish-pr`, no arguments. Works when the worktree is already gone (path B) (`finish-pr:3`).
- **Steps.** Paso 0 detect the repo; stop if the cwd is the worktree to delete (`finish-pr:28-71`). Paso 1 load invariants: path A from the file, path B from the PR cache (`finish-pr:75-90`). Paso 1.5 analyse commits, review comments and `decisions.md` into list A (invariants) and list B (checklist additions) (`finish-pr:94-153`). Paso 2 classify into domain KB or PR cache, with two pauses (`finish-pr:157-212`). Paso 3 write domain entries (`finish-pr:216-249`). Paso 4 copy session files to `prs/pr-N/` (`finish-pr:253-293`). Paso 5 update `prs/pr-N.md` (`finish-pr:297-334`). Paso 5.5 final PR description review (`finish-pr:338-368`). Paso 5.6 review metrics and correlation (`finish-pr:372-491`). Paso 5.7 AGENTS.md reconciliation (`finish-pr:495-512`). Paso 5.8 manifest update (`finish-pr:516-551`). Paso 6 cleanup with confirmation (`finish-pr:555-591`). Paso 6.5 kill the Claude session and delete the Jans session (`finish-pr:595-677`). Paso 7 summary (`finish-pr:681-728`).
- **Inputs.** The planning files, `gh api` (reviews, comments), KB `pr-review.md`, `_common/pr-review.md`, `pre-pr-metrics.log`, `quality-metrics.log`, `~/.claude/sessions/*.json`, `~/.jans/state.json`, `jans-ctl`.
- **Outputs.** KB domain entries, `prs/pr-N/{invariants,coding-rules,progress,findings,decisions}.md`, `prs/pr-N-invariants.md`, `prs/pr-N.md`, additions to `<repo>/pr-review.md`, a manifest `## Closed PRs` row, `finish-pr-metrics.log`, an optional PR description edit. Deletes the worktree, the local branch, the Claude session file and the Jans session.
- **Sub-agents and models.** None. It asks for the implementation model only when `.session-model` is absent (`finish-pr:435-445`).
- **Hooks.** Copies the planning files before the worktree goes (`finish-pr:261-278`). Reads `.session-model` (`finish-pr:431`) and `feature:` (`finish-pr:527`). Depends on the 5 s Jans CLI timeout (`commands.py:8`, `23`, documented at `finish-pr:672-677`).
- **Signals of age.** Says no skill reads `prs/pr-N-invariants.md`, but Paso 1 uses it (D-24). New domain entries lack `description`, `source_files` and `stability` (D-12). Paso 5.5 edits a merged PR (O-12). Eight responsibilities in one skill. Paso 5.7 and 5.8 are skipped on path B (`finish-pr:497`, `518`), against the "works without the worktree" promise. Spanish body.

#### `update-agents-md` (239 lines, 10,772 bytes)

- **Purpose and trigger.** Analyse the PR diff, apply a three-question filter ("Santi's filter"), then create or update `AGENTS.md` files, add code comments or propose tests. `/update-agents-md`, no arguments. Meant for while the PR is open (`quickref:51`, `pr-describe:214`).
- **Steps.** Paso 0 context (`update-agents-md:30-46`). Paso 1 diff and existing `AGENTS.md` (`update-agents-md:50-73`). Paso 2 candidates (`update-agents-md:77-92`). Paso 3 filter, lists A and B (`update-agents-md:96-117`). Paso 4 destination (`update-agents-md:121-137`). Paso 5 proposal and pause (`update-agents-md:141-167`). Paso 6 write `AGENTS.md` (`update-agents-md:171-197`). Paso 6.5 inline comments (`update-agents-md:201-207`). Paso 7 summary (`update-agents-md:211-228`).
- **Inputs and outputs.** `git diff`, `gh pr view`, `AGENTS.md` files up to two levels up, optional `kb:<repo>/prs/pr-N.md`. Writes `AGENTS.md` and Java comments in the working tree. No commit, no push, no log. No sub-agents.
- **Position.** Phase 5, between PR creation and merge. Afterwards `/finish-pr` marks the invariants as `documented_in_repo` (`finish-pr:503`).
- **Signals of age.** The PR cache input is dead before merge (O-13). The filter text also lives in `pre-code:664-666` and `finish-pr:163-167` (D-57). dd-trace-java filters: a directory regex (`update-agents-md:59`) and Java comments (`update-agents-md:203-207`). In no `workflow` phase table (only `workflow:283`). Spanish body.

#### `pr-deep-review` (192 lines, 8,271 bytes)

- **Purpose and trigger.** An interactive, file-by-file walkthrough of the own PR before it opens. `/pr-deep-review`, no arguments (`pr-deep-review:6-14`). `workflow:109` and `workflow:280` place it before `/pre-pr` for complex changes.
- **Steps.** Context guard (`pr-deep-review:38-54`). Paso 1 context and commit hygiene (`pr-deep-review:58-87`). Paso 2 review order (`pr-deep-review:91-100`). Paso 3 per file: presentation, annotated diff, checklist, verdict LGTM, SUGERENCIA or ATENCION, mandatory pause (`pr-deep-review:104-154`). Paso 4 summary and checklist (`pr-deep-review:158-181`).
- **Inputs and outputs.** `git diff`, `git log`, commit bodies (`co-authored-by` grep, `pr-deep-review:78`). Conversation only. No sub-agents; the whole diff stays in the main context (`pr-deep-review:119`).
- **Signals of age.** Refers to "the smola/manuel checklist" but never loads one (D-50). Overlaps `/pre-pr` and `/review-pr` deep mode, which its own guard names (`pr-deep-review:50-53`). Java specifics (`pr-deep-review:132-136`, `177`). Absent from `quickref` and from the Jans scaffold. Spanish body.

#### `codex-review` (139 lines, 6,469 bytes)

- **Purpose and trigger.** Interactive review of the current branch by the Codex MCP, "like `@codex review` on GitHub". `/codex-review [extra context]`. The scope is always `origin/$DEFAULT_BRANCH..HEAD` (`codex-review:6-10`).
- **Steps.** Context guard (`codex-review:55-74`). Paso 1 branch, commits, files (`codex-review:78-94`). Paso 2 build the prompt (`codex-review:98-115`). Paso 3 call the MCP (`codex-review:119-127`). Paso 4 present results and ask before applying (`codex-review:131-139`).
- **Inputs.** `git` and the Codex MCP with `cwd`, `sandbox: read-only`, `approval-policy: never`, `model: gpt-5.6-sol`, `config: {model_reasoning_effort: xhigh, personality: pragmatic}` (`codex-review:32-41`). It needs Codex CLI >= 0.147.0 from npm (`codex-review:43`) and corporate SSO (`codex-review:47-51`).
- **Outputs.** Conversation only. No metrics.
- **Signals of age.** The prompt says "compared to master/main" (D-68). Three Codex entry points with no shared log (`quality:154`, `pre-pr:488`, this skill); only `/quality` logs `codex-*` counters (`quality:385-391`). Pinned model id and CLI version (`codex-review:40`, `43`); a Homebrew install breaks it. No branch for a disconnected MCP (D-30). Spanish body.

### 5.6 Review, research and coordination skills

The five skills form one lifecycle. `/review-pr` handles other people's PRs. `/start-research` and `/finish-research` open and close research sessions. `/link-feature` ties sessions, PRs and research to a manifest. `/resume-status` recovers context from live files or KB caches. Together they are 2,798 lines (about 138 KB). They write three KB caches (`reviews/`, `research/`, `prs/pr-<n>/` archives) and the manifest, and read the caches only through `kb-domains.sh`. All five bodies are English.

#### `review-pr` (834 lines, 37,998 bytes)

- **Purpose and trigger.** Review another person's PR. `/review-pr [ref]`: a PR URL, `owner/repo#N` or a number. Without an argument it reads `repo:` and `pr:` from `session.md` (`review-pr:38-46`). Phase 0 always asks for a mode (`review-pr:86-100`): normal (diff plus KB rules) or deep (subsystem analysis, Codex cross-check, KB extraction, about 2-3x tokens). Enter selects normal. It never posts without explicit confirmation (`review-pr:12`).
- **Steps.** Phase 0 resolve the PR, create `progress.md`, pick the mode. Phase 1 check out the PR head, skipped when Jans already made the worktree. Phase 2 PR metadata and Jira, RFC and related-PR references. Phase 3 KB (`_common/pr-review.md`, `<project>/pr-review.md`, matched domain entries, and for dd-trace-java the repo `docs/`). Phase 3b (deep) Jira, Confluence, related PRs, subsystem reading, `findings.md`. Phase 4 diff review with blocking, non-blocking and nit; sections the KB marks "advisory" are capped at non-blocking. Phase 4b (deep) Codex cross-check after Claude's own findings. Phase 4c (deep) merge into CONFIRMED, CODEX-ONLY and CLAUDE-ONLY, filter Codex-only findings against the KB, deduplicate against the public Codex bot. Phase 5 findings table and post question. Phase 6 optional `gh pr review`. Phase 7: 7a KB extraction (deep), 7b archive, 7c review cache entry, 7d cleanup, 7e metrics.
- **Inputs.** `session.md`, `gh pr view`, `gh pr diff`, `gh api .../pulls/<n>/comments`, the KB (`kb-domains.sh match`, `review-pr:204`), dd-trace-java `docs/` (`review-pr:222-227`), the Atlassian MCP `getJiraIssue` (`review-pr:247-253`), `WebFetch` for Confluence, the `LSP` tool (`review-pr:285`, `334`), the Codex MCP (`review-pr:445-470`). The project comes from `git remote get-url origin`.
- **Outputs.** `progress.md` (`review-pr:76-84`), `findings.md` in deep mode (`review-pr:294-324`), the archive `kb:<project>/prs/pr-<n>/review-{session,progress,findings}.md` with older rounds renamed by mtime (`review-pr:638-643`), the review cache `kb:<project>/reviews/pr-<n>.md` (`review-pr:696-736`), domain additions in deep mode, each confirmed (`review-pr:602-622`), one line in `review-metrics.log` and `progress.md` (`review-pr:817-826`), `gh pr review --request-changes|--comment` (`review-pr:557-582`), and `jans-ctl delete` plus `git worktree remove --force` after a per-action question (`review-pr:765-810`).
- **Sub-agents and models.** No `model:` and no `Agent` call. Phase 3b recommends starting deep reviews from an Opus session because the skill cannot switch models (`review-pr:243`). The second model is Codex with parameters copied from `codex-review` (`review-pr:447-454`). `ultrathink` in Phases 3b and 4.
- **Hooks and manifests.** It creates no `task_plan.md` on purpose, so no injection and no strike gate apply (`review-pr:48-74`). `review-pr:56-63` is the source of truth for review-session files. It uses `Edit` for later `findings.md` additions (`review-pr:313-315`). Reviews are never linked to a manifest (`feature: standalone`, `review-pr:743-746`).
- **Position.** Before: Jans `＋ Review` or `jans-ctl new-review` (`gui.py:260`). After: the archive and the review cache feed `/resume-status` Step 2e and `/link-feature` Phase 2a.
- **Signals of age.** Phase 1 Steps 2-4 (`review-pr:114-159`) are a fallback; Jans already makes the worktree, so Step 1 short-circuits (`review-pr:161`). Phase 3 says "same logic as `/pr-review`" (`review-pr:191`) and repeats the invariant check (`review-pr:402-405`). dd-trace-java rules inside a generic skill (D-51). Edited recently, with many self-corrections.

#### `start-research` (398 lines, 17,072 bytes)

- **Purpose and trigger.** Start a research session with KB context. `/start-research`, no arguments (`start-research:1-4`), run from the session directory. Interactive only when `session.md` is missing or `related_projects` is empty. The mirror of `/finish-research`.
- **Steps.** Phase 1 stop on `type: pr-review-incoming`; read or create `session.md` (types research, task, tooling); create `task_plan.md` and `progress.md` if missing. Phase 2 load `_meta/tools.md` and `_common/pr-review.md`; inventory each related project with `kb-domains.sh list` and load only entries that fit the topic; check the research cache with `kb-domains.sh research`. Phase 3 if `feature:` is a ticket, load the manifest and fetch the Jira issue. Phase 4 create `findings.md` from a template (not for tooling) or summarize the existing one. Phase 5 print the summary.
- **Inputs.** The planning files, `_meta/tools.md`, `_common/pr-review.md`, `<project>/pr-review.md`, selected domain entries, research cache entries, the manifest, the Atlassian MCP with a hard-coded `cloudId` (`start-research:309-314`), `WebFetch`. A fallback loads the whole domain layer after a cost warning of 80-100k tokens (`start-research:269-276`).
- **Outputs.** `session.md` (3 scaffolds at `start-research:89-121`), `task_plan.md`, `progress.md`, `findings.md` (`start-research:137-151`, `333-357`). Console summary. No KB write, no metrics. No sub-agents.
- **Hooks.** Creating `task_plan.md` turns the injector on, and the skill says so (`start-research:130-134`). Tooling sessions get no `feature:` (`start-research:123-128`). It refuses review directories (`start-research:41-58`).
- **Signals of age.** Phase 1 duplicates Jans `_bootstrap_planning_files` (`gui.py:176-262`) for sessions made by hand. The copy must stay identical by hand (`start-research:82-87`) and has drifted (D-34). The frontmatter says it "creates findings.md", but Phase 4 skips that for tooling (`start-research:361-367`).

#### `finish-research` (715 lines, 43,350 bytes)

- **Purpose and trigger.** Close a research session by contributing findings to the KB. `/finish-research`, no arguments. It always asks before a KB write (`finish-research:13-16`). Modes by state: first close; already closed (`closed:` present), where the user picks summary only, reprocess new findings or full reprocess (`finish-research:55-79`); `type: tooling`, which promotes knowledge to `_meta/` and never closes (`finish-research:124-130`); `type: pr-review-incoming`, which stops and redirects (`finish-research:101-122`).
- **Steps.** Phase 1 read the files and check idempotence. Phase 2 resolve targets from `type` and `contribution_targets`. Phase 3 classify each finding as domain invariant, PR review rule, workflow insight, PR-specific context or SKIP (`ultrathink`, `finish-research:154`). Phase 4 propose each addition and wait for y, n or edit. Phase 5 write to the KB; project files need a 7-field frontmatter, `_meta/` and `_common/` none (`finish-research:215-283`). Phase 6 write `closed:` and `contributed_to:`, then a manifest narrative entry, the research cache entry, the `## Related research` row, the `## Active sessions` row, the final summary and `jans-ctl delete`.
- **Inputs.** The planning files, `findings.md` (with the `Started:` line), KB target files, `git -C ~/repos/<repo> rev-parse origin/HEAD` for `last_verified_commit` (`finish-research:246-255`), the manifest, `~/.jans/state.json` (`finish-research:661-682`).
- **Outputs.** KB `domain/*.md`, `pr-review.md`, `_meta/*.md`, and for legacy types `prs/pr-XXXX.md` (append, `finish-research:166-168`); `session.md` keys; the research cache (`finish-research:361-483`); manifest edits with `Edit` (`finish-research:316-614`); `jans-ctl delete` last (`finish-research:639-703`). No metrics log. No sub-agents.
- **Hooks and manifests.** The manifest is the main side effect; rows are keyed by session name. The hook injects the whole manifest into sibling sessions (`finish-research:490-494`). Its `feature:` parser (`finish-research:326`) must match `inject-plan.sh` by hand. It orders its work around the SIGTERM of `jans-ctl delete` (`finish-research:649-656`).
- **Signals of age.** Legacy types and a "Retroactive use" section (O-16). The directory-deletion claim is false (D-14). The `## Related research` table is shared with `/link-feature` Phase 4 by convention only (`finish-research:511`, `link-feature:335-338`).

#### `link-feature` (487 lines, 20,976 bytes)

- **Purpose and trigger.** Link sessions, closed PRs and closed research to a manifest. `/link-feature [TICKET-ID]` (`link-feature:8-11`): with a ticket, interactive for one feature; without, a sweep that infers groups by ticket and asks per group (`link-feature:191-212`). Runs from any directory. Every write is shown and asked first.
- **Steps.** Phase 1 discover live sessions (`~/tasks`, `~/repos`, `~/research`, `~/reviews`) and read `state.json` for the Jans `name`; `~/tools/` is skipped on purpose. Phase 2a discover closed PRs and research from the KB; skip reviews of other people's PRs and report them through `kb-domains.sh review`. Phase 2b (sweep) infer tickets from names, branches, `session.md` and frontmatter. Phase 3 validate; ask for a nickname and description. Phase 4 build the manifest (frontmatter, `Active sessions`, `Closed PRs`, `Related research`, `Key decisions`, `Cross-session invariants`, optional `related_features:`). Phase 5 patch `session.md` in each active session; create `task_plan.md` and `progress.md` for research sessions. Phase 6 summary and warnings.
- **Outputs.** The manifest; `feature:` and `related_sessions:` in `session.md`; minimal `session.md` files; `task_plan.md` and `progress.md` for research sessions. No GitHub or Jans action, no metrics. No sub-agents. The GUI reads `nickname:` from the manifest (`features.py:23,66`).
- **Hooks.** It warns when a linked session has no `task_plan.md`, because then no injection happens (`link-feature:481-487`). `sessions:` must hold the Jans `name` (`link-feature:55-59`).
- **Signals of age.** `related_sessions:` has no reader (O-14). Scan roots are wrong (D-54). Reviews are scanned but have no Phase 5 row (D-15). The manifest tables are also written by `/finish-research` and `/finish-pr`, and this skill reconciles them.

#### `resume-status` (364 lines, 19,534 bytes)

- **Purpose and trigger.** Resume work after a break. `/resume-status`, no arguments, read-only, from the session directory. Step 1 (`resume-status:49-77`) routes to one of seven paths: 2a planning files, 2b legacy `.claude-status.md`, 2c PR cache when the worktree is gone, 2d research cache, 2e review (2e.1 live, 2e.2 cache), 2f tooling. Tooling is checked first, then review, because of false matches the file describes.
- **Steps.** Step 1 gather `task_plan.md`, `session.md`, the `progress.md` tail, `.claude-status.md`, git state and `gh pr view` in parallel, route, and warn if a PR is MERGED while `.claude-invariants.md` still exists (`resume-status:79-90`). Step 2a-2f the selected branch. Step 3 print the git state.
- **Inputs and outputs.** Reads the planning files, `git`, `gh pr view` (`resume-status:31-42`), `prs/pr-{n}.md`, `kb-domains.sh research`, `kb-domains.sh review`, `prs/pr-<n>/review-*.md`, `review-metrics.log`, the manifest. Console only, plus its own markers in `progress.md` (`resume-status:11-27`). It never runs `/finish-pr` itself (`resume-status:90`).
- **Models.** The only skill of the 15 with `model:` in its frontmatter: `claude-haiku-4-5-20251001` (`resume-status:3`). No `Agent` call.
- **Signals of age.** Step 2b is legacy (O-15). Step 2c has two defects (D-10, D-11). The Spanish headings it reads have no known writer (D-52).

### 5.7 Cross-layer interactions

| Interaction | Producer | Consumer | Evidence |
|-------------|----------|----------|----------|
| Scaffold turns hooks on | Jans writes `task_plan.md` for research, task and tool sessions | `inject-plan.sh` plan gate | `gui.py:200-262`, `inject-plan.sh:34-36` |
| Review isolation | Jans writes only `session.md` for reviews; `/review-pr` never creates `task_plan.md` | Hook stays off | `gui.py:255-262`, `review-pr:48-74` |
| Executing marker | `inject-plan.sh pretool` writes, `posttool` and `stop` delete | Jans state detector (`processing` against `needs_input`) | `inject-plan.sh:13-32`, `state_detector.py:11-30`, `121-124` |
| Progress subtitle | Skills append markers to `progress.md` per `conv:7-33` | Jans `_read_last_progress`; `/resume-status` | `gui.py:295-313`, `resume-status:11-27` |
| Metrics lines in `progress.md` | `/quality`, `/pre-pr`, `/review-pr` | Jans shows them as a grey subtitle when last | `quality:397-400`, `pre-pr:329`, `pre-pr:581`, `review-pr:817-826` |
| Feature link | Jans (`session.md` `feature:` and manifest `sessions:`), `/link-feature` | Hook manifest injection, Jans Features tab | `features.py:105-122`, `inject-plan.sh:48-61` |
| Strike files | `/implement` Step 7b | `pretool` gate | `implement:374`, `inject-plan.sh:137-202` |
| `.session-model` | Hook stamp, `/pre-code` Paso 6 | `/implement`, `/quality`, `/pre-pr`, `/finish-pr` | `inject-plan.sh:38-46`, `pre-code:1262`, `quality:375-381`, `pre-pr:324-328`, `finish-pr:431` |
| Plan lock | `/pre-code` Paso 5.5 | `/pre-pr` Fase 1; `/quality` appends trip it | `pre-code:1217`, `pre-pr:92`, `quality:309-311` |
| Session removal | `/finish-pr`, `/finish-research`, `/review-pr` call `jans-ctl delete` | GUI removes the entry and sends SIGTERM to the cwd's Claude | `finish-pr:649-668`, `finish-research:639-703`, `review-pr:765-810`, `gui.py:1690-1705` |
| Direct `state.json` reads | `/link-feature`, `/finish-research`, `/finish-pr` | Map a cwd to the Jans `name` | `link-feature` Phase 1, `finish-research:661-682` |
| Scaffold copies | Jans `_task_plan_content` is kept byte-identical by hand with `/start-research` and `/link-feature` | All readers of `session.md` | `gui.py:272-273`, `start-research:82-87` |

## 6. Obsolescence verdicts

### 6.1 Verdict per skill and per hook

Verdicts: `keep` (no change needed beyond the defects listed elsewhere), `update` (keep the item, but change it), `merge into X` (move its unique part into X, then delete it), `remove`. Each verdict was checked against the sources after the partial findings were verified. The finding IDs point to sections 6.2, 7, 8 and 9.

| # | Item | Kind | Verdict | Reason | Evidence |
|---|------|------|---------|--------|----------|
| 1 | `pre-code` | Skill | `update` | The core of the flow and the main KB reader. Keep it. Fix the Metis input (D-27), drop or enforce the `Commit:` and `Blocked-by:` bullets (O-10), replace the fixed model labels (O-11), cap the agent count for small tasks (P-09), translate the body (D-45) | `pre-code:707-750`, `pre-code:1143-1144`, `pre-code:1248-1251`, `pre-code:473-637`, `conv:123` |
| 2 | `implement` | Skill | `update` | It keeps the orchestrating session cheap and owns the strike protocol. Remove the dead `.session-model` branch (O-09), fix the "full test suite" note (D-49) | `implement:107-117`, `implement:427`, `implement:328-405` |
| 3 | `quality` | Skill | `update` | It is the main writer of `coding-rules.md`. Fix the `pr: none` metrics join (D-31), add a light mode without Codex (P-06), make the Gradle steps conditional (`quality:99-115`, `259`), fix the "parallel" claim in the guides (D-55). It absorbs `codex-review` (row 10) | `quality:370-385`, `quality:154-163`, `finish-pr:465-467` |
| 4 | `pr-review` | Skill | `merge into pre-pr` | `/pre-pr` says it replaces this skill, and its Fase 2c runs the same procedure. `/review-pr` Phase 3 also repeats it. The intro describes a checklist that no longer exists (O-08). `quickref` does not list it. Keep the check as a read-only mode of `/pre-pr` (for example `--check-only`) | `pre-pr:3`, `pre-pr:212-224`, `review-pr:191`, `review-pr:402-405`, `pr-review:6-13`, `quickref:5-16` |
| 5 | `pre-pr` | Skill | `update` | The gate before every PR. Push the branch before `/pr-describe` (D-19), fix the `--iteration` anchor (D-26), document the SHA form and the checks that iteration mode skips (D-28), use one metrics schema (D-46), fix the Fase 9 reference (D-67), state the Opus sub-agent cost in the guides (D-20) | `pre-pr:442-477`, `pre-pr:597-609`, `pre-pr:35-38`, `pre-pr:328`, `pre-pr:726`, `pre-pr:230` |
| 6 | `pr-describe` | Skill | `update` | `/pre-pr` calls it for every repo, but it applies the dd-trace-java template. Detect the repo template first (D-29). Push before `gh pr create` (D-19). Do not overwrite manual body edits in option B | `pr-describe:3`, `pr-describe:118-145`, `pr-describe:178-194`, `quickref:28` |
| 7 | `finish-pr` | Skill | `update` | It closes the KB feedback loop. Remove the self-SIGTERM path (D-04), add the missing frontmatter keys to new entries (D-12), fix the "nobody reads it" claim (D-24), paginate `gh api` (D-32), fetch before range queries (D-40), drop Paso 5.5 (O-12). Consider a split: KB consolidation, metrics, cleanup | `finish-pr:47-62`, `finish-pr:599-640`, `finish-pr:226-236`, `finish-pr:85-88`, `finish-pr:104-105`, `finish-pr:338-368` |
| 8 | `update-agents-md` | Skill | `update` | Its job (repository notes that ship with the PR) has no other owner. Drop the dead PR cache input (O-13), fix `{REPO_NAME}` (D-75), stop `finish-pr` from suggesting it after the merge (D-48), make the Java filters conditional, translate the body | `update-agents-md:43-71`, `update-agents-md:59`, `update-agents-md:203-207`, `finish-pr:505-510` |
| 9 | `pr-deep-review` | Skill | `merge into review-pr` | It loads no KB and no checklist although it refers to one (D-50). Its own guard names `/review-pr` deep mode as the skill that "covers the same". It is in neither `quickref` nor the scaffold. Move the file-by-file walkthrough into `/review-pr` as an own-branch mode that reuses its KB loading (O-07) | `pr-deep-review:12`, `pr-deep-review:144`, `pr-deep-review:50-53`, `workflow:109` |
| 10 | `codex-review` | Skill | `merge into quality` | It is one of three Codex entry points with copied parameters (D-56) and no log. Its own text says it is redundant after `/pre-pr` Fase 8b. Expose `/quality` Pass X alone (for example `/quality --codex-only`) and keep one copy of the parameters (O-07) | `codex-review:10`, `codex-review:32-41`, `quality:149-172`, `pre-pr:488` |
| 11 | `review-pr` | Skill | `update` | The only skill for other people's PRs, current and much corrected. Write the metrics and the `done` marker before `jans-ctl delete` (D-05, D-72), move the dd-trace-java rules to the KB (D-51), split the text by mode (P-12), stop hiding `cp` errors (D-74), share the Codex parameters (D-56) | `review-pr:765-829`, `review-pr:32`, `review-pr:181`, `review-pr:211-227`, `review-pr:645-647` |
| 12 | `start-research` | Skill | `update` | It loads the KB context that research needs. Replace the hand copy of the Jans scaffold with one shared template (D-34). Move the Atlassian `cloudId` out of the text (C-19) | `start-research:82-121`, `start-research:309-314`, `gui.py:176-262` |
| 13 | `finish-research` | Skill | `update` | The only writer of the research cache. Fix the false "directory no longer exists" claim (D-14), drop the legacy types and the retroactive section (O-16), support all manifest table layouts or migrate them (D-53), split the text (P-12) | `finish-research:601-606`, `finish-research:132`, `finish-research:707-715`, `finish-research:598-602` |
| 14 | `link-feature` | Skill | `update` | The only repair tool for manifest drift. Keep review sessions unlinked (D-15), fix the scan roots (D-54), drop `related_sessions:` (O-14) | `link-feature:43`, `link-feature:367-383`, `link-feature:39-44`, `link-feature:390` |
| 15 | `resume-status` | Skill | `update` | Cheap recovery after a break. Fix the macOS `sed` (D-10) and the unreachable Step 2c (D-11), drop Step 2b (O-15), call `gh pr view` only for task sessions (P-14), simplify the routing for Haiku (P-15) | `resume-status:156`, `resume-status:59`, `resume-status:138-144`, `resume-status:41`, `resume-status:49-77` |
| 16 | `inject-plan.sh userprompt` | Hook | `update` | The core context channel. Add a byte cap per section (P-01), skip unchanged content (P-02), parse `feature:` and manifest list items safely (D-37, D-38), drop the scaffold phase list from the injection (P-05) | `inject-plan.sh:48-61`, `inject-plan.sh:63-86`, `inject-plan.sh:89-124` |
| 17 | `inject-plan.sh pretool` | Hook | `update` | The three-strikes gate and the executing marker. Use exact matches in the allowlist (D-06), extend the matcher to `MultiEdit` and `NotebookEdit` or drop that branch (D-07), fail closed with a clear message when `jq` is missing (D-41), read the TODO from the TODO section only (D-42), reject non-numeric strike files (D-77) | `inject-plan.sh:126-219`, `settings.json:164-172` |
| 18 | `inject-plan.sh posttool` | Hook | `update` | Keep the marker removal. Send the `progress.md` reminder only after Edit and Write, not after every Bash call (P-03) | `inject-plan.sh:221-231`, `settings.json:134-142` |
| 19 | `inject-plan.sh precompact` | Hook | `remove` | `PreCompact` cannot carry `additionalContext`, so the "flush progress" text reaches only the debug log. The hook has no effect (O-04) | `inject-plan.sh:233-243`, `settings.json:153-161` |
| 20 | `inject-plan.sh stop` | Hook | `keep` | It removes the executing marker after a blocked call or a denied permission prompt, which `posttool` cannot do. The leak in D-79 comes from a process that dies before `Stop` runs, not from this mode | `inject-plan.sh:25-32`, `state_detector.py:13-14` |
| 21 | `notepad-write-guard.sh` | Hook | `keep` | Small, correct and needed: `Write` would replace accumulated memory. No finding against it | `notepad-write-guard.sh:6-18`, `settings.json:173-181` |
| 22 | `auto-commit-config.sh` | Hook | `keep` | It makes every skill and KB edit recoverable (1,306 commits). The drift D-25 is in the guide text, which says "every change", not in the script. Fix the guide | `auto-commit-config.sh:10-30`, `settings.json:143-151`, `guide:54` |
| 23 | `plan-lock.sh` | Helper (not wired) | `keep` | It catches scope drift, ignores checkbox flips and never blocks, by design. The trip after a `/quality` append is documented | `plan-lock.sh:24-26`, `plan-lock.sh:50-99`, `quality:309-311` |
| 24 | `kb-domains.sh` | Helper (not wired) | `update` | The single KB resolver. Fix the header that calls `prs/pr-<n>-invariants.md` "consumed by nobody" (D-24). The docs that list four subcommands must list five (D-61) | `kb-domains.sh:44-47`, `kb-domains.sh:10-14`, `kb:_meta/README.md:99` |

Totals: 16 `update`, 3 `merge`, 1 `remove`, 4 `keep`.

### 6.2 Other obsolete items

| ID | Item | Evidence (file:line) | Impact | Action |
|----|------|----------------------|--------|--------|
| O-01 | Documents of the old design. `DEVELOPMENT.md` says `main` is the TUI and `menu-bar` is the active tkinter branch; `main` holds the GUI and its backlog item "implement handler `load`" is done. `JANS.md` and `ORCHESTRATOR.md` describe the Textual TUI and its command set | `DEVELOPMENT.md:26-28,79`, `gui.py:1725`, `JANS.md:84`, `ORCHESTRATOR.md:12` | Wrong map of the branches; agents that read them call old commands (D-17) | Delete `JANS.md` and `ORCHESTRATOR.md`, rewrite the branch section of `DEVELOPMENT.md` |
| O-02 | Legacy front ends: the Textual TUI (`app.py`, `widgets/`, `__main__.py`), `menubar.py`, `jans-menu.sh`, the `jans` script, and the dependencies `textual`, `pyte`, `ptyprocess`, `watchfiles`, `rumps`. `pyte`, `ptyprocess` and `watchfiles` are imported nowhere. `app.py` creates no scaffold files | `pyproject.toml:10-14`, `app.py:560-588`, `menubar.py:257-268` | Dead weight. The `jans` command still starts the old TUI while `jans.app` starts the GUI. Two front ends can consume the same IPC files | Remove them and their dependencies |
| O-03 | `web/` does not exist on `main`; it exists only on the abandoned `web-app` branch | `git ls-files`, `DEVELOPMENT.md:28` | None. Recorded so nobody searches for it | None |
| O-04 | The `PreCompact` hook is wired but cannot reach the model. Its echo goes to the debug log | `inject-plan.sh:234-242`, `settings.json:153-161` | A hook with no effect. The "flush progress" instruction is never seen | Remove (row 19 of 6.1) |
| O-05 | Two parallel domain layers: the flat `<repo>/*.md` layer ("legacy") and `domain/` ("current"). The migration is not finished: `dd-trace-java` has 17 flat files and 33 `domain/` files | `kb-domains.sh:4-6`, `kb:README.md:12,15` | Two places to search; `list` merges them | Finish the migration to `domain/` |
| O-06 | `crash-triage-java` and `error-triage-java` are superseded by `error-tracking-triage-java` and kept "untested for rollback" | `conv:140-142` | Three skills for one job; two never run | Remove after `error-tracking-triage-java` write paths are verified (out of scope skills) |
| O-07 | Four review mechanisms for one own-branch diff: `/pr-review`, `/pr-deep-review`, `/codex-review` and `/quality` Pass X, next to `/pre-pr` | `pre-pr:3`, `pre-pr:214`, `quality:154`, `workflow:109` | Duplicate cost and three places to maintain | Merges in rows 4, 9 and 10 of 6.1 |
| O-08 | The `pr-review` intro tells the reader to "walk each section and mark the items" with reviewer quotes. The file is a loader and has no checklist | `pr-review:6-13`, `pr-review:3` | Misleads readers | Goes with the merge into `pre-pr` |
| O-09 | The `/implement` branch for a missing `.session-model` cannot run while hooks are on: the hook stamps the file as soon as `task_plan.md` exists, and Step 1 requires `task_plan.md` | `implement:107-117`, `implement:55`, `inject-plan.sh:42-46` | Dead text; users never see the prompt | Remove, or keep only for runs without hooks |
| O-10 | `Commit:`, `Blocks:` and `Blocked-by:` sub-bullets are generated but no step enforces them: no commit step, no dependency check when a TODO is selected, and the hook takes the first unchecked box | `pre-code:1143-1144`, `implement:121-141`, `implement:193-203`, `implement:233-239`, `inject-plan.sh:209` | The agent still gets them as context, so keep them in any migration. Only mechanical enforcement is missing | Enforce `Blocked-by:` in `/implement` Step 2, or document the bullets as advisory |
| O-11 | The `pre-code` model menu has fixed version labels (`sonnet-4.6`, `opus-4.8`, `sonnet-5`, `opus-5`) that `/implement` reduces to a family. `haiku` and `fable` are missing, though `/implement` accepts both | `pre-code:1248-1251`, `implement:38-39`, `implement:80-88` | Labels go stale at each model release | Offer family names only |
| O-12 | `finish-pr` Paso 5.5 edits the description of a PR that is already merged | `finish-pr:338-368` | Low value, one more interaction | Remove the step |
| O-13 | `update-agents-md` reads a PR cache file that does not exist before the merge, by its own note | `update-agents-md:64`, `update-agents-md:71` | Dead input | Remove the input |
| O-14 | `related_sessions:` is written into `session.md`, but no hook or skill reads it. The skill admits it goes stale | `link-feature:367-376`, `link-feature:378-383` | Dead data and extra prompts per session | Stop writing it |
| O-15 | `resume-status` Step 2b and `.claude-status.md`: nothing in skills, hooks or Jans writes the file. Step 1 still reads it on every run, and the description advertises it | `resume-status:37`, `resume-status:58`, `resume-status:138-144`, `workflow:288` | Dead branch and a wasted read | Remove Step 2b |
| O-16 | `finish-research` legacy types `ticket` and `e2e-validation` have no producer in Jans, which writes research, task, tooling and pr-review-incoming only. The "Retroactive use" section covers directories older than `session.md` | `finish-research:132`, `finish-research:707-715`, `gui.py:202,230,242,260` | Dead branches in the longest skill after `review-pr` | Remove |

## 7. Defects and inconsistencies

All `drift` and `defect` findings, sorted by impact. **High**: data loss, a killed session, or a safety gate that does not hold. **Medium**: a wrong result, lost data or a failed command in normal use. **Low**: a stale document, noise or a cosmetic fault. Inside a level the order is by how often a user meets the fault. The `Src` column names the partial file the finding came from (`01` Jans app, `02` hooks and KB, `03` development skills, `04` review and research skills; `F<n>` is the ID in partial 04). Corrections made during verification are marked "Corrected" and listed in Appendix A.2.

### 7.1 High impact

| ID | Type | Item | Evidence (file:line) | Impact | Src |
|----|------|------|----------------------|--------|-----|
| D-01 | defect | The GUI right-click delete runs `shutil.rmtree` on the session cwd. For a task this is a git worktree: the directory goes, the worktree entry stays in the origin repo. For a `load`ed directory it can be a real project | `gui.py:1152-1169` | Data loss. Contradicts "delete never removes files" in every document | 01 |
| D-02 | defect | `load_saved_sessions` returns `[]` on any exception, for example one entry without `last_activity`. In `_merge_external_sessions` an empty disk list removes every non-active session from memory, and the next save writes the short list. Writes are not atomic | `persistence.py:73,79-81`, `persistence.py:51`, `gui.py:1124-1134` | One bad entry, for example from a hand or skill edit, can erase all paused sessions | 01 |
| D-03 | drift | `delete` is documented as "never kills Claude" (README) and "never deletes files" (`CLAUDE.md`). The GUI handler sends SIGTERM to the Claude process of the cwd | `README.md:137`, `CLAUDE.md:57`, `gui.py:1696-1701` | A delete from the orchestrator ends a live Claude run, possibly with unsaved work | 01 |
| D-04 | defect | `/finish-pr` lets the user "continue" inside the worktree that it will delete. Paso 6.5 then sends SIGTERM to the Claude process whose session file has that cwd, which is the running session. Paso 7 comes after it | `finish-pr:47-62`, `finish-pr:599-640`, `finish-pr:681` | Static reading, no archived run: the session ends before the Paso 7 summary and the `done` marker | 03 |
| D-05 | defect | `/review-pr` runs `jans-ctl delete` in 7d and writes the metrics line in 7e. The delete sends SIGTERM to the Claude process of that cwd, so the process can die before 7e. `/finish-research` avoids this by deleting last | `review-pr:785-788`, `review-pr:812-827`, `gui.py:1695-1701`, `finish-research:649-656` | The `review-metrics.log` line and the last marker can be lost when the user agrees to remove the Jans session. That log is the only long-term signal of review quality | 04 F2 |
| D-06 | defect | The strike-gate allowlist test `*"git stash"*` is a substring match. Under a 3-strike block, `echo git stash; cat /etc/hosts` exited 0 in a test | `inject-plan.sh:164-166` | Any Bash command that contains the text passes the gate, by accident or by design | 02 |
| D-07 | drift | The guide says the three-strikes hook "blocks further tool use". It blocks only `Edit`, `Write` and `Bash`. `Read`, `Grep`, `Agent` and MCP calls pass. The `MultiEdit\|NotebookEdit` branch of the allowlist cannot run, because the matcher excludes those tools | `guide:143`, `settings.json:165`, `inject-plan.sh:177` | A blocked session can still read and spawn agents, and `MultiEdit` and `NotebookEdit` can change code under 3 strikes | 02 |
| D-08 | drift | `switch` and `home` are documented in `CLAUDE.md`, `README.md`, `ORCHESTRATOR.md`, `JANS.md` and `usage()`, but the GUI has no handler. The orchestrator gets `unknown: switch` and `unknown: home` | `CLAUDE.md:34-35`, `ctl.py:37-38`, `gui.py:1761`, `app.py:435-447`, `README.md:139-140` | Every dictated "go to session X" fails. The README promises iTerm2 focus | 01 |

### 7.2 Medium impact

| ID | Type | Item | Evidence (file:line) | Impact | Src |
|----|------|------|----------------------|--------|-----|
| D-09 | defect | IPC uses one fixed command file and one fixed result file, with no lock and no request id. Two `jans-ctl` calls at once overwrite each other, and a caller can read another call's result. After a timeout the CLI deletes the command, but the GUI may have run it already | `commands.py:11-23` | Parallel orchestrator calls (several Bash calls in one turn) can drop or mix results | 01 |
| D-10 | defect | The `sed -E` command in `resume-status` Step 2c uses a lazy `+?`, which BSD sed on macOS rejects with `repetition-operator operand invalid` (reproduced). `PROJECT` stays empty and the lookup returns `NO_PR_CONTEXT`. Without the lazy operator the result would still keep `.git` | `resume-status:156` | PR cache recovery never finds a file on macOS, even when it exists | 04 F6 |
| D-11 | defect | Step 2c is routed when "the worktree is gone or the PR is merged". In the gone-worktree case it still needs `git remote get-url origin` and `gh pr view` from that cwd, and both fail. Corrected: the route is at line 59, and the merged-PR case is reachable | `resume-status:59`, `resume-status:148-158` | Recovery after a deleted worktree works only if the user gives the PR number by hand | 04 F7 |
| D-12 | defect | New KB entries from `/finish-pr` use a frontmatter without `description`, `source_files` or `stability`, unlike `/pre-code`. Corrected citation: the `match` subcommand is `kb-domains.sh:286-335` | `finish-pr:226-236`, `pre-code:1328-1340`, `kb-domains.sh:250-253`, `kb-domains.sh:301-308` | Entries print "no description", go to UNMATCHABLE and are not selected by `match` in `/pr-review` and `/pre-pr`. `pr-review:107` loads UNMATCHABLE entries by judgment, but "no description" gives that judgment little to use | 03 |
| D-13 | defect | `new-task` registers the session and returns ok before the worktree exists. The `fetch` and `worktree add` results are not checked. If `worktree add` fails (branch exists, no `origin/HEAD`), `mkdir` makes a plain directory and Claude starts in a non-git folder | `gui.py:1478-1518` | A silent wrong state: a task session with no branch | 01 |
| D-14 | drift | Three skills say `/finish-research` deletes the research directory, but no step does. `jans-ctl delete` only unregisters and sends SIGTERM. Only the GUI dialog runs `rmtree` | `finish-research:601-606`, `link-feature:363-365`, `resume-status:173-174`, `resume-status:201`, `quickref:40,43`, `gui.py:1165`, `gui.py:1690-1705` | Closed research directories stay on disk. `/resume-status` Step 2d is reached only after a manual delete. `/link-feature` Phase 1 lists closed research as live | 04 F1 |
| D-15 | defect | `link-feature` Phase 1 scans `~/reviews/` and reads `state.json` for it, but Phase 5 has no row for reviews. Phase 5 then adds `feature:` and `related_sessions:` to an existing review `session.md`, while reviews must stay unlinked. Corrected: the fallback to `task` runs only without a `session.md`, so the review type is not overwritten | `link-feature:43`, `link-feature:55-59`, `link-feature:367-390`, `review-pr:743-746`, `gui.py:258-264` | A selected review session gets a feature link and receives the manifest only if it later gets a `task_plan.md`; the review contract is broken in the data. Plausible, not reproduced | 04 F8 |
| D-16 | defect | Session names are not unique. `load` checks (`gui.py:1730`), but `_create_session`, `_create_task_session`, the GUI Load button `_load_dir`, `_load_linked_session` and `_register_review_session` do not. The name is the key for `rename`, `delete`, `color`, the state merge and the manifests. The live `state.json` (43 entries) has no duplicates today. Corrected: the partial said `load` does not check | `gui.py:1602-1633`, `gui.py:1478-1483`, `gui.py:1579-1592`, `gui.py:769-783`, `gui.py:1568-1577`, `gui.py:1097-1136` | A duplicate makes delete or rename hit several sessions and breaks the merge | 01 |
| D-17 | drift | `ORCHESTRATOR.md` and `JANS.md` list `new-task <name>` with one argument and lack `new-tool`, `new-feature`, `feature-status`, `new-review` and `color`. `CLAUDE.md`, the live prompt, omits `new-review` and `state`. `README.md` omits `state` and the optional `[ticket]` of `new-research` | `ORCHESTRATOR.md:12`, `JANS.md:84`, `ctl.py:22-40`, `CLAUDE.md:25-36`, `README.md:115,129` | An agent that reads the older files calls `new-task` wrongly. The orchestrator cannot discover `new-review` from its prompt | 01 |
| D-18 | drift | The channel rule is broken. The same fix exists on `main` (`e5f9f49`) and on `dev` (`05e08ff`) under two hashes, and `main` was not merged back into `dev`. At `e5f9f49`, `git log dev..e5f9f49` lists `ca9c0ae`, `94afd5e`, `e5f9f49`; `git log main..dev` lists `05e08ff`; the merge base is `cd9d41b`. The rule text differs by branch. Corrected: the analysis commits now add four more commits to `dev..main`, and the rule spans lines 60-69 | `CLAUDE.md:60-69` on `main` and `~/research/jans-impl/CLAUDE.md:60-69` on `dev`; `gui.py:1795-1798` (`_raise_window`, the duplicated fix) | History divergence of the kind that `95c09f3` had to repair. The orchestrator prompt differs by branch | 01 |
| D-19 | defect | The normal flow has no `git push` before `gh pr create`. No step in `pre-code`, `implement`, `quality`, `pre-pr` normal mode or `pr-describe` pushes. The only push is in iteration mode | `pre-pr:442-477`, `pr-describe:178-184`, `pre-pr:719` | `gh pr create` needs a pushed branch; the first PR creation fails or prompts, depending on the shell | 03 |
| D-20 | drift | The guide says only Metis and `/implement` spawn real sub-agents and cites a "cannot switch models" note in `pre-pr` Fase 3. `pre-pr` has no such note (the text is in `review-pr:243`), and it spawns two Opus sub-agents. Corrected citation: the claims are in the guide; `quickref:58` names only Metis | `guide:200-211`, `guide:402-403`, `quickref:58`, `quickref:63`, `pre-pr:228-230`, `review-pr:243` | The cost model is wrong: each `/pre-pr` pays two Opus runs over the whole diff, whatever the session model | 03 |
| D-21 | drift | The flow order differs between `workflow`, `quickref`, the guide and the Jans scaffold. `quickref` omits `/pr-review` and `/pr-deep-review`. Three sources show `/pr-describe` as a separate step, but `/pre-pr` calls it | `workflow:279-283`, `quickref:5-16`, `guide:248-262`, `guide:420`, `gui.py:284-290`, `pre-pr:475` | A reader who follows `quickref` runs `/pr-describe` twice and never meets two skills (table in 5.5) | 03 |
| D-22 | drift | The guide says the hooks are "no-ops without `task_plan.md`" and that such sessions are "completely unaffected". The executing marker is written and removed before the plan check, for every session. `notepad-write-guard.sh` and `auto-commit-config.sh` never check for the plan | `guide:67-69`, `guide:394`, `inject-plan.sh:13-36`, `notepad-write-guard.sh:6-18`, `auto-commit-config.sh:10` | Review and tool sessions are touched by three hooks. A migration that copies only the plan-gated behavior loses the Jans state signal | 01, 02 |
| D-23 | drift | The guide says `.session-model` is stamped on first run "so it always exists". It exists only after `task_plan.md` exists. The value is the `model` alias in `settings.json` (`sonnet`), not the running model. `effort` is `unknown` when `CLAUDE_EFFORT` is unset | `guide:175`, `inject-plan.sh:34-46`, `settings.json:131`, `implement:90` | `/implement` can pick a model that does not match the session (for example after `/model`). The default is invisible to the user | 02 |
| D-24 | drift | `kb-domains.sh`, `/finish-pr` and `workflow` say `prs/pr-<n>-invariants.md` is a convenience copy "consumed by nobody". `/finish-pr` Paso 1 path B reads it as the "already processed" flag and as a source to rebuild from. 29 such files exist for `dd-trace-java` | `kb-domains.sh:44-47`, `finish-pr:85-88`, `finish-pr:290`, `finish-pr:726-727`, `workflow:147` | Whoever deletes the "unused" files makes `/finish-pr` repeat a finished close | 02, 03 |
| D-25 | drift | The guide says `auto-commit-config.sh` "auto-commits every change under `~/.claude`". It stages seven fixed paths and runs only after Edit or Write. Log lines appended through Bash (`echo >> ...-metrics.log`) wait for the next Edit or Write in any session | `guide:54`, `auto-commit-config.sh:13-21`, `settings.json:144`, `quality:404` | Rollback may miss recent KB lines. Paths outside the list (for example `commands/`) are never staged | 02 |
| D-26 | defect | `/pre-pr --iteration` without an argument is documented as "last CHANGES_REQUESTED", but the query takes the last review of any state. Corrected citation: the `quickref` text is at line 27 | `pre-pr:597`, `pre-pr:606-609`, `quickref:27` | The anchor can be an approval or a comment; the iteration can miss earlier requested changes | 03 |
| D-27 | drift | `pre-code` Paso 4.9 needs "the draft implementation checklist (section 5)" as Metis input, but no earlier step produces a draft. Paso 4 is synthesis only and the `verify:` rule comes after the checkpoint | `pre-code:714`, `pre-code:642-704`, `pre-code:833`, `pre-code:837-839`, `pre-code:732` (`FAKE_CRITERION`) | Static reading: the model may build a draft ad hoc; if not, the `FAKE_CRITERION` check has nothing to review | 03 |
| D-28 | drift | The `--iteration` header omits the SHA form. Iteration mode skips tests, muzzle, the plan lock and Fase 8c, and Fase I-8 runs `git commit` and `git push` with no local confirmation text | `pre-pr:35-38`, `pre-pr:598`, `pre-pr:592-742`, `pre-pr:10-13`, `pre-pr:719` | The general rule at `pre-pr:10-13` may cover the push. The risk is that review fixes reach the remote without the checks of the first round | 03 |
| D-29 | drift | `/pr-describe` is specific to dd-trace-java and one author, but `/pre-pr` calls it for every repo. `quickref` records the libddwaf-java failure | `pr-describe:3`, `pr-describe:118-145`, `pre-pr:475`, `quickref:28` | Wrong PR body on other repos | 03 |
| D-30 | defect | `codex-review` has no branch for a Codex MCP that is not connected: any empty result is called a timeout. `/quality` Pass X is always on, so every `/quality` run can reach this path | `codex-review:47-51`, `codex-review:139`, `quality:170-172` | With the MCP down, the written path labels it a timeout and suggests a retry. Context: the `codex` MCP server failed with `CONNECTION_CLOSED` in the analysis sessions | 03 |
| D-31 | defect | `/quality` usually runs before the PR exists, so its metrics line has `pr: none`. `/finish-pr` greps `\| pr: {number} \|`, which such a line cannot match. 23 of 28 lines carry `pr: none`: `dd-trace-java` 20 of 23, `agentic-onboarding-evals` 2 of 3, `system-tests` 1 of 1, `dd-source` 0 of 1 | `quality:370-372`, `quality:385`, `finish-pr:465-467`, `kb:dd-trace-java/quality-metrics.log:1-3,5-10,12-18,20-23`, `kb:agentic-onboarding-evals/quality-metrics.log:1,3`, `kb:system-tests/quality-metrics.log:1` | Predicted, the join was not run: a PR whose quality run was logged before PR creation has no quality part in the catch rate (`finish-pr:474-484`), which biases the trend signal (`finish-pr:486-488`) | 03 |
| D-32 | defect | `gh api` calls in `/finish-pr` have no `--paginate` and return the first page only | `finish-pr:104-105`, `finish-pr:380-389` | On PRs with more than 30 review comments the invariants list and the review metrics undercount | 03 |
| D-33 | defect | `.strike_count_*` is not in `~/.gitignore_global`, while `.session-model` and `.plan-lock*` are. `git check-ignore` printed nothing for `.strike_count_TODO-1` | `~/.gitignore_global:1-15`, `implement:374` | A `git add -A` in a worktree can commit a strike file into a PR | 02 |
| D-34 | drift | The `session.md` scaffold differs by creation route, although `start-research` says the copies must be identical. Research: `link-feature` omits `investigation:`, which `gui.py` and `start-research` write. Task: `start-research` writes `feature: "<TICKET-ID>"`, `gui.py` writes `feature: ""` without a ticket, and `link-feature` writes neither `related_projects` nor `contribution_targets`. Research without a ticket gets `"standalone"`, task gets `""`; the hook treats both as "no feature" | `start-research:82-87`, `start-research:89-110`, `link-feature:398-408`, `link-feature:432-440`, `gui.py:204-205`, `gui.py:228-234`, `inject-plan.sh:51-56`, `finish-research:326` | `/finish-research` and other readers see different keys depending on who made the session. Copy-by-hand cannot hold | 01, 04 F4, F5 |
| D-35 | defect | `rename`, `delete` and `color` return ok for a name that does not exist. `rename` and `color` do not validate the new value. A rename does not update manifest `sessions:` lists or `session.md` | `gui.py:1690-1724` | The orchestrator reports success on a typo. Features keep the old name and show `not_loaded` | 01 |
| D-36 | defect | `link_session` treats a session as linked if the text `- <name>` appears anywhere in the file, so `foo` is "already linked" when `foo-bar` is. Without a `sessions:` line the regex changes nothing and it still returns True | `features.py:111-122` | Missing links in the Features tab and in hook injection | 01 |
| D-37 | defect | Inline comments in manifest lists break both parsers. The Jans parser keeps a trailing comment in each list item. The hook's `related_features` parser strips only the leading `- ` and quotes, so `- APPSEC-61842   # note` gives an id with the comment, the file is not found and nothing is injected, with no error. The guide's own manifest example uses such comments. Current manifests have none | `features.py:35-36`, `inject-plan.sh:74-76`, `guide:359` | A manifest written as documented shows every session as `not_loaded` and loses its related context. The Jans parser also drops `related_features` and `sub_features` | 01, 02 |
| D-38 | defect | The feature id parse `grep "^feature:" \| head -1 \| cut -d' ' -f2`: `cut` without `-s` prints the whole line when it has no space, so `feature:APPSEC-1` gives the id `feature:APPSEC-1` (tested). The first match can also come from the body, not the frontmatter | `inject-plan.sh:51` | The manifest is skipped silently | 02 |
| D-39 | defect | The launcher builds shell and AppleScript text from names and paths that contain quotes, with no escaping. `load` and the GUI "Load" accept any path | `gui.py:338-364`, `ctl.py:92-98` | A path or name with `'` or `"` breaks the command or runs unintended text in the iTerm2 tab | 01 |
| D-40 | defect | `/finish-pr` range queries run with no `git fetch`: `origin/{DEFAULT_BRANCH}..HEAD` at lines 101 and 417 and `...HEAD` at line 500. After a merge-commit merge and a fetch the ranges are empty. Corrected: one range uses three dots; the effect is the same | `finish-pr:101`, `finish-pr:417`, `finish-pr:500` | Commit analysis, `fix_commits` and the AGENTS.md check return nothing for that merge style | 03 |
| D-41 | defect | If `jq` is missing, `TOOL_NAME` is empty and the allowlist cannot match. Under a 3-strike block even `git stash` and `rm` of the strike file are denied (reading, not tested) | `inject-plan.sh:133-135`, `inject-plan.sh:185` | The remediation deadlock that the allowlist exists to prevent comes back | 02 |
| D-42 | defect | `pretool` takes the first `- [ ]` line of the whole file as the "pending TODO". Acceptance checklists or notes with unchecked boxes are reported as TODOs | `inject-plan.sh:209-212` | The model gets a wrong "current TODO" fact on each call | 02 |
| D-43 | drift | `DEFAULT_BRANCH` falls back to `master` in many places. `update-agents-md` notes that `origin/HEAD` may be unset in Jans worktrees | `update-agents-md:44`, `pre-code:61`, `pre-code:171`, `pre-pr:71`, `quality:58`, `pr-describe:42`, `codex-review:85`, `pr-deep-review:65`, `pr-review:66` | With `origin/HEAD` unset, a repo whose default is `main` (this one) diffs against a missing `origin/master` | 03 |
| D-44 | drift | README says the GUI saves state "every 3 seconds" and reads a command "on the next tick (3 s)". The command also waits for the whole refresh, and the CLI timeout is 5 s | `README.md:125,168`, `gui.py:1138-1148`, `commands.py:8` | Slow ticks make `jans-ctl` time out while the command still runs later | 01 |
| D-45 | drift | The language policy says skills and KB documents are English. `kb:README.md` is Spanish. `CONVENTIONS.md` lists 9 skills still in Spanish, 8 of them in scope: `pre-code`, `pre-pr`, `finish-pr`, `pr-describe`, `pr-review`, `codex-review`, `pr-deep-review`, `update-agents-md`. The guide says all skills and the KB are English. Corrected citation: `conv:123-131` | `guide:410`, `~/.claude/CLAUDE.md:7-8`, `kb:README.md:1-12`, `conv:63`, `conv:123-131` | A tool that parses headings or keywords in English fails on the Spanish skills; translation blocks publication and migration | 02, 03 |
| D-46 | defect | `pre-pr` Fase 6b writes a `pr:` field before the PR exists (Fase 8) and uses a different line format from Fase 10 in the same log. Corrected: some 6b lines carry real PR numbers (`pr: 12300`, `pr: 12546`), others carry placeholders such as `pr: TBD` or `pr: APPSEC-69734 (branch, no PR yet)` | `pre-pr:328`, `pre-pr:465-477`, `pre-pr:575`, `kb:dd-trace-java/pre-pr-metrics.log:21,26,34,37`, `kb:agentic-onboarding-evals/pre-pr-metrics.log:3` | Two schemas in `pre-pr-metrics.log`; lines with placeholders cannot be joined to a PR | 03 |
| D-47 | defect | `create_feature` silently ignores a second call for the same ticket, so `jans-ctl new-feature T nick desc` on an existing ticket returns ok and keeps the old values. `load_features` swallows all parse errors | `features.py:84`, `features.py:70-71` | The user believes the manifest changed. A broken manifest disappears from the GUI with no log line | 01 |

### 7.3 Low impact

| ID | Type | Item | Evidence (file:line) | Impact | Src |
|----|------|------|----------------------|--------|-----|
| D-48 | drift | Guides say to run `/update-agents-md` before the merge, but `finish-pr` suggests it after the merge, when the change cannot ship with the PR. The skill never commits | `quickref:51`, `finish-pr:505-510`, `update-agents-md:171-228` | Suggestion at the wrong time | 03 |
| D-49 | drift | `implement:427` says `/pre-pr` runs "the full test suite". It runs affected Gradle modules only, and nothing without Gradle | `implement:427`, `pre-pr:334-363`, `pre-pr:382-385` | No step runs the full suite; users may believe it is covered | 03 |
| D-50 | drift | `pr-deep-review` refers to "the smola/manuel checklist" but never loads one, nor any KB file | `pr-deep-review:12`, `pr-deep-review:144` | Verdicts rely on model memory and differ from `/pre-pr` | 03 |
| D-51 | drift | `review-pr` mixes repo-specific rules into a generic skill: the dd-trace-java `docs/` table, the §17 advisory rule, `APPSEC-\d+` patterns | `review-pr:181`, `review-pr:211-227`, `review-pr:357-361` | Other repos run the same text; a new repo needs skill edits | 04 F18 |
| D-52 | drift | `resume-status` Step 2c reads Spanish headings ("Contexto rápido para retomar en frío", "Decisiones de diseño no obvias") from the PR cache. `/finish-pr` Paso 5 writes `## Conocimiento consolidado` instead. No skill or hook writes "Contexto rápido". Corrected: Paso 5 is `finish-pr:297-334`, and "Decisiones de diseño no obvias" appears only at `finish-pr:348` as a check on the PR description | `resume-status:161-162`, `finish-pr:297-334`, `finish-pr:348`, `kb:dd-trace-java/prs/pr-11179.md:25,55,62` | Recovery depends on headings with no known writer. An English KB entry would not match | 04 F9 |
| D-53 | drift | The `## Active sessions` table has three layouts. The `link-feature` template has a `Status` column (used by `APPSEC-70088`); 3 older manifests use `Branch` and `Notes`; `APPSEC-61874` uses `PR \| What \| KB path \| Status`. `finish-research` carries a workaround for two layouts, and its remark "none of the 6 has a `Status` column" is out of date. Corrected: the partial said two layouts | `link-feature:291-294`, `finish-research:598-602`, `kb:_meta/features/APPSEC-70088.md`, `kb:_meta/features/APPSEC-61874.md` | Several writers, several schemas; every consumer needs a branch per layout | 04 F14 |
| D-54 | drift | `link-feature` Phase 1 scans `~/repos/`, which holds origin clones, not sessions. Phase 5 lists `~/IdeaProjects/` as a location, but Phase 1 never scans it. Corrected citation: lines 390 and 432 | `link-feature:39-44`, `link-feature:390`, `link-feature:432` | Noise in the candidate list; sessions under `~/IdeaProjects/` are never found | 04 F13 |
| D-55 | drift | `/quality` is "sequential, independent passes" in the skill but "in parallel" in `workflow`, `quickref` and the guide. It has no sub-agents, so the independence is by prompt only | `quality:3`, `quality:86`, `quickref:25`, `workflow:88` | Readers expect a cost and an isolation that do not exist | 03 |
| D-56 | drift | The Codex parameters (`gpt-5.6-sol`, `xhigh`, sandbox and approval policy) are hand copies in three skills | `codex-review:40-41`, `quality:156-163`, `review-pr:447-454` | A model or CLI upgrade needs three edits | 03, 04 F17 |
| D-57 | drift | The same context guard is copied into five skills and "Santi's filter" into three | `quality:37-40`, `pr-review:46-49`, `codex-review:62-65`, `pr-deep-review:47-50`, `pre-pr:49-52`, `pre-code:664-666`, `finish-pr:163-167`, `update-agents-md:100-104` | Edits must be repeated; divergence is likely | 03 |
| D-58 | drift | The guide says "currently 19 skills". There are 23 skill directories. `CONVENTIONS.md` says 22, and its table has 23 rows | `guide:92`, `ls ~/.claude/skills`, `conv:147`, `conv:121-145` | Three counts disagree | 02 |
| D-59 | drift | The guide and `_meta/README.md` say `_meta/research/` is empty. It holds `IH Role Stabilization.md` (closed 2026-08-24, with an empty `reprocessed:` key). The name has spaces; `resume-status` quotes the grep (line 186) but assigns `SESSION_NAME=<basename ...>` without quotes (line 183). Corrected: the partial said the grep breaks | `guide:186-187`, `kb:_meta/README.md:50-52`, `kb:_meta/research/IH Role Stabilization.md:1-12`, `resume-status:183`, `resume-status:186` | The guide is stale. A literal copy of line 183 breaks on the space | 02, 04 F15 |
| D-60 | drift | `_meta/README.md` lists 5 manifests and 6 active worktrees. Disk has 9 manifests, and only `system-tests-APPSEC-61873-vertx` of the 6 worktrees exists | `kb:_meta/README.md:25-32`, `kb:_meta/README.md:53-58` | The "active worktrees" table is stale | 02 |
| D-61 | drift | The guide says `kb-domains.sh` covers "the KB domain layers and the research cache". It has five subcommands: `list`, `match`, `research`, `review`, `prs`. `_meta/README.md` lists four (no `prs`) | `guide:64`, `kb-domains.sh:10-14`, `kb-domains.sh:256-441`, `kb:_meta/README.md:99` | Two documents describe a smaller tool | 02 |
| D-62 | drift | The `inject-plan.sh` header lists what it injects without `decisions.md` and the executing marker, and says it exits silently without `task_plan.md` | `inject-plan.sh:2-4`, `inject-plan.sh:13-36`, `inject-plan.sh:105-109` | Misleads whoever reads only the header | 02 |
| D-63 | drift | The state threshold is 15 s in the docs and 5 s in the code | `README.md:63-65`, `JANS.md:59-60`, `state_detector.py:12` | Misleads tuning and bug reports | 01 |
| D-64 | drift | The `kind` comment lists `research \| task \| tool \| review`; the code stores `tasks`, `tools`, `reviews`. 11 of 43 live entries have no `kind` | `models.py:33`, `gui.py:1481,1572,1624` | Another tool that reads `state.json` must accept the plural forms and a missing key | 01 |
| D-65 | drift | README calls `log.py` a "rotating file logger". It is a plain `FileHandler` | `README.md:199`, `log.py:23` | Unbounded growth (P-19) | 01 |
| D-66 | drift | The review session name is `<repo>-PR-<n>` in code; README says `<repo>-pr-<n>`. Corrected citation: README lines 39, 108, 132 and 211 | `gui.py:1545`, `README.md:39,108,132,211` | Case matters in `sessions:` lists and on Linux file systems | 01 |
| D-67 | drift | `pre-pr:726` points to "Fase 9 of normal mode" for `SESSION_MODEL`. The code is in Fase 10; Fase 9 is `arpcli` | `pre-pr:726`, `pre-pr:547`, `pre-pr:563-572` | Stale reference after renumbering | 03 |
| D-68 | drift | The `codex-review` prompt says "compared to master/main", while the scope uses the resolved default branch | `codex-review:107`, `codex-review:85` | Wrong base named in the prompt for other default branches | 03 |
| D-69 | drift | `workflow` says checklist "sections 1-17"; the KB file has section 18 and later | `workflow:101`, `kb:dd-trace-java/pr-review.md:430` | Stale count | 03 |
| D-70 | drift | The review-round commit message is `fix: review comments round N` in `workflow` and `address review comments` in the skill | `workflow:132`, `pre-pr:718` | Inconsistent history | 03 |
| D-71 | drift | Marker words do not match headings: `pr-review` emits `Step N` over `Paso` headings, `review-pr` emits `Step N` over `Phase` headings | `pr-review:25`, `pr-review:33`, `pr-review:87`, `review-pr:19-24`, `review-pr:36`, `conv:15` | Breaks the convention; marker numbers do not match what the user sees | 03, 04 F16 |
| D-72 | defect | The `review-pr` rule says the last step writes `[review-pr] done`, but 7e writes a metrics line and no `done` marker. `progress.md` may also be gone after 7d | `review-pr:32`, `review-pr:816-829`, `gui.py:304-310` | Jans shows the metrics line dimmed instead of a green `done`; a finished review looks unfinished | 04 F3 |
| D-73 | defect | `gui.py` paints a progress line green when it contains the substring `done` and no arrow. A step title with that word shows as finished | `gui.py:304-310`, `review-pr:19` | A wrong green subtitle | 04 F20 |
| D-74 | defect | `review-pr` 7b copies files with `cp ... 2>/dev/null`, which hides failures. The skill records that 0 of 4 deep reviews left a `findings.md` because of this; a check and a guard now exist. Corrected: the partial also said `date -r FILE` is BSD-only, but GNU `date` supports `-r` too | `review-pr:289-292`, `review-pr:640`, `review-pr:645-647`, `review-pr:664-671` | Mitigated | 04 F19 |
| D-75 | defect | `update-agents-md` uses `{REPO_NAME}`, but Paso 0 defines only `{REPO_SLUG}` | `update-agents-md:43`, `update-agents-md:64` | The PR cache path uses an undefined placeholder (the path is usually absent anyway, O-13) | 03 |
| D-76 | defect | A stray `kb:pre-pr-metrics.log` sits at the KB root with an empty `repo:` field. The skill appended to `{KB_PATH}` when the path did not resolve | `kb:pre-pr-metrics.log:1`, `pre-pr:582` | One PR's metrics are not in the repo log | 02 |
| D-77 | defect | A non-numeric strike file prints `[: integer expected` on each call and is not counted | `inject-plan.sh:148` (tested) | Noise in the hook log; a typo hides a real block | 02 |
| D-78 | defect | A manual run of `inject-plan.sh` in a real session directory writes `.session-model`. The partial-02 analysis created 13 such files by accident and removed them | `inject-plan.sh:42-46` | A "dry run" is not read-only. Use a copy and a temporary `HOME` (section 8.1) | 02 |
| D-79 | defect | `~/.claude/executing/` holds 47 markers; 38 point to deleted directories. `Stop` removes only the current cwd's marker at the end of each turn. A marker leaks when the process dies before `Stop` runs. Corrected: the partial said `Stop` runs only on a clean session end | `inject-plan.sh:16-32`, `state_detector.py:13-15,30` | Unbounded growth. Jans ignores markers older than 15 minutes, so the state is correct | 02 |
| D-80 | defect | `_pid_tty` compares with `"??"` twice; the second test was meant for another value | `gui.py:430` | Cosmetic | 01 |

## 8. Performance and cost

### 8.1 Per-turn injection cost

**Method** (partial 02, 2026-10-02). The hook was not run against the real session directories or the real `~/.claude`.

1. A script copied `task_plan.md`, `progress.md`, `decisions.md`, `task_coding_rules.md` and `session.md` of each of the 36 sessions under `~/tasks`, `~/research` and `~/tools` that has a `task_plan.md`, each into a temporary directory.
2. It ran `inject-plan.sh userprompt` there with `HOME` set to a temporary directory that holds a copy of `settings.json` and a read-only symlink to the real `features/` directory.
3. It counted stdout bytes per section (split on the `=== ... ===` headers) with `wc -c`.
4. Tokens are bytes divided by 4 (lower bound) to bytes divided by 3 (upper bound for markdown with paths and code). No tokenizer was available offline, so these are estimates.
5. Latency: 10 runs of each mode in the directory with the largest decisions file, divided by 10, including `bash` start-up.

The core of the script, so the numbers can be reproduced:

```bash
T=$(mktemp -d); mkdir -p $T/.claude/knowledge/_meta
ln -s ~/.claude/knowledge/_meta/features $T/.claude/knowledge/_meta/features
cp ~/.claude/settings.json $T/.claude/settings.json
for d in ~/tasks/*/ ~/research/*/ ~/tools/*/; do
  [ -f "$d/task_plan.md" ] || continue
  W=$(mktemp -d)
  for f in task_plan.md progress.md decisions.md task_coding_rules.md session.md; do
    [ -f "$d/$f" ] && cp "$d/$f" "$W/$f"
  done
  out=$(cd "$W" && HOME=$T bash ~/.claude/hooks/inject-plan.sh userprompt 2>/dev/null)
  printf '%s\t%s\n' "$(basename "$d")" "$(printf '%s\n' "$out" | wc -c)"
  rm -rf "$W"
done
```

Do not run the hook in a real session directory: the `.session-model` stamp writes a file there (D-78).

**`userprompt`, bytes per prompt (n = 36 sessions).**

| Statistic | Bytes | Tokens (bytes/4 to bytes/3) |
|-----------|-------|------------------------------|
| min | 337 | 84-112 |
| median | 1,417 | 354-472 |
| mean | 5,651 | 1,413-1,884 |
| p90 | 17,582 | 4,396-5,861 |
| max | 28,018 | 7,005-9,339 |

**By session archetype.** Section sizes include their header line.

| Archetype | Example | Total bytes | Plan | Progress | Decisions | Rules | Feature |
|-----------|---------|-------------|------|----------|-----------|-------|---------|
| Fresh Jans scaffold, standalone | `ander-hdiv` | 337 | 290 | 47 | 0 | 0 | 0 |
| Research with progress markers | `refactor-appsec` | 2,721 | 294 | 2,427 | 0 | 0 | 0 |
| Task after `/pre-code` | `dd-trace-java-APPSEC-69139` | 4,097 | 385 | 1,207 | 0 | 2,505 | 0 |
| Task with feature manifest | `dd-trace-java-APPSEC-69734` | 9,158 | 2,989 | 1,532 | 0 | 2,914 | 1,723 |
| Research on a big feature | `ebpf-context-propagation` | 18,056 | 303 | 1,099 | 0 | 0 | 16,654 |
| Task with long decisions log | `dd-trace-java-appsec-test-1` | 28,018 | 5,589 | 2,883 | 16,634 | 2,912 | 0 |

Of the 36 sessions, 27 have only `progress.md` besides the plan, 6 have rules, decisions and progress, 2 have rules and progress, and 1 has none. The largest single items are one manifest (`APPSEC-70088.md`, 16,616 bytes, about 4,000-5,500 tokens) and one `decisions.md` tail (16.6 KB).

**Other modes.**

| Mode | Bytes to the model | Approx. tokens | Latency (mean of 10) |
|------|--------------------|----------------|---------------------|
| `userprompt` | Table above | Table above | 54 ms |
| `pretool` | 0 with no unchecked box; 144 compact (164 pretty) with one. The text is `Current pending TODO: ` plus the TODO line (39-56 characters in the real plans) | 10-25 | 71 ms |
| `posttool` | 154 pretty, 56-character text | About 14 for the text | 40 ms |
| `precompact` | 0 (debug log, 75 bytes) | 0 | 34 ms |
| `stop` | 0 | 0 | 29 ms |

Only 3 of the 9 real task plans had an unchecked `- [ ]` line. The Jans scaffold writes a numbered phase list, not checkboxes (`gui.py:267-290`), so sessions that never ran `/pre-code` get no `pretool` reminder.

**Per tool call.** An `Edit`, `Write` or `Bash` call costs about 110 ms of hooks (`pretool` 71 + `posttool` 40), plus `auto-commit-config.sh` for Edit and Write (a `git status` over the tracked paths takes about 25 ms; the commit is extra). The context added per call is about 25-40 tokens (estimate).

**Cumulative effect (inferred, not measured on a transcript).** The `userprompt` stdout becomes context for that prompt. If it stays in history until compaction, a heavy session (17-28 KB, about 4,000-9,000 tokens) adds that amount on every prompt even when no file changed. After 30 prompts that is about 120,000-270,000 tokens of repeated text. A median session adds about 12,000 tokens in the same span.

### 8.2 Expensive skills

| Skill | Size (lines, bytes) | Sub-agents and external models | Cost drivers |
|-------|---------------------|-------------------------------|--------------|
| `pre-code` | 1358, 66,686 | Up to 6 Explore agents (Paso 2 plus A to E), 1 Opus Metis agent | 10-20 minutes and 4-6 agents by its own estimate (`pre-code:1353`), `ultrathink`, the largest skill text |
| `pre-pr` | 742, 30,773 | 2 Opus agents per normal run | Two full-diff Opus reviews; iteration mode runs four passes in the session |
| `review-pr` | 834, 37,998 | Codex MCP at `xhigh` in deep mode | Deep mode at 2-3x tokens; about 10k tokens of instructions per call |
| `finish-research` | 715, 43,350 | None | The second largest text by bytes, after `pre-code`; `ultrathink` in Phase 3 |
| `finish-pr` | 737, 31,349 | None | Many `gh api` calls, three confirmations |
| `quality` | 431, 20,028 | Codex MCP at `xhigh`, always | Three passes in one context plus one Codex call per run |
| `implement` | 427, 15,971 | 1 agent per TODO, model from `.session-model` | The full invariants and rules are re-sent per TODO |
| `start-research` | 398, 17,072 | None | Optional fallback that loads 80-100k tokens of KB |

All 15 skill files total about 349 KB. A skill file is loaded in full on each call, so text in branches that do not run is paid for every time.

### 8.3 Sub-agent and model use

| Where | Mechanism | Model | Enforced? |
|-------|-----------|-------|-----------|
| `/pre-code` Paso 2 and 3 | `Agent(Explore, ...)`, up to 6 | Inherited from the session | Yes |
| `/pre-code` Paso 4.9 | `Agent(general-purpose, model: opus)` | Opus | Yes |
| `/implement` Step 5 | `Agent(model, prompt)`, no `subagent_type` | From `.session-model` or the second argument; `default` -> sonnet, `opusplan` -> opus | Yes |
| `/pre-pr` Fase 3 and 4 | Two `Agent(general-purpose, model: opus)` in one message | Opus | Yes, but the guide does not count it (D-20) |
| `/quality` Pass X, `/codex-review`, `/review-pr` 4b | Codex MCP | `gpt-5.6-sol`, `xhigh` | Yes (external) |
| `/resume-status` | `model:` frontmatter | `claude-haiku-4-5-20251001` | Yes |
| Everything else | Session model (`settings.json` `model: sonnet`) | Sonnet unless the user changes it | Recommendations in `quickref:56-66` only |

### 8.4 Jans runtime cost

The GUI runs all work on the Tk main thread every 3 s: state detection, `osascript`, `ps`, IPC and a full widget rebuild (P-16 to P-18). `jans.log` is 117 MB (P-19).

### 8.5 Performance findings

| ID | Item | Evidence (file:line) | Impact | Src |
|----|------|----------------------|--------|-----|
| P-01 | The injection has no byte cap. The manifest (up to 16,616 bytes) and the decisions tail (up to 16.6 KB for 80 lines) are sent whole on every prompt; totals reach 28 KB | `inject-plan.sh:108,115,121-122` | About 4,000-9,300 tokens per prompt in the heaviest sessions, mostly repeated text | 02 |
| P-02 | Unchanged content is injected again on every prompt. Two sessions of one feature each pay for the same manifest | `inject-plan.sh:89-124` | History grows by the full injection per prompt until compaction (inferred, 8.1) | 02 |
| P-03 | `posttool` fires after every `Edit`, `Write` and `Bash` call while `progress.md` exists, including `ls`. Jans scaffolds `progress.md` in every non-review session | `inject-plan.sh:226-229`, `gui.py:225,237,251`, `settings.json:135` | About 14 tokens and 40 ms per call with little value; about 2,800 tokens in a 200-call run | 02 |
| P-04 | `pretool` runs `jq` up to 4 times, `grep` once and `sed` twice per call. Corrected: the partial said 3 `jq` and 1 `sed` | `inject-plan.sh:133-135`, `inject-plan.sh:209-215` | 71 ms per call, about 110 ms with `posttool`. Low but additive | 02 |
| P-05 | Fresh Jans sessions inject the numbered phase list on every prompt, though the text says "informational only" | `gui.py:267-290` | About 300 bytes (75-100 tokens) per prompt for no information | 02 |
| P-06 | `/quality` always runs Codex at `xhigh` effort, with no light mode. A lost connection can hang | `quality:154`, `quality:156-163`, `codex-review:45` | Slow runs on small diffs; it stacks with `/pre-pr` Fase 8b and `/codex-review` | 03 |
| P-07 | Two full-diff Opus sub-agents in every `/pre-pr`; iteration repeats four passes | `pre-pr:230`, `pre-pr:671-695` | High token cost per round | 03 |
| P-08 | `/implement` re-sends the full invariants and rules to a new agent for each TODO | `implement:219-225` | Cost grows with the TODO count and the invariants size; no caching | 03 |
| P-09 | `/pre-code` runs up to 6 Explore agents (one in Paso 2, five in Paso 3) plus an Opus review and `ultrathink`, with no cap for large KBs. Corrected: the partial said up to 5 | `pre-code:439`, `pre-code:450`, `pre-code:473-560`, `pre-code:644`, `pre-code:718`, `pre-code:1353` | 10 to 20 minutes and a high cost per task; only KB hits reduce it | 03 |
| P-10 | `/pr-deep-review` forces one turn per file and keeps the full diff in the main context | `pr-deep-review:146-154`, `pr-deep-review:187-191` | N turns for N files; the context grows | 03 |
| P-11 | `/finish-pr` makes many `gh api` calls and three confirmations | `finish-pr:96-111`, `finish-pr:372-392`, `finish-pr:181-212` | A long closing step; much of it is metrics | 03 |
| P-12 | `review-pr` (834 lines, 37,998 bytes) and `finish-research` (715 lines, 43,350 bytes) load in full on each call; most text is in branches that do not run | `review-pr:1-834`, `finish-research:1-715` | About 10k tokens of instructions per call before any work. A split by mode would cut it | 04 F21 |
| P-13 | Deep review costs 2-3x tokens, and Phase 4b adds a sequential Codex `xhigh` call. The unfiltered fallback in `start-research` can load 80-100k tokens | `review-pr:94`, `review-pr:412-414`, `review-pr:447-454`, `start-research:269-276` | High per-run cost; both are opt-in or warned | 04 F22 |
| P-14 | `resume-status` runs `gh pr view` (network) on every call, also in research and tooling sessions with no PR | `resume-status:41` | Slower start and a noisy `NO_PR` | 04 F23 |
| P-15 | `resume-status` is pinned to Haiku but carries a 7-branch routing with ordering rules | `resume-status:3`, `resume-status:49-77` | A wrong recovery path is plausible; not measured | 04 F24 |
| P-16 | Each tick, for every session, the detector scans and parses all `~/.claude/sessions/*.json` twice (`_refresh` and `detect_state`), runs `ps` twice for sessions with an iTerm2 tab, and reads the whole JSONL with `json.loads` per line. The largest transcript is 70 MB. Corrected: the partial said three scans per tick; the third is in click handlers | `gui.py:1013`, `gui.py:1017`, `gui.py:1054`, `state_detector.py:59-79`, `state_detector.py:97`, `state_detector.py:176-189` | CPU and I/O grow with sessions times transcript size, every 3 s, on the UI thread | 01 |
| P-17 | `osascript` runs on the Tk main thread: once per tick (2 s timeout) and once per second in `_focus_poll` with no timeout | `gui.py:399-421`, `gui.py:324-330`, `gui.py:1788-1793` | A hung iTerm2 freezes the window; IPC answers slow down | 01 |
| P-18 | Every tick destroys and rebuilds all widgets of all tabs. `progress.md` is read once per row per render | `gui.py:852-905`, `gui.py:950` | Flicker and wasted work; the scroll position is not kept | 01 |
| P-19 | `jans.log` has no size limit. Each save, which happens every tick, writes one INFO line "saved 43 sessions to state.json": 953,276 of 960,093 lines. Corrected: the partial said DEBUG lines per change | `log.py:19-23`, `persistence.py:52-53` | 117 MB today, growing about 1 line per 3 s | 01 |

### 8.6 Improvement ideas

- Cap each injected section in bytes and point to the file for the rest (P-01).
- Inject a file only when its hash changed since the last prompt, kept in a per-session state file (P-02). Inject the manifest's summary section only, and the rest on demand.
- Restrict the `posttool` reminder to Edit and Write (P-03). Read the stdin JSON once with one `jq` call (P-04).
- Drop the scaffold phase list from `task_plan.md`, or mark it so the hook skips it (P-05).
- Add `/quality --light` without Codex and use it for small diffs (P-06). Let `/pre-pr` reuse `/quality` findings for unchanged files (P-07).
- Split `review-pr`, `finish-research` and `pre-code` into a short core plus per-mode files that the core reads only when the mode runs (P-12, P-09).
- In Jans: read `~/.claude/sessions` once per tick, parse only the JSONL tail, move `osascript` and the detector to a worker thread, update widgets in place, log saves only on change and rotate the log (P-16 to P-19).

## 9. Migration notes

### 9.1 What another tool must provide

| Capability | What the workflow uses it for | What a replacement must provide | Findings |
|-----------|-------------------------------|----------------------------------|----------|
| Per-prompt context injection | The plan, progress, decisions, rules and manifest on every prompt (`UserPromptSubmit` plain stdout) | A hook before each model turn whose output joins the context, with a size limit you control | C-02, C-04 |
| Pre-tool context and blocking | The TODO reminder (`additionalContext`) and the three-strikes gate and write guard (exit 2 plus stderr) | A pre-tool event that gets the tool name and arguments as structured input, can add a context line, and can deny the call with a message to the model | C-01, C-03 |
| Post-tool context | The `progress.md` reminder; marker removal | A post-tool event with a context channel | C-01 |
| Turn-end event | Executing marker cleanup after a denied or blocked call | An event that fires after every turn, also when a tool call was denied | C-05 |
| Pre-compaction event | Nothing today (O-04) | Not needed | O-04 |
| Event and matcher model | Event names, the matcher `Edit\|Write\|Bash`, tool names, env vars `CLAUDE_EFFORT` and `CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR` | A mapping for each, and a stable working directory for hook scripts | C-03 |
| Skills | Markdown instructions loaded on a slash command, with frontmatter (`name`, `description`, `model`) | Named, user-invoked prompt files with arguments; optional per-skill model pin | C-13, C-17 |
| Slash commands | `/pre-code`, `/loop`, `/rewind`, `/btw` and the other skill commands | A command surface, a recurring-task runner (for `/loop`) and a code rewind (for `/rewind`) | C-17 |
| Sub-agents | Explore agents, Opus reviewers, one agent per TODO with a chosen model | A sub-agent API with isolated context, a type or tool set, and a per-call model | C-11, C-12 |
| Model names | `.session-model` aliases (`sonnet`, `opus`, `opusplan`, `default`) | A model registry and a mapping of the stored aliases | C-12 |
| Reasoning depth | The `ultrathink` keyword | A per-call reasoning or effort setting | C-14 |
| MCP | Atlassian (Jira, with a fixed `cloudId`), Datadog, Google Workspace, Codex | MCP client support, or tool adapters for "fetch ticket", "query spans", "read doc", "second-model review" | C-18, C-19 |
| Code navigation | The `LSP` tool with `jdtls-lsp` for Java | An LSP bridge with `findReferences`, `incomingCalls`, `goToImplementation`, `workspaceSymbol` | C-15 |
| Web fetch | `WebFetch` for Confluence pages | A fetch tool with corporate auth | C-18 |
| Project prompt | `CLAUDE.md` auto-load with `@` import of an absolute path (the orchestrator) | A per-directory system prompt with file includes | C-09 |
| Session registry and transcript | `~/.claude/sessions/*.json` (`cwd`, `pid`, `sessionId`), `~/.claude/projects/<key>/<id>.jsonl` and its record schema | A documented way to list live sessions per cwd and to know if a session is busy, idle or waiting for approval | C-06 |
| Launch and resume | `claude` and `claude --continue` typed into iTerm2 | A CLI that starts or resumes a named session in a cwd | C-08 |
| Terminal | iTerm2, AppleScript, `ps`, iTerm2 escape codes | A terminal API for tabs, focus, colour and title, or an embedded terminal | C-22 |

### 9.2 Claude-specific dependencies

| ID | Item | Evidence (file:line) | Impact | Src |
|----|------|----------------------|--------|-----|
| C-01 | Context injection and blocking use the Claude Code hook JSON protocol: `hookSpecificOutput.additionalContext`, exit 2 plus stderr to block, stdin JSON with `tool_name` and `tool_input` | `inject-plan.sh:129-135,208,214,227`, `notepad-write-guard.sh:6-15` | Another tool needs its own channel for per-call context and for blocking | 02 |
| C-02 | `UserPromptSubmit` plain stdout is the injection channel for the whole plan. The script documents that Pre/PostToolUse stdout is ignored but not why this one works | `inject-plan.sh:89-123`, `inject-plan.sh:204-208`, `inject-plan.sh:222-225` | The core mechanism rests on one undocumented platform behavior | 02 |
| C-03 | The scripts rely on event names, the matcher grammar (`Edit\|Write\|Bash`), the tool names `MultiEdit` and `NotebookEdit`, and the env vars `CLAUDE_EFFORT` and `CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR`. Corrected: no script tests the tool name `Agent`; it appears only in the block message (`inject-plan.sh:190`) and in `implement:78-89` | `settings.json:3,135,165,174`, `inject-plan.sh:44,177` | No equivalent to copy; each needs a mapping | 02 |
| C-04 | The workflow is encoded in file presence: the hook injects planning files only when `task_plan.md` exists, so skills create or avoid files to steer the hook (reviews avoid it; research creates it). `.session-model` comes from `settings.json` | `inject-plan.sh:34-46`, `review-pr:48-74`, `start-research:130-134`, `link-feature:410-414`, `finish-research:490-494`, `pre-code:1118`, `pre-code:1259` | A tool without these hooks loses the injection and the review isolation | 03, 04 F28 |
| C-05 | The "needs input" signal needs the hook marker in `~/.claude/executing`. Without the hook, a session shows `needs_input` for any running tool after 5 s | `state_detector.py:11`, `state_detector.py:121-124` | Couples Jans to `inject-plan.sh` | 01 |
| C-06 | Jans state detection and `/finish-pr` depend on internal, undocumented Claude Code files: the `~/.claude/sessions` registry (`cwd`, `pid`), the project directory key rule (`/` and `.` become `-`) and the JSONL record schema. `/finish-pr` also finds the pid there and sends SIGTERM | `state_detector.py:9-10`, `state_detector.py:41-48`, `state_detector.py:51-88`, `persistence.py:12-14`, `finish-pr:599-640` | Any change in Claude Code breaks the states and the cleanup | 01, 03 |
| C-07 | Hard-coded Claude paths: `$HOME/.claude/knowledge/_meta/features`, `~/.claude/executing`, `~/.claude/settings.json`; Jans reads `~/.claude/sessions`, `~/.claude/projects` and the executing directory | `inject-plan.sh:11,16,43`, `state_detector.py:9-11` | The Jans state and the manifest resolve are tied to one install location | 02 |
| C-08 | Launch and resume use `claude` and `claude --continue` only. Resume picks the latest conversation of the cwd, not a chosen session, because Jans session ids are synthetic UUIDs | `gui.py:338`, `app.py:538-541` | Cannot resume a named conversation; another CLI needs another launcher | 01 |
| C-09 | The orchestrator is a Claude session that reads `CLAUDE.md` from `~/research/jans`; the cwd is a constant, and the prompt imports a file by absolute path. `make_app.py` and `jans-menu.sh` also fix `~/research/jans`. Corrected citation: `make_app.py:7-9` | `gui.py:63`, `CLAUDE.md`, `make_app.py:7-9`, `jans-menu.sh:3` | Blocks a move of the checkout and another agent runtime | 01 |
| C-10 | The progress protocol depends on the model running an `echo` from the skill text, and the Jans subtitle depends on the marker text (`[skill] Step N`, `next →`, `done`). The platform enforces neither | `conv:17-33`, `gui.py:295-313` | A skipped step or a format change leaves the subtitle stale or blank | 01, 02 |
| C-11 | `Agent(...)` with `Explore` and `general-purpose` types and a `model:` argument | `pre-code:439`, `pre-code:718`, `implement:256-261`, `pre-pr:230` | Needs a sub-agent API with model selection | 03 |
| C-12 | `.session-model` holds a Claude model alias read from `settings.json`, and `/implement` maps it to an `Agent(model: ...)` call per TODO | `inject-plan.sh:43`, `implement:72-117` | Model routing is tied to Claude model names and the `Agent` tool | 02 |
| C-13 | The `model:` frontmatter pin and the rule that a skill "cannot switch models"; model choice is a session setting | `resume-status:3`, `review-pr:243` | The pin has no portable equivalent | 04 F27 |
| C-14 | The `ultrathink` keyword | `pre-code:644`, `pre-pr:669`, `pr-review:122`, `finish-research:154`, `review-pr` Phases 3b and 4 | No effect in other tools; reasoning depth is lost | 03, 04 F26 |
| C-15 | The `LSP` tool (`findReferences`, `incomingCalls`, `goToImplementation`) with the `jdtls-lsp` plugin | `pre-code:467`, `quality:88`, `review-pr:285`, `review-pr:330`, `review-pr:334` | Java navigation depends on that plugin | 03, 04 F26 |
| C-16 | Skill logic shaped by hook internals: Glob and Read instead of Bash to avoid the `pretool` gate | `implement:46-48`, `implement:123-126` | A different gate needs different skill text | 03 |
| C-17 | Slash commands, `/loop`, `/rewind`, `/btw` | `pre-pr:497-506`, `conv:39-57` | The command surface is Claude Code only | 03 |
| C-18 | MCP servers and fetch: Google Workspace (needs OAuth, unavailable in headless runs), Datadog, Codex with a pinned model and CLI version, and `WebFetch` for Confluence | `pre-code:150-155`, `pre-code:283-297`, `codex-review:32-45`, `review-pr:445-470`, `review-pr:265`, `start-research:321` | Each needs an equivalent | 03, 04 F26 |
| C-19 | The Atlassian MCP tool `mcp__atlassian__getJiraIssue` with a hard-coded `cloudId`, copied into two skills | `review-pr:247-253`, `start-research:309-314` | Blocks migration; needs a "fetch ticket" abstraction | 04 F25 |
| C-20 | A skill's own final command can kill it: `jans-ctl delete` sends SIGTERM to the matching Claude process. The workaround is to print the summary first. Corrected citation: the workaround is at lines 618-621 and 690-693 | `finish-research:618-621`, `finish-research:649-656`, `finish-research:690-693`, `gui.py:1695-1701` | Needs a different closing mechanism in another host | 04 F29 |
| C-21 | Skills depend on Jans: `jans-ctl delete`, direct `state.json` reads and the progress parser | `finish-pr:644-668`, `gui.py:295-313` | Skills cannot run without Jans and keep their status and cleanup features | 03 |
| C-22 | macOS only: iTerm2 and AppleScript to open, focus, list ttys and read the frontmost app; `ps`; escape codes to a tty for colour, badge and title (iTerm2 `OSC 6` and `OSC 1337`); `rumps` for the menu bar | `gui.py:333-453`, `menubar.py` | No Linux or other terminal support | 01 |
| C-23 | BSD `sed -i ''` | `implement:294-296` | Fails on Linux | 03 |

## 10. Improvement backlog

Priority 1 fixes data loss, self-termination and broken gates. Priority 2 fixes wrong results and the largest costs. Priority 3 removes dead parts and drift. Size: S (under an hour), M (a few hours), L (a day or more). The `Changes` column says where the change lands. Changes to `jans/` follow the channel rule (work on `dev`, merge into `main`).

| # | Priority | Item | Findings | Changes | Size |
|---|----------|------|----------|---------|------|
| 1 | 1 | Make the GUI delete unregister only, like `jans-ctl delete`; if a file delete stays, use `git worktree remove` for worktrees and refuse `load`ed directories | D-01 | `jans/gui.py` | S |
| 2 | 1 | Make `state.json` reads fail safe (skip a bad entry, never return `[]` on one error) and writes atomic (temp file plus rename) | D-02 | `jans/core/persistence.py`, `jans/gui.py` | S |
| 3 | 1 | Decide one `delete` contract (SIGTERM or not) and document it; in the skills, write metrics and the `done` marker before `jans-ctl delete`, and make `/finish-pr` refuse to run inside the worktree it deletes | D-03, D-04, D-05, D-72, C-20 | `jans/gui.py`, `CLAUDE.md`, `README.md`, `finish-pr`, `review-pr` | M |
| 4 | 1 | Use exact allowlist matches in the strike gate, extend the matcher to `MultiEdit` and `NotebookEdit`, and fail with a clear message when `jq` is missing | D-06, D-07, D-41 | `inject-plan.sh`, `settings.json` | S |
| 5 | 1 | Implement `switch` and `home` in the GUI (focus the iTerm2 tab, focus the orchestrator), or remove them from `CLAUDE.md`, `README.md` and `usage()` | D-08 | `jans/gui.py` or docs | S |
| 6 | 1 | Add `.strike_count_*` to `~/.gitignore_global` | D-33 | `~/.gitignore_global` | S |
| 7 | 2 | Give the IPC a request id per call and a result file per id; check `fetch` and `worktree add` results in `new-task`; enforce unique names; return errors for unknown names | D-09, D-13, D-16, D-35, D-44 | `jans/core/commands.py`, `jans/gui.py` | M |
| 8 | 2 | Fix `resume-status` Step 2c: a portable `sed`, and a PR number from `session.md` or the PR cache when the worktree is gone | D-10, D-11 | `resume-status` | S |
| 9 | 2 | Push the branch before `gh pr create`; detect the target repo template in `/pr-describe` | D-19, D-29 | `pre-pr`, `pr-describe` | S |
| 10 | 2 | Fix the metrics joins: log `/quality` and `/pre-pr` Fase 6b with the branch name and resolve the PR at `/finish-pr`; one schema per log; paginate `gh api`; fetch before range queries | D-31, D-32, D-40, D-46, D-76 | `quality`, `pre-pr`, `finish-pr` | M |
| 11 | 2 | Cap each injected section in bytes and skip unchanged sections; restrict the `posttool` reminder to Edit and Write | P-01, P-02, P-03, P-04, P-05 | `inject-plan.sh`, `settings.json` | M |
| 12 | 2 | Parse `feature:` and manifest list items safely in both the hook and Jans (frontmatter only, strip inline comments, `cut -s` or `sed`); fix `link_session` to match whole lines | D-36, D-37, D-38 | `inject-plan.sh`, `jans/core/features.py` | S |
| 13 | 2 | Add `description`, `source_files` and `stability` to `/finish-pr` domain entries; correct the "consumed by nobody" comments | D-12, D-24 | `finish-pr`, `kb-domains.sh`, `workflow` | S |
| 14 | 2 | Fix the `--iteration` anchor query to filter `CHANGES_REQUESTED`; list the SHA form and the skipped checks in the header | D-26, D-28 | `pre-pr` | S |
| 15 | 2 | Keep review sessions out of `/link-feature` Phase 5; fix the scan roots | D-15, D-54 | `link-feature` | S |
| 16 | 2 | Add `/quality --light` without Codex and a branch for a disconnected Codex MCP; keep one copy of the Codex parameters | P-06, D-30, D-56 | `quality`, `codex-review`, `review-pr` | S |
| 17 | 2 | Rewrite the integration guide claims that sections 7 and 8 disprove (no-op hooks, strike coverage, `.session-model`, auto-commit, sub-agent exceptions, counts, `_meta/research/`, `kb-domains.sh`, language) | D-07, D-20, D-22, D-23, D-25, D-45, D-55, D-58, D-59, D-61, D-37 | `~/research/manus/claude-integration-guide.md` | M |
| 18 | 2 | Pick one flow order and make `workflow`, `quickref`, the guide and the Jans scaffold match it | D-21, D-48, D-49, D-69, D-70 | `workflow`, `quickref`, guide, `jans/gui.py` | S |
| 19 | 2 | Restore the channel rule: merge `main` into `dev` and use one rule text | D-18 | git history, `CLAUDE.md` | S |
| 20 | 2 | Update `CLAUDE.md` with `new-review` and `state`; delete `JANS.md` and `ORCHESTRATOR.md`; rewrite the branch section of `DEVELOPMENT.md`; fix README facts | D-17, D-63, D-64, D-65, D-66, O-01 | Repository docs | S |
| 21 | 2 | Move Jans detection and `osascript` off the Tk thread, read only the JSONL tail, update widgets in place, rotate the log and log saves only on change | P-16, P-17, P-18, P-19 | `jans/gui.py`, `jans/core/state_detector.py`, `jans/core/log.py` | L |
| 22 | 3 | Merge `pr-review` into `pre-pr`, `codex-review` into `quality`, `pr-deep-review` into `review-pr` | O-07, O-08, D-50, D-68 | Skills, `quickref`, `workflow`, `conv` | M |
| 23 | 3 | Remove the `PreCompact` hook | O-04 | `settings.json`, `inject-plan.sh` | S |
| 24 | 3 | Remove the Textual TUI, the menu bar and their dependencies | O-02 | `jans/`, `pyproject.toml` | S |
| 25 | 3 | Remove dead branches: `/implement` missing model, `resume-status` 2b, `finish-research` legacy types, `finish-pr` Paso 5.5, `update-agents-md` PR cache input, `related_sessions:` | O-09, O-12, O-13, O-14, O-15, O-16, D-75 | Skills | S |
| 26 | 3 | Generate `session.md` and `task_plan.md` scaffolds from one template that Jans and the skills share | D-34 | `jans/gui.py`, `start-research`, `link-feature` | M |
| 27 | 3 | Split `review-pr`, `finish-research` and `pre-code` into a core plus per-mode files | P-12, P-09 | Skills | L |
| 28 | 3 | Translate the 8 Spanish skills, one at a time per `conv:61-117` | D-45 | Skills, `conv` | L |
| 29 | 3 | Fix the `pre-code` Metis input, the model menu and the `Blocked-by:` enforcement | D-27, O-10, O-11 | `pre-code`, `implement` | M |
| 30 | 3 | Finish the flat to `domain/` KB migration and one manifest table layout | O-05, D-53 | KB, `finish-research`, `link-feature` | M |
| 31 | 3 | Remove the superseded triage skills after verification | O-06 | Skills | S |
| 32 | 3 | Fix the small faults: launcher quoting, `_pid_tty`, the green `done` test, marker words, stale references, `DEFAULT_BRANCH` fallback, duplicate guards, `create_feature` feedback, `cp` errors, Spanish headings, the hook header, stray markers, `_meta/README.md` tables, non-numeric strike files, `.session-model` stamping on manual runs | D-39, D-80, D-73, D-71, D-67, D-43, D-57, D-47, D-74, D-52, D-62, D-79, D-60, D-77, D-78, D-14, D-51 | Jans, skills, hooks, KB | M |
| 33 | 3 | Cut per-run cost in the remaining skills: send `/implement` agents only the invariants that the TODO cites, batch the `/finish-pr` `gh api` calls, and keep deep review and the unfiltered research fallback opt-in with a cost line | P-08, P-10, P-11, P-13 | `implement`, `finish-pr`, `review-pr`, `start-research` | M |

## 11. Source map

Each fact area and the file that owns it. When this document disagrees with an owner, the owner wins.

| Fact area | Owner |
|-----------|-------|
| Jans commands and arguments | `jans/ctl.py` (`usage()`, lines 22-40) |
| What each command does | `jans/gui.py` `_execute_command` (lines 1635-1761) |
| IPC protocol and timeout | `jans/core/commands.py` |
| `state.json` format and merge | `jans/core/persistence.py`, `jans/gui.py` `_merge_external_sessions` |
| Session states and their detection | `jans/models.py`, `jans/core/state_detector.py` |
| Session scaffolds | `jans/gui.py` `_bootstrap_planning_files` (lines 176-291) |
| Feature manifest parsing and creation in Jans | `jans/core/features.py` |
| Orchestrator behavior | `CLAUDE.md` in `~/research/jans` |
| Jans branch and channel rule | `CLAUDE.md` ("Changing Jans itself"), `git log` of `main` and `dev` |
| Which hook fires on which event | `~/.claude/settings.json` `.hooks` |
| What each hook mode injects or blocks | `~/.claude/hooks/inject-plan.sh` (header and per-mode comments) |
| Write guard | `~/.claude/hooks/notepad-write-guard.sh` |
| Auto-commit scope | `~/.claude/hooks/auto-commit-config.sh` |
| Plan lock | `~/.claude/hooks/plan-lock.sh` |
| KB inventory (live) | `~/.claude/hooks/kb-domains.sh` (`list`, `match`, `research`, `review`, `prs`) |
| KB layers and entry format | `~/.claude/knowledge/README.md`, `~/.claude/knowledge/_meta/README.md` |
| Feature manifests | `~/.claude/knowledge/_meta/features/<TICKET>.md` |
| Progress protocol, language policy, skill migration status | `~/.claude/skills/CONVENTIONS.md` |
| When to use which skill, recommended models | `~/.claude/knowledge/_meta/skills-quickref.md` |
| Phase playbook | `~/.claude/skills/jandro-workflow/SKILL.md` |
| Behavior of one skill | `~/.claude/skills/<skill>/SKILL.md` |
| Model per TODO | `.session-model` in the session directory, mapping in `implement/SKILL.md` Step 1 |
| Planning file ignore rules | `~/.gitignore_global` |
| Metrics | `~/.claude/knowledge/<repo>/{quality,pre-pr,review,finish-pr}-metrics.log` |
| MCP servers and tool setup | `~/.claude/knowledge/_meta/tools.md` |
| Jira conventions | `~/.claude/knowledge/_meta/jira.md` |
| User language and writing rules | `~/.claude/CLAUDE.md` |
| High-level map for the orchestrator | `~/research/manus/claude-integration-guide.md` (does not own facts, by its own rule) |
| Analysis of all of the above | This document, at the commits in section 1 |

## Appendix A. Traceability

The four partial files were `docs/jans-analysis/01-jans-app.md`, `02-hooks-kb.md`, `03-skills-dev-flow.md` and `04-skills-review-research.md`. They are deleted in the same change and stay in the git history. No finding was dropped.

### A.1 Merged findings

| Consolidated ID | Partial findings merged | Reason |
|-----------------|-------------------------|--------|
| D-22 | 01 "guide says hooks are no-ops"; 02 "Hooks are no-ops without `task_plan.md`" | Same claim, same code |
| D-24 | 02 "`kb-domains.sh` says `pr-<n>-invariants.md` is consumed by nobody"; 03 "`/finish-pr` and `workflow` say no skill reads `pr-N-invariants.md`" | Same false claim in three files |
| D-34 | 01 task `feature: ""` against research `"standalone"`; 04 F4 (research scaffold); 04 F5 (task scaffold) | One root cause: scaffolds copied by hand |
| D-37 | 01 Jans manifest parser keeps trailing comments; 02 hook `related_features` parser keeps inline comments | One input (the guide's example) breaks both parsers |
| D-45 | 02 language policy against Spanish files; 03 eight Spanish skill bodies | Same policy, same skills |
| D-56 | 03 Codex parameters in three skills; 04 F17 `review-pr` copy | Same copies |
| D-59 | 02 `_meta/research/` not empty; 04 F15 | Same fact |
| D-71 | 03 `pr-review` marker word; 04 F16 `review-pr` marker word | Same convention break |
| C-04 | 03 "hooks inject planning files"; 04 F28 "correctness depends on hooks" | Same dependency |
| C-06 | 01 internal Claude Code files for state detection; 03 `~/.claude/sessions` and SIGTERM in `/finish-pr` | Same internal files |
| C-10 | 01 subtitle depends on marker text; 02 progress protocol depends on an `echo` | Same contract |
| C-12 | 02 `.session-model` alias; the `.session-model` part of 03 "hooks inject planning files" | Same mapping |
| C-14, C-15, C-18 | 04 F26 split by item: `ultrathink` into C-14 (with 03), `LSP` into C-15 (with 03), Codex and `WebFetch` into C-18 (with 03) | F26 bundled four dependencies that 03 lists one by one |

### A.2 Corrections from verification

Each partial finding was checked against the sources. These changed:

| Consolidated ID | Partial | Change |
|-----------------|---------|--------|
| D-11 | 04 F7 | The 2c route is at `resume-status:59` and also covers merged PRs |
| D-12 | 03 | The `match` subcommand is `kb-domains.sh:286-335`, not 266-281 |
| D-15 | 04 F8 | The fallback to `task` runs only without `session.md`; the real effect is a feature link on a review `session.md`. `state.json` read at `link-feature:55-59` |
| D-16 | 01 | `load` does check for duplicates (`gui.py:1730`); five other paths do not |
| D-17 | 01 | README also omits the `[ticket]` of `new-research` |
| D-18 | 01 | The commit lists hold at `e5f9f49`; the analysis commits add four more to `dev..main`. The rule spans lines 60-69 |
| D-20 | 03 | The claims are in the guide (`guide:200-211`, `402-403`); `quickref:58` names only Metis |
| D-22 | 01, 02 | Marker code spans `inject-plan.sh:13-32` |
| D-26 | 03 | The `quickref` anchor text is at line 27 |
| D-27 | 03 | `FAKE_CRITERION` is at `pre-code:732` |
| D-33 | 02 | The planning-file block of `~/.gitignore_global` is lines 1-15 |
| D-34 | 01 | The hook skip spans `inject-plan.sh:51-56` |
| D-37 | 02 | The parser strips the leading `- `, not every dash. Guide example at `guide:359` |
| D-40 | 03 | `finish-pr:500` uses three dots |
| D-45 | 02 | The Spanish rows are `conv:123-131` |
| D-46 | 03 | Some 6b lines carry real PR numbers; the two-schema point stands |
| D-52 | 04 F9 | Paso 5 is `finish-pr:297-334`; the Spanish heading appears at `finish-pr:348` as a description check |
| D-53 | 04 F14 | Three layouts, not two |
| D-54 | 04 F13 | `~/IdeaProjects/` is at `link-feature:390` and `432` |
| D-59 | 04 F15 | The grep is quoted; the unquoted assignment is at `resume-status:183` |
| D-66 | 01 | README lines 39, 108, 132 and 211, not line 20 |
| D-74 | 04 F19 | The claim that `date -r` is BSD-only is false and was removed |
| D-79 | 02 | `Stop` runs every turn; markers leak when the process dies first |
| O-02 | 01 | Dependencies at `pyproject.toml:10-14` |
| O-05 | 02 | The "current" label is in `kb:README.md:15`, not in `kb-domains.sh` |
| O-16 | 04 F12 | `type: research` is at `gui.py:202` |
| P-04 | 02 | Up to 4 `jq` and 2 `sed` calls |
| P-09 | 03 | Up to 6 Explore agents |
| P-16 | 01 | Two scans per tick, not three; `ps` twice per session with a tab |
| P-19 | 01 | Growth comes from one INFO line per save, every tick |
| C-03 | 02 | No script tests the tool name `Agent` |
| C-09 | 01 | `make_app.py:7-9` |
| C-18 | 04 F26 | `WebFetch` cited at `review-pr:265` and `start-research:321` |
| C-20 | 04 F29 | The summary-first workaround is at `finish-research:618-621` and `690-693` |
| 5.2.1 | 02 | `notepad-write-guard.sh` wiring is `settings.json:173-181`, `auto-commit-config.sh` is `143-151` |
