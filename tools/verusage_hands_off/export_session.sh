#!/usr/bin/env bash
# Export an opencode session transcript to a file. Errors out early if the
# JSON is empty or doesn't end with a closing brace.
set -euo pipefail
if [ "$#" -ne 2 ]; then
  echo "usage: $0 <session_id> <output_path>" >&2
  exit 2
fi
sid="$1"; out="$2"
mkdir -p "$(dirname -- "$out")"
opencode export "$sid" > "$out"
last=$(tail -c 4 -- "$out" || true)
case "$last" in
  *"}") ;;
  *) echo "export looks truncated for $sid -> $out" >&2; exit 1 ;;
esac
echo "exported $sid -> $out ($(wc -c <"$out") bytes)"
