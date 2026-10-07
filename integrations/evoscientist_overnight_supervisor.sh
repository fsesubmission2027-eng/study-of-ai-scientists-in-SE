#!/usr/bin/env bash
# Monitor an EvoScientist benchmark run and resume in tmux if the host collector dies.
set -u

RUN_DIR="${1:-}"
TASK_DIR="${2:-}"
THREAD="${3:-}"
CONTAINER="${4:-}"
LOG="${RUN_DIR}/overnight_supervisor.log"

if [[ -z "$RUN_DIR" || -z "$TASK_DIR" || -z "$THREAD" ]]; then
  echo "usage: $0 <run_dir> <task_dir> <thread_id> [container_id]" >&2
  exit 2
fi

export PATH="${HOME}/miniconda3/envs/EvoSci/bin:${PATH:-}"
BENCH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LEDGER="${RUN_DIR}/artifacts/usage_ledger.jsonl"

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG"; }

agent_alive() {
  if [[ -n "$CONTAINER" ]] && docker ps -q --filter "id=${CONTAINER}" | grep -q .; then
    docker exec "$CONTAINER" pgrep -f evoscientist_launcher >/dev/null 2>&1 && return 0
    docker exec "$CONTAINER" pgrep -f 'EvoSci --workdir' >/dev/null 2>&1 && return 0
  fi
  return 1
}

ledger_lines() {
  [[ -f "$LEDGER" ]] && wc -l < "$LEDGER" || echo 0
}

resume_run() {
  log "starting resume thread=${THREAD} run_dir=${RUN_DIR}"
  cd "$BENCH"
  exec python3 integrations/run_evoscientist_task.py \
    --task-dir "$TASK_DIR" \
    --run-dir "$RUN_DIR" \
    --resume-thread "$THREAD" \
    --launch
}

log "supervisor started run_dir=${RUN_DIR} thread=${THREAD} container=${CONTAINER:-none}"

last_lines="$(ledger_lines)"
stall=0
while true; do
  if agent_alive; then
    cur="$(ledger_lines)"
    if [[ "$cur" -gt "$last_lines" ]]; then
      log "agent alive ledger_lines=${cur}"
      last_lines="$cur"
      stall=0
    else
      stall=$((stall + 1))
      log "agent alive no new ledger (${stall}) lines=${cur}"
    fi
    sleep 30
    continue
  fi

  log "agent not running in container; attempting resume"
  resume_run
  exit $?
done
