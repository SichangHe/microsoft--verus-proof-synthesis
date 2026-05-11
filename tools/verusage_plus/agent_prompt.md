# Agent prompt for VeruSAGE+ pilots (full-repo, project-native verifier)

This file is what the harness writes into a pilot working tree as `AGENTS.md`. It is the authoritative prompt for the inner agent (Claude / opencode / etc.). Variables in `{{...}}` are filled in by the harness.

---

You are working on a Verus proof repair task inside a real Rust workspace.

# Workspace
- Repository: `{{repo_path}}`.
- Active branch (created for you): `{{pilot_branch}}`, branched from `{{base_branch}}`.
- Verifier command: `{{verify_command}}` — run from `{{verify_dir}}`.
- Authoritative success signal: the verifier output contains `verification results:: <N> verified, 0 errors` (possibly with a trailing `(partial verification with --verify-*)`). The verifier's *exit code* is unreliable for some projects (e.g. it may exit non-zero even on a clean verification). **Trust the output, not the exit status.**
- {{verify_setup}}
- Verus, `cargo-verus`, and any toolchain dependencies are already on PATH and pre-built for this session. Required Rust toolchain: `{{rust_toolchain}}`. **Do not change the Verus version, the toolchain, or any pinned dependency files** (`Cargo.toml`, `rust-toolchain.toml`, `vstd` paths), except possibly toggling `[package.metadata.verus]` per-package fields if strictly necessary.

# Where to find things

You should not need to discover paths by searching the filesystem. The two locations you will read from are listed below; `find /` / `grep -r /` / `rg /` are forbidden (see Forbidden) and pointless given these.

- **Project source — for the targets and surrounding code**: `{{repo_path}}`. Use `find {{repo_path}} -name '<file>'` or `grep -rn '<symbol>' {{repo_path}}` to locate things inside the project.
- **vstd source — for Verus standard library lemma signatures and definitions** (`Multiset::singleton`, `Set::insert`, `Seq::push`, `u64_leading_zeros`, the bitvector / nonlinear lemma library, `assert_by_compute`, etc.): `{{vstd_paths}}`. Examples:
  - List the modules: `ls {{vstd_paths}}`
  - Locate a vstd file: `find {{vstd_paths}} -name 'multiset.rs'`
  - Find a definition: `grep -rn 'pub proof fn lemma_multiset_' {{vstd_paths}}`
  - Read it: `cat {{vstd_paths}}/multiset.rs` (or use the Read tool with line offsets)
- If a lookup is unclear from the source, the Verus tutorial / reference / vstd rustdoc on `verus-lang.github.io` is a permitted network exception (see Forbidden). Do not visit any other URL.

# Task
- {{n_targets}} functions had their bodies replaced with the stripped VeruSAGE-Bench versions. Your job is to write Verus proofs / loop invariants / ghost annotations so that the verifier reports zero verification errors.
- You may freely edit the bodies of those {{n_targets}} functions and add new helper `proof fn` lemmas inside the same files. Do **not** modify other functions' signatures, postconditions, or executable behavior. Do **not** modify other crates outside the verified package(s) unless absolutely required.
- The list of targets (file :: fn) is in `VERUSAGE_PLUS_TARGETS.txt` next to this AGENTS.md.

# Forbidden — automatic disqualification

You must not retrieve, consult, or copy proofs from anywhere other than your own reasoning. In particular:

- **No other git state.** Do not run `git log`, `git show`, `git diff`, `git checkout`, `git stash show`, `git reflog`, or any tool against any branch, tag, ref, commit, stash, or worktree other than the current `HEAD`. Do not consult `main`, `origin/*`, `upstream/*`, or any historical commit. Do not read files under `.git/` directly. The proofs you are asked to write existed earlier in this repository's history; reading them in any form, by any tool, counts as cheating.
- **No network**, with one exception. Do not run `curl`, `wget`, `git fetch`, `cargo search`, `cargo fetch`, `gh`, web search, web fetch, or any other tool that contacts a remote host. Do not browse GitHub, crates.io, docs.rs, the upstream repos, papers, or any URL. **Permitted exception**: you may fetch from the Verus language documentation (`verus-lang.github.io`, including the Verus tutorial / reference / `vstd` rustdoc). It is the language reference for the tool you are using, not a source of proof solutions. Mention any such fetches in your final summary. All other internet access remains off-limits.
- **No outside-repo reads.** Do not read files outside `{{repo_path}}`. Do not read sibling clones, parent directories, or system locations that might mirror this code. **The only permitted exceptions are the two paths listed in "Where to find things" above** (`{{repo_path}}` and `{{vstd_paths}}`, plus the Cargo-registry vstd at `~/.cargo/registry/src/<index>/vstd-<version>/` when a Cargo-pinned vstd is present). All other package caches, sibling clones, and outside-repo paths remain forbidden. Mention any vstd reads in your final summary.
- **No `find /` or root-walks.** Do not run `find /`, `grep -r /`, `rg / ...`, or any other tool that scans the whole filesystem. They are slow on this host and **will wedge for hours on a hung NFS mount**. The two paths in "Where to find things" cover every legitimate lookup; if you can't find something there, the answer is to think harder about the lemma name, not to search wider.
- **No proof shortcuts.** Do not use `assume`, `admit`, `proof_from_false`, `arbitrary` as a proof shortcut, new axioms, `unimplemented!`, or new/existing `#[verifier::external_body]`. Do not weaken or delete `requires` / `ensures` clauses on the target functions or anywhere else.

If you are uncertain whether a particular action is allowed, treat it as forbidden. The mechanical correctness of the verifier's `verified, 0 errors` is necessary but not sufficient — the run is only valid if you actually wrote the proofs yourself.

# Self-report (anti-cheat)

We rely on your honesty rather than an automated cheat checker. If you could not avoid using a forbidden construct, weakened any postcondition, or otherwise looked up an answer instead of deriving it, state this clearly in your final summary instead of hiding it. Disclosing failure honestly is **strictly** preferred over presenting a copied solution as your own work.

# How to iterate

Run `{{verify_command}}` from `{{verify_dir}}` to see remaining errors. Initial state has {{initial_errors}} errors. Read a failing function, write the proof, re-verify. You may add helper `proof fn` lemmas in the same file.

**Synchronous oracle discipline.** After every verifier run, wait for the result before any further `Edit`, `Write`, or other state-changing tool call. Do not start a second verifier call while the first is in flight. Do not edit "while the verifier runs" — parallel editing destroys the feedback loop and is the single most common cause of cascading regressions.

**Error count must trend down across edits.** Remember the previous count; compare it to the new one. If the new count went up, your last edit regressed something — read the new errors, decide if the edit is salvageable, and roll back to the prior version (`git diff <file>` then revert the relevant hunk) if not. Compile-error → verification-error is **not** progress unless the verification-error count also dropped. Track the count and what is still empty in working memory across turns; don't re-derive each cycle.

**Tee the verifier output once and grep the cache.** Verus is slow; re-running it to refine a grep is waste:
```
{{verify_command}} 2>&1 | tee /tmp/v.out
grep -E "<pattern>" /tmp/v.out
```

**Scope the verifier when iterating on one piece.** Verus accepts `--verify-module <path::to::mod>` and `--verify-function <name>` after the entry-point file (or after `--`, depending on the wrapper — try the simpler form first). Narrowed verification typically runs in seconds; the full-crate run takes much longer. Run the narrowed form during iteration and the full {{verify_command}} for the final closing check.

**Try ideas instead of debating them.** The verifier is your oracle, and a failed verify costs only seconds. If you have a candidate tactic, write it and verify rather than reasoning at length about whether it will work.

**Discovering helpers (don't memorize vstd, query it).** vstd is large. Examples that work from any directory:
```
grep -rn 'pub proof fn \|pub spec fn ' {{vstd_paths}} | head -50
grep -rn 'lemma_seq_\|lemma_set_' {{vstd_paths}}
```
Reading existing usages elsewhere in `{{repo_path}}` is often the quickest way to learn a helper's calling shape.

You are done when {{verify_command}} (without narrowing) reports `verified, 0 errors` and the result includes the {{n_targets}} target functions.

# If a target won't close in this run

If your last few attempts at a target didn't reduce its error count, leave it and move on. Coverage across all target files beats polishing one. Append a one-line entry to `SKIPPED.md` at the repo root so a successor (or later you) can revisit:
```
<file>::<fn> — what I tried — why I gave up
```

# If you're stuck across the whole run

Call `request_review.sh` and stop your turn when **any** of the following holds:

- The overall error count has not decreased across many verifier calls in a row.
- Your last few plans haven't worked and you have no fresh ideas.
- The verifier keeps reporting `cannot find function`, `mismatched types`, or `expected ','` on your edits — those errors have no proof-level meaning and usually mean you are inventing names or syntax that don't exist.

```
request_review.sh "Stuck after N targets closed. Current error count M. What I tried last: X. What I think is blocking: Y."
```

The script prints your status (visible in the run transcript) and exits. End your turn after calling it — issue no further tool calls. A supervisor watching the run will see your status and decide whether to resume this pilot branch or close it.

# Common pitfalls

These apply to every long-running task; they are easy to fall into:

- Tee any non-trivial command output to a temp file and treat it as potentially large. Don't re-run an expensive command to refine a grep — grep the tee.
- Always run commands with a timeout to avoid hanging, or background them and periodically check logs and exit status.
- Combine multiple simple commands into one shell call to avoid round trips.
- Frequently consider whether you are stuck. If you're not making progress (commands hanging, the same error recurring across edits, the same plan attempted twice), reflect on what you have been doing and whether your assumptions may be wrong. Do an easier test to validate the assumption before continuing on the harder problem.

# Finishing

- Leave the final proof in place; commit nothing yourself (the harness handles git).
- In your final summary, list each target and whether you closed it or could not, and explicitly state whether you needed to use any of the forbidden actions above (with details).
