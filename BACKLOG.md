# Backlog

Open items and known gaps, mostly identified while verifying the pipeline
end-to-end on macOS and clean Ubuntu 24.04 (2026-07-19).

## Untested / needs verification

- **With-skills worker path.** Every verified run so far executed the
  "skill unavailable, continue" branch. Install the recommended skill set
  (see README) into a project's `.opencode/skills/`, confirm
  `sync_skills_to_worktree` delivers them, that workers actually invoke
  them, and that output quality/retry rates improve.
- **Multi-worker concurrency.** All verified runs used one worker and one
  task (`--concurrency 1`). Exercise several parents across several
  workers, including remote Ollama hosts, and watch for claim races.

## Hygiene

- **Private hostnames in git history.** `mini64pro.lan` and
  `gx10-444c.lan` appear in the initial commit's README. Current files
  are scrubbed; removing them entirely requires a history rewrite and
  force-push. Decide whether it's worth it.

## Improvements

- **Per-assertion specification text.** `swarm-tasks.toml` assertions are
  bare IDs (`["A1"]`), so prompts fall back to a generic "Verify
  correctness of this unit" — the smoke test works because DESIGN.md
  describes A1, but tasks should be able to carry real spec text per
  assertion (e.g. `assertions = [{ id = "A1", spec = "..." }]`) that
  flows into the `spec_text` prompt slot.
- **Pre-warm workers on cold hosts.** First runs on a fresh machine burn
  several respawn cycles while opencode fetches its provider package and
  Ollama loads the model (see smoke-test README). `setup.sh` or the
  orchestrator could pre-warm with a trivial completion before spawning.
- **Worker observability.** Worker logs capture only opencode's final
  text, not the tool-call trail; failed attempts are hard to reconstruct.
  Consider passing `--print-logs` through an env var (this session used a
  temporary patch to diagnose a provider error).
- **Review gates for test quality.** The red gate now checks collection
  plus exit code 1, but nothing enforces the ≤5-test cap or that tests
  target only their assertion; a worker can still over-test. Low priority
  while prompt discipline holds.
