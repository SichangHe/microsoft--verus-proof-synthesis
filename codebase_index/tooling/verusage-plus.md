- Read this if the task involves the **VeruSAGE+** harness — the full-repo pivot that replaces the per-file slice approach with the project's native Verus verifier against forks of each upstream VeruSAGE source project.
- Distinct from [`verusage-hands-off-pilot.md`](verusage-hands-off-pilot.md) (the older slice-based harness on `benchmarks/VeruSAGE-Bench/source-projects/<proj>/verified/`); the slice tree is not a Cargo crate so per-file `verus --crate-type=lib` could not give a project-wide signal.

## What and why

VeruSAGE-Bench evaluates each task as a single standalone file (849 tasks, all dependencies inlined as `#[verifier::external_body]` stubs). VeruSAGE+ instead evaluates against the original upstream Cargo crate the task was extracted from. For each upstream repo (forked by the maintainer), we (a) pin the project's Verus version, (b) strip the bodies of the VeruSAGE-Bench-listed target functions, and (c) launch a coding agent (currently `claude --print --model claude-sonnet-4-6 --effort high`) against a per-attempt branch with `cargo verus verify` (or the project's own verifier wrapper) as the authoritative success signal. Goal: measure whether modern coding agents can write Verus proofs end-to-end on real verified Rust projects when the proofs are removed but the rest of the code, specs, and harness are intact.

The slice harness is retired because half of `source-projects/<proj>/verified/<task>.rs` slices reference symbols defined only in upstream sibling modules and cannot be compiled in isolation; per-file `verus --crate-type=lib` therefore could not give a project-wide signal. See [`verusage-hands-off-pilot.md`](verusage-hands-off-pilot.md) for that harness's history.

## Project list (8 forks)

Each upstream is forked under `SichangHe/<owner>--<repo>` and cloned to `/ssd1/sichangheagent/<owner>--<repo>` (sibling of this repo).

| Code | VeruSAGE name | Tasks | Upstream | Notes |
|---|---|---:|---|---|
| VE | Vest | 22 | `secure-foundations/vest` | Smallest. `[package.metadata.verus] verify = true` already in `vest/Cargo.toml`. Phase-1/2 done. |
| NO | Node Replication | 29 | `verus-lang/verified-node-replication` | Library-shaped. Smallest non-Vest — recommended Phase-4 starter. |
| AC | Anvil Advanced (controller) | 63 (49 resolved) | `anvil-verifier/anvil` | Same upstream as AL. Targets in `src/controllers/vreplicaset_controller/`. The benchmark excludes 5 fns for `deps_hack` reasons (`source-projects/anvil-controller/Readme.md`). Phase-3 done (partial). |
| ST | Storage | 63 | `microsoft/verified-storage` | Not yet attempted. |
| MA | Memory Allocator | 89 (87 resolved) | `verus-lang/verified-memory-allocator` | Subset uses `integer_ring` (Singular). Phase-3 done (regressed). |
| AL | Anvil (library) | 104 (96 resolved) | `anvil-verifier/anvil` | Same upstream as AC; one fork covers both. Targets in `src/temporal_logic/` and `src/vstd_ext/`. Phase-3 done (green). |
| IR | IronKV | 118 | `verus-lang/verified-ironkv` | Cargo crate root at `ironsht/`. Not yet attempted. |
| OS | ATMO (Atmosphere) | 157 | `mars-research/atmosphere` | Cargo crate root at `kernel/verified/`. Older slice pilot showed Atmosphere needs the latest Verus, not its `Cargo.toml`-pinned version. Not yet attempted. |
| NR | NRKernel | 204 | `matthias-brun/verified-nrkernel` | Largest; schedule last. |

When a project has multiple disjoint target sets in the same upstream (Anvil = AL + AC), the fork carries one strip branch per set (`verusage_plus_AL`, `verusage_plus_AC`).

## Phase outcomes

| Phase | Pilot | Targets | Closed | Cost / cap | Wall | Cheat | Verdict |
|---|---|---:|---:|---:|---:|:---:|---|
| 1 | Vest | 22 | 22 | $1.78 / $30 | 7 min | 3 (correct) | mechanically green, scientifically INVALID — agent recovered originals via `git diff main...verusage_plus`. Pre-hardened prompt; baseline cheat. |
| 2 | Vest | 22 | 22 | $11.88 / $30 | 60 min | 0 | green; first clean pilot. Hardened prompt sufficient. ~17× the Phase-1 cost — the agent actually did the work. |
| 3 | AC | 49 | 17 (35 % error reduction) | $31.16 / $40 | 2 h 3 m | 0 | partial honest. +1777 lines vs strip. Self-reported budget exhaustion. |
| 3 | MA | 87 | ~0 (244 errors final vs 83 strip) | $60.26 / $60 | 4 h 52 m | 0 | regression. Agent broke `bin_size_result_mul8` during algebraic refactor; budget exhaustion mid-fix. Operational hazard: orphan `find /` wedged 5 h on NFS. |
| 3 | AL | 96 | 96 | $31.49 / $80 | 1 h 49 m | 0 | green. +1311 vs strip / +1243/-648 vs main (restructured, not byte-identical recovery). |

Per-target $ for **closed** targets: Vest-P2 = $0.54, AL = $0.33, AC = $1.83, MA = ∞. The cost-vs-domain pattern (clean library lemmas cheap, liveness/TLA expensive, bitvector + nonlinear + `integer_ring` impossible at the caps tried) is more informative than cost-vs-target-count.

Total spend through Phase 3: ~$137 (incl. older slice pilots: $2.58, Phase 1 $1.78, Phase 2 $11.88, AC $31.16, MA $60.26, AL $31.49).

## Phase-3 lessons — what we learned, what we changed

Full analysis with event-level evidence: [`docs/verusage_plus/phase3_postmortem.md`](../../docs/verusage_plus/phase3_postmortem.md). Headline findings (each is N=1 per pilot — pattern-based inference, not statistical):

1. **Sustained context wear correlates with failure**. Green pilots (Vest P2, AL) peaked at 213 k / 279 k tokens; partial/failed (AC, MA) at 366 k / 367 k against a 400 k window. MA additionally underwent compaction mid-run and then issued its catastrophic regression edit post-compaction; AC stayed chronically near-limit without resetting. Belief, not proven: both regimes (near-limit-no-reset and compact-then-recover) are dangerous, while the green pilots stayed in neither.
2. **The "while the verifier runs" parallel-edit pattern is MA-exclusive** (6 verbalizations vs 0 in any other pilot). It was the proximate cause of MA's downward spiral after it reached 1 error remaining at E6046. Now prompt-banned.
3. **Error count must trend down across edits**. AC's E8775 text — *"Good progress — we're past compile errors. Now these are Verus verification errors"* — shows the agent treating a 4→34 error jump as forward progress because the *phase* moved forward. Now prompt rule: count must trend down, roll back if it rises.
4. **`--verify-module` discipline is a double dividend**. AL used it 105×, MA/AC 0×. Narrow verifies are fast (seconds vs minutes) AND produce small outputs that don't bloat context. Now in the prompt as the iteration default.
5. **Tee-then-grep eliminates ~80 % of redundant verifier calls.** All four pilots ran 78–94 % of consecutive verifier calls with the same core command and only the grep tail varying. None used `tee` systematically. Now in the prompt with a worked example.
6. **AC's failure shape is coverage, not domain difficulty.** 3 of 8 target files received 0 edits despite 21 reads; the agent greedy-finished the easier files. Now prompt has *"leave it and move on, append to `SKIPPED.md`"* convention.
7. **Whole-run stuck → exit, don't grind.** New [`request_review.sh`](../../tools/verusage_plus/request_review.sh) lets the agent print a one-paragraph status to the transcript and end its turn when error count plateaus, ideas are exhausted, or the verifier keeps reporting non-proof-level errors (`cannot find function`, `mismatched types`, `expected ','`) that signal helper-hallucination.
8. **Domain-tactic hints are deliberately withheld.** MA mentioned `integer_ring` 59 times and never used it; we record this as a finding about the agent's tactic-search priors, not as a harness gap. The benchmark is meant to be a worst-case eval (no project-specific guidance).

Deliberately not done (with reasons in the postmortem): sandboxing, hard-numeric agent triggers, pre-generated helper-signature files, per-project tactic hints, edit-granularity caps.

Validation experiments are queued but not yet run: re-run MA at $30 and AC at $40 with the upgraded prompt; pass criteria in the postmortem's *Validation plan*.

## Tools (`tools/verusage_plus/`)

- [`strip_proofs.py`](../../tools/verusage_plus/strip_proofs.py) — splices `unverified/<task>.rs` bodies into the upstream files. Manifest format: `<task_name>\t<upstream_file>\t<fn_name>`. The manifest at `tools/verusage_plus/<code>_targets.txt` lives harness-side only — it never enters the pilot working tree, so the agent never reads from it.
- [`build_manifest.py`](../../tools/verusage_plus/build_manifest.py) — given a `mapping_<proj>.txt`, the unverified dir, and the upstream src tree, emits the manifest with strict suffix-match resolution. For task `vreplicaset_controller__proof__guarantee__guarantee_condition_holds`, only an `fn guarantee_condition_holds` in the unverified file AND in the upstream src tree resolves; helper fns in the same unverified file are NOT acceptable substitutes (an earlier loose match silently wrong-resolved AC targets to vstd_ext helpers). Multi-candidate resolution uses path-component scoring against the task's `__`-split prefix; the scoring treats `<stem>.rs` as a match for `<stem>` (so `commit_mask__impl__empty` resolves to `commit_mask.rs::empty`). Targets present in the mapping but absent from the current upstream HEAD (refactored away) are emitted as `# UNRESOLVED ...` comments; the strip script ignores them.
- [`build_pilot.py`](../../tools/verusage_plus/build_pilot.py) — renders `AGENTS.md` from [`agent_prompt.md`](../../tools/verusage_plus/agent_prompt.md) with `--var KEY=VALUE` substitutions. Required keys: `repo_path`, `verify_command`, `verify_dir`, `verify_setup`, `vstd_paths`. Writes `AGENTS.md` into the upstream repo root; caller commits it on the pilot branch. No `VERUSAGE_PLUS_TARGETS.txt` is emitted — the agent's scope is whatever the verifier reports, not a curated manifest (the harness keeps the per-project manifest under `tools/verusage_plus/` for stripping and scoring, out of the agent's view). The script rejects unknown `--var` keys and missing required keys, so passing the old `n_targets` / `initial_errors` raises a hard error rather than silently rendering.
- [`agent_prompt.md`](../../tools/verusage_plus/agent_prompt.md) — hardened agent prompt template. The file is **entirely the agent-visible prompt** — no meta-comment block at the top, since the rendered output goes verbatim into AGENTS.md in the pilot working tree (`build_pilot.py` only substitutes `{{...}}` variables; nothing is stripped). Keep it that way: any documentation about the template belongs here in the codebase index, not in the template body, so the agent doesn't read stale "this file is what the harness writes…" prose. The template covers `cargo verus verify`, `./build.sh ...`, and `./verus-mimalloc/verify.sh` flows by varying `verify_command` and `verify_setup`. The opening contract is "drive the verifier to `verified, 0 errors`" — the agent is given no error count, no target-function count, and no curated target list (a previous iteration shipped all three; they were redundant with the verifier's own output, went stale within seconds of the first edit, and decoupled the agent's self-reported scope from what was actually verifying). Key clauses:
  - The **output line** (`verification results:: <N> verified, 0 errors`) is the authoritative success signal, not the exit code: Verus exits non-zero even on a clean verification under `--crate-type lib + --compile` (Anvil's `anvil.rs` lib build) and aborts before printing the summary line when any errors exist.
  - **"Where to find things"** subsection up-front pins the two paths the agent should ever read from: `{{repo_path}}` (project source) and `{{vstd_paths}}` (vstd source). This was promoted from a buried "Permitted exceptions" bullet after Phase-3 AL/MA agents `find /`-walked NFS-stuck even with vstd paths listed in the forbidden-exceptions section. Surfacing the path with concrete `ls`/`grep`/`find` examples is the prompt-side remedy.
  - Forbid non-HEAD git refs (closes Phase-1 Vest cheat).
  - Forbid network except `verus-lang.github.io`.
  - Forbid `find /` and root-walks (Phase-3 NFS-hang remedy; reinforced by the new "Where to find things" guidance).
  - **Forbid silencing the verifier by hiding the work** — no deleting, renaming, or relocating functions; no signature / visibility / attribute changes that suppress errors; no `#[verifier::external_fn_specification]` or analogous opt-outs; no redirecting call sites past a function to make its errors disappear. Necessary now that the prompt no longer ships a curated target list — "fix all reported errors" is a slightly broader contract than "fill these listed bodies", and this clause closes the obvious loophole.
  - **Verifier-loop discipline** (Phase-3 lessons — see [`docs/verusage_plus/phase3_postmortem.md`](../../docs/verusage_plus/phase3_postmortem.md)): synchronous-oracle ban on "while the verifier runs" parallel-edits; error count must trend down across edits with rollback on regression; `tee /tmp/v.out` + grep the cache instead of re-running the verifier with new grep tails; `--verify-module`/`--verify-function` for per-iteration scoping with the full verify reserved for the closing run; `grep -rn 'pub proof fn '` teach-fishing recipe for vstd discovery.
  - **Stuck-out behaviour**: an unclosable target gets a one-line append to `SKIPPED.md` and the agent moves on (coverage > polish). Whole-run stuck → call `request_review.sh` and stop.
- [`request_review.sh`](../../tools/verusage_plus/request_review.sh) — agent-invokable from any cwd (the harness puts `tools/verusage_plus/` on PATH via `run_pilot.sh`). Takes a one-paragraph status, prints it to stdout (lands in the run transcript) and exits 0. The agent's prompt instructs it to stop issuing tool calls afterwards; a human watching the run sees the status in the transcript and decides whether to resume this pilot branch or close. No side effects on disk, no email — keeping the mechanism minimal because the supervisor is already watching the run.
- [`run_pilot.sh`](../../tools/verusage_plus/run_pilot.sh) — reusable launch driver. Per-run `launch.sh` files set six env vars (`RUN_DIR`, `FORK_REPO`, `RUN_NAME`, `BUDGET_USD`, `VERUS_BIN`, optional `VSTD_PREFIX` / `EXTRA_PATH` / `EXTRA_ENV` / `VERIFIER_CMD`) and `exec` this script. Driver does:
  - Wraps `claude` with `setsid` so it gets its own process group, then SIGKILLs the whole pgroup at script exit. Catches detached `find`/`grep` orphans (Phase-3 MA wedged 5 h on NFS; Phase-3 AL wedged 2 h before manual SIGKILL).
  - Runs `extract_turns.py` and `cheat_scan.py` (with `--vstd-extra-prefix $VSTD_PREFIX`) automatically post-exit. Closes the manual cheat-scan gap that operators had to remember through Phase 3.
  - When `VERIFIER_CMD` is set, runs it after the agent exits, captures stdout+stderr into `<run>/verifier_final.out`, and invokes `error_map.py` (manifest-less mode) to land `<run>/error_map.tsv` and a one-line summary in `<run>/error_map.summary`. This is the harness-side "stats from Verus" path — the final error count and the list of error-bearing functions come from the verifier on HEAD, independent of any pre-computed numbers and of the agent's self-report.
- [`extract_turns.py`](../../tools/verusage_plus/extract_turns.py) — renders a Claude stream-json transcript as a numbered, PWD-stripped turn sketch (THINK / TEXT / one-line tool-call) for human review. Each pilot's `launch.sh` runs it after the agent exits, writing `logs/turns.txt` next to `claude_run.jsonl`. Reusable on past runs: `python3 tools/verusage_plus/extract_turns.py <run>/logs/claude_run.jsonl`. **Subagent (`Agent` tool) child tool calls are NOT inlined** in the parent stream — turns.txt counts only parent activity; subagent edits are summarized as a single `Agent(...)` line. Inspect a subagent's transcript via the `~/.claude/projects/<proj>/<session_id>/tasks/<task_id>.output` files if needed. **Use `turns.txt` rather than `claude_run.jsonl` for any reading-by-eye task — the JSONL is large and noisy.**
- [`error_map.py`](../../tools/verusage_plus/error_map.py) — per-function verifier-error attribution. Two modes:
  - **Manifest-less** (default when `--manifest` is omitted): parse Verus output, walk every source file an error references, attribute each error to the enclosing function via brace-counted range parsing, and emit one row per error-bearing function. The summary on stderr — `total errors: N, distinct error-bearing functions: M, unattributed: U` — is the harness-side "stats from Verus" headline. `run_pilot.sh` invokes this mode automatically when `VERIFIER_CMD` is set.
  - **With `--manifest`**: same machinery, but one row per manifest target lemma (closed lemmas get `n_errors == 0`); the unattributed rows are per-file. Used post-mortem to cross-reference per-lemma lifecycle categories against final verifier outcome (see Phase-3 round 5 in [`docs/verusage_plus/phase3_postmortem.md`](../../docs/verusage_plus/phase3_postmortem.md)).
- [`cheat_scan.py`](../../tools/verusage_plus/cheat_scan.py) — scan a transcript for forbidden git/network/outside-repo tool calls. Exits 0 if clean, 1 if any flag. Run with `--repo <pilot_repo>`; pass `--vstd-extra-prefix <PATH>` (repeatable) to whitelist additional vstd paths. `run_pilot.sh` invokes this automatically; manual invocation pattern: `python3 tools/verusage_plus/cheat_scan.py <run>/logs/claude_run.jsonl --repo <fork> --vstd-extra-prefix <vstd-path>`. Built-in carve-outs:
  - vstd cache: `~/.cargo/registry/src/<index>/vstd-<version>/`
  - vstd git checkout: `~/.cargo/git/checkouts/verus-*/<rev>/source/vstd/`
  - claude harness scratch: `/tmp/claude-*/` and `~/.claude/projects/*/` (subagent tool-result files)
  - `git stash` (bare) is NOT flagged — it's working-tree state management, not a history read. `git stash show|apply|drop|branch|list` IS flagged.
  - `WebFetch` against `verus-lang.github.io` is permitted (Verus tutorial / reference / vstd rustdoc).
  Sanity check: Phase-1 Vest transcript still flags exactly 3 (correct: the 3 `git diff main...verusage_plus` calls). Run on every pilot before accepting the result.

## Per-pilot artifacts (`runs/verusage_plus/<proj>__<tag>__<UTC>/`)

Gitignored under the existing `runs/` rule. Each run dir contains:

- `launch.sh` — thin wrapper exporting the per-pilot env vars and `exec`ing `tools/verusage_plus/run_pilot.sh`. The driver invokes `claude --print --verbose --dangerously-skip-permissions --model claude-sonnet-4-6 --effort high --output-format stream-json --include-partial-messages --max-budget-usd <cap> --setting-sources project,local --strict-mcp-config --name <run-name>`. The `--setting-sources project,local` flag skips user `~/.claude/settings.json` (so personal `effortLevel` / `permissions` / `theme` don't bleed in) and the `--strict-mcp-config` flag skips user-installed MCP servers (so personal Gmail/Calendar/Drive tools don't land in the agent's tool list); both preserve Claude Code built-in agents, skills, and tools. `--bare` would be stricter but blocks OAuth, breaking claude.ai/Max billing on the maintainer's account. Auto-memory and CLAUDE.md auto-discovery have no per-flag disable; both happen to be empty on the maintainer's host but a future user must verify via `~/.claude/projects/<encoded-cwd>/memory/` and any `CLAUDE.md` / `AGENTS.md` reachable up from cwd.
- `logs/claude_run.jsonl` — raw Claude stream-json transcript.
- `logs/claude_run.stderr` — Claude stderr (usually empty).
- `logs/turns.txt` — rendered turn sketch (post-run; preferred reading surface).
- `cheat_scan.txt` — cheat-scan output (post-run, automatic).
- `REPORT.md` — written by the operator after the pilot exits: cost, duration, target-by-target outcome, cheat findings, honest-work signature, next-step proposal. Mirror an existing REPORT.md (e.g. `runs/verusage_plus/AL__all96__20260510T085834Z/REPORT.md`) for structure.

Cost extraction: Claude `--output-format stream-json` emits a single terminal `result` event with `total_cost_usd` and per-model `usage`. If the agent runs over `--max-budget-usd`, you may see TWO `result` events — a normal completion at the budget edge plus a follow-on `error_max_budget_usd` event with `num_turns: 1` and a tiny extra cost (~$0.5). Use the first `result` event for the experimental data. Opencode runs use [`tools/verusage_hands_off/compute_cost.py`](../../tools/verusage_hands_off/compute_cost.py) on `step_finish.part.tokens` events with a static price table.

## Branching convention (every fork)

```
main                              # mirror of upstream HEAD (no edits)
└─ verusage_plus[_<TAG>]          # stripped target bodies (one branch per target set)
   └─ pilot/<proj>-<tag>-<UTC>    # per-attempt; AGENTS.md at root (no target list — the agent works from verifier output)
```

For Anvil where AL and AC strip disjoint target sets, the fork has TWO strip branches off `main`: `verusage_plus_AL` and `verusage_plus_AC`. Each pilot only has its own targets stripped. For Vest and MA where there's one target set, the strip branch is just `verusage_plus`.

Commits on `verusage_plus*` branches use author `VeruSAGE+ harness <verusage-plus@example.local>`.

Phase 1 found that an agent will retrieve the original proofs via `git diff main...HEAD` if the prompt does not explicitly forbid historical-branch reads. The lightweight fix the maintainer chose is to forbid that in the prompt; the strong fix would be making the strip branch orphan-root or running each pilot in a throwaway clone with no other branches. Sandboxing (`bwrap`/`unshare`) is intentionally NOT used — the experiment evaluates how these agents behave the way they are normally invoked. Prompt-only has held through Phase 2 (Vest re-run), AC, MA, AL — `cheat_scan` flags zero real cheats on the four hardened runs.

## How to launch a new pilot

For each new project (`<CODE>`, lowercase upstream dir `<proj-dir>`, fork at `<fork>`):

```bash
REPO=/ssd1/sichangheagent/microsoft--verus-proof-synthesis
UTC=$(date -u +%Y%m%dT%H%M%SZ)

# 1. Resolve targets fresh from the VeruSAGE-Bench mapping. The manifest is
#    harness-side only (used by strip_proofs and post-run scoring); it is
#    not committed into the pilot repo.
python3 $REPO/tools/verusage_plus/build_manifest.py \
  --mapping  $REPO/benchmarks/VeruSAGE-Bench/source-projects/<proj-dir>/mapping_<code>.txt \
  --unverified-dir $REPO/benchmarks/VeruSAGE-Bench/source-projects/<proj-dir>/unverified \
  --src-root <fork>/src --repo-root <fork> \
  | tee $REPO/tools/verusage_plus/<code>_targets.txt

# 2. Cut a strip branch and apply the strip.
cd <fork> && git checkout main && git checkout -b verusage_plus[_TAG]
python3 $REPO/tools/verusage_plus/strip_proofs.py \
  --manifest $REPO/tools/verusage_plus/<code>_targets.txt \
  --repo <fork> \
  --unverified-dir $REPO/benchmarks/VeruSAGE-Bench/source-projects/<proj-dir>/unverified
git -c user.name='VeruSAGE+ harness' -c user.email='verusage-plus@example.local' \
  commit -am "verusage_plus[_TAG]: strip <N> VeruSAGE-Bench <CODE> targets"

# 3. Capture the strip-parent baseline from the verifier itself — initial
#    error count and the set of error-bearing functions both come from
#    Verus output, not from the manifest. The OUTPUT line is the truth,
#    not the exit code.
mkdir -p $REPO/runs/verusage_plus/_baselines
<verifier command> > $REPO/runs/verusage_plus/_baselines/<CODE>.out 2>&1 || true
python3 $REPO/tools/verusage_plus/error_map.py \
  --repo <fork> \
  --verifier-output $REPO/runs/verusage_plus/_baselines/<CODE>.out \
  --out $REPO/runs/verusage_plus/_baselines/<CODE>.tsv
# stderr line of the form
#   "total errors: N, distinct error-bearing functions: M, unattributed: U"
# is the baseline stat. Sanity-check M >= number of stripped target functions.

# 4. Cut the pilot branch and embed AGENTS.md only.
git checkout -b "pilot/<CODE>-allN-$UTC"
python3 $REPO/tools/verusage_plus/build_pilot.py \
  --template $REPO/tools/verusage_plus/agent_prompt.md \
  --out-dir <fork> \
  --var repo_path=<fork> \
  --var "verify_command=<from matrix>" \
  --var verify_dir=<fork> \
  --var "verify_setup=<one sentence about prebuilt deps + env vars>" \
  --var "vstd_paths=<path to bundled vstd>"
git add AGENTS.md && \
  git -c user.name='VeruSAGE+ harness' -c user.email='verusage-plus@example.local' \
    commit -m "pilot/<CODE>-allN: AGENTS.md at root"

# 5. Write a launch.sh by copying an existing one and adjusting the env vars.
#    Set VERIFIER_CMD to the same per-project command so run_pilot.sh runs
#    the final verifier + error_map.py automatically on exit.
mkdir -p $REPO/runs/verusage_plus/<CODE>__allN__$UTC/logs
cp $REPO/runs/verusage_plus/AL__all96__20260510T085834Z/launch.sh \
   $REPO/runs/verusage_plus/<CODE>__allN__$UTC/launch.sh
$EDITOR $REPO/runs/verusage_plus/<CODE>__allN__$UTC/launch.sh   # change FORK_REPO, RUN_NAME, BUDGET_USD, VERUS_BIN, VSTD_PREFIX, VERIFIER_CMD

# 6. Launch (synchronous; turns.txt + cheat_scan.txt + verifier_final.out +
#    error_map.tsv + error_map.summary land at exit).
bash $REPO/runs/verusage_plus/<CODE>__allN__$UTC/launch.sh

# 7. After agent exits, inspect the auto-produced artefacts.
cat $REPO/runs/verusage_plus/<CODE>__allN__$UTC/error_map.summary   # total errors / distinct fns
cat $REPO/runs/verusage_plus/<CODE>__allN__$UTC/cheat_scan.txt
cd <fork> && git add -u && \
  git -c user.name='VeruSAGE+ harness' -c user.email='verusage-plus@example.local' \
    commit -m "pilot/<CODE>-allN: agent edits"
# Compute close-rate by diffing the baseline TSV (step 3) against the
# pilot's error_map.tsv: lines present in baseline but absent (or with
# n_errors == 0) in the final TSV are closed functions. Then write
# REPORT.md by hand using an existing one as model.
```

## Validation policy

- **Correctness**: the verifier's `verification results:: <N> verified, 0 errors` line in stdout. Per-project verifier commands:
  - VE: `cd vest && cargo verus verify`
  - AC: `./build.sh vreplicaset_controller.rs --rlimit 50 --time --verify-module vreplicaset_controller`
  - AL: `./build.sh anvil.rs --crate-type lib --rlimit 50 --time`
  - MA: `VERUS_SINGULAR_PATH=$HOME/.nix-profile/bin/Singular ./verus-mimalloc/verify.sh` (after `./setup-libc-dependency.sh`)
- **Honest-work signature**: `git diff <strip_branch> HEAD --stat` should be non-trivial across the target files (Phase-1 Vest cheat produced 0 lines; honest pilots produce hundreds-to-thousands). The pilot tree contains only `AGENTS.md` on top of the strip parent, so ignore that one row visually.
- **Verifier-derived close-rate**: compare the baseline TSV under `runs/verusage_plus/_baselines/<CODE>.tsv` (produced post-strip) against the pilot's `error_map.tsv` (produced automatically when `VERIFIER_CMD` is set). A function present in the baseline that no longer appears, or that has `n_errors == 0` in the final TSV, is closed; the rest are open. Both numbers come from Verus output, not from the agent's self-report or from a curated manifest, so they are robust against the AC-style "consciously closed vs verifier-passing" divergence seen in Phase 3.
- **Cheat check**: `cheat_scan.py ... --vstd-extra-prefix <bundled-vstd-paths>`. Now invoked automatically by `run_pilot.sh`; its output lands in `<run>/cheat_scan.txt`. The agent's self-report per `agent_prompt.md` complements it but is not load-bearing.
- **Cross-check** (cheap, independent of cheat_scan): grep `turns.txt` for `benchmarks/`, `verified/`, `unverified/`, `mapping_<code>` — if zero hits, the agent never opened the answer key.

## Per-project toolchain matrix

| Code | Verus | Rust toolchain | Sibling deps | Notes |
|---|---|---|---|---|
| VE | prebuilt `0.2026.03.17.a96bad0` (`.local-tools/src/verus-2026-03-17/`) | `1.94.0` | — | `vstd = "=0.0.0-2026-03-17-2326"` pinned in `vest/Cargo.toml`. |
| AC | from-source verus-latest (`0.2026.05.08.3a09b49`, `.local-tools/src/verus-latest/source/target-verus/release/`) | `1.95.0` (+ `1.91.0` for verus's internal rustc) | sibling `/ssd1/sichangheagent/verus/` at tag `release/rolling/0.2025.11.30.840fa61` so `vstd = { path = "../verus/source/vstd" }` resolves | `build.md` pins an OLDER Verus that rejects current source (`final(self)@` syntax error); Anvil's CI actually uses tip-of-main verus. Verifier `./build.sh` ALWAYS exits non-zero; parse the stdout line. `src/deps_hack/target/debug/libdeps_hack.rlib` pre-built via `cd src/deps_hack && cargo build`. |
| AL | same as AC | same | same | Same `./build.sh` driver; AL uses `anvil.rs --crate-type lib`. |
| MA | from-source verus-latest **built with `--features singular`** | `1.95.0` | Singular 4.4.1 via `nix-env -iA nixpkgs.singular` at `~/.nix-profile/bin/Singular`; `./setup-libc-dependency.sh` pre-built `build/liblibc.rlib` | `VERUS_SINGULAR_PATH` must be exported in the launching shell. Without it, `integer_ring` proofs fail with `error: Please provide VERUS_SINGULAR_PATH`. |

Verus build-from-source: `cd .local-tools/src/verus-latest/source && bash -lc "source ../tools/activate && ./tools/get-z3.sh && vargo build --release --features singular"`. The pre-existing `.local-tools/build_verus_latest.sh` builds without `--features singular`; to re-enable Singular support after a clean rebuild, run vargo with the flag explicitly.

Each upstream pins its own Verus version through `vstd = "0.0.0-YYYY-MM-DD-HHMM"` in `Cargo.toml`, BUT in practice the projects whose `Cargo.toml` uses a path dep (`vstd = { path = "../verus/source/vstd" }`, e.g. Anvil) silently track tip-of-main verus, not the version named in `build.md`. Mismatched Verus rejects the source with `expected an expression` or `to dereference a mutable reference parameter in a postcondition...`.

## Manifest resolution caveat

The benchmark's `mapping_<proj>.txt` may reference functions that no longer exist in the current upstream HEAD (refactored / renamed / removed). `build_manifest.py` lists these as `# UNRESOLVED ...`; the strip drops them silently. Observed counts:

- VE: 22 / 22 resolved.
- AC: 49 / 63 resolved (14 fns removed in commit `cc8ab6ab`, May 7 2026 RMQ refactor).
- AL: 96 / 104 resolved (8 fns removed in upstream refactor).
- MA: 87 / 89 resolved (2 ambiguous: `config`, `layout__mod_mul-poly`).

Cross-checking the unresolved set against the upstream is worth doing if a future pilot drops to <70% resolution — it may indicate the wrong upstream commit, not real refactoring.

## Operational hazards

- **`find /` walks NFS and wedges.** On the maintainer's host there is one hard-mounted NFS export (`<redacted-nfs-ip>:/volume1/uscnsl-shared-storage1` at `/synology`, NFSv3 `hard,timeo=600,retrans=2`). `find /` walks into it; if the Synology stalls, the find blocks in `rpc_wait_bit_killable` until SIGKILL. SIGTERM (Claude Code's Bash timeout's first signal) doesn't unstick it. In Phase-3 MA an orphan kept the agent's parent process alive 5 h after the API run finished; in Phase-3 AL another orphan survived 2 h until manually killed. The maintainer chose **not** to sandbox (would diverge from how these agents are normally invoked); two layers of mitigation in place instead:
  - **Prompt**: `agent_prompt.md` now has a "Where to find things" subsection that names the two paths the agent should ever read from (`{{repo_path}}` and `{{vstd_paths}}`) with concrete `find`/`grep` examples, and the Forbidden section says `find /` will hang for hours. Both Phase-3 MA and AL agents `find /`-walked despite the original prompt's ban; they were looking for vstd source files (`bits.rs`, `map_lib.rs`) without knowing where vstd lived. Surfacing the path up-front, not in a forbidden-exception bullet, is the prompt-side cure.
  - **Driver**: `tools/verusage_plus/run_pilot.sh` wraps `claude` with `setsid` + a SIGKILL of the entire process group on script exit. Even if a future agent ignores the prompt, the orphan dies with the script.
- **Anvil verifier exits non-zero on green.** `./build.sh anvil.rs --crate-type lib --rlimit 50 --time` returns 1 even when stdout says `verification results:: 397 verified, 0 errors` — likely warnings-as-errors during the compile half of verus's verify+compile pipeline. The agent prompt names this explicitly so the agent doesn't conclude failure from rc.
- **MA agent regressed in Phase 3.** Final state had 244 errors vs 83 in the strip baseline — the agent introduced parse errors during an algebraic refactor and ran out of budget before fixing them. There's nothing wrong with the harness; this is a real domain-difficulty result that says `integer_ring`/bitvector/nonlinear domains are not within Sonnet-4.6-high reach at $60.

## Open infra items

- **Verus toolchain bootstrap.** A small shell script that, given a `vstd 0.0.0-YYYY-MM-DD-HHMM` string, fetches the matching `verus-<version>-x86-linux.zip` and `rustup toolchain install <toolchain>` (toolchain printed by `verus --version`). Saves manual work for the next 5 projects.
- **`build_verus_latest.sh` Singular flag.** The current script does NOT pass `--features singular`. Future Singular-needing pilots should rerun `vargo build --release --features singular` after any clean rebuild. Worth either patching the script or noting in a header comment.

## Pointers

- VeruSAGE-Bench (the dataset the strips come from): [`benchmarks/VeruSAGE-Bench/`](../../benchmarks/VeruSAGE-Bench/). The `mapping_<proj>.txt` files identify which functions to strip; `unverified/<task>.rs` files supply the stripped body.
- Older slice-based harness (kept for context, not used going forward): [`verusage-hands-off-pilot.md`](verusage-hands-off-pilot.md).
- Email helper used for human updates: `~/.config/helper.sh/email_me.py`. Always include PWD, never print body content.
