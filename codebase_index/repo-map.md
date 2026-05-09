- `autoverus/` -> smaller algorithmic proof synthesis. read [`systems/autoverus.md`](systems/autoverus.md).
- `verusage/` -> agent-based repair/synthesis for larger system-style tasks. read [`systems/verusage.md`](systems/verusage.md).
- `benchmarks/` -> both benchmark suites plus `tasks.jsonl`. read [`data/benchmarks.md`](data/benchmarks.md).
- `generated/` -> saved experiment outputs. read [`data/generated-results.md`](data/generated-results.md).
- `leaderboard/` -> static site + result JSON/schema. read [`data/leaderboard.md`](data/leaderboard.md).
- `utils/lynette/` -> large Rust parser/tool workspace. read [`tooling/lynette-and-vstd.md`](tooling/lynette-and-vstd.md).
- `tools/verusage_hands_off/` -> external-agent (opencode) pilot harness; outputs land under `runs/verusage_hands_off/` (gitignored). read [`tooling/verusage-hands-off-pilot.md`](tooling/verusage-hands-off-pilot.md).
- `assets/` -> docs/site images; usually ignore.

warning

- Start in `README.md`, `autoverus/README.md`, or `verusage/README.md` before large trees like `generated/`, `benchmarks/`, or `utils/lynette/`.
- `verusage/run_all_batches.py` exists, but its default benchmark paths look legacy; check args before using it as a top-level runner.
