- `utils/lynette/` -> AST-aware Verus code-analysis/transformation tool. Verus still does verification and error reporting; Lynette is used for structure-aware operations around that.
- `verusage/vstd_library/` -> parse, index, and search the Verus standard library for repair-time retrieval.
- Start with `verusage/vstd_library/__init__.py`, `build_index.py`, `parser.py`, `indexer.py`, `search_engine.py`.

- If you are asking "why not just use Verus output?" the answer is: Verus says whether code verifies; Lynette helps this repo inspect and transform proof-oriented code.
- The recurring Lynette jobs here are ghost/assertion location extraction, nonlinear detection, and code/invariant merging.

- If the bug is about missing library facts or bad retrieval, start in `verusage/vstd_library/`.
- If the bug is about Verus syntax parsing or structural rewriting, you may need `utils/lynette/` plus `autoverus/lynette.py` or `verusage/lynette.py`.
