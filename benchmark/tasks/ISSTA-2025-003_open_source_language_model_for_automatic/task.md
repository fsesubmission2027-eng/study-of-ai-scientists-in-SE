# Task: ISSTA-2025-003 — Open-Source Language Model for Automatic Software Issue Resolution

## Background

Large language models (LLMs) have significantly improved coding efficiency, and recent LLM-based agents can automatically perform software maintenance and evolution tasks, such as fixing bugs or adding features by resolving real-world GitHub issues. However, state-of-the-art performance relies heavily on closed-source models like GPT-4, which restricts accessibility, customization, and raises privacy concerns when handling sensitive codebases. Moreover, existing models are predominantly trained on static code data, lacking an understanding of the iterative, dynamic processes that developers follow in practice. This gap hinders their ability to navigate complex project structures and generate context-appropriate solutions, limiting practical utility in real-world scenarios. Consequently, there is a need for an open-source model that can effectively resolve end-to-end software issues with performance comparable to closed-source alternatives.

## Research Question

How can an open-source large language model be developed to achieve competitive performance with closed-source models on automatic resolution of real-world GitHub issues, as measured on the SWE-bench benchmark?

## Experiment Setup

### Datasets
```
- name: SWE-bench Lite
  source: https://github.com/SWE-bench/SWE-bench
  description: A curated subset of SWE-bench containing 300 test instances, each consisting of a GitHub issue and a repository snapshot with unit tests.
  access: open
- name: SWE-bench Verified
  source: https://github.com/SWE-bench/SWE-bench
  description: A human-verified subset of SWE-bench with 500 instances, designed to be reliable and diverse, officially recommended for benchmarking LLM-based software engineering agents.
  access: open
```

### Baselines
```
- name: GPT-4
  reference: Closed-source; accessible via OpenAI API
- name: Claude
  reference: Closed-source; accessible via Anthropic API
- name: CodeLlama
  reference: Open-source; https://github.com/facebookresearch/codellama
- name: StarCoder
  reference: Open-source; https://huggingface.co/bigcode/starcoder
- name: DeepSeek-Coder
  reference: Open-source; https://github.com/deepseek-ai/DeepSeek-Coder
- name: Qwen2.5 Coder
  reference: Open-source; available via Hugging Face
- name: CodeGemma
  reference: Open-source; https://github.com/google-deepmind/codegemma
- name: CodeLlama-Instruct
  reference: Open-source instruction-tuned variant of CodeLlama
- name: WizardCoder
  reference: Open-source instruction-tuned model
- name: Magicoder
  reference: Open-source instruction-tuned model
- name: WaveCoder
  reference: Open-source instruction-tuned model
- name: OpenCodeInterpreter
  reference: Open-source instruction-tuned model
```

### Metrics
```
- name: Resolve rate
  definition: Percentage of GitHub issues for which the generated patch passes all associated test cases in the repository, as automatically evaluated by the SWE-bench harness.
```

### Sub-questions
```
- RQ1: How does the open-source model's issue resolution rate compare against state-of-the-art baselines on SWE-bench Lite and SWE-bench Verified?
- RQ2: How do model size and training data characteristics impact issue resolution performance?
```

### Target Subject

LLM-based software engineering agents that automatically resolve issues (bugs, feature requests) in Python repositories, such as those from the SWE-bench collection (e.g., django, scikit-learn, matplotlib).

### Constraints

The solution must be fully open-source and must not rely on closed-source models at inference time. Training data must not include any repositories or issues present in the SWE-bench test sets (data leakage prevention). Evaluation must strictly follow the SWE-bench protocol using the provided Docker-based execution environment.

## Expected Artifacts

- idea
- code
- experiment_results
- paper

## Feasibility Notes

The SWE-bench benchmark and its evaluation infrastructure are publicly available and well-documented. Collecting a training corpus of pull requests from public GitHub repositories via the API is feasible but requires substantial storage and processing. Training a large language model (e.g., 7B parameters) requires significant GPU resources (e.g., 8×A100 GPUs) and may take several days. Careful data leakage checks must be implemented to avoid contamination.

## Metadata

```
subfield: LLM for Software Engineering
venue: ISSTA 2025
year: 2025
difficulty: hard
paper_type: tool
award: ACM SIGSOFT Distinguished Paper Award
```