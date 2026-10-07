# Task: ICSE-2025-017 — Automated Detection of Smart Contract Defects on the TON Blockchain

## Background

The Open Network (TON) blockchain is a high-performance platform designed for decentralized applications, supporting asynchronous communication and a unique cell-based data structure. Smart contracts on TON are written primarily in FunC or Tact, and their development introduces new defect patterns distinct from those on synchronous blockchains like Ethereum. Official documentation and security audit reports have identified several types of defects that can lead to incorrect outcomes, unexpected behavior, or security vulnerabilities. However, no automated detection tool exists for TON smart contract defects, leaving manual review as the only option, which is impractical for the growing number of contracts. This gap motivates the need for an effective method to automatically identify such defects in TON smart contracts.

## Research Question

What is an effective approach to automatically detect known defect patterns in TON smart contracts with high precision?

## Experiment Setup

### Datasets
```
- name: TON FunC Smart Contracts
  source: Constructed from TON Verifier (https://verifier.ton.org) and GitHub (searching for .func/.fc files with TON-specific entry functions).
  description: 922 unique FunC smart contracts (294 from on-chain verified contracts, 628 from open-source GitHub repositories).
  access: constructable
- name: TON Tact Smart Contracts
  source: Constructed by compiling Tact contracts to FunC, with sources from TON Verifier and GitHub.
  description: 718 unique Tact-originated smart contracts (258 on-chain, 460 open-source) after deduplication.
  access: constructable
```

### Baselines
```
[NOT SPECIFIED IN PAPER]
```

### Metrics
```
- name: Precision per defect
  definition: Ratio of true positive instances of a specific defect type correctly identified to all instances reported as that defect type (TP/(TP+FP)).
- name: Overall precision
  definition: Weighted average of per-defect precision rates, where each defect type's precision is weighted by its total occurrences in the dataset.
```

### Sub-questions
```
- RQ1: How prevalent are the eight defined defect types in real-world FunC and Tact smart contracts?
- RQ2: How effective is the detection approach in terms of precision on the FunC dataset?
- RQ3: How effective is the detection approach in terms of precision on the Tact dataset?
```

### Target Subject

Smart contracts on the TON blockchain, written in FunC or Tact. This includes DeFi protocols, NFT marketplaces, wallets, and other decentralized applications deployed on TON.

### Constraints

Detection must use only the smart contract source code; no on-chain execution or dynamic traces are allowed. The dataset consists of open-source, verifiable contracts. The analysis should be reproducible on a standard Linux server (e.g., 12-core CPU, 120 GB RAM). No existing automated TON defect detection tools are available for comparison.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

Both datasets can be reconstructed by crawling TON Verifier and GitHub with the described heuristics. The public FunC/Tact compilers are available for building the analysis. The main technical challenge is accurately modeling the asynchronous message-passing and the cell data structure to detect defects, as no prior analysis framework exists for TON. The computational load is moderate, as the total contract count is under 2,000, and static analysis can run offline.

### Harness (AI Scientist / container)

This task is wired like ICSE-2025-013/010 (**paper artifact corpora**; optional tiny baseline ELF):

| File | Role |
|------|------|
| `download_ton_contracts.sh` | Host-side download from anonymous.4open artifact zip |
| `task.env` | Docker image, `MEMORY=32g`, `CPUS=8`, mount `shared_datasets/ton-smart-contract-defects` |
| `seeds/container_setup.sh` | GCC/CMake, Python venv, Node/npm |
| `run_aiscientist_benchmark.sh` / `run_airesearcher_benchmark.sh` | Launchers |

```bash
chmod +x download_ton_contracts.sh run_aiscientist_benchmark.sh run_airesearcher_benchmark.sh
./download_ton_contracts.sh
# optional baseline binary: FETCH_MODE=all ./download_ton_contracts.sh
./run_aiscientist_benchmark.sh run
```

**Artifact:** https://anonymous.4open.science/r/TON_support_material-ECD4/  
**Shared data root:** `~/ai_scientist_inputs/shared_datasets/ton-smart-contract-defects`  
**In-container mount:** `/shared/ton-smart-contract-defects` → agent `dataset_candidate/ton-smart-contract-defects/`

### Dataset size

| Item | Size / count |
|------|----------------|
| Paper evaluation set | **922 FunC + 718 Tact = 1,640** unique contracts |
| Artifact tree | **~19,498 files** (`contracts/`, `repo/`, `samples/`, `results/`, …) |
| Optional `TONScanner` ELF | **~3.4 MiB** (+ `lib64/`) |
| On-disk MiB after extract | See `.artifact_meta.txt` / `du -sh` after `./download_ton_contracts.sh` |

Default download keeps **datasets** (`contracts/`, `repo/`, `samples/`, `results/`, `blogs/`). Set `FETCH_MODE=all` to also keep the baseline binary. Sandbox RAM (32g) is below the paper’s 120 GB — disclose reduced subsets when needed. anonymous.4open may rate-limit; the download script retries with backoff.

## Metadata

```
subfield: Software Security
venue: ICSE 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```