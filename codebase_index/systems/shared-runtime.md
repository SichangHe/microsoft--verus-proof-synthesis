- `infer.py` -> model calls.
- `veval.py` -> run Verus, parse failures, compute scores.
- `utils.py` -> code cleanup, safety checks, rewrite helpers.
- `houdini.py` -> invariant/predicate helper logic.
- `lynette.py` -> bridge to AST-aware parser/tooling; not a verifier.

- If the question is "how do we call Verus / interpret failures?" start in `veval.py`.
- If the question is "is this rewrite safe / how do we normalize code?" start in `utils.py`.
- If the question is parser, standard-library retrieval, or "what does Lynette add beyond Verus output?" continue to [`../tooling/lynette-and-vstd.md`](../tooling/lynette-and-vstd.md).
