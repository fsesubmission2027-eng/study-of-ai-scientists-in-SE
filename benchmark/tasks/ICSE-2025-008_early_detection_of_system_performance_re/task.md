# Task: ICSE-2025-008 — Early Detection of System Performance Regressions from Component-Level Tests in Microservice Applications

## Background

Performance regressions in software systems can cause severe financial and reputational losses. Traditional system-level performance testing (e.g., load testing) is the primary means to catch these regressions before release, but it is extremely expensive, time-consuming, and can only be performed late in the development cycle after the full system is built and deployed. Component-level testing (e.g., unit tests or microbenchmarks) is cheaper and can run earlier during development, but it only measures isolated component performance and cannot reveal the impact on end-to-end system behavior under realistic workloads. As a result, developers lack a way to reliably predict whether a local performance deviation at the component level will escalate into a system-level regression without actually conducting full-system tests.

## Research Question

How can component-level performance test results be used to predict system-level performance regressions in microservice-based software systems before the system is fully integrated and deployed?

## Experiment Setup

### Datasets
```
- name: TeaStore
  source: https://github.com/DescartesResearch/TeaStore
  description: A microservice reference benchmark application simulating a web store, consisting of five services plus a service registry, approximately 33k lines of code and 163 unit tests.
  access: open
- name: TrainTicket
  source: https://github.com/FudanSELab/train-ticket
  description: A microservice-based train ticket booking system with up to 41 microservices, approximately 289k lines of code and 628 unit tests.
  access: open
```

### Baselines
```
[NOT SPECIFIED IN PAPER]
```

### Metrics
```
- name: Response time deviation
  definition: Percentage increase or absolute change in end-to-end request response time compared to a non-regressed baseline.
- name: CPU usage deviation
  definition: Difference in CPU utilization of service containers relative to the non-regressed scenario.
- name: Detection accuracy
  definition: True positive rate and false positive rate of classifying a code change as a system-level performance regression.
```

### Sub-questions
```
- RQ1: How does the accuracy of system-level regression prediction vary with different regression intensities and injection locations at the component level?
- RQ2: What is the effect of varying system workload intensities on the reliability of early regression detection?
```

### Target Subject

Open-source microservice benchmark systems with detailed documentation, abundant unit tests, and realistic complexity, such as TeaStore and TrainTicket.

### Constraints

The detection must be feasible using only component-level test data and architecturally relevant information (e.g., service topology, call graphs) that can be obtained without executing full system-level performance tests. No system-level test data may be used to make the prediction for a new code version; system-level tests serve only as ground truth for evaluation.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

Both subject systems are publicly available on GitHub with existing unit tests. Performance monitoring tools (e.g., Kieker) are open-source. Regression injection via busy-wait is straightforward. Reproducing the setup requires two interconnected Linux machines with moderate resources (Intel i7, 32 GB RAM). Running all test repetitions and system workloads may take several hours per system.

**Benchmark harness (host):** run `./download_perf_regression_subjects.sh` once, then `./run_aiscientist_benchmark.sh run` (or `run_airesearcher_benchmark.sh`). Data lands in `shared_datasets/perf-regression-early-detect` (~80–110 MiB per subject git tree; TeaStore images ~2.2 GiB; JMeter ~83 MiB; TrainTicket runtime needs ≥24 GiB RAM / ≥50 GiB disk). Zenodo replication: https://doi.org/10.5281/zenodo.13135986. Container setup installs OpenJDK 17, Maven, Docker CLI/Compose, and a Python venv for stats.

## Metadata

```
subfield: AIOps & System Reliability
venue: ICSE 2025
year: 2025
difficulty: medium
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```