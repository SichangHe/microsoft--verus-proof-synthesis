# Agent prompt for VeruSAGE+ pilots (full-repo, cargo-verus)

This file is what the harness writes into a pilot working tree as `AGENTS.md`. It is the authoritative prompt for the inner agent (Claude / opencode / etc.). Variables in `{{...}}` are filled in by the harness.

---

You are working on a Verus proof repair task inside a real Cargo workspace.

# Workspace
- Repository: `{{repo_path}}`.
- Active branch (created for you): `{{pilot_branch}}`, branched from `{{base_branch}}`.
- Verify the package `{{verify_package}}` rooted at `{{verify_manifest}}`. Run `cargo verus verify` from `{{verify_dir}}`.
- Verus binary and `cargo-verus` are already on PATH for this session. Required Rust toolchain: `{{rust_toolchain}}`. `vstd` is pinned in `Cargo.toml`. **Do not change the Verus version, the toolchain, or `Cargo.toml` dependencies**, except possibly toggling `[package.metadata.verus]` per-package fields if strictly necessary.

# Task
- {{n_targets}} functions in `{{verify_package}}` had their bodies replaced with the stripped VeruSAGE-Bench versions. Your job is to write Verus proofs / loop invariants / ghost annotations so that `cargo verus verify` passes again with zero verification errors.
- You may freely edit the bodies of those {{n_targets}} functions and add new helper `proof fn` lemmas inside the same files. Do **not** modify other functions' signatures, postconditions, or executable behavior. Do **not** modify other crates outside the verify package unless absolutely required.
- The list of targets (file :: fn) is in `VERUSAGE_PLUS_TARGETS.txt` next to this AGENTS.md.

# Forbidden — automatic disqualification

You must not retrieve, consult, or copy proofs from anywhere other than your own reasoning. In particular:

- **No other git state.** Do not run `git log`, `git show`, `git diff`, `git checkout`, `git stash show`, `git reflog`, or any tool against any branch, tag, ref, commit, stash, or worktree other than the current `HEAD`. Do not consult `main`, `origin/*`, `upstream/*`, or any historical commit. Do not read files under `.git/` directly. The proofs you are asked to write existed earlier in this repository's history; reading them in any form, by any tool, counts as cheating.
- **No network**, with one exception. Do not run `curl`, `wget`, `git fetch`, `cargo search`, `cargo fetch`, `gh`, web search, web fetch, or any other tool that contacts a remote host. Do not browse GitHub, crates.io, docs.rs, the Vest/Atmosphere/IronKV upstream repos, the VeruSAGE paper, or any URL. **Permitted exception**: you may fetch from the Verus language documentation (`verus-lang.github.io`, including the Verus tutorial / reference / `vstd` rustdoc). It is the language reference for the tool you are using, not a source of proof solutions. Mention any such fetches in your final summary. All other internet access remains off-limits.
- **No outside-repo reads.** Do not read files outside `{{repo_path}}`. Do not read sibling clones, parent directories, or system locations that might mirror this code. **Permitted exception**: you may read the vstd source under `~/.cargo/registry/src/<index>/vstd-<version>/` for lemma signatures and definitions — vstd is the standard library you are calling into, and looking up its lemmas is reasonable mathematical research, not cheating. All other package caches, sibling clones, and outside-repo paths remain forbidden. Mention any vstd reads in your final summary.
- **No proof shortcuts.** Do not use `assume`, `admit`, `proof_from_false`, `arbitrary` as a proof shortcut, new axioms, `unimplemented!`, or new/existing `#[verifier::external_body]`. Do not weaken or delete `requires` / `ensures` clauses on the target functions or anywhere else.

If you are uncertain whether a particular action is allowed, treat it as forbidden. The mechanical correctness of `cargo verus verify` is necessary but not sufficient — the run is only valid if you actually wrote the proofs yourself.

# Self-report (anti-cheat)

We rely on your honesty rather than an automated cheat checker. If you could not avoid using a forbidden construct, weakened any postcondition, or otherwise looked up an answer instead of deriving it, state this clearly in your final summary instead of hiding it. Disclosing failure honestly is **strictly** preferred over presenting a copied solution as your own work.

# How to iterate

- Run `cargo verus verify` from `{{verify_dir}}` to see remaining errors. Initial state has {{initial_errors}} errors.
- Iterate: read the failing function, write the proof, re-verify. You may add helper lemmas in the same file.
- Use `--rlimit` and `--multiple-errors N` Verus flags (after `--`) when helpful.
- **Try ideas instead of debating them.** `cargo verus verify` is your oracle, and a failed verify costs ~10 s of compile time. If you have a candidate proof tactic — `reveal_with_fuel`, a `by (bit_vector)` hint, an inductive helper, an `assert_seqs_equal!`, anything — write it and run `cargo verus verify` rather than reasoning at length about whether it will work. Verus rejects bad ideas at almost no cost, so prefer fast empirical iteration over long deliberation.
- When `cargo verus verify` returns `verification results:: ... 0 errors` for `{{verify_package}}` and the rest of the workspace still passes, you are done.

# Finishing

- Leave the final proof in place; commit nothing yourself (the harness handles git).
- In your final summary, list each target and whether you closed it or could not, and explicitly state whether you needed to use any of the forbidden actions above (with details).
