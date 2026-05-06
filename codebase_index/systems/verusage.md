- Read this if the task mentions VeruSAGE, `verusage/`, VeruSAGE-Bench, agent actions, ORA, or batch repair.
- Flow: `main.py` -> `GlobalConfig` -> `repair_runner.py` -> `agents/main_loop.py` -> `AgentOrchestrator` -> specialized agents + actions.
- Start with `verusage/main.py`, `repair_runner.py`, `agents/main_loop.py`, `agents/__init__.py`, `agents/base_agent.py`, `agents/actions/__init__.py`, `global_config.py`, `vstd_library/`.
- If you need the agent-stack implementation split, read [`verusage-agents.md`](verusage-agents.md).
- If you need the standard-library retrieval implementation split, read [`verusage-vstd-library.md`](verusage-vstd-library.md).
- `agents/prompts/` holds prompt templates. `run_batch.py` is the practical batch runner over `.rs` files.
- `agent_framework.py` is a compatibility re-export; real logic lives in `verusage/agents/`.

warning

- Do not open every agent/action file first. Start with the central loop, then only the specific agent/action family relevant to the failure type.
- `run_all_batches.py` has optional email orchestration, but its default benchmark paths appear to be legacy; check args before use.
