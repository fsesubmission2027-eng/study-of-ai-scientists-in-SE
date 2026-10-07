#!/usr/bin/env bash
# Reproducible WEST/SpecTec toolchain for ASE-2025-005.
# Invoked as root once per TaskSandbox container start.
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

WEST_REPO="https://github.com/kaist-plrg/spectec.git"
WEST_COMMIT="ff7d3ae3764be358bd78af38aa34313791d900b4"
WEST_ROOT="/opt/west"
WEST_DIR="${WEST_ROOT}/spectec"
WASMTIME_VERSION="32.0.0"

apt_retry() {
  local attempt
  for attempt in 1 2 3; do
    if apt-get update -qq \
      && apt-get install -y -qq --no-install-recommends --fix-missing \
        ca-certificates curl git make gcc pkg-config m4 \
        opam libgmp-dev wabt xz-utils; then
      return 0
    fi
    if [[ "$attempt" -eq 3 ]]; then
      echo "[container_setup] apt install failed after 3 attempts" >&2
      return 1
    fi
    sleep $((attempt * 5))
  done
}

apt_retry

if [[ ! -d "${WEST_ROOT}/.git" ]]; then
  rm -rf "$WEST_ROOT"
  git clone --filter=blob:none "$WEST_REPO" "$WEST_ROOT"
fi
git -C "$WEST_ROOT" fetch --depth 1 origin "$WEST_COMMIT"
git -C "$WEST_ROOT" checkout --detach "$WEST_COMMIT"

if [[ ! -d "${WEST_DIR}/_opam" ]]; then
  opam init --bare --disable-sandboxing --yes
  (
    cd "$WEST_DIR"
    opam switch create . 5.0.0 --yes
  )
fi

(
  cd "$WEST_DIR"
  eval "$(opam env --switch=. --set-switch)"
  opam install --yes \
    dune.3.10.0 \
    menhir.20230608 \
    mdx.2.3.1 \
    zarith.1.13
  opam exec -- make exe
)

install -m 0755 "${WEST_DIR}/watsup" /usr/local/bin/watsup

if ! command -v wasmtime >/dev/null 2>&1; then
  arch="$(dpkg --print-architecture)"
  case "$arch" in
    amd64) release_arch="x86_64" ;;
    arm64) release_arch="aarch64" ;;
    *)
      echo "[container_setup] unsupported architecture for Wasmtime: ${arch}" >&2
      exit 1
      ;;
  esac
  archive="wasmtime-v${WASMTIME_VERSION}-${release_arch}-linux.tar.xz"
  url="https://github.com/bytecodealliance/wasmtime/releases/download/v${WASMTIME_VERSION}/${archive}"
  tmp_dir="$(mktemp -d)"
  curl --fail --location --retry 3 "$url" -o "${tmp_dir}/${archive}"
  tar -xJf "${tmp_dir}/${archive}" -C "$tmp_dir"
  install -m 0755 \
    "${tmp_dir}/wasmtime-v${WASMTIME_VERSION}-${release_arch}-linux/wasmtime" \
    /usr/local/bin/wasmtime
  rm -rf "$tmp_dir"
fi

# The agent runs unprivileged and may modify a copied checkout for experiments.
chown -R agent:agent "$WEST_ROOT"

command -v watsup >/dev/null
command -v wasm-validate >/dev/null
command -v wast2json >/dev/null
command -v wasmtime >/dev/null

echo "[container_setup] OK WEST=${WEST_COMMIT} OCaml=5.0.0 Wasmtime=${WASMTIME_VERSION} WABT=$(wasm-validate --version 2>/dev/null || true)"
