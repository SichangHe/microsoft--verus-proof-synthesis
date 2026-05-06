- Read this if the task mentions AutoVerus, `autoverus/`, Verus-Bench, artifact evaluation, or single-file proof generation.
- Flow: `main.py` -> `Generation.run(...)` / `generation.py` -> `refinement.py` -> `veval.py` -> output proof + intermediates.
- Start with `autoverus/main.py`, `generation.py`, `refinement.py`, `veval.py`, `verify.py`.
- `examples/` = few-shot example bank. `lemmas/` = reusable proof snippets.
- `inter_main.py` + `inter_generation.py` = separate preliminary inter-procedural path; ignore unless the task is cross-function generation.

warning

- Do not start in `examples/`; it is prompt/training data, not control flow.
- Do not start in `generated/`; it is output data, not implementation.
