#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
py-spy-helper.sh - safe helper for py-spy Skill prototype

Usage:
  ./py-spy-helper.sh doctor
  ./py-spy-helper.sh record-pid <PID> [OUTPUT.svg] [DURATION_SECONDS]
  ./py-spy-helper.sh dump-pid <PID> [OUTPUT.txt]
  ./py-spy-helper.sh top-pid <PID>
  ./py-spy-helper.sh record-cmd [OUTPUT.svg] -- <python command...>

Environment:
  PY_SPY_RATE=100             Sampling rate for record-pid / record-cmd
  PY_SPY_SUBPROCESSES=1       Add --subprocesses for worker pools
  PY_SPY_FORMAT=flamegraph    flamegraph | speedscope | raw | chrometrace

Safety:
  - This helper never runs sudo.
  - This helper never changes ptrace_scope.
  - This helper never adds Docker or Kubernetes capabilities.
  - This helper never uses --locals by default.
USAGE
}

fail() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

need_py_spy() {
  command -v py-spy >/dev/null 2>&1 || fail "py-spy not found. Install with: pip install py-spy"
}

is_pid() {
  [[ "${1:-}" =~ ^[0-9]+$ ]]
}

show_target() {
  local pid="$1"
  if [[ -r "/proc/$pid/cmdline" ]]; then
    tr '\0' ' ' < "/proc/$pid/cmdline" | sed 's/[[:space:]]*$//'
    printf '\n'
  elif command -v ps >/dev/null 2>&1; then
    ps -p "$pid" -o command= || true
  fi
}

common_record_flags() {
  local flags=()
  local rate="${PY_SPY_RATE:-100}"
  local format="${PY_SPY_FORMAT:-flamegraph}"

  flags+=(--rate "$rate")
  flags+=(--format "$format")

  if [[ "${PY_SPY_SUBPROCESSES:-0}" == "1" ]]; then
    flags+=(--subprocesses)
  fi

  printf '%s\0' "${flags[@]}"
}

cmd="${1:-}"
case "$cmd" in
  doctor)
    need_py_spy
    printf 'py-spy: '
    py-spy --version || true

    printf '\nPython-like processes visible to current user:\n'
    if command -v pgrep >/dev/null 2>&1; then
      pgrep -af 'python|gunicorn|uvicorn|celery' || true
    else
      ps aux | grep -E 'python|gunicorn|uvicorn|celery' | grep -v grep || true
    fi

    if [[ -r /proc/sys/kernel/yama/ptrace_scope ]]; then
      printf '\nLinux ptrace_scope: '
      cat /proc/sys/kernel/yama/ptrace_scope
      printf 'Note: this helper does not change ptrace_scope.\n'
    fi
    ;;

  record-pid)
    need_py_spy
    pid="${2:-}"
    output="${3:-py-spy-profile.svg}"
    duration="${4:-30}"

    is_pid "$pid" || fail "record-pid requires a numeric PID"
    is_pid "$duration" || fail "duration must be an integer number of seconds"
    [[ -d "/proc/$pid" || "$(uname -s)" != "Linux" ]] || fail "PID $pid not found under /proc"

    printf 'Target PID %s: ' "$pid"
    show_target "$pid" || true

    mapfile -d '' flags < <(common_record_flags)
    py-spy record "${flags[@]}" --duration "$duration" -o "$output" --pid "$pid"
    printf 'Wrote profile: %s\n' "$output"
    ;;

  dump-pid)
    need_py_spy
    pid="${2:-}"
    output="${3:-py-spy-dump.txt}"

    is_pid "$pid" || fail "dump-pid requires a numeric PID"
    [[ -d "/proc/$pid" || "$(uname -s)" != "Linux" ]] || fail "PID $pid not found under /proc"

    printf 'Target PID %s: ' "$pid"
    show_target "$pid" || true

    # Intentionally no --locals by default: locals may expose secrets.
    py-spy dump --pid "$pid" > "$output"
    printf 'Wrote dump: %s\n' "$output"
    ;;

  top-pid)
    need_py_spy
    pid="${2:-}"
    is_pid "$pid" || fail "top-pid requires a numeric PID"
    py-spy top --pid "$pid"
    ;;

  record-cmd)
    need_py_spy
    output="${2:-py-spy-profile.svg}"
    shift 2 || true
    [[ "${1:-}" == "--" ]] || fail "record-cmd requires: record-cmd [OUTPUT.svg] -- <command...>"
    shift
    [[ "$#" -gt 0 ]] || fail "record-cmd requires a command after --"

    mapfile -d '' flags < <(common_record_flags)
    py-spy record "${flags[@]}" --duration "${PY_SPY_DURATION:-30}" -o "$output" -- "$@"
    printf 'Wrote profile: %s\n' "$output"
    ;;

  -h|--help|help|'')
    usage
    ;;

  *)
    usage >&2
    fail "unknown command: $cmd"
    ;;
esac
