from pathlib import Path
from .config import MICRO_DONE_DIR

try:
    import tomllib  # py311+
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore

def segment_task_phased(task: dict) -> list[dict]:
    """Segment a parent task into research, discovery, and a T/I pair per assertion."""
    parent_id = task["id"]
    module = task["module"]
    assertions = task.get("assertions", [])
    
    microtasks = []
    
    # 1. Research Phase
    microtasks.append({
        "id": f"{parent_id}.R",
        "parent": parent_id,
        "phase_type": "R",
        "assertion_id": "R",
        "depends_on": None,
        "module": module
    })
    
    # 2. Discovery Phase
    microtasks.append({
        "id": f"{parent_id}.D",
        "parent": parent_id,
        "phase_type": "D",
        "assertion_id": "D",
        "depends_on": f"{parent_id}.R",
        "module": module
    })
    
    # 3. Assertions (TDD pair per assertion)
    prev_id = f"{parent_id}.D"
    for assertion in assertions:
        # T (TDD red test)
        t_id = f"{parent_id}.{assertion}.T"
        microtasks.append({
            "id": t_id,
            "parent": parent_id,
            "phase_type": "T",
            "assertion_id": assertion,
            "depends_on": prev_id,
            "module": module
        })
        
        # I (TDD green implementation)
        i_id = f"{parent_id}.{assertion}.I"
        microtasks.append({
            "id": i_id,
            "parent": parent_id,
            "phase_type": "I",
            "assertion_id": assertion,
            "depends_on": t_id,
            "module": module
        })
        prev_id = i_id
        
    return microtasks

def microtask_status(mtask_id: str) -> str:
    """Return the status of a specific microtask: done, claimed, or pending."""
    from .config import MICRO_CLAIMS_DIR, MICRO_REVIEW_DIR
    
    done_f = MICRO_DONE_DIR / f"{mtask_id}.toml"
    review_f = MICRO_REVIEW_DIR / f"{mtask_id}.toml"
    claim_f = MICRO_CLAIMS_DIR / f"{mtask_id}.toml"
    
    if done_f.exists() and review_f.exists():
        # A review file with a fail verdict (left by an interrupted cleanup)
        # must not count as done
        try:
            with open(review_f, "rb") as f:
                if tomllib.load(f).get("verdict") == "pass":
                    return "done"
        except Exception:
            pass
    if claim_f.exists():
        return "claimed"
    return "pending"

def all_phased_microtasks_done(task: dict) -> bool:
    """Check if all microtasks for the task are completed and reviewed."""
    microtasks = segment_task_phased(task)
    return all(microtask_status(m["id"]) == "done" for m in microtasks)

def next_pending_phased_microtask(task: dict) -> dict | None:
    """Return the next pending microtask in the sequence."""
    microtasks = segment_task_phased(task)
    for m in microtasks:
        status = microtask_status(m["id"])
        if status == "pending":
            return m
        elif status == "claimed":
            # Currently in-flight, block next ones
            return None
    return None
