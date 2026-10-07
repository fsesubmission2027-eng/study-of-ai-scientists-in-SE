#!/bin/bash
# ResearchClaw experiment entrypoint — unified three-phase execution.
# Vendored from AutoResearchClaw/researchclaw/docker/entrypoint.sh for benchmark lite image.
set -e

WORKSPACE="/workspace"
ENTRY_POINT="${RC_ENTRY_POINT:-${1:-main.py}}"
if [ "$#" -gt 0 ]; then
    shift
fi

if [ -f "$WORKSPACE/requirements.txt" ]; then
    echo "[RC] Phase 0: Installing packages from requirements.txt..."
    pip install --no-cache-dir --break-system-packages \
        -r "$WORKSPACE/requirements.txt" 2>&1 | tail -20
    echo "[RC] Phase 0: Package installation complete."
fi

if [ -f "$WORKSPACE/setup.py" ]; then
    echo "[RC] Phase 1: Running setup.py (dataset download/preparation)..."
    python3 -u "$WORKSPACE/setup.py"
    echo "[RC] Phase 1: Setup complete."
fi

if [ "${RC_SETUP_ONLY_NETWORK:-0}" = "1" ]; then
    echo "[RC] Disabling network for experiment phase..."
    if iptables -A OUTPUT -j DROP 2>/dev/null; then
        echo "[RC] Network disabled via iptables."
    elif ip route del default 2>/dev/null; then
        echo "[RC] Network disabled via route removal."
    else
        echo "[RC] Warning: Could not disable network. Continuing with network."
    fi
fi

echo "[RC] Phase 2: Running experiment ($ENTRY_POINT)..."
exec python3 -u "$WORKSPACE/$ENTRY_POINT" "$@"
