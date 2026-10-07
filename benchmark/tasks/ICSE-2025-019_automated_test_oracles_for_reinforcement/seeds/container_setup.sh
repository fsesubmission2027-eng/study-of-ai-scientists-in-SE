#!/usr/bin/env bash
# Toolchain for ICSE-2025-019 (LPEA / RL software test oracle).
# Invoked as root once per TaskSandbox container start.
# Artifact is mounted read-only; this script installs Python/RL deps only.
# Optional: editable install of mounted SB3 fork into the venv (copy-on-write under /opt).
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
VENV_DIR="/opt/icse-2025-019-venv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ_FILE="${SCRIPT_DIR}/requirements.txt"
if [[ ! -f "$REQ_FILE" && -f /task/seeds/requirements.txt ]]; then
  REQ_FILE="/task/seeds/requirements.txt"
fi

# Prefer workspace-aligned mount; fall back to legacy /shared path.
LPEA_REPO="${LPEA_REPO_HOME:-}"
if [[ -z "$LPEA_REPO" || ! -d "$LPEA_REPO" ]]; then
  if [[ -d /workplace/dataset_candidate/lpea-oracle-icse2025/RL-Oracle-Lyapunov-v1 ]]; then
    LPEA_REPO="/workplace/dataset_candidate/lpea-oracle-icse2025/RL-Oracle-Lyapunov-v1"
  elif [[ -d /shared/lpea-oracle-icse2025/RL-Oracle-Lyapunov-v1 ]]; then
    LPEA_REPO="/shared/lpea-oracle-icse2025/RL-Oracle-Lyapunov-v1"
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
        swig \
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

# CPU torch keeps container startup reliable without NVIDIA drivers.
# Agents with GPU can reinstall a CUDA build inside project/ if needed.
"${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
  --index-url https://download.pytorch.org/whl/cpu \
  "torch==2.4.0"

if [[ -f "$REQ_FILE" ]]; then
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    -r "$REQ_FILE"
else
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    "gymnasium>=0.28.1,<0.30" numpy pandas matplotlib scipy cvxpy control openpyxl tqdm
fi

# Editable SB3 from the paper artifact (commit lineage ~4efee92 + LPEA hooks).
# Mount is often :ro — copy into /opt then pip install -e.
if [[ -n "${LPEA_REPO:-}" && -f "${LPEA_REPO}/setup.py" ]]; then
  SB3_EDITABLE="/opt/icse-2025-019-sb3"
  rm -rf "$SB3_EDITABLE"
  mkdir -p "$SB3_EDITABLE"
  # Prefer rsync if available; else cp -a
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --exclude '.git' --exclude '__pycache__' --exclude 'docs' \
      --exclude 'tests' --exclude 'archived_code' \
      "${LPEA_REPO}/" "$SB3_EDITABLE/"
  else
    cp -a "${LPEA_REPO}/." "$SB3_EDITABLE/"
  fi
  (
    cd "$SB3_EDITABLE"
    "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir -e .
  )
  echo "[container_setup] Installed editable SB3 from artifact -> $SB3_EDITABLE"
else
  echo "[container_setup] WARN: LPEA SB3 fork not found; installing PyPI stable-baselines3 as fallback"
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    "stable-baselines3>=2.3.0,<3"
fi

"${VENV_DIR}/bin/python" - <<'PY'
import gymnasium
import numpy
import torch
import importlib.util

print(
    "torch", torch.__version__,
    "cuda", torch.cuda.is_available(),
    "gymnasium", gymnasium.__version__,
    "numpy", numpy.__version__,
)
spec = importlib.util.find_spec("stable_baselines3")
print("stable_baselines3", "ok" if spec else "MISSING")
for mod in ("cvxpy", "control", "openpyxl", "scipy"):
    print(mod, "ok" if importlib.util.find_spec(mod) else "MISSING")
PY

if id agent >/dev/null 2>&1; then
  chown -R agent:agent "$VENV_DIR" || true
  [[ -d /opt/icse-2025-019-sb3 ]] && chown -R agent:agent /opt/icse-2025-019-sb3 || true
elif [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "${SUDO_UID}:${SUDO_GID}" "$VENV_DIR" || true
  [[ -d /opt/icse-2025-019-sb3 ]] && chown -R "${SUDO_UID}:${SUDO_GID}" /opt/icse-2025-019-sb3 || true
fi

command -v python3 >/dev/null
echo "[container_setup] OK ICSE-2025-019 Python=$("${VENV_DIR}/bin/python" --version 2>&1)"
echo "[container_setup] NOTE: artifact mounted at /shared/lpea-oracle-icse2025;"
echo "[container_setup]       agent path: dataset_candidate/lpea-oracle-icse2025/"
echo "[container_setup] NOTE: oracle entry: RL-Oracle-Lyapunov-v1/RLTestingLyapunov/LPEA_Oracle.py"
echo "[container_setup] NOTE: paper full eval ~<=129h on RTX 3060 laptop."
echo "[container_setup] NOTE: CPU torch preinstalled; reinstall CUDA torch in project/ if GPU available."
