# VeruSAGE project-level hands-off pilot

This harness prepares a small project-style benchmark directory from `benchmarks/VeruSAGE-Bench/source-projects`.

It copies a project's `verified/` tree into a runnable workspace, replaces one local target file with its `unverified/` version, and can remove non-target local `proof fn` helpers so the agent sees the implementation/spec context without helper proof bodies or signatures in that file.

The generated directory contains:

- `codebase/`: the project-style Verus files available to the agent.
- `BENCHMARK_CONTEXT.md`: target file, target function, and focus instructions.
- `verify_target.sh`: Verus check for the target file.
- `verify_project.sh`: Verus check for every `.rs` file in `codebase/`.
- `validate_edits.sh`: enforces target-only edits inside the agent-visible workspace.

A sibling `_eval/<run-name>/` directory holds checker inputs that the agent must not see: `original_unverified.rs` preserves the original benchmark file for provenance, and `lynette_baseline.rs` mirrors the agent-visible stripped target. `check_solution.sh` runs Verus and the edit guard from there; it can also run `lynette additions` against the baseline if `LYNETTE_ADDITIONS=1` is set, but that is opt-in for ad-hoc inspection — the standard policy is **Verus + edit-guard only, plus the agent's own self-report**, not an automated cheat checker.

## Run shape

The single-shot driver wraps the whole flow (prepare workspace → opencode run → export transcript → verify → cost report):

```bash
tools/verusage_hands_off/run_pilot.sh \
    --project atmosphere \
    --task va_range__impl2_new.rs \
    --target-name new
```

Output goes to `runs/verusage_hands_off/<project>__<tag>__<UTC_TIMESTAMP>/` with:

- `logs/opencode_run.jsonl` — opencode `--format json` event stream.
- `logs/transcript.json` — `opencode export` of the session (full chat + tool I/O; this is what we read to audit for cheating).
- `logs/cost.txt` / `logs/cost.json` — token totals and dollar estimate (gpt-5.5 medium pricing).
- `logs/verify_target.out`, `logs/validate_edits.out` — validator outputs.
- `REPORT.md` — one-page summary.

To re-export an existing session at any time:

```bash
tools/verusage_hands_off/export_session.sh <sessionID> <output_path.json>
```

## Pilot results, 2026-05-09

Model: `openai/gpt-5.5` variant `medium`. Pricing applied: `$5/M` input, `$30/M` output (reasoning billed as output), `$0.50/M` cached input. Two pilots were run via `opencode run`:

| Run | Verus | Edit guard | Runtime | Session | Cost (USD, gpt-5.5 medium) |
| --- | --- | --- | ---: | --- | ---: |
| `ironkv_singleton_seq` | `1 verified, 0 errors` | target-only | 123.3s | `ses_1f4630a41ffeA7ny2CUZEOpNjW` | $0.46 |
| `atmosphere_va_range_new` | `9 verified, 0 errors` | `only target file changed` | 689.9s | `ses_1f4573df3ffeETZ1OVrtKXwfGY` | $2.12 |

Combined ≈ **$2.58**. Token totals are aggregated from `step_finish.part.tokens` events in each session's exported transcript; see `logs/cost.txt` per run for the per-subagent split (Sisyphus Ultraworker + Hephaestus Deep Agent in the Atmosphere run).

Lynette note: an earlier version of this harness ran `lynette additions` as a cheat check, and Atmosphere's solution was rejected under that rule — the proof replaces `let seq = Ghost(arbitrary());` with `let seq = Ghost(Seq::new(...));` and adds ghost `assert(...)` blocks inside the body of executable `pub fn new`. The `additions` policy refuses any change inside an executable body or inside a `verus!` macro region, even when those changes are pure ghost code completing a TODO that the benchmark explicitly inserted. We removed `lynette additions` from the default validation; the actual Verus check was clean and the agent's edits look like a normal proof completion. The transcripts are the source of truth for cheat-check; `_eval/<run>/check_solution.sh` still supports the strict mode behind `LYNETTE_ADDITIONS=1`.
