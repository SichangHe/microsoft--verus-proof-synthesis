- Read this if the task is about published outputs, artifact reproduction, or comparing AutoVerus vs baseline results.
- `generated/autoverus/` contains `autoverus-generated`, `baseline-generated`, and `abalation-study`.
- Use `README-artifact-evaluation.md` first for expected layout and reproduction commands.
- `baseline-generated` is AutoVerus direct-LLM baseline output; do not confuse it with VeruSAGE paper "Hands-Off".

warning

- Treat `generated/` as output data, not implementation.
- `README-artifact-evaluation.md` still mentions an older `/code` path inside Docker; use it for experiment layout, not current repo navigation.
- The newer hands-off pilot results are **not** in `generated/`; they live under `runs/verusage_hands_off/` (gitignored). The harness, prompt, and human-readable summary are at `tools/verusage_hands_off/`, `docs/verusage_hands_off/project_pilot.md`, and [`../tooling/verusage-hands-off-pilot.md`](../tooling/verusage-hands-off-pilot.md).
