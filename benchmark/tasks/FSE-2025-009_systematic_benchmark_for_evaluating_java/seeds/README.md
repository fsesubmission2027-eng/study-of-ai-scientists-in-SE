# Seeds for FSE-2025-009 — Gleipner Java Deserialization Gadget-Chain Benchmark

## Downloaded data

The paper artifact is cloned and category JARs are built on the host:

- repository: `https://github.com/software-engineering-and-security/Gleipner`
- host path: `~/ai_scientist_inputs/shared_datasets/gleipner`
- legacy Docker mount: `/shared/gleipner` (read-only)
- AI Scientist / aligned path: `dataset_candidate/gleipner/`
- environment variable: `GLEIPNER_HOME=dataset_candidate/gleipner`

### Benchmark files (agent must use these)

| Path | Content |
|------|---------|
| `algorithms/_target/gleipner.chains-1.0-*.jar` | Per-category benchmark JARs (depth, polymorphism, reflection, ysoserial, …) |
| `algorithms/_target/gleipner.chains-1.0-basic.jar` | Sanity-check chains (start here) |
| `algorithms/evaluator.jar` | Official scorer for tool output files |
| `algorithms/` | Author harness / configs for published detectors (optional reference) |
| `chains/`, `scripts/` | Source + chain generators (optional; mount is read-only) |

Re-download / rebuild:

```bash
./download_gleipner_dataset.sh
```

Disk footprint is about **~180 MB** after clone + `make compile` (no git-lfs).

Sink method for tool configuration:

```text
gleipner.core.SinkGadget.sinkMethod(String taint)
```

Ground truth: JAR `META-INF/MANIFEST.MF` properties `chains-tp` / `chains-fp`.

## Java / toolchain environment

`container_setup.sh` automatically ensures:

```text
JDK 8  -> /usr/lib/jvm/java-8-openjdk-amd64   ($JAVA8_HOME)
JDK 11 -> /usr/lib/jvm/java-11-openjdk-amd64  ($JAVA_HOME, default)
Maven, make, g++
/opt/fse-2025-009-venv   (Python orchestration stack)
```

It also copies `custom.so` to `/tmp/custom.so` for the JNI category when Gleipner is mounted.

**Baseline detectors are intentionally not preinstalled.** The agent may clone/build
comparison tools (GadgetInspector, Serianalyzer, Tabby, JDD, …) as needed. Prefer
`$JAVA8_HOME` for older analyzers.

## Agent-visible files

| Path | Visible to agent? | Purpose |
|------|-------------------|---------|
| `agent/dataset_paths.json` | Yes | Benchmark paths and JAR inventory |
| `agent/metrics.json` | Yes | Required metric keys |
| `requirements.txt` | No (pip only) | Python deps for orchestration |
| `container_setup.sh` | No (root setup) | JDK/Maven/Python install |
| `benchmark_config.json` | No | Staging / benchmark rules |
| `README.md` | No | Human documentation |

## Scale note

Running all seven paper baselines across every Gleipner category can exceed a single
autonomous run. Subset categories (always include `basic`) and fewer tools are
acceptable when documented; the **full JAR set** remains under
`dataset_candidate/gleipner/algorithms/_target/`.
