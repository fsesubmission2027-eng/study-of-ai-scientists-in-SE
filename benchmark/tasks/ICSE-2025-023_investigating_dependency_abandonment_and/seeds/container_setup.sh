#!/usr/bin/env bash
# Toolchain for ICSE-2025-023 (npm dependency abandonment / survival + logistic models).
# Invoked as root once per TaskSandbox container start.
# Zenodo AE is mounted read-only; installs R (paper Rmd) + Python analysis deps.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
VENV_DIR="/opt/icse-2025-023-venv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ_FILE="${SCRIPT_DIR}/requirements.txt"
if [[ ! -f "$REQ_FILE" && -f /task/seeds/requirements.txt ]]; then
  REQ_FILE="/task/seeds/requirements.txt"
fi

ART_HOME="${NPM_ABANDONMENT_HOME:-}"
if [[ -z "$ART_HOME" || ! -d "$ART_HOME" ]]; then
  if [[ -d /workplace/dataset_candidate/npm-dependency-abandonment-icse2025 ]]; then
    ART_HOME="/workplace/dataset_candidate/npm-dependency-abandonment-icse2025"
  elif [[ -d /shared/npm-dependency-abandonment-icse2025 ]]; then
    ART_HOME="/shared/npm-dependency-abandonment-icse2025"
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
        libcurl4-openssl-dev \
        libssl-dev \
        libxml2-dev \
        libfontconfig1-dev \
        libharfbuzz-dev \
        libfribidi-dev \
        libfreetype6-dev \
        libpng-dev \
        libtiff5-dev \
        libjpeg-dev \
        r-base \
        r-base-dev \
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
for bin in gcc g++ git python3 R; do
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

# Paper replication libraries (explorationAndModeling.Rmd)
Rscript -e 'pkgs <- c("readr","dplyr","ggplot2","lubridate","survival","survminer","car","pscl","polycor","psych","ltm","tidyverse","broom","gtools"); missing <- pkgs[!pkgs %in% rownames(installed.packages())]; if (length(missing)) install.packages(missing, repos="https://cloud.r-project.org", Ncpus=max(1L, parallel::detectCores()-1L)); cat(paste(pkgs, sapply(pkgs, requireNamespace, quietly=TRUE), sep="=", collapse="\n"), "\n")'

python3 -m venv "$VENV_DIR"
"${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
  -U pip setuptools wheel

if [[ -f "$REQ_FILE" ]]; then
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    -r "$REQ_FILE"
else
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    pandas numpy scipy statsmodels matplotlib seaborn lifelines scikit-learn PyYAML tqdm
fi

"${VENV_DIR}/bin/python" - <<'PY'
import importlib.util
mods = ["numpy", "pandas", "scipy", "matplotlib", "seaborn", "statsmodels", "lifelines", "sklearn", "yaml"]
for mod in mods:
    check = "yaml" if mod == "yaml" else mod
    print(check, "ok" if importlib.util.find_spec(check) else "MISSING")
PY

if id agent >/dev/null 2>&1; then
  chown -R agent:agent "$VENV_DIR" || true
elif [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "${SUDO_UID}:${SUDO_GID}" "$VENV_DIR" || true
fi

n_csv=0
if [[ -n "${ART_HOME:-}" && -d "${ART_HOME}/data" ]]; then
  n_csv="$(find "${ART_HOME}/data" -maxdepth 1 -type f -name '*.csv' | wc -l | tr -d ' ')"
fi

command -v python3 >/dev/null
command -v R >/dev/null
echo "[container_setup] OK ICSE-2025-023 Python=$("${VENV_DIR}/bin/python" --version 2>&1) R=$(R --version | head -1)"
echo "[container_setup] NOTE: artifact mounted at /shared/npm-dependency-abandonment-icse2025;"
echo "[container_setup]       agent path: dataset_candidate/npm-dependency-abandonment-icse2025/"
echo "[container_setup] NOTE: csv files under data/: ${n_csv}"
echo "[container_setup] NOTE: primary path = re-run explorationAndModeling.Rmd (or Python reanalysis of data/)."
echo "[container_setup] NOTE: full WoC/npm remine is out of sandbox scope; use mounted AE CSVs."
