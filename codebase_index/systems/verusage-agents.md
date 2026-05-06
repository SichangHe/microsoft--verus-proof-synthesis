- `agents/main_loop.py` -> central repair loop; picks one failure, invokes orchestrator, validates change.
- `agents/__init__.py` -> `AgentOrchestrator`; maps failures to agent classes.
- `agents/base_agent.py` -> ORA contract shared by all agents.
- `agents/shared_types.py` -> shared dataclasses, acceptance criteria, diff/state helpers.
- `agents/preprocessing.py` -> code analysis shared before repair.
- `agents/verus_syntax_patterns.py` -> shared syntax checks/hints used across repair logic.
- `agents/repair_metadata.py` + `failure_history.py` -> attempt tracking and history.

- `repair_assert_agent.py` is the most complex/high-branching agent; start there for assertion-failure behavior.
- Other `repair_*_agent.py` files mostly map one Verus failure family to a narrower action set.
- `agents/actions/` contains the concrete repair operations. start with `actions/__init__.py`, `base_action.py`, `action_types.py` before a specific action.
- `agents/prompts/` mirrors many actions with prompt templates.
- `debug.py`, `DEBUG_README.md`, and `live_visualizer.py` are support tooling; skip unless the task is debugging agent behavior or visualization.

warning

- Do not read every `repair_*_agent.py` or action file. Identify the failure family first, then open only the matching agent and 1-2 likely actions.
