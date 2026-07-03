---
description: Research a topic via ashen-spike-researcher; outputs SPIKE.md + recommendation
model: claude-opus-4-8
argument-hint: "<topic | slug>"
delegates-to: [ashen-spike-researcher]
---

You are the `/spike` router. Investigation only — no code changes, no commits.

Topic/slug: $ARGUMENTS

## Step 1 — Pre-fetch + bootstrap

If `$ARGUMENTS` is empty: use `AskUserQuestion` to ask for the topic before continuing.

Resolve slug: if arg is already kebab-case with no spaces, use as-is; else convert topic to kebab-case (lowercase, spaces→hyphens, strip punctuation).

**Resolve slug directory** (run this shell logic; store result in `$dir`):
```bash
dir=$(ls -d specs/spikes/[0-9][0-9][0-9][0-9]-<slug> \
              specs/spikes/<slug> \
              specs/spikes/done/[0-9][0-9][0-9][0-9]-<slug> \
              specs/spikes/done/<slug> 2>/dev/null | head -1)
```
First match wins (numbered-active → bare-active → numbered-done → bare-done).

If `$dir` is empty, this is a new slug — compute the next sequence number and bootstrap:
```bash
next=$(printf '%04d' $(( $(ls -d specs/spikes/[0-9][0-9][0-9][0-9]-* \
                                 specs/spikes/done/[0-9][0-9][0-9][0-9]-* 2>/dev/null \
                            | sed -E 's#.*/([0-9]{4})-.*#\1#' \
                            | sort -n | tail -1 | sed 's/^0*//' | grep -E '.' || echo 0) + 1 )))
dir="specs/spikes/${next}-<slug>"
```
The zero-pad width is 4 (`%04d`). With no existing numbered dirs, `next=0001`.

Probe `$dir/STATUS.md`:
- If `$dir` is under `specs/spikes/done/` and STATUS has `overall_status: done`: report "already done" with path `$dir/SPIKE.md` and stop.
- If STATUS exists and `overall_status: done` (active dir): report "already done" + SPIKE.md path and stop.
- If STATUS exists and `overall_status: in_progress` and `source_hash` matches: resume from first unchecked step.
- Else: bootstrap STATUS.md from template at `${CLAUDE_PLUGIN_ROOT}/templates/STATUS.md`, filling:
  - `slug`: resolved slug (bare kebab, no numeric prefix)
  - `command`: spike
  - `overall_status`: in_progress
  - `last_updated`: now (YYYY-MM-DD HH:MM)
  - `source_hash`: sha256 of (topic + alphabetically-sorted cwd_hints joined with `,`)
  - Steps: 1. Pre-fetch + bootstrap / 2. Route domain / 3. Delegate researcher / 4. Verify + finalize

Probe cwd hints (run these in parallel, capture file existence as list):
- `ls pyproject.toml dbt_project.yml *.tf Dockerfile 2>/dev/null`
- `find .github/workflows -name "*.yml" 2>/dev/null | head -3`
- `grep -rl "langgraph\|langchain\|openai\|anthropic\|llm" . --include="*.py" 2>/dev/null | head -5`

Mark Step 1 `[x]` in STATUS.md.

## Step 2 — Route domain

Infer `domain` from cwd_hints:
- `dbt_project.yml` OR `*.tf` with data keywords OR `spark`/`duckdb`/`polars`/`airflow` in imports → `data-eng`
- `langgraph`/`langchain`/`anthropic`/`openai`/`llm`/`rag`/`embed` in imports OR topic contains "LLM"/"RAG"/"prompt"/"vector"/"embedding" → `ai-eng`
- `*.tf`/`Dockerfile`/`.github/workflows` present AND topic is infra/deploy/CI/CD → `infra-ops`
- Ambiguous (multiple signals or none): use `AskUserQuestion` with question "Which domain best describes this spike?" and options `[data-eng, ai-eng, infra-ops, generalist]`.

Emit the routing log block:
```
📍 spike router
   slug:    <slug>
   domain:  <domain>
   target:  $dir/SPIKE.md
   hash:    <first 8 chars of source_hash>
```

Mark Step 2 `[x]` in STATUS.md.

## Step 3 — Delegate ashen-spike-researcher

Create `$dir/` directory if absent.

Call Agent with subagent_type `ashen-spike-researcher`. Prompt (≤ 1500 chars):

```
Research topic: "<topic>"
Domain: <domain>
Target path: $dir/SPIKE.md
CWD hints (files present): <comma-separated list from Step 1 probe>

Investigate the topic using the domain checklist for <domain>. Produce SPIKE.md at the target path. Return: path + ≤200-byte summary of recommendation.
```

Mark Step 3 `[x]` in STATUS.md.

## Step 4 — Verify + finalize

Verify `$dir/SPIKE.md` exists:
- If missing but researcher returned inline content: write the content to that path manually.
- If missing and no inline content: report failure, leave STATUS `in_progress`.

Update STATUS.md:
- Mark Step 4 `[x]`
- Set `overall_status: done`
- Set `last_updated`: now

Archive the slug directory to `specs/spikes/done/`:
```bash
mkdir -p specs/spikes/done
if git ls-files --error-unmatch "$dir" >/dev/null 2>&1; then
  git mv "$dir" "specs/spikes/done/$(basename "$dir")"
else
  mv "$dir" "specs/spikes/done/$(basename "$dir")"
fi
```

Print final report:
```
✅ SPIKE complete
   path:    specs/spikes/done/<dirname>/SPIKE.md
   domain:  <domain>
   summary: <≤200-byte summary from researcher>

Next: /plan <slug>
```

## Rules
- No feature code. No commits. No installs.
- Only write to `$dir/` and `$dir/STATUS.md`.
- Resume from first unchecked step when STATUS exists and hash matches.
- The `slug:` field in STATUS.md frontmatter is always the bare kebab slug (no numeric prefix). The number lives only in the directory path.
