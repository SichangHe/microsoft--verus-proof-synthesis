- `Verus-Bench` -> 150 algorithm-level tasks. use for smaller single-function proof synthesis. key layout: `tasks.jsonl`, paired `unverified/` + `verified/` trees.
- `VeruSAGE-Bench` -> 849 repository-level tasks. use for system-scale reasoning. key layout: `tasks.jsonl`, `tasks/`, `tasks-sampled-100/`, `tasks-batches/`, `source-projects/`.

- Need classic algorithms / invariants / self-contained tasks -> `Verus-Bench`.
- Need repo-style tasks derived from real verified systems -> `VeruSAGE-Bench`.

warning

- Prefer `tasks.jsonl` when you only need task inventories or metadata.
- Some Storage (`ST`) VeruSAGE-Bench tasks need dependencies built first.
