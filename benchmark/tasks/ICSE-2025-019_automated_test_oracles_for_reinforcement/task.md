# Task: ICSE-2025-019 — Automated Test Oracles for Reinforcement Learning Software

## Background

Reinforcement learning (RL) software outputs trained agents that learn optimal decision-making policies. Testing such software is challenging because the correctness of a trained agent cannot be uniquely defined: agent performance is multi-dimensional, statistical, and environment-dependent, making traditional output correctness criteria inapplicable. The lack of a well-defined expected output leads to the test oracle problem—a mechanism to automatically judge whether an RL implementation is buggy or correct is missing. Current practice relies on human experts to manually inspect agent behavior, which is subjective, costly, and not scalable. There is a critical need for an automated oracle that can determine the correctness of RL software outputs without human intervention.

## Research Question

How to design an automated test oracle for RL software that effectively detects bugs in RL implementations using only the behavior of the trained agents?

## Experiment Setup

### Datasets
```
- name: RL Software Bug Benchmark (LPEA AE artifact)
  source: Zenodo AE package https://doi.org/10.5281/zenodo.14759447 (GitHub mirror https://github.com/QixinWangCpsLab/LPEA_Oracle_ICSE2025_AE_Track); based on Stable Baselines3 commit 4efee92.
  description: Balanced buggy / bug-less SB3 implementations of A2C (19/19), PPO (22/22), and TD3 (15/15). Includes 44 injectable bugs (ids 0–43), harmless no-op variations for bug-less expansion, and LPEA oracle scripts. Zip ≈ 4.3 MiB; no GB-scale external corpus.
  access: provided via shared_datasets/lpea-oracle-icse2025 (download_lpea_oracle.sh)
```

### Baselines
```
- name: Human Oracle (STARLA-expanded)
  reference: Based on the STARLA specification (Zolfagharian et al.) and expanded in the source paper, using classic RL environments (e.g., CartPole, MountainCar) and human-defined faulty states. Paper labels 672 interaction traces (~6 human-hours; ~24h compute).
```

### Metrics
```
- name: False Positive Count (FP)
  definition: Number of bug-less implementations incorrectly flagged as buggy.
- name: True Negative Count (TN)
  definition: Number of bug-less implementations correctly identified as bug-less.
- name: False Negative Count (FN)
  definition: Number of buggy implementations incorrectly identified as bug-less.
- name: Accuracy
  definition: (TN + TP) / (TN + TP + FP + FN), where TP is true positive count.
- name: Precision
  definition: TP / (TP + FP).
- name: Recall
  definition: TP / (TP + FN).
- name: F1 Score
  definition: Harmonic mean of precision and recall.
- name: ROC AUC
  definition: Area under the receiver operating characteristic curve, plotting true positive rate vs. false positive rate.
```

### Sub-questions
```
- RQ1: How does the automated oracle compare to the human oracle in terms of bug detection accuracy?
- RQ2: What are the trade-offs between false positive and false negative rates for the automated oracle?
- RQ3: How does the automated oracle's performance differ across on-policy (A2C, PPO) and off-policy (TD3) RL algorithms?
```

### Target Subject

Stable implementations of on-policy (A2C, PPO) and off-policy (TD3) reinforcement learning algorithms from the Stable Baselines3 library, as well as their buggy variants created via artificial and real-world bug injection.

### Constraints

The automated oracle must operate without access to the internal source code of the RL implementation; decisions must be based solely on the behaviour of the trained agents. The oracle must be fully automated and require no human judgment. Evaluation uses the described benchmark of implementations; each implementation is supplied with a set of training environments, produces an agent, and the oracle judges correctness from the agent's interaction with test environments.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The AE artifact provides SB3 + LPEA oracle + bug injection scripts; the bug benchmark can also be reconstructed over SB3 commit 4efee92. Training agents for the full paper protocol (I=20 agents, multi-algorithm) needs substantial CPU/GPU time (paper: ≤129h on an RTX 3060 laptop). For sandbox runs, use disclosed reduced `I`/`J` or algorithm subsets. Main research challenge remains designing a novel automated oracle competitive with the human baseline under the black-box constraint.

### Harness (AI Scientist / container)

This task is wired like ICSE-2025-017/013 (**paper AE artifact** + container Python/RL stack):

| File | Role |
|------|------|
| `download_lpea_oracle.sh` | Host-side download from Zenodo AE zip (~4.3 MiB) |
| `task.env` | Docker image, `MEMORY=32g`, `CPUS=8`, mount `shared_datasets/lpea-oracle-icse2025` |
| `seeds/container_setup.sh` | CPU torch, Gymnasium, editable SB3 from artifact, cvxpy/control |
| `run_aiscientist_benchmark.sh` / `run_airesearcher_benchmark.sh` | Launchers |

```bash
chmod +x download_lpea_oracle.sh run_aiscientist_benchmark.sh run_airesearcher_benchmark.sh
./download_lpea_oracle.sh
./run_aiscientist_benchmark.sh run
```

**Zenodo:** https://doi.org/10.5281/zenodo.14759447  
**GitHub:** https://github.com/QixinWangCpsLab/LPEA_Oracle_ICSE2025_AE_Track  
**Shared data root:** `~/ai_scientist_inputs/shared_datasets/lpea-oracle-icse2025`  
**In-container mount:** `/shared/lpea-oracle-icse2025` → agent `dataset_candidate/lpea-oracle-icse2025/`

### Dataset size

| Item | Size / count |
|------|----------------|
| Zenodo AE zip | **≈ 4.3 MiB** |
| Paper benchmark | A2C **19/19**, PPO **22/22**, TD3 **15/15** (buggy/bug-less) |
| Injectable bugs | **44** (ids 0–43; `-1` = bug-less) |
| Human-oracle traces | **672** |
| On-disk after extract | See `.artifact_meta.txt` / `du -sh` after `./download_lpea_oracle.sh` |

Default download uses Zenodo. Set `FETCH_MODE=git` to clone the GitHub mirror. Sandbox uses CPU torch by default; full paper wall-clock may need GPU and reduced protocol disclosure.

## Metadata

```
subfield: AI/ML System Testing
venue: ICSE 2025
year: 2025
difficulty: medium
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```
