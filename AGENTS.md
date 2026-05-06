Read `codebase_index/README.md` to find docs you need
This repo is implementation/artifact workspace for automated Verus proof synthesis using LLM

2 systems:

- `autoverus/`: three-phase proof generation for smaller algorithmic tasks
- `verusage/`: agent-based repair/synthesis for larger system-style tasks

2 benchmark suites:

- `benchmarks/Verus-Bench`: 150 algorithm-level tasks
- `benchmarks/VeruSAGE-Bench`: 849 repository-level tasks
- `leaderboard/`: static site + JSON result data
- `generated/`: large saved experiment outputs
