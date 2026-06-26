#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER="$ROOT_DIR/py-spy-helper.sh"
SKILL="$ROOT_DIR/SKILL.md"
README="$ROOT_DIR/README.md"

fail() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

[[ -f "$SKILL" ]] || fail "missing SKILL.md"
[[ -f "$README" ]] || fail "missing README.md"
[[ -f "$HELPER" ]] || fail "missing py-spy-helper.sh"

bash -n "$HELPER"
bash -n "$0"

helper_output="$(bash "$HELPER" --help)"
printf '%s\n' "$helper_output" | grep -q 'record-pid' || fail "helper help missing record-pid"
printf '%s\n' "$helper_output" | grep -q 'dump-pid' || fail "helper help missing dump-pid"
printf '%s\n' "$helper_output" | grep -q 'never runs sudo' || fail "helper help missing safety language"

grep -q '^name: py-spy$' "$SKILL" || fail "SKILL.md missing name frontmatter"
grep -q 'Do not automatically run `sudo`' "$SKILL" || fail "SKILL.md missing sudo safety rule"
grep -q 'Do not use `py-spy dump --locals` unless the user explicitly confirms' "$SKILL" || fail "SKILL.md missing locals safety rule"

printf 'py-spy skill smoke test passed.\n'
