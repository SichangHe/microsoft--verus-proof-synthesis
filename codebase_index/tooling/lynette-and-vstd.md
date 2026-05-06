- `utils/lynette/` -> large Rust parser/tool workspace used for proof-synthesis support. only open it if the task is parser or transformation specific.
- `verusage/vstd_library/` -> parse, index, and search the Verus standard library for repair-time retrieval.
- Start with `verusage/vstd_library/__init__.py`, `build_index.py`, `parser.py`, `indexer.py`, `search_engine.py`.

- If the bug is about missing library facts or bad retrieval, start in `verusage/vstd_library/`.
- If the bug is about Verus syntax parsing or structural rewriting, you may need `utils/lynette/` plus `autoverus/lynette.py` or `verusage/lynette.py`.
