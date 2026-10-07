#!/usr/bin/env bash
# Toolchain for ISSTA-2025-002 (RouthSearch / UAV PID range identification).
# Invoked as root once per TaskSandbox container start.
# Artifact is mounted read-only; installs Python + pymavlink analysis deps.
# Full ArduPilot SITL + PX4 jMAVSim are NOT installed here —
# sandbox path prefers oracle code / sample oracle_logs re-analysis.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
VENV_DIR="/opt/issta-2025-002-venv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ_FILE="${SCRIPT_DIR}/requirements.txt"
if [[ ! -f "$REQ_FILE" && -f /task/seeds/requirements.txt ]]; then
  REQ_FILE="/task/seeds/requirements.txt"
fi

ART_HOME="${ROUTHSEARCH_HOME:-}"
if [[ -z "$ART_HOME" || ! -d "$ART_HOME" ]]; then
  if [[ -d /workplace/dataset_candidate/routhsearch-issta2025 ]]; then
    ART_HOME="/workplace/dataset_candidate/routhsearch-issta2025"
  elif [[ -d /shared/routhsearch-issta2025 ]]; then
    ART_HOME="/shared/routhsearch-issta2025"
  fi
fi

apt_retry() {
  local attempt
  for attempt in 1 2 3; do
    if apt-get update -qq \
      && apt-get install -y -qq --no-install-recommends --fix-missing \
        build-essential \
        gcc \
        g++ \
        git \
        curl \
        wget \
        ca-certificates \
        unzip \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        pkg-config \
        libxml2-dev \
        libxslt1-dev \
        time \
        bc \
        procps \
        jq; then
      return 0
    fi
    if [[ "$attempt" -eq 3 ]]; then
      echo "[container_setup] apt install failed after 3 attempts" >&2
      return 1
    fi
    echo "[container_setup] apt attempt ${attempt}/3 failed; retrying..." >&2
    sleep $((attempt * 5))
  done
}

need_apt=0
for bin in gcc g++ git python3; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    need_apt=1
    break
  fi
done
if ! python3 -m venv --help >/dev/null 2>&1; then
  need_apt=1
fi
if [[ "$need_apt" -eq 1 ]]; then
  apt_retry
fi

python3 -m venv "$VENV_DIR"
"${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
  -U pip setuptools wheel

if [[ -f "$REQ_FILE" ]]; then
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    -r "$REQ_FILE" || true
fi

"${VENV_DIR}/bin/python" - <<'PY'
import importlib.util

def ok(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False

for mod in ("pymavlink", "numpy", "matplotlib", "scipy", "pandas", "yaml", "psutil"):
    print(mod, "ok" if ok(mod) else "MISSING")
PY

if id agent >/dev/null 2>&1; then
  chown -R agent:agent "$VENV_DIR" || true
elif [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "${SUDO_UID}:${SUDO_GID}" "$VENV_DIR" || true
fi

# Counting dirs is best-effort only — never fail the toolchain install because
# find hit a permission/IO quirk on a read-only dataset mount (pipefail).
n_eval=0
n_oracle_logs=0
if [[ -n "${ART_HOME:-}" && -d "${ART_HOME}/evaluation_script" ]]; then
  n_eval="$(find "${ART_HOME}/evaluation_script" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | wc -l | tr -d ' ' || true)"
fi
if [[ -n "${ART_HOME:-}" && -d "${ART_HOME}" ]]; then
  n_oracle_logs="$(find "${ART_HOME}" -type d -name oracle_logs 2>/dev/null | wc -l | tr -d ' ' || true)"
fi

command -v python3 >/dev/null
echo "[container_setup] OK ISSTA-2025-002 Python=$("${VENV_DIR}/bin/python" --version 2>&1)"
echo "[container_setup] NOTE: artifact mounted at /shared/routhsearch-issta2025;"
echo "[container_setup]       agent path: dataset_candidate/routhsearch-issta2025/"
echo "[container_setup] NOTE: evaluation_script mode dirs: ${n_eval}; oracle_logs dirs: ${n_oracle_logs}"
echo "[container_setup] NOTE: artifact includes oracle code + sample logs under /shared/routhsearch-issta2025."
echo "[container_setup] NOTE: full ArduPilot SITL + PX4 jMAVSim are NOT installed in this venv."
echo "[container_setup] NOTE: paper GT construction ≈ 7000 CPU hours; discovery budget 48h."
exit 0
