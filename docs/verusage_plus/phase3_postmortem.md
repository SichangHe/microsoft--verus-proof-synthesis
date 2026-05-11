# VeruSAGE+ Phase-3 post-mortem

Single source of truth for what we learned from the four Phase-3 pilots
(Vest re-run, AC, MA, AL) run with `claude --print --model claude-sonnet-4-6
--effort high` against four hardened VeruSAGE+ pilot branches. Two of four
green (Vest P2 22/22, AL 96/96), one partial (AC 17/49), one regressed (MA
83 errors at strip → 244 errors at exit). The analysis below is built from
the four `runs/verusage_plus/*/logs/claude_run.jsonl` transcripts; every
quantitative claim references the artefact line. Caveat: each pilot is one
run; the patterns below are inferences from N=1 per pilot, not statistical
results. The mechanisms are plausible and well-evidenced; the magnitudes
are not.

## Outcomes

| Pilot | Targets | Closed | Cost / cap | Wall | Cheat | Verdict |
|---|---:|---:|---:|---:|:---:|---|
| Vest P2 | 22 | 22 | $11.88 / $30 | 1 h 1 m | 0 | green |
| AC      | 49 | 17 | $31.16 / $40 | 2 h 3 m | 0 | partial; honest +1 777 lines |
| MA      | 87 | ~0 | $60.26 / $60 | 4 h 52 m | 0 | regression; 83 → 244 errors |
| AL      | 96 | 96 | $31.49 / $80 | 1 h 49 m | 0 | green |

Per-target $ for **closed** targets: AL $0.33, Vest-P2 $0.54, AC $1.83, MA ∞.

## Key takeaways

### 1. Sustained context wear is the strongest correlate of failure, with compaction as a sharp inflection

Across the four pilots, mean / p90 / peak context size in tokens
(`cache_read + cache_create + input` per assistant message;
`/tmp/anal/ma_ctx.log` and parallel extracts):

| Pilot | mean | p90 | peak |
|---|---:|---:|---:|
| Vest P2 (green) | 126 k | 202 k | 213 k |
| AL (green) | 150 k | 242 k | 279 k |
| **AC (partial)** | **204 k** | **347 k** | **366 k** |
| **MA (failed)** | **207 k** | **342 k** | **367 k** |

The two green pilots ran ~75 k below the two not-green pilots on every
percentile. Sonnet 4.6's context window is 400 k; AC and MA both spent
substantial time at 85–92 % full. **Inference**: extended attention over
~half-full or fuller windows is a likely degradation regime. We do not have
a controlled experiment for this; the pattern is correlational and N=1
per pilot.

**Compaction nuance.** MA's context dropped from 367 k peak at E16275 to
~41 k at E24935 (sampled assistant message) before climbing back to 150 k —
a clear compaction event. MA's catastrophic regression edit at E26946
(+6 697 B inserted as one Edit, taking the crate from a near-green state to
244 errors) happened **after** that compaction. **Belief, not proven fact**:
post-compaction the agent retained a summary of the prior turns but had
lost the texture of "I just made a fix that may have worked", which made
"start a large parallel rewrite" feel locally reasonable. The post-mortem
mechanism for the failed pilot is consistent across the transcript
evidence; whether compaction *caused* it or merely co-occurred would need a
forced-compaction control run.

AC by contrast operated chronically near the limit (p90 = 347 k) without a
visible compaction event. Its failure mode is smooth degradation rather
than reset-then-collapse. Both regimes are bad; the green pilots stayed in
neither.

### 2. The "while the verifier runs" parallel-edit pattern was the unique behavioral failure in MA

Six verbalizations of "while the verifier runs" or close paraphrases in
MA's transcript; **zero** in any other pilot
(`/tmp/anal/while_verifier2.log`). The mechanism, traced through events
E5976–E6292:

- E5976: agent runs the full `./verus-mimalloc/verify.sh` (60–300 s wall).
- E5989: text — *"Good, verification is running. Let me continue writing
  the remaining bin_sizes.rs proofs while it runs:"*
- E6007: parent inserts a new `pub proof fn idx_in_range_has_bin_size(...)`
  body. The verifier is still running from E5976.
- E6046: first verifier returns — **1 error** (one fix from green).
- E6211: edit (+390 B to `commit_mask.rs`) — the fix attempt.
- E6249: verifier kicked off; output piped through grep to 214 chars
  (count invisible).
- E6261: text — *"While the verifier runs, let me continue writing the
  remaining bin_sizes.rs proofs:"*
- E6275, E6292: two more `pub proof fn` insertions without confirmation
  that the E6211 fix worked.

The agent committed to a state-modification path without an oracle
confirmation that the previous fix worked. From here MA accumulates
untested edits, eventually issuing the E26946 +6 697 B regression edit.

Fix shipped: synchronous-oracle clause in `agent_prompt.md` —
*"After every verifier run, wait for the result before any further `Edit`,
`Write`, or other state-changing tool call. Do not start a second verifier
call while the first is in flight."*

### 3. Error count must trend down — agents treat phase progress as count progress

AC's regression edit (E8739, +244 B to `terminate.rs`) took the crate
from 4 errors to 34. Agent text immediately after at E8775: *"Good progress
— we're past compile errors. Now these are Verus verification errors. Let
me see the details:"* — the agent treated the *compile→verify-error*
transition as forward progress while ignoring the count jump
(`/tmp/anal/ac_regression.log`). It did not roll back.

**Inference**: absent an explicit rule, the agent's mental model of
"progress" is phase-ordered, not count-based. Compile-error → verify-error
is conceptually forward even when the count multiplies.

Fix shipped: *"Compare the new error count to the previous one. If the
count went up, your last edit regressed something — roll back if not
salvageable."*

### 4. `--verify-module` is a double dividend: faster cycle, smaller context

AL used `--verify-module` 105 times out of 107 verifier calls (62 % of all
verifier calls were narrowed-scope). MA used it 0. AC used it 0
(`/tmp/anal/verify_narrow.log`).

AL's per-cycle verifier output is 50–500 chars (one module's `verification
results::` line); MA's full-build output is 1.5–5 kB per call. Across MA's
76 verifier calls the cumulative verifier output added megabytes to its
context. AL's context stayed lean partly because of narrow verifies
producing tiny outputs.

Both `./build.sh` (AC/AL) and `./verus-mimalloc/verify.sh` (MA) pass
extra args through to verus via `"$@"` — the narrowing flag was available
in every project and never reached for outside AL. AL discovered the
technique organically at E2353 (~73 % of the way through its run), only
once errors had shrunk to the per-module scale where narrowing felt
natural; the AGENTS.md it was given did not recommend it.

Fix shipped: prompt now recommends `--verify-module <mod>` and
`--verify-function <fn>` during iteration, full verify for the closing
check.

### 5. Verifier re-running with grep-tail variations is a universal base-rate inefficiency

Across all four pilots, **78–94 % of successive verifier calls share the
same core command and differ only in the trailing `| grep …` filter**
(`/tmp/anal/redundancy.log`):

| Pilot | Verifier calls | Same-core consecutive | Rate |
|---|---:|---:|---:|
| Vest P2 | 27 | 24 | 89 % |
| AC | 48 | 45 | 94 % |
| MA | 76 | 59 | 78 % |
| AL | 107 | 87 | 81 % |

`tee /tmp/foo` to cache the verifier output once and grep the cache: used
0 / 2 / 7 / 0 times across the four pilots — under 4 % of total verifier
calls. **Estimate**: on MA's full-build verifier (mean ~120 s per call),
59 redundant calls ≈ ~2 h of wasted wall time, on a ~5 h run. The
estimate is rough (per-call wall varies); the qualitative claim is robust.

Fix shipped: prompt example pairs `tee /tmp/v.out` with `grep -E … /tmp/v.out`.

### 6. AC's failure shape is coverage, not domain difficulty

The 32 errors AC could not close are concentrated in three target files
that received **zero edits** (`/tmp/anal/ac_coverage.log`):

| File | Reads | Edits | Lemmas left empty |
|---|---:|---:|---:|
| `proof/liveness/resource_match.rs` | 15 | **0** | 13 |
| `proof/liveness/api_actions.rs` | 3 | **0** | 4 |
| `proof/guarantee.rs` | 3 | **0** | 1 |

The agent read `resource_match.rs` 15 times but never wrote to it. 18 of
the 32 unclosed errors are pure coverage failure; another 4 are
empty-bodied targets in `proof.rs`. The greedy schedule was
"finish-easy-files-first" with no preserved budget for the harder cluster.

Fix shipped: prompt now says *"If your last few attempts at a target
didn't reduce its error count, leave it and move on. Coverage across all
target files beats polishing one."* Plus a `SKIPPED.md` convention so a
successor session (or later, after closing other targets) can revisit
with context.

### 7. MA's 43 "cannot find function" errors signal helper-hallucination

MA's verifier output across the run accumulated 43 occurrences of
`cannot find function`, 30 `mismatched types`, and 28 `expected ','` parse
errors — together more than the 67 actual proof-level postcondition
failures (`/tmp/anal/err_classes.log`). The agent kept inventing helper
names it expected vstd to have. AL by contrast read vstd's `multiset.rs` 6
times before writing edits in that area.

**Belief, not proven**: hallucination correlates with reduced ability to
self-detect the same. Asking the agent to "watch for hallucinations" is
weak; the observable signal is repeated `cannot find function` and friends.

Fix shipped: the `request_review.sh` trigger conditions explicitly include
these error classes — *"the verifier keeps reporting `cannot find
function`, `mismatched types`, or `expected ','` … those errors have no
proof-level meaning and usually mean you are inventing names or syntax
that don't exist"*. Plus a teach-fishing grep recipe so the agent
enumerates real helpers before writing.

### 8. Subagent dispatch pattern groups by outcome

Three patterns observed (`/tmp/anal/subagents.log`):

- **Green pilots (AL, Vest P2)** — context-primed template-and-apply.
  Parent does reconnaissance, dispatches one subagent whose prompt
  *embeds the relevant type definitions inline* (AL: `Execution<T>`,
  `head`, `head_next` from `defs.rs`; Vest P2: `Seq::fold_left`'s
  right-recursive equation from vstd's `seq_lib.rs`), subagent returns
  full code, parent applies as many sequential `Edit` calls.
- **Partial (AC)** — 2 exploratory subagents ("read all 49 targets",
  "find references in other controllers") + 1 productive template-and-apply
  for terminate.rs only. Exploration ate the budget that could have
  driven a second template for `resource_match.rs`.
- **Failed (MA)** — 2 narrow vstd-fact lookups returning paragraphs not
  code. Parent then wrote all proofs solo, hitting the helper-hallucination
  and parse-error patterns.

This is descriptive, not prescriptive. The prompt does not mandate a
dispatch shape; pushing a specific pattern via the prompt risks
over-fitting to N=2 green cases. The teach-fishing grep recipe and the
SKIPPED.md / request_review.sh mechanisms address the underlying problems
(missing reconnaissance, getting stuck on one cluster) without
prescribing how the agent organizes delegation.

### 9. The benchmark deliberately withholds domain-tactic hints — this is a worst-case eval

MA mentioned `integer_ring` 59 times in its transcript and never used it
once: 0 `#[verifier::integer_ring]` annotations added, 0 `by(integer_ring)`
clauses written (`/tmp/anal/ma_deep.log`). The agent had the tactic in its
vocabulary but not in its repertoire for polynomial-equality goals on
`pow2(e+f) == pow2(e) * pow2(f)`-shape problems.

We deliberately do **not** ship a per-project hint that "for `pow2`
equalities, reach for `#[verifier::integer_ring]`". For benchmark purposes
that would be giving the agent the solution shape; the value of the
result is that it tells us *what tactics the agent reaches for absent any
hint*. The realistic deployment scenario for a project the agent has
never seen looks more like the benchmark than like a guided engagement.

The same logic applies to AC's `decreases (rank, …)` vocabulary in
`terminate.rs`. We note these as findings about the agent, not as harness
gaps to fix.

## Implementation done in response

Single commit `286419a4` on branch `explore`:

- `tools/verusage_plus/agent_prompt.md` — rewrites the *How to iterate*
  section with synchronous-oracle, error-count-trend, tee-then-grep,
  `--verify-module`, teach-fishing-grep clauses. Adds three short
  sections: *If a target won't close*, *If you're stuck across the run*,
  *Common pitfalls* (operator instructions extracted: tee large outputs,
  timeout/background, batch commands, frequently consider whether stuck).
- `tools/verusage_plus/request_review.sh` — agent-invokable: writes
  `STUCK.md` to the pilot working tree, emails the supervisor via
  `~/.config/helper.sh/email_me.py`, prints a stop instruction.
- `tools/verusage_plus/run_pilot.sh` — prepends `tools/verusage_plus/`
  to the agent's PATH so `request_review.sh` is invocable by name;
  exports `FORK_REPO` so child processes find the pilot tree.

No domain-tactic riders. No `VERUSAGE_PLUS_SCOPE.txt` pre-generation
(teach-fishing instead). No hard numeric triggers (the trigger conditions
for `request_review.sh` are framed as observable patterns:
"error count not decreasing across many calls", "no fresh ideas",
"verifier keeps emitting `cannot find function`/`expected ,`/`mismatched
types`").

## Validation plan

The next concrete experiments should test whether the prompt changes
move the metrics they target. **Not yet run**; awaiting maintainer
go-ahead.

1. **Re-run MA at $30** (lower than the failed $60) on a fresh pilot
   branch from the existing `verusage_plus` strip parent. Pass if any 3
   of:
   - `--verify-module` calls > 0 in the new transcript;
   - "while" not present in any text event;
   - "cannot find function" count in verifier output near zero;
   - any `#[verifier::integer_ring]` annotation added.

2. **Re-run AC at $40** (same cap as the failed run) on a fresh pilot
   branch from `verusage_plus_AC`. Pass if any 2 of:
   - edits on `resource_match.rs` > 0;
   - no run of >2 consecutive edits without an intervening verifier
     call that prints a parseable result;
   - `SKIPPED.md` written with at least one entry (evidence the
     "leave-and-move-on" pattern fired).

If both validators pass, proceed to Phase 4 (NO 29 → ST 63 → IR 118 →
OS 157 → NR 204) with the upgraded prompt baseline. For NR specifically,
plan to chunk the manifest across multiple pilot launches — at 204
targets the run is likely to exceed comfortable context headroom even
with the prompt fixes.

## What is deliberately out of scope

- **Sandboxing the agent** (`bwrap`/`unshare`). The experiment evaluates
  how these agents behave the way they are normally invoked.
- **Hard numbers as agent triggers.** The new prompt frames triggers as
  observable patterns ("no progress", "no fresh ideas") not magic
  numbers. Numbers in the prompt become anchors the agent argues against;
  patterns become guidance the agent can apply contextually.
- **Pre-generated VERUSAGE_PLUS_SCOPE.txt with all helper signatures.**
  Teach-fishing grep recipe instead. Same effect, smaller permanent
  artefact, generalizes to projects we don't anticipate.
- **Per-project domain-tactic hints.** See takeaway 9.
- **Edit-granularity caps.** The 8-consecutive-edits-then-verify pattern
  in AC (E8826–E10507) was inefficient but net-progressive (-2 errors).
  The hard rule is rollback-on-regression, not size cap.
- **Splitting tasks across multiple contexts via harness-side manifest
  chunking.** Useful for NR (204 targets) but not for Phase 3 re-runs.
  Defer to Phase 4 NR scheduling.

## Reproducing the analysis

The numbers above are reproducible from the four transcripts at
`runs/verusage_plus/{vest__all22__20260510T044733Z,AC__all49__20260510T085834Z,MA__all87__20260510T085834Z,AL__all96__20260510T085834Z}/logs/claude_run.jsonl`.

Analysis scripts used during the post-mortem were kept under `/tmp/anal/`
(ephemeral). They are not committed; the persistent record is this
document and the per-run REPORT.md files. If the analysis is rerun, the
key extractors needed are (a) per-event timeline (tool_use type + input
snippet); (b) per-verifier-call core-command vs grep-tail split;
(c) per-assistant-message `usage.cache_read_input_tokens +
cache_creation_input_tokens + input_tokens` for context size;
(d) phrase counts in verifier `tool_result` content for error-class
recurrence.
