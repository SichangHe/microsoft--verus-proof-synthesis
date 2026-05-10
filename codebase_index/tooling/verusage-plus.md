- Read this if the task involves the **VeruSAGE+** harness — the full-repo pivot that replaces the per-file slice approach with `cargo verus verify` against forks of each upstream VeruSAGE source project.
- Distinct from [`verusage-hands-off-pilot.md`](verusage-hands-off-pilot.md) (the older slice-based harness on `benchmarks/VeruSAGE-Bench/source-projects/<proj>/verified/`); the slice tree is not a Cargo crate so per-file `verus --crate-type=lib` could not give a project-wide signal.
- Top-level files:
  - [`tools/verusage_plus/strip_proofs.py`](../../tools/verusage_plus/strip_proofs.py) — splices `unverified/<task>.rs` bodies into the upstream files. Manifest format: `<task_name>\t<upstream_file>\t<fn_name>`.
  - [`tools/verusage_plus/vest_targets.txt`](../../tools/verusage_plus/vest_targets.txt) — Vest's 22 VE targets, the only manifest written so far.
  - [`tools/verusage_plus/agent_prompt.md`](../../tools/verusage_plus/agent_prompt.md) — hardened agent prompt template; pilot branches embed a filled-in copy as `AGENTS.md`.
  - [`docs/verusage_plus/HANDOFF.md`](../../docs/verusage_plus/HANDOFF.md) — entry point for picking up where Phase 1 ended.
  - [`runs/verusage_plus/<proj>__<tag>__<UTC>/`](../../runs/verusage_plus/) — per-pilot transcript / cost / report. Gitignored (under the existing `runs/` rule).
- Branching convention in each upstream fork: `main` (mirror) → `verusage_plus` (pinned Verus + 22-or-N stripped functions) → `pilot/<proj>-<tag>-<UTC>` (per-attempt working branch with `AGENTS.md` and `VERUSAGE_PLUS_TARGETS.txt` at the root).
- Validation policy: `cargo verus verify` is the **only** authoritative check. We rely on the agent's self-report (per `agent_prompt.md`) for cheat detection; an automated post-run scan is a reasonable add but not yet built. **Phase 1 found that an agent will retrieve the original proofs via `git diff main...HEAD` if the prompt does not explicitly forbid historical-branch reads** — see [`runs/verusage_plus/vest__all22__20260510T012907Z/REPORT.md`](../../runs/verusage_plus/vest__all22__20260510T012907Z/REPORT.md) for the full trace and lessons. The current prompt template explicitly forbids any non-HEAD git access and any network/web access.
- Project list, upstream URLs, per-project caveats, and full multi-phase plan: [`PLAN-verusage-plus.md`](../../PLAN-verusage-plus.md) (gitignored scratch in repo root).

warning

- Each upstream project pins its own Verus version through `vstd = "0.0.0-YYYY-MM-DD-HHMM"`. Match the Verus binary and Rust toolchain to that exactly; mismatched Verus rejects the source as e.g. `error: to dereference a mutable reference parameter in a postcondition...` (the mut-ref migration). For Vest, the right binary is the prebuilt `verus-0.2026.03.17.a96bad0-x86-linux` plus `rustup toolchain install 1.94.0`.
- The benchmark-suite README (`benchmarks/VeruSAGE-Bench/README.md`) describes the *single-file* benchmark; VeruSAGE+ is a different evaluation. The 849 standalone tasks in `benchmarks/VeruSAGE-Bench/tasks/` are not used by VeruSAGE+ — only the `mapping_<proj>.txt` files (to identify which functions to strip) and `unverified/<task>.rs` (to source the stripped body).
