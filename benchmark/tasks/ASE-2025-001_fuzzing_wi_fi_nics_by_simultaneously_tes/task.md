# Task: ASE-2025-001 — Fuzzing Wi-Fi NICs by Simultaneously Testing Transmission and Reception Interactions

## Background

Wi-Fi Network Interface Cards (NICs) are critical for wireless connectivity in many domains, making their security paramount. Fuzzing has been applied to detect vulnerabilities in Wi-Fi devices, but existing fuzzers focus on unidirectional testing—either sending frames as a station or as an access point. This approach overlooks the complex interactions between frame transmission and reception (e.g., acknowledgment sequences, buffer management, retransmission protocols) that involve shared state and execution dependencies. Consequently, vulnerabilities hidden in these interactions remain undetected, limiting the effectiveness of current fuzzing. There is a need for a testing method that can generate test cases simultaneously exercising both transmission and reception paths to uncover such vulnerabilities.

## Research Question

How can a fuzzer generate test inputs that explore both transmission and reception behaviors concurrently to detect vulnerabilities hidden in Wi-Fi NIC interaction logic?

## Experiment Setup

### Datasets
```
- name: Wi-Fi NIC Testbed
  source: Hardware procurement (e.g., Intel AX210, Realtek RTL8852BE, Mediatek MT7921, Broadcom BCM4361); complete list available from the research project repository or selected based on availability of widely deployed chipsets.
  description: Eight real-world Wi-Fi NICs from various manufacturers covering a range of chipsets, used to evaluate fuzzing effectiveness on diverse hardware/firmware.
  access: constructable
```

### Baselines
```
- name: OwFuzz
  reference: Zhang et al., 'OwFuzz: Fuzzing Wi-Fi Access Points with Protocol-aware Mutation', NDSS 2022
- name: wpaspy
  reference: Kim et al., 'Fuzzing Wi-Fi Drivers using wpa_supplicant P2P Injection', 2020
- name: Greyhound
  reference: Liu et al., 'Greyhound: Directed Fuzzing for Wi-Fi Stations', USENIX Security 2021
- name: VIRTFUZZ
  reference: Chen et al., 'VIRTFUZZ: Fuzzing Wi-Fi Drivers via Virtual Machines', 2020
- name: µAFL
  reference: Zheng et al., 'µAFL: Non-Intrusive Feedback-Driven Fuzzing for Microcontroller Firmware', USENIX Security 2021
```

### Metrics
```
- name: Number of unique bugs detected
  definition: Count of previously unknown vulnerabilities discovered during the fuzzing campaign that were confirmed via reproduction and root cause analysis.
- name: Average speed-up
  definition: Ratio of the baseline fuzzer's time to find a bug to the evaluated fuzzer's time, averaged across all bugs discovered.
```

### Sub-questions
```
- RQ1: How effective is the fuzzer at detecting previously unknown vulnerabilities in real-world Wi-Fi NICs compared to existing tools?
- RQ2: Do the interaction model and the coordination strategy improve the fuzzer's ability to trigger vulnerabilities in transmission-reception interactions?
- RQ3: What is the precision and recall of the anomaly detectors in identifying true vulnerabilities while testing?
- RQ4: How does the fuzzer's internal code coverage of Wi-Fi NICs (where measurable) compare to state-of-the-art fuzzers?
```

### Target Subject

Wi-Fi Network Interface Cards (NICs) that implement the IEEE 802.11 standard, including their driver, firmware, and hardware components. The NICs may operate in Access Point (AP) or Station (STA) modes. Examples: Intel AX210, Realtek RTL8852BE, Broadcom BCM4361.

### Constraints

Time limit: 24 hours per fuzzing run. Network: isolated local wireless network with no external interference. Target configuration: NICs must use default settings; no custom tuning. Repetition: 10 independent runs per experiment. No access to internal firmware source code or hardware instrumentation. Fuzzer must not rely on known vulnerability signatures or prior bug reports for the specific targets.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The evaluation requires physical access to multiple Wi-Fi NICs, which can be purchased. Setting up an isolated wireless lab is straightforward. Fuzzing campaigns are long (24h per run, 10 repetitions per tool across many NICs), necessitating parallel execution on multiple machines. No specialized hardware beyond the NICs and a standard desktop is needed. The main challenge is the time and resource investment to run the full suite, and ensuring driver stability across different NICs under heavy fuzz testing, which may cause system freezes.

## Metadata

```
subfield: Fuzzing & Vulnerability Detection
venue: ASE 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```