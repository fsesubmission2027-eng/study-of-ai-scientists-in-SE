#!/usr/bin/env bash
# Toolchain for ICSE-2025-004 (THANOS / DBMS differential testing).
# Invoked as root once per TaskSandbox container start.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
VENV_DIR="/opt/icse-2025-004-venv"
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
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        pkg-config \
        cmake \
        ninja-build \
        autoconf \
        automake \
        libtool \
        flex \
        bison \
        zlib1g-dev \
        libssl-dev \
        libncurses5-dev \
        libreadline-dev \
        libaio-dev \
        libevent-dev \
        liblz4-dev \
        libzstd-dev \
        libbz2-dev \
        libxml2-dev \
        libboost-all-dev \
        clang \
        llvm \
        afl++ \
        openjdk-17-jdk \
        gradle \
        unixodbc \
        unixodbc-dev \
        libmysqlclient-dev \
        default-libmysqlclient-dev \
        time \
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
for bin in clang python3 java make git bison flex; do
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
    numpy pandas matplotlib pyyaml tqdm
fi

if id agent >/dev/null 2>&1; then
  chown -R agent:agent "$VENV_DIR"
elif [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "${SUDO_UID}:${SUDO_GID}" "$VENV_DIR"
fi

command -v clang >/dev/null
command -v make >/dev/null
command -v python3 >/dev/null
command -v java >/dev/null
command -v bison >/dev/null
command -v flex >/dev/null

clang_ver="$(clang --version 2>/dev/null | head -1 || true)"
afl_ver="$(afl-fuzz -h 2>&1 | head -1 || true)"
java_ver="$(java -version 2>&1 | head -1 || true)"
echo "[container_setup] OK ICSE-2025-004 Python=$("${VENV_DIR}/bin/python" --version 2>&1)"
echo "[container_setup] clang=${clang_ver} | afl=${afl_ver} | java=${java_ver}"
echo "[container_setup] NOTE: compile MySQL/MariaDB/Percona with AFL++ (afl-clang-fast) for branch coverage."
