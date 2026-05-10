#!/usr/bin/env python3
"""Splice VeruSAGE-Bench unverified function bodies into a Vest-style upstream repo.

Input: a target manifest (`<task_name>\\t<upstream_file>\\t<fn_name>` per line),
the upstream repo root, and the VeruSAGE-Bench unverified directory.

For each (task_name, upstream_file, fn_name) we (1) locate the function body in
`<unverified_dir>/<task_name>.rs`, then (2) replace the body of the same-named
function in `<repo>/<upstream_file>` with that unverified body.

This matches VeruSAGE's per-task strip exactly: pure proof functions end up with
an empty body, and `exec` functions retain their executable Rust without proof
annotations (loop invariants, ghost asserts, etc.). The stripped repo will fail
`cargo verus verify` until an agent fills the proofs back in.

Heuristic: a function body's opening brace is on a line whose stripped content
is exactly "{". Closing brace is found by depth counting, treating //, /*..*/,
and double-quoted strings as opaque. Both unverified and Vest upstream use the
brace-on-its-own-line style, so this resolves cleanly for all 22 VE targets.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Target:
    task: str
    file: Path
    fn: str


def load_manifest(path: Path) -> list[Target]:
    out: list[Target] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = re.split(r"\s+", line, maxsplit=2)
        if len(parts) != 3:
            raise SystemExit(f"bad manifest line: {raw!r}")
        out.append(Target(parts[0], Path(parts[1]), parts[2]))
    return out


def find_fn_signature_start(text: str, fn: str) -> int:
    pattern = re.compile(rf"\bfn\s+{re.escape(fn)}\b\s*[<(]", re.MULTILINE)
    m = pattern.search(text)
    if not m:
        raise ValueError(f"could not find `fn {fn}`")
    second = pattern.search(text, m.end())
    if second:
        raise ValueError(f"ambiguous `fn {fn}` (multiple definitions)")
    return m.start()


def find_body_open_brace(text: str, after: int) -> int:
    cursor = after
    for line in text[after:].splitlines(keepends=True):
        if line.strip() == "{":
            return cursor + line.index("{")
        cursor += len(line)
    raise ValueError("body brace not found (no line of just `{`)")


def find_matching_close_brace(text: str, open_brace: int) -> int:
    if text[open_brace] != "{":
        raise ValueError("expected `{` at open_brace position")
    i = open_brace
    n = len(text)
    depth = 0
    while i < n:
        ch = text[i]
        if ch == "/" and i + 1 < n and text[i + 1] == "/":
            nl = text.find("\n", i)
            i = n if nl < 0 else nl + 1
            continue
        if ch == "/" and i + 1 < n and text[i + 1] == "*":
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
            continue
        if ch == '"':
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == '"':
                    j += 1
                    break
                j += 1
            i = j
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError("unmatched body brace")


def extract_body(text: str, fn: str) -> str:
    """Return the function body text from `{` (inclusive) to `}` (inclusive)."""
    sig_start = find_fn_signature_start(text, fn)
    body_open = find_body_open_brace(text, sig_start)
    body_end = find_matching_close_brace(text, body_open)
    return text[body_open:body_end]


def splice(text: str, fn: str, new_body: str) -> str:
    sig_start = find_fn_signature_start(text, fn)
    body_open = find_body_open_brace(text, sig_start)
    body_end = find_matching_close_brace(text, body_open)
    return text[:body_open] + new_body + text[body_end:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--repo", type=Path, required=True, help="upstream Vest repo root")
    ap.add_argument(
        "--unverified-dir",
        type=Path,
        required=True,
        help="benchmarks/VeruSAGE-Bench/source-projects/vest/unverified",
    )
    ap.add_argument("--check", action="store_true", help="verify resolution; do not write files")
    args = ap.parse_args()

    targets = load_manifest(args.manifest)

    by_file: dict[Path, list[Target]] = {}
    for t in targets:
        by_file.setdefault(t.file, []).append(t)

    for rel, fns in sorted(by_file.items()):
        full = args.repo / rel
        if not full.exists():
            raise SystemExit(f"missing upstream file: {full}")
        original = full.read_text()
        new = original
        for t in fns:
            unv = args.unverified_dir / f"{t.task}.rs"
            if not unv.exists():
                raise SystemExit(f"missing unverified file: {unv}")
            try:
                body = extract_body(unv.read_text(), t.fn)
            except ValueError as e:
                raise SystemExit(f"unverified {t.task}.rs :: fn {t.fn}: {e}")
            try:
                new = splice(new, t.fn, body)
            except ValueError as e:
                raise SystemExit(f"upstream {rel} :: fn {t.fn}: {e}")
            print(f"OK  {t.task} -> {rel}::{t.fn}  (body {len(body)} bytes)")
        if args.check:
            continue
        if new != original:
            full.write_text(new)

    return 0


if __name__ == "__main__":
    sys.exit(main())
