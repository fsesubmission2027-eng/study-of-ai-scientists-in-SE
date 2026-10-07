"""Bootstrap ARIS /research-pipeline for benchmark runs (parallel to evoscientist_workflow)."""

from __future__ import annotations

import re
from pathlib import Path

from agent_task_document import (
    build_agent_task_document,
)
from path_alignment import load_aligned_task_benchmark_config
from task_prompt import blind_task_label

# Unattended-run constraints for in-container `aris` single-shot launch.
BENCHMARK_ARIS_AUTONOMY_SECTION = """## Benchmark run mode

This is an unattended ai_scientist_benchmark run.
- Do not ask the user for choices or confirmation between steps; use reasonable defaults.
- Invoke ARIS skills via the Skill tool; follow `/research-pipeline` rather than improvising shortcuts."""


def _aris_pipeline_venue(venue: str) -> str:
    """Map task metadata venue to an ARIS `/research-pipeline` venue token."""
    token = re.sub(r"\s+\d{4}\b", "", venue.strip())
    upper = token.upper()
    if upper.startswith("ICSE") or upper.startswith("FSE") or upper.startswith("ASE"):
        return "IEEE_CONF"
    if upper.startswith("NEURIPS"):
        return "NeurIPS"
    if upper.startswith("ICML"):
        return "ICML"
    if upper.startswith("ICLR"):
        return "ICLR"
    if upper.startswith("CVPR"):
        return "CVPR"
    if upper.startswith("ACL"):
        return "ACL"
    if upper in {"IEEE", "IEEE_CONF", "IEEE_JOURNAL", "ACM"}:
        return upper.replace(" ", "_")
    return token or "IEEE_CONF"


def build_aris_research_brief(
    task_dir: Path,
    task_env: dict[str, str] | None = None,
) -> str:
    """Task + dataset brief consumed by `/research-pipeline`."""
    env = task_env if task_env is not None else {}
    cfg = load_aligned_task_benchmark_config(task_dir, env)
    body = build_agent_task_document(task_dir, env)
    return (
        f"# Research Brief — {blind_task_label(task_dir)}\n\n"
        "> Auto-generated from `task.md` for ARIS `/research-pipeline`.\n\n"
        f"{body.lstrip()}"
    )


def _benchmark_constraint_lines(cfg) -> list[str]:
    lines: list[str] = []
    for rule in cfg.benchmark_rules:
        lines.append(f"- {rule}")
    for key, value in (cfg.dataset_env or {}).items():
        lines.append(f"- `{key}={value}`")
    if cfg.non_goals:
        lines.append("- Non-goals:")
        for item in cfg.non_goals:
            lines.append(f"  - {item}")
    return lines


def build_aris_launch_prompt(
    task_dir: Path,
    task_env: dict[str, str] | None = None,
) -> str:
    """Thin orchestration prompt: invoke `/research-pipeline` with task context on disk."""
    env = task_env if task_env is not None else {}
    cfg = load_aligned_task_benchmark_config(task_dir, env)
    venue = _aris_pipeline_venue(cfg.venue)
    direction = cfg.research_direction.replace('"', "'")
    constraints = _benchmark_constraint_lines(cfg)
    constraint_block = "\n".join(constraints) if constraints else "- Follow `RESEARCH_BRIEF.md`."

    return "\n".join(
        [
            f"You are executing {blind_task_label(task_dir)} inside this workspace.",
            "",
            "1. Read `RESEARCH_BRIEF.md` and `CLAUDE.md` for task context.",
            "2. Start the native ARIS end-to-end workflow by **invoking skills** (Skill tool), "
            "not shortcuts. Use `/research-pipeline` as defined in "
            "`.claude/skills/research-pipeline/SKILL.md` (including its resumable-run "
            "conventions when applicable).",
            "3. Run autonomously until the pipeline completes or you are genuinely blocked:",
            "",
            (
                f'/research-pipeline "{direction}" — venue: {venue}, AUTO_WRITE: true, '
                "AUTO_PROCEED: true, human checkpoint: false, code review: true, "
                "ARXIV_DOWNLOAD: false, effort: balanced"
            ),
            "",
            "Benchmark constraints:",
            constraint_block,
            "- Use `/usr/bin/python3` for ARIS workflow utilities; "
            "use `./bin/python` only for experiment/runtime code when `./bin` exists.",
            "- Follow `dataset_candidate/metrics_schema.json` for results provenance.",
            "- Do not ask for confirmation between steps.",
            "- If interrupted, resume via the pipeline's native resume mechanism "
            "(see `.aris/runs/` and `/research-pipeline — resume <run_id>`).",
            "",
            BENCHMARK_ARIS_AUTONOMY_SECTION.strip(),
            "",
        ]
    )


def build_aris_resume_continuation_prompt(task_dir: Path, run_root: Path | None = None) -> str:
    """Continuation prompt after transient failure or manual --run-dir resume."""
    from metrics_schema import format_required_metrics_prompt_note_for_task
    from transient_retry import build_transient_continuation_prompt

    root = run_root or Path(".")
    run_id_hint = ""
    runs_dir = root / ".aris" / "runs"
    if runs_dir.is_dir():
        ids = sorted(p.stem for p in runs_dir.glob("*.json") if p.is_file())
        if ids:
            run_id_hint = (
                f"If `.aris/runs/` is trustworthy, prefer "
                f"`/research-pipeline — resume {ids[-1]}`; "
                "otherwise continue from on-disk artifacts without restarting long experiments."
            )
    hints = [
        "Read `RESEARCH_BRIEF.md` / `CLAUDE.md` and existing `idea-stage/`, `project/`, "
        "`experiment_results/`, `results/`, `review-stage/`, `paper/`.",
        "Prefer completing missing deliverables over re-running completed experiment campaigns.",
        "Copy or symlink `experiment_results/metrics.json` → `results/metrics.json` when needed.",
        "Then finish Stage 3–5: auto-review, NARRATIVE_REPORT.md, and paper writing "
        "(AUTO_WRITE / `/paper-writing`) as applicable.",
        format_required_metrics_prompt_note_for_task(task_dir, code_hint=False),
    ]
    if run_id_hint:
        hints.insert(0, run_id_hint)
    return build_transient_continuation_prompt(tool="aris", run_root=root, extra_hints=hints)
