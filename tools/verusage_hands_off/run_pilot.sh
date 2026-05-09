#!/usr/bin/env bash
# One-shot driver for a VeruSAGE-style hands-off project pilot.
#
# Usage:
#   tools/verusage_hands_off/run_pilot.sh \
#       --project ironkv \
#       --task seq_is_unique__singleton_seq_to_set_is_singleton_set.rs \
#       --target-name singleton_seq_to_set_is_singleton_set
#
# Optional:
#   --model openai/gpt-5.5 --variant medium  (opencode model selection)
#   --price-model gpt-5.5-medium             (compute_cost.py price table key)
#   --strip-helper-proofs / --no-strip-helper-proofs (default: strip)
#   --verus PATH    --lynette PATH
#   --tag NAME      (suffix appended to run dir; default = derived from task)
#   --dry-run       (only prepare workspace; do not invoke opencode)
#
# Output dir: runs/verusage_hands_off/<project>__<tag>__<UTC_TIMESTAMP>/
# After the run we save:
#   logs/opencode_run.jsonl     opencode --format json event stream
#   logs/opencode_run.stderr    captured stderr
#   logs/transcript.json        opencode export of the session
#   logs/cost.txt               compute_cost.py summary
#   logs/verify_target.out      Verus result on the target file
#   logs/validate_edits.out     edit-guard result
#   REPORT.md                   human-readable summary

set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
cd "$ROOT"

project=""; task=""; target_name=""
opencode_model="openai/gpt-5.5"; opencode_variant="medium"
price_model="gpt-5.5-medium"
strip=1
tag=""
dry=0
verus="${VERUS:-}"; lynette_path="${LYNETTE:-}"

die() { echo "error: $*" >&2; exit 2; }

while [ "$#" -gt 0 ]; do
  case "$1" in
    --project) project="$2"; shift 2 ;;
    --task) task="$2"; shift 2 ;;
    --target-name) target_name="$2"; shift 2 ;;
    --model) opencode_model="$2"; shift 2 ;;
    --variant) opencode_variant="$2"; shift 2 ;;
    --price-model) price_model="$2"; shift 2 ;;
    --strip-helper-proofs) strip=1; shift ;;
    --no-strip-helper-proofs) strip=0; shift ;;
    --verus) verus="$2"; shift 2 ;;
    --lynette) lynette_path="$2"; shift 2 ;;
    --tag) tag="$2"; shift 2 ;;
    --dry-run) dry=1; shift ;;
    -h|--help) sed -n '1,30p' "$0"; exit 0 ;;
    *) die "unknown flag: $1" ;;
  esac
done

[ -n "$project" ] || die "--project required"
[ -n "$task" ] || die "--task required"
[ -n "$target_name" ] || die "--target-name required"

if [ -z "$tag" ]; then
  tag=${task%.rs}
fi
ts=$(date -u +%Y%m%dT%H%M%SZ)
run_dir="runs/verusage_hands_off/${project}__${tag}__${ts}"
mkdir -p "$run_dir/logs"
echo "run_dir: $run_dir"

prep_args=(--project "$project" --task "$task" --target-name "$target_name" --out "$run_dir")
[ "$strip" -eq 1 ] && prep_args+=(--strip-helper-proofs)
python3 tools/verusage_hands_off/prepare_project_pilot.py "${prep_args[@]}" \
  | tee "$run_dir/logs/prepare.out"

if [ -n "$verus" ]; then export VERUS="$verus"; fi
if [ -n "$lynette_path" ]; then export LYNETTE="$lynette_path"; fi

if [ "$dry" -eq 1 ]; then
  echo "dry run; workspace prepared at $run_dir" >&2
  exit 0
fi

prompt_file="$ROOT/tools/verusage_hands_off/project_prompt.md"
title="verusage-${project}-${tag}-${ts}"

echo "START $(date -Iseconds)" > "$run_dir/logs/opencode_run.jsonl"
( cd "$run_dir" && \
  opencode run --dangerously-skip-permissions \
    --model "$opencode_model" --variant "$opencode_variant" \
    --format json --title "$title" \
    --file "$prompt_file" \
    "$(cat BENCHMARK_CONTEXT.md)" \
    >> "logs/opencode_run.jsonl" 2> "logs/opencode_run.stderr" )

# Extract sessionID from the first event that carries it.
sid=$(python3 -c "
import json,sys
for line in open('$run_dir/logs/opencode_run.jsonl'):
    line=line.strip()
    if not line.startswith('{'): continue
    try: ev=json.loads(line)
    except: continue
    s=ev.get('sessionID') or ev.get('part',{}).get('sessionID')
    if s:
        print(s); break
")
echo "sessionID: $sid"
echo "$sid" > "$run_dir/logs/session_id.txt"

if [ -n "$sid" ]; then
  tools/verusage_hands_off/export_session.sh "$sid" "$run_dir/logs/transcript.json" || \
    echo "warn: transcript export failed" >&2
fi

set +e
( cd "$run_dir" && ./verify_target.sh ) > "$run_dir/logs/verify_target.out" 2>&1
verus_status=$?
( cd "$run_dir" && ./validate_edits.sh ) > "$run_dir/logs/validate_edits.out" 2>&1
edits_status=$?
set -e

cost_input="$run_dir/logs/transcript.json"
[ -s "$cost_input" ] || cost_input="$run_dir/logs/opencode_run.jsonl"
python3 tools/verusage_hands_off/compute_cost.py "$cost_input" --model "$price_model" \
  > "$run_dir/logs/cost.txt"
python3 tools/verusage_hands_off/compute_cost.py "$cost_input" --model "$price_model" --json \
  > "$run_dir/logs/cost.json"

verus_summary=$(grep -E 'verification results::' "$run_dir/logs/verify_target.out" | tail -n1 || true)
edits_summary=$(tail -n1 "$run_dir/logs/validate_edits.out" || true)
cost_total=$(python3 -c "import json;print(json.load(open('$run_dir/logs/cost.json'))['total']['cost_usd'])")

cat > "$run_dir/REPORT.md" <<REPORT
# $project / $tag — $ts

- Session: \`$sid\`
- Workspace: \`$run_dir\`
- Verus (\`verify_target.sh\`): exit=$verus_status — $verus_summary
- Edit guard (\`validate_edits.sh\`): exit=$edits_status — $edits_summary
- Estimated cost ($price_model): \$${cost_total}

Validation policy: Verus + edit-guard only. Cheating is checked by reading
the transcript at \`logs/transcript.json\` and the agent's self-report; we do
not run \`lynette additions\` by default (set \`LYNETTE_ADDITIONS=1\` when
invoking the eval baseline at \`runs/verusage_hands_off/_eval/$(basename "$run_dir")/check_solution.sh\`).
REPORT

echo "==="
cat "$run_dir/REPORT.md"
