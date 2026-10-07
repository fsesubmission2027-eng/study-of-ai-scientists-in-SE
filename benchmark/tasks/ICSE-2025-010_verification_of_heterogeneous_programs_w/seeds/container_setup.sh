#!/usr/bin/env bash
# Toolchain for ICSE-2025-010 (Hetrify / heterogeneous RISC-V verification).
# Invoked as root once per TaskSandbox container start.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
VENV_DIR="/opt/icse-2025-010-venv"
CBMC_PREFIX="/opt/cbmc"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQ_FILE="${SCRIPT_DIR}/requirements.txt"
if [[ ! -f "$REQ_FILE" && -f /task/seeds/requirements.txt ]]; then
  REQ_FILE="/task/seeds/requirements.txt"
fi

# Prefer shared mount; fall back to common agent path
CBMC_DEB_CANDIDATES=(
  "${CBMC_DEB:-}"
  /shared/hetrify-svcomp/tools/cbmc.deb
  /shared/hetrify-svcomp/tools/ubuntu-22.04-cbmc-5.95.1-Linux.deb
  /workplace/dataset_candidate/hetrify-svcomp/tools/cbmc.deb
)
GHIDRA_CANDIDATES=(
  /shared/hetrify-svcomp/tools/ghidra
  /shared/hetrify-svcomp/ghidra
  /workplace/dataset_candidate/hetrify-svcomp/tools/ghidra
)

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
        gcc-riscv64-unknown-elf \
        binutils-riscv64-unknown-elf \
        gdb-multiarch \
        time \
        bc \
        procps \
        jq \
        libgomp1 \
        libwww-perl; then
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
for bin in gcc g++ python3 git curl; do
  if ! command -v "$bin" >/dev/null 2>&1; then
    need_apt=1
    break
  fi
done
if ! command -v riscv64-unknown-elf-gcc >/dev/null 2>&1; then
  need_apt=1
fi
if ! python3 -m venv --help >/dev/null 2>&1; then
  need_apt=1
fi
if [[ "$need_apt" -eq 1 ]]; then
  apt_retry
fi

# --- Install CBMC from shared .deb when available ---
install_cbmc_from_deb() {
  local deb=""
  local c
  for c in "${CBMC_DEB_CANDIDATES[@]}"; do
    [[ -z "$c" ]] && continue
    if [[ -f "$c" ]]; then
      deb="$c"
      break
    fi
  done
  if [[ -z "$deb" ]]; then
    echo "[container_setup] WARN: CBMC .deb not found on shared mount; trying apt cbmc if present"
    apt-get install -y -qq --no-install-recommends cbmc 2>/dev/null || true
    return 0
  fi
  echo "[container_setup] Installing CBMC from $deb"
  mkdir -p "$CBMC_PREFIX"
  # dpkg may need deps; fall back to extracting .deb if dpkg fails in minimal images
  if dpkg -i "$deb" 2>/dev/null; then
    apt-get install -y -qq -f --no-install-recommends || true
  else
    local tmp
    tmp="$(mktemp -d)"
    dpkg-deb -x "$deb" "$tmp"
    mkdir -p "$CBMC_PREFIX/bin"
    # Common layout: usr/bin/cbmc
    if [[ -x "$tmp/usr/bin/cbmc" ]]; then
      cp -a "$tmp/usr/bin/"* "$CBMC_PREFIX/bin/" 2>/dev/null || true
      ln -sfn "$CBMC_PREFIX/bin/cbmc" /usr/local/bin/cbmc 2>/dev/null || true
      # also copy sibling tools
      for t in goto-cc goto-instrument cbmc; do
        [[ -x "$tmp/usr/bin/$t" ]] && ln -sfn "$CBMC_PREFIX/bin/$t" "/usr/local/bin/$t" 2>/dev/null || true
      done
    fi
    rm -rf "$tmp"
  fi
}

install_cbmc_from_deb

python3 -m venv "$VENV_DIR"
if [[ -f "$REQ_FILE" ]]; then
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    -r "$REQ_FILE"
else
  "${VENV_DIR}/bin/python" -m pip install --disable-pip-version-check --no-cache-dir \
    numpy pandas matplotlib pyyaml tqdm
fi

if id agent >/dev/null 2>&1; then
  chown -R agent:agent "$VENV_DIR" || true
elif [[ -n "${SUDO_UID:-}" && -n "${SUDO_GID:-}" ]]; then
  chown -R "${SUDO_UID}:${SUDO_GID}" "$VENV_DIR" || true
fi

# Optional Ghidra path hint
GHIDRA_HOME=""
for g in "${GHIDRA_CANDIDATES[@]}"; do
  if [[ -d "$g" ]]; then
    # find analyzeHeadless
    if [[ -x "$g/support/analyzeHeadless" ]]; then
      GHIDRA_HOME="$g"
    else
      nested="$(find "$g" -maxdepth 2 -type f -name analyzeHeadless 2>/dev/null | head -1 || true)"
      if [[ -n "$nested" ]]; then
        GHIDRA_HOME="$(cd "$(dirname "$nested")/.." && pwd)"
      fi
    fi
    [[ -n "$GHIDRA_HOME" ]] && break
  fi
done
if [[ -n "$GHIDRA_HOME" ]]; then
  echo "export GHIDRA_HOME=\"$GHIDRA_HOME\"" >/etc/profile.d/icse-2025-010-ghidra.sh || true
  echo "[container_setup] GHIDRA_HOME=$GHIDRA_HOME"
else
  echo "[container_setup] Ghidra not mounted (optional RQ3). FETCH_MODE=all on host to download."
fi

command -v gcc >/dev/null
command -v python3 >/dev/null
command -v riscv64-unknown-elf-gcc >/dev/null

cbmc_ver="$(cbmc --version 2>/dev/null | head -1 || echo 'cbmc-missing')"
riscv_ver="$(riscv64-unknown-elf-gcc --version 2>/dev/null | head -1 || echo 'riscv-gcc-missing')"
java_ver="$(java -version 2>&1 | head -1 || true)"

echo "[container_setup] OK ICSE-2025-010 Python=$("${VENV_DIR}/bin/python" --version 2>&1)"
echo "[container_setup] ${cbmc_ver} | ${riscv_ver}"
echo "[container_setup] java=${java_ver}"
echo "[container_setup] NOTE: SV-COMP mounts read-only at /shared/hetrify-svcomp;"
echo "[container_setup]       copy selected tasks under project/ before edits / compilation."
echo "[container_setup] NOTE: paper CBMC timeout=3000s, unwind=20 for correct programs;"
echo "[container_setup]       sandbox MEMORY may be far below paper 384GB — report reduced protocols."
echo "[container_setup] NOTE: IDA Pro unavailable (commercial). Prefer Ghidra when present."
echo "[container_setup] NOTE: Hetrify binary may be at anonymous.4open; else reimplement conversion."
