import os
import json
import time
import subprocess
from pathlib import Path
from .config import (
    ROOT, STATE, CLAIMS_DIR, DONE_DIR, REVIEW_DIR,
    MICRO_CLAIMS_DIR, MICRO_DONE_DIR, MICRO_REVIEW_DIR,
    LOGS_DIR, load_tasks, init_directories
)
from .segmenter import (
    segment_task_phased, next_pending_phased_microtask, 
    all_phased_microtasks_done, microtask_status
)
from .worktree import create_worker_worktree, write_worker_opencode_json
from .prompts import generate_phased_prompt
from .reviewer import review_phased_microtask

try:
    import tomllib  # py311+
except ModuleNotFoundError:
    import tomli as tomllib  # type: ignore

def log(msg: str, **kv) -> None:
    """Log structured events to logs and stdout."""
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    line = f"[{ts}] {msg}"
    if kv:
        line += " " + json.dumps(kv, default=str)
    print(line, flush=True)
    
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOGS_DIR / "orchestrator.jsonl", "a") as f:
        f.write(json.dumps({"ts": ts, "event": msg, **kv}) + "\n")

def claim_parent(task_id: str, worker_id: str) -> Path | None:
    """Claim a parent task and allocate its worktree."""
    claim_file = CLAIMS_DIR / f"{task_id}.toml"
    if claim_file.exists():
        d = load_claim(claim_file)
        return Path(d["worktree"]) if "worktree" in d else None
        
    wt = create_worker_worktree(task_id, worker_id)
    content = (
        f'task = "{task_id}"\n'
        f'worker = "{worker_id}"\n'
        f'worktree = "{wt}"\n'
        f'claimed_at = "{time.strftime("%Y-%m-%dT%H:%M:%S")}"\n'
    )
    claim_file.write_text(content)
    return wt

def load_claim(claim_file: Path) -> dict:
    """Read minimalist claim TOML."""
    if not claim_file.exists():
        return {}
    with open(claim_file, "rb") as f:
        return tomllib.load(f)

def claim_microtask(mtask_id: str, worker_id: str, wt: Path) -> bool:
    """Claim a single microtask."""
    claim_file = MICRO_CLAIMS_DIR / f"{mtask_id}.toml"
    if claim_file.exists():
        return False
    content = (
        f'task = "{mtask_id}"\n'
        f'worker = "{worker_id}"\n'
        f'worktree = "{wt}"\n'
        f'claimed_at = "{time.strftime("%Y-%m-%dT%H:%M:%S")}"\n'
    )
    claim_file.write_text(content)
    return True

def spawn_phased_worker(task: dict, mtask: dict, worker_id: str, wt: Path, worker_config: dict) -> None:
    """Spawn the local LLM agent to execute the microtask."""
    mtask_id = mtask["id"]
    
    # Generate prompt and config
    prompt = generate_phased_prompt(task, mtask)
    write_worker_opencode_json(worker_id, wt, worker_config)
    
    # Save prompt to temp file
    prompt_file = wt / ".opencode" / f"prompt-{mtask_id}.md"
    prompt_file.write_text(prompt)
    
    # Setup log file
    log_dir = LOGS_DIR / "micro" / worker_id
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"{mtask_id}.log"
    
    # Run the worker process
    lf = open(log_file, "w")
    host = worker_config.get("host", "localhost")
    model = worker_config.get("model", "qwen3.6:35b")
    provider_name = f"ollama-{host.split('.')[0]}"
    
    proc = subprocess.Popen(
        ["opencode", "run", "--auto", "-m", f"{provider_name}/{model}", str(prompt_file)],
        cwd=str(wt),
        stdout=lf,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        preexec_fn=os.setpgrp if hasattr(os, "setpgrp") else None
    )
    
    # Record PID in claim to allow reaping
    claim_file = MICRO_CLAIMS_DIR / f"{mtask_id}.toml"
    content = claim_file.read_text() + f"pid = {proc.pid}\n"
    claim_file.write_text(content)
    
    log("spawned_phased_microtask", task=mtask_id, worker=worker_id, pid=proc.pid)

def reap_microtask_workers() -> None:
    """Identify workers that crashed, timed out, or finished, and clean claims."""
    for claim_file in MICRO_CLAIMS_DIR.glob("*.toml"):
        mtask_id = claim_file.stem
        try:
            with open(claim_file, "rb") as f:
                c = tomllib.load(f)
            pid = c.get("pid")
            if not pid:
                continue
            
            # Check if PID is still active
            os.kill(pid, 0)
        except ProcessLookupError:
            # Worker process exited. Check if it completed
            done_file = MICRO_DONE_DIR / f"{mtask_id}.toml"
            if not done_file.exists():
                log("worker_crashed_no_done", task=mtask_id)
                claim_file.unlink() # Allow retry
        except Exception:
            pass

def run_watch_loop(concurrency: int = 3, loop_sleep: int = 120) -> None:
    """The central polling dispatcher loop."""
    init_directories()
    log("watch_start", concurrency=concurrency, loop_sleep=loop_sleep)
    
    while True:
        try:
            reap_microtask_workers()
            data = load_tasks()
            tasks = data["tasks"]
            workers = data["workers"]
            
            # Identify active workers
            busy_workers = set()
            for c in CLAIMS_DIR.glob("*.toml"):
                with open(c, "rb") as f:
                    w = tomllib.load(f).get("worker")
                    if w:
                        busy_workers.add(w)
            
            idle_workers = [w for w in workers if w not in busy_workers]
            
            # 1. Dispatch parent tasks to idle workers
            for tid, t in sorted(tasks.items()):
                if not idle_workers:
                    break
                
                # Verify parent task status (is it ready to start?)
                claim_file = CLAIMS_DIR / f"{tid}.toml"
                done_file = DONE_DIR / f"{tid}.toml"
                if claim_file.exists() or done_file.exists():
                    continue
                
                # Check concurrency ceiling
                if len(busy_workers) >= concurrency:
                    break
                    
                # Claim parent
                w = idle_workers.pop(0)
                busy_workers.add(w)
                wt = claim_parent(tid, w)
                log("claimed_parent_task", task=tid, worker=w, worktree=str(wt))
            
            # 2. Advance microtask state in claimed parents
            for c in CLAIMS_DIR.glob("*.toml"):
                parent_id = c.stem
                parent_task = tasks.get(parent_id)
                if not parent_task:
                    continue
                    
                claim_data = load_claim(c)
                worker = claim_data.get("worker")
                wt = Path(claim_data["worktree"])
                
                # Skip if we already have an active microtask in-flight for this parent
                micro_in_flight = False
                for mc in MICRO_CLAIMS_DIR.glob(f"{parent_id}.*.toml"):
                    mc_id = mc.stem
                    m_done = MICRO_DONE_DIR / f"{mc_id}.toml"
                    m_review = MICRO_REVIEW_DIR / f"{mc_id}.toml"
                    if not m_done.exists() or not m_review.exists():
                        micro_in_flight = True
                        break
                
                if micro_in_flight:
                    continue
                
                # Review any newly completed microtasks
                for done_f in MICRO_DONE_DIR.glob(f"{parent_id}.*.toml"):
                    mtask_id = done_f.stem
                    review_f = MICRO_REVIEW_DIR / f"{mtask_id}.toml"
                    if review_f.exists():
                        continue
                        
                    # Find microtask in segment list
                    microtasks = segment_task_phased(parent_task)
                    mtask = next((m for m in microtasks if m["id"] == mtask_id), None)
                    if mtask:
                        with open(done_f, "rb") as df:
                            done_data = tomllib.load(df)
                        
                        # Verify the microtask
                        acceptance_cmd = parent_task["acceptance"]
                        if mtask["phase_type"] in ("T", "I") and mtask["assertion_id"] != "R" and mtask["assertion_id"] != "D":
                            a_lower = mtask["assertion_id"].lower()
                            # Run target pytest assertion specifically
                            acceptance_cmd = f"pytest -k {a_lower}"
                            
                        ok = review_phased_microtask(mtask_id, mtask, wt, acceptance_cmd)
                        log("microtask_reviewed", task=mtask_id, ok=ok)
                        if not ok:
                            # Re-add to queue by removing claim
                            MICRO_CLAIMS_DIR.joinpath(f"{mtask_id}.toml").unlink(missing_ok=True)
                            done_f.unlink(missing_ok=True)
                
                # Spawn next pending microtask
                next_mtask = next_pending_phased_microtask(parent_task)
                if next_mtask:
                    if claim_microtask(next_mtask["id"], worker, wt):
                        spawn_phased_worker(parent_task, next_mtask, worker, wt, workers[worker])
                elif all_phased_microtasks_done(parent_task):
                    # Write parent done file
                    parent_done = DONE_DIR / f"{parent_id}.toml"
                    if not parent_done.exists():
                        parent_done.write_text(f'task = "{parent_id}"\nworker = "{worker}"\n')
                        log("parent_task_completed", task=parent_id)
                        
        except Exception as e:
            log("orchestrator_error", err=str(e))
            
        if loop_sleep <= 0:
            break
        time.sleep(loop_sleep)
