import os
import subprocess
from pathlib import Path
from .config import ROOT, MICRO_REVIEW_DIR, LOGS_DIR

def review_phased_microtask(mtask_id: str, mtask: dict, worktree_path: Path, acceptance_cmd: str) -> bool:
    """
    Run review checks for the specific microtask phase.
    Writes verdict = "pass" or "fail" to state/micro_review/<mtask_id>.toml.
    """
    phase_type = mtask["phase_type"]
    module = mtask["module"]
    module_path = worktree_path / "modules" / module
    
    verdict = "fail"
    
    MICRO_REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    log_dir = LOGS_DIR / "micro" / "review"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{mtask_id}.log"
    
    with open(log_file, "w") as lf:
        lf.write(f"=== review {mtask_id}: phase {phase_type} ===\n")
        lf.flush()
        
        if phase_type == "R":
            # Research verification: check RESEARCH.md file exists and has sections
            res_md = module_path / "RESEARCH.md"
            if res_md.exists():
                text = res_md.read_text().lower()
                if "contract" in text or "convention" in text:
                    verdict = "pass"
                    lf.write("RESEARCH.md validated successfully.\n")
                else:
                    lf.write("RESEARCH.md missing data contract sections.\n")
            else:
                lf.write("RESEARCH.md file not found.\n")
                
        elif phase_type == "D":
            # Discovery verification: check TEST_PLAN.md file exists and has ## A blocks
            plan_md = module_path / "TEST_PLAN.md"
            if plan_md.exists():
                text = plan_md.read_text()
                if "##" in text:
                    verdict = "pass"
                    lf.write("TEST_PLAN.md validated successfully.\n")
                else:
                    lf.write("TEST_PLAN.md lacks assertion blocks.\n")
            else:
                lf.write("TEST_PLAN.md file not found.\n")
                
        elif phase_type == "T":
            # TDD Red verification: run pytest and verify it exits with 1 (fails as expected)
            proc = subprocess.run(
                ["bash", "-lc", f"{acceptance_cmd} ; test $? -eq 1"],
                cwd=str(worktree_path),
                shell=False,
                stdout=lf, stderr=subprocess.STDOUT,
                env={**os.environ, "PATH": f"{ROOT}/.venv/bin:{os.environ['PATH']}"}
            )
            if proc.returncode == 0:
                verdict = "pass"
                lf.write("\nVerification passed: test failed with exit code 1 as expected.\n")
            else:
                lf.write(f"\nVerification failed: exit {proc.returncode}.\n")
                
        elif phase_type == "I":
            # TDD Green verification: run pytest and verify it exits with 0 (passes)
            proc = subprocess.run(
                ["bash", "-lc", acceptance_cmd],
                cwd=str(worktree_path),
                shell=False,
                stdout=lf, stderr=subprocess.STDOUT,
                env={**os.environ, "PATH": f"{ROOT}/.venv/bin:{os.environ['PATH']}"}
            )
            if proc.returncode == 0:
                verdict = "pass"
                lf.write("\nVerification passed: test succeeded with exit code 0.\n")
            else:
                lf.write(f"\nVerification failed: exit {proc.returncode}.\n")
                
    # Write verdict to status file
    verdict_file = MICRO_REVIEW_DIR / f"{mtask_id}.toml"
    verdict_file.write_text(f'task = "{mtask_id}"\nverdict = "{verdict}"\n')
    
    return verdict == "pass"
