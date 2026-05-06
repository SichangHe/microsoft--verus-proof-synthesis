- If you need the repo-wide picture first, read [`repo-map.md`](repo-map.md).
- If you need the proof-synthesis implementations:
  - Small, mostly single-file algorithmic proof generation -> [`systems/autoverus.md`](systems/autoverus.md).
  - Agent-based repair for larger system code -> [`systems/verusage.md`](systems/verusage.md).
  - Shared verifier / LLM / code-rewrite helpers used by both systems -> [`systems/shared-runtime.md`](systems/shared-runtime.md).
- If you need datasets, experiment assets, or evaluation outputs:
  - Benchmark structure and task formats -> [`data/benchmarks.md`](data/benchmarks.md).
  - Pre-generated experiment results / artifact-reproduction context -> [`data/generated-results.md`](data/generated-results.md).
  - Public results website / submission schema -> [`data/leaderboard.md`](data/leaderboard.md).
- If you need the parser / retrieval tooling around Verus itself -> [`tooling/lynette-and-vstd.md`](tooling/lynette-and-vstd.md).

warning

- `generated/` is huge and mostly output data; avoid recursive reading unless your task is explicitly about published results.
- `utils/lynette/` is a large bundled Rust parser/tool workspace; do not dive in unless the task is parser- or transformation-related.
- `README-artifact-evaluation.md` still refers to an older `/code` path. For current layout, prefer `README.md` plus the subsystem docs in this index.
