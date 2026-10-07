#!/usr/bin/env bash
# Toolchain for ISSTA-2025-004 (Hulk / data-sensitive DBMS performance anomalies).
# Invoked as root once per TaskSandbox container start.
# Mounts open baselines (APOLLO / SQLancer / Squirrel); installs Java + Python clients.
# Full DBMS server builds (MySQL/MariaDB/...) are NOT installed here.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
VENV_DIR="/opt/issta-2025-004-venv"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ_FILE="${SCRIPT_DIR}/requirements.txt"
if [[ ! -f "$REQ_FILE" && -f /task/seeds/requirements.txt ]]; then
  REQ_FILE="/task/seeds/requirements.txt"
fi

ART_HOME="${HULK_ISSTA2025_BASELINES_HOME:-}"
if [[ -z "$ART_HOME" || ! -d "$ART_HOME" ]]; then
  if [[ -d /workplace/dataset_candidate/hulk-issta2025-baselines ]]; then
    ART_HOME="/workplace/dataset_candidate/hulk-issta2025-baselines"
  elif [[ -d /shared/hulk-issta2025-baselines ]]; then
    ART_HOME="/shared/hulk-issta2025-baselines"
  fi
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
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        pkg-config \
        cmake \
        openjdk-17-jdk \
        gradle \
        unixodbc \
        unixodbc-dev \
        libmysqlclient-dev \
        default-libmysqlclient-dev \
        libpq-dev \
        postgresql-client \
        default-mysql-client \
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
for bin in git python3 java; do
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
    -r "$REQ_FILE" || true
fi

"${VENV_DIR}/bin/python" - <<'PY'
import importlib.util

def ok(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False

for mod in ("numpy", "pandas", "matplotlib", "yaml", "psutil", "pymysql", "psycopg2"):
    print(mod, "ok" if ok(mod) else "MISSING")
PY

if id agent >/dev/null 2>&1; then
  chown -R agent:agent "$VENV_DIR" || true
elif [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "${SUDO_UID}:${SUDO_GID}" "$VENV_DIR" || true
fi

have_apollo=0
have_sqlancer=0
have_squirrel=0
[[ -n "${ART_HOME:-}" && -d "${ART_HOME}/apollo" ]] && have_apollo=1
[[ -n "${ART_HOME:-}" && -d "${ART_HOME}/sqlancer" ]] && have_sqlancer=1
[[ -n "${ART_HOME:-}" && -d "${ART_HOME}/squirrel" ]] && have_squirrel=1

command -v python3 >/dev/null
command -v java >/dev/null || true
echo "[container_setup] OK ISSTA-2025-004 Python=$("${VENV_DIR}/bin/python" --version 2>&1)"
echo "[container_setup] NOTE: baselines at /shared/hulk-issta2025-baselines;"
echo "[container_setup]       agent path: dataset_candidate/hulk-issta2025-baselines/"
echo "[container_setup] NOTE: apollo=${have_apollo} sqlancer=${have_sqlancer} squirrel=${have_squirrel}"
echo "[container_setup] NOTE: workload is constructable on-the-fly; Hulk source is NOT packaged."
echo "[container_setup] NOTE: full DBMS servers (MySQL/MariaDB/TiDB/...) are NOT preinstalled."
echo "[container_setup] NOTE: paper protocol = up to 2 weeks × 6 DBMSs."
