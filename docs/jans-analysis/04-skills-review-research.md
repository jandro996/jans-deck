# 04 - Skills: review, research and coordination

Scope: `review-pr`, `start-research`, `finish-research`, `link-feature`, `resume-status`.

Source paths: every skill file is `~/.claude/skills/<skill>/SKILL.md`. Each skill has only that
file, with no support files. A reference such as `review-pr:441` means line 441 of
`~/.claude/skills/review-pr/SKILL.md`. A reference such as `gui.py:1700` means
`jans/gui.py` in this repository. Hook and KB script paths are written in full.

## Summary

- The five skills form one lifecycle: `/review-pr` handles other people's PRs. `/start-research`
  and `/finish-research` open and close research sessions. `/link-feature` ties sessions, PRs and
  research to a feature manifest. `/resume-status` recovers context from live files or KB caches.
- They write to three KB caches (`reviews/`, `research/`, and `prs/pr-<n>/` archives) and to the
  feature manifest. They read the caches only through `kb-domains.sh` subcommands.
- Total size is 2798 lines (about 138 KB). `finish-research` (715 lines) and `review-pr`
  (834 lines) are the heaviest. Each is loaded in full on every call.
- Main problems: the claim that `/finish-research` deletes the research directory is false,
  `review-pr` runs `jans-ctl delete` before it writes its metrics, and one `sed` command in
  `resume-status` fails on macOS. Session scaffolds are copied in three places and have drifted.
- Strong Claude coupling: MCP tool names, a hardcoded Atlassian `cloudId`, the `LSP` tool,
  `ultrathink`, a Codex MCP call, the `model:` frontmatter and hook gating.

## Components

### 1. `review-pr`

**Purpose and trigger.** Review someone else's PR as a reviewer. Slash command `/review-pr [ref]`
(`review-pr:1-4`). The argument can be a PR URL, `owner/repo#N` or a plain number. With no
argument, it reads `repo:` and `pr:` from `session.md` (`review-pr:38-46`). Phase 0 always asks
for a mode (`review-pr:86-100`):

- Normal: diff plus KB rules.
- Deep: subsystem analysis first, Codex cross-check, KB extraction. The skill states a cost of
  about 2-3x tokens.

The mode is chosen interactively, and Enter selects normal. The skill never posts to GitHub
without explicit confirmation (`review-pr:12`).

**Steps.** The numbered "Step N" markers are really phases:

1. Phase 0: resolve the PR, create `progress.md`, pick the mode.
2. Phase 1: checkout of the PR head. It is skipped when Jans already created the worktree.
3. Phase 2: load PR metadata and extract Jira, RFC and related PR references.
4. Phase 3: load KB (`_common/pr-review.md`, `{project}/pr-review.md`, matched domain entries).
   For dd-trace-java it also loads repo `docs/`.
5. Phase 3b (deep): fetch Jira, Confluence and related PRs. Read the subsystem. Write
   `findings.md`.
6. Phase 4: review the diff and classify each finding as blocking, non-blocking or nit.
   Sections the KB marks "advisory" are capped at non-blocking.
7. Phase 4b (deep): Codex MCP cross-check, run after Claude's own findings.
8. Phase 4c (deep): merge into CONFIRMED, CODEX-ONLY and CLAUDE-ONLY. Filter Codex-only findings
   against the KB. Deduplicate against the public Codex bot.
9. Phase 5: findings table, then ask whether to post.
10. Phase 6 (optional): `gh pr review`.
11. Phase 7: 7a KB extraction (deep), 7b archive, 7c review cache entry, 7d cleanup, 7e metrics.

**Inputs.**

- `session.md` (`repo:`, `pr:`); `gh pr view`, `gh pr diff`, `gh api .../pulls/<n>/comments`.
- KB: `_common/pr-review.md`, `{project}/pr-review.md`, and `kb-domains.sh match {project} <files>`
  (`review-pr:204`).
- dd-trace-java repo `docs/` (table at `review-pr:222-227`).
- External: Atlassian MCP `getJiraIssue` (`review-pr:247-253`), `WebFetch` for Confluence,
  the `LSP` tool for Java call sites (`review-pr:285`, `review-pr:334`), Codex MCP (`review-pr:445-470`).
- The project name comes from `git remote get-url origin`.

**Outputs.**

- `progress.md` (created in Step 0, `review-pr:76-84`) and, in deep mode, `findings.md`
  (`review-pr:294-324`).
- Archive `~/.claude/knowledge/<project>/prs/pr-<n>/review-{session,progress,findings}.md`.
  Older rounds are renamed with an mtime stamp (`review-pr:638-643`).
- Review cache `<project>/reviews/pr-<n>.md` with a fixed frontmatter (`review-pr:696-736`).
- Domain KB additions `{project}/domain/*.md` in deep mode, each one confirmed (`review-pr:602-622`).
- One line in `<project>/review-metrics.log` and in `progress.md` (`review-pr:817-826`).
- GitHub: `gh pr review --request-changes|--comment` (`review-pr:557-582`).
- Jans: `jans-ctl delete <name>` and `git worktree remove --force` after a per-action question
  (`review-pr:765-810`).

**Sub-agents and models.** No `model:` in the frontmatter and no `Agent` call. The session model
is used. Phase 3b says deep mode is worth running from an Opus session, because the skill cannot
switch models (`review-pr:243`). The only second model is Codex MCP. The parameters are `gpt-5.6-sol`,
`model_reasoning_effort: xhigh`, `sandbox: read-only`, `approval-policy: never` (`review-pr:447-454`).
These are copied by hand from `codex-review/SKILL.md:40-41`. `ultrathink` appears in Phases 3b
and 4.

**Interaction with hooks, planning files and manifests.**

- It deliberately creates no `task_plan.md`. The hooks (`inject-plan.sh`) gate on that file, so
  no injection and no three-strikes gate apply (`review-pr:48-74`).
- `review-pr:56-63` is the "single source of truth" table of who creates which file in a review
  session. `/start-research` and `/finish-research` refuse `pr-review-incoming` sessions and
  point back here.
- `notepad-write-guard.sh` blocks `Write` on an existing `findings.md`. The skill uses `Edit`
  for later additions (`review-pr:313-315`).
- Reviews are never linked to a feature manifest (`feature: standalone`, `review-pr:743-746`).

**Position in the flow.** Before: Jans `＋ Review` or `jans-ctl new-review` creates the worktree
and `session.md` (`gui.py:260`). After: the archive and review cache feed
`/resume-status` Step 2e and `/link-feature` Phase 2a. It is independent of `/pre-code`,
`/pr-review`, `/codex-review` and `/pr-deep-review`, which review your own branch.

**Obsolescence note.**

- Phase 1 Steps 2-4 (`review-pr:114-159`) are mostly a fallback. The skill itself says Jans
  already creates a correct worktree, so Step 1 short-circuits (`review-pr:161`, `gui.py:120-135`).
  Only the degraded case without a local clone reaches them.
- Overlap with `/pr-review`: Phase 3 says "same logic as `/pr-review`" (`review-pr:191`) and the
  Knowledge Base Invariant Check is repeated (`review-pr:402-405`). Phase 3 and the
  `docs/` table are dd-trace-java specific but live in a generic skill.
- Otherwise current. It was edited recently and has many self-corrections.

### 2. `start-research`

**Purpose and trigger.** Initialize a research session with KB context. Slash command
`/start-research`, no arguments (`start-research:1-4`). It runs from the session directory
(`~/research/<name>/`, a task worktree or `~/tools/<name>/`). It is interactive only when
`session.md` is missing or `related_projects` is empty. There are no modes. It is the mirror of
`/finish-research`.

**Steps** (Phase markers match the headings):

1. Phase 1: stop if `type: pr-review-incoming`. Read or interactively create `session.md`
   (types research, task, tooling). Create `task_plan.md` and `progress.md` if missing.
2. Phase 2: load `_meta/tools.md` and `_common/pr-review.md`. Inventory each related project with
   `kb-domains.sh list` and load only the entries that fit the topic. Check the research cache
   with `kb-domains.sh research`.
3. Phase 3: if `feature:` is a ticket, load the manifest and fetch the Jira issue.
4. Phase 4: create `findings.md` from a template (not for tooling) or summarize the existing one.
5. Phase 5: print the summary.

**Inputs.**

- `session.md`, `task_plan.md`, `progress.md`, `findings.md`.
- KB: `_meta/tools.md`, `_common/pr-review.md`, `{project}/pr-review.md`, selected domain
  entries, research cache entries, and the feature manifest `_meta/features/<ID>.md`.
- Atlassian MCP `getJiraIssue` with a hardcoded `cloudId` (`start-research:309-314`); `WebFetch`
  for Confluence links.
- The fallback of loading the whole domain layer is allowed after a cost warning of 80-100k
  tokens (`start-research:269-276`).

**Outputs.**

- `session.md` (if missing, 3 scaffolds at `start-research:89-121`); edits to `related_projects:`.
- `task_plan.md`, `progress.md`, `findings.md` (`start-research:137-151`, `333-357`).
- Console summary only. No KB write, no metrics log, no GitHub action, no Jans action.

**Sub-agents and models.** None. No `model:` frontmatter, no `Agent` call.

**Interaction with hooks, planning files and manifests.**

- Creating `task_plan.md` turns on `inject-plan.sh`. The skill says so explicitly
  (`start-research:130-134`).
- It reads the manifest for context but never writes it. Tooling sessions get no `feature:`
  (`start-research:123-128`).
- It refuses to run in a review directory, to protect the review contract (`start-research:41-58`).

**Position in the flow.** Before: Jans creates the session (usually with `session.md`,
`task_plan.md`, `findings.md`, `progress.md` already present, `gui.py:196-262`). After:
investigation, then `/finish-research`. The research cache it reads is written by
`/finish-research`.

**Obsolescence note.**

- Most of Phase 1 duplicates Jans `_bootstrap_planning_files` (`gui.py:176-262`). It only covers
  sessions made by hand or before Jans. This is a copy that must be kept identical by hand
  (`start-research:82-87`), and it has drifted (see findings F4, F5).
- The frontmatter description says it "creates findings.md", but Phase 4 skips that for
  `type: tooling` (`start-research:361-367`). The description is incomplete.
- No dead steps found otherwise.

### 3. `finish-research`

**Purpose and trigger.** Close a research session by contributing findings to the KB. Slash command
`/finish-research`, no arguments (`finish-research:1-4`). It always asks for confirmation before a
KB write (`finish-research:13-16`). Modes by state:

- First close.
- Already closed (`closed:` present). The user chooses summary only, reprocess new findings or
  full reprocess (`finish-research:55-79`).
- `type: tooling`. It promotes knowledge to `_meta/` and never closes (`finish-research:124-130`).
- `type: pr-review-incoming`. It stops and redirects to `/review-pr` (`finish-research:101-122`).

**Steps** (Phases 1 to 6; Phase 6 has seven sub-sections):

1. Phase 1: read `session.md`, `findings.md`, `task_plan.md`, `progress.md`; idempotence check.
2. Phase 2: resolve contribution targets from `type` and `contribution_targets` (file paths only,
   relative to `~/.claude/knowledge/`).
3. Phase 3: classify each finding as domain invariant, PR review rule, workflow insight, PR-specific
   context or SKIP.
4. Phase 4: propose each addition. Wait for y/n/edit.
5. Phase 5: write to the KB. Project files need the 7-field frontmatter. `_meta/` and `_common/`
   need none (`finish-research:215-283`).
6. Phase 6: write `closed:` and `contributed_to:` into the `session.md` frontmatter. Then:
   - Propagate a narrative entry to the manifest.
   - Write the research cache entry.
   - Add the `## Related research` row.
   - Sync the `## Active sessions` row.
   - Print the final summary.
   - Run `jans-ctl delete`.

**Inputs.**

- `session.md`, `findings.md` (including the `Started:` line), `task_plan.md`, `progress.md`.
- KB target files and `git -C ~/repos/<repo> rev-parse origin/HEAD` for `last_verified_commit`
  (`finish-research:246-255`).
- The manifest `_meta/features/<ID>.md`; `~/.jans/state.json` to resolve the Jans session name
  (`finish-research:661-682`).

**Outputs.**

- KB files: `{project}/domain/*.md`, `{project}/pr-review.md`, `_meta/*.md`, and for legacy types
  `{project}/prs/pr-XXXX.md` (append only, `finish-research:166-168`).
- `session.md`: `closed:` and `contributed_to:`.
- Research cache `{project}/research/<session>.md`, or `_meta/research/` for multi-repo research
  (`finish-research:361-483`).
- Manifest edits: narrative entry, `## Related research` row, `## Active sessions` status
  (`finish-research:316-614`). All use `Edit`.
- Jans: `jans-ctl delete <name>` as the last action (`finish-research:639-703`).
- No metrics log. Unlike `review-pr`, `quality` and `pre-pr`, this skill appends no line to any
  `*-metrics.log`.

**Sub-agents and models.** None. No `model:` frontmatter and no `Agent` call. `ultrathink` is
used in Phase 3 (`finish-research:154`).

**Interaction with hooks, planning files and manifests.**

- Reads `task_plan.md` and `progress.md` only as input.
- The manifest is the main side effect. Rows are keyed by session name and edited in place.
  `inject-plan.sh` injects the whole manifest into sibling sessions (`finish-research:490-494`).
- The `feature:` parser (`finish-research:326`) must stay in sync with `inject-plan.sh` by hand.
- `notepad-write-guard.sh` is relevant to `progress.md` and `findings.md`; this skill does not
  write them.
- `jans-ctl delete` makes the running GUI send `SIGTERM` to the Claude process whose cwd matches
  (`gui.py:1690-1701`). The skill orders its work around this (`finish-research:649-656`).

**Position in the flow.** Before: `/start-research`, investigation. After: the research cache is
read by `/start-research`, `/link-feature` Phase 2a and `/resume-status` Step 2d. `/pre-code` also
reads the manifest's `Related research` table.

**Obsolescence note.**

- Legacy types `ticket` and `e2e-validation` (`finish-research:132`) have no producer in Jans
  (`gui.py` writes research, task, tooling and pr-review-incoming only). Likely dead.
- The "Retroactive use" section (`finish-research:707-715`) covers directories that predate
  `session.md`. Probably historical.
- Claims that the skill deletes the research directory are wrong (finding F1).
- Large overlap with `/link-feature` Phase 4 on the `## Related research` table. The two share a
  format by convention only (`finish-research:511`, `link-feature:335-338`).

### 4. `link-feature`

**Purpose and trigger.** Link sessions, closed PRs and closed research to a feature manifest. Slash
command `/link-feature [TICKET-ID]` (`link-feature:1-4`). Two modes (`link-feature:8-11`):

- With a ticket: interactive for one feature. The user picks items by number.
- Without: sweep mode. It scans everything, infers groups by ticket ID and asks to confirm
  each group (`link-feature:191-212`).

It runs from any directory. Every write is shown first and asked.

**Steps.**

1. Phase 1: discover live sessions (`~/tasks`, `~/repos`, `~/research`, `~/reviews`) and read
   Jans `state.json` for the Jans `name`. `~/tools/` is skipped on purpose.
2. Phase 2a: discover closed PRs and closed research from the KB (`prs/`,
   `kb-domains.sh research`). Skip reviews of other people's PRs. Report reviews via
   `kb-domains.sh review`.
3. Phase 2b (sweep): infer ticket IDs from names, branches, `session.md`, PR frontmatter and
   research frontmatter.
4. Phase 3: validate selections; ask for a nickname and a description.
5. Phase 4: build the manifest (frontmatter, `Active sessions`, `Closed PRs`, `Related research`,
   `Key decisions`, `Cross-session invariants`); optional `related_features:`.
6. Phase 5: patch `session.md` in each active session; create `task_plan.md` and `progress.md`
   for research sessions if missing.
7. Phase 6: summary and warnings.

**Inputs.**

- Directory listings, `~/.jans/state.json`, `session.md` files, `git branch --show-current`.
- KB: `prs/` caches, `kb-domains.sh research`, `kb-domains.sh review`, existing manifests.

**Outputs.**

- Manifest `~/.claude/knowledge/_meta/features/<ID>.md` (new, or merged).
- Patched `session.md`: `feature:` and `related_sessions:`. Minimal `session.md` for sessions that
  have none. `task_plan.md` and `progress.md` for research sessions.
- No GitHub action, no Jans action, no metrics log. The Jans GUI reads `nickname:` from the
  manifest (`jans/core/features.py:23,66`).

**Sub-agents and models.** None. No `model:` frontmatter and no `Agent` call.

**Interaction with hooks, planning files and manifests.**

- The manifest is the product. `inject-plan.sh` reads `feature:` from `session.md`, then injects
  the manifest and the `related_features:` manifests on every turn. The skill warns when a linked
  session has no `task_plan.md`, because then no injection happens (`link-feature:481-487`).
- `related_sessions:` is explicitly informative. No hook or skill reads it (`link-feature:367-376`).
- `sessions:` must hold the Jans `name`, not the cwd basename (`link-feature:55-59`).

**Position in the flow.** After session creation (or after PRs and research are closed). It is the
sweep that repairs drift between manifests and reality. `/finish-research` and `/finish-pr` write
their own rows for the same tables, and `/link-feature` reconciles them.

**Obsolescence note.**

- `related_sessions:` is a stale-by-design copy of data the manifest already owns (finding F10).
- Phase 1 scans `~/repos/` (`link-feature:41`), which holds origin clones and not sessions.
  Phase 5 lists `~/IdeaProjects/` as a location (`link-feature:388`), but Phase 1 never scans it.
- Reviews are scanned in Phase 1 (`link-feature:43`) but have no place in Phase 5 (finding F8).
- Overlap: manifest tables are also written by `/finish-research` and `/finish-pr`.

### 5. `resume-status`

**Purpose and trigger.** Resume work after an interruption. Slash command `/resume-status`, no
arguments (`resume-status:1-8`). It is read-only and runs from the session directory. The routing
in Step 1 (`resume-status:49-77`) picks one of seven paths:

- 2a: planning files (task or research).
- 2b: legacy `.claude-status.md`.
- 2c: PR cache, when the worktree is gone.
- 2d: research cache.
- 2e: review (live 2e.1 or cache 2e.2).
- 2f: tooling.

Tooling is checked first, then review, because of the false matches described in the file.

**Steps.**

1. Step 1: gather `task_plan.md`, `session.md`, `progress.md` tail, `.claude-status.md`, git state
   and `gh pr view` in parallel. Route. Warn if a PR is MERGED and `.claude-invariants.md` still
   exists (`resume-status:79-90`).
2. Step 2a-2f: the selected branch.
3. Step 3: always print the git state.

**Inputs.**

- `task_plan.md`, `session.md`, `progress.md`, `findings.md`, `.claude-status.md`, `.claude-invariants.md`.
- `git branch/status/log`, `gh pr view` (`resume-status:31-42`).
- KB: `prs/pr-{n}.md`, `kb-domains.sh research`, `kb-domains.sh review`, `prs/pr-<n>/review-*.md`,
  `review-metrics.log`, and the feature manifest.

**Outputs.**

- Console summary only. It appends step markers to `progress.md` when the file exists
  (`resume-status:11-27`). No KB write, no metrics log, no GitHub action, no Jans action.
- It never runs `/finish-pr` on its own (`resume-status:90`).

**Sub-agents and models.** It is the only one of the five with a `model:` in the frontmatter:
`claude-haiku-4-5-20251001` (`resume-status:3`). No `Agent` call. The integration guide counts it
as one of the two read-only skills that pin a cheap model.

**Interaction with hooks, planning files and manifests.**

- It uses the planning files as input and the progress marker as the "where it stopped" signal.
- Hooks are not triggered by it.
- It points at the manifest for feature context (`resume-status:204-206`).
- It consumes `progress.md` markers written by other skills. Jans renders the last such line as
  the subtitle (`gui.py:295-310`).

**Position in the flow.** Entry point after a break. It recommends the next skill (`/pre-code`,
`/implement`, `/quality`, `/pre-pr`, `/finish-pr`, `/finish-research`, `/review-pr`) and never
runs it.

**Obsolescence note.**

- Step 2b `.claude-status.md` is a legacy path. Nothing in `~/.claude/skills`, `~/.claude/hooks`
  or Jans writes that file; it is mentioned only in `resume-status` and `jandro-workflow/SKILL.md:288`.
- Step 2c has two defects (findings F6, F7).
- The Spanish headings it reads from the PR cache conflict with the English language policy
  (finding F9).
- No other dead steps found.

## Interactions with the other layers

**Jans app (`jans/`).**

- Scaffolds: `_bootstrap_planning_files` (`gui.py:176-262`) writes `session.md`, `task_plan.md`,
  `findings.md` and `progress.md` per type. `start-research` and `link-feature` recreate the same
  content when it is missing.
- Delete: `jans-ctl delete` (`gui.py:1690-1705`) removes the session from memory and sends
  `SIGTERM` to the Claude process of that cwd. It does not remove files. Only the GUI delete dialog
  does (`gui.py:1165`). `finish-research` and `review-pr` call `jans-ctl delete`.
- Subtitle: `_read_last_progress` (`gui.py:295-310`) takes the last line that starts with `[`.
  A line containing `done` without an arrow is green, one with `next →` is blue. All five skills
  write markers in this format.
- State: `link-feature` and `finish-research` read `~/.jans/state.json` to map cwd to the Jans
  `name`.

**Hooks.**

- `inject-plan.sh` gates every injection on `task_plan.md`. This explains why `review-pr` must not
  create it and why `start-research` and `link-feature` must create it for research sessions.
- The manifest is injected whole on `UserPromptSubmit`. Skills rely on this instead of any
  explicit sync.
- `notepad-write-guard.sh` forces `Edit` on `findings.md` and `progress.md`. `review-pr` and
  `finish-research` follow this.
- `kb-domains.sh` is the single reader of the caches: `list`, `match`, `research`, `review`, `prs`
  (`~/.claude/hooks/kb-domains.sh:9-13`). The five skills call only `list`, `match`, `research` and
  `review`.

**Knowledge base.**

| Layer | Writer | Readers (of these five) |
|---|---|---|
| `{project}/domain/*.md` | `finish-research` P5, `review-pr` 7a | `start-research` P2, `review-pr` P3 |
| `{project}/pr-review.md` | `finish-research` P5 | `start-research` P2, `review-pr` P3 |
| `{project}/research/<session>.md` | `finish-research` P6 | `start-research` P2, `link-feature` 2a, `resume-status` 2d |
| `{project}/reviews/pr-<n>.md` | `review-pr` 7c | `link-feature` 2a, `resume-status` 2e |
| `{project}/prs/pr-<n>/review-*.md` | `review-pr` 7b | `link-feature` 2a (filter), `resume-status` 2e |
| `{project}/prs/pr-<n>.md` | `/finish-pr` | `link-feature` 2a, `resume-status` 2c |
| `_meta/features/<ID>.md` | `link-feature` P4, `finish-research` P6 | `start-research` P3, all hooked sessions |
| `{project}/review-metrics.log` | `review-pr` 7e | `resume-status` 2e.2 |

## Findings

Types: `obsolete`, `drift`, `defect`, `performance`, `claude-specific`. IDs are for reference only.

| type | item | evidence (file:line) | impact |
|---|---|---|---|
| drift | F1: Three skills say `/finish-research` deletes the research directory, but no step does it. `jans-ctl delete` only unregisters and sends SIGTERM. Only the GUI delete dialog calls `rmtree`. | `finish-research/SKILL.md:601-606` ("directory ... no longer exists after this skill finishes"); `link-feature/SKILL.md:363-365`; `resume-status/SKILL.md:173-174`, `201`; `gui.py:1165`, `gui.py:1690-1705` | Closed research directories stay on disk. `/resume-status` Step 2d (cache recovery) is reached only after a manual delete. `/link-feature` Phase 1 still lists closed research as live. The `closed` state rationale in the manifest is correct but the stated reason is false. |
| defect | F2: `review-pr` runs `jans-ctl delete` in 7d and writes the metrics line in 7e afterwards. The delete sends SIGTERM to the Claude process of that cwd, so the process can be killed before 7e. `finish-research` avoids this by putting delete last. | `review-pr/SKILL.md:785-788`, `812-827`; `gui.py:1695-1701`; ordering rule at `finish-research/SKILL.md:649-656` | `review-metrics.log` line and the last `progress.md` marker can be lost when the user answers "yes" to removing the Jans session. The metrics log is the only long-term signal of review quality. |
| defect | F3: The skill rule says the last step writes `[review-pr] done` (`review-pr:32`), but 7e writes a metrics line instead and no `done` marker is written. Also, `progress.md` is gone after 7d. | `review-pr/SKILL.md:32`, `816-829`; `gui.py:304-310` | Jans shows the metrics line in dim color as the subtitle instead of a green `done`. A finished review looks unfinished. |
| drift | F4: The research `session.md` scaffold differs by creation route. `link-feature` omits `investigation:`; `gui.py` and `start-research` include it. `start-research` claims the three must be identical. | `start-research/SKILL.md:82-87`, `89-99`; `link-feature/SKILL.md:398-408`; `gui.py:204` | `/finish-research` and other readers see different keys depending on who made the session. The copy-by-hand design cannot hold. |
| drift | F5: The task scaffold differs. `start-research` writes `feature: "<TICKET-ID>"`; `gui.py` writes `feature: ""` when there is no ticket; `link-feature` writes neither `related_projects` nor `contribution_targets` for tasks. | `start-research/SKILL.md:102-110`; `gui.py:228-234`; `link-feature/SKILL.md:432-440` | Same as F4. An empty `feature:` is also an edge case for the `cut -d' ' -f2` parser (`finish-research/SKILL.md:326`). |
| defect | F6: The `sed -E` command in Step 2c uses a lazy `+?`, which BSD sed on macOS rejects (`repetition-operator operand invalid`). Reproduced here. `PROJECT` stays empty and the lookup returns `NO_PR_CONTEXT`. Without the lazy operator the result would still keep `.git`. | `resume-status/SKILL.md:156` | The PR cache recovery never finds a file on macOS, even when it exists. The user sees "no saved context". |
| defect | F7: Step 2c runs only when the worktree is gone, but it needs `git remote get-url origin` and `gh pr view` from that same cwd. In a missing worktree both fail, so neither PR number nor project can be resolved. | `resume-status/SKILL.md:60-61`, `148-158` | Step 2c is unreachable in its main case. Recovery works only if the user supplies the PR number by hand. |
| defect | F8: `link-feature` Phase 1 scans `~/reviews/` and reads `state.json` for it, but Phase 5 has no row for reviews. A review dir that reaches Phase 5 gets no valid type and may fall to `task`, which would overwrite a `pr-review-incoming` `session.md`. The skill only guards `~/tools/`. | `link-feature/SKILL.md:43`, `164-169`, `385-396` | Risk of breaking the review contract (`session.md` only, no hooks) if a review dir is selected. Plausible, not reproduced. |
| drift | F9: `resume-status` Step 2c reads Spanish headings ("Contexto rápido para retomar en frío", "Decisiones de diseño no obvias") from the PR cache. The language policy says KB documents are English. `/finish-pr` Paso 5 does not write those headings; it writes `## Conocimiento consolidado`. The writer of the headings is not identified. | `resume-status/SKILL.md:161-162`; `finish-pr/SKILL.md:297-345`; `~/.claude/knowledge/dd-trace-java/prs/pr-11179.md:25,55,62` | Recovery depends on headings with no known owner. A KB entry written under the English policy would not match. |
| obsolete | F10: `related_sessions:` is written into `session.md` but no hook or skill reads it. The skill admits it goes stale. | `link-feature/SKILL.md:367-376`, `378-383` | Dead data and extra prompts per session, with no consumer. |
| obsolete | F11: Step 2b and `.claude-status.md`. No producer exists in skills, hooks or Jans. The file is also read in every Step 1 run. | `resume-status/SKILL.md:37`, `58`, `138-144`; `jandro-workflow/SKILL.md:288` | Dead branch plus a wasted read. The frontmatter description keeps advertising it. |
| obsolete | F12: Legacy types `ticket` and `e2e-validation` have no producer in Jans. The "Retroactive use" section covers directories older than `session.md`. | `finish-research/SKILL.md:132`, `707-715`; `gui.py:204,230,242,260` | Dead branches that add reading cost to the longest skill after `review-pr`. |
| drift | F13: `link-feature` Phase 1 scans `~/repos/` (origin clones, not sessions) and Phase 5 lists `~/IdeaProjects/`, which Phase 1 never scans. | `link-feature/SKILL.md:39-44`, `387-389` | Noise in the candidate list; sessions under `~/IdeaProjects/` are never discovered. |
| drift | F14: The Active sessions table has two layouts. The template has a `Status` column; the older real manifests have `Branch` and `Notes`. `finish-research` carries a 3-case workaround. | `link-feature/SKILL.md:291-294`; `finish-research/SKILL.md:598-602` | Two writers, two schemas. Every consumer needs a branch for each layout. |
| drift | F15: The integration guide says `_meta/research/` is empty, but it holds `IH Role Stabilization.md` (research, closed 2026-08-24, name with spaces). Its `reprocessed:` key is empty. | `~/.claude/knowledge/_meta/research/IH Role Stabilization.md:1-12`; `claude-integration-guide.md` ("Research cache" section) | The guide is stale. The space in the session name also affects `grep -i "$SESSION_NAME"` in Step 2d. |
| drift | F16: Progress markers say "Step N" in `review-pr` although its headings are "Phase N". `start-research`, `finish-research` and `link-feature` say Phase. | `review-pr/SKILL.md:19-24` versus `36`, `104`, `165` | Marker numbers do not match the headings a user sees. Minor. |
| drift | F17: The Codex parameters in `review-pr` are a hand copy of `codex-review/SKILL.md`. The model name and effort live in two places. | `review-pr/SKILL.md:447-454`; `codex-review/SKILL.md:40-41`, `125-126` | A change in one file leaves the other with stale parameters. |
| drift | F18: `review-pr` mixes repo-specific rules into a generic skill: dd-trace-java `docs/` table, §17 advisory rule, `APPSEC-\d+` patterns. | `review-pr/SKILL.md:181`, `211-227`, `357-361` | Other repos run the same text. The skill needs edits to support a new repo. |
| defect | F19: `review-pr` 7b copies files with `cp ... 2>/dev/null`, which hides failures. The skill itself records that 0 of 4 deep reviews left a `findings.md` because of this. A check and a guard now exist. `date -r FILE +fmt` is BSD-only. | `review-pr/SKILL.md:290-292`, `640`, `645-647`, `664-671` | Mitigated, but the stamp command breaks on GNU/Linux. |
| defect | F20: `gui.py` marks a progress line green when it contains the substring `done` without `→`. A marker whose title contains the word (for example a step title) is shown as finished. | `gui.py:304-310`; markers at `review-pr/SKILL.md:19` | Low. A wrong green subtitle. |
| performance | F21: Skill size. `review-pr` 834 lines (37,998 B) and `finish-research` 715 lines (43,350 B) are loaded in full on each call. Most of the text is in branches that do not run in a given call. | `review-pr/SKILL.md:1-834`; `finish-research/SKILL.md:1-715` | Roughly 10k tokens of instructions per invocation, before any work. Splitting by mode would cut it. |
| performance | F22: Deep review is costed at 2-3x tokens, and Phase 4b adds a sequential Codex `xhigh` call after Claude's pass. The unfiltered fallback in `start-research` can load 80-100k tokens. | `review-pr/SKILL.md:94`, `412-414`, `447-454`; `start-research/SKILL.md:269-276` | High per-run cost. Both are opt-in or warned. |
| performance | F23: `resume-status` runs `gh pr view` (network) on every call, including research and tooling sessions that have no PR. | `resume-status/SKILL.md:41` | Slower start and a noisy `NO_PR`. Low. |
| performance | F24: `resume-status` is pinned to Haiku but carries a 7-branch routing with ordering rules ("check this first"). A weak model may misroute. | `resume-status/SKILL.md:3`, `49-77` | Wrong recovery path is plausible. Not measured. |
| claude-specific | F25: Atlassian MCP tool `mcp__atlassian__getJiraIssue` with a hardcoded `cloudId`. The same block is in two skills. | `review-pr/SKILL.md:247-253`; `start-research/SKILL.md:309-314` | Blocks migration. Needs an abstraction for "fetch ticket". |
| claude-specific | F26: Codex MCP call, `LSP` tool (`findReferences`, `incomingCalls`, `goToImplementation`), `WebFetch`, and the keyword `ultrathink`. | `review-pr/SKILL.md:243`, `285`, `330`, `334`, `445-470`; `finish-research/SKILL.md:154` | Each is a Claude Code feature or a Claude MCP. Another tool needs equivalents. |
| claude-specific | F27: `model:` frontmatter and the instruction that "the skill cannot switch models". Model choice is a session setting. | `resume-status/SKILL.md:3`; `review-pr/SKILL.md:243` | The pinning mechanism has no portable equivalent. |
| claude-specific | F28: Correctness depends on hooks: `task_plan.md` gating in `inject-plan.sh`, the `notepad-write-guard.sh` rule on `Write`, and manifest injection. Skills create or avoid files to steer the hook. | `review-pr/SKILL.md:48-74`; `start-research/SKILL.md:130-134`; `link-feature/SKILL.md:410-414`; `finish-research/SKILL.md:490-494` | The workflow is encoded in file presence. A tool without these hooks loses the injection and the review isolation. |
| claude-specific | F29: The skill process can be killed by its own final command (`jans-ctl delete` sends SIGTERM to the matching Claude process). The workaround is to print the summary first. | `finish-research/SKILL.md:649-656`, `695-703`; `gui.py:1695-1701` | Needs a different closing mechanism in another host. |
