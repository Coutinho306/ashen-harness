---
description: Execute a SPEC via domain-routed builder + advisory reviewer; commits, no PRs
model: claude-sonnet-4-6
argument-hint: "<slug>"
delegates-to: [ashen-data-eng-builder, ashen-ai-eng-builder, ashen-infra-ops-builder, ashen-generalist-builder, ashen-reviewer]
---

You are the `/task` router. Implement a spec via a domain-routed builder, then run advisory review.

Slug: $ARGUMENTS

## Step 1 — Pre-fetch + route

If `$ARGUMENTS` is empty: use `AskUserQuestion` to ask for the slug before continuing.

Try to read `specs/features/<slug>/SPEC.md`. If missing, try `specs/<slug>.md` and `specs/<slug>-*.md` (glob). If still not found, stop and report: "SPEC not found at specs/features/<slug>/SPEC.md — run /plan <slug> first."

Run these probes in parallel:
- Read `specs/features/<slug>/SPEC.md` — parse YAML frontmatter for `domain`, `status`, `slug`
- `cat specs/features/<slug>/PLAN.md 2>/dev/null` → capture plan_content (empty if absent)
- `cat specs/features/<slug>/STATUS.md 2>/dev/null` → check if resumable

Parse `domain` from SPEC frontmatter (use bash one-liner: `python3 -c "import sys; lines=[l for l in open('specs/features/<slug>/SPEC.md').readlines()]; fm=''.join(lines[1:lines.index('---\n',1)]); exec('import yaml'); print(yaml.safe_load(fm).get('domain',''))" 2>/dev/null || grep "^domain:" specs/features/<slug>/SPEC.md | head -1 | cut -d' ' -f2`).

If `domain` is empty or unset: use `AskUserQuestion` with question "Which domain does this task fall under?" and options `[data-eng, ai-eng, infra-ops, generalist]`. Then update SPEC frontmatter: replace `domain: ` line with the chosen value (use Edit tool).

Route:
- `data-eng` → `ashen-data-eng-builder`
- `ai-eng` → `ashen-ai-eng-builder`
- `infra-ops` → `ashen-infra-ops-builder`
- `generalist` → `ashen-generalist-builder`

Compute `input_hash = sha256(spec_body + plan_body)` (first 8 chars).

STATUS.md logic at `specs/features/<slug>/STATUS.md`:
- If done → report "already done" + commits list and stop.
- If in_progress and hash matches → resume from first `[ ]` step.
- Else → bootstrap from template at `${CLAUDE_PLUGIN_ROOT}/templates/STATUS.md`:
  - slug, command=task, overall_status=in_progress, last_updated=now, input_hash
  - Steps: 1. Pre-fetch + route / 2. Build / 3. Verify / 4. Review / 5. Finalize

Emit routing block:
```
📍 task router
   slug:    <slug>
   domain:  <domain>
   builder: <subagent-name>
   spec:    specs/features/<slug>/SPEC.md
   plan:    <specs/features/<slug>/PLAN.md | none>
   hash:    <first 8 chars>
```

Mark Step 1 `[x]` in STATUS.md.

## Step 2 — Build

Call Agent with subagent_type `<chosen-builder>`. Prompt (≤ 1500 chars):

```
Spec path: specs/features/<slug>/SPEC.md
Plan path: <specs/features/<slug>/PLAN.md | none>
Task IDs: all uncompleted tasks in SPEC
CWD hints: <cwd>

Implement all uncompleted tasks from SPEC.md in order. If PLAN.md present, follow its phase ordering.

Commit contract (mandatory):
- One commit per coherent change — never bulk-commit a whole feature.
- Prefix: feat(<area>): / fix(<area>): / refactor(<area>): etc. — imperative, specific.
- Append (specs/<slug>) to every commit message.
- No Co-Authored-By, no "Generated with", no --author override.
- Never amend, never force-push.
- Python deps: uv add <pkg> — surface every new dep via AskUserQuestion before adding.
- Never pip install.

Return: changed_files[], commits[] (hash + message).
```

If delegation fails, implement inline using Edit/Write/Bash with the same commit contract.

Receive `changed_files[]` and `commits[]`. Mark Step 2 `[x]` in STATUS.md.

## Step 3 — Verify

Read `specs/features/<slug>/SPEC.md` and extract the `## Validation` section (everything between `## Validation` and the next `##` heading).

If the section is missing or contains no fenced shell code blocks: `verify = {status: skipped, commands: [], total: 0}`. Skip to marking Step 3 `[x]`.

Otherwise, extract each fenced shell command — one command per line inside the fenced block — in declared order. For each command, in order:
- Run it via Bash in the repo root.
- Capture the exit code.
- On exit 0: record `{cmd, exit: 0}` (no tail).
- On non-zero exit: record `{cmd, exit, tail: <last ~15 lines of combined output>}`, then stop running further commands.

Compute `verify.status`:
- `pass` if every command ran and exited 0.
- `fail` if any command exited non-zero.
- `skipped` if there were no commands to run.

`verify = {status, commands: [...], total: N}` where `N` is the number of commands declared.

Mark Step 3 `[x]` in STATUS.md. Verify is unconditional — it always runs regardless of `tier` (computed below) and `tier` never gates Step 3 or Step 5 (Finalize).

## Tier classifier

Compute `tier ∈ {trivial, standard}` from the Step 2 build output, before running Step 4.

- File count: `len(changed_files)` (from Step 2's `changed_files[]`).
- Line count: run `git diff --shortstat HEAD~<commit_count>..HEAD` (same ref Step 4 builds for the reviewer) and parse the `N insertions(+), M deletions(-)` summary into `insertions + deletions`. If either number is absent in the output, treat it as `0`.
- `tier = trivial` iff `len(changed_files) == 1` AND `(insertions + deletions) < 30`. Otherwise `tier = standard`.
- If the `--shortstat` output can't be parsed (empty, no match, command error), default `tier = standard` — fail safe toward running review.

The `1 file / 30 line` threshold is a hardcoded constant, not configurable — do not add a flag or config surface for it.

`tier` only gates Step 4 (Review). It never affects Step 3 (Verify) or Step 5 (Finalize): a trivial change still runs every Validation command and can still produce `verify.status: fail`.

## Step 4 — Review (advisory)

If `tier == trivial`: skip the `ashen-reviewer` Agent call entirely. Set `review = {status: skipped, reason: trivial, files: <len(changed_files)>, lines: <insertions + deletions>}`. Mark Step 4 `[x]` in STATUS.md and continue to Step 5.

If `tier == standard`: call Agent with subagent_type `ashen-reviewer`. Prompt (≤ 1500 chars):

```
Spec path: specs/features/<slug>/SPEC.md
Diff ref: HEAD~<commit_count>..HEAD
CWD: <cwd>

Review the implementation against SPEC acceptance criteria. Return structured findings[] grouped by severity (risk/warn/info). Advisory only — never block. Return findings: [] if none.
```

If reviewer delegation fails: log "reviewer unavailable" in STATUS notes and continue.

Receive `findings[]`. Set `review = {status: reviewed}`. Mark Step 4 `[x]` in STATUS.md.

## Step 5 — Finalize

If `verify.status` is `pass` or `skipped`: update `specs/features/<slug>/SPEC.md` frontmatter, set `status: done`. Set `overall_status: done` in STATUS.md.

If `verify.status` is `fail`: leave SPEC `status` unchanged. Set `overall_status: blocked` in STATUS.md. Append failure detail to STATUS notes:
```
## Verify failure (<date>)
status: fail
failing command: <cmd>
exit: <exit>
tail:
<tail>
```

Append to STATUS.md notes:
```
## Review findings (<date>)
<if review.status == skipped: "review: skipped (trivial, <review.files> file(s), <review.lines> lines)">
<else: findings from reviewer, or "none">
```

Mark Step 5 `[x]`. Update `last_updated`.

Print final report. On `verify.status` pass or skipped:
```
✅ task complete
   slug:     <slug>
   commits:  <count> — <list of hash + message>
   files:    <changed_files list>
   verify:   <verify.status> (<total> command(s))
   findings: <if review.status == skipped: "skipped (trivial)"; else: "risk: N  warn: N  info: N">

Review notes: specs/features/<slug>/STATUS.md
```

On `verify.status` fail:
```
⚠️ task blocked — verify failed
   slug:     <slug>
   commits:  <count> — <list of hash + message>
   files:    <changed_files list>
   verify:   fail — <failing cmd> (exit <exit>)
   tail:     <tail>
   findings: <if review.status == skipped: "skipped (trivial)"; else: "risk: N  warn: N  info: N">

SPEC status left unchanged. See specs/features/<slug>/STATUS.md
```

## Rules
- No PRs. No pushes. No `gh pr create` in any form.
- No `Co-Authored-By`, no AI trailers.
- Resume from first `[ ]` step when STATUS exists and hash matches.
- Reviewer findings are notes only — never halt or revert on findings alone.
- `tier` gates only Step 4 (Review). Verify (Step 3) and Finalize (Step 5) always run unconditionally.
- If SPEC `status` is already `done`, ask user to confirm re-run before proceeding.
