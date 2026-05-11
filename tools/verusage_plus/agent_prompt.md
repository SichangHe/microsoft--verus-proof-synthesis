You are repairing Verus proofs in a real Rust workspace. {{n_targets}} `proof` / `spec` function bodies in this repo have been stripped; the current verifier reports {{initial_errors}} errors. Write proofs, loop invariants, and ghost annotations until the verifier reports `verified, 0 errors`. The list of targets (one `<file>\t<fn>` per line) is at `VERUSAGE_PLUS_TARGETS.txt` in the repo root.

Run the verifier with `{{verify_command}}` from `{{verify_dir}}`. The authoritative success signal is the stdout line `verification results:: <N> verified, 0 errors`. Verus's exit code is unreliable — it may exit non-zero on a clean verification and may abort before the summary line when errors exist. Trust the output, not the exit code. {{verify_setup}}

Edit target function bodies and add new helper `proof fn` lemmas in the same file. Do not change other functions' signatures, `requires` / `ensures` clauses, or executable behavior. Do not change Verus, the Rust toolchain, or any pinned dependency files (`Cargo.toml`, `rust-toolchain.toml`, `vstd` path deps).

Code lives in `{{repo_path}}`. The vstd source — `Multiset`, `Set`, `Seq`, `u64_leading_zeros`, the bitvector / nonlinear lemma library, `assert_by_compute`, the `lemma_*` family — is at `{{vstd_paths}}`. Don't memorize vstd; query it (`grep -rn 'pub proof fn \|pub spec fn ' {{vstd_paths}} | head -50`, then read specific files). Reading existing usages elsewhere in `{{repo_path}}` is often the quickest way to learn a helper's calling shape.

# Forbidden — automatic disqualification

- **No non-HEAD git state.** No `git log` / `show` / `diff` / `checkout` / `stash show` / `reflog` / anything against any branch, tag, ref, commit, stash, or worktree other than the current `HEAD`. No reads under `.git/`. The proofs you're asked to write existed earlier in this repo's history; consulting them in any form is cheating.
- **No network**, one exception: you may fetch from `verus-lang.github.io` (Verus tutorial / reference / `vstd` rustdoc). Everything else is off-limits — no `curl` / `wget` / `git fetch` / `cargo search` / `cargo fetch` / `gh` / web search / web fetch / any URL.
- **No reads outside the repo** beyond `{{repo_path}}` and `{{vstd_paths}}` (plus `~/.cargo/registry/src/<index>/vstd-<version>/` when a Cargo-pinned vstd is present). No sibling clones, no parent directories, no system locations that might mirror this code.
- **No `find /` or root-walks.** Slow on this host; will wedge for hours on a hung NFS mount. The two paths above cover every legitimate lookup.
- **No proof shortcuts**: no `assume`, `admit`, `proof_from_false`, `arbitrary`-as-shortcut, new axioms, `unimplemented!`, or new/existing `#[verifier::external_body]`. Don't weaken or delete `requires` / `ensures`.

We rely on your honesty rather than a checker. If you couldn't avoid a forbidden construct, weakened any postcondition, or looked up an answer instead of deriving it, state it plainly in your final summary. `verified, 0 errors` is necessary but not sufficient — the run is only valid if you wrote the proofs yourself.

# How to iterate

The verifier is your oracle; use it tightly.

**Synchronous oracle.** After each verifier run, wait for the result before any further `Edit`, `Write`, or other state-changing tool call. Don't start a second verifier call while the first is in flight. Don't edit "while the verifier runs" — parallel editing breaks the feedback loop and is the most common cause of cascading regressions.

**Error count must trend down.** Remember the previous count and compare it to the new one. If it went up, your last edit regressed something — read the new errors, roll back if not salvageable. Compile-error → verification-error is **not** progress unless the verification-error count also drops. Keep the count and what's still empty in working memory rather than re-deriving each cycle.

**Tee verifier output, grep the cache.** Verus is slow; re-running it to refine a grep is waste:
```
{{verify_command}} 2>&1 | tee /tmp/v.out
grep -E "<pattern>" /tmp/v.out
```

**Scope the verifier when iterating on one piece.** Verus accepts `--verify-module <path::to::mod>` and `--verify-function <name>` (after the entry-point file, or after `--` if the wrapper requires it — try the simple form first). Narrowed verifies run in seconds vs minutes; reserve the full verify for the closing check.

**Try ideas, don't debate them.** A failed verify costs seconds. Write the candidate tactic, run the verifier.

# When you get stuck

**On one target** (your last few attempts didn't reduce its error count): leave it and move on. Coverage across all target files beats polishing one. Append a one-line entry to `SKIPPED.md` at the repo root: `<file>::<fn> — what I tried — why I gave up`.

**Across the whole run** — call `request_review.sh "<one-paragraph status>"` and end your turn when (a) the overall error count hasn't decreased across many verifier calls, (b) your last few plans haven't worked and you have no fresh ideas, or (c) the verifier keeps reporting `cannot find function` / `mismatched types` / `expected ','` on your edits (these have no proof-level meaning and usually mean you're inventing names or syntax). The script prints your status into the run transcript and exits; a supervisor decides whether to resume or close.

# Common pitfalls

Tee any non-trivial command output to a temp file and treat it as potentially large. Run commands with a timeout, or background them and periodically check logs and exit status. Combine multiple simple commands into one shell call to avoid round trips. Frequently consider whether you are stuck — if you're not making progress (commands hanging, same error recurring across edits, same plan attempted twice), reflect on your assumptions and run an easier test to validate them before continuing on the harder problem.

# Finishing

You are done when `{{verify_command}}` (no narrowing) reports `verified, 0 errors` and includes the {{n_targets}} target functions. Leave the final proof in place — the harness commits. In your final summary, list each target and whether you closed it, and explicitly state whether you used any forbidden action.
