#!/usr/bin/env bash
# Agent-invokable: signal "I am stuck, please review" and end the run.
#
# Effect: writes STUCK.md to the pilot working tree, emails a human supervisor
# with the status, and prints a stop instruction back to the agent. Exits 0 so
# the calling Bash tool doesn't error.
#
# Usage (from inside the pilot working tree):
#   request_review.sh "<one-paragraph status>"
#
# The script reads $FORK_REPO (set by run_pilot.sh / launch.sh); falls back to
# $PWD when invoked by hand. Email helper at ~/.config/helper.sh/email_me.py is
# optional — if absent, the script still writes STUCK.md.
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: $0 \"<one-paragraph status>\"" >&2
  exit 2
fi

status="$1"
repo="${FORK_REPO:-$PWD}"
ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
stuck="$repo/STUCK.md"

{
  echo "# STUCK at $ts"
  echo
  echo "$status"
} > "$stuck"

email_helper="$HOME/.config/helper.sh/email_me.py"
if [ -x "$email_helper" ]; then
  body=$(
    printf 'PWD: %s\n\n' "$repo"
    printf 'The pilot agent has self-reported stuck and is ending its turn.\n\n'
    printf 'Status:\n\n%s\n\n' "$status"
    printf 'STUCK.md is at %s. Resume the same pilot branch (the agent will see STUCK.md as part of its initial reads) or revise the prompt before relaunching.\n' "$stuck"
  )
  "$email_helper" "VeruSAGE+ agent requesting review" "$body" >/dev/null 2>&1 || true
fi

cat <<EOF
request_review accepted at $ts.
STUCK.md written to $stuck.
Supervisor has been emailed.

STOP NOW: do not issue further tool calls. End your turn.
EOF
