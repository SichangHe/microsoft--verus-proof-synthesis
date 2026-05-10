#!/usr/bin/env python3
"""Scan a Claude stream-json transcript for VeruSAGE+ pilot prompt violations.

Flags four categories of forbidden tool use, per `agent_prompt.md`:

- GIT-cmd  : Bash that runs git on any non-HEAD ref (log, show, diff, checkout,
             stash, reflog, fetch, ls-tree, cat-file, rev-list, merge-base,
             describe, blame, worktree).
- NET-cmd  : Bash that contacts a remote host (curl, wget, gh, git
             fetch/clone/pull/push/remote, cargo search/fetch/install,
             pip install, npm install).
- NET-tool : direct WebFetch / WebSearch tool use.
- OUT-bash : Bash that reads or greps outside the pilot repo. Reads under
             `~/.cargo/registry/src/.../vstd-<version>/` are NOT flagged
             since vstd is the standard library and Phase 2 confirmed it
             is not a proof-leak surface.
- OUT-read : Read tool against a path outside the pilot repo (same vstd
             carve-out applies).

Usage:
    python3 tools/verusage_plus/cheat_scan.py <jsonl> [--repo PATH]

Repo path defaults to the JSONL's CWD as recorded in the `system/init` event.
Outputs a numbered summary; exit code 0 if no flags, 1 if any.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass

GIT_CMD_RE = re.compile(
    r"\bgit\s+("
    r"diff|log|show|checkout|stash|reflog|fetch|ls-tree|cat-file|"
    r"rev-list|merge-base|describe|blame|worktree"
    r")\b"
)
NET_CMD_RE = re.compile(
    r"\b("
    r"curl|wget|gh\s|"
    r"git\s+(fetch|clone|pull|push|remote)|"
    r"cargo\s+(search|fetch|install)|"
    r"pip\s+install|npm\s+install"
    r")\b"
)
VSTD_CACHE_RE = re.compile(
    r"/\.cargo/registry/src/[^/\s]+/vstd-[0-9]+\.[0-9]+\.[0-9]+-[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{4}/"
)


@dataclass
class Flag:
    kind: str
    tool: str
    payload: str


def is_outside_repo(path: str, repo: str) -> bool:
    return not path.startswith(repo)


def scan(jsonl_path: str, repo: str) -> list[Flag]:
    flags: list[Flag] = []
    with open(jsonl_path) as f:
        for line in f:
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if ev.get("type") != "assistant":
                continue
            for c in ev.get("message", {}).get("content", []):
                if c.get("type") != "tool_use":
                    continue
                name = c.get("name", "")
                inp = c.get("input", {}) or {}
                if name in ("WebFetch", "WebSearch"):
                    flags.append(Flag("NET-tool", name, json.dumps(inp)[:200]))
                    continue
                if name == "Bash":
                    cmd = inp.get("command", "") or ""
                    if GIT_CMD_RE.search(cmd):
                        flags.append(Flag("GIT-cmd", name, cmd[:200]))
                    if NET_CMD_RE.search(cmd):
                        flags.append(Flag("NET-cmd", name, cmd[:200]))
                    cmd_no_vstd = VSTD_CACHE_RE.sub("VSTD/", cmd)
                    repo_parent = "/".join(repo.rstrip("/").split("/")[:-1]) or "/"
                    repo_leaf = repo.rstrip("/").split("/")[-1]
                    # Outside-repo siblings: same parent, different leaf.
                    sibling_re = re.compile(
                        re.escape(repo_parent + "/") + r"(?!" + re.escape(repo_leaf) + r"(?:/|\b))"
                    )
                    misc_out_re = re.compile(
                        r"(/home/[^/]+/\.cargo/(?!registry/src/[^/]+/vstd-)|"
                        r"/home/[^/]+/\.rustup/|/var/|/etc/passwd)"
                    )
                    if sibling_re.search(cmd_no_vstd) or misc_out_re.search(cmd_no_vstd):
                        flags.append(Flag("OUT-bash", name, cmd[:200]))
                if name == "Read":
                    path = inp.get("file_path", "") or ""
                    if path and is_outside_repo(path, repo) and not VSTD_CACHE_RE.search(path):
                        flags.append(Flag("OUT-read", name, path))
    return flags


def init_cwd(jsonl_path: str) -> str | None:
    with open(jsonl_path) as f:
        for line in f:
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if ev.get("type") == "system" and ev.get("subtype") == "init":
                return ev.get("cwd")
    return None


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    _ = p.add_argument("jsonl", help="Path to claude_run.jsonl")
    _ = p.add_argument("--repo", help="Pilot repo absolute path (default: cwd from init event)")
    args = p.parse_args(argv)
    repo = args.repo or init_cwd(args.jsonl)
    if not repo:
        print("error: could not determine repo path; pass --repo", file=sys.stderr)
        return 2
    flags = scan(args.jsonl, repo)
    print(f"repo: {repo}")
    print(f"flags: {len(flags)}")
    for fl in flags:
        print(f"  ! {fl.kind:8s} | {fl.payload}")
    return 1 if flags else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
