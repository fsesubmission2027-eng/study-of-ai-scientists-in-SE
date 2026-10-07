"""Prepare EvoScientist run directories from ai_scientist_inputs/task.md."""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from benchmark_task_config import load_task_benchmark_config
from path_alignment import (
    align_run_dataset_paths,
    load_aligned_task_benchmark_config,
    load_task_env,
)
from seed_staging import stage_seeds_for_agent
from agent_task_document import build_agent_task_document
from evoscientist_workflow import build_evoscientist_launch_prompt


def build_research_brief(task_dir: Path, task_env: dict[str, str] | None = None) -> str:
    return build_agent_task_document(task_dir, task_env)


def research_direction_from_task(task_dir: Path) -> str:
    return load_task_benchmark_config(task_dir).research_direction


def seed_run_workspace(run_root: Path, task_dir: Path, task_env: dict[str, str] | None = None) -> None:
    env = task_env if task_env is not None else load_task_env(task_dir)
    seeds = task_dir / "seeds"
    for sub in (
        "dataset_candidate",
        "project",
        "results",
        "paper",
        "artifacts",
    ):
        (run_root / sub).mkdir(parents=True, exist_ok=True)

    if seeds.is_dir():
        stage_seeds_for_agent(seeds, run_root / "dataset_candidate", task_env=env)


def write_evoscientist_config(
    run_root: Path,
    *,
    provider: str,
    model: str,
    api_key: str,
    base_url: str,
) -> Path:
    """Per-run isolated EvoScientist config (via XDG_CONFIG_HOME)."""
    config_home = run_root / ".xdg-config" / "evoscientist"
    config_home.mkdir(parents=True, exist_ok=True)
    (run_root / ".container-home").mkdir(parents=True, exist_ok=True)
    config_path = config_home / "config.yaml"
    lines = [
        f"provider: {provider}",
        f"model: {model}",
        "auto_mode: true",
        "auto_approve: true",
        "enable_ask_user: false",
        "enable_async_subagents: true",
        "ui_backend: cli",
        "show_thinking: false",
        "memory_workers_enabled: false",
        "dangerous_mode: true",
    ]
    if provider == "custom-openai":
        lines.extend(
            [
                f"custom_openai_api_key: {api_key}",
                f"custom_openai_base_url: {base_url}",
            ]
        )
    elif provider == "openai":
        lines.extend(
            [
                f"openai_api_key: {api_key}",
            ]
        )
    else:
        lines.append(f"custom_openai_api_key: {api_key}")
        lines.append(f"custom_openai_base_url: {base_url}")
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return config_path


def prepare_run_layout(
    task_dir: Path,
    *,
    run_dir: Path | None = None,
) -> tuple[Path, Path]:
    workspace_root = task_dir / "workspace"
    task_env = load_task_env(task_dir)
    if run_dir is not None:
        run_root = run_dir.resolve()
        run_root.mkdir(parents=True, exist_ok=True)
        # Refresh briefs without wiping experiment artifacts.
        task_input = build_agent_task_document(task_dir, task_env)
        (run_root / "task_input.md").write_text(task_input, encoding="utf-8")
        brief = build_research_brief(task_dir, task_env)
        (run_root / "RESEARCH_BRIEF.md").write_text(brief, encoding="utf-8")
        (run_root / "research_request.md").write_text(brief, encoding="utf-8")
        seed_run_workspace(run_root, task_dir, task_env)
        return run_root, workspace_root

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_root = workspace_root / f"evoscientist_{timestamp}"
    run_root.mkdir(parents=True, exist_ok=True)

    task_input = build_agent_task_document(task_dir, task_env)
    (run_root / "task_input.md").write_text(task_input, encoding="utf-8")
    (run_root / "RESEARCH_BRIEF.md").write_text(build_research_brief(task_dir, task_env), encoding="utf-8")
    (run_root / "research_request.md").write_text(build_research_brief(task_dir, task_env), encoding="utf-8")

    seed_run_workspace(run_root, task_dir, task_env)
    return run_root, workspace_root


def finalize_run_metadata(
    run_root: Path,
    *,
    returncode: int,
    container_id: str | None,
    docker_workdir: str | None,
    benchmark_complete: bool | None = None,
    benchmark_issues: list[str] | None = None,
    thread_id: str | None = None,
) -> Path:
    from run_metering import write_manifest_with_metering

    manifest = {
        "framework": "evoscientist",
        "run_dir": str(run_root),
        "returncode": returncode,
        "docker": {
            "container_id": container_id,
            "workdir": docker_workdir,
        },
        "thread_id": thread_id,
        "benchmark_complete": benchmark_complete,
        "benchmark_issues": benchmark_issues or [],
        "artifacts": collect_artifact_paths(run_root),
        "status": {
            "research_request": (run_root / "research_request.md").is_file(),
            "plan": (run_root / "todos.md").is_file() or (run_root / "plan.md").is_file(),
            "metrics": (run_root / "results" / "metrics.json").is_file(),
            "paper_tex": (run_root / "paper" / "main.tex").is_file(),
            "paper_pdf": (run_root / "paper" / "main.pdf").is_file(),
            "readme": (run_root / "README.md").is_file(),
        },
    }
    out = run_root / "artifacts" / "manifest.json"
    log_path = run_root / "evoscientist_run.log"
    return write_manifest_with_metering(
        out,
        manifest,
        run_root,
        log_path=log_path if log_path.is_file() else None,
    )


def _first_artifact(run_root: Path, *candidates: str) -> str:
    for name in candidates:
        if (run_root / name).is_file():
            return name
    return ""


def collect_artifact_paths(run_root: Path) -> dict[str, str | dict[str, str]]:
    code_files: dict[str, str] = {}
    project = run_root / "project"
    if project.is_dir():
        for path in sorted(project.rglob("*.py")):
            rel = path.relative_to(run_root).as_posix()
            code_files[rel] = rel

    paper_files: dict[str, str] = {}
    paper = run_root / "paper"
    if paper.is_dir():
        for path in sorted(paper.rglob("*")):
            if path.is_file():
                rel = path.relative_to(run_root).as_posix()
                paper_files[rel] = rel

    return {
        "research_brief": "RESEARCH_BRIEF.md",
        "task_input": "task_input.md",
        "research_request": "research_request.md",
        "plan": _first_artifact(run_root, "todos.md", "plan.md"),
        "metrics": "results/metrics.json" if (run_root / "results" / "metrics.json").is_file() else "",
        "readme": "README.md" if (run_root / "README.md").is_file() else "",
        "code": code_files,
        "paper": paper_files,
    }


def write_runtime_files(
    run_root: Path,
    task_dir: Path,
    *,
    docker_workdir: str,
    task_env: dict[str, str] | None = None,
) -> Path:
    del docker_workdir  # workdir is the run root; no extra agent-facing doc needed
    env = task_env if task_env is not None else load_task_env(task_dir)
    prompt = build_evoscientist_launch_prompt(task_dir, env)
    prompt_path = run_root / ".evoscientist-benchmark" / "launch_prompt.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt, encoding="utf-8")
    return prompt_path


def refresh_aligned_runtime_docs(
    run_root: Path,
    task_dir: Path,
    task_env: dict[str, str],
    *,
    docker_workdir: str,
) -> Path:
    """Re-align dataset paths and refresh task/dataset docs after container seeding."""
    del docker_workdir
    align_run_dataset_paths(run_root, task_env)
    brief = build_agent_task_document(task_dir, task_env)
    (run_root / "task_input.md").write_text(brief, encoding="utf-8")
    (run_root / "RESEARCH_BRIEF.md").write_text(brief, encoding="utf-8")
    (run_root / "research_request.md").write_text(brief, encoding="utf-8")
    return write_runtime_files(run_root, task_dir, docker_workdir=str(run_root), task_env=task_env)
