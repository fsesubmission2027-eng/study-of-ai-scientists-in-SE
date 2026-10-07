#!/usr/bin/env bash
# Reproducible Python + C toolchain for ASE-2025-013 (HFDecomposer / header decomposition).
# Invoked as root once per TaskSandbox container start.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
VENV_DIR="/opt/ase-2025-013-venv"
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
        clang \
        git \
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
for bin in clang gcc git; do
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

# algorithmic.sty used by many paper drafts.
if ! kpsewhich algorithmic.sty >/dev/null 2>&1; then
  apt-get update -qq
  apt-get install -y -qq --no-install-recommends --fix-missing \
    texlive-science || true
fi

python3 -m venv "$VENV_DIR"

if [[ -f "$REQ_FILE" ]]; then
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    -r "$REQ_FILE"
else
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    "GitPython==3.1.44" \
    "httpx==0.28.1" \
    "matplotlib==3.10.3" \
    "networkx==3.2.1" \
    "nltk==3.9.1" \
    "numpy==2.2.6" \
    "openai==1.79.0" \
    "pandas==2.2.3" \
    "scikit-learn==1.6.1" \
    "seaborn==0.13.2" \
    "tqdm==4.66.5" \
    "tree-sitter==0.24.0" \
    "tree-sitter-c==0.23.2"
fi

"${VENV_DIR}/bin/python" - <<'PY'
import networkx
import nltk
import numpy
import pandas
import sklearn
import tree_sitter_c
from git import Repo  # noqa: F401
print(
    "networkx", networkx.__version__,
    "pandas", pandas.__version__,
    "sklearn", sklearn.__version__,
)
for pkg in ("punkt", "punkt_tab"):
    try:
        nltk.data.find(f"tokenizers/{pkg}")
    except LookupError:
        nltk.download(pkg, quiet=True)
PY

if id agent >/dev/null 2>&1; then
  chown -R agent:agent "$VENV_DIR"
elif [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "${SUDO_UID}:${SUDO_GID}" "$VENV_DIR"
fi

command -v clang >/dev/null
command -v gcc >/dev/null
echo "[container_setup] OK ASE-2025-013 Python=$("${VENV_DIR}/bin/python" --version 2>&1) clang=$(clang --version 2>/dev/null | head -1)"
