#!/usr/bin/env bash
# Toolchain for ICSE-2025-005 (EvoSuite + SF110 / class observability).
# Invoked as root once per TaskSandbox container start.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
VENV_DIR="/opt/icse-2025-005-venv"
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
        ant \
        time \
        bc \
        procps; then
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
for bin in java javac mvn python3 unzip; do
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
if [[ -f "$REQ_FILE" ]]; then
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    -r "$REQ_FILE"
else
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    numpy pandas matplotlib scipy pyyaml tqdm
fi

if id agent >/dev/null 2>&1; then
  chown -R agent:agent "$VENV_DIR"
elif [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "${SUDO_UID}:${SUDO_GID}" "$VENV_DIR"
fi

command -v java >/dev/null
command -v javac >/dev/null
command -v python3 >/dev/null

# Prefer JAVA_HOME from Debian OpenJDK package layout
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
echo "[container_setup] OK ICSE-2025-005 Python=$("${VENV_DIR}/bin/python" --version 2>&1)"
echo "[container_setup] java=${java_ver} | mvn=${mvn_ver} | JAVA_HOME=${JAVA_HOME:-unset}"
echo "[container_setup] NOTE: SF110 mounted read-only at /shared/sf110-evosuite; copy classes before instrumentation."
