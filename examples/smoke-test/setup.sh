#!/usr/bin/env bash
# Scaffold a minimal one-task project to verify a micro-swarm installation
# end-to-end: worker config, git worktree isolation, opencode + Ollama
# connectivity, and the phased review gates.
#
# Usage:
#   ./setup.sh [target-dir]
#
# Environment overrides:
#   SMOKE_HOST   Ollama host for the worker      (default: localhost)
#   SMOKE_MODEL  Model tag available on the host (default: qwen3.6:35b)
set -euo pipefail

TARGET="${1:-swarm-smoke-test}"
HOST="${SMOKE_HOST:-localhost}"
MODEL="${SMOKE_MODEL:-qwen3.6:35b}"

if [ -e "$TARGET" ]; then
    echo "error: $TARGET already exists; remove it or pick another dir" >&2
    exit 1
fi

for cmd in git python3 opencode; do
    command -v "$cmd" >/dev/null || { echo "error: $cmd not found in PATH" >&2; exit 1; }
done

if ! curl -sf --max-time 5 "http://$HOST:11434/api/version" >/dev/null; then
    echo "error: no Ollama endpoint responding at http://$HOST:11434" >&2
    exit 1
fi

mkdir -p "$TARGET/modules/calculator"
cd "$TARGET"

cat > swarm-tasks.toml <<EOF
[workers]
w1 = { host = "$HOST", model = "$MODEL" }

[[task]]
id = "T001"
module = "calculator"
acceptance = "pytest modules/calculator/tests/ -q"
assertions = ["A1"]
EOF

cat > modules/calculator/DESIGN.md <<'EOF'
# Calculator Module Design

A minimal pure-Python calculator library.

Source layout: modules/calculator/src/calculator.py
Tests: modules/calculator/tests/

## Assertions
- A1: `add(a, b)` returns the arithmetic sum of two numbers.
EOF

printf 'venv/\n.venv/\nstate/\nworktrees/\n__pycache__/\n' > .gitignore

git init -q -b main
git add -A
git -c user.email="smoke@micro-swarm.local" -c user.name="smoke-test" \
    commit -q -m "smoke test scaffold"

python3 -m venv .venv
.venv/bin/pip install -q pytest

cat <<EOF

Smoke test project ready in: $(pwd)
Worker: $HOST / $MODEL

Run it:
  cd $(pwd)
  micro-swarm --watch --concurrency 1 --loop-sleep 20

Watch progress from another terminal:
  micro-swarm --status
  tail -f state/logs/orchestrator.jsonl

Success looks like: T001 advances through phases R -> D -> A1.T -> A1.I,
each with a passing review, and state/done/T001.toml appears. Timing
depends entirely on your model and hardware (minutes, not seconds).
EOF
