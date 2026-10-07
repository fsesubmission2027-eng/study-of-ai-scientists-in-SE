"""Convert ai_scientist_inputs/task.md into an AI-Scientist-v2 idea JSON entry."""

from __future__ import annotations

import json
import re
from pathlib import Path

from agent_task_document import build_agent_task_document
from path_alignment import load_task_env
from task_prompt import load_task1_from_md


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:48] or "research_task"


def _extract_section(task_md: str, heading: str) -> str:
    pattern = rf"## {re.escape(heading)}\s*\n\n([\s\S]*?)(?=\n## |\Z)"
    match = re.search(pattern, task_md)
    return match.group(1).strip() if match else ""


def task_dir_to_idea(task_dir: Path) -> dict:
    task_env = load_task_env(task_dir)
    task_doc = build_agent_task_document(task_dir, task_env)
    blind_md = load_task1_from_md(task_dir)
    title_match = re.search(r"^# Task:\s*(.+)$", blind_md, flags=re.MULTILINE)
    title = title_match.group(1).strip() if title_match else "Research Task"

    background = _extract_section(blind_md, "Background")
    research_question = _extract_section(blind_md, "Research Question")

    return {
        "Name": _slugify(title),
        "Title": title,
        "Short Hypothesis": research_question or title,
        "Related Work": background or "See task background.",
        "Abstract": task_doc,
        "Experiments": ["Follow the task specification and dataset section in the Abstract."],
        "Risk Factors and Limitations": [
            "Task feasibility depends on dataset availability and the chosen methods.",
        ],
    }


def write_task_idea_files(task_dir: Path, run_dir: Path) -> tuple[Path, Path]:
    idea = task_dir_to_idea(task_dir)
    ideas = [idea]
    json_path = run_dir / "idea.json"
    md_path = run_dir / "idea_from_task.md"
    json_path.write_text(json.dumps(ideas, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(idea["Abstract"], encoding="utf-8")
    return json_path, md_path
