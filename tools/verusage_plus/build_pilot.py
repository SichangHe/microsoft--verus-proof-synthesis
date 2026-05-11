#!/usr/bin/env python3
"""Render an AGENTS.md from agent_prompt.md template + emit a VERUSAGE_PLUS_TARGETS.txt
beside it. Both files are written into the upstream repo's working tree (not committed
here — caller commits onto the pilot branch).

The variable values are passed via --var KEY=VALUE flags. Required variables:
  repo_path, verify_command, verify_dir, verify_setup, n_targets, initial_errors,
  vstd_paths.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", type=Path, required=True, help="agent_prompt.md")
    ap.add_argument("--manifest", type=Path, required=True, help="<proj>_targets.txt (the resolved manifest)")
    ap.add_argument("--out-dir", type=Path, required=True, help="upstream repo root where AGENTS.md + VERUSAGE_PLUS_TARGETS.txt land")
    ap.add_argument("--var", action="append", default=[], help="KEY=VALUE")
    args = ap.parse_args()

    template = args.template.read_text()
    vars_in: dict[str, str] = {}
    for v in args.var:
        if "=" not in v:
            raise SystemExit(f"--var must be KEY=VALUE: {v!r}")
        k, val = v.split("=", 1)
        vars_in[k.strip()] = val

    rendered = template
    for k, v in vars_in.items():
        rendered = rendered.replace("{{" + k + "}}", v)
    missing = [tok for tok in [
        "repo_path", "verify_command", "verify_dir", "verify_setup",
        "n_targets", "initial_errors", "vstd_paths",
    ] if "{{" + tok + "}}" in rendered]
    if missing:
        raise SystemExit(f"unfilled variables: {missing}")

    out_dir: Path = args.out_dir
    (out_dir / "AGENTS.md").write_text(rendered)

    # Build VERUSAGE_PLUS_TARGETS.txt: <upstream_file>\t<fn> per target line.
    lines: list[str] = []
    for raw in args.manifest.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            raise SystemExit(f"malformed manifest line: {raw!r}")
        _task, file, fn = parts
        lines.append(f"{file}\t{fn}")
    (out_dir / "VERUSAGE_PLUS_TARGETS.txt").write_text("\n".join(lines) + "\n")

    print(f"wrote AGENTS.md and VERUSAGE_PLUS_TARGETS.txt ({len(lines)} targets) under {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
