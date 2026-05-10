#!/usr/bin/env python3
"""Render a Claude Code stream-json transcript as a numbered, PWD-stripped
turn-by-turn sketch suitable for human review.

Each `assistant` content block becomes one turn. THINK / TEXT blocks keep their
text; tool-use blocks keep a one-line sketch (command, file_path, etc.).
`user`/`stream_event`/`system`/`result` events are dropped — the JSONL retains
the full record. The agent's working directory (from the `system.init` event)
is replaced with the literal `<repo>` so the file is shareable without leaking
local paths.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Turn:
    kind: str
    body: str


def truncate(s: str, n: int) -> str:
    s = s.replace("\r", "")
    return s if len(s) <= n else s[:n] + "..."


def sketch_tool_use(name: str, inp: dict) -> Turn:
    """One-line summary of a tool call. Keep enough to grep, drop enough that
    the file stays a sketch rather than a replay."""
    match name:
        case "Bash":
            return Turn("BASH", truncate(inp.get("command", ""), 600))
        case "Edit":
            return Turn("EDIT", inp.get("file_path", "?"))
        case "Read":
            rng = ""
            if "offset" in inp or "limit" in inp:
                rng = f' [offset={inp.get("offset","-")} limit={inp.get("limit","-")}]'
            return Turn("READ", f'{inp.get("file_path", "?")}{rng}')
        case "Write":
            return Turn("WRITE", inp.get("file_path", "?"))
        case "Glob":
            return Turn("GLOB", f'{inp.get("pattern","?")} @ {inp.get("path","")}'.rstrip(" @ "))
        case "Grep":
            return Turn("GREP", f'{inp.get("pattern","?")} @ {inp.get("path","")}'.rstrip(" @ "))
        case "TodoWrite":
            todos = inp.get("todos", [])
            summary = " | ".join(
                f'{t.get("status","?")[:4]}:{truncate(t.get("content",""),60)}'
                for t in todos
            )
            return Turn("TODO", summary)
        case _:
            return Turn(name.upper(), truncate(json.dumps(inp), 250))


def extract(jsonl: Path) -> tuple[str | None, list[Turn]]:
    cwd: str | None = None
    turns: list[Turn] = []
    with jsonl.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if cwd is None and d.get("type") == "system" and d.get("subtype") == "init":
                cwd = d.get("cwd")
            if d.get("type") != "assistant":
                continue
            for blk in d.get("message", {}).get("content", []):
                bt = blk.get("type")
                if bt == "thinking":
                    turns.append(Turn("THINK", blk.get("thinking", "")))
                elif bt == "text":
                    turns.append(Turn("TEXT", blk.get("text", "")))
                elif bt == "tool_use":
                    turns.append(sketch_tool_use(blk.get("name", "?"), blk.get("input", {})))
    return cwd, turns


def render(cwd: str | None, turns: list[Turn]) -> str:
    if cwd:
        turns = [Turn(t.kind, t.body.replace(cwd, "<repo>")) for t in turns]
    width = max(3, len(str(len(turns))))
    lines: list[str] = []
    if cwd:
        lines.append("# paths under the agent's working dir replaced with <repo>")
    lines.append(f"# turns: {len(turns)}")
    lines.append("")
    for i, t in enumerate(turns, 1):
        lines.append(f"=== {str(i).zfill(width)} {t.kind} ===")
        lines.append(t.body)
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("input", type=Path, help="Claude stream-json transcript (.jsonl)")
    p.add_argument(
        "-o", "--output", type=Path,
        help="Output path. Default: <input parent>/turns.txt",
    )
    args = p.parse_args()
    out: Path = args.output or args.input.parent / "turns.txt"
    cwd, turns = extract(args.input)
    out.write_text(render(cwd, turns))
    print(f"wrote {len(turns)} turns -> {out}")


if __name__ == "__main__":
    main()
