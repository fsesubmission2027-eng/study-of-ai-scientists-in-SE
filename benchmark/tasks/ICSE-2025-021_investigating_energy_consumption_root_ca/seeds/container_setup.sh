#!/usr/bin/env bash
# Toolchain for ICSE-2025-021 (EnergyDebug / Redis energy root-cause analysis).
# Invoked as root once per TaskSandbox container start.
# Artifact is mounted read-only; this script installs Python analysis deps only.
# Note: new EnergiBridge measurements need bare-metal MSR access and are NOT
# installed here — sandbox path is notebook re-analysis of mounted data/.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
VENV_DIR="/opt/icse-2025-021-venv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ_FILE="${SCRIPT_DIR}/requirements.txt"
if [[ ! -f "$REQ_FILE" && -f /task/seeds/requirements.txt ]]; then
  REQ_FILE="/task/seeds/requirements.txt"
fi

# Prefer workspace-aligned mount; fall back to /shared.
ENERGY_HOME="${ENERGYDEBUG_HOME:-}"
if [[ -z "$ENERGY_HOME" || ! -d "$ENERGY_HOME" ]]; then
  if [[ -d /workplace/dataset_candidate/energydebug-icse2025 ]]; then
    ENERGY_HOME="/workplace/dataset_candidate/energydebug-icse2025"
  elif [[ -d /shared/energydebug-icse2025 ]]; then
    ENERGY_HOME="/shared/energydebug-icse2025"
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
        gfortran \
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
        libopenblas-dev \
        liblapack-dev \
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

# Prefer artifact requirements when present on the mount (exact paper pins).
INSTALL_REQ="$REQ_FILE"
if [[ -n "${ENERGY_HOME:-}" && -f "${ENERGY_HOME}/requirements.txt" ]]; then
  INSTALL_REQ="${ENERGY_HOME}/requirements.txt"
  echo "[container_setup] Using artifact requirements: $INSTALL_REQ"
fi

"${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
  -U pip setuptools wheel

"${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
  -r "$INSTALL_REQ"

# Jupyter execution path used by artifact README smoke check
"${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
  "jupyter>=1.0" "nbconvert>=7.0" "ipykernel>=6.0"

"${VENV_DIR}/bin/python" - <<'PY'
import importlib.util

mods = [
    "numpy", "pandas", "scipy", "matplotlib", "seaborn",
    "statsmodels", "yaml", "psutil", "sklearn",
]
for mod in mods:
    name = "sklearn" if mod == "sklearn" else mod
    # pyyaml imports as yaml
    check = "yaml" if mod == "yaml" else mod
    print(check, "ok" if importlib.util.find_spec(check) else "MISSING")
print("nbconvert", "ok" if importlib.util.find_spec("nbconvert") else "MISSING")
PY

if id agent >/dev/null 2>&1; then
  chown -R agent:agent "$VENV_DIR" || true
elif [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "${SUDO_UID}:${SUDO_GID}" "$VENV_DIR" || true
fi

command -v python3 >/dev/null
echo "[container_setup] OK ICSE-2025-021 Python=$("${VENV_DIR}/bin/python" --version 2>&1)"
echo "[container_setup] NOTE: artifact mounted at /shared/energydebug-icse2025;"
echo "[container_setup]       agent path: dataset_candidate/energydebug-icse2025/"
echo "[container_setup] NOTE: primary path = re-run energydebug.ipynb on mounted data/."
echo "[container_setup] NOTE: new EnergiBridge collection needs bare-metal AMD/Intel MSR (not in this venv)."
