- `vstd_library/build_index.py` -> CLI entrypoint to rebuild the index from a `--vstd-path`.
- `parser.py` -> parse `vstd` Rust files into structured functions/open specs with requires/ensures/triggers/keywords/callees.
- `indexer.py` -> build/save/load searchable index data.
- `search_engine.py` -> ranked search over indexed functions/specs.
- `query_generator.py` -> generate search queries from repair context.
- `result_formatter.py` -> shape retrieved results for downstream LLM use.

- If the bug is “index is stale or missing entries,” start in `build_index.py` + `indexer.py` + `parser.py`.
- If the bug is “retrieval returns the wrong library facts,” start in `search_engine.py` + `query_generator.py` + `result_formatter.py`.
