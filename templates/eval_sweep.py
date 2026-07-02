#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic>=2"]
# ///
"""Offline parameter sweep runner. Scaffold this into your repo and edit sweep_config.json."""

from __future__ import annotations

import argparse
import dataclasses
import itertools
import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, field_validator, model_validator


class SweepConfig(BaseModel):
    axes: dict[str, list[Any]]
    command: str
    strategy: Literal["grid", "random"] = "random"
    max_runs: int
    results_path: str
    seed: int

    @field_validator("max_runs")
    @classmethod
    def max_runs_positive(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("max_runs must be > 0")
        return v

    @model_validator(mode="after")
    def placeholders_match_axes(self) -> "SweepConfig":
        placeholders = set(re.findall(r"\{(\w+)\}", self.command))
        axis_keys = set(self.axes.keys())
        unknown = placeholders - axis_keys
        unused = axis_keys - placeholders
        if unknown:
            raise ValueError(f"command references unknown axes: {sorted(unknown)}")
        if unused:
            raise ValueError(f"axes not referenced in command: {sorted(unused)}")
        return self


def load_config(path: str) -> SweepConfig:
    raw = json.loads(Path(path).read_text())
    return SweepConfig.model_validate(raw)


@dataclasses.dataclass
class RunRecord:
    combo: dict[str, Any]
    score: float | None
    status: Literal["ok", "failed"]
    duration_s: float
    stdout_tail: str


def _all_combos(config: SweepConfig) -> list[dict[str, Any]]:
    keys = list(config.axes.keys())
    values = [config.axes[k] for k in keys]
    return [dict(zip(keys, combo)) for combo in itertools.product(*values)]


def _select_combos(config: SweepConfig) -> list[dict[str, Any]]:
    all_combos = _all_combos(config)
    if config.strategy == "grid":
        return all_combos[: config.max_runs]
    import random
    rng = random.Random(config.seed)
    cap = min(config.max_runs, len(all_combos))
    return rng.sample(all_combos, cap)


def _combo_key(combo: dict[str, Any]) -> frozenset:
    return frozenset(sorted(combo.items()))


def _load_done_keys(results_path: str) -> set[frozenset]:
    p = Path(results_path)
    if not p.exists():
        return set()
    done: set[frozenset] = set()
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
            combo = {k: v for k, v in record.items() if k not in {"score", "status", "duration_s", "stdout_tail"}}
            done.add(_combo_key(combo))
        except json.JSONDecodeError:
            pass
    return done


_SCORE_RE = re.compile(r"score=([-+]?\d*\.?\d+)")


def _parse_score(stdout: str) -> float | None:
    for line in reversed(stdout.splitlines()):
        m = _SCORE_RE.search(line)
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                pass
    return None


def _run_combo(config: SweepConfig, combo: dict[str, Any]) -> RunRecord:
    cmd = config.command.format(**combo)
    t0 = time.monotonic()
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    duration = time.monotonic() - t0
    tail_lines = result.stdout.splitlines()[-20:]
    stdout_tail = "\n".join(tail_lines)
    score = _parse_score(result.stdout)
    status: Literal["ok", "failed"] = "ok" if score is not None else "failed"
    return RunRecord(combo=combo, score=score, status=status, duration_s=round(duration, 3), stdout_tail=stdout_tail)


def _append_record(results_path: str, record: RunRecord) -> None:
    row = {**record.combo, "score": record.score, "status": record.status, "duration_s": record.duration_s, "stdout_tail": record.stdout_tail}
    with open(results_path, "a") as f:
        f.write(json.dumps(row) + "\n")


def _print_best(results_path: str) -> None:
    best: dict[str, Any] | None = None
    best_score = float("-inf")
    p = Path(results_path)
    if not p.exists():
        print("No results written.")
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("status") == "ok" and isinstance(row.get("score"), (int, float)):
            if row["score"] > best_score:
                best_score = row["score"]
                best = row
    if best is None:
        print("No successful runs recorded.")
    else:
        print(f"Best combo (score={best_score}):")
        for k, v in best.items():
            print(f"  {k}: {v}")
    print(f"Results: {results_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline parameter sweep runner")
    parser.add_argument("--config", required=True, help="Path to sweep_config.json")
    parser.add_argument("--resume", action="store_true", help="Skip already-recorded combos")
    parser.add_argument("--dry-run", action="store_true", help="Print planned combos and exit")
    args = parser.parse_args()

    config = load_config(args.config)
    planned = _select_combos(config)

    if args.dry_run:
        print(f"Planned {len(planned)} combo(s) [{config.strategy}, max_runs={config.max_runs}, seed={config.seed}]:")
        for i, combo in enumerate(planned, 1):
            print(f"  {i:>3}. {combo}")
        return

    done_keys: set[frozenset] = set()
    if args.resume:
        done_keys = _load_done_keys(config.results_path)
        if done_keys:
            print(f"Resuming: {len(done_keys)} combo(s) already recorded, skipping.")

    pending = [c for c in planned if _combo_key(c) not in done_keys]
    if not pending:
        print("Nothing to do — all planned combos already recorded.")
        _print_best(config.results_path)
        return

    print(f"Running {len(pending)} combo(s)...")
    for i, combo in enumerate(pending, 1):
        print(f"  [{i}/{len(pending)}] {combo}", end="", flush=True)
        record = _run_combo(config, combo)
        _append_record(config.results_path, record)
        status_tag = f"score={record.score}" if record.status == "ok" else "FAILED"
        print(f" -> {status_tag} ({record.duration_s}s)")

    _print_best(config.results_path)


if __name__ == "__main__":
    main()
