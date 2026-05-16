"""Per-function verifier-error map.

Walks captured Verus stdout, attributing each `error: ... --> file:line:col`
to the function whose body contains that line. Two modes:

1. **With `--manifest`** (per-pilot scoring): emits one row per stripped
   target lemma. Row columns:
       task\tfile_rel\tfn_name\tn_errors\tfirst_error_line\terror_kinds_top3
   Errors that don't fall inside any manifest lemma are bucketed into
   `__unattributed__` rows per file so totals line up.

2. **Without `--manifest`** (Verus-derived stats): the "target set" is
   whatever the verifier complains about. One row per function carrying
   at least one error. Row columns:
       file_rel\tfn_name\tn_errors\tfirst_error_line\terror_kinds_top3
   The summary on stderr is the headline stat — total errors and the
   number of distinct error-bearing functions, both derived from Verus
   output alone (not from any harness manifest).

Invocation (per-pilot scoring):
  python3 error_map.py \\
    --manifest tools/verusage_plus/ac_targets.txt \\
    --repo /ssd1/sichangheagent/anvil-verifier--anvil \\
    --verifier-output /tmp/anal/verify/AC.out \\
    --out /tmp/anal/error_map/AC.tsv

Invocation (Verus-only stats; used post-strip and post-pilot in
`run_pilot.sh` when `VERIFIER_CMD` is set):
  python3 error_map.py \\
    --repo /ssd1/sichangheagent/anvil-verifier--anvil \\
    --verifier-output <run>/verifier_final.out \\
    --out <run>/error_map.tsv
"""
from __future__ import annotations
import argparse, re, sys
from dataclasses import dataclass, field
from pathlib import Path
from collections import Counter

# Verus error preamble: `error: <message>` followed by `   --> <path>:<line>:<col>`.
# We catch the second line; the first line tells us the error kind.
RE_ERR_ARROW = re.compile(r"^\s*-->\s*([^\s:]+):(\d+):(\d+)\s*$")
RE_ERR_KIND = re.compile(r"^error(?:\[E\d+\])?:\s*(.*)$")
# fn signature in Verus / Rust. Supports `pub`, `pub(crate)`, `pub broadcast`,
# `broadcast proof fn`, `proof fn`, `open spec fn`, `closed spec fn`, `spec fn`,
# attribute-prefixed lines, and `fn` (executable).
RE_FN_SIG = re.compile(
    r"^(?P<indent>\s*)"
    r"(?:pub(?:\([^)]+\))?\s+)?"  # pub / pub(crate)
    r"(?:broadcast\s+)?"           # broadcast keyword
    r"(?:(?:proof|spec|exec)\s+)?" # proof / spec / exec keyword
    r"(?:open\s+|closed\s+)?"       # open / closed (spec) modifier
    r"(?:(?:proof|spec|exec)\s+)?" # second mode keyword after open/closed
    r"fn\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)"
)


@dataclass
class FnRange:
    name: str
    file_rel: str
    start_line: int  # 1-based, line of signature
    body_open_line: int  # line of opening { for body
    end_line: int  # line of matching } closing the body


@dataclass
class Err:
    file_rel: str
    line: int
    col: int
    kind: str  # first line after `error:`
    raw_first_line: str  # the raw `error: ...` line


def parse_fn_ranges(src: str, file_rel: str) -> list[FnRange]:
    """Walk source text once. For every fn signature line, find the next
    `{` at the same logical level (paren_depth == 0) and brace-count from
    there. Tolerates `where` clauses and multi-line `requires`/`ensures`.

    Comments and strings are not fully parsed; we approximate by tracking
    `//` line comments and `/* ... */` block comments and `"..."`/`'...'`
    string literals enough to skip braces inside them. Verus source rarely
    has braces inside string literals so this is good enough.
    """
    lines = src.splitlines()
    out: list[FnRange] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        m = RE_FN_SIG.match(line)
        if not m:
            i += 1
            continue
        name = m.group("name")
        start_line = i + 1
        # scan forward for the body `{` at paren depth 0
        # ignore everything inside `(...)` and `<...>`-generic where clauses
        body_open_line = None
        body_open_idx_in_line = None
        paren_depth = 0
        angle_depth = 0
        in_line_comment = False
        in_block_comment = False
        string_char: str | None = None
        j = i
        col = m.end()  # start searching after the matched signature prefix
        while j < n:
            ln = lines[j]
            k = col if j == i else 0
            while k < len(ln):
                c = ln[k]
                # comment / string handling first
                if in_block_comment:
                    if c == "*" and k + 1 < len(ln) and ln[k + 1] == "/":
                        in_block_comment = False
                        k += 2
                        continue
                    k += 1
                    continue
                if in_line_comment:
                    break  # rest of line is comment
                if string_char is not None:
                    if c == "\\" and k + 1 < len(ln):
                        k += 2
                        continue
                    if c == string_char:
                        string_char = None
                    k += 1
                    continue
                # start of comment / string
                if c == "/" and k + 1 < len(ln):
                    if ln[k + 1] == "/":
                        in_line_comment = True
                        break
                    if ln[k + 1] == "*":
                        in_block_comment = True
                        k += 2
                        continue
                if c == '"' or c == "'":
                    string_char = c
                    k += 1
                    continue
                # paren / angle tracking
                if c == "(":
                    paren_depth += 1
                elif c == ")":
                    paren_depth -= 1
                elif c == "<" and (k == 0 or ln[k - 1] in "=,(<: "):
                    # heuristic: treat `<` after `,` / `(` / `=` as a generic
                    # (not as `<` operator). We just need to NOT count it.
                    angle_depth += 1
                elif c == ">":
                    if angle_depth > 0:
                        angle_depth -= 1
                elif c == "{" and paren_depth == 0 and angle_depth == 0:
                    body_open_line = j + 1
                    body_open_idx_in_line = k
                    break
                elif c == ";" and paren_depth == 0:
                    # forward decl `pub proof fn foo(...);` — no body
                    break
                k += 1
            if body_open_line is not None or (k < len(ln) and ln[k] == ";"):
                break
            in_line_comment = False
            j += 1
            col = 0
        if body_open_line is None:
            # not a function with a body (e.g. an extern decl)
            i += 1
            continue
        # brace count from body_open_idx_in_line
        depth = 0
        end_line = None
        in_line_comment = False
        in_block_comment = False
        string_char = None
        jj = body_open_line - 1
        kk = body_open_idx_in_line
        while jj < n:
            ln = lines[jj]
            while kk < len(ln):
                c = ln[kk]
                if in_block_comment:
                    if c == "*" and kk + 1 < len(ln) and ln[kk + 1] == "/":
                        in_block_comment = False
                        kk += 2
                        continue
                    kk += 1
                    continue
                if in_line_comment:
                    break
                if string_char is not None:
                    if c == "\\" and kk + 1 < len(ln):
                        kk += 2
                        continue
                    if c == string_char:
                        string_char = None
                    kk += 1
                    continue
                if c == "/" and kk + 1 < len(ln):
                    if ln[kk + 1] == "/":
                        in_line_comment = True
                        break
                    if ln[kk + 1] == "*":
                        in_block_comment = True
                        kk += 2
                        continue
                if c == '"' or c == "'":
                    string_char = c
                    kk += 1
                    continue
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        end_line = jj + 1
                        break
                kk += 1
            if end_line is not None:
                break
            in_line_comment = False
            jj += 1
            kk = 0
        if end_line is None:
            # malformed source; skip
            i = j + 1
            continue
        out.append(FnRange(
            name=name,
            file_rel=file_rel,
            start_line=start_line,
            body_open_line=body_open_line,
            end_line=end_line,
        ))
        i = end_line  # don't re-enter the same body
    return out


def parse_verifier_errors(text: str) -> list[Err]:
    """Walk verifier output. Each `error[:|\\[Ennn\\]]: msg` is followed
    by lines of context including `   --> path:L:C`. Capture (path, L,
    msg_first_line). Errors without `-->` (top-level / global) get
    file='', line=0.
    """
    out: list[Err] = []
    lines = text.splitlines()
    i = 0
    n = len(lines)
    pending_kind: str | None = None
    pending_raw: str | None = None
    while i < n:
        line = lines[i]
        m_kind = RE_ERR_KIND.match(line)
        if m_kind:
            pending_kind = m_kind.group(1).strip()
            pending_raw = line.strip()
            i += 1
            # scan a small window for the --> line (Verus typically emits within
            # ~4 lines)
            depth = 0
            while depth < 6 and (i + depth) < n:
                m_arrow = RE_ERR_ARROW.match(lines[i + depth])
                if m_arrow:
                    out.append(Err(
                        file_rel=m_arrow.group(1),
                        line=int(m_arrow.group(2)),
                        col=int(m_arrow.group(3)),
                        kind=pending_kind,
                        raw_first_line=pending_raw or "",
                    ))
                    pending_kind = None
                    pending_raw = None
                    break
                # if we hit another error before --> arrow, the previous one had
                # no location
                m_next = RE_ERR_KIND.match(lines[i + depth])
                if m_next and depth > 0:
                    out.append(Err(file_rel="", line=0, col=0,
                                   kind=pending_kind, raw_first_line=pending_raw or ""))
                    pending_kind = None
                    pending_raw = None
                    break
                depth += 1
            continue
        i += 1
    if pending_kind is not None:
        out.append(Err(file_rel="", line=0, col=0,
                       kind=pending_kind, raw_first_line=pending_raw or ""))
    return out


def file_path_matches(err_file: str, manifest_file_rel: str, repo: Path) -> bool:
    """Verus may emit paths relative to crate root, source root, or
    workspace root. Match by suffix: the manifest's file_rel ends with the
    same path components as the error's file_rel.
    """
    err_parts = Path(err_file).parts
    man_parts = Path(manifest_file_rel).parts
    if len(err_parts) == 0 or len(man_parts) == 0:
        return False
    # last K components of manifest must equal last K of err for K = min len
    k = min(len(err_parts), len(man_parts))
    return err_parts[-k:] == man_parts[-k:]


def _load_src(repo: Path, file_rel: str) -> str | None:
    """Try absolute and repo-relative resolutions of the error's file path."""
    candidate = Path(file_rel)
    if not candidate.is_absolute():
        candidate = repo / candidate
    if candidate.exists():
        return candidate.read_text(errors="replace")
    return None


def _resolve_err_file(err_file: str, repo: Path) -> str | None:
    """Resolve an error's file path to a stable on-disk key, preferring a
    `repo`-relative form when the file lives under `repo`."""
    p = Path(err_file)
    abs_p = p if p.is_absolute() else (repo / p)
    if not abs_p.exists():
        return None
    try:
        return str(abs_p.resolve().relative_to(repo.resolve()))
    except ValueError:
        return str(abs_p)


def _run_with_manifest(args, errors, repo):
    manifest = []
    for line in Path(args.manifest).read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        task, fp, fn = parts
        if "UNRESOLVED" in fp or "UNRESOLVED" in fn:
            continue
        manifest.append((task, fp, fn))

    by_file: dict[str, list[tuple[str, str]]] = {}
    for task, fp, fn in manifest:
        by_file.setdefault(fp, []).append((task, fn))

    fn_ranges_by_file: dict[str, list[FnRange]] = {}
    for fp in by_file:
        src = _load_src(repo, fp)
        if src is None:
            print(f"WARNING: source file missing: {repo / fp}", file=sys.stderr)
            continue
        ranges = parse_fn_ranges(src, fp)
        named = {fn for _, fn in by_file[fp]}
        fn_ranges_by_file[fp] = [r for r in ranges if r.name in named]

    per_lemma_errors: dict[tuple[str, str], list[Err]] = {(fp, fn): [] for _, fp, fn in manifest}
    unattributed: list[Err] = []
    for err in errors:
        matched_file = None
        for fp in by_file:
            if file_path_matches(err.file_rel, fp, repo):
                matched_file = fp
                break
        if matched_file is None:
            unattributed.append(err)
            continue
        ranges = fn_ranges_by_file.get(matched_file, [])
        matched_fn = None
        for r in ranges:
            if r.start_line <= err.line <= r.end_line:
                matched_fn = r.name
                break
        if matched_fn is None:
            unattributed.append(err)
            continue
        per_lemma_errors[(matched_file, matched_fn)].append(err)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fh:
        fh.write("task\tfile_rel\tfn_name\tn_errors\tfirst_error_line\terror_kinds_top3\n")
        for task, fp, fn in manifest:
            errs = per_lemma_errors.get((fp, fn), [])
            kinds = Counter(e.kind[:60] for e in errs)
            top3 = " | ".join(f"{c}x {k}" for k, c in kinds.most_common(3))
            fh.write(f"{task}\t{fp}\t{fn}\t{len(errs)}\t{errs[0].line if errs else 0}\t{top3}\n")
        unattr_by_file = Counter(e.file_rel for e in unattributed)
        for f, c in unattr_by_file.most_common():
            kinds = Counter(e.kind[:60] for e in unattributed if e.file_rel == f)
            top3 = " | ".join(f"{cc}x {k}" for k, cc in kinds.most_common(3))
            fh.write(f"__unattributed__\t{f}\t-\t{c}\t0\t{top3}\n")

    closed = sum(1 for errs in per_lemma_errors.values() if not errs)
    total = len(per_lemma_errors)
    print(f"closed: {closed}/{total}, unattributed errors: {len(unattributed)}",
          file=sys.stderr)


def _run_without_manifest(args, errors, repo):
    """Derive `(file, fn)` keys from the verifier output itself. The target
    set is whatever the verifier reports — no harness manifest consulted.
    """
    files_in_errors = {e.file_rel for e in errors if e.file_rel}
    ranges_by_resolved: dict[str, list[FnRange]] = {}
    file_resolution: dict[str, str | None] = {}
    for raw in files_in_errors:
        resolved = _resolve_err_file(raw, repo)
        file_resolution[raw] = resolved
        if resolved is None or resolved in ranges_by_resolved:
            continue
        src = _load_src(repo, resolved)
        if src is None:
            print(f"WARNING: cannot read {raw}", file=sys.stderr)
            ranges_by_resolved[resolved] = []
            continue
        ranges_by_resolved[resolved] = parse_fn_ranges(src, resolved)

    per_fn: dict[tuple[str, str], list[Err]] = {}
    unattributed_by_file: dict[str, list[Err]] = {}
    for err in errors:
        resolved = file_resolution.get(err.file_rel) if err.file_rel else None
        if resolved is None:
            unattributed_by_file.setdefault(err.file_rel or "<no-file>", []).append(err)
            continue
        ranges = ranges_by_resolved.get(resolved, [])
        matched = None
        for r in ranges:
            if r.start_line <= err.line <= r.end_line:
                matched = r.name
                break
        if matched is None:
            unattributed_by_file.setdefault(resolved, []).append(err)
            continue
        per_fn.setdefault((resolved, matched), []).append(err)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as fh:
        fh.write("file_rel\tfn_name\tn_errors\tfirst_error_line\terror_kinds_top3\n")
        for (fp, fn), errs in sorted(per_fn.items()):
            kinds = Counter(e.kind[:60] for e in errs)
            top3 = " | ".join(f"{c}x {k}" for k, c in kinds.most_common(3))
            fh.write(f"{fp}\t{fn}\t{len(errs)}\t{errs[0].line}\t{top3}\n")
        for fp, errs in sorted(unattributed_by_file.items()):
            kinds = Counter(e.kind[:60] for e in errs)
            top3 = " | ".join(f"{cc}x {k}" for k, cc in kinds.most_common(3))
            fh.write(f"{fp}\t__unattributed__\t{len(errs)}\t0\t{top3}\n")

    total_errors = len(errors)
    n_fns = len(per_fn)
    n_unattr = sum(len(v) for v in unattributed_by_file.values())
    print(
        f"total errors: {total_errors}, distinct error-bearing functions: {n_fns}, "
        f"unattributed: {n_unattr}",
        file=sys.stderr,
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--manifest",
        default=None,
        help="optional per-pilot manifest; omit to derive targets from verifier output",
    )
    p.add_argument("--repo", required=True)
    p.add_argument("--verifier-output", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    repo = Path(args.repo)
    verifier_text = Path(args.verifier_output).read_text(errors="replace")
    errors = parse_verifier_errors(verifier_text)
    print(f"parsed errors: {len(errors)}", file=sys.stderr)

    if args.manifest:
        _run_with_manifest(args, errors, repo)
    else:
        _run_without_manifest(args, errors, repo)


if __name__ == "__main__":
    main()
