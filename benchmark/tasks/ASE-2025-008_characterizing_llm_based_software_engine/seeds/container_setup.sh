#!/usr/bin/env bash
# Reproducible Python analysis environment for ASE-2025-008.
# Invoked as root once per TaskSandbox container start.
set -euo pipefail

VENV_DIR="/opt/ase-2025-008-venv"

python3 -m venv "$VENV_DIR"
"${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
  "matplotlib>=3.6" \
  "matplotlib-venn>=0.11.9" \
  "numpy>=1.23" \
  "pandas>=1.5"

"${VENV_DIR}/bin/python" -c \
  "import matplotlib, matplotlib_venn, numpy, pandas"

# Agent runs unprivileged and must be able to pip-install extra packages into this venv.
if id agent >/dev/null 2>&1; then
  chown -R agent:agent "$VENV_DIR"
elif [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "${SUDO_UID}:${SUDO_GID}" "$VENV_DIR"
fi

echo "[container_setup] OK ASE-2025-008 Python=$("${VENV_DIR}/bin/python" --version 2>&1)"
