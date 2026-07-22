---
description: Whole-tree security audit via ashen-security-scanner; returns structured findings[] grouped by severity
model: claude-sonnet-4-6
argument-hint: "<path | slug>"
delegates-to: [ashen-security-scanner]
---

You are the `/audit` router. Security scan only — no code changes, no commits.

Target: $ARGUMENTS

## Step 1 — Pre-fetch + bootstrap

If `$ARGUMENTS` is empty: use `AskUserQuestion` to ask for the path or slug to audit before continuing.

Resolve target: if arg looks like a file path (contains `/` or ends with a known extension), use as-is. If arg is kebab-case with no spaces, treat as slug and resolve to the corresponding source directory (or `.` if directory not found). If arg is `.` or empty after resolution, scan the full repo from cwd.

Probe `specs/audits/<slug>/STATUS.md` where `<slug>` is derived from arg (kebab-case):
- If exists and `overall_status: done`: report "already done" + findings path and stop.
- If exists and `overall_status: in_progress` and `source_hash` matches: resume from first unchecked step.
- Else: bootstrap STATUS.md from template at `${CLAUDE_PLUGIN_ROOT}/templates/STATUS.md`, filling:
  - `slug`: derived slug
  - `command`: audit
  - `overall_status`: in_progress
  - `last_updated`: now (YYYY-MM-DD HH:MM)
  - `source_hash`: sha256 of (target arg + cwd)
  - Steps: 1. Pre-fetch + bootstrap / 2. Delegate scanner / 3. Verify + finalize

Create `specs/audits/<slug>/` directory if absent. **Write STATUS.md to disk now** (Write tool) — before continuing. Every "Mark Step N" below means: Edit the file on disk immediately, not at the end.

Edit `specs/audits/<slug>/STATUS.md` now: mark Step 1 `[x]`, update `last_updated`.

## Step 2 — Delegate ashen-security-scanner

Emit routing block:
```
📍 audit router
   target:  <resolved path or slug>
   slug:    <derived slug>
   hash:    <first 8 chars of source_hash>
```

Call Agent with subagent_type `ashen-security-scanner`. Prompt (≤ 1500 chars):

```
Target: <resolved path>
CWD: <cwd>

Scan the target for security issues. Detect gitleaks/bandit/semgrep first and use them for detection (mode: full); grep fallback only if none present (mode: degraded). Triage each raw finding in context — drop false positives, rank by blast radius. Return mode, tools_used, structured findings[] grouped by severity (risk/warn/info), suppressed count. Advisory only — never block. Return findings: [] if none.
```

If scanner delegation fails: log "scanner unavailable" in STATUS notes and continue.

Receive `mode`, `tools_used`, `findings[]`, `suppressed`. Edit `specs/audits/<slug>/STATUS.md` now: mark Step 2 `[x]`, update `last_updated`.

## Step 3 — Verify + finalize

Confirm `findings[]` (or empty list) was returned by the scanner.

Edit `specs/audits/<slug>/STATUS.md` now: mark Step 3 `[x]`, set `overall_status: done`, update `last_updated`.

Append to STATUS.md notes:
```
## Scan findings (<date>)
<findings from scanner, or "none">
```

Print final report:
```
✅ audit complete
   target:   <resolved path>
   mode:     <full | degraded — grep only, install gitleaks/semgrep for real coverage>
   tools:    <tools_used>
   findings: risk: N  warn: N  info: N  (suppressed <n> false positives)
   total:    <total count>

Findings detail:
<findings list, or "none">
```

## Rules
- No feature code. No commits. No installs.
- Only write to `specs/audits/<slug>/STATUS.md`.
- Scanner findings are advisory — never halt or revert on findings alone.
- Resume from first unchecked step when STATUS exists and hash matches.
