#!/usr/bin/env bash
# Reusable launch driver for VeruSAGE+ pilots.
# Source-of-truth for the Claude CLI invocation, post-run extract+cheat-scan,
# and process-group cleanup. Per-run launch.sh files set the few variables
# that differ and `exec` this script.
#
# Required env vars:
#   RUN_DIR       absolute path to runs/verusage_plus/<run>/
#   FORK_REPO     absolute path to the upstream fork to cd into
#   RUN_NAME      `claude --name` value (e.g. "AL-all96-20260510T085834Z")
#   BUDGET_USD    `--max-budget-usd` cap
#   VERUS_BIN     directory containing `verus` and `cargo-verus`
# Optional env vars:
#   VSTD_PREFIX   extra vstd source root for cheat_scan whitelist
#                 (in addition to the built-in `~/.cargo/...` carve-outs).
#                 Set when vstd lives outside Cargo's cache, e.g. the
#                 sibling Verus checkout used by Anvil/MA.
#   EXTRA_PATH    extra dirs to prepend to PATH (e.g. nix Singular dir)
#   EXTRA_ENV     extra `export X=Y;` snippet evaluated before the launch
#                 (e.g. `export VERUS_SINGULAR_PATH=...`)
#   CLAUDE_MODEL  default `claude-sonnet-4-6`
#   CLAUDE_EFFORT default `high`
set -euo pipefail
: "${RUN_DIR:?missing}"; : "${FORK_REPO:?missing}"; : "${RUN_NAME:?missing}"
: "${BUDGET_USD:?missing}"; : "${VERUS_BIN:?missing}"

REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
TOOLS_DIR="$REPO_ROOT/tools/verusage_plus"
mkdir -p "$RUN_DIR/logs"
# Prepend TOOLS_DIR so the agent can invoke harness helpers (`request_review.sh`)
# by name from any cwd. Also prepend EXTRA_PATH and VERUS_BIN.
export PATH="${EXTRA_PATH:+$EXTRA_PATH:}$VERUS_BIN:$TOOLS_DIR:$PATH"
# Export FORK_REPO so child processes (request_review.sh) can find the pilot tree.
export FORK_REPO
[[ -n "${EXTRA_ENV:-}" ]] && eval "$EXTRA_ENV"
cd "$FORK_REPO"

# Run claude in its own session/process group via setsid so any descendant
# (e.g. a `find` that detaches from claude after Bash-tool timeout) can be
# SIGKILLed wholesale at script exit instead of orphaning across sessions
# on hung NFS mounts. See codebase_index/tooling/verusage-plus.md for the
# Phase-3 MA/AL incidents this guards against.
rc=0
setsid claude --print --verbose --dangerously-skip-permissions \
  --model "${CLAUDE_MODEL:-claude-sonnet-4-6}" \
  --effort "${CLAUDE_EFFORT:-high}" \
  --output-format stream-json --include-partial-messages \
  --max-budget-usd "$BUDGET_USD" \
  --setting-sources project,local \
  --strict-mcp-config \
  --name "$RUN_NAME" \
  "Please read $FORK_REPO/AGENTS.md and complete the task it describes. Iterate with the verifier command listed there until the verifier output reports 'verified, 0 errors', then stop and give a final summary. Verus and cargo-verus are on PATH." \
  > "$RUN_DIR/logs/claude_run.jsonl" \
  2> "$RUN_DIR/logs/claude_run.stderr" &
CLAUDE_PID=$!
CLAUDE_PGID=$(ps -o pgid= -p "$CLAUDE_PID" | tr -d ' ')

cleanup() {
  # Idempotent SIGKILL of the entire claude session.
  [[ -n "${CLAUDE_PGID:-}" ]] && kill -KILL -- -"$CLAUDE_PGID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

wait "$CLAUDE_PID" || rc=$?

# Numbered, PWD-stripped turn sketch (the human-readable view of the run).
python3 "$REPO_ROOT/tools/verusage_plus/extract_turns.py" \
  "$RUN_DIR/logs/claude_run.jsonl" || true

# Cheat-scan with the bundled-vstd whitelist if applicable.
extra_vstd=()
[[ -n "${VSTD_PREFIX:-}" ]] && extra_vstd+=(--vstd-extra-prefix "$VSTD_PREFIX")
python3 "$REPO_ROOT/tools/verusage_plus/cheat_scan.py" \
  "$RUN_DIR/logs/claude_run.jsonl" \
  --repo "$FORK_REPO" \
  "${extra_vstd[@]}" \
  > "$RUN_DIR/cheat_scan.txt" 2>&1 || true

exit "$rc"
