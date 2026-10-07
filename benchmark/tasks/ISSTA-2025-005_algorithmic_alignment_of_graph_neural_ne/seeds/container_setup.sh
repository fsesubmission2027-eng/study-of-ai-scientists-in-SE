#!/usr/bin/env bash
# Toolchain for ISSTA-2025-005 (DFA-GNN / algorithmic alignment with DFA).
# Invoked as root once per TaskSandbox container start.
# Artifact is mounted read-only; installs JAX/Haiku Python stack.
# Full Bazel build of programl_edited is NOT performed here.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
VENV_DIR="/opt/issta-2025-005-venv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ_FILE="${SCRIPT_DIR}/requirements.txt"
if [[ ! -f "$REQ_FILE" && -f /task/seeds/requirements.txt ]]; then
  REQ_FILE="/task/seeds/requirements.txt"
fi

ART_HOME="${DFAGNNS_HOME:-}"
if [[ -z "$ART_HOME" || ! -d "$ART_HOME" ]]; then
  if [[ -d /workplace/dataset_candidate/dfagnns-issta2025 ]]; then
    ART_HOME="/workplace/dataset_candidate/dfagnns-issta2025"
  elif [[ -d /shared/dfagnns-issta2025 ]]; then
    ART_HOME="/shared/dfagnns-issta2025"
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
        bzip2 \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        pkg-config \
        libopenblas-dev \
        protobuf-compiler \
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
for bin in gcc g++ git python3 bzip2; do
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

# CPU JAX keeps container startup reliable without NVIDIA drivers.
# Agents with GPU can reinstall a CUDA jaxlib inside project/ if needed.
if [[ -f "$REQ_FILE" ]]; then
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    -r "$REQ_FILE"
else
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    "numpy>=1.26" "jax>=0.4.20" "jaxlib>=0.4.20" "dm-haiku>=0.0.11" \
    "optax>=0.1.7" "chex>=0.1.85" networkx matplotlib pandas tqdm PyYAML
fi

# Editable DFAGNNs (dm-clrs namespace) when the mount is present.
if [[ -n "${ART_HOME:-}" && -f "${ART_HOME}/DFAGNNs/setup.py" ]]; then
  DFAGNNS_EDITABLE="/opt/issta-2025-005-dfagnns"
  rm -rf "$DFAGNNS_EDITABLE"
  mkdir -p "$DFAGNNS_EDITABLE"
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --exclude '.git' --exclude '__pycache__' \
      "${ART_HOME}/DFAGNNs/" "$DFAGNNS_EDITABLE/"
  else
    cp -a "${ART_HOME}/DFAGNNs/." "$DFAGNNS_EDITABLE/"
  fi
  (
    cd "$DFAGNNS_EDITABLE"
    # Avoid pulling tensorflow/tfds from upstream install_requires during setup.
    "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
      --no-deps -e . || true
  )
  echo "[container_setup] Installed editable DFAGNNs -> $DFAGNNS_EDITABLE"
else
  echo "[container_setup] WARN: DFAGNNs setup.py not found under mount"
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
if ok("jax"):
    import jax
    print("jax", jax.__version__, "devices", jax.devices())
else:
    print("jax MISSING")
for mod in ("haiku", "optax", "chex", "networkx", "matplotlib"):
    print(mod, "ok" if ok(mod) else "MISSING")
print("clrs", "ok" if ok("clrs") else "MISSING")
PY

if id agent >/dev/null 2>&1; then
  chown -R agent:agent "$VENV_DIR" || true
  [[ -d /opt/issta-2025-005-dfagnns ]] && chown -R agent:agent /opt/issta-2025-005-dfagnns || true
elif [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "${SUDO_UID}:${SUDO_GID}" "$VENV_DIR" || true
  [[ -d /opt/issta-2025-005-dfagnns ]] && chown -R "${SUDO_UID}:${SUDO_GID}" /opt/issta-2025-005-dfagnns || true
fi

have_code=0
have_graphs=0
have_programl=0
have_stats=0
[[ -n "${ART_HOME:-}" && -d "${ART_HOME}/DFAGNNs" ]] && have_code=1
[[ -n "${ART_HOME:-}" && -d "${ART_HOME}/graphs" ]] && have_graphs=1
[[ -n "${ART_HOME:-}" && -d "${ART_HOME}/programl_edited" ]] && have_programl=1
[[ -n "${ART_HOME:-}" && -d "${ART_HOME}/statistics" ]] && have_stats=1

command -v python3 >/dev/null
echo "[container_setup] OK ISSTA-2025-005 Python=$("${VENV_DIR}/bin/python" --version 2>&1)"
echo "[container_setup] NOTE: artifact at /shared/dfagnns-issta2025;"
echo "[container_setup]       agent path: dataset_candidate/dfagnns-issta2025/"
echo "[container_setup] NOTE: code=${have_code} graphs=${have_graphs} programl_edited=${have_programl} stats=${have_stats}"
echo "[container_setup] NOTE: DFAGNNs expects graphs as <id>.ProgramGraph.pb under PROGRAML_GRAPHS_HOME."
echo "[container_setup] NOTE: labels/trajectories need programl.yzd_analyze (build programl_edited) or a classical DFA labeler."
echo "[container_setup] NOTE: CPU JAX preinstalled; reinstall CUDA jaxlib in project/ if GPU available."
