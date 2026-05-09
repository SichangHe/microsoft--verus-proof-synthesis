#!/usr/bin/env python3
"""Estimate token usage and dollar cost for an opencode session.

Inputs: an `opencode export <sessionID>` JSON file or a step-finish JSONL
written by `opencode run --format json` (line-delimited events).

We aggregate `step_finish.part.tokens.{input,output,reasoning,cache.{read,write}}`,
optionally split by sub-agent (Sisyphus / Hephaestus / ...), and price using
a static table. Pricing is per 1M tokens.

The `reasoning` channel is billed as output for OpenAI GPT-5 family.
`cache.write` is billed at the input rate by default (override with --cache-write-rate).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Price:
    input_per_m: float
    output_per_m: float
    cached_input_per_m: float
    cache_write_per_m: float | None = None


PRICES: dict[str, Price] = {
    "gpt-5.5-medium": Price(5.00, 30.00, 0.50),
    "gpt-5.5": Price(5.00, 30.00, 0.50),
    "composer-2": Price(0.60, 3.00, 0.10),
    "kimi-k2.5": Price(0.60, 3.00, 0.10),
}


@dataclass
class Tally:
    input: int = 0
    output: int = 0
    reasoning: int = 0
    cache_read: int = 0
    cache_write: int = 0
    steps: int = 0

    def add_tokens(self, tk: dict) -> None:
        self.input += tk.get("input", 0) or 0
        self.output += tk.get("output", 0) or 0
        self.reasoning += tk.get("reasoning", 0) or 0
        c = tk.get("cache") or {}
        self.cache_read += c.get("read", 0) or 0
        self.cache_write += c.get("write", 0) or 0
        self.steps += 1

    def cost(self, price: Price) -> float:
        cw_rate = price.cache_write_per_m if price.cache_write_per_m is not None else price.input_per_m
        return (
            self.input * price.input_per_m
            + (self.output + self.reasoning) * price.output_per_m
            + self.cache_read * price.cached_input_per_m
            + self.cache_write * cw_rate
        ) / 1_000_000


@dataclass
class Run:
    session_id: str = ""
    title: str = ""
    by_agent: dict[str, Tally] = field(default_factory=dict)
    total: Tally = field(default_factory=Tally)


def from_export_json(path: Path) -> Run:
    data = json.loads(path.read_text())
    run = Run(session_id=data.get("info", {}).get("id", ""), title=data.get("info", {}).get("title", ""))
    for m in data.get("messages", []):
        info = m.get("info", {})
        agent = info.get("agent", "?")
        for p in m.get("parts", []):
            if p.get("type") != "step-finish":
                continue
            tk = p.get("tokens") or {}
            run.by_agent.setdefault(agent, Tally()).add_tokens(tk)
            run.total.add_tokens(tk)
    return run


def from_jsonl(path: Path) -> Run:
    run = Run()
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line.startswith("{"):
                continue
            ev = json.loads(line)
            if ev.get("type") != "step_finish":
                continue
            run.session_id = run.session_id or ev.get("sessionID", "")
            tk = ev.get("part", {}).get("tokens") or {}
            run.by_agent.setdefault("(jsonl-no-agent)", Tally()).add_tokens(tk)
            run.total.add_tokens(tk)
    return run


def render(run: Run, price: Price, model_label: str) -> str:
    lines: list[str] = []
    if run.title or run.session_id:
        lines.append(f"session: {run.session_id}  title: {run.title}")
    lines.append(f"model:   {model_label}  prices/M:  in=${price.input_per_m}  out=${price.output_per_m}  cached_in=${price.cached_input_per_m}")
    header = f"{'agent':<28} {'steps':>5} {'input':>10} {'output':>8} {'reason':>8} {'cache_r':>10} {'cache_w':>8} {'$':>9}"
    lines.append(header)
    lines.append("-" * len(header))
    for agent, t in sorted(run.by_agent.items()):
        lines.append(
            f"{agent:<28} {t.steps:>5} {t.input:>10} {t.output:>8} {t.reasoning:>8} {t.cache_read:>10} {t.cache_write:>8} {t.cost(price):>8.4f}"
        )
    t = run.total
    lines.append("-" * len(header))
    lines.append(
        f"{'TOTAL':<28} {t.steps:>5} {t.input:>10} {t.output:>8} {t.reasoning:>8} {t.cache_read:>10} {t.cache_write:>8} {t.cost(price):>8.4f}"
    )
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path", type=Path, help="opencode export JSON or step-finish JSONL")
    ap.add_argument("--model", default="gpt-5.5-medium", choices=sorted(PRICES))
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON instead of a table")
    args = ap.parse_args()

    text = args.path.read_text(errors="replace")
    is_export = text.lstrip().startswith("{") and '"messages"' in text[:4096]
    run = from_export_json(args.path) if is_export else from_jsonl(args.path)
    price = PRICES[args.model]

    if args.json:
        out = {
            "session_id": run.session_id,
            "title": run.title,
            "model": args.model,
            "prices_per_million": {
                "input": price.input_per_m,
                "output": price.output_per_m,
                "cached_input": price.cached_input_per_m,
            },
            "by_agent": {
                a: {
                    "steps": t.steps,
                    "input": t.input,
                    "output": t.output,
                    "reasoning": t.reasoning,
                    "cache_read": t.cache_read,
                    "cache_write": t.cache_write,
                    "cost_usd": round(t.cost(price), 6),
                }
                for a, t in run.by_agent.items()
            },
            "total": {
                "steps": run.total.steps,
                "input": run.total.input,
                "output": run.total.output,
                "reasoning": run.total.reasoning,
                "cache_read": run.total.cache_read,
                "cache_write": run.total.cache_write,
                "cost_usd": round(run.total.cost(price), 6),
            },
        }
        print(json.dumps(out, indent=2))
    else:
        print(render(run, price, args.model))
    return 0


if __name__ == "__main__":
    sys.exit(main())
