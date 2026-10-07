#!/usr/bin/env bash
# Reproducible Java/Maven toolchain for FSE-2025-009 (Gleipner gadget-chain benchmark).
# Invoked as root once per TaskSandbox container start.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
VENV_DIR="/opt/fse-2025-009-venv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ_FILE="${SCRIPT_DIR}/requirements.txt"
if [[ ! -f "$REQ_FILE" && -f /task/seeds/requirements.txt ]]; then
  REQ_FILE="/task/seeds/requirements.txt"
fi

JAVA11_HOME="/usr/lib/jvm/java-11-openjdk-amd64"
JAVA8_HOME="/usr/lib/jvm/java-8-openjdk-amd64"
JAVA17_HOME="/usr/lib/jvm/java-17-openjdk-amd64"

apt_retry() {
  local attempt
  for attempt in 1 2 3; do
    if apt-get update -qq \
      && apt-get install -y -qq --no-install-recommends --fix-missing \
        build-essential \
        g++ \
        git \
        curl \
        wget \
        ca-certificates \
        make \
        maven \
        openjdk-8-jdk-headless \
        openjdk-11-jdk-headless \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        pkg-config; then
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
for bin in java javac mvn make g++ python3; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    need_apt=1
    break
  fi
done
if [[ ! -d "$JAVA8_HOME" ]]; then
  need_apt=1
fi
if [[ ! -d "$JAVA11_HOME" ]]; then
  need_apt=1
fi
if ! python3 -m venv --help >/dev/null 2>&1; then
  need_apt=1
fi
if [[ "$need_apt" -eq 1 ]]; then
  apt_retry
fi

# Prefer JDK 11 for Gleipner builds and most static-analysis tools.
if [[ -d "$JAVA11_HOME" ]]; then
  export JAVA_HOME="$JAVA11_HOME"
  export PATH="$JAVA_HOME/bin:$PATH"
elif [[ -d "$JAVA17_HOME" ]]; then
  export JAVA_HOME="$JAVA17_HOME"
  export PATH="$JAVA_HOME/bin:$PATH"
fi

python3 -m venv "$VENV_DIR"
if [[ -f "$REQ_FILE" ]]; then
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    -r "$REQ_FILE"
else
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    numpy \
    pandas \
    matplotlib \
    pyyaml \
    tqdm
fi

if id agent >/dev/null 2>&1; then
  chown -R agent:agent "$VENV_DIR"
elif [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "${SUDO_UID}:${SUDO_GID}" "$VENV_DIR"
fi

# JNI category expects custom.so under /tmp (see Gleipner Makefile).
GLEIPNER_ROOT=""
for candidate in \
  "${GLEIPNER_HOME:-}" \
  /workplace/dataset_candidate/gleipner \
  /shared/gleipner \
  /task/dataset_candidate/gleipner; do
  if [[ -n "$candidate" && -d "$candidate" ]]; then
    GLEIPNER_ROOT="$candidate"
    break
  fi
done
if [[ -n "$GLEIPNER_ROOT" && -f "$GLEIPNER_ROOT/chains/src/main/resources/custom.so" ]]; then
  cp -f "$GLEIPNER_ROOT/chains/src/main/resources/custom.so" /tmp/custom.so
  chmod a+r /tmp/custom.so || true
fi

command -v java >/dev/null
command -v javac >/dev/null
command -v mvn >/dev/null
command -v python3 >/dev/null

java_ver="$(java -version 2>&1 | head -1 || true)"
mvn_ver="$(mvn -version 2>/dev/null | head -1 || true)"
java8_ok="missing"
if [[ -x "$JAVA8_HOME/bin/java" ]]; then
  java8_ok="$("$JAVA8_HOME/bin/java" -version 2>&1 | head -1 || true)"
fi

echo "[container_setup] OK FSE-2025-009 Python=$("${VENV_DIR}/bin/python" --version 2>&1) JAVA_HOME=${JAVA_HOME:-unset} java=${java_ver} java8=${java8_ok} mvn=${mvn_ver}"
