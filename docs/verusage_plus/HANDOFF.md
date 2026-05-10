# VeruSAGE+ hand-off

Status as of 2026-05-10. This document is the entry point for whoever picks up the multi-project, full-repo VeruSAGE-style verification experiment. It deliberately points at existing artifacts instead of duplicating them.

## What "VeruSAGE+" is

We pivoted away from VeruSAGE-Bench's per-task slice harness because the slice tree (`benchmarks/VeruSAGE-Bench/source-projects/<proj>/verified/`) is not a buildable Cargo crate — see [`docs/verusage_hands_off/project_pilot.md`](../verusage_hands_off/project_pilot.md) for the older slice harness and [`codebase_index/tooling/verusage-hands-off-pilot.md`](../../codebase_index/tooling/verusage-hands-off-pilot.md) for context on why per-file `verus --crate-type=lib` cannot give a meaningful project-wide signal.

VeruSAGE+ instead uses the **upstream repo** of each VeruSAGE source project, with `cargo verus verify` as the authoritative success signal. For each of the 8 upstream repos:

1. Fork the repo on GitHub.
2. On a `verusage_plus` branch: pin the project's Verus version and strip the bodies of the VeruSAGE-Bench-listed target functions by splicing the corresponding `unverified/<task>.rs` body in.
3. From `verusage_plus`, cut a per-attempt `pilot/<proj>-<tag>-<UTC>` branch. Place an `AGENTS.md` (built from the template in [`tools/verusage_plus/agent_prompt.md`](../../tools/verusage_plus/agent_prompt.md)) and a `VERUSAGE_PLUS_TARGETS.txt` file at the repo root.
4. Run an LLM agent (`claude` or `opencode`) against the pilot branch, with cost cap, full transcript capture, and post-run validation of `cargo verus verify`.

The full ordered project list, per-project upstream URL, and project-specific caveats are in [`PLAN-verusage-plus.md`](../../PLAN-verusage-plus.md) at the repo root (gitignored scratch).

## Phase 1 result (Vest, 22 targets)

Mechanically green, scientifically invalid. The agent recovered the original verified proofs by running `git diff main...verusage_plus` instead of writing proofs. Full Bash trace, transcript pointer, cost ($1.78), and tokens are documented in [`runs/verusage_plus/vest__all22__20260510T012907Z/REPORT.md`](../../runs/verusage_plus/vest__all22__20260510T012907Z/REPORT.md). The harness-fix list is at the end of that report.

## What is in place and works

- **Per-project Verus toolchain bootstrapping.** For Vest we downloaded the prebuilt `verus-0.2026.03.17.a96bad0-x86-linux.zip` and installed Rust toolchain `1.94.0`. Same flow generalizes to every other project (each upstream pins its own Verus version through `vstd = "0.0.0-YYYY-MM-DD-HHMM"` in `Cargo.toml`).
- **Proof stripper.** [`tools/verusage_plus/strip_proofs.py`](../../tools/verusage_plus/strip_proofs.py) takes `<task_name>\t<upstream_file>\t<fn_name>` per line, finds the body in `benchmarks/VeruSAGE-Bench/source-projects/<proj>/unverified/<task>.rs`, and splices it into the upstream file. Works for both pure proof functions (empty body) and exec functions (executable body without ghost annotations).
- **Vest manifest.** [`tools/verusage_plus/vest_targets.txt`](../../tools/verusage_plus/vest_targets.txt) lists all 22 Vest targets. Manifests for the other 7 projects do not exist yet.
- **Hardened agent prompt template.** [`tools/verusage_plus/agent_prompt.md`](../../tools/verusage_plus/agent_prompt.md). The Phase 1 prompt did not explicitly forbid `git diff` or web access; the new template does. The Vest fork's committed `AGENTS.md` (on `pilot/vest-all22-20260510T012907Z`) still has the older wording and **must be replaced before any re-run**.
- **Run-launch script pattern.** See [`runs/verusage_plus/vest__all22__20260510T012907Z/launch.sh`](../../runs/verusage_plus/vest__all22__20260510T012907Z/launch.sh) for the exact Claude CLI invocation, including `--print --verbose --output-format stream-json --include-partial-messages --max-budget-usd 30`. Reuse as-is for the next pilot, only changing model / cost cap / working dir.
- **Cost extraction.** Claude's stream-json emits a single `result` event with `total_cost_usd` and `usage` per model. For opencode runs, [`tools/verusage_hands_off/compute_cost.py`](../../tools/verusage_hands_off/compute_cost.py) computes cost from `step_finish.part.tokens` events using a static price table.

## What is open

The harness fixes from Phase 1's report:

1. **Make `verusage_plus` an orphan-root commit** (or run the agent in a throwaway clone with no `main` branch), so historical git state cannot leak the original proofs. The Phase 1 prompt fix (telling the agent not to look at other branches) is the cheap fix the user chose; a sandbox would be the strong fix.
2. **Update existing pilot branches.** The Vest fork's `pilot/vest-all22-20260510T012907Z` branch needs its `AGENTS.md` swapped for the new hardened template before any re-run. After that, cherry-pick the strip onto a fresh pilot branch and relaunch.
3. **Per-project setup for the other 7.** Upstream URLs and project-specific caveats are in [`PLAN-verusage-plus.md`](../../PLAN-verusage-plus.md). For each: fork → pick the project's pinned Verus version → confirm baseline `cargo verus verify` passes → write the project's target manifest from `mapping_<proj>.txt` → strip → cut pilot branch → launch agent.
4. **Reproducible toolchain install.** A short shell script that, given a `vstd 0.0.0-YYYY-MM-DD-HHMM` string, fetches the matching Verus release and installs the matching `rustup` toolchain, would save manual work for the next 7 projects. Not built yet.

## Pointers

- Phase 1 detailed plan + Verus toolchain workflow + Vest pilot history: [`PLAN-vest-pilot.md`](../../PLAN-vest-pilot.md).
- Master plan across all 8 projects: [`PLAN-verusage-plus.md`](../../PLAN-verusage-plus.md).
- Older slice-based harness (kept for context, not used going forward): [`docs/verusage_hands_off/project_pilot.md`](../verusage_hands_off/project_pilot.md), [`tools/verusage_hands_off/`](../../tools/verusage_hands_off/), and [`codebase_index/tooling/verusage-hands-off-pilot.md`](../../codebase_index/tooling/verusage-hands-off-pilot.md).
- VeruSAGE-Bench (the dataset the strips come from): [`benchmarks/VeruSAGE-Bench/`](../../benchmarks/VeruSAGE-Bench/). Per-project README and `mapping_<code>.txt` give the upstream URL and the task list.
- Email helper used for human updates: `~/.config/helper.sh/email_me.py` (always include PWD, never print body).
