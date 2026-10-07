#!/usr/bin/env bash
# Toolchain for ICSE-2025-017 (TON FunC/Tact smart-contract defect detection).
# Invoked as root once per TaskSandbox container start.
# Datasets are mounted read-only; this script installs build/analysis deps only.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
VENV_DIR="/opt/icse-2025-017-venv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ_FILE="${SCRIPT_DIR}/requirements.txt"
if [[ ! -f "$REQ_FILE" && -f /task/seeds/requirements.txt ]]; then
  REQ_FILE="/task/seeds/requirements.txt"
fi

apt_retry() {
  local attempt
  for attempt in 1 2 3; do
    if apt-get update -qq \
      && apt-get install -y -qq --no-install-recommends --fix-missing \
        build-essential \
        gcc \
        g++ \
        make \
        cmake \
        ninja-build \
        git \
        curl \
        wget \
        ca-certificates \
        unzip \
        zip \
        tar \
        xz-utils \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        time \
        bc \
        procps \
        jq \
        pkg-config \
        zlib1g-dev \
        libssl-dev \
        flex \
        bison \
        nodejs \
        npm; then
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
for bin in gcc g++ cmake python3 unzip git; do
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
if [[ -f "$REQ_FILE" ]]; then
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    -r "$REQ_FILE"
else
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    numpy pandas matplotlib scipy pyyaml tqdm
fi

if id agent >/dev/null 2>&1; then
  chown -R agent:agent "$VENV_DIR" || true
elif [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "${SUDO_UID}:${SUDO_GID}" "$VENV_DIR" || true
fi

command -v gcc >/dev/null
command -v g++ >/dev/null
command -v cmake >/dev/null
command -v python3 >/dev/null

gcc_ver="$(gcc --version 2>/dev/null | head -1 || true)"
cmake_ver="$(cmake --version 2>/dev/null | head -1 || true)"
node_ver="$(node --version 2>/dev/null || echo 'node=missing')"

echo "[container_setup] OK ICSE-2025-017 Python=$("${VENV_DIR}/bin/python" --version 2>&1)"
echo "[container_setup] ${gcc_ver} | ${cmake_ver} | ${node_ver}"
echo "[container_setup] NOTE: dataset mounted read-only at /shared/ton-smart-contract-defects;"
echo "[container_setup]       agent path: dataset_candidate/ton-smart-contract-defects/"
echo "[container_setup] NOTE: FunC sources under contracts/ and repo/; labeled samples/ for precision."
echo "[container_setup] NOTE: optional baseline ELF at tools/TONScanner (needs LD_LIBRARY_PATH=tools/lib64)."
echo "[container_setup] NOTE: paper machine ~120GB RAM; sandbox MEMORY may be lower —"
echo "[container_setup]       use disclosed subsets when needed. Tact→FunC already prepared in artifact."
echo "[container_setup] NOTE: FunC/Tact compilers not preinstalled; fetch ton.org / tact toolchain if rebuilding IR."
