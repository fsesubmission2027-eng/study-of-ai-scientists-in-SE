#!/usr/bin/env bash
# System toolchain for FSE-2025-006 (Unconfirmed Statistical Assumptions in Notebooks).
# Invoked as root once per container start by TaskSandbox / hooks.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

need_apt=0
for bin in python3 pip3 R; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    need_apt=1
    break
  fi
done

if [[ "$need_apt" -eq 1 ]]; then
  attempt=1
  max_attempts=3
  while true; do
    if apt-get update -qq \
      && apt-get install -y -qq --fix-missing \
        build-essential \
        git \
        curl \
        wget \
        python3 \
        python3-pip \
        python3-dev \
        python3-venv \
        python3-numpy \
        python3-scipy \
        python3-pandas \
        python3-matplotlib \
        python3-seaborn \
        python3-yaml \
        python3-requests \
        python3-nbformat \
        python3-nbconvert \
        jupyter-nbconvert \
        r-base \
        r-base-dev \
        libssl-dev \
        libcurl4-openssl-dev \
        libxml2-dev \
        libfontconfig1-dev \
        pandoc \
        apt-utils; then
      break
    fi
    if [[ "$attempt" -ge "$max_attempts" ]]; then
      echo "[container_setup] apt install failed after ${max_attempts} attempts" >&2
      exit 1
    fi
    echo "[container_setup] apt attempt ${attempt}/${max_attempts} failed; retrying..." >&2
    attempt=$((attempt + 1))
    sleep $((attempt * 5))
  done
fi

# Prefer apt packages; fill gaps with pip (break-system-packages for PEP 668 images).
pip_install() {
  if pip3 install --quiet --no-cache-dir --break-system-packages "$@" 2>/tmp/fse006_pip.err; then
    return 0
  fi
  if pip3 install --quiet --no-cache-dir "$@" 2>>/tmp/fse006_pip.err; then
    return 0
  fi
  echo "[container_setup] WARN: pip install failed for: $*" >&2
  sed -n '1,20p' /tmp/fse006_pip.err >&2 || true
  return 1
}

# Always ensure notebook/kaggle stack via pip (apt names vary by distro).
pip_install \
  numpy \
  scipy \
  pandas \
  statsmodels \
  matplotlib \
  seaborn \
  jupyter \
  nbformat \
  nbclient \
  nbconvert \
  ipykernel \
  kaggle \
  requests \
  tqdm \
  pyyaml \
  || true

# Soft-fail rpy2 (heavy / often broken); not required for core eval.
pip_install rpy2 || echo "[container_setup] WARN: rpy2 skipped"

# R packages used by stats notebooks / assumption checks
Rscript -e 'pkgs <- c("jsonlite","rmarkdown","knitr","testthat");
  for (p in pkgs) if (!requireNamespace(p, quietly=TRUE))
    install.packages(p, repos="https://cloud.r-project.org", quiet=TRUE)' 2>/dev/null \
  || echo "[container_setup] WARN: some R packages failed to install"

# Wire Kaggle credentials (env token preferred; file mount as fallback)
mkdir -p "${HOME}/.kaggle" /root/.kaggle /home/agent/.kaggle 2>/dev/null || true
if [[ -n "${KAGGLE_API_TOKEN:-}" ]]; then
  for dest in "${HOME}/.kaggle/access_token" /root/.kaggle/access_token /home/agent/.kaggle/access_token; do
    printf '%s' "$KAGGLE_API_TOKEN" > "$dest" 2>/dev/null || true
    chmod 600 "$dest" 2>/dev/null || true
  done
  echo "[container_setup] Kaggle API token loaded from KAGGLE_API_TOKEN env"
elif [[ -f /shared/kaggle/access_token ]]; then
  for dest in "${HOME}/.kaggle/access_token" /root/.kaggle/access_token /home/agent/.kaggle/access_token; do
    cp -f /shared/kaggle/access_token "$dest" 2>/dev/null || true
    chmod 600 "$dest" 2>/dev/null || true
  done
  export KAGGLE_API_TOKEN="$(cat /shared/kaggle/access_token)"
  echo "[container_setup] Kaggle access_token copied from /shared/kaggle"
elif [[ -f /shared/kaggle/kaggle.json ]]; then
  for dest in "${HOME}/.kaggle/kaggle.json" /root/.kaggle/kaggle.json /home/agent/.kaggle/kaggle.json; do
    cp -f /shared/kaggle/kaggle.json "$dest" 2>/dev/null || true
    chmod 600 "$dest" 2>/dev/null || true
  done
  echo "[container_setup] Legacy Kaggle kaggle.json found at /shared/kaggle/kaggle.json"
else
  # Non-fatal: agent can still use host-injected env later; do not fail preflight.
  echo "[container_setup] WARN: no Kaggle credentials yet (KAGGLE_API_TOKEN / /shared/kaggle/access_token)"
fi
export KAGGLE_CONFIG_DIR="${KAGGLE_CONFIG_DIR:-${HOME}/.kaggle}"

command -v python3 >/dev/null
command -v pip3 >/dev/null

# Hard requirement: core Python scientific + notebook modules
if ! python3 -c "import numpy, scipy, pandas, nbformat; print('py-ok')" 2>/tmp/fse006_pycheck.err; then
  echo "[container_setup] ERROR: required Python modules missing; retrying pip..." >&2
  cat /tmp/fse006_pycheck.err >&2 || true
  pip_install numpy scipy pandas nbformat nbclient nbconvert kaggle
  python3 -c "import numpy, scipy, pandas, nbformat; print('py-ok')"
fi

command -v kaggle >/dev/null 2>&1 && kaggle --version || echo "[container_setup] WARN: kaggle CLI missing"
command -v R >/dev/null && R --version | head -1 || echo "[container_setup] WARN: R missing"

echo "[container_setup] OK FSE-2025-006 python/R/jupyter/kaggle toolchain ready"
