#!/usr/bin/env bash
# Toolchain for ICSE-2025-013 (Java-JNI cross-language static analysis / JNIFER-style).
# Invoked as root once per TaskSandbox container start.
# Datasets are mounted read-only; this script only installs analyzers' build deps.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
VENV_DIR="/opt/icse-2025-013-venv"
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
        gcc \
        g++ \
        make \
        cmake \
        ninja-build \
        git \
        curl \
        wget \
        ca-certificates \
        unzip \
        zip \
        tar \
        xz-utils \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        openjdk-17-jdk \
        maven \
        ant \
        time \
        bc \
        procps \
        jq \
        pkg-config \
        zlib1g-dev \
        libncurses-dev \
        libxml2-dev \
        flex \
        bison; then
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
for bin in java javac mvn gcc g++ cmake python3 unzip; do
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

# Optional OpenJDK 8 (subject era / some JNI builds). Ignore if unavailable.
if ! update-java-alternatives -l 2>/dev/null | grep -q 'java-1.8.0\|java-8'; then
  apt-get install -y -qq --no-install-recommends openjdk-8-jdk 2>/dev/null || \
    echo "[container_setup] WARN: openjdk-8-jdk not available; using JDK 17 for builds"
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
  chown -R agent:agent "$VENV_DIR" || true
elif [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "${SUDO_UID}:${SUDO_GID}" "$VENV_DIR" || true
fi

# Prefer JAVA_HOME from Debian OpenJDK 17
if [[ -d /usr/lib/jvm/java-17-openjdk-amd64 ]]; then
  echo "export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64" >/etc/profile.d/icse-2025-013-java.sh || true
  export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
elif [[ -d /usr/lib/jvm/java-17-openjdk-arm64 ]]; then
  echo "export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-arm64" >/etc/profile.d/icse-2025-013-java.sh || true
  export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-arm64
fi

command -v java >/dev/null
command -v javac >/dev/null
command -v mvn >/dev/null
command -v gcc >/dev/null
command -v cmake >/dev/null
command -v python3 >/dev/null

java_ver="$(java -version 2>&1 | head -1 || true)"
mvn_ver="$(mvn -version 2>/dev/null | head -1 || true)"
gcc_ver="$(gcc --version 2>/dev/null | head -1 || true)"
cmake_ver="$(cmake --version 2>/dev/null | head -1 || true)"

echo "[container_setup] OK ICSE-2025-013 Python=$("${VENV_DIR}/bin/python" --version 2>&1)"
echo "[container_setup] ${java_ver}"
echo "[container_setup] ${mvn_ver}"
echo "[container_setup] ${gcc_ver} | ${cmake_ver}"
echo "[container_setup] JAVA_HOME=${JAVA_HOME:-unset}"
echo "[container_setup] NOTE: subjects mounted read-only at /shared/jnifer-subjects;"
echo "[container_setup]       agent path: dataset_candidate/jnifer-subjects/"
echo "[container_setup] NOTE: copy subjects under project/ before edits / builds."
echo "[container_setup] NOTE: paper used 128GB RAM; sandbox MEMORY may be lower —"
echo "[container_setup]       use disclosed reduced subsets/timeouts when needed."
echo "[container_setup] NOTE: dynamic HotSpot ground truth is NOT in the dataset mount;"
echo "[container_setup]       reconstruct via instrumentation or report proxy metrics."
echo "[container_setup] NOTE: JNIFER/JN-Sum/Native-Scanner images not preloaded;"
echo "[container_setup]       implement or fetch tools separately if required."
