# claudinho-harness

Personal Claude Code slash commands for a domain-routed builder pipeline:
`/spike`, `/plan`, `/task` — each routing work through specialist subagents with an advisory reviewer.

## Commands

| Command | What it does |
|---|---|
| `/spike <topic>` | Delegates to `claudinho-spike-researcher`; outputs `specs/spikes/<slug>/SPIKE.md` |
| `/plan <slug>` | Delegates to `claudinho-specifier` then `claudinho-planner`; outputs `SPEC.md` + `PLAN.md` |
| `/task <slug>` | Routes to domain builder (`data-eng`, `ai-eng`, `infra-ops`, `generalist`), runs a post-build verify gate against SPEC's `## Validation` commands, then advisory reviewer |

## Requirements

- Claude Code 2.1.197 or later
- `gh` CLI authenticated with repo read access (required for private repo installs)

## Install (consumer)

### 1. Register the marketplace

```
claude plugin marketplace add Coutinho306/claudinho-harness
```

### 2. Install the plugin

```
claude plugin install claudinho-harness@claudinho-harness --scope local
```

### 3. Reload

Run `/reload-plugins` inside a Claude Code session, then verify with `/spike`, `/plan`, or `/task`.

## Local dev loop

```
# Register the local repo as a marketplace source
claude plugin marketplace add /absolute/path/to/claudinho-harness

# Install from the local marketplace
claude plugin install claudinho-harness@claudinho-harness --scope local

# After editing any file in commands/ or agents/:
# In Claude Code: /reload-plugins
```

No restart required — `/reload-plugins` picks up changes immediately.

## Bare-name aliases (`/spike` instead of `/claudinho-harness:spike`)

Marketplace-installed plugin commands are invoked with a `claudinho-harness:` prefix
(e.g. `/claudinho-harness:spike`). If you want plain `/spike`, `/plan`, `/task` back,
Claude Code doesn't let a plugin register a bare top-level command name — only
**personal** commands (`~/.claude/commands/`) are exempt from prefixing. So the fix
is a one-time local alias install, not something the plugin can do for you automatically.

Wrapper sources live in this repo under `aliases/` — copy them into your personal
commands dir once per machine:

```
cp aliases/*.md ~/.claude/commands/
```

Each file is a thin redirect, e.g. `aliases/spike.md`:

```
---
description: "Alias for claudinho-harness:spike"
argument-hint: "<topic | slug>"
---

/claudinho-harness:spike $ARGUMENTS
```

After copying, `/reload-plugins` (or restart) and `/spike` works as a bare command.

**Cost:** none — it's a static text expansion to the prefixed command before send,
not an extra model call or round-trip.

**Caveat:** if you ever install a *different* plugin that also defines `/spike`,
`/plan`, or `/task`, your personal alias wins silently (personal commands take
priority) and will always point at claudinho-harness's version regardless of
which plugin you meant.

## Agents included

| Agent | Domain | Role |
|---|---|---|
| `claudinho-spike-researcher` | all | Research + SPIKE.md authoring |
| `claudinho-specifier` | all | SPEC.md authoring |
| `claudinho-planner` | all | PLAN.md authoring |
| `claudinho-data-eng-builder` | data-eng | dbt, Spark, SQL pipelines |
| `claudinho-ai-eng-builder` | ai-eng | LangGraph, RAG, prompt harness |
| `claudinho-infra-ops-builder` | infra-ops | Terraform, CI, Docker |
| `claudinho-generalist-builder` | generalist | scripts, configs, tooling |
| `claudinho-reviewer` | all | Advisory code review (never blocks) |
