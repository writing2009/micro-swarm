def generate_phased_prompt(task: dict, phase: dict, spec_text: str = "") -> str:
    """Generate phase-specific prompts containing explicit skill tool call instructions."""
    phase_type = phase["phase_type"]
    parent = phase["parent"]
    module = phase["module"]
    assertion_id = phase["assertion_id"]
    a_lower = assertion_id.lower()
    
    # Extract details or use general placeholders
    acceptance = task.get("acceptance", "pytest")
    module_path = f"modules/{module}"
    
    # Set up base workflow instructions depending on phase type
    if phase_type == "R":
        return f"""You are a Research Worker. ONE deliverable: {parent}.R.

MODULE: {module}
WRITE ONLY: {module_path}/RESEARCH.md
DO NOT modify files under {module_path}/src/ or tests/.

YOUR SPECIFICATION TARGET:
{spec_text or "Read design requirements for this module."}

WORKFLOW:
0. FIRST: Call the `skill` tool with name "using-superpowers" and follow its instructions. This is mandatory.
1. Read the specification design files.
2. Write {module_path}/RESEARCH.md detailing data contracts and open design questions.
3. Commit your work: git add {module_path}/RESEARCH.md && git commit -m "{parent}.R: research"
4. Write state/micro_done/{parent}.R.toml with task/worker/commit/acceptance_exit=0.
5. Stop.
"""

    elif phase_type == "D":
        return f"""You are a Discovery Worker. ONE deliverable: {parent}.D.

MODULE: {module}
WRITE ONLY: {module_path}/TEST_PLAN.md
INPUT: Read {module_path}/RESEARCH.md.

YOUR SPECIFICATION TARGET:
{spec_text or "Read design requirements for this module."}

WORKFLOW:
0. FIRST: Call the `skill` tool with name "writing-plans" and follow its instructions.
1. Read the module specifications and RESEARCH.md.
2. Write {module_path}/TEST_PLAN.md detailing the test files and fixtures needed for each assertion.
3. Commit your work: git add {module_path}/TEST_PLAN.md && git commit -m "{parent}.D: test plan"
4. Write state/micro_done/{parent}.D.toml with task/worker/commit/acceptance_exit=0.
5. Stop.
"""

    elif phase_type == "T":
        return f"""You are a TDD-Red Worker. ONE deliverable: {parent}.{assertion_id}.T.

MODULE: {module}
WRITE ONLY: {module_path}/tests/test_{a_lower}_*.py
DO NOT write or modify code under {module_path}/src/.

THE ONE ASSERTION YOU MUST SATISFY:
Assertion {assertion_id}: {spec_text or "Verify correctness of this unit."}

WORKFLOW:
0. FIRST: Call the `skill` tool with name "test-driven-development" and follow its instructions.
1. Read RESEARCH.md and TEST_PLAN.md.
2. Write ONE failing test file {module_path}/tests/test_{a_lower}_*.py for this assertion only.
3. Run the tests and confirm it fails (exits 1) as expected.
4. Commit: git add {module_path}/tests/ && git commit -m "{parent}.{assertion_id}.T: red test"
5. Write state/micro_done/{parent}.{assertion_id}.T.toml with task/worker/commit/acceptance_exit=0.
6. Stop. Do NOT start implementing code.
"""

    elif phase_type == "I":
        return f"""You are a TDD-Green Worker. ONE deliverable: {parent}.{assertion_id}.I.

MODULE: {module}
WRITE ONLY: {module_path}/src/ files (minimum code needed to pass).
DO NOT touch test files or other assertion directories.

THE ONE ASSERTION YOU MUST SATISFY:
Assertion {assertion_id}: {spec_text or "Verify correctness of this unit."}

WORKFLOW:
0. FIRST: Call the `skill` tool with name "test-driven-development" to focus on minimal code change.
1. Read the failing test {module_path}/tests/test_{a_lower}_*.py.
2. Write the MINIMUM production code under {module_path}/src/ to make the test pass.
3. Call the `skill` tool with name "verification-before-completion" and follow its instructions.
4. Re-run the tests, confirm exit 0, and verify all code is linted.
5. Commit: git add {module_path}/ && git commit -m "{parent}.{assertion_id}.I: green impl"
6. Write state/micro_done/{parent}.{assertion_id}.I.toml with task/worker/commit/acceptance_exit=0.
7. Stop.
"""

    raise ValueError(f"Unknown phase type: {phase_type}")
