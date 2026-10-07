#!/bin/bash
set -euo pipefail
WORKSPACE=/workspace
RESULT_DIR=/evaluator/results
mkdir -p "$RESULT_DIR"

score=0

[ -f "$WORKSPACE/README.md" ] || [ -f "$WORKSPACE/main.py" ] && score=$((score+20))
[ -d "$WORKSPACE/results" ] && [ "$(ls -A "$WORKSPACE/results" 2>/dev/null)" ] && score=$((score+30))
[ -f "$WORKSPACE/paper/main.tex" ] && score=$((score+25))
[ -f "$WORKSPACE/idea.md" ] && score=$((score+25))

echo "{\"task_id\":\"ASE-2025-001\",\"score\":$score,\"max\":100}" | tee "$RESULT_DIR/result.json"