#!/usr/bin/env bash
# Reproducible toolchain for FSE-2025-011 (PDCAT / compiler auto-tuning).
# Invoked as root once per TaskSandbox container start.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
VENV_DIR="/opt/fse-2025-011-venv"
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
        g++ \
        gcc \
        make \
        time \
        git \
        curl \
        wget \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        pkg-config \
        bc; then
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
for bin in gcc g++ make python3 time; do
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

# Paper uses GCC 13.1.0; base image ships Ubuntu 22.04 / gcc 11.4.
# Prefer newer toolchain when available without compiling GCC from source.
if ! command -v gcc-12 >/dev/null 2>&1; then
  apt-get install -y -qq --no-install-recommends gcc-12 g++-12 2>/dev/null || true
fi
if command -v gcc-12 >/dev/null 2>&1; then
  update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-12 120 2>/dev/null || true
  update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-12 120 2>/dev/null || true
fi

python3 -m venv "$VENV_DIR"
if [[ -f "$REQ_FILE" ]]; then
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    -r "$REQ_FILE"
else
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    numpy scipy pandas matplotlib pyyaml tqdm
fi

if id agent >/dev/null 2>&1; then
  chown -R agent:agent "$VENV_DIR"
elif [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "${SUDO_UID}:${SUDO_GID}" "$VENV_DIR"
fi

command -v gcc >/dev/null
command -v g++ >/dev/null
command -v make >/dev/null
command -v python3 >/dev/null

gcc_ver="$(gcc --version 2>/dev/null | head -1 || true)"
echo "[container_setup] OK FSE-2025-011 Python=$("${VENV_DIR}/bin/python" --version 2>&1) gcc=${gcc_ver}"
echo "[container_setup] NOTE: paper target is GCC 13.1.0; use mounted PDCAT scripts with --gcc_path=gcc"
