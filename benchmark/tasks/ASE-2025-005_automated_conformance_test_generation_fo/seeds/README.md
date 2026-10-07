# Seeds for ASE-2025-005 — WEST

## What is downloaded

There is no conventional tabular dataset. Container startup clones the authors'
public SpecTec fork and checks out the paper implementation:

- repository: `https://github.com/kaist-plrg/spectec.git`
- branch: `west`
- pinned commit: `ff7d3ae3764be358bd78af38aa34313791d900b4`
- container path: `/opt/west`

That checkout contains the SpecTec DSL inputs, engine-specific specification
subsets, the WEST top-down and bottom-up generators, the official Wasm
conformance suite, coverage scripts, and preserved bug-triggering tests.

## System toolchain (auto-installed)

`container_setup.sh` installs and verifies:

- OCaml 5.0.0 in a local opam switch
- dune 3.10.0, menhir 20230608, mdx 2.3.1, zarith 1.13
- the pinned WEST `watsup` executable
- WABT (`wasm-validate`, `wast2json`)
- Wasmtime 32.0.0

The full browser-engine matrix is deliberately not built at startup. V8 and
JavaScriptCore source builds are very large; SpiderMonkey has a similar cost.
The authors' own `dockerfile.mini` notes that WebKit cloning alone can take
about one hour. Wasmtime is the required practical baseline in this benchmark.

## Original experimental budget

The paper generated and executed tests for **24 hours per engine** with a
**3-second per-test timeout** on five engines: V8, SpiderMonkey,
JavaScriptCore, Wasmtime, and Wasmer. Thus the stated campaign is at least
**120 engine-hours** of generation/execution, excluding engine compilation,
failure triage, coverage measurement, and manual bug confirmation. It is not a
single 24-hour run.

For AI-Scientist, use a reduced and explicitly reported protocol, such as one
engine for minutes to a few hours. Do not claim full reproduction unless the
five-engine, 24-hour-per-engine protocol and matching revisions are used.
