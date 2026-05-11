#!/usr/bin/env bash
# Agent-invokable: signal "I am stuck, please review" and end the turn.
#
# Prints the agent's one-paragraph status to stdout (which lands in the run
# transcript) and exits 0. The agent's prompt instructs it to stop issuing
# tool calls afterwards; a human supervisor watching the run sees the status
# in the transcript and decides whether to resume this pilot branch or close.
#
# Usage (from inside the pilot working tree):
#   request_review.sh "<one-paragraph status>"
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: $0 \"<one-paragraph status>\"" >&2
  exit 2
fi

cat <<EOF
request_review at $(date -u +%Y-%m-%dT%H:%M:%SZ).

Status:
$1

STOP NOW: do not issue further tool calls. End your turn.
A supervisor will decide whether to resume this pilot branch or close it.
EOF
