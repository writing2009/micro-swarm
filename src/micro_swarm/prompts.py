from pathlib import Path
from .config import MICRO_DONE_DIR

# Skill invoked at the start of each phase (plus a pre-completion
# verification skill for the green phase). Projects can override or disable
# these via the [skills] table in swarm-tasks.toml.
DEFAULT_SKILLS = {
    "research": "using-superpowers",
    "discovery": "writing-plans",
    "tdd_red": "test-driven-development",
    "tdd_green": "test-driven-development",
    "verification": "verification-before-completion",
}

def resolve_skills(skills: dict | None) -> dict:
    """Merge the [skills] config over the defaults.

    enabled = false disables all skills; setting an individual key to ""
    disables the skill for just that phase; unset keys use the default.
    """
    skills = skills or {}
    if not skills.get("enabled", True):
        return {k: None for k in DEFAULT_SKILLS}
    return {k: (skills.get(k, DEFAULT_SKILLS[k]) or None) for k in DEFAULT_SKILLS}

def _skill_step(name: str | None, purpose: str = "follow it") -> str | None:
    if not name:
        return None
    return (f'FIRST: If a skill named "{name}" is available, invoke it via the '
            f'`skill` tool and {purpose}; if unavailable, continue.')

def _workflow(steps: list[str | None]) -> str:
    """Number the non-empty steps into a WORKFLOW block."""
    present = [s for s in steps if s]
    return "\n".join(f"{i}. {s}" for i, s in enumerate(present, 1))

def generate_phased_prompt(task: dict, phase: dict, spec_text: str = "",
                           worktree: Path | None = None,
                           skills: dict | None = None) -> str:
    """Generate phase-specific prompts containing explicit skill tool call instructions."""
    phase_type = phase["phase_type"]
    parent = phase["parent"]
    module = phase["module"]
    assertion_id = phase["assertion_id"]
    a_lower = assertion_id.lower()
    skill_for = resolve_skills(skills)
    # All paths handed to the agent must be absolute: agents resolve relative
    # paths against their own notion of project root, which can escape the
    # worktree (e.g. following the worktree .git file back to the main checkout)
    done_dir = MICRO_DONE_DIR

    # Extract details or use general placeholders
    acceptance = task.get("acceptance", "pytest")
    module_path = f"{worktree}/modules/{module}" if worktree else f"modules/{module}"
    git_prefix = f"cd {worktree} && " if worktree else ""

    if phase_type == "R":
        workflow = _workflow([
            _skill_step(skill_for["research"]),
            "Read the specification design files.",
            f"Write {module_path}/RESEARCH.md detailing data contracts and open design questions.",
            f'Commit your work: {git_prefix}git add {module_path}/RESEARCH.md && git commit -m "{parent}.R: research"',
            f"Write {done_dir}/{parent}.R.toml with task/worker/commit/acceptance_exit=0.",
            "Stop.",
        ])
        return f"""You are a Research Worker. ONE deliverable: {parent}.R.

MODULE: {module}
WRITE ONLY: {module_path}/RESEARCH.md
DO NOT modify files under {module_path}/src/ or tests/.

YOUR SPECIFICATION TARGET:
{spec_text or "Read design requirements for this module."}

WORKFLOW:
{workflow}
"""

    elif phase_type == "D":
        workflow = _workflow([
            _skill_step(skill_for["discovery"]),
            "Read the module specifications and RESEARCH.md.",
            f"Write {module_path}/TEST_PLAN.md detailing the test files and fixtures needed for each assertion.",
            f'Commit your work: {git_prefix}git add {module_path}/TEST_PLAN.md && git commit -m "{parent}.D: test plan"',
            f"Write {done_dir}/{parent}.D.toml with task/worker/commit/acceptance_exit=0.",
            "Stop.",
        ])
        return f"""You are a Discovery Worker. ONE deliverable: {parent}.D.

MODULE: {module}
WRITE ONLY: {module_path}/TEST_PLAN.md
INPUT: Read {module_path}/RESEARCH.md.

YOUR SPECIFICATION TARGET:
{spec_text or "Read design requirements for this module."}

WORKFLOW:
{workflow}
"""

    elif phase_type == "T":
        workflow = _workflow([
            _skill_step(skill_for["tdd_red"]),
            "Read RESEARCH.md and TEST_PLAN.md.",
            f"Write ONE failing test file {module_path}/tests/test_{a_lower}_*.py for this assertion only.",
            "Run the tests: collection must succeed, then the run must FAIL (exit 1).",
            f'Commit: {git_prefix}git add {module_path}/tests/ && git commit -m "{parent}.{assertion_id}.T: red test"',
            f"Write {done_dir}/{parent}.{assertion_id}.T.toml with task/worker/commit/acceptance_exit=0.",
            "Stop. Do NOT start implementing code.",
        ])
        return f"""You are a TDD-Red Worker. ONE deliverable: {parent}.{assertion_id}.T.

MODULE: {module}
WRITE ONLY: files under {module_path}/tests/ (test_{a_lower}_*.py plus conftest.py if needed)
DO NOT write or modify code under {module_path}/src/.

THE ONE ASSERTION YOU MUST SATISFY:
Assertion {assertion_id}: {spec_text or "Verify correctness of this unit."}

TEST REQUIREMENTS (the review gate enforces these):
- At most 5 focused test cases, covering ONLY this assertion. Do not invent
  extra error-handling or edge-case requirements beyond the assertion.
- The file must collect cleanly (`pytest --collect-only` must succeed) even
  though the implementation does not exist yet. Therefore import the function
  under test INSIDE each test function (e.g. `from {module} import ...`),
  never at module level.
- If imports need {module_path}/src on sys.path, write
  {module_path}/tests/conftest.py that inserts it.

WORKFLOW:
{workflow}
"""

    elif phase_type == "I":
        workflow = _workflow([
            _skill_step(skill_for["tdd_green"], "focus on minimal code change"),
            f"Read the failing test {module_path}/tests/test_{a_lower}_*.py.",
            f"Write the MINIMUM production code under {module_path}/src/ to make the test pass.",
            _skill_step(skill_for["verification"]),
            "Re-run the tests, confirm exit 0, and verify all code is linted.",
            f'Commit: {git_prefix}git add {module_path}/ && git commit -m "{parent}.{assertion_id}.I: green impl"',
            f"Write {done_dir}/{parent}.{assertion_id}.I.toml with task/worker/commit/acceptance_exit=0.",
            "Stop.",
        ])
        return f"""You are a TDD-Green Worker. ONE deliverable: {parent}.{assertion_id}.I.

MODULE: {module}
WRITE ONLY: {module_path}/src/ files (minimum code needed to pass).
DO NOT touch test files or other assertion directories.

THE ONE ASSERTION YOU MUST SATISFY:
Assertion {assertion_id}: {spec_text or "Verify correctness of this unit."}

WORKFLOW:
{workflow}
"""

    raise ValueError(f"Unknown phase type: {phase_type}")
