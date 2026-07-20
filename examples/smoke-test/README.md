# Smoke Test

Verifies a micro-swarm installation end-to-end with the smallest possible
workload: one task, one module, one assertion (`add(a, b)` returns the sum).
A successful run proves your worker config, Ollama endpoint, `opencode`
integration, git worktree isolation, and all four phase review gates work.

## Prerequisites

- `micro-swarm` installed (see the top-level README)
- `opencode` on your PATH
- An Ollama endpoint serving your chosen model

## Run

```bash
./setup.sh                                  # scaffold ./swarm-smoke-test
SMOKE_MODEL=qwen3.6:35b ./setup.sh mytest   # custom model and target dir
SMOKE_HOST=ollama-host-2.lan ./setup.sh     # remote Ollama worker

cd swarm-smoke-test
micro-swarm --watch --concurrency 1 --loop-sleep 20
```

Monitor from another terminal with `micro-swarm --status` or
`tail -f state/logs/orchestrator.jsonl`.

## What success looks like

The task `T001` expands into four microtasks that must each complete and
pass review, in order:

| Phase       | Deliverable                            | Review gate            |
|-------------|----------------------------------------|------------------------|
| `T001.R`    | `RESEARCH.md`                          | contract sections exist |
| `T001.D`    | `TEST_PLAN.md`                         | assertion blocks exist  |
| `T001.A1.T` | failing test `tests/test_a1_*.py`      | pytest exits 1          |
| `T001.A1.I` | `src/` code making the test pass       | pytest exits 0          |

When all four are done, `state/done/T001.toml` appears and
`micro-swarm --status` shows every phase as `done`.

## Notes

The phase prompts reference optional opencode skills (`using-superpowers`,
`writing-plans`, `test-driven-development`, `verification-before-completion`).
micro-swarm syncs these into each worktree from your project's
`.opencode/skills` directory when present; this scaffold does not include
them, so workers proceed without them. Installing them in your real projects
improves worker discipline but is not required for the smoke test to pass.

Total wall time depends on your model and hardware — expect minutes.
A worker that exits without finishing is respawned automatically
(`worker_crashed_no_done` in the log followed by a retry is normal,
especially for the final implementation phase on smaller models).

On a fresh machine, expect a burst of fast `worker_crashed_no_done`
retries at the very start: opencode downloads its provider package on
first use, and Ollama needs time to load a large model into memory.
Workers fail quickly ("Unexpected server error") until both are warm,
then proceed normally. Pre-warming helps, e.g.:
`ollama run <model> "hi"` before starting the watch loop.
