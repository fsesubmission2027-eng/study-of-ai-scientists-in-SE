# Task: ASE-2025-002 — Guiding Blackbox IoT Protocol Fuzzing with External Runtime Feedback

## Background

Internet of Things (IoT) devices are widely deployed and often contain security vulnerabilities, but their proprietary nature makes source code and firmware unavailable for analysis, restricting testing to blackbox methods. Blackbox fuzzing is commonly used to test network protocol implementations, yet its effectiveness is severely limited by the lack of feedback signals such as code coverage. Without coverage information, fuzzers struggle to generate inputs that explore deep parts of the implementation. Consequently, existing blackbox fuzzers for IoT protocols often achieve low coverage and miss bugs.

## Research Question

How can blackbox fuzzing of proprietary IoT protocols achieve higher code coverage and bug detection by leveraging runtime information from open-source implementations of the same protocol?

## Experiment Setup

### Datasets
```
- name: IoT Protocol Implementations
  source: [NOT SPECIFIED IN PAPER] – constructable by collecting open-source implementations of common IoT protocols (FTP, DNS, NTP, RTSP, DICOM, SIP, SSH, DTLS12) from public repositories such as GitHub.
  description: A curated set of server implementations for eight representative IoT protocols, varying in complexity and code base size, used as fuzzing targets or guidance sources.
  access: constructable
- name: Protocol Seed Corpus
  source: GitHub: AFLNet (https://github.com/aflnet/aflnet) and ProFuzzBench (https://github.com/profuzzbench/profuzzbench)
  description: Initial packet seeds for various protocol fuzzers, originally created by the AFLNet and ProFuzzBench projects.
  access: open
```

### Baselines
```
- name: Boofuzz
  reference: Boofuzz – a Python-based network protocol fuzzer (https://github.com/jtpereyda/boofuzz)
- name: Spike
  reference: SPIKE fuzzer creation kit (Immunity Inc., http://www.immunitysec.com/resources-freesoftware.shtml)
- name: Peach
  reference: Peach Fuzzer (https://www.peach.tech/)
- name: Snipuzz
  reference: Snipuzz – black-box fuzzer for IoT protocols (USENIX Security 2022)
- name: Pulsar
  reference: Pulsar – stateful black-box protocol fuzzer (2021 IEEE S&P)
- name: ChatAFL (blackbox mode)
  reference: ChatAFL – LLM-assisted fuzzer (2024 preprint, arXiv:2306.xxxxx), run in dumb mode with grammar-guided mutation
```

### Metrics
```
- name: Edge Coverage
  definition: Number of unique control-flow edges exercised during fuzzing, collected through binary instrumentation (e.g., AFL-style Clang instrumentation) of the target protocol implementation.
- name: Bug Discovery Count
  definition: Number of distinct confirmed bugs (crashes, hangs) triggered on the target protocol service during the fuzzing campaign.
```

### Sub-questions
```
- RQ1: To what extent does the approach improve edge coverage and bug discovery compared to baseline blackbox fuzzers?
- RQ2: How sensitive is the approach to the selection of open-source implementations used for guidance?
- RQ3: How does the approach enhance the quality of the initial seed corpus for blackbox fuzzing?
- RQ4: Can the approach uncover previously unknown vulnerabilities in real IoT devices?
```

### Target Subject

Server implementations of common IoT protocols (e.g., FTP, DNS, NTP, SIP, RTSP, DICOM, SSH, DTLS12) running on Linux virtual machines or physical IoT devices.

### Constraints

The blackbox fuzzer must not access the source code or binary instrumentation of the target. Experiments require two separate machines communicating over LAN; each fuzzer process is limited to one CPU core, a 10-hour time budget, and is repeated 5 times. Target and guidance implementations run inside Ubuntu 20.04 virtual machines.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

All required protocol implementations are open-source and can be compiled on Ubuntu 20.04. Seed corpora and several baseline fuzzers (Boofuzz, Snipuzz, ChatAFL) are publicly available; others (Spike, Peach) may require obtaining licenses. The experimental setup demands careful orchestration of virtual machines and LAN communication, which can be technically challenging. Compute cost is moderate: about 100 CPU-hours per complete experiment (10 hours × 5 repeats across machines).

## Metadata

```
subfield: Fuzzing & Vulnerability Detection
venue: ASE 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```