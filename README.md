# claudinho-harness

Personal Claude Code slash commands for a domain-routed builder pipeline:
`/spike`, `/plan`, `/task` — each routing work through specialist subagents with an advisory reviewer.

## Commands

| Command | What it does |
|---|---|
| `/spike <topic>` | Delegates to `claudinho-spike-researcher`; outputs `specs/spikes/<slug>/SPIKE.md` |
| `/plan <slug>` | Delegates to `claudinho-specifier` then `claudinho-planner`; outputs `SPEC.md` + `PLAN.md` |
| `/task <slug>` | Routes to domain builder (`data-eng`, `ai-eng`, `infra-ops`, `generalist`) then advisory reviewer |

## Requirements

- Claude Code 2.1.197 or later
- `gh` CLI authenticated with repo read access (required for private repo installs)

## Install (consumer)

### 1. Register the marketplace

```
claude plugin marketplace add thiago18coutinho/claudinho-harness
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
