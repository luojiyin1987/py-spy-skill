#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HELPER="$ROOT_DIR/py-spy-helper.sh"
SKILL="$ROOT_DIR/SKILL.md"
README="$ROOT_DIR/README.md"
FLAMEGRAPH_TEMPLATE="$ROOT_DIR/docs/flamegraph-interpretation-template.md"
FLAMEGRAPH_ANALYZER="$ROOT_DIR/scripts/analyze-flamegraph.py"

fail() {
  printf 'error: %s\n' "$*" >&2
  exit 1
}

[[ -f "$SKILL" ]] || fail "missing SKILL.md"
[[ -f "$README" ]] || fail "missing README.md"
[[ -f "$HELPER" ]] || fail "missing py-spy-helper.sh"
[[ -f "$FLAMEGRAPH_TEMPLATE" ]] || fail "missing flamegraph interpretation template"
[[ -f "$FLAMEGRAPH_ANALYZER" ]] || fail "missing flamegraph analyzer"

bash -n "$HELPER"
bash -n "$0"
python3 -m py_compile "$FLAMEGRAPH_ANALYZER"

helper_output="$(bash "$HELPER" --help)"
printf '%s\n' "$helper_output" | grep -q 'record-pid' || fail "helper help missing record-pid"
printf '%s\n' "$helper_output" | grep -q 'dump-pid' || fail "helper help missing dump-pid"
printf '%s\n' "$helper_output" | grep -q 'analyze-flamegraph' || fail "helper help missing analyze-flamegraph"
printf '%s\n' "$helper_output" | grep -q 'never runs sudo' || fail "helper help missing safety language"

grep -q '^name: py-spy$' "$SKILL" || fail "SKILL.md missing name frontmatter"
grep -q 'Do not automatically run `sudo`' "$SKILL" || fail "SKILL.md missing sudo safety rule"
grep -q 'Do not use `py-spy dump --locals` unless the user explicitly confirms' "$SKILL" || fail "SKILL.md missing locals safety rule"
grep -q 'analyze-flamegraph' "$SKILL" || fail "SKILL.md missing analyzer workflow"
grep -q 'docs/flamegraph-interpretation-template.md' "$SKILL" || fail "SKILL.md missing flamegraph template reference"
grep -q 'Bottleneck Classification' "$FLAMEGRAPH_TEMPLATE" || fail "flamegraph template missing bottleneck classification section"
grep -q 'Final Answer Shape' "$FLAMEGRAPH_TEMPLATE" || fail "flamegraph template missing final answer shape"

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT
sample_svg="$tmp_dir/sample.svg"
analysis_md="$tmp_dir/analysis.md"
cat > "$sample_svg" <<'SVG'
<svg xmlns="http://www.w3.org/2000/svg">
  <g><title>all (100 samples, 100.00%)</title></g>
  <g><title>app.handlers.render_json (45 samples, 45.00%)</title></g>
  <g><title>json.encoder.iterencode (25 samples, 25.00%)</title></g>
</svg>
SVG

bash "$HELPER" analyze-flamegraph "$sample_svg" "$analysis_md" 5 >/dev/null
[[ -f "$analysis_md" ]] || fail "analyze-flamegraph did not write report"
grep -q 'app.handlers.render_json' "$analysis_md" || fail "analysis report missing top frame"
grep -q 'JSON / serialization' "$analysis_md" || fail "analysis report missing category"

printf 'py-spy skill smoke test passed.\n'
