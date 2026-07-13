# ashen-harness

A personal Claude Code plugin demonstrating domain-routed agent workflows for structured engineering: from research spike to validated build, through specialist subagents.

## Why this exists

Modern engineering workflows benefit from structure: research before plan, plan before build, validation gate before review. This plugin formalizes that flow with specialist subagents per domain (data-eng, ai-eng, infra-ops, generalist), each with focused prompt and clear scope.

The result: less drift between intent and output, clearer artifacts (SPIKE.md, SPEC.md, PLAN.md) at each stage, and a pluggable model where new domains add a builder without changing the routing layer.

Alongside the build pipeline, three standalone advisory commands work on any tree without a spec: `/audit` (security triage), `/tidy` (code-quality scan), and `/eval-sweep` (offline eval-sweep scaffolding). All advisory scanners delegate detection to deterministic tools when present and never write, commit, or block.

## Architecture

```
/spike <topic>
   │
   └─→ ashen-spike-researcher
           │
           └─→ specs/spikes/<slug>/SPIKE.md

/plan <slug>
   │
   ├─→ ashen-specifier ────→ SPEC.md
   └─→ ashen-planner ─────→ PLAN.md

/task <slug>
   │
   ├─→ domain-router (data-eng | ai-eng | infra-ops | generalist)
   │      │
   │      └─→ specialist-builder
   │
   ├─→ verify gate (against SPEC ## Validation)
   │
   └─→ ashen-reviewer (advisory, never blocks)

Standalone advisory scanners (whole-tree, no build pipeline):

/audit <path>          /tidy <path>           /eval-sweep <slug>
   │                       │                       │
   └─→ ashen-             └─→ ashen-             └─→ ashen-ai-eng-builder
       security-scanner       code-cleaner           (scaffolds eval_sweep.py
       (findings by           (findings by            + sweep_config.json;
        severity)              category)               runs offline, no cost)
```

Hooks fire alongside this flow on session/compaction/subagent events — see [Hooks](#hooks) below.

## Hooks

Wired in `hooks/hooks.json`.

| Event | Matcher | Script | What it does |
|---|---|---|---|
| `SessionStart` | `startup` | `update-context.sh` | Self-learning `.claude/context.json` updater. Detects active feature from current branch and infers test command from project layout. Idempotent — only fills missing fields, never overwrites developer-set ones. Prefers `jq`, falls back to Python3. |
| `PreCompact` | `compact` | `snapshot-state.sh` | Persists pipeline state (`CLAUDE_PIPELINE_*` env vars) to `specs/features/<slug>/.pipeline-state.json` before context compaction, so long-running `/spike`, `/plan`, `/task` runs survive compression. No-op outside a pipeline run. |
| `SubagentStop` | `ashen-*-builder` agents | `run-tests-on-stop.sh` | Auto-detects stack and runs tests after a builder agent finishes. Opt-in via `HARNESS_AUTOTEST=1`; no-op otherwise. |

## Commands

| Command | What it does |
|---|---|
| `/spike <topic>` | Delegates to `ashen-spike-researcher`; outputs `specs/spikes/<slug>/SPIKE.md` |
| `/plan <slug>` | Delegates to `ashen-specifier` then `ashen-planner`; outputs `SPEC.md` + `PLAN.md` |
| `/task <slug>` | Routes to domain builder (`data-eng`, `ai-eng`, `infra-ops`, `generalist`), runs a post-build verify gate against SPEC's `## Validation` commands, then advisory reviewer |
| `/audit <path\|slug>` | Delegates to `ashen-security-scanner`; whole-tree security scan (gitleaks/bandit/semgrep, grep fallback), returns findings grouped by severity. Advisory — no changes, no commits. Resumable via `specs/audits/<slug>/STATUS.md` |
| `/tidy <path\|slug>` | Delegates to `ashen-code-cleaner`; code-quality scan (ruff/black/prettier report-only + LLM judgment on comments, docs, structure), returns findings grouped by category. Advisory — no changes, no commits. Resumable via STATUS.md |
| `/eval-sweep <slug>` | Delegates to `ashen-ai-eng-builder`; scaffolds `eval_sweep.py` + `sweep_config.json` into the repo root and commits them. Sweep runs offline — no LLM cost. Never executes the sweep |

## Requirements

- Claude Code 2.1.197 or later
- `gh` CLI authenticated with repo read access (required for private repo installs)

## Install (consumer)

### 1. Register the marketplace

```
claude plugin marketplace add Coutinho306/ashen-harness
```

### 2. Install the plugin

```
claude plugin install ashen-harness@ashen-harness --scope local
```

### 3. Reload

Run `/reload-plugins` inside a Claude Code session, then verify with `/spike`, `/plan`, or `/task`.

## Local dev loop

```
# Register the local repo as a marketplace source
claude plugin marketplace add /absolute/path/to/ashen-harness

# Install from the local marketplace
claude plugin install ashen-harness@ashen-harness --scope local

# After editing any file in commands/ or agents/:
# In Claude Code: /reload-plugins
```

No restart required — `/reload-plugins` picks up changes immediately.

## Uninstall

```
claude plugin uninstall ashen-harness@ashen-harness
claude plugin marketplace remove ashen-harness
```

If you added bare-name aliases (below), also remove them:

```
rm ~/.claude/commands/{spike,plan,task,audit,tidy,eval-sweep}.md
```

## Bare-name aliases (`/spike` instead of `/ashen-harness:spike`)

Marketplace-installed plugin commands are invoked with a `ashen-harness:` prefix
(e.g. `/ashen-harness:spike`). If you want plain `/spike`, `/plan`, `/task` back,
Claude Code doesn't let a plugin register a bare top-level command name — only
**personal** commands (`~/.claude/commands/`) are exempt from prefixing. So the fix
is a one-time local alias install, not something the plugin can do for you automatically.

Wrapper sources live in this repo under `aliases/` (one per command: `spike`,
`plan`, `task`, `audit`, `tidy`, `eval-sweep`). Install them into your personal
commands dir once per machine. Either symlink them (picks up new aliases as the
repo adds them) via the helper script:

```
scripts/link-aliases.sh
```

or copy them verbatim:

```
cp aliases/*.md ~/.claude/commands/
```

Each file is a thin redirect, e.g. `aliases/spike.md`:

```
---
description: "Alias for ashen-harness:spike"
argument-hint: "<topic | slug>"
---

/ashen-harness:spike $ARGUMENTS
```

After copying, `/reload-plugins` (or restart) and `/spike` works as a bare command.

**Cost:** none — it's a static text expansion to the prefixed command before send,
not an extra model call or round-trip.

**Caveat:** if you ever install a *different* plugin that also defines `/spike`,
`/plan`, or `/task`, your personal alias wins silently (personal commands take
priority) and will always point at ashen-harness's version regardless of
which plugin you meant.

## Agents included

| Agent | Domain | Role |
|---|---|---|
| `ashen-spike-researcher` | all | Research + SPIKE.md authoring |
| `ashen-specifier` | all | SPEC.md authoring |
| `ashen-planner` | all | PLAN.md authoring |
| `ashen-data-eng-builder` | data-eng | dbt, Spark, SQL pipelines |
| `ashen-ai-eng-builder` | ai-eng | LangGraph, RAG, prompt harness |
| `ashen-infra-ops-builder` | infra-ops | Terraform, CI, Docker |
| `ashen-generalist-builder` | generalist | scripts, configs, tooling |
| `ashen-reviewer` | all | Advisory code review (never blocks) |
| `ashen-security-scanner` | all | Advisory security triage — delegates to gitleaks/bandit/semgrep, grep fallback (never blocks) |
| `ashen-code-cleaner` | all | Advisory code-quality scan — delegates to ruff/black/prettier + LLM judgment (never writes, never blocks) |
