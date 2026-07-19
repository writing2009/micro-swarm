import argparse
import sys
from pathlib import Path
from .config import load_tasks, CLAIMS_DIR, DONE_DIR
from .segmenter import segment_task_phased, microtask_status
from .orchestrator import run_watch_loop

def print_status():
    """Print clean status table of all parent tasks and their segmented microtask phases."""
    data = load_tasks()
    tasks = data.get("tasks", {})
    
    if not tasks:
        print("No tasks found in swarm-tasks.toml.")
        return
        
    print("=" * 60)
    print(f"{'Task/Phase':25} | {'Phase Type':10} | {'Status':10}")
    print("=" * 60)
    
    for tid, t in sorted(tasks.items()):
        parent_status = "pending"
        if DONE_DIR.joinpath(f"{tid}.toml").exists():
            parent_status = "done"
        elif CLAIMS_DIR.joinpath(f"{tid}.toml").exists():
            parent_status = "claimed"
            
        print(f"{tid:25} | {'Parent':10} | {parent_status:10}")
        
        # Segment and display microtasks
        microtasks = segment_task_phased(t)
        for m in microtasks:
            mid = m["id"]
            m_status = microtask_status(mid)
            print(f"  - {mid:21} | {m['phase_type']:10} | {m_status:10}")
            
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description="Phased Microtask Swarm Orchestrator")
    parser.add_argument("--watch", action="store_true", help="Start the orchestrator watch loop")
    parser.add_argument("--status", action="store_true", help="Print current task status")
    parser.add_argument("--concurrency", type=int, default=3, help="Max parallel worker worktrees")
    parser.add_argument("--loop-sleep", type=int, default=120, help="Polling cycle delay in seconds")
    
    args = parser.parse_args()
    
    if args.status:
        print_status()
        sys.exit(0)
    elif args.watch:
        run_watch_loop(concurrency=args.concurrency, loop_sleep=args.loop_sleep)
        sys.exit(0)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
