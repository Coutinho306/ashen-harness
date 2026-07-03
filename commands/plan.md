---
description: Plan a feature via ashen-specifier + ashen-planner; outputs SPEC.md + PLAN.md
model: claude-opus-4-8
argument-hint: "<slug | topic>"
delegates-to: [ashen-specifier, ashen-planner, ashen-code-cleaner]
---

You are the `/plan` router. Spec and plan only — no code changes, no commits.

Topic/slug: $ARGUMENTS

## Step 1 — Pre-fetch + bootstrap

If `$ARGUMENTS` is empty: use `AskUserQuestion` to ask for the topic/feature to plan before continuing.

Resolve slug: if arg is already kebab-case with no spaces, use as-is; else convert to kebab-case (lowercase, spaces→hyphens, strip punctuation).

**Resolve slug directory** (run this shell logic; store result in `$dir`):
```bash
dir=$(ls -d specs/features/[0-9][0-9][0-9][0-9]-<slug> \
              specs/features/<slug> 2>/dev/null | head -1)
```
First match wins (numbered-active → bare-active). If nothing found, this is a new slug — compute the next sequence number and bootstrap:
```bash
_fp="specs/features"
next=$(printf '%04d' $(( $(ls -d ${_fp}/[0-9][0-9][0-9][0-9]-* \
                                 ${_fp}/done/[0-9][0-9][0-9][0-9]-* 2>/dev/null \
                            | sed -E 's#.*/([0-9]{4})-.*#\1#' \
                            | sort -n | tail -1 | sed 's/^0*//' | grep -E '.' || echo 0) + 1 )))
dir="specs/features/${next}-<slug>"
```
The zero-pad width is 4 (`%04d`). With no existing numbered dirs anywhere, `next=0001`. The scan for next-number includes the archived subtree (via `${_fp}/done/`) to avoid collisions — but the resolved `$dir` for an in-flight slug always points into the active `specs/features/` tree.

Run these probes in parallel:
- `cat specs/spikes/<slug>/SPIKE.md 2>/dev/null` → capture as `spike_content` (empty string if absent)
- Read `$dir/STATUS.md` if exists → check if resumable
- `ls pyproject.toml dbt_project.yml *.tf Dockerfile 2>/dev/null`
- `grep -rl "langgraph\|langchain\|openai\|anthropic\|llm\|embed" . --include="*.py" --exclude-dir=".venv" 2>/dev/null | head -5`

Compute `source_hash = sha256(topic + spike_content)` (first 8 chars for display).

STATUS.md logic:
- If STATUS exists and `overall_status: done` → report "already done" + paths and stop.
- If STATUS exists and `overall_status: in_progress` and hash matches → resume from first unchecked step.
- Else → bootstrap `$dir/STATUS.md` from template at `${CLAUDE_PLUGIN_ROOT}/templates/STATUS.md`:
  - `slug`: resolved slug (bare kebab, no numeric prefix)
  - `command`: plan
  - `overall_status`: in_progress
  - `last_updated`: now (YYYY-MM-DD HH:MM)
  - `source_hash`: computed hash
  - Steps: 1. Pre-fetch + bootstrap / 2. Specifier → SPEC.md / 3. Checkpoint / 4. Planner → PLAN.md

Create `$dir/` directory if absent.

Mark Step 1 `[x]` in STATUS.md.

## Step 2 — Delegate ashen-specifier

Emit routing block:
```
📍 plan router — specifier
   slug:    <slug>
   spike:   <specs/spikes/<slug>/SPIKE.md | none>
   target:  $dir/SPEC.md
   hash:    <first 8 chars>
```

Call Agent with subagent_type `ashen-specifier`. Prompt (≤ 1500 chars):

```
Slug: <slug>
Target path: $dir/SPEC.md
SPIKE path: <specs/spikes/<slug>/SPIKE.md | none>
CWD hints (files present): <comma-separated list from probe>

Author SPEC.md at the target path. If SPIKE path is provided, read it as auxiliary context (background + recommended approach) — but author SPEC from your understanding and AskUserQuestion responses, not SPIKE prose verbatim. Set domain (ask user if can't infer from cwd hints or topic). Return: path + frontmatter summary.
```

Verify `$dir/SPEC.md` exists after agent returns. If missing but content returned inline, write it manually.

Mark Step 2 `[x]` in STATUS.md. Update `last_updated`.

Print SPEC summary:
```
📄 SPEC written: $dir/SPEC.md
   <frontmatter summary from specifier>
```

## Step 3 — Human checkpoint

```
AskUserQuestion:
  question: "SPEC is ready. Proceed to planning phase?"
  options: [yes — continue to planner, edit-spec-first — I'll edit and re-run /plan, abort — stop here]
```

- `yes` → continue.
- `edit-spec-first` → update STATUS note: "user wants to edit SPEC before planning". Set `overall_status: in_progress`. Print: "Edit `$dir/SPEC.md` then re-run `/plan <slug>`. STATUS will resume from planner step." Stop.
- `abort` → mark STATUS `overall_status: done`, note "aborted at checkpoint". Stop.

Mark Step 3 `[x]` in STATUS.md.

## Step 4 — Delegate ashen-planner

Emit routing block:
```
📍 plan router — planner
   spec:    $dir/SPEC.md
   target:  $dir/PLAN.md
```

Call Agent with subagent_type `ashen-planner`. Prompt (≤ 1500 chars):

```
Spec path: $dir/SPEC.md
Target path: $dir/PLAN.md
CWD hints (files present): <comma-separated list from Step 1 probe>

Read SPEC.md fully. Produce PLAN.md at target path with dependency-ordered phases (each phase independently verifiable). Include task IDs (T1.1, T1.2, ...) and validation criteria per phase. Return: path + phase count + summary.
```

Verify `$dir/PLAN.md` exists. If missing but content returned inline, write it manually.

Mark Step 4 `[x]` in STATUS.md. Set `overall_status: done`. Update `last_updated`.

Print final report:
```
✅ PLAN complete
   SPEC:  $dir/SPEC.md
   PLAN:  $dir/PLAN.md
   <phase count + summary from planner>

Next: /task <slug>
```

## Rules
- No feature code. No commits. No installs.
- Only write to `$dir/` and its STATUS.md.
- SPIKE.md is auxiliary context — specifier does not copy it verbatim.
- Resume from first unchecked step when STATUS exists and hash matches.
- `ashen-code-cleaner` is available for advisory code-quality review during planning if the specifier or planner needs it.
- The `slug:` field in STATUS.md frontmatter is always the bare kebab slug (no numeric prefix). The number lives only in the directory path.
- `/plan` does NOT move the feature directory on completion — feature archival happens only at `/task` finalize.
