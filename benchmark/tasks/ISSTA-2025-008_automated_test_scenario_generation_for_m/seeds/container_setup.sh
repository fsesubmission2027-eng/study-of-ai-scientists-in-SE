#!/usr/bin/env bash
# Toolchain for ISSTA-2025-008 (COLREGS multi-vessel ASV scene generation).
# Invoked as root once per TaskSandbox container start.
# Artifact is mounted read-only; installs pymoo / Scenic / Shapely stack for SB+RS.
# High-fidelity maritime simulators (MOOS-IvP / ArduPilot SITL) are NOT installed here.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
VENV_DIR="/opt/issta-2025-008-venv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ_FILE="${SCRIPT_DIR}/requirements.txt"
if [[ ! -f "$REQ_FILE" && -f /task/seeds/requirements.txt ]]; then
  REQ_FILE="/task/seeds/requirements.txt"
fi

ART_HOME="${ASVTESTSCENEGENERATION_HOME:-}"
if [[ -z "$ART_HOME" || ! -d "$ART_HOME" ]]; then
  if [[ -d /workplace/dataset_candidate/asvtestscenegeneration-issta2025 ]]; then
    ART_HOME="/workplace/dataset_candidate/asvtestscenegeneration-issta2025"
  elif [[ -d /shared/asvtestscenegeneration-issta2025 ]]; then
    ART_HOME="/shared/asvtestscenegeneration-issta2025"
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
        libgeos-dev \
        libxml2-dev \
        libxslt1-dev \
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
for bin in gcc g++ git python3; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    need_apt=1
    break
  fi
done
if ! python3 -m venv --help >/dev/null 2>&1; then
  need_apt=1
fi
# Shapely wheels usually bundle GEOS; install headers if missing for source builds.
if ! ldconfig -p 2>/dev/null | grep -q libgeos; then
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
    "numpy>=1.26" "scipy>=1.11" "pandas>=2.0" "matplotlib>=3.7" seaborn \
    "pymoo>=0.6" "pygad>=3.3" "Shapely>=2.0" lxml PyYAML jsonpickle \
    "commonroad-io>=2023.1" scenic tqdm
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
for mod in ("scipy", "pandas", "pymoo", "pygad", "shapely", "matplotlib", "scenic", "lxml"):
    print(mod, "ok" if ok(mod) else "MISSING")
PY

if id agent >/dev/null 2>&1; then
  chown -R agent:agent "$VENV_DIR" || true
elif [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "${SUDO_UID}:${SUDO_GID}" "$VENV_DIR" || true
fi

have_co=0
have_func=0
have_src=0
have_scenic=0
have_eval=0
co_xml=0
[[ -n "${ART_HOME:-}" && -d "${ART_HOME}/assets/common_ocean_scenarios" ]] && have_co=1
[[ -n "${ART_HOME:-}" && -d "${ART_HOME}/assets/functional_models" ]] && have_func=1
[[ -n "${ART_HOME:-}" && -d "${ART_HOME}/src" ]] && have_src=1
[[ -n "${ART_HOME:-}" && -d "${ART_HOME}/assets/scenic" ]] && have_scenic=1
[[ -n "${ART_HOME:-}" && -f "${ART_HOME}/src/scripts/evaluation_main.py" ]] && have_eval=1
if [[ "$have_co" -eq 1 ]]; then
  co_xml="$(find "${ART_HOME}/assets/common_ocean_scenarios" -type f -name '*.xml' 2>/dev/null | wc -l | tr -d ' ')"
fi

command -v python3 >/dev/null
echo "[container_setup] OK ISSTA-2025-008 Python=$("${VENV_DIR}/bin/python" --version 2>&1)"
echo "[container_setup] NOTE: artifact at /shared/asvtestscenegeneration-issta2025;"
echo "[container_setup]       agent path: dataset_candidate/asvtestscenegeneration-issta2025/"
echo "[container_setup] NOTE: commonocean=${have_co} xml=${co_xml} functional=${have_func} src=${have_src} scenic_assets=${have_scenic} evaluation_main=${have_eval}"
echo "[container_setup] NOTE: PYTHONPATH should include artifact src/ for SB/RS scripts."
echo "[container_setup] NOTE: MOOS-IvP / ArduPilot SITL not preinstalled; add under project/ if needed."
