#!/usr/bin/env bash
# Toolchain for ICSE-2025-008 (TeaStore/TrainTicket performance regression early detection).
# Invoked as root once per TaskSandbox container start.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
VENV_DIR="/opt/icse-2025-008-venv"
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
        git \
        curl \
        wget \
        ca-certificates \
        unzip \
        zip \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        openjdk-17-jdk \
        maven \
        time \
        bc \
        procps \
        docker.io \
        docker-compose-v2 \
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
for bin in java javac mvn python3 git curl; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    need_apt=1
    break
  fi
done
if ! python3 -m venv --help >/dev/null 2>&1; then
  need_apt=1
fi
# Prefer docker CLI if present; install via apt when missing.
if ! command -v docker >/dev/null 2>&1; then
  need_apt=1
fi
if [[ "$need_apt" -eq 1 ]]; then
  apt_retry
fi

python3 -m venv "$VENV_DIR"
if [[ -f "$REQ_FILE" ]]; then
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    -r "$REQ_FILE"
else
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    numpy pandas matplotlib scipy pyyaml tqdm statsmodels
fi

if id agent >/dev/null 2>&1; then
  chown -R agent:agent "$VENV_DIR"
elif [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "${SUDO_UID}:${SUDO_GID}" "$VENV_DIR"
fi

command -v java >/dev/null
command -v javac >/dev/null
command -v python3 >/dev/null

if [[ -z "${JAVA_HOME:-}" ]]; then
  for candidate in /usr/lib/jvm/java-17-openjdk-* /usr/lib/jvm/java-17-openjdk; do
    if [[ -d "$candidate" ]]; then
      export JAVA_HOME="$candidate"
      break
    fi
  done
fi

java_ver="$(java -version 2>&1 | head -1 || true)"
mvn_ver="$(mvn -version 2>/dev/null | head -1 || true)"
docker_ver="$(docker --version 2>/dev/null || echo 'docker-cli-missing')"
compose_ver="$(docker compose version 2>/dev/null || docker-compose --version 2>/dev/null || echo 'compose-missing')"

echo "[container_setup] OK ICSE-2025-008 Python=$("${VENV_DIR}/bin/python" --version 2>&1)"
echo "[container_setup] java=${java_ver} | mvn=${mvn_ver} | JAVA_HOME=${JAVA_HOME:-unset}"
echo "[container_setup] ${docker_ver} | ${compose_ver}"
echo "[container_setup] NOTE: subjects mounted read-only at /shared/perf-regression-early-detect;"
echo "[container_setup]       copy TeaStore/TrainTicket under project/ before edits."
echo "[container_setup] NOTE: paper used Podman+Compose; Docker CLI is the sandbox equivalent."
echo "[container_setup]       Nested daemon access depends on host docker.sock (ResearchClaw mounts it;"
echo "[container_setup]       AI-Scientist/AI-Researcher may only do component-level work without sock)."
