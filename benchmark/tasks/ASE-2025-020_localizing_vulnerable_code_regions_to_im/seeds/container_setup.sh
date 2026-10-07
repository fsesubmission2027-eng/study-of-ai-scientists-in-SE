#!/usr/bin/env bash
# Reproducible Python + CPU-torch env for ASE-2025-020 (LOSVER / PLM vulnerability detection).
# Invoked as root once per TaskSandbox container start.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
VENV_DIR="/opt/ase-2025-020-venv"
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
        git \
        ca-certificates \
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
if ! command -v git >/dev/null 2>&1; then
  need_apt=1
fi
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

# CPU torch keeps container startup reliable without requiring NVIDIA drivers.
# Agents that have GPU can still reinstall a CUDA build inside project/.
"${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
  --index-url https://download.pytorch.org/whl/cpu \
  "torch==2.4.0"

if [[ -f "$REQ_FILE" ]]; then
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    -r "$REQ_FILE"
else
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    "GitPython==3.1.44" \
    "huggingface_hub==0.24.7" \
    "matplotlib==3.10.3" \
    "numpy==2.2.6" \
    "pandas==2.2.3" \
    "scikit-learn==1.6.1" \
    "tqdm==4.66.5" \
    "transformers==4.44.2"
fi

"${VENV_DIR}/bin/python" - <<'PY'
import pandas
import sklearn
import torch
import transformers
print(
    "torch", torch.__version__,
    "transformers", transformers.__version__,
    "pandas", pandas.__version__,
    "sklearn", sklearn.__version__,
    "cuda", torch.cuda.is_available(),
)
PY

# The mounted FFmpeg/qemu clones are owned by the host user, which makes git
# refuse to read them ("dubious ownership") under a different container UID.
git config --system --add safe.directory '*' || true

if id agent >/dev/null 2>&1; then
  chown -R agent:agent "$VENV_DIR"
elif [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "${SUDO_UID}:${SUDO_GID}" "$VENV_DIR"
fi

echo "[container_setup] OK ASE-2025-020 Python=$("${VENV_DIR}/bin/python" --version 2>&1) torch=$("${VENV_DIR}/bin/python" -c 'import torch; print(torch.__version__)')"
