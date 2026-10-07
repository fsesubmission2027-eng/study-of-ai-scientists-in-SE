"""Build agent-facing prompts from ai_scientist_inputs/task.md."""

from __future__ import annotations

import re
from pathlib import Path

# paper_type values that may focus on reproduction / characterization.
_REPLICATION_OK_TYPES = frozenset(
    {
        "survey",
        "study",
        "empirical",
        "empirical-study",
        "case-study",
        "replication",
    }
)
# Constructive contribution types that must go beyond pure reproduction.
_INNOVATION_REQUIRED_TYPES = frozenset(
    {
        "tool",
        "technique",
        "method",
        "approach",
        "system",
        "framework",
        "dataset",
        "benchmark",
    }
)


def _strip_metadata_section(text: str) -> str:
    """Remove the Metadata block at the end of task.md."""
    return re.sub(
        r"\n## Metadata\s*\n```[\s\S]*?```\s*$",
        "",
        text,
        flags=re.MULTILINE,
    )


def _strip_feasibility_section(text: str) -> str:
    """Remove the Feasibility Notes block (benchmark-only, not for agents)."""
    return re.sub(
        r"\n## Feasibility Notes\s*\n[\s\S]*?(?=\n## |\Z)",
        "",
        text,
        flags=re.MULTILINE,
    )


def _generic_title(text: str) -> str:
    """Replace task id / venue in the H1 line with a generic title."""
    return re.sub(
        r"^# Task:\s*[A-Z]+-\d{4}-\d+\s*—\s*",
        "# Task: ",
        text,
        count=1,
        flags=re.MULTILINE,
    )


def strip_agent_excluded_sections(text: str) -> str:
    """Strip Metadata and Feasibility Notes before feeding task.md to agents."""
    cleaned = _strip_metadata_section(_strip_feasibility_section(text))
    return cleaned.rstrip() + "\n"


def sanitize_blind_text(text: str) -> str:
    """Remove venue/year tokens that reveal the target paper source."""
    text = re.sub(r"\bICSE-\d{4}-\d{3}\b", "benchmark task", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(?:ICSE|FSE|ASE|ISSTA)\s*2025\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b2025\b", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def blind_task_label(_task_dir: Path | None = None) -> str:
    """Generic label for agent-facing orchestration prompts."""
    return "benchmark task"


def load_paper_type(task_dir: Path) -> str | None:
    """Return paper_type from task.md Metadata (e.g. tool, empirical, survey)."""
    task_md = (task_dir / "task.md").read_text(encoding="utf-8")
    m = re.search(r"(?im)^\s*paper_type:\s*(\S+)\s*$", task_md)
    if not m:
        return None
    return m.group(1).strip().lower()


def paper_type_policy_bucket(paper_type: str | None) -> str:
    """Return 'replication_ok', 'innovation_required', or 'unknown'."""
    if not paper_type:
        return "unknown"
    token = paper_type.strip().lower()
    if token in _REPLICATION_OK_TYPES or any(k in token for k in ("survey", "study", "empirical")):
        return "replication_ok"
    if token in _INNOVATION_REQUIRED_TYPES or any(
        k in token for k in ("tool", "method", "technique", "system", "framework")
    ):
        return "innovation_required"
    return "unknown"


def load_task1_from_md(task_dir: Path) -> str:
    task_md = (task_dir / "task.md").read_text(encoding="utf-8")
    return sanitize_blind_text(_generic_title(strip_agent_excluded_sections(task_md)))


def load_research_question_from_md(task_dir: Path) -> str:
    """Research Question only — minimal ARC topic for literature stages."""
    task_md = (task_dir / "task.md").read_text(encoding="utf-8")
    rq = re.search(r"## Research Question\s*\n\n([\s\S]*?)\n\n## ", task_md)
    if not rq:
        raise ValueError(
            f"Could not parse Research Question from {task_dir / 'task.md'}"
        )
    return sanitize_blind_text(rq.group(1).strip() + "\n")


def load_task_background_rq_from_md(task_dir: Path) -> str:
    """Background + Research Question only — shorter ARC topic for literature stages."""
    task_md = (task_dir / "task.md").read_text(encoding="utf-8")
    bg = re.search(r"## Background\s*\n\n([\s\S]*?)\n\n## Research Question", task_md)
    rq = re.search(r"## Research Question\s*\n\n([\s\S]*?)\n\n## ", task_md)
    if not bg or not rq:
        raise ValueError(
            f"Could not parse Background / Research Question from {task_dir / 'task.md'}"
        )
    return sanitize_blind_text(
        "## Background\n\n"
        f"{bg.group(1).strip()}\n\n"
        "## Research Question\n\n"
        f"{rq.group(1).strip()}\n"
    )


def load_task2_from_md(task_dir: Path) -> str:
    task_md = strip_agent_excluded_sections(
        (task_dir / "task.md").read_text(encoding="utf-8")
    )
    bg = re.search(r"## Background\s*\n\n([\s\S]*?)\n\n## Research Question", task_md)
    rq = re.search(r"## Research Question\s*\n\n([\s\S]*?)\n\n## Experiment Setup", task_md)
    parts = []
    if bg:
        parts.append(bg.group(1).strip())
    if rq:
        parts.append(rq.group(1).strip())
    parts.append(
        "Propose and implement an approach that answers the research question above, "
        "using the provided dataset when available, and produce code, experiments, "
        "and a research write-up."
    )
    return "\n\n".join(parts) + "\n"
