#!/usr/bin/env bash
# Reproducible Java 8 + Maven + AspectJ + Python analysis env for ASE-2025-016 (Valg).
# Invoked as root once per TaskSandbox container start.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
VENV_DIR="/opt/ase-2025-016-venv"
TOOLS_DIR="/opt/ase-2025-016-tools"
JAVA_HOME_TARGET="/usr/lib/jvm/java-8-openjdk"
MAVEN_VERSION="3.8.8"
ASPECTJ_VERSION="1.9.7"
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
        openjdk-8-jdk \
        wget \
        unzip \
        zip \
        git \
        ca-certificates \
        python3-venv \
        python3-dev \
        bc \
        parallel; then
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
if ! java -version 2>&1 | grep -q '1\.8'; then
  need_apt=1
fi
for bin in wget git unzip; do
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

# Normalize JAVA_HOME path like the official Valg Dockerfile.
if [[ ! -d "$JAVA_HOME_TARGET" ]]; then
  src="$(ls -d /usr/lib/jvm/java-8-openjdk* 2>/dev/null | head -1 || true)"
  if [[ -n "$src" && "$src" != "$JAVA_HOME_TARGET" ]]; then
    mv "$src" "$JAVA_HOME_TARGET"
  fi
fi
export JAVA_HOME="$JAVA_HOME_TARGET"
export PATH="${JAVA_HOME}/bin:${PATH}"

mkdir -p "$TOOLS_DIR"

# Maven 3.8.8 (matches Valg scripts/Dockerfile)
MAVEN_HOME="${TOOLS_DIR}/apache-maven"
if [[ ! -x "${MAVEN_HOME}/bin/mvn" ]]; then
  tmp="$(mktemp -d)"
  archive="apache-maven-${MAVEN_VERSION}-bin.tar.gz"
  url="https://archive.apache.org/dist/maven/maven-3/${MAVEN_VERSION}/binaries/${archive}"
  mirror="https://downloads.apache.org/maven/maven-3/${MAVEN_VERSION}/binaries/${archive}"
  if ! wget -q -O "${tmp}/${archive}" "$url"; then
    wget -q -O "${tmp}/${archive}" "$mirror"
  fi
  tar -xzf "${tmp}/${archive}" -C "$TOOLS_DIR"
  rm -rf "$MAVEN_HOME"
  mv "${TOOLS_DIR}/apache-maven-${MAVEN_VERSION}" "$MAVEN_HOME"
  rm -rf "$tmp"
fi
export M2_HOME="$MAVEN_HOME"
export MAVEN_HOME
export PATH="${MAVEN_HOME}/bin:${PATH}"

# AspectJ 1.9.7 (needed by JavaMOP / Valg instrumentation)
ASPECTJ_DIR="${TOOLS_DIR}/aspectj-${ASPECTJ_VERSION}"
if [[ ! -x "${ASPECTJ_DIR}/bin/ajc" ]]; then
  tmp="$(mktemp -d)"
  jar="aspectj-${ASPECTJ_VERSION}.jar"
  wget -q -O "${tmp}/${jar}" \
    "https://github.com/eclipse-aspectj/aspectj/releases/download/V1_9_7/aspectj-${ASPECTJ_VERSION}.jar"
  mkdir -p "$ASPECTJ_DIR"
  "${JAVA_HOME}/bin/java" -jar "${tmp}/${jar}" -to "$ASPECTJ_DIR"
  # Raise ajc heap like the official Dockerfile (monitor weaving can be large).
  if [[ -f "${ASPECTJ_DIR}/bin/ajc" ]]; then
    sed -i 's/64M/10240M/g' "${ASPECTJ_DIR}/bin/ajc" || true
  fi
  rm -rf "$tmp"
fi
export ASPECTJ_HOME="$ASPECTJ_DIR"
export PATH="${ASPECTJ_DIR}/bin:${PATH}"
export CLASSPATH="${ASPECTJ_DIR}/lib/aspectjtools.jar:${ASPECTJ_DIR}/lib/aspectjrt.jar:${ASPECTJ_DIR}/lib/aspectjweaver.jar:${CLASSPATH:-}"

# Python analysis / Optuna tuning helpers
python3 -m venv "$VENV_DIR"
if [[ -f "$REQ_FILE" ]]; then
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    -r "$REQ_FILE"
else
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    "GitPython==3.1.44" \
    "httpx==0.28.1" \
    "matplotlib==3.10.3" \
    "numpy==2.2.6" \
    "openai==1.79.0" \
    "optuna==4.2.1" \
    "pandas==2.2.3" \
    "PyYAML==6.0.2" \
    "scikit-learn==1.6.1" \
    "seaborn==0.13.2" \
    "tqdm==4.66.5"
fi

"${VENV_DIR}/bin/python" - <<'PY'
import optuna
import pandas
import sklearn
from git import Repo  # noqa: F401
print("optuna", optuna.__version__, "pandas", pandas.__version__, "sklearn", sklearn.__version__)
PY

if id agent >/dev/null 2>&1; then
  chown -R agent:agent "$VENV_DIR" "$TOOLS_DIR"
elif [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "${SUDO_UID}:${SUDO_GID}" "$VENV_DIR" "$TOOLS_DIR"
fi

command -v java >/dev/null
command -v mvn >/dev/null
command -v ajc >/dev/null
java -version 2>&1 | head -1
mvn -version 2>&1 | head -1
echo "[container_setup] OK ASE-2025-016 JAVA_HOME=$JAVA_HOME MAVEN_HOME=$MAVEN_HOME ASPECTJ_HOME=$ASPECTJ_HOME Python=$("${VENV_DIR}/bin/python" --version 2>&1)"
