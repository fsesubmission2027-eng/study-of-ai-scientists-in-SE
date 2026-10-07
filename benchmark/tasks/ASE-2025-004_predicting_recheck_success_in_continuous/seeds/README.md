# Seeds for ASE-2025-004 — OpenStack CI Recheck Prediction

This task predicts whether a CI recheck request will succeed using historical
features (bot/job/user history, patch metadata, timing).

## Recommended data strategy

1. **Agents (benchmark runs)**  
   Use real OpenStack Gerrit recheck data or another authentic source.  
   **`sample_rechecks.csv` is not copied into agent workspaces** (human smoke-test only).

2. **Human smoke test (optional)**  
   `sample_rechecks.csv` — local pipeline validation only; do not use for agent evaluation.

## Files

- `sample_rechecks.csv` — synthetic sample (~200 rows) for smoke testing
- `requirements.txt` — task-specific Python deps (already in base image)

## Feature families (from paper)

- bot history: bot success ratio, flip ratio, diff avg success/failure
- job history: job success ratio
- patch info: insertions, deletions, file numbers, file success ratio
- timing: month, day, hour, minute
- user: user success ratio, user status, experience
