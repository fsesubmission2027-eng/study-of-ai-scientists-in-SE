"""Split AI-Scientist task materials into ARC-native input channels.

ARC expects:
  - ``research.topic``: short research question (not a full brief)
  - ``research.domains``: literature / routing labels (SE for these tasks)
  - ``prompts.custom_file``: block/template overrides (esp. dataset_guidance)
  - ``prompts.extra_prompts.<stage>``: per-stage additional guidance files

This pack keeps the shared ``build_agent_task_document`` on disk as
``RESEARCH_BRIEF.md`` for humans / other tools, while feeding ARC in the
upstream-recommended shape.
"""

from __future__ import annotations

import re
from pathlib import Path

from agent_task_document import (
    BENCHMARK_DATASET_USAGE_SECTION,
    BENCHMARK_PERSIST_INTERMEDIATES_SECTION,
    BENCHMARK_TASK_TYPE_POLICY_SECTION,
    build_agent_task_document,
)
from path_alignment import load_aligned_task_benchmark_config
from task_prompt import (
    load_paper_type,
    load_research_question_from_md,
    load_task1_from_md,
    paper_type_policy_bucket,
)

# Stages that should see task background / experiment framing.
_SCOPING_STAGES = ("topic_init", "problem_decompose", "search_strategy")
# Stages that shape the research idea.
_IDEATION_STAGES = ("knowledge_extract", "synthesis", "hypothesis_gen")
# Stages that must obey dataset and experiment constraints.
_EXPERIMENT_STAGES = (
    "experiment_design",
    "code_generation",
    "resource_planning",
    "result_analysis",
)
# Stages that write the manuscript.
_WRITING_STAGES = ("paper_outline", "paper_draft", "paper_revision", "export_publish")


def _extract_section(task_md: str, heading: str) -> str:
    pattern = rf"## {re.escape(heading)}\s*\n\n([\s\S]*?)(?=\n## |\Z)"
    match = re.search(pattern, task_md)
    return match.group(1).strip() if match else ""


def _task_type_blurb(task_dir: Path) -> str:
    paper_type = load_paper_type(task_dir)
    bucket = paper_type_policy_bucket(paper_type)
    shown = paper_type or "unknown"
    if bucket == "replication_ok":
        hint = (
            "Policy class: **survey / study / empirical** — reproduction of closely "
            "related prior work is allowed when it answers the research questions."
        )
    elif bucket == "innovation_required":
        hint = (
            "Policy class: **tool / constructive** — pure reproduction is insufficient; "
            "propose and implement a non-trivial new contribution."
        )
    else:
        hint = (
            "Policy class: **unknown** — prefer a clear technical contribution beyond "
            "bare reproduction when in doubt."
        )
    return f"- `paper_type`: `{shown}`\n- {hint}"


def _dataset_section(task_dir: Path, task_env: dict[str, str]) -> str:
    cfg = load_aligned_task_benchmark_config(task_dir, task_env)
    lines = [
        "## Dataset (benchmark-provided)",
        "",
        f"- {cfg.pilot_data_note}",
    ]
    for key, value in (cfg.dataset_env or {}).items():
        lines.append(f"- `{key}={value}`")
    lines.append(
        "- Paths and layout: `dataset_candidate/dataset_paths.json`, "
        "`dataset_candidate/MOUNT_STATUS.json`"
    )
    lines.append(
        "- Inside ARC experiment Docker, large corpora are at "
        "`/workspace/data/<dataset_name>/` (read-only)."
    )
    return "\n".join(lines)


def build_scoping_extra(task_dir: Path, task_env: dict[str, str]) -> str:
    """Background + experiment setup for Stages 1–3."""
    task_md = load_task1_from_md(task_dir)
    background = _extract_section(task_md, "Background")
    experiment = _extract_section(task_md, "Experiment Setup")
    artifacts = _extract_section(task_md, "Expected Artifacts")
    parts = [
        "# Benchmark task context (not the research.topic)",
        "",
        "Use this for scoping and problem framing. The pipeline `research.topic` "
        "is only the Research Question — do not invent a different topic.",
        "",
        "## Task type",
        "",
        _task_type_blurb(task_dir),
        "",
    ]
    if background:
        parts.extend(["## Background", "", background, ""])
    if experiment:
        parts.extend(["## Experiment Setup", "", experiment, ""])
    parts.extend([_dataset_section(task_dir, task_env), ""])
    if artifacts:
        parts.extend(["## Expected Artifacts", "", artifacts, ""])
    return "\n".join(parts).rstrip() + "\n"


def build_ideation_extra(task_dir: Path, task_env: dict[str, str]) -> str:
    """Policy + dataset notes for synthesis / hypothesis stages."""
    return (
        "# Benchmark ideation constraints\n\n"
        "## Task type\n\n"
        f"{_task_type_blurb(task_dir)}\n\n"
        f"{BENCHMARK_TASK_TYPE_POLICY_SECTION.strip()}\n\n"
        f"{_dataset_section(task_dir, task_env)}\n\n"
        f"{BENCHMARK_DATASET_USAGE_SECTION.strip()}\n"
    )


def build_experiment_extra(task_dir: Path, task_env: dict[str, str]) -> str:
    """Hard dataset / implementation constraints for Stages 9–13."""
    task_md = load_task1_from_md(task_dir)
    experiment = _extract_section(task_md, "Experiment Setup")
    parts = [
        "# Benchmark experiment constraints",
        "",
        "## Task type",
        "",
        _task_type_blurb(task_dir),
        "",
        _dataset_section(task_dir, task_env),
        "",
        BENCHMARK_DATASET_USAGE_SECTION.strip(),
        "",
        "## Implementation rules",
        "",
        "- Emit a real runnable entrypoint: `main.py` must have "
        '`if __name__ == "__main__":` and orchestrate the experiment.',
        "- Do **not** leave `main.py` as a Config stub or a copy of `config.py`.",
        "- Prefer `/workspace/data/<name>/` (or `os.environ[*_HOME]`) for large data; "
        "small schemas may live under `experiment/data/`.",
        "- Do not invent alternate public corpora, synthetic tensors/CSVs, or "
        "`/data/oss-projects`-style placeholders when the mounted dataset exists.",
        "- Include `requirements.txt` when extra deps are needed; avoid naming "
        "files that shadow stdlib/pip packages (e.g. prefer `experiment_config.py` "
        "over `config.py` if imports collide).",
        "",
    ]
    if experiment:
        parts.extend(
            [
                "## Experiment Setup (from task)",
                "",
                experiment,
                "",
            ]
        )
    parts.append(BENCHMARK_PERSIST_INTERMEDIATES_SECTION.strip())
    return "\n".join(parts).rstrip() + "\n"


def build_writing_extra(task_dir: Path, task_env: dict[str, str]) -> str:
    """Short policy reminder for paper stages."""
    del task_env
    rq = load_research_question_from_md(task_dir).strip()
    return (
        "# Benchmark writing constraints\n\n"
        "## Research Question (must stay aligned)\n\n"
        f"{rq}\n\n"
        "## Task type\n\n"
        f"{_task_type_blurb(task_dir)}\n\n"
        f"{BENCHMARK_TASK_TYPE_POLICY_SECTION.strip()}\n\n"
        "Report only evidence-backed results from the executed experiments.\n"
    )


def build_custom_prompts_yaml_text(task_dir: Path, task_env: dict[str, str]) -> str:
    """Override ARC default ML dataset_guidance with mounted-corpus rules."""
    cfg = load_aligned_task_benchmark_config(task_dir, task_env)
    env_lines = []
    for key, value in (cfg.dataset_env or {}).items():
        env_lines.append(f"- `{key}` → workspace `{value}` and Docker `/workspace/data/`")
    env_block = "\n".join(env_lines) if env_lines else (
        "- Read `dataset_candidate/dataset_paths.json` for active mounts."
    )
    dataset_guidance = f"""## Benchmark-mounted datasets (MANDATORY when provided)

This run provides real corpora under the experiment Docker at
`/workspace/data/<dataset_name>/` (sourced from EXTRA_VOLUME_* / HOME cache mounts).
Workspace-relative access: `dataset_candidate/<name>/`.

Dataset note: {cfg.pilot_data_note}

Active env bindings:
{env_block}

Rules:
- You MUST load and analyze these real files when present.
- NEVER substitute synthetic `torch.randn` / random graphs / toy CSVs /
  invented HuggingFace downloads when the mounted dataset is readable.
- NEVER invent paths like `/data/oss-projects` or clone alternate public repos
  as stand-ins for the provided corpus.
- Prefer `/workspace/data/<name>/` inside Docker; use `os.environ[*_HOME]` when set.
- Read `experiment/data/dataset_paths.json` and `MOUNT_STATUS.json` when present.
- If a mount is missing or empty, document the blocker instead of silently
  fabricating data.

Do NOT default to CIFAR/MNIST/ImageNet unless this task's Dataset section
explicitly asks for them.
"""
    # literal block scalar so multiline guidance stays intact (4-space body)
    indented = "\n".join(
        ("    " + line) if line else "" for line in dataset_guidance.splitlines()
    )
    return (
        "# Auto-generated by ai_scientist_benchmark for AutoResearchClaw.\n"
        "# Overrides shared prompt blocks; does not replace stage templates.\n"
        "blocks:\n"
        "  dataset_guidance: |\n"
        f"{indented}\n"
    )


def write_researchclaw_prompt_pack(
    run_root: Path,
    task_dir: Path,
    task_env: dict[str, str],
) -> dict:
    """Write brief + prompt pack under *run_root*; return config prompt stanza.

    Returns a dict suitable for the ``prompts:`` section of ``config.arc.yaml``:
    ``{custom_file, extra_prompts}`` with absolute paths so ARC can resolve them
    regardless of CWD.
    """
    prompts_dir = run_root / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)

    brief = build_agent_task_document(task_dir, task_env)
    (run_root / "RESEARCH_BRIEF.md").write_text(brief, encoding="utf-8")

    scoping = prompts_dir / "extra_scoping.md"
    ideation = prompts_dir / "extra_ideation.md"
    experiment = prompts_dir / "extra_experiment.md"
    writing = prompts_dir / "extra_writing.md"
    custom = prompts_dir / "custom.benchmark.yaml"

    scoping.write_text(build_scoping_extra(task_dir, task_env), encoding="utf-8")
    ideation.write_text(build_ideation_extra(task_dir, task_env), encoding="utf-8")
    experiment.write_text(build_experiment_extra(task_dir, task_env), encoding="utf-8")
    writing.write_text(build_writing_extra(task_dir, task_env), encoding="utf-8")
    custom.write_text(
        build_custom_prompts_yaml_text(task_dir, task_env),
        encoding="utf-8",
    )

    extra: dict[str, str] = {}
    for stage in _SCOPING_STAGES:
        extra[stage] = str(scoping.resolve())
    for stage in _IDEATION_STAGES:
        extra[stage] = str(ideation.resolve())
    for stage in _EXPERIMENT_STAGES:
        extra[stage] = str(experiment.resolve())
    for stage in _WRITING_STAGES:
        extra[stage] = str(writing.resolve())

    return {
        "custom_file": str(custom.resolve()),
        "extra_prompts": extra,
    }


def resolve_research_domains(task_dir: Path | None = None) -> list[str]:
    """Benchmark SE tasks → software-engineering domain label for ARC."""
    del task_dir
    return ["software-engineering"]
