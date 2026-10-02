# 03 - Development flow skills

Partial analysis for `docs/jans-analysis.md`. Scope: 10 skills of the task-implementation flow:
`pre-code`, `implement`, `quality`, `pr-review`, `pre-pr`, `pr-describe`, `finish-pr`,
`update-agents-md`, `pr-deep-review`, `codex-review`.

Sources were read in full on 2026-10-02. All skills live in `~/.claude/skills/<name>/SKILL.md`.
None of the 10 has support files (each directory holds only `SKILL.md`).

## Citation legend

Citations have the form `name:LINE`.

| Prefix | File |
|--------|------|
| `<skill>` (for example `pre-pr`) | `~/.claude/skills/<skill>/SKILL.md` |
| `workflow` | `~/.claude/skills/jandro-workflow/SKILL.md` |
| `conv` | `~/.claude/skills/CONVENTIONS.md` |
| `quickref` | `~/.claude/knowledge/_meta/skills-quickref.md` |
| `inject-plan.sh`, `plan-lock.sh`, `kb-domains.sh` | `~/.claude/hooks/<file>` |
| `gui.py`, `commands.py` | `jans/gui.py`, `jans/core/commands.py` in this repository |
| `kb:<path>` | `~/.claude/knowledge/<path>` |

## Summary

- The 10 skills form one chain: `pre-code` -> `implement` (per TODO) -> `quality` -> `pre-pr` -> `pr-describe` -> reviewer loop (`pre-pr --iteration`) -> `finish-pr`. Four skills are side branches: `pr-review`, `pr-deep-review`, `codex-review`, `update-agents-md`.
- Only three skills spawn sub-agents: `pre-code` (Explore agents and one Opus "Metis" review), `implement` (one agent per TODO, model from `.session-model`) and `pre-pr` (two parallel Opus reviewers). No skill sets `model:` in its frontmatter.
- The three sources that define the flow order (`workflow`, `quickref`, the Jans scaffold in `gui.py`) disagree on `/pr-review`, `/pr-deep-review`, `/codex-review`, `/update-agents-md` and on whether `/pr-describe` is a separate step.
- 8 of the 10 skill bodies are still in Spanish, against the language policy. Most logic is tied to dd-trace-java (Gradle, muzzle, AppSec examples) and to Claude Code (Agent, LSP, `ultrathink`, Glob-for-hook-bypass, `~/.claude/sessions`).
- Most serious defects: 23 of 28 lines in the four `quality-metrics.log` files carry `pr: none` (observed), which a `finish-pr` join by PR number cannot match (inferred, the join was not run); `finish-pr` Paso 6.5 would SIGTERM its own session if the user continues from inside the worktree (static reading); `finish-pr` writes KB entries that `kb-domains.sh match` cannot select (they stay reachable only by manual judgment); `--iteration` without argument does not use the documented anchor.

## Components

### Flow diagram

Order below is the one in `workflow` phases 0 to 6 (`workflow:47-151`), merged with
`quickref:5-16` and with what each skill calls internally. `*` marks optional steps.

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

Where the three order sources disagree:

| Topic | `workflow` | `quickref` | Jans scaffold (`gui.py:284-290`) | Skill itself |
|-------|-----------|-----------|----------------------------------|--------------|
| `/implement` | Phase 1 step 1.3 (`workflow:72`) | Listed (`quickref:24`), absent from the "when to use" table (`quickref:5-16`) | Phase 1 "Implementation", no command | Requires `/pre-code` first (`implement:55`) |
| `/quality` | Optional, "in parallel" (`workflow:84-88`) | "in parallel" (`quickref:25`) | Phase 2, optional | "sequential, independent passes" (`quality:3`, `quality:86`) |
| `/pr-review` | Quick reference only (`workflow:279`), not in any phase | Not mentioned at all | Not mentioned | `/pre-pr` "replaces" it (`pre-pr:3`); Fase 2c reuses its procedure (`pre-pr:214`) |
| `/pr-deep-review` | Optional before `/pre-pr` (`workflow:109`) | Not mentioned at all | Not mentioned | Standalone, no link to other skills |
| `/codex-review` | Phase 5.1 fallback (`workflow:129`) | Support list (`quickref:52`) | Not mentioned | Told to be redundant after `/pre-pr` Fase 8b (`codex-review:10`); `/quality` Pass X also runs Codex (`quality:154`) |
| `/pr-describe` | Separate Phase 4 step after `/pre-pr` (`workflow:117`) | `/quality` -> `/pre-pr` -> `/pr-describe` (`quickref:8`) | Phase 4 | `/pre-pr` Fase 8 calls it itself (`pre-pr:475`), so a manual run afterwards hits the "PR exists" branch `gh pr edit` (`pr-describe:189-194`) |
| `/update-agents-md` | Quick reference only (`workflow:283`) | "before merging" (`quickref:51`) | Not mentioned | `finish-pr` suggests it after the merge, before cleanup (`finish-pr:505-510`) |
| Review-round commit | `"fix: review comments round N"` (`workflow:132`) | n/a | n/a | `"address review comments"` (`pre-pr:718`) |
| Number of checklist sections | "sections 1-17 of dd-trace-java/pr-review.md" (`workflow:101`) | n/a | n/a | KB file has section 18 and more (`kb:dd-trace-java/pr-review.md:430`) |

### `pre-code`

- **Purpose and trigger.** Discover domain invariants and the canonical pattern before writing code. Command `/pre-code [arg]`. Argument is one of: a prior `.claude-invariants.md` (extend it), a spec `.md`, or an inline task text; with no argument it reads the conversation (`pre-code:42-53`). A retroactive mode validates an existing PR diff against KB invariants (`pre-code:55-78`). `workflow:275` says "Always, before coding".
- **Steps.**
  1. Paso 0 task text, create `progress.md` and `decisions.md` (`pre-code:80-102`).
  2. Paso 0.5 detect project from the git remote, check `docs/`, optional Google Doc via MCP (`pre-code:109-157`).
  3. Paso 0.6 fetch and offer rebase (`pre-code:161-202`).
  4. Paso 1 classify the task (`pre-code:206-241`).
  5. Paso 1.5 load KB: `kb-domains.sh list`, `_common/pr-review.md`, `<repo>/pr-review.md`, `coding-rules.md`, feature manifest, closed PRs, research cache, `kb-domains.sh prs` (`pre-code:245-426`).
  6. Paso 2 reference example via Explore agent (`pre-code:430-459`).
  7. Paso 3 parallel Explore agents A to E (`pre-code:463-638`).
  8. Paso 4 synthesis with `ultrathink` (`pre-code:642-704`).
  9. Paso 4.9 Metis adversarial plan review (`pre-code:707-750`).
  10. Paso 4.5 checkpoint, user must confirm (`pre-code:754-833`).
  11. Paso 5 write `.claude-invariants.md` and `task_coding_rules.md` (max 40 lines) (`pre-code:837-1108`).
  12. Paso 5.5 append TODOs to `task_plan.md`, preview, confirm, then `plan-lock.sh lock` (`pre-code:1112-1220`).
  13. Paso 6 summary, then model choice written to `.session-model` (`pre-code:1224-1278`).
  14. Paso 6.5 update domain KB (`pre-code:1282-1346`).
- **Inputs.** Codebase; `docs/` of the repo (dd-trace-java); KB layers `_common`, `<repo>/*.md`, `<repo>/domain/`, `prs/`, `research/`, `_meta/features/`; `session.md`; tools `git`, `gh pr diff`, `kb-domains.sh`; MCP: Datadog (span check, `pre-code:283-297`), Google Workspace (`pre-code:150-155`); `LSP` tool with the `jdtls-lsp` plugin (`pre-code:467`).
- **Outputs.** `.claude-invariants.md`, `task_coding_rules.md`, `task_plan.md` (append only), `decisions.md` header, `progress.md` checkpoint block (`pre-code:813-827`), `.session-model`, `.plan-lock*` files, KB domain entries with frontmatter (`pre-code:1328-1340`). No metrics log.
- **Sub-agents and models.** No `model:` in frontmatter (`pre-code:1-4`). Up to 5 `Agent(Explore, ...)` calls in parallel for dd-trace-java, 4 for system-tests (`pre-code:473-637`). One `Agent(general-purpose, model: opus)` for Metis (`pre-code:718`). `quickref:62` lists Metis as the only real sub-agent exception. Model menu for `/implement` offers `sonnet-4.6`, `opus-4.8`, `sonnet-5`, `opus-5`, other (`pre-code:1248-1251`). Estimated cost: 10 to 20 minutes, 4 to 6 agents (`pre-code:1353`).
- **Hooks and planning files.** Creates `decisions.md` (guarded later by `notepad-write-guard.sh`, `pre-code:102`). Locks the plan at the end of Paso 5.5 (`pre-code:1217`). `task_coding_rules.md` is injected whole on each `UserPromptSubmit`; `task_plan.md` is injected up to 200 lines (`pre-code:1118`, `inject-plan.sh:91-96`). Overwrites the default `.session-model` stamped by the hook (`pre-code:1259-1262`, `inject-plan.sh:39-46`). Progress markers use the word `Paso` (`pre-code:15`).
- **Position in flow.** First step of a task session (Phase 0). Before: Jans creates the worktree plus `session.md`, `task_plan.md` (reference phases, no checkboxes), `progress.md` (`gui.py:225-251`, `gui.py:266-291`). After: `/implement`. Not for research sessions (`workflow:168`).
- **Obsolescence signals.**
  - Model menu hard-codes version labels that `/implement` collapses to a family (`pre-code:1248-1251`, `implement:80-88`); the menu has no `haiku` or `fable` entry although `/implement` accepts both (`implement:38-39`).
  - Paso 4.9 asks for "the draft implementation checklist (section 5)" as Metis input (`pre-code:714`), but no step before it produces a draft: Paso 4 lists synthesis only (`pre-code:642-704`) and the `verify:` rule is placed after the checkpoint (`pre-code:833`, `pre-code:837-839`). The skill does not say where the draft comes from. This is a static reading; no archived run shows what Metis received.
  - `touch progress.md` runs unconditionally (`pre-code:85`) while the checkpoint says to never create it (`pre-code:829`). Low impact because Jans scaffolds it (`gui.py:225`).
  - `Commit:`, `Blocks:` and `Blocked-by:` sub-bullets (`pre-code:1143-1144`) reach the agent only as verbatim text (`implement:193-203`). No step of `/implement` acts on them: no commit step for `Commit:`, no check of `Blocked-by:` when a TODO is selected (`implement:121-141`), and the agent instructions name only References and `verify:` (`implement:233-239`). The hook picks the first unchecked box (`inject-plan.sh:208`). They are not enforced.
  - dd-trace-java and system-tests branches are hard-coded (`pre-code:133-137`); other repos get a "generic" path with no agent prompts.
  - Spanish body (`pre-code:3`); `conv:123` marks it "actively changing", so not migrated.

### `implement`

- **Purpose and trigger.** Run one TODO of `task_plan.md` in a focused sub-agent. Commands: `/implement`, `/implement TODO-1`, `/implement TODO-1 sonnet` (second argument is a one-shot model override: `sonnet`, `opus`, `haiku`, `fable`) (`implement:30-40`).
- **Steps.**
  1. Step 1 verify `task_plan.md` and `.claude-invariants.md` exist (via Glob), resolve the model (`implement:44-117`).
  2. Step 2 select the TODO (`implement:121-141`).
  3. Step 3 read the strike count; stop at 3 (`implement:145-185`).
  4. Step 4 build a self-contained prompt from the verbatim TODO block, the full invariants, the full coding rules and past failures (`implement:189-250`).
  5. Step 5 launch `Agent(model, prompt)` (`implement:254-263`).
  6. Step 6 show the result; the user answers success, failure or review (`implement:267-284`).
  7. Step 7a on success, set `[x]`, write progress, remove the strike file (`implement:288-324`).
  8. Step 7b on failure, append to `decisions.md` first, then write the strike file (`implement:328-405`).
  9. Step 7c on review, show `git diff` (`implement:409-418`).
- **Inputs.** `task_plan.md`, `.claude-invariants.md`, `task_coding_rules.md`, `decisions.md`, `.session-model`, `.strike_count_<TODO-ID>`.
- **Outputs.** Code changes by the agent; `[x]` in `task_plan.md`; status line in `progress.md` (`implement:302`, `implement:380`); strike file; strike block in `decisions.md`. No commit, no metrics log.
- **Sub-agents and models.** One `Agent` per TODO, no `subagent_type` given (`implement:256-261`). Model map: `default` -> sonnet, `opusplan` -> opus, otherwise family substring, unknown -> sonnet (`implement:78-105`). Per-call override in the second argument (`implement:59-70`).
- **Hooks and planning files.** Uses Glob and Read instead of Bash in Steps 1 and 2 so the `pretool` BLOCKED gate does not trip before strike handling (`implement:46-48`, `implement:123-126`). Writes `decisions.md` with Edit, never a heredoc, because only Write/Edit tools are allowlisted at 3 strikes (`implement:352-358`). Strike file name uses the full id (`implement:152-154`); `inject-plan.sh` derives the id back from the file name. Ordering rule: `decisions.md` before the counter (`implement:330-333`). Checkbox flips are ignored by `plan-lock.sh:24-26`.
- **Position in flow.** After `/pre-code`; repeated per TODO. Next: `/quality` or `/pre-pr` (`implement:323`).
- **Obsolescence signals.**
  - The "`.session-model` missing" branch (`implement:107-117`) is dead when hooks run: `inject-plan.sh` stamps the file as soon as `task_plan.md` exists (`inject-plan.sh:42-46`), and Step 1 already requires `task_plan.md` (`implement:55`).
  - No Step 7 branch has an explicit command for the closing `[implement] done` marker; only the general protocol asks for it (`implement:28`, `implement:299-324`). Archived `progress.md` files do contain the marker (8 lines `[implement] done` under `kb:*/prs/*/progress.md`), so the model writes it from the protocol text. The skill is ambiguous, not broken.
  - Note at `implement:427` says `/pre-pr` runs "the full test suite"; `/pre-pr` runs only affected Gradle modules (`pre-pr:334-363`) and nothing when there is no Gradle (`pre-pr:382-385`).
  - `sed -i ''` is BSD-only (`implement:294-296`), acknowledged in a comment.
  - `default` -> `sonnet` assumes the account default (`implement:96`); `settings.json` has `model: sonnet` today, so the rule is correct only while that holds.

### `quality`

- **Purpose and trigger.** Review the own branch diff for tech debt, simplification and correctness, check each finding against domain invariants, apply valid fixes, grow `coding-rules.md`. Command `/quality [file]`; with no argument it reviews `origin/$DEFAULT_BRANCH..HEAD` (`quality:78-80`). Optional per `workflow:84-90`.
- **Steps.**
  1. Context guard: stop inside `~/reviews/` or a `pr-review-incoming` session (`quality:30-44`).
  2. Step 0 load context and KB (`quality:48-80`).
  3. Step 1 passes A (techdebt), B (simplify), C (code review) plus mandatory checkpoint output (`quality:84-145`).
  4. Pass X: Codex MCP inline, after the checkpoint (`quality:149-172`).
  5. Step 2 classify VALID, CONFLICTS, NEEDS-JUDGMENT against invariants (`quality:176-203`).
  6. Step 3 findings table and confirmation (`quality:207-233`).
  7. Step 4 apply fixes, run `./gradlew spotlessApply` (`quality:237-260`).
  8. Step 5 write `coding-rules.md`, exceptions, candidate invariants (`quality:264-363`).
  9. Step 6 metrics line and summary (`quality:368-431`).
- **Inputs.** `.claude-invariants.md`, `kb:<repo>/coding-rules.md`, first 100 lines of `kb:<repo>/pr-review.md` (`quality:74-75`), git diff, `gh pr view`, Codex MCP, `LSP` tool (`quality:88`).
- **Outputs.** Source edits; `kb:<repo>/coding-rules.md`; optional `## §N - Candidate invariants` appended to `.claude-invariants.md` (`quality:288-311`); one metrics line to `progress.md` and `kb:<repo>/quality-metrics.log` (`quality:395-410`). Fields include `codex-findings`, `codex-valid`, `codex-conflicts` (`quality:385-391`).
- **Sub-agents and models.** No Agent calls. All passes run in the session context. Codex call parameters: `cwd`, `sandbox: read-only`, `approval-policy: never`, `model: gpt-5.6-sol`, `config: {model_reasoning_effort: xhigh, personality: pragmatic}` (`quality:156-163`). `quickref:65` recommends Sonnet.
- **Hooks and planning files.** Reads `.session-model` with `awk '{print $1}'` (`quality:375-381`). Appending to `.claude-invariants.md` makes `plan-lock.sh verify` warn in the next `/pre-pr` Fase 1; the skill documents this (`quality:309-311`). Marker word `Step`; Pass X has no marker of its own.
- **Position in flow.** After the last `/implement`, before `/pre-pr`. `finish-pr` joins its metrics with `pre-pr` metrics (`finish-pr:460-491`).
- **Obsolescence signals.**
  - Description says "sequential" (`quality:3`); `workflow:88` and `quickref:25` say "in parallel". Since no sub-agents are used, the passes share one context, so the anti-anchoring claim (`quality:86`) holds only for the order "Claude first, Codex second" (`quality:151-152`).
  - Passes B and C and the `spotlessApply` call are Java/Gradle specific (`quality:99-115`, `quality:259`); on Python repos they produce noise or `NO_SPOTLESS`.
  - Pass X is "always on" within each invocation (`quality:154`) and has no light mode. `workflow:90` lets the user skip the whole `/quality` run for trivial changes, which is compatible.
  - Codex parameters are copied into three skills (`quality:156-163`, `codex-review:40-41`, `review-pr:453`).
  - Same guard block copied into five skills (`quality:37-40`).

### `pr-review`

- **Purpose and trigger.** Loader plus "Knowledge Base Invariant Check": load `_common/pr-review.md` and `<repo>/pr-review.md`, resolve matching domain entries with `kb-domains.sh match`, verify the diff against each invariant, print a table (`pr-review:57-167`). Command `/pr-review`, no arguments. For the own branch only (`pr-review:41-45`).
- **Steps.** Context guard (`pr-review:39-53`); "Knowledge Base loading" (`pr-review:57-77`); "Knowledge Base Invariant Check" with Paso 1 diff and domain match, Paso 2 staleness via `last_verified_commit`, Paso 3 verify with `ultrathink`, Paso 4 report with status icons (`pr-review:81-167`).
- **Inputs.** `git remote`, `git diff origin/$DEFAULT_BRANCH...HEAD`, KB `_common/pr-review.md`, `<repo>/pr-review.md`, `domain/*.md`, `kb-domains.sh match`.
- **Outputs.** A table in the conversation only. No file, no KB write, no metrics log.
- **Sub-agents and models.** None. No `model:`.
- **Hooks and planning files.** Only progress markers. Markers use `Step N` over the order of `##` sections (`pr-review:25`, `pr-review:33`), while the in-file headings are `### Paso 1..4` (`pr-review:87`, `pr-review:109`, `pr-review:120`, `pr-review:144`).
- **Position in flow.** Optional, between `/quality` and `/pre-pr`. `/pre-pr` Fase 2c re-runs the same procedure (`pre-pr:214`), so manual use is redundant.
- **Obsolescence signals.**
  - The intro (`pr-review:6-13`) still tells the reader to "walk each section and mark the items" with italic reviewer quotes; the file has no checklist any more (it is a loader, `pr-review:3`).
  - `pre-pr:3` says `/pre-pr` replaces the `/pr-review` cycle, yet `workflow:279` and the Jandro guide still list it as a step, and `quickref` omits it entirely.
  - `finish-pr` still calls the KB file "the `/pr-review` checklist" (`finish-pr:123`, `finish-pr:143`, `finish-pr:202`, `finish-pr:699`).
  - Paso 3 examples are dd-trace-java specific, labelled as such (`pr-review:129-142`).
  - Marker word `Step` does not match the `Paso` headings, against `conv:15`.

### `pre-pr`

- **Purpose and trigger.** Gate before opening a PR: plan compliance, double review, batch fixes, one commit, draft PR. Commands: `/pre-pr`; `/pre-pr --iteration`; `/pre-pr --iteration <sha | comment-url>` (`pre-pr:35-38`, `pre-pr:596-598`). Never applies fixes without user confirmation (`pre-pr:10-13`).
- **Steps (normal mode).**
  1. Context guard (`pre-pr:42-56`).
  2. Fase 1 snapshot, clean tree, `plan-lock.sh verify` (`pre-pr:60-95`).
  3. Fase 2 load KB and local planning files (`pre-pr:99-118`).
  4. Fase 2b run every `verify:` command, then scope fidelity against `task_plan.md` (`pre-pr:122-208`).
  5. Fase 2c domain invariant check (`pre-pr:212-224`).
  6. Fase 3 and 4 two parallel Opus sub-agents, A (KB rules) and B (adversarial) (`pre-pr:228-247`).
  7. Fase 5 merge findings with the priority filter invariants > project rules > coding rules > adversarial (`pre-pr:251-284`).
  8. Fase 6 apply fixes, `./gradlew spotlessApply` (`pre-pr:288-303`).
  9. Fase 6b update `coding-rules.md` and log (`pre-pr:307-330`).
  10. Fase 6c affected-module Gradle tests, muzzle for instrumentation modules (`pre-pr:334-438`).
  11. Fase 7 one commit `review: pre-PR checks` (`pre-pr:442-461`).
  12. Fase 8 call `/pr-describe` if no PR exists (`pre-pr:465-477`).
  13. Fase 8b `gh pr comment --body "@codex review"`, dd-trace-java only; suggest `/loop 3m watch PR` (`pre-pr:481-506`).
  14. Fase 8c append `decisions.md` to the feature manifest (`pre-pr:510-543`).
  15. Fase 9 optional `arpcli review` (`pre-pr:547-559`).
  16. Fase 10 metrics (`pre-pr:563-588`).
- **Iteration mode.** I-1 scope (last review, SHA or comment, force-push detection), I-2 and I-2c KB, I-3 comment status (informational), I-4 four passes A to D, I-5 merge, I-6 fixes, I-7 coding-rules, I-8 commit `address review comments` and `git push`, I-9 metrics (`pre-pr:592-742`).
- **Inputs.** `git`, `gh` (`pr view`, `api`, `pr comment`), `.claude-invariants.md`, `task_plan.md`, `task_coding_rules.md`, `decisions.md`, `session.md`, KB `pr-review.md`, `domain/`, `plan-lock.sh`, `kb-domains.sh`, Gradle, `arpcli` (internal tool).
- **Outputs.** One commit; draft PR (through `/pr-describe`); `@codex review` comment; `coding-rules.md` rules and exceptions; manifest `## Key decisions` block; lines in `kb:<repo>/pre-pr-metrics.log` and `progress.md`.
- **Sub-agents and models.** `Agent(subagent_type: general-purpose, model: opus)` twice in one message (`pre-pr:230`). Each sub-agent resolves the diff itself (`pre-pr:230`). `quickref:63` still lists "Fases 3+4: Opus" under recommended session model.
- **Hooks and planning files.** `plan-lock.sh verify` at Fase 1; mismatch asks the user, never blocks (`pre-pr:92-95`). Reads `.session-model` (`pre-pr:324-328`). Reads `verify:` lines in `.claude-invariants.md` and `task_plan.md` (`pre-pr:128-145`). Skips scope analysis when `task_plan.md` has no real TODOs (`pre-pr:193`). Marker word `Fase`, including letters (`pre-pr:25`).
- **Position in flow.** After `/quality`; before and including PR creation. Iteration mode replaces the flow after review comments (`pre-pr:594`).
- **Obsolescence signals.**
  - `quickref:58` and the Jandro guide say only Metis and `/implement` spawn real sub-agents and cite a "cannot switch models" note in `pre-pr` Fase 3. The note is not in `pre-pr`; the text exists only in `review-pr:243`. `pre-pr` itself spawns two Opus sub-agents (`pre-pr:230`).
  - `pre-pr:726` points to "Fase 9 of normal mode" for `SESSION_MODEL`; the code is in Fase 10 (`pre-pr:563-572`) and Fase 9 is `arpcli`.
  - Header lists only `--iteration` and `--iteration <comment-url>` (`pre-pr:35-38`), body adds a SHA form (`pre-pr:598`).
  - Iteration pass A to C repeat `/quality` text (`pre-pr:673-691`) and run in one context, unlike the sub-agent design of normal mode (`pre-pr:693-695`).
  - Iteration mode skips plan-lock, acceptance criteria, tests, muzzle and `decisions.md` propagation (`pre-pr:592-742`).
  - `arpcli` (`pre-pr:549-557`) and `@codex review` (`pre-pr:488`) are Datadog-internal or bot-specific.

### `pr-describe`

- **Purpose and trigger.** Generate PR title and body in the dd-trace-java template and the personal style of one author, then create or update the PR. Command `/pr-describe`, no arguments. Normally called by `/pre-pr` Fase 8 (`pre-pr:475`); `workflow:117` also lists it as a manual step.
- **Steps.** Paso 1 context and Jira key from branch or commits, stacked-branch handling (`pr-describe:32-70`); Paso 2 ask for ticket (`pr-describe:74-80`); Paso 3 title rules (`pr-describe:84-112`); Paso 4 body template (`pr-describe:116-170`); Paso 5 publish with option A `gh pr create --draft`, B `gh pr edit`, C markdown (`pr-describe:174-214`); Paso 5b labels (`pr-describe:218-222`); Paso 6 confirm (`pr-describe:224-230`).
- **Inputs.** `git log` and `git diff` against the default branch, branch name, Jira key; `gh`. No MCP.
- **Outputs.** GitHub PR (draft) or edited PR; labels (`type:`, `comp:` or `inst:`); markdown fallback. No KB write, no metrics log.
- **Sub-agents and models.** None.
- **Hooks and planning files.** Progress markers only (`Paso`).
- **Position in flow.** Invoked from `/pre-pr` Fase 8, after the commit. Next: Fase 8b (`@codex review`), reviewer loop. Reminder to run `/update-agents-md` is printed here (`pr-describe:214`).
- **Obsolescence signals.**
  - Hard-coded to `DataDog/dd-trace-java` and one author's style (`pr-describe:3`, `pr-describe:86-112`, `pr-describe:118-145`). `quickref:28` records the libddwaf-java failure but the skill still applies the template to any repo, and `pre-pr:475` calls it for any repo.
  - No push step before `gh pr create` (`pr-describe:178-184`); the normal flow of `pre-pr` has no `git push` either (only `pre-pr:719`).
  - Option B replaces the full body (`pr-describe:191-194`), including manual edits.
  - Paso 5b has no step number in the progress sequence and comes after the "final" Paso 5 text.

### `finish-pr`

- **Purpose and trigger.** Close a merged PR: consolidate invariants into the KB, archive session context, update the PR cache, compute review metrics, remove worktree, branch and Jans session. Command `/finish-pr`, no arguments. Works with the worktree already deleted (path B) (`finish-pr:3`).
- **Steps.**
  1. Paso 0 detect repo, stop if cwd is the worktree to delete (`finish-pr:28-71`).
  2. Paso 1 load invariants: path A file, path B PR cache (`finish-pr:75-90`).
  3. Paso 1.5 analyse commits, review comments and `decisions.md`; lists A (invariants) and B (checklist additions) (`finish-pr:94-153`).
  4. Paso 2 classify to Domain KB or PR cache; two user pauses (`finish-pr:157-212`).
  5. Paso 3 write domain KB entries (`finish-pr:216-249`).
  6. Paso 4 copy session files to `prs/pr-N/` (`finish-pr:253-293`).
  7. Paso 5 update `prs/pr-N.md` (`finish-pr:297-334`).
  8. Paso 5.5 final PR description review, optional `gh pr edit` (`finish-pr:338-368`).
  9. Paso 5.6 review metrics and correlation (`finish-pr:372-491`).
  10. Paso 5.7 AGENTS.md reconciliation (`finish-pr:495-512`).
  11. Paso 5.8 feature manifest update (`finish-pr:516-551`).
  12. Paso 6 cleanup with confirmation (`finish-pr:555-591`).
  13. Paso 6.5 kill Claude session and delete Jans session (`finish-pr:595-677`).
  14. Paso 7 summary (`finish-pr:681-728`).
- **Inputs.** `.claude-invariants.md`, `task_coding_rules.md`, `progress.md`, `findings.md`, `decisions.md`, `.session-model`, `session.md`; `gh api` (reviews, comments); KB `pr-review.md`, `_common/pr-review.md`, `pre-pr-metrics.log`, `quality-metrics.log`; `~/.claude/sessions/*.json`; `~/.jans/state.json`; `jans-ctl`.
- **Outputs.** KB domain entries; `kb:<repo>/prs/pr-N/{invariants,coding-rules,progress,findings,decisions}.md`; `prs/pr-N-invariants.md`; `prs/pr-N.md`; additions to `kb:<repo>/pr-review.md`; manifest `## Closed PRs` row; `finish-pr-metrics.log`; optional PR description edit; deleted worktree, local branch, Claude session file, Jans session.
- **Sub-agents and models.** None. Asks the user for the implementation model only when `.session-model` is absent (`finish-pr:435-445`).
- **Hooks and planning files.** Copies the planning files before the worktree disappears (`finish-pr:261-278`). Reads `.session-model` (`finish-pr:431`) and `session.md` `feature:` (`finish-pr:527`). Depends on the Jans CLI timeout of 5 s (`commands.py:8`, `commands.py:23`, documented at `finish-pr:672-677`).
- **Position in flow.** Last step (Phase 6), after merge. Before: `/update-agents-md` (suggested again at `finish-pr:505-510`).
- **Obsolescence signals.**
  - Says no skill reads `prs/pr-N-invariants.md` (`finish-pr:290`, `finish-pr:726-727`, `workflow:147`), but Paso 1 uses it as the "already processed" flag (`finish-pr:85-88`).
  - New domain entries use a frontmatter template without `description`, `source_files` or `stability` (`finish-pr:226-236`), unlike `pre-code:1328-1340`.
  - Paso 5.5 edits the description of an already merged PR (`finish-pr:338-368`); little value after merge.
  - Eight responsibilities in one 737-line skill; Paso 5.7 and 5.8 are skipped on path B (`finish-pr:497`, `finish-pr:518`), contradicting the "works without the worktree" promise.
  - Spanish body.

### `update-agents-md`

- **Purpose and trigger.** Analyse the PR diff, apply a three-question filter ("Santi's filter"), then create or update `AGENTS.md` files, add code comments, or propose tests. Command `/update-agents-md`, no arguments. Intended while the PR is still open (`quickref:51`, `pr-describe:214`).
- **Steps.** Paso 0 context (`update-agents-md:30-46`); Paso 1 diff and existing AGENTS.md (`update-agents-md:50-73`); Paso 2 candidates (`update-agents-md:77-92`); Paso 3 filter, lists A and B (`update-agents-md:96-117`); Paso 4 destination in the tree (`update-agents-md:121-137`); Paso 5 proposal and pause (`update-agents-md:141-167`); Paso 6 write AGENTS.md (`update-agents-md:171-197`); Paso 6.5 inline code comments (`update-agents-md:201-207`); Paso 7 summary (`update-agents-md:211-228`).
- **Inputs.** `git diff`, `gh pr view`, existing `AGENTS.md` files up to two levels up, optional `kb:<repo>/prs/pr-N.md`.
- **Outputs.** `AGENTS.md` files and Java comments in the working tree. No commit, no push, no log.
- **Sub-agents and models.** None.
- **Hooks and planning files.** Progress markers only (`Paso`).
- **Position in flow.** Phase 5, between PR creation and merge. After: commit and push by hand, then `/finish-pr`, which marks the invariants as `documented_in_repo` (`finish-pr:503`).
- **Obsolescence signals.**
  - The PR cache source is a dead path by the skill's own note ("normally absent", `update-agents-md:64`, `update-agents-md:71`).
  - The filter text is duplicated in `pre-code:664-666`, `finish-pr:163-167` and here (`update-agents-md:100-104`).
  - dd-trace-java filters: directory regex (`update-agents-md:59`) and Java comments (`update-agents-md:203-207`).
  - Not part of any `workflow` phase table (only `workflow:283`); not in the Jans scaffold.
  - Spanish body.

### `pr-deep-review`

- **Purpose and trigger.** Interactive, file-by-file walkthrough of the own PR before opening it. Command `/pr-deep-review`, no arguments (`pr-deep-review:6-14`). `workflow:109` and `workflow:280` position it before `/pre-pr` for complex changes.
- **Steps.** Context guard (`pr-deep-review:38-54`); Paso 1 context and commit hygiene (`pr-deep-review:58-87`); Paso 2 review order (`pr-deep-review:91-100`); Paso 3 per file: presentation, annotated diff, checklist, verdict LGTM/SUGERENCIA/ATENCION, mandatory pause (`pr-deep-review:104-154`); Paso 4 summary and last-minute checklist (`pr-deep-review:158-181`).
- **Inputs.** `git diff`, `git log`, commit bodies (`co-authored-by` grep, `pr-deep-review:78`).
- **Outputs.** Conversation only. No file, no KB write, no log.
- **Sub-agents and models.** None. The whole diff stays in the main context (`pr-deep-review:119`).
- **Hooks and planning files.** Progress markers only (`Paso`).
- **Position in flow.** Optional, after `/quality`, before `/pre-pr`.
- **Obsolescence signals.**
  - Refers to "the smola/manuel checklist" (`pr-deep-review:12`, `pr-deep-review:144`) but never loads one; no KB or invariants read in the whole file.
  - Overlaps `/pre-pr` (adversarial pass) and `/review-pr` deep mode (`pr-deep-review:53`); `workflow:109` calls it "still available".
  - Java specifics: `AgentScope`, spotless, star imports (`pr-deep-review:132-136`, `pr-deep-review:177`).
  - Absent from `quickref`; absent from the Jans scaffold.
  - Spanish body.

### `codex-review`

- **Purpose and trigger.** Interactive review of the current branch by the Codex MCP, "like `@codex review` on GitHub". Command `/codex-review [extra context]`; scope is always `origin/$DEFAULT_BRANCH..HEAD` (`codex-review:6-10`).
- **Steps.** Context guard (`codex-review:55-74`); Paso 1 collect branch, commits, files (`codex-review:78-94`); Paso 2 build prompt (`codex-review:98-115`); Paso 3 call the MCP (`codex-review:119-127`); Paso 4 present results and ask before applying (`codex-review:131-139`).
- **Inputs.** `git`; Codex MCP with mandatory `cwd`, `sandbox: read-only`, `approval-policy: never`, `model: gpt-5.6-sol`, `config: {model_reasoning_effort: xhigh, personality: pragmatic}` (`codex-review:32-41`). Needs Codex CLI >= 0.147.0 from npm (`codex-review:43`). Auth is the corporate SSO (`codex-review:47-51`).
- **Outputs.** Conversation only. No metrics.
- **Sub-agents and models.** External model `gpt-5.6-sol`, not a Claude model.
- **Hooks and planning files.** Progress markers only (`Paso`).
- **Position in flow.** Optional, before the PR (Phase 3) or during the review loop (`workflow:129`). Redundant after `/pre-pr` Fase 8b (`codex-review:10`).
- **Obsolescence signals.**
  - Prompt text says "compared to master/main" (`codex-review:107`) while the scope uses the resolved default branch (`codex-review:85`).
  - Three Codex entry points exist: `/quality` Pass X (`quality:154`), `/pre-pr` Fase 8b (`pre-pr:488`) and this skill, with no shared log; only `/quality` logs `codex-*` counters (`quality:385-391`).
  - Pinned model id and CLI version (`codex-review:40`, `codex-review:43`); a Homebrew install silently breaks it.
  - Failure handling treats any empty result as a timeout (`codex-review:47-51`, `codex-review:139`); there is no branch for "MCP server not connected" (context only: the `codex` MCP server failed with `CONNECTION_CLOSED` in the analysis session; no execution record shows how the skill reacted).
  - Spanish body.

## Interactions with the other layers

### Jans app

| Interaction | Evidence |
|-------------|----------|
| Jans reads the last line of `progress.md` starting with `[`; `done` (without an arrow) renders green, `next →` blue, anything else grey | `gui.py:294-312` |
| Jans scaffolds `session.md`, `progress.md`, `task_plan.md` (reference phases, no checkboxes) for new sessions; `/pre-code` appends TODOs under `## Phases` | `gui.py:225-251`, `gui.py:266-291`, `pre-code:1114` |
| The scaffold's task phases are 0 to 6 and mention only `/pre-code`, `/quality`, `/pre-pr`, `/pr-describe`, `/finish-pr` | `gui.py:284-290` |
| `/finish-pr` removes the Jans session by `jans-ctl delete`, which fails in 5 s when the GUI is off and leaves a stale `state.json` entry | `finish-pr:649-668`, `commands.py:8`, `commands.py:23` |
| `/finish-pr` also SIGTERMs the Claude process found in `~/.claude/sessions/*.json` for the same cwd | `finish-pr:599-640` |
| Marker word differs per skill (`Step`, `Paso`, `Fase`); Jans parser ignores it | `conv:15`, `conv:28` |

Metric lines are also appended to `progress.md` (`quality:397-400`, `pre-pr:329`, `pre-pr:581`). When the metric line is the last line, Jans shows it as a grey subtitle.

### Hooks

| Hook behaviour | Skills affected | Evidence |
|----------------|-----------------|----------|
| Plan injection, the `.session-model` stamp and the three-strikes gate are no-ops without `task_plan.md`. The executing marker (written on pretool, removed on posttool and stop) is handled before that check, for every session; Jans status detection reads it | All task skills; `/pre-code` must create `task_plan.md` before the plan features matter | `inject-plan.sh:13-31` (marker), `inject-plan.sh:34-36` (exit) |
| `UserPromptSubmit` injects `task_plan.md` (200 lines), `task_coding_rules.md`, progress/decisions tails | `pre-code` output size limits | `inject-plan.sh:91-96`, `pre-code:1078`, `pre-code:1118` |
| `PreToolUse` emits `Current pending TODO: <first unchecked box>` and enforces the three-strikes gate | `implement` | `inject-plan.sh:208-216`, `implement:145-185` |
| `.session-model` stamped with `<model> effort:<effort>` on first run; `/pre-code` overwrites with a bare label | `pre-code`, `implement`, `quality`, `pre-pr`, `finish-pr` | `inject-plan.sh:39-46`, `pre-code:1262`, `quality:375-381`, `pre-pr:324-328`, `finish-pr:431` |
| `plan-lock.sh lock` at end of Paso 5.5; `verify` at `/pre-pr` Fase 1; checkbox state normalised | `pre-code`, `pre-pr`, `quality` (side effect) | `pre-code:1217`, `pre-pr:92`, `plan-lock.sh:24-26`, `quality:309-311` |
| `PostToolUse` reminder is emitted only if `progress.md` exists | All skills that write progress | `inject-plan.sh:224-228` |
| `notepad-write-guard.sh` blocks `Write` on existing `decisions.md` and `progress.md` | `implement` (uses Edit), `pre-code` | `implement:352-358`, `pre-code:102` |

### Knowledge base

| Skill | Reads | Writes |
|-------|-------|--------|
| `pre-code` | `_common/pr-review.md`, `<repo>/pr-review.md`, `coding-rules.md`, `domain/*`, `prs/*`, `research/*`, `_meta/features/*` (`pre-code:245-418`) | `<repo>/domain/*.md` or flat entries (`pre-code:1282-1346`) |
| `implement` | none | none |
| `quality` | `coding-rules.md`, `pr-review.md` head (`quality:74-75`) | `coding-rules.md`, `quality-metrics.log` |
| `pr-review` | `_common/pr-review.md`, `<repo>/pr-review.md`, `domain/*` via `kb-domains.sh match` | none |
| `pre-pr` | `pr-review.md`, `domain/*` | `coding-rules.md`, `pre-pr-metrics.log`, `_meta/features/<id>.md` (`pre-pr:510-543`) |
| `pr-describe` | none | none |
| `finish-pr` | `pr-review.md`, `prs/*`, metrics logs | `domain/*`, `prs/pr-N/*`, `prs/pr-N.md`, `pr-review.md`, `finish-pr-metrics.log`, `_meta/features/<id>.md` |
| `update-agents-md` | `prs/pr-N.md` (usually absent) | none (writes into the repo) |
| `pr-deep-review`, `codex-review` | none | none |

Unified metric logs: `quality-metrics.log`, `pre-pr-metrics.log`, `finish-pr-metrics.log` per repo. `pr-review`, `pr-describe`, `update-agents-md`, `pr-deep-review`, `codex-review` and `pre-code` leave no metric line.

Observed log shape (2026-10-02). Counted with `grep -n 'pr: none'` on `kb:<repo>/quality-metrics.log`: `dd-trace-java` lines 1-3, 5-10, 12-18, 20-23 (20 of 23); `agentic-onboarding-evals` lines 1 and 3 (2 of 3); `system-tests` line 1 (1 of 1); `dd-source` none (0 of 1). Total 23 of 28. These are records, not closed PRs: whether each later reached `/finish-pr` and lost its join is not measured. For `pre-pr-metrics.log`: `kb:dd-trace-java/pre-pr-metrics.log` and other repo logs mix full lines with `[pre-pr] coding-rules | pr: ...` lines, and other repos hold ad-hoc fields such as `status: draft-opened` or `pr: TBD`.

### Language and portability

Skill body language (`conv:121-131`): Spanish in `pre-code`, `pre-pr`, `finish-pr`, `pr-describe`, `pr-review`, `codex-review`, `pr-deep-review`, `update-agents-md`; English in `quality`, `implement`. The policy (`conv:63`) says skill content must be English.

## Findings

Types: `obsolete`, `drift` (doc says X, code does Y), `defect`, `performance`, `claude-specific`.

| type | item | evidence (file:line) | impact |
|------|------|----------------------|--------|
| defect | `/quality` usually runs before the PR exists, so its metric line has `pr: none`; `/finish-pr` greps `\| pr: {number} \|`, which a `pr: none` line cannot match | `quality:370-372`, `quality:385`, `finish-pr:465-467`; `kb:dd-trace-java/quality-metrics.log:1-3,5-10,12-18,20-23` (20 of 23), `kb:agentic-onboarding-evals/quality-metrics.log:1,3` (2 of 3), `kb:system-tests/quality-metrics.log:1` (1 of 1), `kb:dd-source/quality-metrics.log` (0 of 1): 23 of 28 lines; the join itself was not run | Predicted, not measured: a PR whose quality run was logged before PR creation has no quality part in the catch rate (`finish-pr:474-484`), which would bias the "trend signal" (`finish-pr:486-488`) |
| defect | `/finish-pr` allows "continue" inside the worktree to delete, then Paso 6.5 SIGTERMs the Claude process whose session file has that cwd, which is the running session | `finish-pr:47-62`, `finish-pr:599-640` | Static reading, no archived run: the session would end before the Paso 7 summary and the `done` marker |
| defect | New KB entries from `/finish-pr` have no `description`, `source_files` or `stability` | `finish-pr:226-236`, `pre-code:1328-1340`, `kb-domains.sh:250-253`, `kb-domains.sh:266-281` | Entries print "no description", land in UNMATCHABLE and are not auto-selected by `kb-domains.sh match` in `/pr-review` and `/pre-pr`. `pr-review:107` does load UNMATCHABLE entries by manual judgment, but with "no description" that judgment has little to go on |
| defect | `/pre-pr --iteration` with no argument documents "last CHANGES_REQUESTED" but the query takes the last review of any state | `pre-pr:597`, `pre-pr:606-609`, `quickref:9` | Scope anchor can be an approval or a comment; the iteration may miss earlier requested changes |
| defect | `gh api` calls without `--paginate` return the first page only | `finish-pr:104-105`, `finish-pr:380-389` | On PRs with more than 30 review comments the invariants list and review metrics undercount |
| defect | `pre-pr` Fase 6b writes `pr: {number}` before the PR exists (Fase 8) and uses a different line format from Fase 10 in the same log | `pre-pr:328`, `pre-pr:465-477`, `pre-pr:575`; log lines `[pre-pr] coding-rules \| pr: none` | Two schemas in `pre-pr-metrics.log`; the 6b line cannot be joined to a PR |
| defect | Normal flow has no `git push` before `gh pr create` | `pre-pr:442-477`, `pr-describe:178-184`, only push at `pre-pr:719` | `gh pr create` needs a pushed branch; first PR creation fails or prompts, depending on the shell |
| drift | `pre-code` Paso 4.9 requires a draft checklist as Metis input, but no earlier step produces one | `pre-code:714`, `pre-code:642-704`, `pre-code:833`, `pre-code:837-839` | Static reading only, no runtime evidence: the model may build a draft ad hoc; if it does not, the `FAKE_CRITERION` check (`pre-code:733`) has nothing to review |
| defect | `update-agents-md` uses `{REPO_NAME}` but Paso 0 defines only `{REPO_SLUG}` | `update-agents-md:43`, `update-agents-md:64` | PR cache path is built from an undefined placeholder (low, the path is usually absent) |
| defect | `codex-review` has no branch for a Codex MCP that is not connected; a missing-error branch: empty output is always called a timeout | `codex-review:47-51`, `codex-review:139`, `quality:170-172` | Risk, no execution record: with the MCP server down, the written path would label it a timeout and suggest a retry; `/quality` Pass X is "always on", so every run reaches this path |
| defect | `/finish-pr` ranges use `origin/{DEFAULT_BRANCH}..HEAD` with no fetch; after a merge-commit merge and a fetch the range is empty | `finish-pr:101`, `finish-pr:417`, `finish-pr:500` | Commit analysis, `fix_commits` and AGENTS.md detection return nothing for that merge style |
| drift | `/quality` is "sequential, independent" in the skill but "in parallel" in two guides; no sub-agents exist, so independence is by prompt only | `quality:3`, `quality:86`, `quickref:25`, `workflow:88` | Readers expect parallel cost and isolation that do not exist |
| drift | Guides say only Metis and `/implement` spawn real sub-agents and cite a "cannot switch" note in `pre-pr`; `pre-pr` spawns two Opus sub-agents and has no such note | `quickref:58`, `quickref:63`, `pre-pr:230`, `review-pr:243` | Cost model is wrong: each `/pre-pr` pays two Opus runs over the whole diff regardless of the session model |
| drift | Flow order differs in `workflow`, `quickref` and the Jans scaffold; `/pr-review` and `/pr-deep-review` are missing from `quickref`; `/pr-describe` is shown as a separate step but `/pre-pr` calls it | `workflow:279-283`, `quickref:5-16`, `gui.py:284-290`, `pre-pr:475` | A reader following `quickref` runs `/pr-describe` twice and never meets two skills |
| drift | `/finish-pr` and `workflow` say no skill reads `pr-N-invariants.md`; `/finish-pr` Paso 1 does | `finish-pr:85-88`, `finish-pr:290`, `workflow:147` | Removing the "convenience copy" breaks idempotence detection |
| drift | `workflow` says checklist "sections 1-17"; the KB file has section 18 and later | `workflow:101`, `kb:dd-trace-java/pr-review.md:430` | Stale count; low |
| drift | Review-round commit message differs | `workflow:132`, `pre-pr:718` | Inconsistent history; low |
| drift | `pre-pr` Fase 10 cross-reference points to a Fase 9 that is `arpcli` | `pre-pr:726`, `pre-pr:547`, `pre-pr:563-572` | Stale reference after renumbering |
| drift | `implement:427` says `/pre-pr` runs the full test suite; it runs affected Gradle modules and nothing without Gradle | `implement:427`, `pre-pr:334-363`, `pre-pr:382-385` | No step runs the full suite; teams may believe it is covered |
| drift | `/update-agents-md` is "before merge" in guides, but `finish-pr` suggests it after merge, when the change cannot ship with the PR | `quickref:51`, `finish-pr:505-510` | Suggestion at the wrong time; also the skill never commits (`update-agents-md:171-228`) |
| drift | `--iteration` header omits the SHA form; iteration mode skips tests, muzzle, plan-lock and Fase 8c, and Fase I-8 shows `git commit` and `git push` with no local confirmation text | `pre-pr:35-38`, `pre-pr:598`, `pre-pr:592-742`, `pre-pr:10-13`, `pre-pr:719` | The general rule at `pre-pr:10-13` may still apply to the push; the risk is the missing local reminder and that review fixes reach the remote without the checks of the first round |
| drift | `/pr-describe` is repo-specific but is called by `/pre-pr` for every repo | `pr-describe:3`, `pr-describe:118-145`, `pre-pr:475`, `quickref:28` | Wrong PR body on non-dd-trace-java repos (libddwaf-java case) |
| drift | `pr-deep-review` refers to a checklist it never loads | `pr-deep-review:12`, `pr-deep-review:144` | Verdicts rely on model memory; results differ from `/pre-pr` |
| drift | `codex-review` prompt hard-codes `master/main` | `codex-review:107`, `codex-review:85` | Wrong comparison base in prompt for other default branches |
| drift | `DEFAULT_BRANCH` falls back to `master` in many places; `update-agents-md` notes `origin/HEAD` may be unset in Jans worktrees | `update-agents-md:44`, `pre-code:61`, `pre-code:171`, `pre-pr:71`, `quality:58`, `pr-describe:42`, `codex-review:85`, `pr-deep-review:65`, `pr-review:66` | When `origin/HEAD` is unset, repos whose default is `main` (this one) diff against a missing `origin/master` |
| drift | Marker word does not match the heading word in `pr-review` | `pr-review:25`, `pr-review:33`, `pr-review:87`, `conv:15` | Violates the convention; low |
| drift | Eight skill bodies are Spanish despite the English policy | `pre-code:3`, `pre-pr:3`, `finish-pr:3`, `pr-describe:3`, `pr-review:6`, `codex-review:6`, `pr-deep-review:6`, `update-agents-md:6`, `conv:63`, `conv:121-131` | Blocks marketplace publication and tool migration without translation |
| drift | Same context guard copied in five skills and the Santi filter in three | `quality:37-40`, `pr-review:46-49`, `codex-review:62-65`, `pr-deep-review:47-50`, `pre-pr:49-52`, `pre-code:664-666`, `finish-pr:163-167`, `update-agents-md:100-104` | Edits must be repeated; divergence is likely |
| drift | Codex parameters live in three skills | `codex-review:40-41`, `quality:156-163`, `review-pr:453` | A model or CLI upgrade needs three edits; `quality` says "same as codex-review" by prose only |
| obsolete | `pr-review` intro describes a checklist and reviewer quotes that no longer exist | `pr-review:6-13`, `pr-review:3` | Misleads readers about what the skill does |
| obsolete | `/implement` branch for a missing `.session-model` cannot run while hooks are on | `implement:107-117`, `inject-plan.sh:42-46` | Dead code; users never see the prompt |
| obsolete | `Commit:`, `Blocks:`, `Blocked-by:` sub-bullets are generated but not enforced by any step | `pre-code:1143-1144`, `implement:191-203`, `inject-plan.sh:208` | The agent still receives them as context, so keep them in any migration; only mechanical enforcement (commit step, dependency order) is missing |
| obsolete | `pre-code` model menu has fixed version labels that `/implement` reduces to a family | `pre-code:1248-1251`, `implement:80-88` | Labels go stale at each model release; `haiku` and `fable` are missing |
| obsolete | `finish-pr` Paso 5.5 edits the description of a merged PR | `finish-pr:338-368` | Low value after merge; extra interaction |
| obsolete | `update-agents-md` reads a PR cache file that does not exist before merge | `update-agents-md:64`, `update-agents-md:71` | Dead input |
| obsolete | `/pr-review`, `/pr-deep-review`, `/codex-review` overlap `/pre-pr` and `/quality` Pass X | `pre-pr:3`, `pre-pr:214`, `quality:154`, `workflow:109` | Four review mechanisms for one diff; candidates for merge or removal |
| performance | `/quality` always runs Codex at `xhigh` effort, in every invocation, with no light mode; a lost connection can hang (`codex-review:45`) | `quality:154`, `quality:156-163`, `codex-review:45` | Slow runs on small diffs; stacks with `/pre-pr` Fase 8b and `/codex-review` |
| performance | Two full-diff Opus sub-agents in every `/pre-pr`; iteration repeats four passes | `pre-pr:230`, `pre-pr:671-695` | High token cost per round |
| performance | `/implement` re-sends the full invariants and rules to a new agent for each TODO | `implement:219-225` | Cost grows with TODO count and invariants size; no caching |
| performance | `/pre-code` runs up to 5 Explore agents plus an Opus review and `ultrathink`; no cap for large KBs | `pre-code:473-637`, `pre-code:644`, `pre-code:718`, `pre-code:1353` | 10 to 20 minutes and high cost per task; mitigated only by KB hits |
| performance | `/pr-deep-review` forces one turn per file and keeps the full diff in the main context | `pr-deep-review:146-154`, `pr-deep-review:187-191` | N turns for N files; context grows |
| performance | `/finish-pr` makes many `gh api` calls and three confirmations | `finish-pr:96-111`, `finish-pr:372-392`, `finish-pr:181-212` | Long closing step; much of it is metrics |
| claude-specific | `ultrathink` keyword | `pre-code:644`, `pre-pr:669`, `pr-review:122` | No effect on other tools; reasoning depth lost |
| claude-specific | `Agent(...)` with `Explore`, `general-purpose` and `model:` argument | `pre-code:439`, `pre-code:718`, `implement:256-261`, `pre-pr:230` | Needs a sub-agent API with model selection |
| claude-specific | `LSP` tool and `jdtls-lsp` plugin | `pre-code:467`, `quality:88` | Java navigation depends on that plugin |
| claude-specific | Glob/Read used instead of Bash to avoid the pretool BLOCKED gate | `implement:46-48`, `implement:123-126` | Skill logic shaped by hook internals |
| claude-specific | Hooks inject planning files; `.session-model` read from `settings.json` | `inject-plan.sh:39-46`, `pre-code:1118`, `pre-code:1259` | Planning-file model needs another injection mechanism |
| claude-specific | `~/.claude/sessions/*.json` with `cwd` and `pid`, plus SIGTERM | `finish-pr:599-640` | Relies on undocumented Claude Code files |
| claude-specific | Slash commands, `/loop`, `/rewind`, `/btw` | `pre-pr:497-506`, `conv:39-57` | Command surface is Claude Code only |
| claude-specific | Google Workspace and Datadog MCP, Codex MCP with pinned model | `pre-code:150-155`, `pre-code:283-297`, `codex-review:32-45` | Each MCP needs an equivalent; Google Workspace needs OAuth in headless runs |
| claude-specific | BSD `sed -i ''`, macOS-only | `implement:294-296` | Fails on Linux |
| claude-specific | Jans coupling (`jans-ctl delete`, `state.json`, progress parser) | `finish-pr:644-668`, `gui.py:294-312` | Skills cannot run standalone without losing the status and cleanup features |
