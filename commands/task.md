---
description: Execute a SPEC via domain-routed builder + advisory reviewer; commits, no PRs
model: claude-sonnet-4-6
argument-hint: "<slug>"
delegates-to: [claudinho-data-eng-builder, claudinho-ai-eng-builder, claudinho-infra-ops-builder, claudinho-generalist-builder, claudinho-reviewer]
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
- `data-eng` → `claudinho-data-eng-builder`
- `ai-eng` → `claudinho-ai-eng-builder`
- `infra-ops` → `claudinho-infra-ops-builder`
- `generalist` → `claudinho-generalist-builder`

Compute `input_hash = sha256(spec_body + plan_body)` (first 8 chars).

STATUS.md logic at `specs/features/<slug>/STATUS.md`:
- If done → report "already done" + commits list and stop.
- If in_progress and hash matches → resume from first `[ ]` step.
- Else → bootstrap from template at `${CLAUDE_PLUGIN_ROOT}/templates/STATUS.md`:
  - slug, command=task, overall_status=in_progress, last_updated=now, input_hash
  - Steps: 1. Pre-fetch + route / 2. Build / 3. Review / 4. Finalize

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

## Step 3 — Review (advisory)

Call Agent with subagent_type `claudinho-reviewer`. Prompt (≤ 1500 chars):

```
Spec path: specs/features/<slug>/SPEC.md
Diff ref: HEAD~<commit_count>..HEAD
CWD: <cwd>

Review the implementation against SPEC acceptance criteria. Return structured findings[] grouped by severity (risk/warn/info). Advisory only — never block. Return findings: [] if none.
```

If reviewer delegation fails: log "reviewer unavailable" in STATUS notes and continue.

Receive `findings[]`. Mark Step 3 `[x]` in STATUS.md.

## Step 4 — Finalize

Update `specs/features/<slug>/SPEC.md` frontmatter: set `status: done`.

Append to STATUS.md notes:
```
## Review findings (<date>)
<findings from reviewer, or "none">
```

Mark Step 4 `[x]`. Set `overall_status: done`. Update `last_updated`.

Print final report:
```
✅ task complete
   slug:     <slug>
   commits:  <count> — <list of hash + message>
   files:    <changed_files list>
   findings: <risk: N  warn: N  info: N>

Review notes: specs/features/<slug>/STATUS.md
```

## Rules
- No PRs. No pushes. No `gh pr create` in any form.
- No `Co-Authored-By`, no AI trailers.
- Resume from first `[ ]` step when STATUS exists and hash matches.
- Reviewer findings are notes only — never halt or revert on findings alone.
- If SPEC `status` is already `done`, ask user to confirm re-run before proceeding.
