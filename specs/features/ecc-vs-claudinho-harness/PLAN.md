---
slug: ecc-vs-claudinho-harness
spec: specs/features/ecc-vs-claudinho-harness/SPEC.md
date: 2026-06-30
---

# PLAN: Post-build verify gate for /task

## Phase 1 — SPEC template: Validation section
**Validation**: `templates/SPEC.md` has a `## Validation` section between `## Design` and `## Tasks`, documenting the one-command-per-line fenced convention, a concrete example, the skipped-when-empty rule, and the parsing contract.
**Tasks**:
- T1.1 Add `## Validation` heading + body to templates/SPEC.md, positioned after `## Design`, before `## Tasks`
- T1.2 Document fenced-shell-command-per-line convention with example (`uv run pytest -q`)
- T1.3 State empty/absent → skipped; state parsing contract (declared order, each via Bash, repo root)

## Phase 2 — task.md verify gate + renumbering + STATUS template
**Validation**: `commands/task.md` has Step 3 — Verify between Build and Review; steps renumbered 1-5; Finalize gates on verify status; `templates/STATUS.md` shows 5 steps.
**Tasks**:
- T2.1 Insert "Step 3 — Verify" heading + body between current Step 2 (Build) and Step 3 (Review)
- T2.2 Verify parses `## Validation`, extracts fenced commands in declared order
- T2.3 Runs each via Bash; captures exit code; on fail captures last ~15 lines of output, omits tail on pass
- T2.4 Emits `verify: {status: pass|fail|skipped, commands: [{cmd, exit, tail}], total: N}`
- T2.5 Renumber: Build=2 (unchanged), Verify=3 (new), Review=4 (was 3), Finalize=5 (was 4); update every in-text reference and heading
- T2.6 Update Step 1's STATUS.md bootstrap step list to 5-step sequence; confirm resume-from-first-`[ ]` logic still works
- T2.7 Update templates/STATUS.md example step list to 5 steps: 1. Pre-fetch+route / 2. Build / 3. Verify / 4. Review / 5. Finalize
- T2.8 Gate Finalize (Step 5): SPEC `status: done` only if verify.status in {pass, skipped}; on fail, SPEC status unchanged, STATUS `overall_status: blocked`, failure detail appended to STATUS notes, failure surfaced in final report
- T2.9 Verify is a separate gate from Review — Review prompt/behavior stays advisory/unchanged; verify fail doesn't require reviewer to flag it too

## Phase 3 — Docs + dry-run verification
**Validation**: README documents the gate in one line; 3 sample-SPEC dry-runs traced by hand confirm pass/fail/skipped behavior; scope guardrail confirmed (no files outside the allowed set); T3.6 only triggered if inline Bash proves unworkably noisy (default: skip).
**Tasks**:
- T3.1 Add one README.md line documenting the post-build verify gate + `## Validation` convention
- T3.2 Dry-run sample SPEC A (passing commands) against task.md's Step 3/5 logic by hand — confirm pass + status:done
- T3.3 Dry-run sample SPEC B (failing command) — confirm fail + overall_status:blocked + SPEC status unchanged + failure in report/STATUS
- T3.4 Dry-run sample SPEC C (no Validation commands) — confirm skipped + status:done
- T3.5 Confirm scope guardrails: touched files limited to commands/task.md, templates/SPEC.md, templates/STATUS.md, README.md
- T3.6 (conditional, default skip) Add agents/claudinho-verifier.md only if inline Bash proves unworkably noisy
