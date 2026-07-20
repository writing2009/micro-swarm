import os
import sys
from pathlib import Path

try:
    import tomllib  # py311+
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore

# Root of the active project repository (defaults to working directory)
ROOT = Path(os.getcwd()).resolve()
STATE = ROOT / "state"

# Subdirectories for state tracking
TASKS_TOML = ROOT / "swarm-tasks.toml"
TASKS_DIR = STATE / "tasks"
CLAIMS_DIR = STATE / "claims"
DONE_DIR = STATE / "done"
REVIEW_DIR = STATE / "review"

MICRO_CLAIMS_DIR = STATE / "micro_claims"
MICRO_DONE_DIR = STATE / "micro_done"
MICRO_REVIEW_DIR = STATE / "micro_review"

WORKTREES_DIR = ROOT / "worktrees"
LOGS_DIR = STATE / "logs"

def init_directories():
    """Ensure all swarm state directories exist."""
    for path in (TASKS_DIR, CLAIMS_DIR, DONE_DIR, REVIEW_DIR, 
                 MICRO_CLAIMS_DIR, MICRO_DONE_DIR, MICRO_REVIEW_DIR, 
                 WORKTREES_DIR, LOGS_DIR):
        path.mkdir(parents=True, exist_ok=True)

def load_tasks() -> dict[str, dict]:
    """Loads and deserializes swarm-tasks.toml configuration."""
    if not TASKS_TOML.exists():
        return {"tasks": {}, "workers": {}, "skills": {}}

    with open(TASKS_TOML, "rb") as f:
        data = tomllib.load(f)

    tasks = {t["id"]: t for t in data.get("task", [])}
    return {"tasks": tasks, "workers": data.get("workers", {}), "skills": data.get("skills", {})}
