# Seeds for FSE-2025-005 — Automated Porting of Security Patches Across Divergent Repository Branches

## Agent data policy

**No pre-downloaded evaluation corpus.** The dataset must be **constructed** from public NVD/CVE
records and GitHub commits following the four-step protocol described in the task brief.
Construct and store under `dataset_candidate/cve_patches/` inside the container workspace.

Human-only files live in `seeds/` root. Agent-visible config is under `seeds/agent/` only.

## Dataset Construction

The dataset is a CVE-based C repository patch porting dataset built from public sources:

1. **Collect**: Query NVD API for CVE entries with associated GitHub commits to C projects
2. **Expand**: Find additional commits via edit distance or commit message heuristics  
3. **Filter**: Keep only function-level changes; pair earliest vs. latest patches per CVE
4. **Split**: Temporal split at 2023-08-23 — before = fine-tuning, after = evaluation

**Scale guidance (reduced for a single benchmark run):**
- Full paper: 2,842 CVEs fine-tuning / 694 CVEs evaluation
- Acceptable subset: 50–200 CVEs for evaluation-only (zero-shot LLM baselines)
- Fine-tuning (LoRA on 13B model) requires GPU ≥48GB; skip if unavailable

**Example C projects:** Linux kernel, OpenSSL, libpng, curl, OpenBSD, FFmpeg

## System toolchain (auto-installed)

`seeds/container_setup.sh` is run as root by the generic `TaskSandbox.start()`
preflight when the script exists (controlled by `CONTAINER_SETUP=true` in `task.env`).

Installs via apt + pip3 (~60s):

- `gcc` / `g++` / `clang` / `build-essential`
- `git`, `patch`, `diffutils`
- Python: `requests`, `PyGithub`, `gitpython`, `transformers`, `nltk`, `sacrebleu`, `tree-sitter`, `openai`, `anthropic`
- NLTK data for BLEU scoring

Opt out: set `CONTAINER_SETUP=false` in `task.env`.

## Layout

| Path | Visible to agent? | Purpose |
|------|-------------------|---------|
| `agent/dataset_paths.json` | Yes | Dataset paths and construction instructions |
| `agent/metrics.json` | Yes | Required metrics keys |
| `requirements.txt` | No (pip only) | Python deps for orchestration |
| `container_setup.sh` | No (root setup) | Toolchain install |
| `benchmark_config.json` | No | Staging / benchmark rules |
| `README.md` | No | Human documentation |

## Baselines

- **GPT-3.5 / GPT-4o**: Zero-shot prompt-based porting (primary accessible baseline)
- **FixMorph**: Pattern-based patch porting (optional, build from source if time allows)
- **TSBPORT**: Semantic hunk types (optional, build from source if time allows)
- **PPatHF**: LLM-based function-level porting (optional)
- **CodeLlama 13B / StarCoder 15.5B**: Zero-shot or fine-tuned LLM (optional, GPU required)

## Metrics

| Metric | Description |
|--------|-------------|
| E-M (Exact Match) | Character-by-character identical to human-written fix |
| Succ (Success) | Semantically equivalent to human fix |
| Fail (Failure) | Not semantically equivalent |
| C-B (Code BLEU) | Token-level similarity for failed patches (0–1) |
