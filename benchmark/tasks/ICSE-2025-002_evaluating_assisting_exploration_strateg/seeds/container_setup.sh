#!/usr/bin/env bash
# Reproducible toolchain for ICSE-2025-002 (CDFUZZ / grey-box fuzzing study).
# Invoked as root once per TaskSandbox container start.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
VENV_DIR="/opt/icse-2025-002-venv"
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
        autoconf \
        automake \
        libtool \
        flex \
        bison \
        zlib1g-dev \
        libpcap-dev \
        libglib2.0-dev \
        clang \
        llvm \
        afl++ \
        llvm-13 \
        clang-13 \
        lld-13 \
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
for bin in clang python3 make git; do
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

# Paper uses AFL llvm-mode with LLVM-13.
if [[ -d /usr/lib/llvm-13/bin ]]; then
  ln -sf /usr/lib/llvm-13/bin/llvm-config /usr/local/bin/llvm-config-13 2>/dev/null || true
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

# Best-effort compile CDFuzz from the mounted artifact (optional; agent may rebuild).
ARTIFACT="${FUZZING_EMPIRICAL_STUDY_HOME:-/shared/fuzzing-empirical-study}"
CDFUZZ_SRC="${ARTIFACT}/CDFuzz"
if [[ -d "$CDFUZZ_SRC" && ! -x "${CDFUZZ_SRC}/afl-fuzz" ]]; then
  echo "[container_setup] compiling CDFuzz from ${CDFUZZ_SRC} ..."
  (
    export PATH="/usr/lib/llvm-13/bin:${PATH}"
    export LLVM_CONFIG=llvm-config-13
    cd "$CDFUZZ_SRC"
    make clean >/dev/null 2>&1 || true
    make -j"$(nproc)" || echo "[container_setup] WARN: CDFuzz make failed; agent may rebuild" >&2
    if [[ -d llvm_mode ]]; then
      cd llvm_mode
      make clean >/dev/null 2>&1 || true
      make -j"$(nproc)" || echo "[container_setup] WARN: CDFuzz llvm_mode make failed" >&2
    fi
  ) || true
fi

clang_ver="$(clang --version 2>/dev/null | head -1 || true)"
afl_ver="$(afl-fuzz -h 2>&1 | head -1 || true)"
llvm13_ver="$(/usr/lib/llvm-13/bin/clang --version 2>/dev/null | head -1 || echo 'llvm-13 missing')"
echo "[container_setup] OK ICSE-2025-002 Python=$("${VENV_DIR}/bin/python" --version 2>&1)"
echo "[container_setup] clang=${clang_ver} | llvm13=${llvm13_ver} | afl=${afl_ver}"
echo "[container_setup] NOTE: paper targets AFL llvm-mode (LLVM-13); use afl-clang-fast from CDFuzz or AFL++."
