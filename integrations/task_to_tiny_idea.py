"""Convert ai_scientist_inputs/task.md into a TinyScientist idea dict."""

from __future__ import annotations

import json
import re
from pathlib import Path

from agent_task_document import build_agent_task_document
from path_alignment import load_aligned_task_benchmark_config, load_task_env
from task_prompt import load_task1_from_md
from task_to_idea import _extract_section, task_dir_to_idea


def _parse_block_items(block: str, field: str) -> list[str]:
    pattern = rf"- {re.escape(field)}:\s*(.+)"
    return [match.strip() for match in re.findall(pattern, block)]


def _extract_subsection(task_md: str, heading: str) -> str:
    pattern = rf"### {re.escape(heading)}\s*\n```?\n?([\s\S]*?)```?(?=\n### |\n## |\Z)"
    match = re.search(pattern, task_md)
    if match:
        return match.group(1).strip()
    return _extract_section(task_md, heading)


def task_dir_to_tiny_idea(task_dir: Path, *, workspace_rel: str = ".") -> dict:
    """Map benchmark task.md to TinyScientist fields used by Coder/Writer."""
    task_env = load_task_env(task_dir)
    cfg = load_aligned_task_benchmark_config(task_dir, task_env)
    base = task_dir_to_idea(task_dir)
    blind_md = load_task1_from_md(task_dir)
    task_doc = build_agent_task_document(task_dir, task_env)

    research_question = _extract_section(blind_md, "Research Question")
    metrics_block = _extract_subsection(blind_md, "Metrics")
    metric_names = _parse_block_items(metrics_block, "name")

    dataset_home = next(iter((cfg.dataset_env or {}).values()), "dataset_candidate")
    approach = task_doc.strip()

    experiment = {
        "Name": base["Name"],
        "Title": base["Title"],
        "Short Hypothesis": research_question or base["Title"],
        "Abstract": task_doc,
        "Description": approach,
        "Dataset": cfg.pilot_data_note,
        "Metric": ", ".join(metric_names) if metric_names else "See task metrics",
        "Baselines": "See task Experiment Setup",
        "Model": "Use methods appropriate to the task and dataset.",
        "MetricKeys": (
            ", ".join(name.strip().lower().replace(" ", "_") for name in metric_names)
            if metric_names
            else "task_metrics"
        ),
        "Workspace": workspace_rel,
        "DatasetHome": dataset_home,
    }
    return experiment


def write_tiny_idea_files(task_dir: Path, run_dir: Path) -> tuple[Path, Path]:
    idea = task_dir_to_tiny_idea(task_dir, workspace_rel=".")
    json_path = run_dir / "idea.json"
    md_path = run_dir / "idea.md"
    json_path.write_text(json.dumps(idea, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    md_path.write_text(idea["Abstract"], encoding="utf-8")
    return json_path, md_path
