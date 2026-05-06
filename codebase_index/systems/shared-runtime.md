- `infer.py` -> model calls.
- `veval.py` -> run Verus, parse failures, compute scores.
- `utils.py` -> code cleanup, safety checks, rewrite helpers.
- `houdini.py` -> invariant/predicate helper logic.
- `lynette.py` -> bridge to parser/tooling.

- If the question is "how do we call Verus / interpret failures?" start in `veval.py`.
- If the question is "is this rewrite safe / how do we normalize code?" start in `utils.py`.
- If the question is parser or standard-library retrieval related, continue to [`../tooling/lynette-and-vstd.md`](../tooling/lynette-and-vstd.md).
