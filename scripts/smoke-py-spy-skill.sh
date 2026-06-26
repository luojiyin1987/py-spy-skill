#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER="$ROOT_DIR/py-spy-helper.sh"
SKILL="$ROOT_DIR/SKILL.md"
README="$ROOT_DIR/README.md"
FLAMEGRAPH_TEMPLATE="$ROOT_DIR/docs/flamegraph-interpretation-template.md"
FLAMEGRAPH_ANALYZER="$ROOT_DIR/scripts/analyze-flamegraph.py"
DUMP_ANALYZER="$ROOT_DIR/scripts/analyze-dump.py"
BOTTLENECK_TREE="$ROOT_DIR/docs/bottleneck-decision-tree.md"
HIGH_CPU_COOKBOOK="$ROOT_DIR/docs/cookbook/high-cpu.md"

fail() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

[[ -f "$SKILL" ]] || fail "missing SKILL.md"
[[ -f "$README" ]] || fail "missing README.md"
[[ -f "$HELPER" ]] || fail "missing py-spy-helper.sh"
[[ -f "$FLAMEGRAPH_TEMPLATE" ]] || fail "missing flamegraph interpretation template"
[[ -f "$FLAMEGRAPH_ANALYZER" ]] || fail "missing flamegraph analyzer"
[[ -f "$DUMP_ANALYZER" ]] || fail "missing dump analyzer"
[[ -f "$BOTTLENECK_TREE" ]] || fail "missing bottleneck decision tree"
[[ -f "$HIGH_CPU_COOKBOOK" ]] || fail "missing high CPU cookbook"

bash -n "$HELPER"
bash -n "$0"
python3 -m py_compile "$FLAMEGRAPH_ANALYZER"
python3 -m py_compile "$DUMP_ANALYZER"

helper_output="$(bash "$HELPER" --help)"
printf '%s\n' "$helper_output" | grep -q 'record-pid' || fail "helper help missing record-pid"
printf '%s\n' "$helper_output" | grep -q 'dump-pid' || fail "helper help missing dump-pid"
printf '%s\n' "$helper_output" | grep -q 'analyze-flamegraph' || fail "helper help missing analyze-flamegraph"
printf '%s\n' "$helper_output" | grep -q 'analyze-dump' || fail "helper help missing analyze-dump"
printf '%s\n' "$helper_output" | grep -q 'never runs sudo' || fail "helper help missing safety language"

grep -q '^name: py-spy$' "$SKILL" || fail "SKILL.md missing name frontmatter"
grep -q 'Do not automatically run `sudo`' "$SKILL" || fail "SKILL.md missing sudo safety rule"
grep -q 'Do not use `py-spy dump --locals` unless the user explicitly confirms' "$SKILL" || fail "SKILL.md missing locals safety rule"
grep -q 'analyze-flamegraph' "$SKILL" || fail "SKILL.md missing analyzer workflow"
grep -q 'analyze-dump' "$SKILL" || fail "SKILL.md missing dump analyzer workflow"
grep -q 'docs/bottleneck-decision-tree.md' "$SKILL" || fail "SKILL.md missing bottleneck tree reference"
grep -q 'docs/flamegraph-interpretation-template.md' "$SKILL" || fail "SKILL.md missing flamegraph template reference"
grep -q 'Bottleneck Classification' "$FLAMEGRAPH_TEMPLATE" || fail "flamegraph template missing bottleneck classification section"
grep -q 'Final Answer Shape' "$FLAMEGRAPH_TEMPLATE" || fail "flamegraph template missing final answer shape"
grep -q 'Decision Tree' "$BOTTLENECK_TREE" || fail "bottleneck tree missing decision tree section"
grep -q 'High CPU Python Process' "$HIGH_CPU_COOKBOOK" || fail "high CPU cookbook missing title"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
sample_svg="$tmp_dir/sample.svg"
flamegraph_analysis_md="$tmp_dir/flamegraph-analysis.md"
cat > "$sample_svg" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg">
  <g><title>all (100 samples, 100.00%)</title></g>
  <g><title>app.handlers.render_json (45 samples, 45.00%)</title></g>
  <g><title>json.encoder.iterencode (25 samples, 25.00%)</title></g>
</svg>
SVG

bash "$HELPER" analyze-flamegraph "$sample_svg" "$flamegraph_analysis_md" 5 >/dev/null
[[ -f "$flamegraph_analysis_md" ]] || fail "analyze-flamegraph did not write report"
grep -q 'app.handlers.render_json' "$flamegraph_analysis_md" || fail "flamegraph analysis report missing top frame"
grep -q 'JSON / serialization' "$flamegraph_analysis_md" || fail "flamegraph analysis report missing category"

sample_dump="$tmp_dir/dump.txt"
dump_analysis_md="$tmp_dir/dump-analysis.md"
cat > "$sample_dump" <<'DUMP'
Thread 1 (active)
  File "/app/server.py", line 10, in handle_request
  File "/usr/lib/python3.12/threading.py", line 359, in wait
Thread 2 (active)
  File "/app/worker.py", line 20, in run
  File "/usr/lib/python3.12/threading.py", line 359, in wait
DUMP

bash "$HELPER" analyze-dump "$sample_dump" "$dump_analysis_md" 5 >/dev/null
[[ -f "$dump_analysis_md" ]] || fail "analyze-dump did not write report"
grep -q 'lock / synchronization wait' "$dump_analysis_md" || fail "dump analysis report missing lock category"
grep -q 'threading.py' "$dump_analysis_md" || fail "dump analysis report missing repeated frame"

printf 'py-spy skill smoke test passed.\n'
