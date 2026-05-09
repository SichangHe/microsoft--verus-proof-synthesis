#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Project:
    key: str
    path: str
    mapping: str


PROJECTS = {
    "ironkv": Project("ironkv", "benchmarks/VeruSAGE-Bench/source-projects/ironkv", "mapping_ir.txt"),
    "atmosphere": Project("atmosphere", "benchmarks/VeruSAGE-Bench/source-projects/atmosphere", "mapping_os.txt"),
}


def read_mapping(path: Path) -> dict[str, Path]:
    out: dict[str, Path] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        left, sep, right = line.partition("->")
        if not sep:
            continue
        out[left.strip()] = Path(right.strip())
    return out


def find_matching_close_brace(text: str, open_brace: int) -> int:
    depth = 0
    for i in range(open_brace, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    raise ValueError("unmatched brace while stripping helper proof functions")


def line_start(text: str, index: int) -> int:
    return text.rfind("\n", 0, index) + 1


def strip_preceding_attrs(text: str, start: int) -> int:
    cur = line_start(text, start)
    while cur > 0:
        prev_end = cur - 1
        prev_start = line_start(text, prev_end)
        prev = text[prev_start:prev_end].strip()
        if prev.startswith("#[") or prev.startswith("///") or prev.startswith("//!") or prev == "":
            cur = prev_start
            continue
        break
    return cur


def find_body_open_brace(text: str, after: int) -> int:
    """Find a proof/function body brace, not a spec-expression brace."""
    for line in text[after:].splitlines(keepends=True):
        start = after
        after += len(line)
        if line.strip() == "{":
            return start + line.index("{")
    raise ValueError("could not find proof function body brace")


def proof_fn_spans(text: str) -> list[tuple[str, int, int]]:
    spans: list[tuple[str, int, int]] = []
    needle = "proof fn "
    search_from = 0
    while True:
        pos = text.find(needle, search_from)
        if pos < 0:
            return spans
        name_start = pos + len(needle)
        name_end = name_start
        while name_end < len(text) and (text[name_end].isalnum() or text[name_end] == "_"):
            name_end += 1
        name = text[name_start:name_end]
        if not name:
            search_from = name_end
            continue
        brace = find_body_open_brace(text, name_end)
        end = find_matching_close_brace(text, brace)
        spans.append((name, strip_preceding_attrs(text, pos), end))
        search_from = end


def strip_helper_proofs(text: str, target: str) -> tuple[str, list[str]]:
    removed: list[str] = []
    spans = proof_fn_spans(text)
    for name, start, end in reversed(spans):
        if name == target:
            continue
        text = text[:start] + text[end:]
        removed.append(name)
    removed.reverse()
    return text, removed


def write_verify_scripts(out_dir: Path, target_rel: Path) -> None:
    target = Path("codebase") / target_rel
    target_script = out_dir / "verify_target.sh"
    target_script.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "VERUS=${VERUS:-verus}\n"
        f"exec \"$VERUS\" --crate-type=lib {target}\n"
    )
    target_script.chmod(0o755)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def write_baseline_manifest(out_dir: Path, target_rel: Path, eval_dir: Path) -> None:
    target = Path("codebase") / target_rel
    rows = []
    for path in sorted((out_dir / "codebase").rglob("*.rs")):
        rel = path.relative_to(out_dir)
        rows.append(f"{sha256(path)}  {rel.as_posix()}")
    (out_dir / "baseline.sha256").write_text("\n".join(rows) + "\n")
    script = out_dir / "validate_edits.sh"
    script.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"target='{target.as_posix()}'\n"
        "tmp=$(mktemp)\n"
        "find codebase -type f -name '*.rs' -print0 | sort -z | while IFS= read -r -d '' f; do sha256sum \"$f\"; done > \"$tmp\"\n"
        "changed=$(comm -3 <(sort baseline.sha256) <(sort \"$tmp\") | sed 's/^\\t//' | awk '{print $2}' | sort -u)\n"
        "rm -f \"$tmp\"\n"
        "bad=0\n"
        "while IFS= read -r f; do\n"
        "  [ -z \"$f\" ] && continue\n"
        "  if [ \"$f\" != \"$target\" ]; then echo \"unexpected edited file: $f\"; bad=1; fi\n"
        "done <<< \"$changed\"\n"
        "[ \"$bad\" -eq 0 ]\n"
        "echo \"only target file changed\"\n"
    )
    script.chmod(0o755)
    eval_script = eval_dir / "check_solution.sh"
    eval_script.write_text(
        "#!/usr/bin/env bash\n"
        "# External, hidden-from-agent validation. Verus + edit-guard only;\n"
        "# we rely on agent self-report (see project_prompt.md) instead of a\n"
        "# static cheat checker. Set LYNETTE_ADDITIONS=1 to also run the\n"
        "# (overly strict) lynette additions diff policy against the saved\n"
        "# baseline for ad-hoc inspection.\n"
        "set -euo pipefail\n"
        "VERUS=${VERUS:-verus}\n"
        "script_dir=$(cd -- \"$(dirname -- \"${BASH_SOURCE[0]}\")\" && pwd)\n"
        f"run_dir='{out_dir}'\n"
        f"target='codebase/{target_rel.as_posix()}'\n"
        "(cd \"$run_dir\" && ./validate_edits.sh && ./verify_target.sh)\n"
        "if [ \"${LYNETTE_ADDITIONS:-0}\" = 1 ]; then\n"
        "  LYNETTE=${LYNETTE:-lynette}\n"
        "  \"$LYNETTE\" additions \"$script_dir/lynette_baseline.rs\" \"$run_dir/$target\"\n"
        "fi\n"
    )
    eval_script.chmod(0o755)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", choices=sorted(PROJECTS), required=True)
    parser.add_argument("--task", required=True, help="Unverified task filename, e.g. seq_is_unique__singleton_seq_to_set_is_singleton_set.rs")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--target-name", required=True, help="Function the agent should prove or repair")
    parser.add_argument("--strip-helper-proofs", action="store_true")
    args = parser.parse_args()
    root = Path.cwd()
    project = PROJECTS[args.project]
    project_dir = root / project.path
    mapping = read_mapping(project_dir / project.mapping)
    if args.task not in mapping:
        raise SystemExit(f"unknown task {args.task!r} for project {args.project}")
    verified_rel = mapping[args.task]
    source_verified = project_dir / "verified"
    source_unverified = project_dir / "unverified" / args.task
    out_dir = args.out.resolve()
    if out_dir.exists():
        shutil.rmtree(out_dir)
    shutil.copytree(source_verified, out_dir / "codebase")
    target_rel = verified_rel.relative_to("verified")
    target_path = out_dir / "codebase" / target_rel
    text = source_unverified.read_text()
    removed: list[str] = []
    if args.strip_helper_proofs:
        text, removed = strip_helper_proofs(text, args.target_name)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(text)
    eval_dir = out_dir.parent / "_eval" / out_dir.name
    eval_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_unverified, eval_dir / "original_unverified.rs")
    (eval_dir / "lynette_baseline.rs").write_text(text)
    write_verify_scripts(out_dir, target_rel)
    write_baseline_manifest(out_dir, target_rel, eval_dir)
    (out_dir / "BENCHMARK_CONTEXT.md").write_text(
        f"# VeruSAGE hands-off project pilot\n\n"
        f"Project: `{args.project}`.\n"
        f"Task: `{args.task}`.\n"
        f"Target file: `codebase/{target_rel}`.\n"
        f"Target function: `{args.target_name}`.\n"
        f"Verification: run `./verify_target.sh` while iterating. Success is defined by the target file verifying.\n"
        f"Removed local helper proof functions: {len(removed)}.\n"
        "Do not inspect files outside this directory. Focus on the target file and nearby definitions under `codebase/`.\n"
        "Edit only the target file. Run `./validate_edits.sh` before finishing.\n"
    )
    print(out_dir)
    print(f"target=codebase/{target_rel}")
    print(f"removed_helpers={','.join(removed) if removed else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
