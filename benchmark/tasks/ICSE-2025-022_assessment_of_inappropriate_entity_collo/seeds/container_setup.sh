#!/usr/bin/env bash
# Toolchain for ICSE-2025-022 (PairSmell / inappropriate entity collocation).
# Invoked as root once per TaskSandbox container start.
# Dataset is mounted read-only; this script installs Python analysis deps only.
# Author PairSmell Code/Docker/_Agreement labels are NOT on the mount — agents
# must detect InSep/InCol from modularization outputs vs folder modules.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
VENV_DIR="/opt/icse-2025-022-venv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ_FILE="${SCRIPT_DIR}/requirements.txt"
if [[ ! -f "$REQ_FILE" && -f /task/seeds/requirements.txt ]]; then
  REQ_FILE="/task/seeds/requirements.txt"
fi

# Prefer workspace-aligned mount; fall back to /shared.
PAIR_HOME="${PAIRSMELL_HOME:-}"
if [[ -z "$PAIR_HOME" || ! -d "$PAIR_HOME" ]]; then
  if [[ -d /workplace/dataset_candidate/pairsmell ]]; then
    PAIR_HOME="/workplace/dataset_candidate/pairsmell"
  elif [[ -d /shared/pairsmell ]]; then
    PAIR_HOME="/shared/pairsmell"
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

"${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
  -U pip setuptools wheel

if [[ -f "$REQ_FILE" ]]; then
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    -r "$REQ_FILE"
else
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    pandas numpy networkx scipy scikit-learn statsmodels matplotlib seaborn PyYAML tqdm pydriller
fi

"${VENV_DIR}/bin/python" - <<'PY'
import importlib.util

mods = [
    "numpy", "pandas", "scipy", "matplotlib", "seaborn",
    "statsmodels", "yaml", "networkx", "sklearn", "tqdm", "pydriller",
]
for mod in mods:
    check = "yaml" if mod == "yaml" else mod
    print(check, "ok" if importlib.util.find_spec(check) else "MISSING")
PY

if id agent >/dev/null 2>&1; then
  chown -R agent:agent "$VENV_DIR" || true
elif [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "${SUDO_UID}:${SUDO_GID}" "$VENV_DIR" || true
fi

n_projects=0
if [[ -n "${PAIR_HOME:-}" && -d "$PAIR_HOME" ]]; then
  n_projects="$(find "$PAIR_HOME" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
fi

command -v python3 >/dev/null
echo "[container_setup] OK ICSE-2025-022 Python=$("${VENV_DIR}/bin/python" --version 2>&1)"
echo "[container_setup] NOTE: artifact mounted at /shared/pairsmell;"
echo "[container_setup]       agent path: dataset_candidate/pairsmell/"
echo "[container_setup] NOTE: projects visible under mount: ${n_projects}"
echo "[container_setup] NOTE: detect InSep/InCol yourself; _Agreement labels were removed."
echo "[container_setup] NOTE: use ACDC/FCA/WCA_LIMBO + entities/deps/commits as inputs."
