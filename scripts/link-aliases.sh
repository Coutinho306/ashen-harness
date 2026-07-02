#!/usr/bin/env bash
# Symlinks aliases/*.md into ~/.claude/commands/ so new plugin aliases
# register as bare /name commands without a manual copy step per file.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
aliases_dir="$repo_root/aliases"
commands_dir="${CLAUDE_COMMANDS_DIR:-$HOME/.claude/commands}"

mkdir -p "$commands_dir"

for alias_file in "$aliases_dir"/*.md; do
  name="$(basename "$alias_file")"
  target="$commands_dir/$name"

  if [ -L "$target" ] && [ "$(readlink -f "$target")" = "$(readlink -f "$alias_file")" ]; then
    echo "ok      $name (already linked)"
    continue
  fi

  if [ -e "$target" ] && [ ! -L "$target" ]; then
    echo "skip    $name (exists, not a symlink — remove manually to replace)" >&2
    continue
  fi

  ln -sf "$alias_file" "$target"
  echo "linked  $name"
done
