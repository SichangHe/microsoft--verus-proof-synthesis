#!/usr/bin/env python3
"""Render an AGENTS.md from `agent_prompt.md` into the pilot working tree.

The variable values are passed via --var KEY=VALUE flags. Required:
  repo_path, verify_command, verify_dir, verify_setup, vstd_paths.

The agent-visible scope is the verifier output, not a curated manifest;
no `VERUSAGE_PLUS_TARGETS.txt` is emitted here. The harness still keeps
the per-project manifest at `tools/verusage_plus/<code>_targets.txt`
for stripping and post-run scoring (`error_map.py`).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REQUIRED = (
    "repo_path",
    "verify_command",
    "verify_dir",
    "verify_setup",
    "vstd_paths",
)
TOKEN_RE = re.compile(r"\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", type=Path, required=True, help="agent_prompt.md")
    ap.add_argument(
        "--out-dir", type=Path, required=True,
        help="upstream repo root where AGENTS.md lands",
    )
    ap.add_argument("--var", action="append", default=[], help="KEY=VALUE")
    args = ap.parse_args()

    template = args.template.read_text()
    vars_in: dict[str, str] = {}
    for v in args.var:
        if "=" not in v:
            raise SystemExit(f"--var must be KEY=VALUE: {v!r}")
        k, val = v.split("=", 1)
        vars_in[k.strip()] = val

    declared = set(TOKEN_RE.findall(template))
    unknown = sorted(set(vars_in) - declared)
    if unknown:
        raise SystemExit(f"unknown variables not present in template: {unknown}")
    missing = sorted(t for t in REQUIRED if t not in vars_in)
    if missing:
        raise SystemExit(f"required variables not supplied: {missing}")

    rendered = template
    for k, val in vars_in.items():
        rendered = rendered.replace("{{" + k + "}}", val)
    stragglers = sorted(set(TOKEN_RE.findall(rendered)))
    if stragglers:
        raise SystemExit(f"unfilled variables in template: {stragglers}")

    out_dir: Path = args.out_dir
    (out_dir / "AGENTS.md").write_text(rendered)
    print(f"wrote AGENTS.md under {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
