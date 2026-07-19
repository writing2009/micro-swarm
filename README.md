# Micro-Swarm: Phased Microtask Orchestrator

`micro-swarm` is a standalone, lightweight orchestrator that segments complex development tasks (typically scoped to entire software modules) into a linear dependency chain of small, single-assertion **phased microtasks**.

This approach minimizes the prompt size and LLM context window required for any single step, making it highly reliable when running local AI agent instances (e.g., using Ollama) with 35B parameter class models.

---

### Why We Are Open-Sourcing `micro-swarm`

Most current AI-native development platforms rely on massive, closed-source cloud models with high API costs and potential data privacy concerns. While local, open-weights models (like the 35B parameter class) offer complete privacy and cost-free execution on consumer-grade hardware, they have traditionally struggled with the multi-step reasoning required for full-scale software engineering tasks.

We built and are sharing `micro-swarm` to bridge this gap.

By introducing the **Phased Microtask Orchestration** paradigm, we show that you don't need giant context windows or expensive cloud endpoints to build complex codebases. Instead, by segmenting feature development into small, linear, self-verifying phases (Research → Discovery → TDD Red → TDD Green) and utilizing isolated Git worktrees, we enable local models to work concurrently and with a high degree of correctness.

We are sharing this framework with the open-source community to democratize agentic software development, allowing any developer or team to run private, secure, and cost-efficient AI coding swarms locally.

---

## 1. Installation

To install `micro-swarm` locally in editable developer mode:

```bash
cd micro-swarm
pip install -e .
```

---

## 2. Configuration (`swarm-tasks.toml`)

Create a `swarm-tasks.toml` file in the root of your project directory. This file defines the workers (local AI endpoints), concurrency rules, and tasks.

```toml
# swarm-tasks.toml

# Define the local AI worker nodes
[workers]
w1 = { host = "localhost", model = "qwen3.6:35b" }
w2 = { host = "mini64pro.lan", model = "qwen3.6:35b" }
w3 = { host = "gx10-444c.lan", model = "qwen3.6:35b" }

# Define the tasks (each mapped to a specific codebase module)
[[task]]
id = "T001"
module = "auth-service"
acceptance = "pytest modules/auth-service/tests/ -q"
assertions = ["A1", "A2", "A3"]

[[task]]
id = "T002"
module = "vault-io"
acceptance = "pytest modules/vault-io/tests/ -q"
assertions = ["A1"]
```

---

## 3. Usage

### Check Task Swarm Status
Prints a comprehensive tree showing parent tasks and the execution status (`pending`, `claimed`, or `done`) of their individual Research, Discovery, and TDD Red/Green microtask phases:

```bash
micro-swarm --status
```

### Start the Watcher loop
Starts the background loop that polls task statuses, claims available parents, allocates isolated `git worktree` workspaces, and spawns the workers using OpenCode:

```bash
micro-swarm --watch --concurrency 3 --loop-sleep 60
```

---

## 4. How it Works (Under the Hood)

1. **Segmentation**: A parent task `T001` with assertions `["A1", "A2"]` is automatically expanded into:
   * `T001.R` (Research phase: writes `RESEARCH.md` defining data contracts).
   * `T001.D` (Discovery phase: writes `TEST_PLAN.md` mapping tests to assertions).
   * `T001.A1.T` (TDD Red: writes failing test for `A1`).
   * `T001.A1.I` (TDD Green: implements minimal code to pass `A1`).
   * `T001.A2.T` (TDD Red: writes failing test for `A2`).
   * `T001.A2.I` (TDD Green: implements minimal code to pass `A2`).

2. **Git Worktrees**: The framework creates a separate worktree (`worktrees/w1-T001/`) for the assigned worker so concurrent runs do not conflict.

3. **Virtualenv Symlinking**: To avoid copying large dependencies, the local virtualenv (`.venv`) is automatically symlinked into each worktree, allowing relative test command invocation (like `.venv/bin/pytest`) to resolve.

4. **Skill Tool Injection**: Prompts inject explicit tool instructions (`using-superpowers`, `writing-plans`, and `test-driven-development`) as Step 0 of the workflow. AI agents execute tool instructions with significantly higher reliability than prose guidelines.

5. **Phase-Specific Verification**: Completed work is reviewed in the worktree:
   * **Research/Discovery**: Confirms required docs are present and properly sectioned.
   * **TDD Red**: Asserts the test suite exits with **Exit Code 1** (fails).
   * **TDD Green**: Asserts the test suite exits with **Exit Code 0** (passes).
