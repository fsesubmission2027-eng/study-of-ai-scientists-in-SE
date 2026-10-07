# Seeds for FSE-2025-001 — Targeted Java Unit Test Generation

## Agent data policy

**Agents must not use pilot/synthetic sample CSVs.** Evaluation must run on **Defects4J**
via the shared mount (`DEFECTS4J_HOME=/shared/defects4j` inside Docker).

Human-only files live in `seeds/` root. Agent-visible config is under `seeds/agent/` only.

## Defects4J

Mounted read-only at `/shared/defects4j` (see `task.env`).

```bash
defects4j info -p Lang
defects4j checkout -p Lang -v 1b -w /tmp/lang-1b
```

Host path: `~/ai_scientist_inputs/shared_datasets/defects4j`

## Layout

| Path | Visible to agent? | Purpose |
|------|-------------------|---------|
| `agent/dataset_paths.json` | Yes | Defects4J paths |
| `agent/metrics.json` | Yes | Required metrics keys |
| `requirements.txt` | No (pip only) | Python deps for orchestration |
| `benchmark_config.json` | No | Staging rules for benchmark integration |
| `README.md` | No | Human documentation |

## Baselines

- Randoop: bundled under Defects4J after `init.sh`
- EvoSuite: bundled under Defects4J after `init.sh`
