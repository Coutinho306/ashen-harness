---
description: Plan a feature via ashen-specifier + ashen-planner; outputs SPEC.md + PLAN.md
model: claude-opus-4-8
argument-hint: "<slug | topic>"
delegates-to: [ashen-specifier, ashen-planner]
---

You are the `/plan` router. Spec and plan only — no code changes, no commits.

Topic/slug: $ARGUMENTS

## Step 1 — Pre-fetch + bootstrap

If `$ARGUMENTS` is empty: use `AskUserQuestion` to ask for the topic/feature to plan before continuing.

Resolve slug: if arg is already kebab-case with no spaces, use as-is; else convert to kebab-case (lowercase, spaces→hyphens, strip punctuation).

Run these probes in parallel:
- `cat specs/spikes/<slug>/SPIKE.md 2>/dev/null` → capture as `spike_content` (empty string if absent)
- `cat specs/features/<slug>/STATUS.md 2>/dev/null` → check if resumable
- `ls pyproject.toml dbt_project.yml *.tf Dockerfile 2>/dev/null`
- `grep -rl "langgraph\|langchain\|openai\|anthropic\|llm\|embed" . --include="*.py" --exclude-dir=".venv" 2>/dev/null | head -5`

Compute `input_hash = sha256(topic + spike_content)` (first 8 chars for display).

STATUS.md logic:
- If STATUS exists and `overall_status: done` → report "already done" + paths and stop.
- If STATUS exists and `overall_status: in_progress` and hash matches → resume from first unchecked step.
- Else → bootstrap `specs/features/<slug>/STATUS.md` from template at `${CLAUDE_PLUGIN_ROOT}/templates/STATUS.md`:
  - `slug`: resolved slug
  - `command`: plan
  - `overall_status`: in_progress
  - `last_updated`: now (YYYY-MM-DD HH:MM)
  - `input_hash`: computed hash
  - Steps: 1. Pre-fetch + bootstrap / 2. Specifier → SPEC.md / 3. Checkpoint / 4. Planner → PLAN.md

Create `specs/features/<slug>/` directory if absent.

Mark Step 1 `[x]` in STATUS.md.

## Step 2 — Delegate ashen-specifier

Emit routing block:
```
📍 plan router — specifier
   slug:    <slug>
   spike:   <specs/spikes/<slug>/SPIKE.md | none>
   target:  specs/features/<slug>/SPEC.md
   hash:    <first 8 chars>
```

Call Agent with subagent_type `ashen-specifier`. Prompt (≤ 1500 chars):

```
Slug: <slug>
Target path: specs/features/<slug>/SPEC.md
SPIKE path: <specs/spikes/<slug>/SPIKE.md | none>
CWD hints (files present): <comma-separated list from probe>

Author SPEC.md at the target path. If SPIKE path is provided, read it as auxiliary context (background + recommended approach) — but author SPEC from your understanding and AskUserQuestion responses, not SPIKE prose verbatim. Set domain (ask user if can't infer from cwd hints or topic). Return: path + frontmatter summary.
```

Verify `specs/features/<slug>/SPEC.md` exists after agent returns. If missing but content returned inline, write it manually.

Mark Step 2 `[x]` in STATUS.md. Update `last_updated`.

Print SPEC summary:
```
📄 SPEC written: specs/features/<slug>/SPEC.md
   <frontmatter summary from specifier>
```

## Step 3 — Human checkpoint

```
AskUserQuestion:
  question: "SPEC is ready. Proceed to planning phase?"
  options: [yes — continue to planner, edit-spec-first — I'll edit and re-run /plan, abort — stop here]
```

- `yes` → continue.
- `edit-spec-first` → update STATUS note: "user wants to edit SPEC before planning". Set `overall_status: in_progress`. Print: "Edit `specs/features/<slug>/SPEC.md` then re-run `/plan <slug>`. STATUS will resume from planner step." Stop.
- `abort` → mark STATUS `overall_status: done`, note "aborted at checkpoint". Stop.

Mark Step 3 `[x]` in STATUS.md.

## Step 4 — Delegate ashen-planner

Emit routing block:
```
📍 plan router — planner
   spec:    specs/features/<slug>/SPEC.md
   target:  specs/features/<slug>/PLAN.md
```

Call Agent with subagent_type `ashen-planner`. Prompt (≤ 1500 chars):

```
Spec path: specs/features/<slug>/SPEC.md
Target path: specs/features/<slug>/PLAN.md
CWD hints (files present): <comma-separated list from Step 1 probe>

Read SPEC.md fully. Produce PLAN.md at target path with dependency-ordered phases (each phase independently verifiable). Include task IDs (T1.1, T1.2, ...) and validation criteria per phase. Return: path + phase count + summary.
```

Verify `specs/features/<slug>/PLAN.md` exists. If missing but content returned inline, write it manually.

Mark Step 4 `[x]` in STATUS.md. Set `overall_status: done`. Update `last_updated`.

Print final report:
```
✅ PLAN complete
   SPEC:  specs/features/<slug>/SPEC.md
   PLAN:  specs/features/<slug>/PLAN.md
   <phase count + summary from planner>

Next: /task <slug>
```

## Rules
- No feature code. No commits. No installs.
- Only write to `specs/features/<slug>/` and its STATUS.md.
- SPIKE.md is auxiliary context — specifier does not copy it verbatim.
- Resume from first unchecked step when STATUS exists and hash matches.
