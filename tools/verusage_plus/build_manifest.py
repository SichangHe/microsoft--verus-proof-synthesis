#!/usr/bin/env python3
"""Build a VeruSAGE+ target manifest for one project.

Given a VeruSAGE-Bench `mapping_<code>.txt` (lines like `<task>.rs -> verified/<dir>/<task>.rs`),
the project's `unverified/` directory, and the upstream repo's source root, emit a
`<task>\\t<upstream_file_relative_to_repo>\\t<fn>` line per target.

Resolution:
- fn name candidates = (task_name, last `__`-split chunk of task_name).
  We try the longest first so multi-chunk fn names like
  `lemma_eventually_always_garbage_collector_does_not_delete_vrs_pods` aren't truncated.
- upstream file is the unique src/ file containing `fn <candidate>` (any qualifier).
- if multiple matches, pick the one whose path's components (best-effort) align with
  the task's `__`-separated path prefix.
- if zero or still-ambiguous, emit a `# UNRESOLVED ...` line and continue.

Run with `--check` to print only resolved/unresolved without writing output, otherwise
print to stdout.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MapEntry:
    task: str
    verified_path: Path  # path under benchmark verified/, informational


def load_mapping(path: Path) -> list[MapEntry]:
    out: list[MapEntry] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^(\S+)\.rs\s+->\s+(verified/\S+\.rs)\s*$", line)
        if not m:
            continue
        out.append(MapEntry(m.group(1), Path(m.group(2))))
    return out


FN_RX = re.compile(r"\bfn\s+(\w+)")


def find_fn_candidates(unverified_file: Path, task: str) -> list[str]:
    """Yield fn names whose name suffixes the task name.

    The task name encodes path + fn (joined by `__`). The fn name is whatever
    declared fn appears in the unverified file AND whose name suffixes `task`.
    Helper fns the unverified file also declares are NOT acceptable substitutes.
    """
    text = unverified_file.read_text()
    declared: list[str] = []
    seen: set[str] = set()
    for m in FN_RX.finditer(text):
        name = m.group(1)
        if name in seen or name == "main":
            continue
        seen.add(name)
        declared.append(name)
    return [n for n in declared if task == n or task.endswith("__" + n)]


def grep_fn_in_repo(src_root: Path, fn: str) -> list[Path]:
    """Run rg to find src files declaring `fn <fn>`. Returns paths relative to src_root."""
    proc = subprocess.run(
        ["rg", "-l", "--", rf"\bfn\s+{re.escape(fn)}\b", str(src_root)],
        capture_output=True, text=True,
    )
    if proc.returncode not in (0, 1):
        raise SystemExit(f"rg failed: {proc.stderr}")
    paths = [Path(p) for p in proc.stdout.splitlines() if p]
    rel: list[Path] = []
    for p in paths:
        try:
            rel.append(p.relative_to(src_root))
        except ValueError:
            pass
    return rel


def split_task_path(task: str) -> list[str]:
    return task.split("__")


def _path_components(p: Path) -> set[str]:
    """Return the set of identifier-like components of a path: each parent dir name plus
    the file's stem (filename without `.rs`)."""
    out: set[str] = set()
    for part in p.parts:
        out.add(part)
        if part.endswith(".rs"):
            out.add(part[:-3])
    return out


def disambiguate(candidates: list[Path], task: str) -> Path | None:
    """Pick the candidate file whose path components best match the task's `__`-split prefix."""
    if len(candidates) == 1:
        return candidates[0]
    parts = split_task_path(task)
    best: tuple[int, Path] | None = None
    for c in candidates:
        comps = _path_components(c)
        score = sum(1 for p in parts[:-1] if p in comps)
        if best is None or score > best[0]:
            best = (score, c)
    if best and best[0] > 0:
        return best[1]
    return None


def build_one(task: str, unverified_dir: Path, src_root: Path, repo_root: Path) -> tuple[str, str, str] | str:
    unv = unverified_dir / f"{task}.rs"
    if not unv.exists():
        return f"# UNRESOLVED missing-unverified {task}"
    candidates_fn = find_fn_candidates(unv, task)
    for fn in candidates_fn:
        files = grep_fn_in_repo(src_root, fn)
        if not files:
            continue
        if len(files) == 1:
            f = files[0]
        else:
            picked = disambiguate(files, task)
            if picked is None:
                continue
            f = picked
        rel_to_repo = (src_root / f).relative_to(repo_root)
        return (task, str(rel_to_repo), fn)
    return f"# UNRESOLVED no-fn-match {task} (candidates={candidates_fn[:5]})"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mapping", type=Path, required=True)
    ap.add_argument("--unverified-dir", type=Path, required=True)
    ap.add_argument("--src-root", type=Path, required=True, help="upstream repo's src root (e.g. .../anvil-verifier--anvil/src)")
    ap.add_argument("--repo-root", type=Path, required=True, help="upstream repo root (e.g. .../anvil-verifier--anvil)")
    args = ap.parse_args()

    mapping = load_mapping(args.mapping)
    n_resolved = 0
    n_unresolved = 0
    for entry in mapping:
        result = build_one(entry.task, args.unverified_dir, args.src_root, args.repo_root)
        if isinstance(result, tuple):
            task, file, fn = result
            print(f"{task}\t{file}\t{fn}")
            n_resolved += 1
        else:
            print(result)
            n_unresolved += 1
    print(f"# resolved={n_resolved} unresolved={n_unresolved}", file=sys.stderr)
    return 0 if n_unresolved == 0 else 2


if __name__ == "__main__":
    sys.exit(main())
