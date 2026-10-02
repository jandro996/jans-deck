# 02 - Hooks, settings, KB and conventions

Scope: the Claude Code hook layer (`~/.claude/settings.json` `.hooks`, `~/.claude/hooks/*`), the
knowledge base layout (`~/.claude/knowledge/`) and the skill contract
(`~/.claude/skills/CONVENTIONS.md`). Sources were read on 2026-10-02. Nothing under `~/.claude` was
changed. Line numbers refer to the files as read on that date.

## 1. Summary

- Five Claude Code events call one script, `inject-plan.sh`, with a mode argument. Only `userprompt` injects the planning files. The other modes inject one line, nothing, or only clean up a marker.
- Per user prompt the injection has a median of about 1.4 KB (about 350-470 tokens). Sessions with a coding-rules file or a feature manifest reach 17-28 KB (about 4,000-9,300 tokens). Nothing caps the size in bytes.
- Two hooks can block a call. The three-strikes gate in `inject-plan.sh` covers only `Edit|Write|Bash`, and its `git stash` allowlist test is a substring match. `notepad-write-guard.sh` blocks `Write` on an existing `findings.md`, `progress.md` or `decisions.md`.
- The `userprompt` mode of the injector loads one KB layer: the feature manifests in `_meta/features/` (`inject-plan.sh:118-122`). No hook loads the other layers. Skills read them through `kb-domains.sh`. The integration guide and the READMEs disagree with the scripts on at least eight points (section 4).
- Enabled plugins (`trajectory`, `trajectory-security`) register more hooks outside `settings.json`. They were not analysed.

## 2. Components

### 2.1 Hook wiring in `settings.json`

Source: `~/.claude/settings.json:132-202`. No hook sets `timeout` or `async`, so the platform defaults apply. All commands are absolute paths. `settings.local.json` has no `hooks` key.

| Event | Matcher | Command (arguments) | Line |
|-------|---------|---------------------|------|
| `UserPromptSubmit` | none (every prompt) | `inject-plan.sh userprompt` | 193-201 |
| `PreToolUse` | `Edit\|Write\|Bash` | `inject-plan.sh pretool` | 164-172 |
| `PreToolUse` | `Write` | `notepad-write-guard.sh` | 173-180 |
| `PostToolUse` | `Edit\|Write\|Bash` | `inject-plan.sh posttool` | 134-142 |
| `PostToolUse` | `Edit\|Write` | `auto-commit-config.sh` | 143-150 |
| `PreCompact` | none | `inject-plan.sh precompact` | 153-161 |
| `Stop` | none | `inject-plan.sh stop` | 183-191 |

Not matched by any matcher: `MultiEdit`, `NotebookEdit`, `Read`, `Grep`, `Glob`, `Agent`, MCP tools. Hooks do not run for them.

Related settings: `env.CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR=1` (line 3) resets the Bash cwd to the session root after each call. The hooks rely on this because they read `task_plan.md` from `$PWD`. `model` is `"sonnet"` (line 131). The stamp of `.session-model` reads it.

Scripts not wired as hooks: `plan-lock.sh` and `kb-domains.sh`. Skills call them.

### 2.2 `inject-plan.sh`

Purpose: put the session plan in front of the model, enforce the three-strikes gate, and publish an "executing" marker for Jans.

Input: first argument is the mode (default `userprompt`, line 6). The `pretool` mode also reads the hook JSON from stdin (lines 129-135). Environment: `HOME`, `PWD`, `CLAUDE_EFFORT`.

Common preamble, in order (lines 6-61). Items 1-4 run; item 5 only defines a function:

1. **Executing marker** (lines 13-32). The key is `$PWD` with every `/` replaced by `__`. The file is `~/.claude/executing/<key>` and contains the cwd. `pretool` creates it. `posttool` and `stop` delete it. This runs before the `task_plan.md` check, so it applies to every session.
2. **Plan gate** (lines 34-36). `stop` has already exited at line 31. If `task_plan.md` is missing in `$PWD`, every other mode exits 0 here.
3. **`.session-model` stamp** (lines 38-46). If the file is missing, the script writes `"<settings.json .model> effort:<CLAUDE_EFFORT>"`. A failed `jq` gives `unknown`. `CLAUDE_EFFORT` unset gives `effort:unknown`. This runs in `userprompt`, `pretool`, `posttool` and `precompact`. `/pre-code` Paso 6 later overwrites it with the real choice (`pre-code/SKILL.md:1262`).
4. **Feature resolve** (lines 48-61). `grep "^feature:" session.md | head -1 | cut -d' ' -f2`, with quotes stripped. Empty or `standalone` skips. Otherwise the manifest is `~/.claude/knowledge/_meta/features/<ID>.md`. A missing manifest skips silently.
5. **`related_features`** (function `inject_related_features`, defined at lines 63-86 and called only by `userprompt` at line 122). When called, it scans the manifest line by line. After a `related_features:` line it takes each following `- <id>` line, strips quotes, and prints `=== RELATED FEATURE: <id> ===` plus the whole file. The block ends at the first line that is not a list item. It is one level deep: related manifests are not scanned in turn.

#### Mode `userprompt` (lines 89-124)

| Item | Value |
|------|-------|
| Trigger | Every user prompt (`UserPromptSubmit`, no matcher) |
| Files read | `task_plan.md`, `progress.md`, `decisions.md`, `task_coding_rules.md`, `session.md`, the feature manifest and related manifests |
| Injection | Plain stdout, in this order: `=== TASK PLAN ===`; `=== RECENT PROGRESS ===`; `=== DECISIONS (last 80 lines ...) ===`; `=== TASK CODING RULES ===`; `=== FEATURE CONTEXT: <id> ===` plus `=== RELATED FEATURE: <id> ===` blocks |
| Limits | Plan: `head -200` plus a `(truncated: N more lines ...)` note (lines 93-97). Progress: `tail -20` (line 102). Decisions: `tail -80` (line 108). Coding rules: whole file (line 115). Manifests: whole files (lines 121-122). No byte cap anywhere. Each section is omitted when its file is missing |
| Exit code | Implicit: the status of the last command. This mode never calls `exit 2`, so it cannot block the prompt |
| Side effects | `.session-model` stamp (preamble) |

#### Mode `pretool` (lines 126-219)

| Item | Value |
|------|-------|
| Trigger | Before each `Edit`, `Write` or `Bash` call |
| Files read | stdin JSON (`tool_name`, `tool_input.command`, `tool_input.file_path`), `.strike_count_*`, `task_plan.md` |
| Injection | When no TODO is blocked: JSON `{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"Current pending TODO: <text>"}}` (lines 209-217), built from the first line that matches `^\s*- \[ \]`. When no unchecked box exists, it prints nothing |
| Limits | One line. Measured 144 bytes compact (164 pretty) for a 57-character TODO |
| Exit code | 0 normally. 2 with a stderr message when the strike gate blocks (line 197) |
| Side effects | Creates the executing marker (line 22). Removes it again before a block (line 196) |

Three-strikes gate (lines 137-202):

- **Strike files.** `.strike_count_<TODO-ID>` in `$PWD`. Each holds an integer. `/implement` writes them (`implement/SKILL.md:374`) and clears them (`:308`, `:393`).
- **Threshold.** A count `>= 3` blocks (line 148). Every file at the threshold is collected into `blocked_todos` and `blocked_files`. A non-numeric file prints an error on stderr and does not block.
- **Block.** When the call is not allowlisted, stderr gets four required actions (`git stash push -m "strike-3 ..."`, document in `decisions.md`, launch one isolated Agent, ask the user one question), then `rm -f <blocked files>`, then "Do NOT attempt a 4th variation" (lines 186-193). Exit 2.
- **Allowlist** (lines 159-183). `Bash`: any command containing `git stash` (line 165), or an exact match of `rm -f <file>`, `rm <file>`, `rm -f ./<file>`, `rm ./<file>` for a blocked file. `Write|Edit|MultiEdit|NotebookEdit`: a target whose basename is `decisions.md`. An allowlisted call exits 0 at line 201 and skips the TODO reminder.
- The gate only runs when `task_plan.md` exists and only for the matched tools.

#### Mode `posttool` (lines 221-231)

| Item | Value |
|------|-------|
| Trigger | After each `Edit`, `Write` or `Bash` call |
| Files read | `progress.md` (existence only) |
| Injection | If `progress.md` exists: JSON `additionalContext` = `progress.md may need updating with the change just made.` The text is 56 characters and the JSON is 154 bytes pretty. It fires for every call, including read-only Bash such as `ls` |
| Exit code | 0 |
| Side effects | Deletes the executing marker (line 24) |

#### Mode `precompact` (lines 233-243)

| Item | Value |
|------|-------|
| Trigger | Before context compaction |
| Injection | None that reaches the model. It echoes `[Pre-compact: flush any pending progress to progress.md before compacting]` (75 bytes) to the debug log only |
| Reason (script comment, lines 234-241) | `PreCompact` does not support `hookSpecificOutput.additionalContext`. Blocking with exit 2 is the only way to reach the model, and the author rejects it |
| Exit code | 0 |
| Side effects | `.session-model` stamp only |

#### Mode `stop` (lines 25-32)

| Item | Value |
|------|-------|
| Trigger | End of each assistant turn (`Stop`) |
| Action | Delete the executing marker, then `exit 0` before any other work. Reads no stdin and no planning file |
| Reason (comment, lines 26-29) | A blocked `pretool` or a denied permission prompt means `posttool` never runs. Without this, Jans would see the cwd as permanently executing |

#### Other modes

An unknown first argument matches no `case` branch (lines 88-244). The script then exits silently after the preamble. There is no usage message.

### 2.3 `notepad-write-guard.sh` (20 lines)

- Purpose: stop `Write` from replacing the accumulated session memory files.
- Caller: `PreToolUse`, matcher `Write` (`settings.json:174-178`).
- Input: stdin JSON. Reads `tool_name` and `tool_input.file_path` with `jq` (lines 6-8).
- Behavior: if the tool is `Write`, the basename is `findings.md`, `progress.md` or `decisions.md`, and the file already exists, it writes `BLOCKED: ... use Edit` to stderr and exits 2 (lines 10-16). Otherwise exit 0. First-time creation stays allowed.
- It does not look at `task_plan.md` and it does not guard `MultiEdit`. `inject-plan.sh pretool` also runs for `Write`. Either script can block the call with exit 2.

### 2.4 `auto-commit-config.sh` (30 lines)

- Purpose: keep `~/.claude` recoverable by committing changes to a fixed set of paths.
- Caller: `PostToolUse`, matcher `Edit|Write` (`settings.json:144-148`). It runs after every Edit or Write in any session and any repo. It does not check which file triggered it (header, lines 2-5).
- Behavior: exits 0 if `~/.claude` is not a git repo (line 10). Runs `git add skills/ knowledge/ hooks/ settings.json CLAUDE.md snowflake-mcp-setup.md .gitignore` with errors discarded (lines 13-21). Exits 0 if nothing is staged (line 24). Otherwise commits with the message `auto: <first 5 changed file names>` (lines 27-28).
- Output: nothing on stdout. Errors of `git add` are discarded (`2>/dev/null`, line 21). The `git commit` call has no redirect, so its stderr is visible (for example when another session holds `index.lock`). The script still exits 0 (line 30).
- State: the repo has 1,306 commits, 186 of them since 2026-09-01. Commit subjects are file names only.

### 2.5 `plan-lock.sh` (106 lines)

- Purpose: detect scope drift between the plan the user approved and the plan the PR implements.
- Callers: `/pre-code` runs `lock` at the end of Paso 5.5 (`pre-code/SKILL.md:1217`). `/pre-pr` runs `verify` (`pre-pr/SKILL.md:92`). Not a hook.
- Files: reads `.claude-invariants.md` and `task_plan.md`. Writes `.plan-lock`, `.plan-lock-snapshot.md`, `.plan-lock-taskplan`, `.plan-lock-taskplan-snapshot.md`. All four names are in `~/.gitignore_global`.
- `lock` (lines 29-48): SHA-256 of the invariants file, and SHA-256 of `task_plan.md` after `sed 's/- \[x\]/- [ ]/'` (lines 24-26). A missing source file prints a warning to stderr and does not fail.
- `verify` (lines 50-99): compares both hashes. On a mismatch it prints `diff snapshot current | head -60`, sets a flag and prints `Continue with /pre-pr? (y/n)`. A missing lock prints a warning and skips. It always exits 0 (line 99): the caller must read the text. Any other argument prints usage and exits 1.
- Portability: uses `sha256sum` if present, else `shasum -a 256` (line 19).

### 2.6 `kb-domains.sh` (441 lines)

- Purpose: read-only inventory and resolver over the KB, so no skill keeps its own table of KB files. It never writes.
- Callers: `/pre-code`, `/start-research`, `/pr-review`, `/pre-pr`, `/review-pr`, `/link-feature`, `/finish-research`, `/resume-status` (greps in `~/.claude/skills/*/SKILL.md`).
- Subcommands (usage, lines 10-14 and 55-62):

| Command | Reads | Output |
|---------|-------|--------|
| `list <repo>` | `<repo>/*.md` and `<repo>/domain/*.md`, minus reserved names (`pr-review.md`, `coding-rules.md`, `README.md`, `*.log`) | One row per entry (path, domain, description, stability) from the frontmatter. Entries without `source_files:` go under `UNMATCHABLE` |
| `match <repo> <file>...` | Same files | Entries whose `source_files:` match a changed file (exact, path suffix, or directory prefix). `UNMATCHABLE` is listed as well |
| `research [<repo>]` | `<repo>/research/*.md` and `_meta/research/*.md` | One row per closed research session |
| `review [<repo>]` | `<repo>/reviews/*.md` | One row per review of another person's PR |
| `prs [<repo>]` | `<repo>/prs/pr-<n>.md` (flat files only) | One row per closed PR. It reports a `MISMATCH` block when the `repo:` field disagrees with the directory |

- Exit: 0, or 1 with usage text. It uses `set -u` only.

### 2.7 Context cost per turn

**Method.** The hook was not run against the real session directories or the real `~/.claude`.

1. The script `/tmp/measure.sh` copied `task_plan.md`, `progress.md`, `decisions.md`, `task_coding_rules.md` and `session.md` of each of the 36 sessions under `~/tasks`, `~/research` and `~/tools` that has a `task_plan.md`. Each copy went into a temp directory.
2. It ran `inject-plan.sh userprompt` there with `HOME` set to a temp directory. That directory holds a copy of `settings.json` and a symlink to the real `features/` directory (read only).
3. It counted bytes of stdout per section (split on the `=== ... ===` headers) with `wc -c`.
4. Tokens are bytes divided by 4 (lower bound) to bytes divided by 3 (upper bound for markdown with paths and code). No tokenizer was available offline, so these are estimates, not counts.
5. Latency: 10 runs of each mode in the temp directory with the largest decisions file, divided by 10. It includes `bash` start-up.
6. The `pretool` and `posttool` payloads were captured from a synthetic plan with one unchecked TODO.

The measurement script was a temporary file (`/tmp/measure.sh`) and is not kept in the repository. Its core is below, so the numbers can be reproduced:

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

Per-section counts split the output on the `=== ... ===` header lines with `awk`.

A first attempt ran the hook directly in the real session directories. The `.session-model` stamp then created 13 files named `.session-model` (content `sonnet effort:high`) in sessions that had none. They were removed again (only files with that content, created in the last minutes). No other state changed. Section 4 lists the stamp as a hazard for any manual run.

**`userprompt`, bytes per prompt (n = 36 sessions).**

| Statistic | Bytes | Tokens (bytes/4 to bytes/3) |
|-----------|-------|------------------------------|
| min | 337 | 84-112 |
| median | 1,417 | 354-472 |
| mean | 5,651 | 1,413-1,884 |
| p90 | 17,582 | 4,396-5,861 |
| max | 28,018 | 7,005-9,339 |

**By session archetype (measured rows).**

| Archetype | Example | Total bytes | Plan | Progress | Decisions | Rules | Feature |
|-----------|---------|-------------|------|----------|-----------|-------|---------|
| Fresh Jans scaffold, standalone | `ander-hdiv` | 337 | 290 | 47 | 0 | 0 | 0 |
| Research with progress markers | `refactor-appsec` | 2,721 | 294 | 2,427 | 0 | 0 | 0 |
| Task after `/pre-code` | `dd-trace-java-APPSEC-69139` | 4,097 | 385 | 1,207 | 0 | 2,505 | 0 |
| Task with feature manifest | `dd-trace-java-APPSEC-69734` | 9,158 | 2,989 | 1,532 | 0 | 2,914 | 1,723 |
| Research on a big feature | `ebpf-context-propagation` | 18,056 | 303 | 1,099 | 0 | 0 | 16,654 |
| Task with long decisions log | `dd-trace-java-appsec-test-1` | 28,018 | 5,589 | 2,883 | 16,634 | 2,912 | 0 |

Section sizes include their header line. Of the 36 sessions: 27 have only `progress.md` besides the plan, 6 have rules, decisions and progress, 2 have rules and progress, 1 has none. The largest single items are a feature manifest (`APPSEC-70088.md`, 16,616 bytes, about 4,000-5,500 tokens) and a `decisions.md` tail (16.6 KB).

**Other modes.**

| Mode | Bytes to the model | Approx. tokens | Latency (avg of 10) |
|------|--------------------|----------------|---------------------|
| `userprompt` | table above | table above | 54 ms |
| `pretool` | 0 with no unchecked box; 144 compact (164 pretty) with one. The text itself is `Current pending TODO: ` plus the TODO line (39-56 characters in the real plans) | 10-25 | 71 ms |
| `posttool` | 154 pretty, 56-character text | about 14 for the text | 40 ms |
| `precompact` | 0 (debug log, 75 bytes) | 0 | 34 ms |
| `stop` | 0 | 0 | 29 ms |

Only 3 of the 9 real task plans had an unchecked `- [ ]` line at all. The Jans scaffold writes a numbered phase list, not checkboxes (`jans/gui.py:267-290`), so sessions that never ran `/pre-code` get no `pretool` reminder.

**Per-tool-call overhead.** For an `Edit`, `Write` or `Bash` call the hooks add about 110 ms (`pretool` 71 + `posttool` 40), plus `auto-commit-config.sh` for Edit and Write. A `git status` over the tracked paths takes about 25 ms (5 runs in 0.125 s); the commit is extra. Context added per call is about 25-40 tokens (pretool TODO, posttool reminder). This is an estimate.

**Cumulative effect (inferred, not measured on a transcript).** The `userprompt` stdout becomes context in the conversation for that prompt. If it stays in history until compaction, a heavy session (17-28 KB, about 4,000-9,000 tokens) adds that amount on every prompt even when the files did not change. After 30 prompts that is about 120,000-270,000 tokens of repeated text. A median session adds about 12,000 tokens in the same span. The estimate assumes no compaction.

### 2.8 Platform constraints documented by the scripts

| Constraint | Where |
|------------|-------|
| Plain stdout of `PreToolUse` never reaches the model. Use JSON `hookSpecificOutput.additionalContext`, phrased as a fact | `inject-plan.sh:204-208` |
| Plain stdout of `PostToolUse` only reaches the debug log. Use the same JSON field | `inject-plan.sh:222-225` |
| `PreCompact` supports no `additionalContext`. Its only JSON fields are `decision` and `reason`. `additionalContext` exists for `SessionStart`, `Setup`, `SubagentStart`, `UserPromptSubmit`, `UserPromptExpansion`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch`, `Stop` and `SubagentStop` | `inject-plan.sh:234-241` |
| Exit 2 blocks a `PreToolUse` call and feeds stderr to the model | `inject-plan.sh:186-197`, `notepad-write-guard.sh:14-15` |
| A blocked `PreToolUse` call and a denied permission prompt skip `PostToolUse`, so cleanup needs `Stop` | `inject-plan.sh:26-29`, `:194-196` |
| stdin can be read once; guard with `-t 0` for manual runs | `inject-plan.sh:127-131` |
| `UserPromptSubmit` plain stdout is used as injected context. The script relies on this and does not document it | `inject-plan.sh:89-123` |

### 2.9 KB layout (structure only)

Root: `~/.claude/knowledge/` (3.4 MB, 424 files). Reference documents: `README.md` (Spanish, layer map and entry format), `_meta/README.md` (ecosystem and hook overview), `kb-domains.sh list <repo>` (live inventory).

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
                                  findings, decisions; review-*.md for older reviews)
    research/<session>.md         research cache
    reviews/pr-<n>.md             review cache for other people's PRs
    quality-metrics.log pre-pr-metrics.log review-metrics.log finish-pr-metrics.log
```

Counts for `dd-trace-java`, as scale only: 113 entries in `prs/` (37 flat summaries, 29 invariants copies, 47 archive directories), 33 files in `domain/`, 17 in `reviews/`, 3 in `research/`.

Layers by purpose:

| Layer | Kind | Seen by `kb-domains.sh` command |
|-------|------|----------------------------------|
| Flat `<repo>/*.md` and `domain/` | Domain invariants | `list`, `match` |
| `prs/` | Closed own PRs | `prs` |
| `research/` | Closed research | `research` |
| `reviews/` | Reviews of other people's PRs | `review` |
| `coding-rules.md`, `pr-review.md` | Rules | none (reserved names) |
| `*-metrics.log` | Metrics | none |
| `_meta/features/` | Feature manifests | none (the hook and skills read them by path) |
| `_common/`, `_meta/*.md` | Shared knowledge | none |

#### Who writes and who reads each layer

From grep of `~/.claude/skills/*/SKILL.md` and the hook scripts. "Hook" means `inject-plan.sh userprompt`.

| Layer | Written by | Read by |
|-------|------------|---------|
| Flat and `domain/` | `/finish-pr` (consolidates invariants), `/finish-research` (Phase 5, `domain/` only), `/review-pr` deep (Phase 7a), `/pre-code` Paso 6.5 (new invariants) | `/pre-code` (`kb-domains.sh list`), `/start-research` (`list`), `/pr-review`, `/pre-pr`, `/review-pr` (`match`) |
| `coding-rules.md` | `/quality`, `/pre-pr` (append findings with PR provenance) | `/pre-code`, `/quality`, `/pre-pr`, `/pr-describe` |
| `pr-review.md` | `/finish-pr` (confirmed checks), `/finish-research` (Phase 4-5), `/review-pr` 7a | `/pr-review`, `/review-pr`, `/start-research`, `/pre-code`, `/pre-pr` |
| `_common/pr-review.md` | no skill writes it (edited by hand) | `/review-pr`, `/pre-code`, `/finish-pr`, `/pre-pr` (`SKILL.md:110-113`), `/pr-review` (`SKILL.md:70,74`) |
| `prs/` | `/finish-pr` (Paso 4 archive, Paso 5 summary), `/review-pr` Phase 7b (verbatim `review-*.md`) | `/pre-code` (`kb-domains.sh prs`), `/link-feature`, `/resume-status` Step 2c, `/finish-pr` |
| `research/` | `/finish-research` Phase 6 | `/start-research` Phase 2, `/pre-code` Paso 1.5, `/link-feature`, `/resume-status` Step 2d |
| `reviews/` | `/review-pr` Phase 7c | `/resume-status` Step 2e, `/link-feature` Phase 2a |
| `_meta/features/` | `/link-feature`, `/finish-research` (research table), `/pre-pr` and `/finish-pr` (propagate decisions, closed PRs) | **Hook** (every prompt, when `session.md` names a feature), `/pre-code`, `/link-feature` |
| `quality-metrics.log` | `/quality` | by hand (`cat`) |
| `pre-pr-metrics.log` | `/pre-pr` | `/finish-pr` (grep by PR), by hand |
| `review-metrics.log` | `/review-pr` Phase 7e | `/resume-status` (grep by PR), by hand |
| `finish-pr-metrics.log` | `/finish-pr` | by hand |

No hook writes or loads the KB, except the manifest read by the `userprompt` mode. `auto-commit-config.sh` commits the whole tree after an Edit or Write.

### 2.10 `skills/CONVENTIONS.md` (structure only)

The file is not a skill. It is the contract for all skills. It has these parts:

| Part | Lines | Rule |
|------|-------|------|
| Progress reporting | 7-33 | Each skill emits `[skill] Step\|Paso\|Fase\|Phase N - title` before a step, `[skill] next -> ...` after it, and `[skill] done` at the end. The line goes to the conversation and is appended to `progress.md` only if the file exists (`[ -f progress.md ] && echo ... >>`, never `tee -a`). The word (Step, Paso, Fase or Phase) must match the skill's own headings. Jans reads the last line of `progress.md` and colors it: grey for current, blue for `next`, green for `done` (parser checks a leading `[`, the substring `next`, and `done`) |
| Recovery tools | 37-45 | Mention `/rewind` in skills that auto-fix, and `/btw` in long-analysis skills |
| `/loop` for CI | 49-57 | Suggested after PR open (`/pre-pr` Fase 8b) |
| Language policy | 61-117 | Skill content in English; user communication in Spanish. Spanish skills migrate one at a time with a backup, a translation that changes no behavior, a read check, a smoke run and a backup removal |
| Migration status table | 119-150 | One row per skill: language, stability, readiness |
| Adding a new skill | 154-176 | Template for the `Progress reporting` block, placed before the first step heading |

Exception: `jandro-skills` has no progress block (pure index skill).

### 2.11 Planning files (per session directory)

Files live in the session cwd. `~/.gitignore_global` ignores all except `.strike_count_*`.

| File | Created by | Written by | Read by | Injected each prompt? |
|------|------------|------------|---------|------------------------|
| `task_plan.md` | Jans scaffold (`jans/gui.py:209,236,249`); `/start-research` and `/link-feature` recreate it | `/pre-code` appends `- [ ] TODO-N`; `/implement` ticks boxes | Hook (all modes use it as the gate); `/implement`, `/resume-status`, `/pre-pr`, plan-lock | Yes, `head -200` |
| `progress.md` | Jans scaffold (`gui.py:225,237,251`) | Every skill (markers); the model | Hook; Jans (last line as subtitle); `/resume-status` | Yes, `tail -20` |
| `decisions.md` | `/pre-code` (`SKILL.md:88-92`) | `/implement` (strike log), `/pre-code` | Hook; `/pre-pr` (propagates to the manifest); `/finish-pr` | Yes, `tail -80` |
| `task_coding_rules.md` | `/pre-code` | `/pre-code` | Hook; `/implement` agent; `/pre-pr` Capa 3 | Yes, whole file |
| `.claude-invariants.md` | `/pre-code` | `/pre-code`; `/quality` appends a `## §N - Candidate invariants` section, or creates the file (`quality/SKILL.md:292-302`) | `/implement` agent, `/quality`, `/pre-pr`, `/finish-pr`, plan-lock | **No** |
| `session.md` | Jans scaffold (`gui.py:200-262`) | `/link-feature` (sets `feature:`) | Hook (`feature:` line only); most skills | No (only its `feature:` value is used) |
| `findings.md` | Jans scaffold (research, tool); `/start-research` | The model; skills | `/finish-research`, `/resume-status` | No |
| `.session-model` | Hook stamp (default) | `/pre-code` Paso 6 (user choice); `/implement` Step 1 if missing | `/implement`, `/quality`, `/pre-pr`, `/finish-pr` | No |
| `.strike_count_<TODO-ID>` | `/implement` Step 7b | `/implement`; user clears | Hook `pretool` | No |
| `.plan-lock*` (4 files) | `plan-lock.sh lock` | `plan-lock.sh lock` | `plan-lock.sh verify` | No |

Review sessions (`type: pr-review-incoming`) get `session.md` only (`gui.py:255-262`), so the injection and the strike gate do not apply to them.

## 3. Interactions with the other layers

**Jans app.**

- Scaffold. Jans writes `task_plan.md`, `progress.md`, `session.md` (and `findings.md` for research and tool) in every mode except review (`jans/gui.py:200-262`). That one write turns the hook on for the session. The phase list in the scaffold is numbered text, so it adds about 300 bytes to each prompt and no `pretool` reminder.
- Executing marker. `jans/core/state_detector.py:11-30` reads `~/.claude/executing/<cwd with / replaced by __>`. A fresh marker (under 15 minutes old, line 15) makes a pending tool call count as `PROCESSING`. A pending tool call without a marker counts as `NEEDS_INPUT` (line 122). The key rule in Jans must match the key rule in `inject-plan.sh:17`. Neither file points to the other, except a comment in the hook.
- Subtitle. Jans reads the last line of `progress.md`. The format is owned by `CONVENTIONS.md`.
- Feature link. The `feature:` value in `session.md` selects the manifest the hook injects. Jans writes it from the ticket argument for research and task sessions and writes none for tool sessions (`jans/gui.py:200-262`). `/link-feature` can set it later.

**KB.** The hook reads only `_meta/features/` and never touches the rest. Skills read KB layers through `kb-domains.sh` or by path. `auto-commit-config.sh` makes every KB edit by Edit or Write a git commit.

**Skills.** Skills create and consume the planning files (section 2.11). They call `plan-lock.sh` and `kb-domains.sh`. `/implement` writes strike files that the `pretool` gate reads, and reads `.session-model` that the hook stamps. The progress markers depend on the model running a shell `echo`; the platform does not enforce them.

## 4. Findings

Evidence uses `file:line`. `guide` is `~/research/manus/claude-integration-guide.md`. `guide:N` is a line number in that file. The quoted phrase repeats the claim.

| type | item | evidence (file:line) | impact |
|------|------|----------------------|--------|
| drift | Guide says the injector, "Hooks are no-ops without `task_plan.md`" and that sessions without planning files are "completely unaffected". The executing marker is written and removed before the plan check. `notepad-write-guard.sh` and `auto-commit-config.sh` never check for the plan | guide:67-69,394; `inject-plan.sh:13-36`; `notepad-write-guard.sh:6-18`; `auto-commit-config.sh:10` | Review and tool sessions are touched by three hooks. A migration that copies only the plan-gated behavior loses the Jans state signal |
| drift | Guide says the three-strikes hook "blocks further tool use". It blocks only `Edit`, `Write`, `Bash`. `Read`, `Grep`, `Agent` and MCP calls pass. The `MultiEdit\|NotebookEdit` branch of the allowlist cannot run because the matcher excludes them | guide:143; `settings.json:165`; `inject-plan.sh:177` | A blocked session can still read and spawn agents. `MultiEdit` and `NotebookEdit` can change code under 3 strikes |
| drift | Guide says `.session-model` is stamped on first run "so it always exists". It exists only after `task_plan.md` exists. The value is the `model` alias in `settings.json` (`sonnet`), not the running model. `effort` is `unknown` when `CLAUDE_EFFORT` is unset | guide:175; `inject-plan.sh:34-46`; `settings.json:131`; `implement/SKILL.md:90` | `/implement` can pick a model that does not match the session (for example after `/model`). The "default" is invisible to the user |
| drift | Guide says `auto-commit-config.sh` "auto-commits every change under `~/.claude`". It stages seven fixed paths and runs only after Edit or Write. Log appends done through Bash (`echo >> ...-metrics.log`) wait for the next Edit or Write in any session | guide:54; `auto-commit-config.sh:13-21`; `settings.json:144`; `quality/SKILL.md:404` | Rollback may miss recent KB lines. Paths outside the list (for example `commands/`) are not staged by the hook |
| drift | Guide says `kb-domains.sh` covers "the KB domain layers and the research cache". It has five subcommands: `list`, `match`, `research`, `review`, `prs`. `_meta/README.md` lists four (no `prs`) | guide:64; `kb-domains.sh:10-14,256-441`; `_meta/README.md:99` | Two docs describe a smaller tool than the one that runs |
| drift | Guide says "currently 19 skills". There are 23 skill directories. `CONVENTIONS.md` says 22 and its table has 23 rows | guide:92; `ls ~/.claude/skills` (23 dirs); `CONVENTIONS.md:147,121-145` | Counts in three places disagree |
| drift | Guide and `_meta/README.md` say `_meta/research/` is empty. It holds `IH Role Stabilization.md` | guide:187; `_meta/README.md:50-52`; `ls knowledge/_meta/research` | `kb-domains.sh research` already returns this row; the guide says no research was closed |
| drift | `_meta/README.md` lists 5 manifests and 6 active worktrees. Disk has 9 manifests. Of the 6 worktrees, only `system-tests-APPSEC-61873-vertx` exists | `_meta/README.md:25-32,53-58`; `ls knowledge/_meta/features` | The "active worktrees" table is stale |
| drift | The header of `inject-plan.sh` lists what it injects and omits `decisions.md` and the executing marker. It says it exits silently without `task_plan.md` | `inject-plan.sh:2-4` vs `:13-36,105-109` | The header misleads anyone who reads only the header |
| drift | Language policy says KB documents are English. `knowledge/README.md` is Spanish. `CONVENTIONS.md` lists 9 skills still in Spanish (including `pre-code`, `pre-pr`, `finish-pr`). The guide says all skills and KB are English | guide:410; `~/.claude/CLAUDE.md:7-8`; `knowledge/README.md:1-12`; `CONVENTIONS.md:121-130` | A tool that parses headings or keywords in English fails on the Spanish skills |
| defect | The allowlist test `*"git stash"*` is a substring match. Under a 3-strike block, `echo git stash; cat /etc/hosts` exited 0 in a test, so any Bash command that contains the text passes | `inject-plan.sh:164-166` | The gate can be bypassed by accident or by design |
| defect | `related_features` parser strips quotes and dashes only. An inline comment stays in the id (`- APPSEC-61842   # note` gives an id with the comment), the file is not found and nothing is injected, with no error. The guide's own manifest example has such a comment. Current manifests have none | `inject-plan.sh:74-76`; guide Example 3 | Latent loss of shared feature context |
| defect | Feature id parsing: `grep "^feature:" \| head -1 \| cut -d' ' -f2`. `cut` without `-s` prints the whole line when there is no space, so `feature:APPSEC-1` gives the id `feature:APPSEC-1` (tested). The lookup of `features/feature:APPSEC-1.md` fails. The first match can come from the body, not the frontmatter | `inject-plan.sh:51` | The manifest is skipped silently |
| defect | `.strike_count_*` is not in `~/.gitignore_global`. `.session-model` and `.plan-lock` are. `git check-ignore` printed nothing for `.strike_count_TODO-1` | `~/.gitignore_global:5-16`; `implement/SKILL.md:374` | A `git add -A` in a worktree can commit a strike file into a PR |
| defect | A stray `~/.claude/knowledge/pre-pr-metrics.log` sits at the KB root with an empty `repo:` field. The skill appended to `{KB_PATH}` when the path did not resolve | `knowledge/pre-pr-metrics.log:1`; `pre-pr/SKILL.md:582` | One PR's metrics are not in the repo log. `kb-domains.sh` and `cat` queries miss it |
| defect | If `jq` is missing, `TOOL_NAME` is empty and the allowlist cannot match. Under a 3-strike block even `git stash` and `rm` of the strike file are denied (reading, not tested) | `inject-plan.sh:133-135,185` | The remediation deadlock the allowlist exists to prevent returns |
| defect | `pretool` takes the first `- [ ]` line of the whole file as the "pending TODO". Acceptance checklists or notes with unchecked boxes are reported as TODOs | `inject-plan.sh:209-212` | The model gets a wrong "current TODO" fact on each call |
| defect | A non-numeric strike file prints a `[: integer expected` error on each call and is not counted | `inject-plan.sh:148` (tested) | Noise in the hook log; a typo hides a real block |
| defect | Manual run of `inject-plan.sh` in a real session directory writes `.session-model` (13 files created in this analysis) | `inject-plan.sh:42-46` | Any "dry run" is not read-only. Use a copy and a temp `HOME` |
| defect | `executing/` holds 47 markers; 38 point to deleted directories (finished reviews and tasks). `Stop` removes only the current cwd's marker and runs only if the session ends cleanly | `inject-plan.sh:16-32`; `ls ~/.claude/executing` | Unbounded growth. Jans ignores markers older than 15 minutes (`state_detector.py:15,30`), so state is correct |
| performance | The injection has no byte cap. The manifest (up to 16,616 bytes) and the decisions tail (up to 16.6 KB for 80 lines) are sent whole on every prompt. Totals reach 28 KB per prompt | `inject-plan.sh:108,115,121-122`; measurements in 2.7 | About 4,000-9,300 tokens per prompt in the heaviest sessions, mostly repeated text |
| performance | Unchanged content is injected again on every prompt. Two sessions of one feature each pay for the same manifest | `inject-plan.sh:89-124` | History grows by the full injection per prompt until compaction (inferred, 2.7) |
| performance | `posttool` fires after every `Edit`, `Write` and `Bash` call when `progress.md` exists, including `ls`. Jans scaffolds `progress.md` in every non-review session | `inject-plan.sh:226-229`; `jans/gui.py:225,237,251`; `settings.json:135` | About 14 tokens and 40 ms per call with little value. In a 200-call run it adds about 2,800 tokens |
| performance | `pretool` runs `jq` three times plus `grep` and `sed` per call | `inject-plan.sh:133-135,209-212` | 71 ms per call. About 110 ms with `posttool`. Low but additive |
| performance | Fresh Jans sessions inject the numbered phase list on every prompt, though the text says "informational only" | `jans/gui.py:267-290` | About 300 bytes (about 75-100 tokens) per prompt for no information |
| obsolete | `PreCompact` is wired but cannot reach the model. The echo goes to the debug log only | `inject-plan.sh:234-242`; `settings.json:153-161` | A hook with no effect. The "flush progress" instruction is never seen |
| obsolete | Two parallel domain layers: flat `<repo>/*.md` ("legacy") and `domain/` ("current"). Migration is not finished (for example `dd-trace-java` has both) | `kb-domains.sh:4-6`; `knowledge/README.md` | Two places to search; `list` merges them |
| drift | `kb-domains.sh` says `prs/pr-<n>-invariants.md` is "a verbatim convenience copy ... consumed by nobody". `/finish-pr` Camino B reads it as the marker that the PR was already processed, and as a source to rebuild from. 29 such files exist for `dd-trace-java` | `kb-domains.sh:44-47`; `finish-pr/SKILL.md:80-88` | The header comment hides a live reader. Someone who deletes the "unused" files makes `/finish-pr` repeat a finished close |
| obsolete | `crash-triage-java` and `error-triage-java` are superseded by `error-tracking-triage-java` and kept "untested for rollback" | `CONVENTIONS.md:140-142` | Three skills for one job; two never run |
| claude-specific | Context injection uses the Claude Code hook JSON protocol: `hookSpecificOutput.additionalContext`, exit 2 plus stderr to block, stdin JSON with `tool_name` and `tool_input` | `inject-plan.sh:129-135,208,214,227`; `notepad-write-guard.sh:6-15` | Another tool needs its own channel for per-turn context and for blocking |
| claude-specific | The scripts rely on event names, matcher grammar (`Edit\|Write\|Bash`), tool names (`MultiEdit`, `NotebookEdit`, `Agent`) and the env vars `CLAUDE_EFFORT` and `CLAUDE_BASH_MAINTAIN_PROJECT_WORKING_DIR` | `settings.json:3,135,165,174`; `inject-plan.sh:44,177` | No equivalent exists to copy; each needs a mapping |
| claude-specific | `UserPromptSubmit` plain stdout is the injection channel for the whole plan. The script documents that Pre/PostToolUse stdout is ignored but does not document why this one works | `inject-plan.sh:89-123` vs `:204-208,222-225` | The core mechanism depends on one undocumented platform behavior |
| claude-specific | Hard-coded Claude paths: `$HOME/.claude/knowledge/_meta/features`, `~/.claude/executing`, `~/.claude/settings.json`. Jans also reads `~/.claude/sessions`, `~/.claude/projects` and the executing dir | `inject-plan.sh:11,16,43`; `state_detector.py:9-11` | The state of Jans and the manifest resolve are tied to one install location |
| claude-specific | `.session-model` holds a Claude model alias read from `settings.json`, and `/implement` maps it to an `Agent(model: ...)` call per TODO | `inject-plan.sh:43`; `implement/SKILL.md:72-117` | Model routing is tied to Claude model names and the `Agent` tool |
| claude-specific | The progress protocol depends on the model running an `echo` from the skill text. The platform does not enforce it, and Jans' subtitle depends on it | `CONVENTIONS.md:17-33` | Skipped steps silently leave the subtitle stale |
