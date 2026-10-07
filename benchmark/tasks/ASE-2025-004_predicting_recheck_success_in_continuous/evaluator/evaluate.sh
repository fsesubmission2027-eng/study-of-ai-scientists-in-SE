#!/bin/bash
set -euo pipefail

WORKSPACE=/workspace
RESULT_DIR=/evaluator/results
mkdir -p "$RESULT_DIR"

score=0

[ -f "$WORKSPACE/README.md" ] || [ -f "$WORKSPACE/main.py" ] || [ -f "$WORKSPACE/project/run_training_testing.py" ] && score=$((score + 15))
[ -f "$WORKSPACE/project/train_model.py" ] || [ -f "$WORKSPACE/project/run_training_testing.py" ] && score=$((score + 20))
[ -f "$WORKSPACE/results/metrics.json" ] && score=$((score + 25))
[ -f "$WORKSPACE/idea.md" ] && score=$((score + 10))
[ -d "$WORKSPACE/paper" ] && [ -f "$WORKSPACE/paper/main.tex" ] && score=$((score + 10))

if [ -f "$WORKSPACE/results/metrics.json" ]; then
  python3 - <<'PY' && score=$((score + 20))
import json, sys
from pathlib import Path
m = json.loads(Path("/workspace/results/metrics.json").read_text())
for key in ("auroc", "brier_score", "auprc"):
    if key not in m or not isinstance(m[key], (int, float)):
        sys.exit(1)
PY
fi

echo "{\"task_id\":\"ASE-2025-004\",\"score\":$score,\"max\":100}" | tee "$RESULT_DIR/result.json"
