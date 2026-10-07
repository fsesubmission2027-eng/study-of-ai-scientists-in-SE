"""Canonical agent-facing task prompt for all ai_scientist_benchmark tools.

``build_agent_task_document`` is the single shared input used (or mirrored) by
ResearchClaw, AI-Scientist, TinyScientist, DeepScientist, EvoScientist, ARIS,
and AI-Researcher. It combines sanitized ``task.md`` with dataset paths,
mandatory real-dataset usage, task-type novelty policy, and end-to-end
completion requirements.
"""

from __future__ import annotations

from pathlib import Path

from benchmark_task_config import load_task_benchmark_config
from path_alignment import load_aligned_task_benchmark_config, load_task_env
from task_prompt import load_paper_type, load_task1_from_md, paper_type_policy_bucket

# Shared across all benchmark agent tools (EvoScientist, ARIS, DeepScientist, etc.).
BENCHMARK_FULL_RESEARCH_WORKFLOW_SECTION = """## Benchmark completion requirement

Complete an **end-to-end** scientific research run for this task in this workspace. At minimum you must finish (and persist artifacts for) all of the following — your tool may use different stage names, and you may add extra modules, but you must **not** skip any of these outcomes:

1. **Literature search & synthesis** — retrieve and review relevant prior work (open search is allowed; do not invent citations).
2. **Idea / hypothesis generation** — produce a concrete research idea that addresses the research questions (see task-type policy below for how much novelty is required).
3. **Implementation** — write working code for the method, analysis, or tooling described by the idea.
4. **Experiments** — run the experiments on complete real data when a dataset is provided (see Dataset); record metrics and logs.
5. **Paper / research write-up** — produce a manuscript-style write-up (markdown and/or LaTeX) that covers motivation, method, experiments, and results.

Additional requirements:
- Do **not** end after planning, scoping, or status narration alone; continue until the process above is finished or you are genuinely blocked.
- Follow your tool's native end-to-end workflow; do not improvise a shortcut that skips literature, ideation, coding, experiments, or writing unless you are blocked.
- Report only evidence-backed results; if blocked, document the blocker and remaining work in persisted workspace artifacts."""

BENCHMARK_TASK_TYPE_POLICY_SECTION = """## Task-type policy (novelty vs reproduction)

Use the **Task type** value above (from the benchmark metadata `paper_type`). If Task type is unknown, infer from the research questions and expected artifacts.

### Survey / study / empirical tasks
If the task type is **survey**, **study**, **empirical**, or similar characterization work:
- Faithful reproduction or carefully scoped re-analysis of closely related prior papers is **allowed** when it answers the stated research questions.
- You may reimplement published methods and re-run analyses on the provided or stated datasets.
- Still complete literature search, a clear idea/plan, working code, experiments, and a write-up — reproduction is a valid idea when it matches the task.

### Tool / method / system tasks
If the task type is **tool**, **technique**, **method**, **system**, **framework**, or similar constructive work:
- Do **not** stop at reproducing an existing paper's method and results.
- You must propose and implement a **non-trivial contribution** beyond a plain reimplementation — e.g. a new idea, method, algorithm, tooling capability, evaluation protocol, or substantial improvement over prior work — and demonstrate it with code and experiments.
- Literature and baselines remain required; novelty must show up in the idea, implementation, and experimental story.

### Dataset / benchmark tasks
If the task type is **dataset** or **benchmark**, treat it like constructive work: delivering only a reproduction of someone else's release is insufficient; contribute a clear dataset/benchmark artifact or protocol improvement as stated by the task."""

BENCHMARK_DATASET_USAGE_SECTION = """## Dataset usage (mandatory when provided)

- If this task provides datasets (see **Dataset** below, `dataset_candidate/`, `EXTRA_VOLUME_*` mounts, or env vars such as `PAIRSMELL_HOME` / `DEFECTS4J_HOME`), you **must use those complete real provided datasets** for experiments.
- Do **not** invent substitute CSVs, synthetic toy data, or alternate public corpora when the provided dataset is available and readable.
- Prefer paths under `dataset_candidate/<name>/` for file tools, and (when your executor mounts large corpora there) `/workspace/data/<name>/` inside experiment containers.
- Read `dataset_candidate/dataset_paths.json` and `dataset_candidate/MOUNT_STATUS.json` when present. If a dataset mount is missing or empty, document the blocker instead of silently switching to fabricated data."""

BENCHMARK_PERSIST_INTERMEDIATES_SECTION = """## Persist all intermediate artifacts (mandatory)

Every step of your tool's native research workflow must leave **durable artifacts on disk** in this workspace before you advance — not only in session UI, chat memory, or ephemeral in-session task lists.

- Use your tool's normal file-writing mechanisms; in-session-only state does not satisfy this requirement.
- Persist the kinds of intermediate outputs your tool would normally produce across a full run (literature synthesis, ideation, experiment design and execution logs, code, measurements, analysis, review notes, writing drafts, and similar).
- Update persisted artifacts as work progresses so a human or a resumed run can continue from disk without re-deriving prior decisions."""

BENCHMARK_RESUME_CONTINUATION_BRIEF = (
    "Continue this benchmark run autonomously from where you stopped. "
    "Complete the full scientific research process for this task (see the launch brief), "
    "including literature search, idea generation, coding, experiments, and paper writing; "
    "do not stop at planning or status updates alone. "
    "Use reasonable defaults and do not ask for confirmation."
)


def _task_type_section(task_dir: Path) -> str:
    paper_type = load_paper_type(task_dir)
    bucket = paper_type_policy_bucket(paper_type)
    shown = paper_type or "unknown"
    if bucket == "replication_ok":
        hint = (
            "Policy class: **survey / study / empirical** — reproduction of closely related "
            "prior work is allowed when it answers the research questions."
        )
    elif bucket == "innovation_required":
        hint = (
            "Policy class: **tool / constructive** — pure reproduction is insufficient; "
            "propose and implement a non-trivial new contribution."
        )
    else:
        hint = (
            "Policy class: **unknown** — infer from the research questions; when in doubt, "
            "prefer a clear technical contribution beyond bare reproduction."
        )
    return (
        "## Task type\n\n"
        f"- `paper_type`: `{shown}`\n"
        f"- {hint}"
    )


def build_agent_task_document(
    task_dir: Path,
    task_env: dict[str, str] | None = None,
    *,
    extra_sections: list[str] | None = None,
) -> str:
    """Canonical task prompt: task.md + dataset + novelty policy + E2E workflow.

    All benchmark tool integrations should feed this document (or a thin
    tool-specific wrapper that includes it verbatim) into the agent.
    """
    env = task_env if task_env is not None else load_task_env(task_dir)
    cfg = load_aligned_task_benchmark_config(task_dir, env)
    task_md = load_task1_from_md(task_dir)
    lines = [
        task_md.strip(),
        "",
        _task_type_section(task_dir).strip(),
        "",
        "## Dataset",
        "",
        f"- {cfg.pilot_data_note}",
    ]
    for key, value in (cfg.dataset_env or {}).items():
        lines.append(f"- `{key}={value}`")
    lines.append(
        "- Paths and layout: `dataset_candidate/dataset_paths.json`, "
        "`dataset_candidate/MOUNT_STATUS.json`"
    )
    lines.extend(
        [
            "",
            BENCHMARK_DATASET_USAGE_SECTION.strip(),
            "",
            BENCHMARK_TASK_TYPE_POLICY_SECTION.strip(),
            "",
            BENCHMARK_FULL_RESEARCH_WORKFLOW_SECTION.strip(),
            "",
            BENCHMARK_PERSIST_INTERMEDIATES_SECTION.strip(),
        ]
    )
    for section in extra_sections or []:
        section = section.strip()
        if section:
            lines.extend(["", section])
    return "\n".join(lines) + "\n"


def canonical_agent_prompt(
    task_dir: Path,
    task_env: dict[str, str] | None = None,
    *,
    extra_sections: list[str] | None = None,
) -> str:
    """Alias for :func:`build_agent_task_document` (shared entry point name)."""
    return build_agent_task_document(
        task_dir, task_env, extra_sections=extra_sections
    )


def task_title_and_goal(task_dir: Path) -> tuple[str, str]:
    cfg = load_task_benchmark_config(task_dir)
    return cfg.title, cfg.research_direction


def build_runtime_workdir_note(*, workdir: str) -> str:
    return f"- Working directory: `{workdir}`\n"
