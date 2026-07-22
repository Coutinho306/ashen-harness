---
description: Execute a SPEC via domain-routed builder + advisory reviewer; commits, no PRs
model: claude-sonnet-4-6
argument-hint: "<slug>"
delegates-to: [ashen-data-eng-builder, ashen-ai-eng-builder, ashen-infra-ops-builder, ashen-generalist-builder, ashen-reviewer, ashen-code-cleaner]
---

You are the `/task` router. Implement a spec via a domain-routed builder, then run advisory review.

Slug: $ARGUMENTS

## Step 1 — Pre-fetch + route

If `$ARGUMENTS` is empty: use `AskUserQuestion` to ask for the slug before continuing.

**Resolve slug directory** (run this shell logic; store result in `$dir`):
```bash
dir=$(ls -d specs/features/[0-9][0-9][0-9][0-9]-<slug> \
              specs/features/<slug> \
              specs/features/done/[0-9][0-9][0-9][0-9]-<slug> \
              specs/features/done/<slug> 2>/dev/null | head -1)
```
First match wins (numbered-active → bare-active → numbered-done → bare-done).

If `$dir` is empty, this is a new slug that has no SPEC yet — try the SPEC fallback search below before concluding it is unplanned.

**SPEC resolution**: Try to read `$dir/SPEC.md`. If `$dir` is empty or `$dir/SPEC.md` is missing, search these fallback locations in order:
1. `specs/features/[0-9][0-9][0-9][0-9]-<slug>/SPEC.md` (numbered active)
2. `specs/features/<slug>/SPEC.md` (bare active)
3. `specs/features/done/[0-9][0-9][0-9][0-9]-<slug>/SPEC.md` (numbered done)
4. `specs/features/done/<slug>/SPEC.md` (bare done)
5. `specs/<slug>.md`
6. `specs/<slug>-*.md` (glob)

If SPEC is found via fallback, update `$dir` to the directory containing that SPEC. If still not found after all fallbacks, stop and report: "SPEC not found for slug <slug> — run /plan <slug> first."

Run these probes in parallel:
- Read `$dir/SPEC.md` — parse YAML frontmatter for `domain`, `status`, `slug`
- `cat $dir/PLAN.md 2>/dev/null` → capture plan_content (empty if absent)
- `cat $dir/STATUS.md 2>/dev/null` → check if resumable

Parse `domain` from SPEC frontmatter (use bash one-liner: `python3 -c "import sys; lines=[l for l in open('$dir/SPEC.md').readlines()]; fm=''.join(lines[1:lines.index('---\n',1)]); exec('import yaml'); print(yaml.safe_load(fm).get('domain',''))" 2>/dev/null || grep "^domain:" $dir/SPEC.md | head -1 | cut -d' ' -f2`).

If `domain` is empty or unset: use `AskUserQuestion` with question "Which domain does this task fall under?" and options `[data-eng, ai-eng, infra-ops, generalist]`. Then update SPEC frontmatter: replace `domain: ` line with the chosen value (use Edit tool).

Route:
- `data-eng` → `ashen-data-eng-builder`
- `ai-eng` → `ashen-ai-eng-builder`
- `infra-ops` → `ashen-infra-ops-builder`
- `generalist` → `ashen-generalist-builder`

Compute `source_hash = sha256(spec_body + plan_body)` (first 8 chars).

STATUS.md logic at `$dir/STATUS.md`:
- If `$dir` is under a `done/` path and STATUS has `overall_status: done`: report "already done" with path `$dir` and commits list, then stop.
- If STATUS exists and `overall_status: done` → report "already done" + commits list and stop.
- If STATUS exists and `overall_status: in_progress` and hash matches → resume from first `[ ]` step.
- Else → bootstrap from template at `${CLAUDE_PLUGIN_ROOT}/templates/STATUS.md`:
  - slug (bare kebab, no numeric prefix), command=task, overall_status=in_progress, last_updated=now, source_hash
  - Steps: 1. Pre-fetch + route / 2. Build / 3. Verify / 4. Review / 5. Finalize
  - **Write this file to `$dir/STATUS.md` immediately** (Write tool), before doing any other Step 1 work. Do not hold STATUS state in memory only — every "Mark Step N `[x]`" instruction below means: Edit `$dir/STATUS.md` on disk right now, not at the end.

If `$dir` is empty (no existing dir and SPEC was found via legacy path), compute next sequence number and set `$dir`:
```bash
_fp="specs/features"
next=$(printf '%04d' $(( $(ls -d ${_fp}/[0-9][0-9][0-9][0-9]-* \
                                 ${_fp}/done/[0-9][0-9][0-9][0-9]-* 2>/dev/null \
                            | sed -E 's#.*/([0-9]{4})-.*#\1#' \
                            | sort -n | tail -1 | sed 's/^0*//' | grep -E '.' || echo 0) + 1 )))
dir="${_fp}/${next}-<slug>"
```
The zero-pad width is 4 (`%04d`). With no existing numbered dirs, `next=0001`.

Emit routing block:
```
📍 task router
   slug:    <slug>
   domain:  <domain>
   builder: <subagent-name>
   spec:    $dir/SPEC.md
   plan:    <$dir/PLAN.md | none>
   hash:    <first 8 chars>
```

Edit `$dir/STATUS.md` now: mark Step 1 `[x]`, update `last_updated`.

## Step 2 — Build

Call Agent with subagent_type `<chosen-builder>`. Prompt (≤ 1500 chars):

```
Spec path: $dir/SPEC.md
Plan path: <$dir/PLAN.md | none>
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

Receive `changed_files[]` and `commits[]`. Edit `$dir/STATUS.md` now: mark Step 2 `[x]`, update `last_updated`.

## Step 3 — Verify

Read `$dir/SPEC.md` and extract the `## Validation` section (everything between `## Validation` and the next `##` heading).

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

Edit `$dir/STATUS.md` now: mark Step 3 `[x]`, update `last_updated`. Verify is unconditional — it always runs regardless of `tier` (computed below) and `tier` never gates Step 3 or Step 5 (Finalize).

## Tier classifier

Compute `tier ∈ {trivial, standard}` from the Step 2 build output, before running Step 4.

- File count: `len(changed_files)` (from Step 2's `changed_files[]`).
- Line count: run `git diff --shortstat HEAD~<commit_count>..HEAD` (same ref Step 4 builds for the reviewer) and parse the `N insertions(+), M deletions(-)` summary into `insertions + deletions`. If either number is absent in the output, treat it as `0`.
- `tier = trivial` iff `len(changed_files) == 1` AND `(insertions + deletions) < 30`. Otherwise `tier = standard`.
- If the `--shortstat` output can't be parsed (empty, no match, command error), default `tier = standard` — fail safe toward running review.

The `1 file / 30 line` threshold is a hardcoded constant, not configurable — do not add a flag or config surface for it.

`tier` only gates Step 4 (Review). It never affects Step 3 (Verify) or Step 5 (Finalize): a trivial change still runs every Validation command and can still produce `verify.status: fail`.

## Step 4 — Review (advisory)

If `tier == trivial`: skip the `ashen-reviewer` Agent call entirely. Set `review = {status: skipped, reason: trivial, files: <len(changed_files)>, lines: <insertions + deletions>}`. Edit `$dir/STATUS.md` now: mark Step 4 `[x]`, update `last_updated`. Continue to Step 5.

If `tier == standard`: call Agent with subagent_type `ashen-reviewer`. Optionally also call `ashen-code-cleaner` for advisory code-quality findings (comment policy, docs gaps, structure smells) — both are advisory and run in parallel if invoked. Prompt for `ashen-reviewer` (≤ 1500 chars):

```
Spec path: $dir/SPEC.md
Diff ref: HEAD~<commit_count>..HEAD
CWD: <cwd>

Review the implementation against SPEC acceptance criteria. Return structured findings[] grouped by severity (risk/warn/info). Advisory only — never block. Return findings: [] if none.
```

If reviewer delegation fails: log "reviewer unavailable" in STATUS notes and continue.

Receive `findings[]`. Set `review = {status: reviewed}`. Edit `$dir/STATUS.md` now: mark Step 4 `[x]`, update `last_updated`.

## Step 5 — Finalize

If `verify.status` is `pass` or `skipped`: update `$dir/SPEC.md` frontmatter, set `status: done`. Set `overall_status: done` in STATUS.md.

Then archive the slug directory to `specs/features/done/`:
```bash
mkdir -p specs/features/done
if git ls-files --error-unmatch "$dir" >/dev/null 2>&1; then
  git mv "$dir" "specs/features/done/$(basename "$dir")"
else
  mv "$dir" "specs/features/done/$(basename "$dir")"
fi
```

If `verify.status` is `fail`: leave SPEC `status` unchanged. Set `overall_status: blocked` in STATUS.md. Do NOT move the directory — leave it active so the user can find and fix it. Append failure detail to STATUS notes:
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
   dir:      specs/features/done/<dirname>
   commits:  <count> — <list of hash + message>
   files:    <changed_files list>
   verify:   <verify.status> (<total> command(s))
   findings: <if review.status == skipped: "skipped (trivial)"; else: "risk: N  warn: N  info: N">

Review notes: specs/features/done/<dirname>/STATUS.md
```

On `verify.status` fail:
```
⚠️ task blocked — verify failed
   slug:     <slug>
   dir:      $dir
   commits:  <count> — <list of hash + message>
   files:    <changed_files list>
   verify:   fail — <failing cmd> (exit <exit>)
   tail:     <tail>
   findings: <if review.status == skipped: "skipped (trivial)"; else: "risk: N  warn: N  info: N">

SPEC status left unchanged. See $dir/STATUS.md
```

## Rules
- No PRs. No pushes. No `gh pr create` in any form.
- No `Co-Authored-By`, no AI trailers.
- Resume from first `[ ]` step when STATUS exists and hash matches.
- Reviewer findings are notes only — never halt or revert on findings alone.
- `tier` gates only Step 4 (Review). Verify (Step 3) and Finalize (Step 5) always run unconditionally.
- If SPEC `status` is already `done`, ask user to confirm re-run before proceeding.
- The `slug:` field in STATUS.md frontmatter is always the bare kebab slug (no numeric prefix). The number lives only in the directory path.
