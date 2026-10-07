#!/usr/bin/env bash
# Toolchain for ISSTA-2025-009 (LLM4SZZ / bug-inducing commit identification).
# Invoked as root once per TaskSandbox container start.
# Artifact is mounted read-only; installs GitPython / tree-sitter / OpenAI client.
# Local Llama-3 weights, NeuralSZZ GPU training, and subject git clones are NOT installed.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
VENV_DIR="/opt/issta-2025-009-venv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ_FILE="${SCRIPT_DIR}/requirements.txt"
if [[ ! -f "$REQ_FILE" && -f /task/seeds/requirements.txt ]]; then
  REQ_FILE="/task/seeds/requirements.txt"
fi

ART_HOME="${LLM4SZZ_HOME:-}"
if [[ -z "$ART_HOME" || ! -d "$ART_HOME" ]]; then
  if [[ -d /workplace/dataset_candidate/llm4szz-issta2025/package ]]; then
    ART_HOME="/workplace/dataset_candidate/llm4szz-issta2025/package"
  elif [[ -d /shared/llm4szz-issta2025/package ]]; then
    ART_HOME="/shared/llm4szz-issta2025/package"
  elif [[ -d /shared/llm4szz-issta2025/replication/llmszz-replication-package1 ]]; then
    ART_HOME="/shared/llm4szz-issta2025/replication/llmszz-replication-package1"
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
for bin in gcc g++ git python3 unzip; do
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

if [[ -f "$REQ_FILE" ]]; then
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    -r "$REQ_FILE"
else
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    "numpy>=1.24" "pandas>=2.0" GitPython PyDriller "tree-sitter>=0.21" \
    "openai>=1.35" PyYAML tqdm requests matplotlib
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
for mod in ("pandas", "git", "pydriller", "tree_sitter", "openai", "yaml"):
    print(mod, "ok" if ok(mod) else "MISSING")
PY

if id agent >/dev/null 2>&1; then
  chown -R agent:agent "$VENV_DIR" || true
elif [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "${SUDO_UID}:${SUDO_GID}" "$VENV_DIR" || true
fi

have_linux=0
have_github=0
have_apache=0
have_code=0
have_logs=0
have_ts=0
[[ -n "${ART_HOME:-}" && -f "${ART_HOME}/dataset/DS_LINUX.json" ]] && have_linux=1
[[ -n "${ART_HOME:-}" && -f "${ART_HOME}/dataset/DS_GITHUB.json" ]] && have_github=1
[[ -n "${ART_HOME:-}" && -f "${ART_HOME}/dataset/DS_APACHE.json" ]] && have_apache=1
[[ -n "${ART_HOME:-}" && -f "${ART_HOME}/llm4szz.py" ]] && have_code=1
[[ -n "${ART_HOME:-}" && -d "${ART_HOME}/save_logs" ]] && have_logs=1
[[ -n "${ART_HOME:-}" && -f "${ART_HOME}/build/my-languages.so" ]] && have_ts=1

n_linux=0
n_github=0
n_apache=0
if [[ "$have_linux" -eq 1 ]]; then
  n_linux="$("${VENV_DIR}/bin/python" -c "import json; print(len(json.load(open('${ART_HOME}/dataset/DS_LINUX.json'))))")"
fi
if [[ "$have_github" -eq 1 ]]; then
  n_github="$("${VENV_DIR}/bin/python" -c "import json; print(len(json.load(open('${ART_HOME}/dataset/DS_GITHUB.json'))))")"
fi
if [[ "$have_apache" -eq 1 ]]; then
  n_apache="$("${VENV_DIR}/bin/python" -c "import json; print(len(json.load(open('${ART_HOME}/dataset/DS_APACHE.json'))))")"
fi

command -v python3 >/dev/null
echo "[container_setup] OK ISSTA-2025-009 Python=$("${VENV_DIR}/bin/python" --version 2>&1)"
echo "[container_setup] NOTE: artifact at /shared/llm4szz-issta2025;"
echo "[container_setup]       agent path: dataset_candidate/llm4szz-issta2025/"
echo "[container_setup] NOTE: linux=${have_linux}(n=${n_linux}) github=${have_github}(n=${n_github}) apache=${have_apache}(n=${n_apache}) code=${have_code} logs=${have_logs} tree_sitter_so=${have_ts}"
echo "[container_setup] NOTE: set API key in package llm.py / env for GPT-4o-mini path; Llama/NeuralSZZ GPU stacks not preinstalled."
echo "[container_setup] NOTE: subject repository clones must be obtained at runtime under project/ as needed."
