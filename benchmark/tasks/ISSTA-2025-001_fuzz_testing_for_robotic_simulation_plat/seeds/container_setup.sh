#!/usr/bin/env bash
# Toolchain for ISSTA-2025-001 (GzFuzz / Gazebo simulator fuzzing).
# Invoked as root once per TaskSandbox container start.
# Artifact is mounted read-only; installs Python/RL analysis deps.
# Full Gazebo 8.0.0 + LCOV coverage builds are NOT installed here —
# sandbox path prefers re-analysis of mounted data/ (AFL++/Fuzzotron/GzFuzz runs).
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
VENV_DIR="/opt/issta-2025-001-venv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ_FILE="${SCRIPT_DIR}/requirements.txt"
if [[ ! -f "$REQ_FILE" && -f /task/seeds/requirements.txt ]]; then
  REQ_FILE="/task/seeds/requirements.txt"
fi

ART_HOME="${GZFUZZ_HOME:-}"
if [[ -z "$ART_HOME" || ! -d "$ART_HOME" ]]; then
  if [[ -d /workplace/dataset_candidate/gzfuzz-issta2025 ]]; then
    ART_HOME="/workplace/dataset_candidate/gzfuzz-issta2025"
  elif [[ -d /shared/gzfuzz-issta2025 ]]; then
    ART_HOME="/shared/gzfuzz-issta2025"
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
        libxml2-dev \
        libxslt1-dev \
        protobuf-compiler \
        libprotobuf-dev \
        time \
        bc \
        procps \
        jq \
        lcov; then
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

# CPU torch first (matches paper Readme: pytorch 2.4.1+cpu)
"${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
  --index-url https://download.pytorch.org/whl/cpu \
  "torch==2.4.1" || \
"${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir "torch==2.4.1"

if [[ -f "$REQ_FILE" ]]; then
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    -r "$REQ_FILE" || true
fi

"${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
  "randomproto==0.0.1" || \
  echo "[container_setup] WARN: randomproto==0.0.1 not installed (optional)"

"${VENV_DIR}/bin/python" - <<'PY'
import importlib.util

def ok(name: str) -> bool:
    try:
        if name == "google.protobuf":
            import google.protobuf  # noqa: F401
            return True
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False

for mod in ("torch", "numpy", "scipy", "sklearn", "lxml", "google.protobuf",
            "psutil", "git", "matplotlib", "seaborn", "pandas", "yaml"):
    print(mod, "ok" if ok(mod) else "MISSING")
PY

if id agent >/dev/null 2>&1; then
  chown -R agent:agent "$VENV_DIR" || true
elif [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "${SUDO_UID}:${SUDO_GID}" "$VENV_DIR" || true
fi

n_data_dirs=0
if [[ -n "${ART_HOME:-}" && -d "${ART_HOME}/data" ]]; then
  n_data_dirs="$(find "${ART_HOME}/data" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ')"
fi

command -v python3 >/dev/null
echo "[container_setup] OK ISSTA-2025-001 Python=$("${VENV_DIR}/bin/python" --version 2>&1)"
echo "[container_setup] NOTE: artifact mounted at /shared/gzfuzz-issta2025;"
echo "[container_setup]       agent path: dataset_candidate/gzfuzz-issta2025/"
echo "[container_setup] NOTE: data/ method dirs visible: ${n_data_dirs}"
echo "[container_setup] NOTE: primary sandbox path = re-analyze mounted data/ (crashes/coverage)."
echo "[container_setup] NOTE: full Gazebo 8.0.0 + colcon Coverage build is NOT installed in this venv."
echo "[container_setup] NOTE: paper eval = 12h x 5 runs."
