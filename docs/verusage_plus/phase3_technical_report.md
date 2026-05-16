---
name: VeruSAGE+ Phase-3 technical report
description: Compact research-style methods-and-results write-up of the four Phase-3 pilots; companion to `phase3_postmortem.md`.
type: report
---

# Behavioral correlates of success and failure in autonomous Verus proof completion

## Methods

We evaluated Claude Sonnet 4.6 (extended thinking, high effort, via the
Claude Code CLI with read/edit/bash and subagent-dispatch tools) on
four Rust/Verus repositories spanning three proof domains:
parser-combinator correctness (Vest, 22 target lemmas), Kubernetes
controller liveness (AC, 49; AL, 96), and a verified-allocator
polynomial-ring fragment (MA, 87). For each project an upstream
"strip-parent" commit removes the bodies of the target lemmas; the
agent starts from the strip parent with the project's existing
`AGENTS.md`, a generic VeruSAGE+ prompt, and the target manifest, and
is asked to restore proofs until the project's verifier script reports
success. No per-project tactic hints are supplied. Each pilot has a USD
budget cap (Vest $30, AC $40, MA $60, AL $80) and no wall-clock cap.

The full JSONL transcript of every assistant message and every
tool call/result is captured per pilot. We derive: (i) per-message
context size, taken as
`cache_read_input_tokens + cache_creation_input_tokens + input_tokens`
against Sonnet 4.6's 400 k window; (ii) for each bash invocation, a
`(core_command, pipeline_tail)` split, classifying consecutive verifier
calls as *same-core* when their core commands are byte-identical; (iii)
substring counts in verifier outputs for fixed phrases
(`cannot find function`, `expected ','`, `postcondition not satisfied`,
etc.); (iv) per-lemma lifecycle windows keyed by
`(file_basename, fn_name)`, recording parent-edit count, max
single-edit byte delta, first-edit event index normalised by pilot
total events, and whether any subagent dispatch prompt contains the
lemma's `fn_name`. From (iv) we define five mutually exclusive
*lifecycle categories*: ABANDONED (zero parent edits, never named in a
subagent), SUBAGENT_OR_NONE (zero parent edits but named),
PARENT_ONE_SHOT (one edit), PARENT_LIGHT (2–3), PARENT_HEAVY (≥4).

Final closure is measured externally: we re-run each project's verifier
on the agent's HEAD with `--multiple-errors 100`, parse every
`error[: <kind>] --> file:line:col`, and attribute each error to the
target lemma whose body brace-range contains the error line. A lemma
is *closed* iff no error is attributed to its body. Self-reported
closure is ignored; in AC it under-counted by ≈30 % because the agent
counted consciously-completed rather than verifier-passing lemmas.

## Results

**Aggregate.** The agent closed 143 of the 167 lemmas the verifier
successfully ran on (86 %) at $134.79 over 9 h 45 m. Vest 22/22 and AL
96/96 closed; AC 25/49; MA's verifier did not execute (see below). No
pilot exhibited verifier-bypassing behavior (no fabricated tool output,
no new `external_body`, no `requires`/`ensures` weakening vs the strip
parent).

**Joint behavioral signature.** Three orthogonal per-lemma features
separate green from non-green pilots simultaneously across the 254
target lemmas:

| Feature                                    | Vest (✓)| AL (✓) | AC (½) | MA (✗) |
|--------------------------------------------|---:|---:|---:|---:|
| Subagent-mention rate                      | 100 % | 98 % | 18 % |   1 % |
| Max-single-edit ≥ 10 kB (lemma count)      |   0 |  0 |  1 | 31 |
| First-edit event index, p50 (% of run)     | 88 % | 50 % | 32 % | 15 % |
| Per-message context size, mean (k tokens)  | 126 | 150 | 204 | 207 |
| Per-message context size, peak (k tokens)  | 213 | 279 | 366 | 367 |

None of the four features is individually sufficient. The joint
signature — late, small, subagent-backed edits at modest context
fill — characterises the closed pilots; early, large, parent-only edits
under near-full context fill characterise the failed pilot. AL's
heaviest-iterated lemma `temp_pred_equality` received 50 parent edits
(max Δ 3 996 B) and closed; MA's `commit_mask.rs::set` received 39
parent edits (max Δ 33 644 B) and failed: iteration *count* does not
discriminate, per-edit *size* does.

**Iteration cliff in AC.** The one pilot with non-trivial per-lemma
variance in both closure and lifecycle category shows a sharp
monotone close-rate gradient that saturates at two edits:

| Category | n | Closed | Open | Close rate |
|---|---:|---:|---:|---:|
| ABANDONED        | 19 |  3 | 16 |  16 % |
| SUBAGENT_OR_NONE |  2 |  1 |  1 |  50 % |
| PARENT_ONE_SHOT  | 20 | 13 |  7 |  65 % |
| PARENT_LIGHT     |  7 |  7 |  0 | 100 % |
| PARENT_HEAVY     |  1 |  1 |  0 | 100 % |

AC's 24 open lemmas decompose as 16 coverage-failure (never attempted;
concentrated in `resource_match.rs` 11/13 and `api_actions.rs` 4/4),
7 iteration-failure (one edit, verifier rejected, never revisited),
and 1 domain-difficulty. The 65 → 100 % step between one and two
iterations is the largest tactical-level gradient in our data.

**MA is verifier-blocked, not proof-broken.** The verifier on MA's HEAD
reports 245 errors with verus-time 0 ms: 244 are `cannot find function`
(E0425) downstream errors and 1 is a single `expected ','` parse error
in `bin_sizes.rs:1355:15`, inside `bin_size_result_mul8`. The public
functions are unchanged vs the strip parent; the cascade arises because
the `verus! { ... }` macro expansion fails partway through
`bin_sizes.rs` and items below the parse error are invisible to rustc.
MA's true per-lemma proof state is therefore *unknown*; the binding
constraint at exit is one parser ambiguity. Within-run verifier outputs
show MA also accumulating characteristic syntactic-cascade signals
throughout (43 `cannot find function`, 30 `mismatched types`, 28
`expected ','` events, together exceeding the 67
`postcondition not satisfied` events). AC's residual errors are
entirely Verus proof-level (25× `postcondition not satisfied`, 2×
`Could not automatically infer triggers`, 4× `assertion failed`, 1×
`precondition not satisfied`).

**Oracle synchronisation.** The phrase "while the verifier runs" (or
close paraphrases) occurs 0 times in Vest/AL/AC text events and 6 times
in MA (events E5989–E6261). Each MA occurrence is followed by an
`Edit` event issued before the previously-launched verifier call has
returned; the six occurrences bracket the sequence that produced MA's
first uncontrolled accumulation of untested edits.

**Reconnaissance shape in closed pilots.** Vest and AL spend the first
half of the transcript on reads and bash calls and concentrate
productive edits after a single subagent dispatch whose prompt embeds
(i) every target lemma name, (ii) relevant type/helper definitions
inline from project source, (iii) a per-lemma proof-strategy sketch.
The parent then applies the subagent's returned code as a sequence of
small edits. Vest's dispatch at event 3 449 returns "All proofs
verified" at event 3 909; AL's at event 1 385 is followed by 18
sequential parent edits in [1 440, 1 494]. AC achieves this only for
the `terminate.rs` cluster (9/9 closed via a dispatch at event 6 900);
its other subagents are exploratory and return prose. MA's two
subagents are narrow vstd-fact lookups returning prose, never
proof-strategy sketches; all MA proof writing is parent-issued.

**Verifier hygiene.** 78–94 % of consecutive verifier calls share the
same core command and differ only in the pipeline tail. The
`tee /tmp/foo`-then-`grep` pattern that caches the output once is used
in under 4 % of total calls (0/7/2/0 across Vest/AC/MA/AL). The
narrow-scope flag `--verify-module <mod>` is used 105/107 times in AL
and 0 times in AC and MA; AL's first narrow-scope call lands only at
event 2 353, by which point full-build errors have already fallen from
96 to 7. AL's per-call verifier output is 50–500 chars post-narrowing;
MA's full-build output is 1.5–5 kB per call. On MA's ≈120 s full-build
verifier the 59 redundant same-core calls correspond to ≈2 h of wall
time on a 4 h 52 m run.

## Caveats

Every pilot is a single run. Per-lemma features within a pilot are not
independent of parent-agent state. Edit byte deltas double-count edits
whose `old_string`/`new_string` spans multiple target lemmas; MA's
33 644-byte `commit_mask.rs` edit contributes 10 of the 31 ≥10 kB
entries, but the count remains nonzero after collapsing to unique
edits. Subagent-mention is a substring test on dispatch prompts;
manual inspection in AC and MA found no false positives. We make no
causal claim; the joint signature is consistent across four pilots and
three proof domains, but a forced-control study (prompt-induced
subagent dispatch vs direct editing on matched lemmas) would be needed
to establish it as causal rather than incidental.
