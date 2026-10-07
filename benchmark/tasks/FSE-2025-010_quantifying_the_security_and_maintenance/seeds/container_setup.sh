#!/usr/bin/env bash
# Reproducible toolchain for FSE-2025-010 (npm pinning vs floating empirical study).
# Invoked as root once per TaskSandbox container start.
#
# Node note: DeepScientist requires Node >= 18. Do NOT install Ubuntu's nodejs 12
# (it leaves libnode-dev and breaks NodeSource Node 20 upgrades).
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
VENV_DIR="/opt/fse-2025-010-venv"
NODE_MAJOR_MIN=18
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
        git \
        curl \
        wget \
        ca-certificates \
        gnupg \
        unzip \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        pkg-config \
        r-base-core \
        r-base-dev; then
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

node_major() {
  if ! command -v node >/dev/null 2>&1; then
    echo 0
    return 0
  fi
  node -p "process.versions.node.split('.')[0]" 2>/dev/null || echo 0
}

purge_distro_node() {
  # Ubuntu nodejs leaves libnode-dev / libnode72 which conflict with NodeSource.
  apt-get remove -y --purge \
    nodejs npm libnode-dev libnode72 2>/dev/null || true
  apt-get autoremove -y 2>/dev/null || true
}

ensure_node20() {
  local major
  major="$(node_major)"
  if [[ "$major" -ge "$NODE_MAJOR_MIN" ]]; then
    return 0
  fi

  echo "[container_setup] installing Node.js 20 (found major=${major}, need >= ${NODE_MAJOR_MIN})"
  purge_distro_node
  apt-get update -qq
  apt-get install -y -qq --no-install-recommends ca-certificates curl gnupg
  curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
  # Defensive: purge again in case setup pulled meta packages
  purge_distro_node
  apt-get install -y -qq --no-install-recommends nodejs
  major="$(node_major)"
  if [[ "$major" -lt "$NODE_MAJOR_MIN" ]]; then
    echo "[container_setup] ERROR: node major=${major} after install" >&2
    return 1
  fi
}

need_apt=0
for bin in python3 curl; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    need_apt=1
    break
  fi
done
if ! python3 -m venv --help >/dev/null 2>&1; then
  need_apt=1
fi
# R is optional but preferred for panel-regression notebooks in the artifact.
if ! command -v Rscript >/dev/null 2>&1; then
  need_apt=1
fi
if [[ "$need_apt" -eq 1 ]]; then
  apt_retry
fi

ensure_node20

python3 -m venv "$VENV_DIR"
if [[ -f "$REQ_FILE" ]]; then
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    -r "$REQ_FILE"
else
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    numpy \
    pandas \
    matplotlib \
    scipy \
    statsmodels \
    networkx \
    pyyaml \
    tqdm \
    jupyter \
    openpyxl
fi

if id agent >/dev/null 2>&1; then
  chown -R agent:agent "$VENV_DIR"
elif [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "${SUDO_UID}:${SUDO_GID}" "$VENV_DIR"
fi

command -v python3 >/dev/null
command -v node >/dev/null
command -v npm >/dev/null

node_ver="$(node --version 2>/dev/null || true)"
npm_ver="$(npm --version 2>/dev/null || true)"
rscript_ver="$(Rscript --version 2>&1 | head -1 || echo missing)"
echo "[container_setup] OK FSE-2025-010 Python=$("${VENV_DIR}/bin/python" --version 2>&1) node=${node_ver} npm=${npm_ver} R=${rscript_ver}"
