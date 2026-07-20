import json
import os
import shutil
import subprocess
from pathlib import Path
from .config import ROOT, WORKTREES_DIR

def create_worker_worktree(parent_id: str, worker_id: str) -> Path:
    """Create a git worktree on a unique branch to isolate the worker's changes."""
    WORKTREES_DIR.mkdir(parents=True, exist_ok=True)
    branch = f"ag-work-{parent_id}-{worker_id}"
    wt = WORKTREES_DIR / f"{worker_id}-{parent_id}"
    
    if not wt.exists():
        # Drop registrations for worktree dirs deleted outside git
        subprocess.run(
            ["git", "worktree", "prune"],
            cwd=str(ROOT), check=False, capture_output=True
        )
        # Check out a new branch off main; -B resets a branch left over
        # from a previous run of the same task
        subprocess.run(
            ["git", "worktree", "add", "-B", branch, str(wt), "main"],
            cwd=str(ROOT), check=True, capture_output=True
        )
        
    # Ensure virtualenv is symlinked so relative path resolutions work
    parent_venv = ROOT / ".venv"
    worker_venv = wt / ".venv"
    if parent_venv.exists() and not worker_venv.exists():
        try:
            worker_venv.symlink_to(parent_venv)
        except OSError:
            pass
            
    # Sync skills directory so the worker's skill tool can discover them
    sync_skills_to_worktree(wt)
    
    return wt

def sync_skills_to_worktree(wt: Path) -> None:
    """Copy the skill catalog from the main repo into the worktree's .opencode/skills."""
    src_skills = ROOT / ".opencode" / "skills"
    dst_skills = wt / ".opencode" / "skills"
    
    if dst_skills.exists():
        return # Already synced

    if not src_skills.exists():
        # Don't create the destination dir, so skills added later still sync
        return

    dst_skills.mkdir(parents=True, exist_ok=True)

    for entry in src_skills.iterdir():
        real_src = entry.resolve()
        if not real_src.exists():
            continue
            
        dst = dst_skills / entry.name
        try:
            if real_src.is_dir():
                shutil.copytree(real_src, dst, symlinks=False, dirs_exist_ok=True)
            else:
                shutil.copy2(real_src, dst)
        except Exception:
            pass

def write_worker_opencode_json(worker_id: str, wt: Path, worker_config: dict) -> Path:
    """Write an opencode.json configured for the specific worker and its LLM model endpoint."""
    opencode_dir = wt / ".opencode"
    opencode_dir.mkdir(parents=True, exist_ok=True)
    
    host = worker_config.get("host", "localhost")
    model = worker_config.get("model", "qwen3.6:35b")
    base = f"http://{host}:11434/v1"
    provider_name = f"ollama-{host.split('.')[0]}"
    
    cfg = {
        "$schema": "https://opencode.ai/config.json",
        "permission": {"*": "allow"},
        "model": f"{provider_name}/{model}",
        "provider": {
            provider_name: {
                "models": {model: {"name": model, "_launch": True}},
                "name": f"Ollama-{worker_id}",
                "npm": "@ai-sdk/openai-compatible",
                "options": {"baseURL": base},
            }
        }
    }
    
    cfg_file = opencode_dir / "opencode.json"
    cfg_file.write_text(json.dumps(cfg, indent=2))
    return cfg_file
