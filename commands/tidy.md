---
description: Whole-tree code-quality tidy via ashen-code-cleaner; returns structured findings[] grouped by category
model: claude-sonnet-4-6
argument-hint: "<path | slug>"
delegates-to: [ashen-code-cleaner]
---

You are the `/tidy` router. Code-quality advisory only — no code changes, no commits.

Target: $ARGUMENTS

## Step 1 — Pre-fetch + bootstrap

If `$ARGUMENTS` is empty: use `AskUserQuestion` to ask for the path or slug to tidy before continuing.

Resolve target: if arg looks like a file path (contains `/` or ends with a known extension), use as-is. If arg is kebab-case with no spaces, treat as slug and resolve to the corresponding source directory (or `.` if directory not found). If arg is `.` or empty after resolution, scan the full repo from cwd.

Probe `specs/audits/<slug>/STATUS.md` where `<slug>` is derived from arg (kebab-case):
- If exists and `overall_status: done`: report "already done" + findings path and stop.
- If exists and `overall_status: in_progress` and `source_hash` matches: resume from first unchecked step.
- Else: bootstrap STATUS.md from template at `${CLAUDE_PLUGIN_ROOT}/templates/STATUS.md`, filling:
  - `slug`: derived slug
  - `command`: tidy
  - `overall_status`: in_progress
  - `last_updated`: now (YYYY-MM-DD HH:MM)
  - `source_hash`: sha256 of (target arg + cwd)
  - Steps: 1. Pre-fetch + bootstrap / 2. Delegate cleaner / 3. Verify + finalize

Create `specs/audits/<slug>/` directory if absent. **Write STATUS.md to disk now** (Write tool) — before continuing. Every "Mark Step N" below means: Edit the file on disk immediately, not at the end.

Edit `specs/audits/<slug>/STATUS.md` now: mark Step 1 `[x]`, update `last_updated`.

## Step 2 — Delegate ashen-code-cleaner

Emit routing block:
```
📍 tidy router
   target:  <resolved path or slug>
   slug:    <derived slug>
   hash:    <first 8 chars of source_hash>
```

Call Agent with subagent_type `ashen-code-cleaner`. Prompt (≤ 1500 chars):

```
Target: <resolved path>
CWD: <cwd>

Scan the target for code-quality issues. Detect ruff/black/prettier first and use them report-only (mode: full); no grep fallback — if none present, set mode: degraded and recommend uv tool install ruff. Run LLM judgment pass for comment (CLAUDE.md WHY-only policy), docs (undocumented public symbols), and structure (long funcs, duplication, unclear names) categories. Return mode, tools_used, structured findings[] with category/severity/file/line/note, and total. Advisory only — never write files, never block. Return findings: [] if none.
```

If cleaner delegation fails: log "cleaner unavailable" in STATUS notes and continue.

Receive `mode`, `tools_used`, `findings[]`. Edit `specs/audits/<slug>/STATUS.md` now: mark Step 2 `[x]`, update `last_updated`.

## Step 3 — Verify + finalize

Confirm `findings[]` (or empty list) was returned by the cleaner.

Edit `specs/audits/<slug>/STATUS.md` now: mark Step 3 `[x]`, set `overall_status: done`, update `last_updated`.

Append to STATUS.md notes:
```
## Tidy findings (<date>)
<findings from cleaner, or "none">
```

Print final report:
```
✅ tidy complete
   target:   <resolved path>
   mode:     <full | degraded — install ruff: uv tool install ruff>
   tools:    <tools_used>
   findings: format: N  comment: N  docs: N  structure: N
   total:    <total count>

Findings detail:
<findings list grouped by category, or "none">
```

## Rules
- No feature code. No commits. No installs.
- Only write to `specs/audits/<slug>/STATUS.md`.
- Cleaner findings are advisory — never halt or revert on findings alone.
- Resume from first unchecked step when STATUS exists and hash matches.
