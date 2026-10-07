#!/usr/bin/env bash
# Convenience launcher for ASE-2025-017 with EvoScientist.
set -euo pipefail

TASK_DIR="~/ai_scientist_inputs/ASE-2025-017_native_proof_certification_for_core_guid"
SCRIPT="~/ai_scientist_benchmark/integrations/run_evoscientist_task.py"

usage() {
  cat <<'EOF'
Usage:
  ./run_evoscientist_benchmark.sh prepare     # prepare run dir + Docker, no EvoSci launch
  ./run_evoscientist_benchmark.sh run         # prepare + launch
  ./run_evoscientist_benchmark.sh run-keep    # same as run (container kept)
  ./run_evoscientist_benchmark.sh resume      # print latest run dir and resume steps

Requires MSE 2024 weighted instances at ai_scientist_inputs/shared_datasets/maxsat2024.
Download/verify: ./download_maxsat2024_dataset.sh
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
    latest="$(ls -dt "$TASK_DIR"/workspace/evoscientist_* 2>/dev/null | head -1 || true)"
    if [[ -z "$latest" ]]; then
      echo "No evoscientist_* run directory found under $TASK_DIR/workspace" >&2
      exit 1
    fi
    echo "Latest run: $latest"
    echo
    if [[ -f "$latest/README_BENCHMARK.md" ]]; then
      sed -n '/## Manual launch/,/^## /p' "$latest/README_BENCHMARK.md" | head -n -1
    else
      echo "cd $latest"
      echo "export XDG_CONFIG_HOME=\"$latest/.xdg-config\""
      echo "export PATH=\"$latest/bin:\$PATH\""
      echo "EvoSci --workdir $latest --ui cli --auto-mode --auto-approve \\"
      echo "  -p \"\$(cat $latest/.evoscientist-benchmark/launch_prompt.txt)\""
    fi
    ;;
  -h|--help|help)
    usage
    ;;
  *)
    echo "Unknown command: $cmd" >&2
    usage >&2
    exit 1
    ;;
esac
