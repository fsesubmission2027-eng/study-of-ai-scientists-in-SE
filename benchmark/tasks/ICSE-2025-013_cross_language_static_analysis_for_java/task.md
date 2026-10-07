# Task: ICSE-2025-013 — Cross-Language Static Analysis for Java Native Code Interactions

## Background

Java programs extensively use native methods via the Java Native Interface (JNI) to access OS features, legacy C libraries, or performance-critical routines. These native methods are declared in Java but implemented in C, creating complex cross-language interactions: Java calls C functions, and C code can invoke Java methods, create objects, or access fields via JNI. Modern static analysis of Java applications struggles with such mixed-language code because native implementations are opaque to Java-only analyzers. Existing state-of-the-art tools either unsoundly ignore native code or partially model it, resulting in low recall (many dynamic interactions missed) or poor precision (many spurious interactions reported). This severely limits the usefulness of static analysis for bug finding, security auditing, and software understanding in real-world Java applications that depend on native code. There is thus a pressing need for a static analysis framework that can accurately resolve both directions of JNI interactions with high soundness and precision.

## Research Question

How can a static analysis framework resolve cross-language interactions through JNI to achieve significantly higher soundness and precision than current tools, while handling full JNI specifications and real-world Java/C codebases?

## Experiment Setup

### Datasets
```
- name: OpenJDK 8
  source: https://openjdk.org/projects/jdk8/
  description: The reference implementation of Java SE 8, containing extensive JNI usage across core libraries and a large test suite (28 directories, hundreds of test cases).
  access: open
- name: aspectj-1.6.9
  source: https://github.com/eclipse/org.aspectj
  description: Aspect-oriented programming extension for Java; uses native methods for weaving.
  access: open
- name: lucene-4.3.0
  source: https://github.com/apache/lucene
  description: High-performance text search engine library with native code acceleration.
  access: open
- name: tomcat-native-1.2.23
  source: https://github.com/apache/tomcat-native
  description: Apache Tomcat native library providing OS-level integration via JNI.
  access: open
- name: log4j-1.2.16
  source: https://github.com/apache/logging-log4j2
  description: Logging framework that uses native code for performance.
  access: open
```

### Baselines
```
- name: JN-Sum
  reference: JN-Sum: A Summary-Based Approach for Resolving Native Code in Java Programs
- name: Native-Scanner
  reference: Native-Scanner: A Static Analysis Framework For Resolving JNI Interactions
```

### Metrics
```
- name: Soundness (Recall)
  definition: Percentage of dynamically recorded true cross-language interactions (via JVM instrumentation) that are correctly resolved by the static analysis.
- name: Precision
  definition: Percentage of statically resolved interactions that match the true interactions determined by manual inspection of source code.
- name: Efficiency
  definition: Wall-clock time for the entire analysis on each benchmark, measured in seconds.
```

### Sub-questions
```
- RQ1: What is the recall and precision of resolving Java-to-C native method calls compared to the baselines, using dynamic ground truth?
- RQ2: What is the recall and precision of resolving the most common C-to-Java interactions (method calls, object creation, field accesses) compared to the baselines?
- RQ3: How does the analysis scale with program size and what is the speedup relative to baseline analyzers?
```

### Target Subject

Java applications that make extensive use of JNI to C native code, including the JDK itself and widely-used libraries with native components. Examples: OpenJDK core class libraries, Apache Tomcat native connectors, Lucene search engine.

### Constraints

Must handle full JNI specification (including dynamic binding via RegisterNatives, all JNI function types). Must analyze unmodified C and Java source/binary code simultaneously. Ground truth for soundness requires running test suites with a modified JVM to record dynamic interactions. Hardware: 64-bit Linux, recommended 128GB RAM for whole-program analysis. Time budget not specified but the analysis should complete within hours for the largest benchmark.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

All benchmarks are open-source and accessible. The ground truth collection requires building a custom HotSpot JVM with instrumentation, which is complex but documented. The analysis is memory-intensive (OpenJDK analysis may need >64GB). Integrating a Java pointer analysis with a C pointer analysis is technically challenging, requiring careful cross-language points-to propagation. The task is suitable for researchers with expertise in program analysis and JNI internals.

### Harness (AI Scientist / container)

This task is wired like ICSE-2025-005/010 (**datasets only**; tool/baseline images are not pre-downloaded):

| File | Role |
|------|------|
| `download_jnifer_subjects.sh` | Host-side download of the five paper subjects |
| `task.env` | Docker image, `MEMORY=48g`, `CPUS=8`, mount `shared_datasets/jnifer-subjects` |
| `seeds/container_setup.sh` | OpenJDK 17 (+ optional 8), Maven/Ant, GCC/CMake, Python venv |
| `run_aiscientist_benchmark.sh` / `run_airesearcher_benchmark.sh` | Launchers |

```bash
chmod +x download_jnifer_subjects.sh run_aiscientist_benchmark.sh run_airesearcher_benchmark.sh
./download_jnifer_subjects.sh
./run_aiscientist_benchmark.sh run
```

**Shared data root:** `~/ai_scientist_inputs/shared_datasets/jnifer-subjects`  
**In-container mount:** `/shared/jnifer-subjects` → agent `dataset_candidate/jnifer-subjects/`

### Dataset sizes (subjects only)

| Subject | Compressed size |
|---------|-----------------|
| OpenJDK 8 (`openjdk8u462-b08.tar.xz`) | **~57 MiB** |
| aspectj-1.6.9 | **~50 MiB** |
| lucene-4.3.0-src | **~27 MiB** |
| log4j-1.2.16 | **~2.7 MiB** |
| tomcat-native-1.2.23 | **~0.4 MiB** |
| **Total** | **~140 MiB** |

HotSpot instrumentation ground truth is **not** in this mount. Optional tool images (JNIFER/JN-Sum/Native-Scanner) live on Zenodo `10.5281/zenodo.14897613` and are **not** required for the subject mount. Sandbox RAM (48g) is below the paper’s 128 GB — disclose reduced subsets when needed.

## Metadata

```
subfield: Program Analysis & Verification
venue: ICSE 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```