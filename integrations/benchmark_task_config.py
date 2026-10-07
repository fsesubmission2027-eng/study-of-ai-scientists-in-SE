"""Task-aware benchmark configuration parsed from ai_scientist_inputs task directories.

Single source of truth for task-specific rules:
  ``<task_dir>/seeds/benchmark_config.json``

This module only:
  1. Parses identity / RQ / metric names from ``task.md``
  2. Applies a generic default when seeds omit fields
  3. Overlays ``seeds/benchmark_config.json`` (and optional ``metrics.json``)
  4. Merges ``dataset_env`` from ``seeds/**/dataset_paths.json`` when present

Do **not** add per-task ``if task_id == ...`` branches here — put overrides in seeds.
Agent-facing dataset paths must be workspace-relative (``dataset_candidate/<name>/``),
never legacy ``/shared/...`` mount points (those stay in ``task.env`` only).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TaskBenchmarkConfig:
    task_id: str
    title: str
    venue: str
    research_direction: str
    pilot_data_note: str
    required_metrics: list[str] = field(default_factory=list)
    benchmark_rules: list[str] = field(default_factory=list)
    non_goals: list[str] = field(default_factory=list)
    dataset_env: dict[str, str] = field(default_factory=dict)


def _parse_task_id(task_dir: Path, task_md: str) -> str:
    folder = task_dir.name
    m = re.match(r"([A-Z]+-\d{4}-\d{3})", folder)
    if m:
        return m.group(1)
    title_m = re.search(r"^# Task:\s*([A-Z]+-\d{4}-\d{3})", task_md, re.M)
    if title_m:
        return title_m.group(1)
    return folder.split("_")[0]


def _parse_title(task_md: str) -> str:
    m = re.search(r"^# Task:\s*.+?—\s*(.+)$", task_md, re.M)
    return m.group(1).strip() if m else "Benchmark Task"


def _parse_venue(task_md: str) -> str:
    m = re.search(r"venue:\s*(\S+)", task_md, re.I)
    if m:
        return m.group(1).strip()
    return "IEEE_CONF"


def _parse_research_direction(task_md: str) -> str:
    rq = re.search(r"## Research Question\s*\n\n([\s\S]*?)\n\n## ", task_md)
    if rq:
        return rq.group(1).strip()
    return "Execute the benchmark research workflow autonomously."


def _parse_metric_names(task_md: str) -> list[str]:
    section = re.search(r"### Metrics\s*\n```\s*\n(.*?)\n```", task_md, re.S)
    if not section:
        return []
    names = re.findall(r"^- name:\s*(.+)$", section.group(1), re.M)
    return [_metric_key(name) for name in names]


def _metric_key(display_name: str) -> str:
    key = display_name.strip().lower()
    key = re.sub(r"[^a-z0-9]+", "_", key)
    return key.strip("_")


def _load_json_object(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _load_seeds_overrides(seeds_dir: Path) -> dict:
    for name in ("benchmark_config.json", "metrics.json"):
        data = _load_json_object(seeds_dir / name)
        if data:
            return data
    return {}


def _generic_config(
    task_id: str,
    title: str,
    venue: str,
    direction: str,
    metrics: list[str],
) -> TaskBenchmarkConfig:
    metric_keys = metrics or ["primary_metric"]
    return TaskBenchmarkConfig(
        task_id=task_id,
        title=title,
        venue=venue,
        research_direction=direction,
        pilot_data_note=(
            "Use files under `dataset_candidate/` (from task seeds / mounted datasets) "
            "for experiments. Do not invent synthetic data when real data is available."
        ),
        required_metrics=metric_keys[:3] if len(metric_keys) > 3 else metric_keys,
        benchmark_rules=[
            "Follow the task evaluation protocol; if blocked, document the blocker in workspace artifacts.",
        ],
        non_goals=[
            "Fabricating paper-scale results that were not executed",
        ],
    )


def _merge_dataset_env_from_paths(cfg: TaskBenchmarkConfig, task_dir: Path) -> None:
    """Fill dataset_env from seeds dataset_paths.json files (does not invent /shared paths)."""
    candidates = [
        task_dir / "seeds" / "dataset_paths.json",
        task_dir / "seeds" / "agent" / "dataset_paths.json",
    ]
    for path in candidates:
        data = _load_json_object(path)
        if not data:
            continue
        nested = data.get("dataset_env")
        if isinstance(nested, dict):
            for key, value in nested.items():
                cfg.dataset_env.setdefault(str(key), str(value))
        for key, value in data.items():
            if key.endswith("_env") and isinstance(value, dict):
                for env_key, env_val in value.items():
                    cfg.dataset_env.setdefault(str(env_key), str(env_val))


def load_task_benchmark_config(task_dir: Path) -> TaskBenchmarkConfig:
    task_md = (task_dir / "task.md").read_text(encoding="utf-8")
    task_id = _parse_task_id(task_dir, task_md)
    title = _parse_title(task_md)
    venue = _parse_venue(task_md)
    direction = _parse_research_direction(task_md)
    metrics = _parse_metric_names(task_md)

    cfg = _generic_config(task_id, title, venue, direction, metrics)

    seeds_overrides = _load_seeds_overrides(task_dir / "seeds")
    if seeds_overrides.get("required_metrics"):
        cfg.required_metrics = list(seeds_overrides["required_metrics"])
    if seeds_overrides.get("agent_data_note"):
        cfg.pilot_data_note = str(seeds_overrides["agent_data_note"])
    elif seeds_overrides.get("pilot_data_note"):
        cfg.pilot_data_note = str(seeds_overrides["pilot_data_note"])
    if seeds_overrides.get("benchmark_rules"):
        cfg.benchmark_rules = list(seeds_overrides["benchmark_rules"])
    if seeds_overrides.get("non_goals"):
        cfg.non_goals = list(seeds_overrides["non_goals"])
    if seeds_overrides.get("dataset_env"):
        cfg.dataset_env.update(
            {str(k): str(v) for k, v in seeds_overrides["dataset_env"].items()}
        )

    _merge_dataset_env_from_paths(cfg, task_dir)
    return cfg
