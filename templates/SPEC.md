---
slug: <kebab>
kind: feature | bugfix | refactor | research | automation
domain: data-eng | ai-eng | infra-ops | generalist
tier: light | standard
status: draft
date: YYYY-MM-DD
related: []
---

# <title>

## Problem
What's broken or missing. Why now.

## Goal
Testable acceptance criteria. Numbered.

## Non-goals
Explicit out-of-scope.

## Design
Approach, files touched, tradeoffs, rejected options.

## Validation
Fenced shell commands, one per line, run by `/task` after build (in declared order, each via Bash, in repo root). Example:

```
uv run pytest -q
```

Leave this section empty or omit it entirely if there's nothing to run — `/task` reports `skipped` in that case.

## Tasks
- [ ] ordered steps

## Open questions
Unresolved decisions.
