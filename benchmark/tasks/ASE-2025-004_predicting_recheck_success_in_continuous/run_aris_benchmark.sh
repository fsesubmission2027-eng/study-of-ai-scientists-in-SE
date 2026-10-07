#!/usr/bin/env bash
# Convenience launcher for ASE-2025-004 with ARIS benchmark integration.
set -euo pipefail

TASK_DIR="~/ai_scientist_inputs/ASE-2025-004_predicting_recheck_success_in_continuous"
SCRIPT="~/ai_scientist_benchmark/integrations/run_aris_task.py"

usage() {
  cat <<'EOF'
Usage:
  ./run_aris_benchmark.sh prepare          # prepare run dir + Docker, no ARIS launch
  ./run_aris_benchmark.sh run              # prepare + launch aris pipeline (default)
  ./run_aris_benchmark.sh run-keep         # like run, keep Docker container after exit
  ./run_aris_benchmark.sh resume         # print latest run dir and manual resume steps

Requires: aris (ARIS-Code CLI), docker, ai-scientist-base image, ~/.config/aris/config.json
EOF
}

cmd="${1:-run}"
shift || true

case "$cmd" in
  prepare)
    exec python3 "$SCRIPT" --task-dir "$TASK_DIR" --prepare-only "$@"
    ;;
  run)
    exec python3 "$SCRIPT" --task-dir "$TASK_DIR" --launch "$@"
    ;;
  run-keep)
    exec python3 "$SCRIPT" --task-dir "$TASK_DIR" --launch --keep-sandbox "$@"
    ;;
  resume)
    latest="$(ls -dt "$TASK_DIR"/workspace/aris_* 2>/dev/null | head -1 || true)"
    if [[ -z "$latest" ]]; then
      echo "No aris_* run directory found under $TASK_DIR/workspace" >&2
      exit 1
    fi
    echo "Latest run: $latest"
    echo
    echo "1) cd $latest"
    echo "2) export PATH=\"$latest/bin:\$PATH\""
    echo "3) aris"
    echo "4) /research-pipeline — resume <run_id>   # see .aris/runs/"
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "Unknown command: $cmd" >&2
    usage
    exit 1
    ;;
esac
