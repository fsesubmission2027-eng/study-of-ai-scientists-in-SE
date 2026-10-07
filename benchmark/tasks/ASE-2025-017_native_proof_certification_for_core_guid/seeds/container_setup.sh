#!/usr/bin/env bash
# C++ toolchain + EvalMaxSAT + Python analysis env for ASE-2025-017 (MaxSAT proof logging).
# Invoked as root once per TaskSandbox container start.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
VENV_DIR="/opt/ase-2025-017-venv"
TOOLS_DIR="/opt/ase-2025-017-tools"
EVAL_DIR="${TOOLS_DIR}/EvalMaxSAT"
EVAL_REPO="https://github.com/FlorentAvellaneda/EvalMaxSAT.git"
EVAL_COMMIT="94e677456cab96b2718f6da3f808bf694ac383d6"
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
        cmake \
        git \
        ca-certificates \
        wget \
        unzip \
        xz-utils \
        zlib1g-dev \
        python3-venv \
        python3-dev; then
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
for bin in g++ cmake git wget unzip xz; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    need_apt=1
    break
  fi
done
if ! python3 -m venv --help >/dev/null 2>&1; then
  need_apt=1
fi
# Glucose (EvalMaxSAT SAT backend) includes <zlib.h>; skip-apt when the
# compiler already exists would otherwise leave this header missing.
if [[ ! -f /usr/include/zlib.h ]]; then
  need_apt=1
fi
if [[ "$need_apt" -eq 1 ]]; then
  apt_retry
fi

BIN_DIR="${TOOLS_DIR}/bin"
mkdir -p "$TOOLS_DIR" "$BIN_DIR"
EVAL_BIN="${BIN_DIR}/EvalMaxSAT_bin"
if [[ ! -x "$EVAL_BIN" ]]; then
  rm -rf "$EVAL_DIR"
  git clone --recurse-submodules --depth 1 "$EVAL_REPO" "$EVAL_DIR" || \
    git clone --recurse-submodules "$EVAL_REPO" "$EVAL_DIR"
  git -C "$EVAL_DIR" fetch --depth 1 origin "$EVAL_COMMIT" 2>/dev/null || true
  git -C "$EVAL_DIR" checkout --detach "$EVAL_COMMIT" 2>/dev/null \
    || git -C "$EVAL_DIR" checkout --detach "$(git -C "$EVAL_DIR" rev-parse HEAD)"
  git -C "$EVAL_DIR" submodule update --init --recursive || true
  mkdir -p "${EVAL_DIR}/build"
  # Cadical can compile without its autotools build.hpp when NBUILD is set.
  cmake -S "$EVAL_DIR" -B "${EVAL_DIR}/build" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CXX_FLAGS="-DNBUILD"
  cmake --build "${EVAL_DIR}/build" -j"$(nproc)"
  built=""
  while IFS= read -r -d '' candidate; do
    if [[ -x "$candidate" ]]; then
      built="$candidate"
      break
    fi
  done < <(find "${EVAL_DIR}/build" -type f -name EvalMaxSAT_bin -print0 2>/dev/null)
  if [[ -z "$built" ]]; then
    echo "[container_setup] EvalMaxSAT build finished but EvalMaxSAT_bin was not found under ${EVAL_DIR}/build" >&2
    find "${EVAL_DIR}/build" -maxdepth 3 -type f >&2 || true
    exit 1
  fi
  install -m 0755 "$built" "$EVAL_BIN"
  ln -sfn "$EVAL_BIN" "${EVAL_DIR}/build/EvalMaxSAT_bin"
fi

python3 -m venv "$VENV_DIR"
if [[ -f "$REQ_FILE" ]]; then
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    -r "$REQ_FILE"
else
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    "GitPython==3.1.44" \
    "matplotlib==3.10.3" \
    "numpy==2.2.6" \
    "pandas==2.2.3" \
    "scikit-learn==1.6.1" \
    "seaborn==0.13.2" \
    "tqdm==4.66.5"
fi

"${VENV_DIR}/bin/python" - <<'PY'
import numpy
import pandas
import sklearn
print("numpy", numpy.__version__, "pandas", pandas.__version__, "sklearn", sklearn.__version__)
PY

if id agent >/dev/null 2>&1; then
  chown -R agent:agent "$VENV_DIR" "$TOOLS_DIR"
elif [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "${SUDO_UID}:${SUDO_GID}" "$VENV_DIR" "$TOOLS_DIR"
fi

command -v g++ >/dev/null
command -v cmake >/dev/null
if [[ ! -x "$EVAL_BIN" ]]; then
  echo "[container_setup] missing EvalMaxSAT binary at ${EVAL_BIN}" >&2
  exit 1
fi
echo "[container_setup] OK ASE-2025-017 g++=$(g++ --version | head -1) EvalMaxSAT=${EVAL_BIN} Python=$("${VENV_DIR}/bin/python" --version 2>&1)"
