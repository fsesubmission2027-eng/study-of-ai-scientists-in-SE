#!/usr/bin/env bash
# Toolchain for ISSTA-2025-007 (function-level ML4VD benchmark validity).
# Invoked as root once per TaskSandbox container start.
# Artifact is mounted read-only; installs sklearn/transformers stack for RQ2.
# Full Devign / ReVeal GNN training stacks are NOT installed here.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
VENV_DIR="/opt/issta-2025-007-venv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ_FILE="${SCRIPT_DIR}/requirements.txt"
if [[ ! -f "$REQ_FILE" && -f /task/seeds/requirements.txt ]]; then
  REQ_FILE="/task/seeds/requirements.txt"
fi

ART_HOME="${TOPSCOREWRONGEXAM_HOME:-}"
if [[ -z "$ART_HOME" || ! -d "$ART_HOME" ]]; then
  if [[ -d /workplace/dataset_candidate/topscorewrongexam-issta2025 ]]; then
    ART_HOME="/workplace/dataset_candidate/topscorewrongexam-issta2025"
  elif [[ -d /shared/topscorewrongexam-issta2025 ]]; then
    ART_HOME="/shared/topscorewrongexam-issta2025"
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
        git-lfs \
        curl \
        wget \
        ca-certificates \
        unzip \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        pkg-config \
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
for bin in gcc g++ git python3 unzip; do
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

git lfs install --skip-repo >/dev/null 2>&1 || true

python3 -m venv "$VENV_DIR"
"${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
  -U pip setuptools wheel

if [[ -f "$REQ_FILE" ]]; then
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    -r "$REQ_FILE"
else
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    "numpy>=1.26" "pandas>=2.0" "scikit-learn>=1.3" matplotlib tqdm PyYAML \
    transformers sentencepiece tokenizers
fi

"${VENV_DIR}/bin/python" - <<'PY'
import importlib.util

def ok(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False

import numpy
print("numpy", numpy.__version__)
for mod in ("pandas", "sklearn", "matplotlib", "transformers", "tokenizers"):
    print(mod, "ok" if ok(mod) else "MISSING")
PY

if id agent >/dev/null 2>&1; then
  chown -R agent:agent "$VENV_DIR" || true
elif [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "${SUDO_UID}:${SUDO_GID}" "$VENV_DIR" || true
fi

have_bigvul=0
have_devign=0
have_diverse=0
have_labeled=0
have_scripts=0
[[ -n "${ART_HOME:-}" && -f "${ART_HOME}/original_datasets/BigVul/MSR_data_cleaned.csv" ]] && have_bigvul=1
[[ -n "${ART_HOME:-}" && -f "${ART_HOME}/original_datasets/Devign/function.json" ]] && have_devign=1
[[ -n "${ART_HOME:-}" && -f "${ART_HOME}/original_datasets/DiverseVul/diversevul_20230702.json" ]] && have_diverse=1
[[ -n "${ART_HOME:-}" && -d "${ART_HOME}/labeled_samples" ]] && have_labeled=1
[[ -n "${ART_HOME:-}" && -d "${ART_HOME}/scripts" ]] && have_scripts=1

command -v python3 >/dev/null
echo "[container_setup] OK ISSTA-2025-007 Python=$("${VENV_DIR}/bin/python" --version 2>&1)"
echo "[container_setup] NOTE: artifact at /shared/topscorewrongexam-issta2025;"
echo "[container_setup]       agent path: dataset_candidate/topscorewrongexam-issta2025/"
echo "[container_setup] NOTE: bigvul=${have_bigvul} devign=${have_devign} diversevul=${have_diverse} labeled=${have_labeled} scripts=${have_scripts}"
echo "[container_setup] NOTE: RQ2 scripts expect cwd at artifact root (original_datasets/...)."
echo "[container_setup] NOTE: Devign/ReVeal deep models not preinstalled; add torch/etc. under project/ if needed."
