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
- `tools/verusage_plus/request_review.sh` — agent-invokable: prints the
  agent's one-paragraph status to stdout (which lands in the run
  transcript) and exits. No side effects on disk, no email — the human
  supervisor is already watching the run, so the transcript is sufficient.
- `tools/verusage_plus/run_pilot.sh` — prepends `tools/verusage_plus/`
  to the agent's PATH so `request_review.sh` is invocable by name.

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

## Round 3 — how the agent actually solves vs fails proofs (sample-level)

The earlier sections describe *what* happened across the runs. This
section describes *how* the agent worked when zoomed in on individual
lemmas. 12 specific lemmas were sampled across the 4 pilots and their
full event windows extracted from `/tmp/anal/lc/`. Every claim below
names the lemma and event range that supports it. Caveat: 12 is small;
the pattern is consistent across all 4 pilots but should be treated as
mechanism hypotheses, not statistical results.

### 11. Successful iteration is rapid style-diversification, not parameter tweaking

The single hardest target in Vest P2 — `lemma_spec_serialize_length` in
`leb128.rs` — was attempted with **10 qualitatively different proof
shapes in ~110 events** (E3496–E3605, inside the subagent):

1. `reveal_with_fuel + assert(v >> 70 == 0) by (bit_vector)` (one-liner).
2. Helper `lemma_spec_serialize_length_by_bits(v, 64nat)`.
3. Counter-style helper `_aux(v, remaining)`.
4. Refactored signature on the same helper.
5. `lemma_spec_serialize_length_bounded(v, 10)` with explanatory comments.
6. Hand-unrolled 10 levels: `let v1 = v >> 7; let v2 = v1 >> 7; …`.
7. Refactored the unrolled version.
8. Dropped `decreases`, tried a different recursion structure.
9. "Countdown induction" with a `steps_remaining` parameter.
10. Final form: `lemma_spec_serialize_length_shift(v, 70u64, 10nat)`.

Each attempt changes proof *style* (direct vs helper vs unrolled vs
countdown), not just tactics. Successful iteration is closer to
breadth-first search over proof shapes than to gradient descent on one
shape.

AL's `always_p_or_eventually_q` shows the same pattern at the error
class level: from E2282 to E2830 the verifier reports trigger-can't-be-
inferred → triggers-can't-contain-lambda → antecedent-not-assumed →
postcondition-mismatch → precondition-not-satisfied → assertion-failed.
Each fix addresses a different class. **The agent moves between error
classes, not within one.**

The failing counter-example is MA: 28 `error: expected ','` parse
errors appeared in nearly identical shape across the run
(`/tmp/anal/err_classes.log`). The agent retried the same
`assert(...) by (nonlinear_arith) requires …` syntax repeatedly without
escaping into a different proof style.

### 12. Most of the green-pilot proof work happens *inside* subagents

Tracing `set_range` (Vest P2 utils.rs, trivially closed) and
`theorem_serialize_parse_roundtrip_helper` (Vest's hardest) shows the
same pattern at the parent level:

1. Parent reads target manifest (E47).
2. Parent reads relevant file once (E88 utils.rs; E153 repetition.rs).
3. Parent runs initial verifier; classifies errors per target in text
   (E3452 lists "1. `lemma_spec_parse_err_unrecoverable`: induction on
   n2 / 2. `lemma_parse_length_helper`: induction on n / … /
   4. `theorem_serialize_parse_roundtrip_helper`: induction on n / …").
4. Parent dispatches **one** subagent with the diagnoses embedded.
5. Parent waits; subagent returns "All proofs verified" at E3909.

Every edit and every verifier call for these lemmas lives **inside the
subagent**, invisible to the parent transcript. The parent has the
*diagnosis* and the *result*; the work is delegated. Same shape for AL:
E1385 dispatch with `Execution<T>` definitions embedded, parent then
applies 18+ sequential edits returned by the subagent (E1440–E1494).

Operational implication: **the agent's top-level reasoning is not where
the proofs are found**. It's where the problem is classified and the
context is assembled.

### 13. AC's `resource_match.rs` was decision-avoidance, not lack of time

The unclosed cluster in AC was studied across **7+ separate
read-sessions over 5 500+ events** without a single edit
(`/tmp/anal/lc/AC_resource_match.rs_*.txt`):

- E95–E127: reads the whole file in 4 chunks.
- E293–E526: reads it again in 4 chunks.
- E5246–E5267: reads it again.
- E5373: dispatches a subagent to *find references in other controllers*
  — receives sibling lemma signatures, no implementation plan.
- E5386–E5480: greps siblings' resource_match.rs, lists their
  `pub proof fn` names.
- **No `Edit` to vreplicaset's `resource_match.rs` ever fires.**

The agent recognized the work, gathered evidence, peeled off to do
something else — three times. Each return re-reads the file because the
prior reads' content is no longer in working memory. **Each return
costs reads, never gets to a write.** AC closed `terminate.rs` (via a
productive "Implement terminate.rs" subagent at E6900), so the agent
*knew how* to do the pattern. It just did it once instead of three
times.

The shipped "leave-and-move-on with SKIPPED.md" rule addresses the
symptom. The underlying mechanism (oscillation in and out of the same
file) needs the agent to *commit* via SKIPPED before pivoting; otherwise
the next pass re-pays the read cost.

### 14. MA spent ~20 000 events in "exploration mode" before the catastrophic edit

Between the second small edit on `bin_size_result_mul8` at E7354 and
the regression edit at E26946, MA's parent transcript shows hundreds of
`READ` and grep `BASH` events, almost no edits, and **repeated reads of
the same offsets**: E14320 → offset 1218, E14352 → 1186; E15790 →
1248, E16150 → 1248 again; E16439 → 1150, E16976 → 1240. The agent
re-reads material it already read.

At E26775 the agent texts: *"Given the complexity and budget
constraints, let me write the most concise algebraic proof for
`bin_size_result_mul8` by adding a helper lemma that directly proves
the key bound"* — and at E26946 commits a single +6 697 B Edit. That
single edit is larger than 90 % of MA's edits and breaks the build
into 244 errors.

The pattern: long exploration without action → late realization of
budget pressure → monolithic last-ditch attempt → catastrophic
regression. **The exploration phase is the actual failure window**, not
the regression edit. The regression edit was the panic move at the end
of a 20 000-event unproductive reconnaissance.

The shipped "no progress, no fresh ideas → request_review/skip" clause
addresses this. If the agent had ended the run at E15000 when the same
offsets were being re-read, the regression would have been spared and
the human would have a partial proof to resume from.

### 15. The agent's reasoning text is load-bearing in green runs, intent-only in failed

In every green case the parent text right before a productive Edit
*lists the strategy*:

- Vest P2 E3452: numbered list of 9 proof techniques, one per target.
- AL E1388: every empty fn enumerated with its `decreases` hint.
- AC E6903 (the *one* AC subagent that closed): 6 strategy bullets per
  fn, with proof skeletons.

In MA the comparable text exists (E26775) but is *intent-shaped* not
*strategy-shaped*: "let me write the most concise algebraic proof".
Forward-looking but no enumerable sub-steps. **Load-bearing reasoning
has a numbered or strategy-enumerated shape; non-load-bearing reasoning
is a single declarative intent.** When the agent's text doesn't
enumerate, the next edit tends to be monolithic.

This is a subtle prompt opportunity. The current prompt asks for
progress-tracking but not for enumerated strategy before a rewrite.
Adding *"Before any rewrite of more than a few lines, list the
sub-pieces you plan to write and the verifier check for each"* would
push the agent out of MA-style intent-only reasoning.

### 16. `--verify-module` adoption is outcome-conditional

AL's first `--verify-module` use is at E2353 — **after** the agent has
reduced full-build errors from 96 to 7 (~73 % through the run). Before
E2353 it ran full builds. Once errors were small enough that "verify
just this module" felt obvious, the narrow flag became the default.

MA never reached a state where narrowing felt natural (it spent most of
its run at full-build error counts of 9, 244, and unparseable
intermediate states from self-induced parse errors).

The shipped prompt recommends `--verify-module`. The rule the agent
needs is conditional: *narrow once errors are localized to a small set
of modules*. The current phrasing ("use these to keep the verify cycle
under ~30 s") is the right shape; no numbers needed.

### 17. Subagent dispatch shape is the strongest behavioral correlate of outcome

The 12 sampled lemmas, classified by the dispatch shape that actually
produced their edits:

| Lemma | Pilot | Dispatch shape | Outcome |
|---|---|---|:---:|
| `set_range` | Vest P2 | Recon-then-template-and-apply | closed |
| `theorem_serialize_parse_roundtrip_helper` | Vest P2 | Same; ~360 events of subagent zigzag inside | closed |
| `lemma_spec_serialize_length` | Vest P2 | Same; 10-style search | closed |
| `always_lift_state_unfold` | AL | Recon-then-template-and-apply (E1385) | closed |
| `always_p_or_eventually_q` | AL | Same; subagent then parent iterates | closed |
| `commutativity_of_seq_map_and_filter` | AL | Same | closed |
| `reconcile_eventually_terminates` | AC | Recon-then-template-and-apply (E6900) | closed |
| `stable_spec_is_stable` | AC | Same | closed |
| `lemma_from_after_send_list_pods_req_to_…` | AC | Reads only, no template-and-apply | NOT closed |
| `bin_size_result_mul8` | MA | No subagent for proof writing; parent monolithic | failed |
| `all_set` | MA | Parent only | failed |
| `lemma_pigeonhole_missing_idx_implies_double_helper` | MA | None — abandoned after 5 events | failed |

**Every closed sample (9 / 9) was reached via recon-then-template-and-
apply. Every unclosed sample (3 / 3) was reached without it.** N=12;
the consistency across 4 pilots and 3 different proof domains (parser
combinators, temporal logic, Kubernetes liveness) is the more
informative number than the count.

### Summary of round-3 implications

If only one rule could be added to the prompt today it would be:
**"When you have classified the errors and identified the right shape
of proof for each target, dispatch a subagent with the lemma names,
the relevant type/helper definitions inline, and a brief per-lemma
strategy. Apply the subagent's output as small per-lemma edits,
verifying after each."** Everything else (style-diversification,
verifier cadence, narrow-scope verifies) is downstream behavior the
subagent can do better than the bloated parent.

The current `agent_prompt.md` does not explicitly recommend this pattern.
Adding it would be ~10 lines and is consistent with the prior shipped
fixes.

## Round 4 — full-population sweep over all 254 target lemmas

Round 3 (N=12) gave a strong-looking pattern; the user (correctly)
pushed back on the sample size. Round 4 ran the same classification
over **every target lemma in every pilot** — 22 + 49 + 87 + 96 = 254
lemmas. Auto-classifier and per-pilot TSVs at `/tmp/anal/batch/`.
Numbers below are population values, not samples.

### 18. Subagent-mention rate is the strongest single predictor of outcome

For each target, we asked: did the agent ever dispatch an `Agent`/`Task`
subagent whose prompt input mentions this lemma's `fn_name`? Results
across **all 254 lemmas**:

| Pilot | Targets | Mentioned in a subagent dispatch | Rate |
|---|---:|---:|---:|
| Vest P2 (green) | 22 | 22 | **100 %** |
| AL (green) | 96 | 94 | **98 %** |
| AC (partial) | 49 | 9 | 18 % |
| MA (failed) | 87 | 1 | 1 % |

This is the cleanest separator I found in the entire analysis. The two
green pilots ran a subagent prompt whose body explicitly names virtually
every target lemma; the failed pilot named one; the partial pilot named
the ones that closed (terminate.rs cluster, 9 of 9) and not the ones
that didn't (resource_match.rs / api_actions.rs / guarantee.rs).
**Subagent-mention is essentially the "did the agent dispatch the
template-and-apply pattern for this lemma" indicator at scale.**

### 19. Max-single-Edit size is a 31×-vs-0 signal between green and failed

For each lemma we computed `max_edit_delta` = the largest absolute Δ
across all parent-level Edits whose old or new string contained the
fn name. Distribution by bucket across the 254 lemmas:

| Pilot | <100 | 100–499 | 500–999 | 1k–2k | 2k–5k | 5k–10k | ≥10k |
|---|---:|---:|---:|---:|---:|---:|---:|
| Vest P2 (green) | 4 | 8 | 3 | 5 | 1 | 1 | **0** |
| AL (green) | 9 | 34 | 25 | 12 | 13 | 3 | **0** |
| AC (partial) | 21 | 2 | 2 | 6 | 6 | 11 | 1 |
| MA (failed) | 16 | 5 | 4 | 9 | 12 | 10 | **31** |

**Zero lemmas in either green pilot had a single Edit ≥10 kB.
31 of MA's 87 lemmas did.** AC has 1.

The shape difference is also informative. AL's distribution peaks at
100–999 B (=lines of proof scope); MA is bimodal — many tiny edits
(abandoned or trivial) and many >5 kB / >10 kB (monolithic), with a
relative gap in the middle. Healthy iteration in Verus looks like a
heap of 100–1 000 B edits; failure looks like a few 10 kB+ rewrites.

(Caveat: when one parent Edit replaces a region containing several
target lemma definitions, all those lemmas inherit the same large
`max_edit_delta`. The MA `commit_mask.rs` 33 644 B edit appears 10
times because it spanned ten lemma names. The qualitative point holds:
the agent did write a single 33 kB block.)

### 20. First-edit timing — green pilots delay edits until reconnaissance completes

For each lemma we recorded the event index of its first parent Edit (if
any), normalised by total events in the pilot. Median across each pilot:

| Pilot | p25 | p50 (first-edit median, as % of run) | p75 | n |
|---|---:|---:|---:|---:|
| Vest P2 | 88 % | **88 %** | 89 % | 19 |
| AL | 46 % | **50 %** | 55 % | 95 |
| AC | 29 % | 32 % | 60 % | 28 |
| MA | 7 % | **15 %** | 23 % | 79 |

The two green pilots' first edits land in the middle-to-late part of
each run; MA's land in the first quarter. **The agent's edit rate is
back-loaded in green pilots and front-loaded in failed.**

The mechanism is consistent with takeaway 18: in green pilots, the
parent agent spends the first half of the run on reconnaissance and
preparation of the subagent's prompt; the productive edits come after
the subagent returns. In MA the agent skips this phase and starts
writing proofs in the first ~15 % of the run, before it has assembled
enough context.

Vest P2's extreme 88 % is the limiting case: 19 of its 22 lemmas have
ZERO parent edits during the first 75 % of the run, because Vest's
parent does all proof work inside its single subagent. The 3 lemmas
with no parent edit at all (utils.rs `compare_slice`, `init_vec_u8`,
`set_range`) were finalised entirely inside the subagent and never
touched by the parent.

### 21. Per-category outcomes across all 254 targets

Auto-classifier categories: ABANDONED (0 parent edits, never mentioned
in a subagent), SUBAGENT_OR_NONE (0 parent edits but mentioned in
subagent), PARENT_ONE_SHOT (1), PARENT_LIGHT (2–3), PARENT_HEAVY (≥4).

| Pilot | ABANDONED | SUBAGENT_ONLY | ONE_SHOT | LIGHT | HEAVY |
|---|---:|---:|---:|---:|---:|
| Vest P2 (22) | 0 | 3 | 9 | 7 | 3 |
| AL (96) | 0 | 1 | 41 | 35 | 19 |
| AC (49) | **19** | 2 | 20 | 7 | 1 |
| MA (87) | **8** | 0 | 30 | 27 | **22** |

The AC ABANDONED breakdown by file matches the round-3 finding exactly:
**11 of the 13 lemmas in `resource_match.rs`, all 4 of `api_actions.rs`,
3 of 5 in `liveness/proof.rs`, the 1 in `guarantee.rs`** — 19 lemmas
the agent never wrote a body for. The 2 mentioned-in-subagent entries
in resource_match.rs were named by AC's exploratory subagent (E5373:
"find references in other controllers") but never reached the
template-and-apply dispatch stage.

MA's PARENT_HEAVY count (22) is the highest of any pilot. The agent
edited the same lemma 4+ times in 22 cases — and yet nothing in MA
closes. **Heavy parent iteration without subagent backing is
counter-productive**: it correlates with the helper-hallucination /
parse-error patterns documented in earlier sections.

### 22. AL's heavy-iteration lemmas all closed; MA's all failed

AL's PARENT_HEAVY entries (19 lemmas):

| Edits | Max Δ | Lemma |
|---:|---:|---|
| 50 | 3 996 | `temp_pred_equality` |
| 44 | 2 405 | `execution_equality` |
| 39 | 2 405 | `entails_apply` |
| 11 | 1 982 | `tla_forall_always_equality` |

All 19 closed (AL was 96/96 green). The key shape: **many small edits,
none over ~4 kB, all dispatched via the subagent template-and-apply
pattern at E1385**. The 50-edit `temp_pred_equality` is the limit case
of healthy convergent iteration.

MA's PARENT_HEAVY entries (22 lemmas):

| Edits | Max Δ | Lemma |
|---:|---:|---|
| 39 | **33 644** | `commit_mask.rs::set` |
| 21 | **33 644** | `commit_mask.rs::lemma_view` |
| 20 | **33 644** | `commit_mask.rs::lemma_is_bit_set` |
| 13 | 686 | `bin_sizes.rs::idx_in_range_has_bin_size` |

The MA agent's 39-edit `set` in `commit_mask.rs` is the *opposite*
shape of AL's 50-edit `temp_pred_equality`: same total iteration
count, but a 10× larger Max Δ. The 33 644 B figure is one Edit
replacing a multi-lemma block. **Same effort, very different edit
shape, very different outcome.**

### 23. Vest P2's success pattern is even more extreme than round 3 suggested

Of Vest P2's 22 targets:

- 3 (`compare_slice`, `init_vec_u8`, `set_range`) have **zero parent
  edits at all** — fully resolved inside the subagent's context.
- 19 are touched by the parent **after the subagent dispatch at E3449**
  (the parent applies the subagent's code as sequential Edits).
- 22 of 22 are mentioned by name in the subagent's prompt.

The Vest parent transcript shows essentially the "delegated solve"
shape end-to-end: read → diagnose → one subagent → apply → done. The
parent never iterates on a target without the subagent's plan as input.

### 24. Synthesising the population-level pattern

Across all 254 targets, the green vs. not-green separation is
strongest along three axes simultaneously:

| Metric | Vest P2 | AL | AC | MA |
|---|---:|---:|---:|---:|
| Subagent-mentioned rate | 100 % | 98 % | 18 % | 1 % |
| Max-Edit ≥ 10 kB count | 0 | 0 | 1 | **31** |
| First-edit p50 (% of run) | 88 % | 50 % | 32 % | 15 % |

None of these is a *single* sufficient cause — but the combination is
the failure signature. **Successful pilots dispatch a context-loaded
subagent that names the target lemmas, then apply small edits late in
the run. Failed pilots edit early, often without a subagent, with
periodic monolithic rewrites.**

This is essentially the same conclusion as round 3, but resting on
N=254 instead of N=12. The single-rule prompt addition recommended at
the end of round 3 — explicit "recon-then-template-and-apply" pattern
in `agent_prompt.md` — is the change with the largest expected
behavioral lift. Adding edit-size discipline ("split rewrites larger
than ~2 kB into multiple `Edit` calls") is the second-largest.

### 25. Things the population sweep ruled in vs out

- **In**: the recon-then-template-and-apply shape is the strongest
  green-correlate. 254-lemma confirmation.
- **In**: the edit-size 10 kB cliff is real and quantified.
- **In**: the front-loaded vs back-loaded edit timing pattern.
- **Out**: edit *count* per lemma is not by itself a failure signal —
  AL has 19 lemmas with ≥4 edits and they all closed. The shape of
  those edits (size, subagent backing) matters more than the count.
- **Out**: the round-2 "8 consecutive edits without verify" pattern in
  AC is real but only 1 of 49 lemmas (AC's PARENT_HEAVY count). The
  finding is texture, not a population-scale failure mode.
- **Open**: per-lemma closed/not-closed status (the population sweep
  measures *edit behavior*, not *verifier outcome*). The two green
  pilots are 100 % closed by construction. AC's 17/49 and MA's ~0/87
  splits are at the run level, not per-lemma; mapping each lemma to
  closed/open status would need a per-lemma final-verifier-error map,
  which can be built but wasn't for this round. **Built and closed in
  round 5 below.**

## Round 5 — per-lemma final-verifier-error map

The S4 task deferred at the end of round 4. Built a proper tool,
`tools/verusage_plus/error_map.py`, that re-runs each pilot's verifier
on the pilot-branch HEAD with `--multiple-errors 100`/`300`, parses
every `error[: <kind>] --> file:line:col` triple, walks the source
files with brace-counting to find each target lemma's line range, and
attributes errors to the lemma whose body contains the error line.
Output: per-pilot TSV (`/tmp/anal/error_map/{AC,MA}.tsv`) plus a
cross-reference TSV joining the lifecycle category with the verifier
outcome (`/tmp/anal/joined/{AC,MA}.tsv`).

Vest P2 (22/22 verified, 0 errors) and AL (397/0 errors at exit) are
100 % closed by construction; the tool isn't re-run on them.

### 26. AC closed **25 of 49** target lemmas, not 17

The Phase-3 REPORT.md for AC and the agent's final summary both said
"17 of 49 closed". Re-running the verifier on the pilot's HEAD with
`--multiple-errors 100` and attributing each of the 36 errors to a
target lemma reveals **25 closed, 24 open**. Effective close rate
51 %, not 35 %. The discrepancy comes from lemmas the agent never
narrated about — their stripped bodies happen to be auto-verifiable by
Verus (e.g., several spec lemmas with vacuous postconditions). The
agent's self-report counted *consciously-closed* lemmas, not
*verifier-passing* ones.

### 27. AC's 24 open lemmas decompose cleanly by lifecycle category

Joining the per-lemma error-map TSV with round-4's per-lemma
lifecycle categories produces this cross-table for AC:

| lifecycle category   | N  | CLOSED | OPEN | close rate |
|----------------------|---:|------:|----:|-----------:|
| ABANDONED            | 19 |     3 |  16 |     15.8 % |
| SUBAGENT_OR_NONE     |  2 |     1 |   1 |     50.0 % |
| PARENT_ONE_SHOT      | 20 |    13 |   7 |     65.0 % |
| PARENT_LIGHT (2–3)   |  7 |     7 |   0 |    100.0 % |
| PARENT_HEAVY (≥4)    |  1 |     1 |   0 |    100.0 % |

Decomposition of the 24 open:

- **16 are ABANDONED-OPEN** — agent never wrote a line. Located in
  `resource_match.rs` (11), `api_actions.rs` (4), `proof.rs` (3),
  `guarantee.rs` (1).
- **7 are PARENT_ONE_SHOT-OPEN** — agent wrote one edit, verifier
  rejected, agent moved on. 5 in `liveness/proof.rs`, 1 in
  `helper_invariants/proof.rs` (×4 actually), 1 in `spec.rs`, 1 in
  `terminate.rs`. Of these 7 errors: 2 are "Could not automatically
  infer triggers for this quantifier" (single-tactic fix); 5 are
  "postcondition not satisfied" (proof-body insufficiency).
- **1 is SUBAGENT_OR_NONE-OPEN** — mentioned in a subagent prompt
  but never edited.

The close-rate gap **65 % at one edit → 100 % at two edits** is the
strongest tactical signal from round 5. The 7 PARENT_ONE_SHOT-open
lemmas are not necessarily harder than the 7 PARENT_LIGHT closures;
they just got abandoned after the first verifier rejection.

### 28. AC's failures decompose 23 of 24 into process discipline, 1 into real difficulty

- 16 ABANDONED-open: coverage / scheduling failure.
- 7 PARENT_ONE_SHOT-open: iteration failure.
- 1 SUBAGENT_OR_NONE-open: domain-difficulty failure.

≈ 96 % of AC's open lemmas are attributable to process choices the
agent made, not to inherent proof difficulty.

### 29. MA's "244 errors" is **one root parse error cascading**

Re-running the MA verifier on HEAD gives 245 errors. Of those:

- **1** is a target-lemma error: an assertion failure in
  `bin_size_result_mul8`, `bin_sizes.rs`.
- **244** are unattributed downstream errors:
  - 157 × `cannot find function size_of_bin in this scope`
  - 17 × `cannot find function valid_bin_idx`
  - 14 × `cannot find function smallest_bin_fitting_size`
  - 10 × `cannot find function bounds_for_smallest_bin_fitting_size`
  - 9 + 8 × `pfd_lower` / `pfd_upper`
  - long tail of "cannot find" for `slice_bin`, `idx_in_range_has_bin_size`,
    `size_of_bin_mult_word_size`, `lemma_bin_sizes_constants`, etc.
  - **1 × `expected ','` in `bin_sizes.rs:1355:15`** — the only
    actual parse error.

Inspection shows the public functions are still defined in
`bin_sizes.rs` at HEAD (`pub open spec fn size_of_bin`, etc.
unchanged vs strip parent). So the downstream files aren't broken
because someone deleted public functions; they're broken because the
`verus! { ... }` macro expansion fails partway through `bin_sizes.rs`,
and the items below that point are invisible to rustc. That cascades
into 244 `cannot find function` reports across files that call into
`bin_sizes.rs`.

**Verus's verification-time reported as `0 ms`**. The verifier never
got past rustc; no proof was ever actually checked.

### 30. MA's actual proof state is **unknown**, not "244 broken proofs"

The error_map for MA reports 86 of 87 target lemmas with 0 attributed
errors. **This is misleading**: the verifier didn't run on those
lemmas, so "no error attributed" reflects only that no rustc error
fell inside the line range. The earlier narrative "MA produced 244
broken proofs" is wrong; the real state is "MA produced **0
actually-verified proofs** because rustc rejected the file".

A scratch-worktree experiment attempted to bypass the parse error.
Reformatting the broken inline `assert(P) by (T) requires X, Y;`
at line 1353 into vstd's multi-line `requires` block syntax, then
replacing it with `assume(...)`, did NOT eliminate the parse error
— the parser still reports `expected ','` at line 1355:15. The
actual root parse error is somewhere earlier in
`bin_size_result_mul8` / `size_of_bin_ge_formula` (10 other
inline `assert ... by (T) requires X, Y;` patterns the agent
introduced live in the file), in a state-carrying syntactic context.
Locating the precise root would take more time than this analysis
warrants — but the structural finding holds.

### 31. The agent's error-count monitor over-reported by ~244 ×

When MA's trajectory went `1 → 244` near the end (the regression
from round 1's finding 2), the agent observed "245 errors after this
edit" and reasonably concluded its rewrite was catastrophic. But all
but ~1 of those errors were a downstream cascade of a single root
parse error introduced by that edit.

The agent's local model "error count ≈ count of broken proofs" fails
at the rustc-cascade boundary: one bad macro expansion produces
N × callsites of errors.

This recasts MA's failure mode:

- **Earlier framing**: agent fixed 27 of 28 parse errors during
  iteration, then introduced a new wave of 244 *proof-level*
  regressions. Recovery would require fixing 244 individual proofs.
- **Round-5 framing**: agent fixed 27 of 28 parse errors, was left
  with 1 stubborn parse error that masquerades as 244 downstream
  errors. **Recovery would require fixing 1 parse error**; the
  verifier could then run and reveal whatever the *actual* number of
  proof failures is.

The actual proof-failure count after a clean parse could be small or
large — MA's domain (polynomial-ring / pow2 arithmetic) is hard, and
the agent never reached for `integer_ring`. But at exit the binding
constraint was a single parser ambiguity, not a wave of broken
proofs.

### 32. Error-class signal is qualitatively different for MA vs AC

AC's 36 errors:
- 25 × `postcondition not satisfied` (proof body too weak)
- 4 × `assertion failed`
- 1 × `precondition not satisfied`
- 2 × `Could not automatically infer triggers for this quantifier`

All Verus proof-level. The agent's edits parse; the prover rejects
the goal.

MA's 245 errors:
- 244 × rustc-level `cannot find function ... in this scope` (E0425)
- 1 × `expected ','` (parse error)

All rustc/parser-level. No proof check has happened.

The qualitative difference matters for tooling:

- AC's residual work is "write better proofs" — domain content.
- MA's residual work is "make the file parse cleanly" — syntactic
  cleanup, then the unknown.

A pre-commit check that *would have caught MA at the first
regression* is "run rustc on the file before re-running verus; if
rustc-level error count increased, roll back the edit." A one-line
addition to the iteration loop that needs no Verus-level understanding.

### 33. Iteration is the cheap fix; in AC's domain it works at 100 %

AC's close rate increases monotonically with iteration count:

| iteration count | close rate |
|----------------:|----------:|
| 0 (ABANDONED)   |       16 % |
| 1 (ONE_SHOT)    |       65 % |
| 2–3 (LIGHT)     |      100 % |
| ≥4 (HEAVY)      |      100 % |

The single strongest tactical signal in round 5. For AC's domain
(liveness / TLA invariants), the cost of "do one follow-up edit when
verifier rejects" is small relative to the benefit. The 7
PARENT_ONE_SHOT-open lemmas would likely have closed at the same
100 % rate as PARENT_LIGHT had the agent stayed on them for one more
verify-edit-verify cycle.

MA's analogous cross-table shows close rates near 100 % across all
categories, but that's an artifact (the verifier didn't run); MA
gives no analogous evidence on iteration ROI.

### Cross-pilot summary at round 5

| pilot   | targets | closed | open | closure |
|---------|--------:|-------:|----:|--------:|
| Vest P2 |      22 |     22 |   0 |    100 % |
| AC      |      49 |     25 |  24 |     51 % |
| MA      |      87 | unknown (verifier blocked by 1 parse-error cascade) | — | — |
| AL      |      96 |     96 |   0 |    100 % |

Phase 3's net measurable closure across the 167 verifiable targets:
**143 of 167 closed (86 %)**, with MA's 87 targets unverifiable due
to one upstream parser break.

### Three new rules emerge from round 5

Separate from rounds 1–4's recommendations, in priority order:

1. **Iterate at least twice per lemma before moving on.** The
   PARENT_LIGHT close rate at 100 % vs PARENT_ONE_SHOT at 65 % is
   the strongest tactical signal. Targets 7 of AC's 24 open lemmas
   directly. Cheapest possible prompt change.
2. **Pre-verify with rustc before re-running Verus.** After each
   non-trivial edit (e.g. >200 bytes, or edits to `requires` /
   `ensures` / signatures), run `cargo check` or the equivalent
   rustc-only invocation to detect parser / type cascades early.
   If rustc-level error count *increases* materially, the edit broke
   compilation and should be reverted. **This rule alone would have
   caught MA's regression and let the agent recover.**
3. **Read error-count jumps >10 × as ambiguous, not as catastrophic
   proof failure.** If the error count multiplies, the most likely
   cause is a parser / type / macro cascade, not 240+ new proof
   failures. The agent's response should be "find the one bad token
   I just introduced", not "rewrite 244 proofs".

(P1–P5 from round 1 remain complementary; this is a new layer of
iteration-discipline + diagnostic-discipline rules.)

### Tool & artefact pointers

- `tools/verusage_plus/error_map.py` — the per-lemma
  error-attribution tool. Module-doc at top; takes manifest, repo,
  verifier-output, out-TSV.
- `/tmp/anal/verify/{AC,MA}.out` — full verifier output captured
  for this round.
- `/tmp/anal/error_map/{AC,MA}.tsv` — per-lemma error rows.
- `/tmp/anal/joined/{AC,MA}.tsv` — lifecycle × error_map join.
- `/tmp/anal/crossref.log` — printed cross-tables (per-category,
  per file, by subagent involvement).
- `/tmp/anal/ma_root.py`, `/tmp/anal/verify/MA_fix*.out` — root-cause
  experiment evidence for the MA cascade.

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
recurrence; (e) per-lemma life-cycle window keyed by `(file_base,
fn_name)` for sample-level traces (the `/tmp/anal/lifecycle.py`
extractor used in round 3).
