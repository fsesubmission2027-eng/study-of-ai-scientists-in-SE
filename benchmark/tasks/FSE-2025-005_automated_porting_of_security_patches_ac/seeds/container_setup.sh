#!/usr/bin/env bash
# System toolchain for FSE-2025-005 (Automated Porting of Security Patches).
# Invoked as root once per container start by hooks/patch_and_run.py.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

# Check if tools are already installed
need_install=0
for bin in git gcc python3 pip3; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    need_install=1
    break
  fi
done

if [[ "$need_install" -eq 1 ]]; then
  attempt=1
  max_attempts=3
  while true; do
    if apt-get update -qq \
      && apt-get install -y -qq --fix-missing \
        build-essential \
        gcc \
        g++ \
        clang \
        git \
        curl \
        wget \
        python3 \
        python3-pip \
        python3-dev \
        libssl-dev \
        libffi-dev \
        pkg-config \
        patch \
        diffutils \
        unidiff; then
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

# Install Python dependencies for CodeBLEU evaluation and data collection
pip3 install --quiet --no-cache-dir \
  requests \
  PyGithub \
  gitpython \
  transformers \
  nltk \
  sacrebleu \
  tree-sitter \
  tqdm \
  pandas \
  numpy \
  openai \
  anthropic 2>/dev/null || true

# Download NLTK data needed for BLEU evaluation
python3 -c "import nltk; nltk.download('punkt', quiet=True); nltk.download('punkt_tab', quiet=True)" 2>/dev/null || true

# Verify core tools
command -v gcc >/dev/null
command -v git >/dev/null
command -v python3 >/dev/null
command -v patch >/dev/null

gcc_ver="$(gcc --version 2>/dev/null | head -1 || true)"
git_ver="$(git --version 2>/dev/null || true)"
python_ver="$(python3 --version 2>/dev/null || true)"
echo "[container_setup] OK gcc=${gcc_ver} | git=${git_ver} | python=${python_ver} | patch=installed | CodeBLEU-deps=installed"
