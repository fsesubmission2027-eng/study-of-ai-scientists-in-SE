"""Prepare AI-Researcher run directories from ai_scientist_inputs/task.md."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from agent_task_document import build_agent_task_document
from airesearcher_literature_seed import (
    load_source_papers_for_task,
    warp_source_papers,
    write_source_papers_json,
)
from path_alignment import align_run_dataset_paths, load_task_env
from researchclaw_literature_seed import RelatedWorkError
from seed_staging import stage_seeds_for_agent
from task_prompt import load_task1_from_md, load_task_background_rq_from_md


def _slug_instance_id(task_dir: Path) -> str:
    name = task_dir.name
    # ASE-2025-013_automated_... → ase_2025_013
    m = re.match(r"^([A-Za-z]+)-(\d{4})-(\d+)", name)
    if m:
        return f"{m.group(1).lower()}_{m.group(2)}_{int(m.group(3)):03d}"
    slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    return slug[:64] or "benchmark_task"


def _task_target(task_dir: Path) -> str:
    meta = task_dir / "metadata.json"
    if meta.is_file():
        try:
            data = json.loads(meta.read_text(encoding="utf-8"))
            for key in ("task_title", "title", "paper_title"):
                val = data.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
        except json.JSONDecodeError:
            pass
    task_md = (task_dir / "task.md").read_text(encoding="utf-8")
    m = re.search(r"^#\s+Task:\s*(.+)$", task_md, flags=re.MULTILINE)
    if m:
        return re.sub(r"^[A-Z]+-\d{4}-\d+\s*—\s*", "", m.group(1)).strip()
    return task_dir.name


def _task_url(task_dir: Path) -> str:
    meta = task_dir / "metadata.json"
    if not meta.is_file():
        return ""
    try:
        data = json.loads(meta.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return ""
    for key in ("paper_url", "pdf_url", "url"):
        val = data.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    return ""


def build_task2_prompt(task_dir: Path) -> str:
    """Background + RQ + a generic implementation ask (not task-specific boilerplate)."""
    try:
        body = load_task_background_rq_from_md(task_dir).strip()
    except ValueError:
        body = load_task1_from_md(task_dir).strip()
    ask = (
        "Propose and implement an approach that answers the research question above, "
        "using the provided dataset when available, and produce code, experiments, "
        "and a research write-up."
    )
    return f"{body}\n\n{ask}\n"


def build_research_brief(task_dir: Path, task_env: dict[str, str] | None = None) -> str:
    return build_agent_task_document(task_dir, task_env)


def seed_run_workspace(
    run_root: Path,
    task_dir: Path,
    task_env: dict[str, str] | None = None,
) -> None:
    env = task_env if task_env is not None else load_task_env(task_dir)
    seeds = task_dir / "seeds"
    for sub in (
        "dataset_candidate",
        "project",
        "results",
        "paper",
        "artifacts",
        "downloads",
        ".container-home",
        ".container-home/.cache",
        ".xdg-config",
    ):
        (run_root / sub).mkdir(parents=True, exist_ok=True)

    if seeds.is_dir():
        stage_seeds_for_agent(seeds, run_root / "dataset_candidate", task_env=env)
    align_run_dataset_paths(run_root, env)


def container_home_for_run(run_root: Path) -> Path:
    home = run_root / ".container-home"
    home.mkdir(parents=True, exist_ok=True)
    (home / ".cache").mkdir(parents=True, exist_ok=True)
    return home


def apply_writable_home_env(run_root: Path, env: dict[str, str] | None = None) -> dict[str, str]:
    """Point HOME/XDG_* at the per-run writable tree (host home is not fully mounted)."""
    target = env if env is not None else os.environ
    home = container_home_for_run(run_root)
    xdg_config = run_root / ".xdg-config"
    xdg_config.mkdir(parents=True, exist_ok=True)
    target["HOME"] = str(home)
    target["XDG_CACHE_HOME"] = str(home / ".cache")
    target["XDG_CONFIG_HOME"] = str(xdg_config)
    # Playwright browsers live in the host cache (mounted into the sandbox).
    playwright_browsers = Path.home() / ".cache" / "ms-playwright"
    if playwright_browsers.is_dir():
        target["PLAYWRIGHT_BROWSERS_PATH"] = str(playwright_browsers)
    return target


def synthesize_instance(
    task_dir: Path,
    *,
    task_env: dict[str, str] | None = None,
    related_work_path: Path | None = None,
    instance_id: str | None = None,
    category: str = "benchmark",
    max_papers: int | None = None,
) -> tuple[dict[str, Any], list[str]]:
    """Build an AI-Researcher instance dict from task.md + related_work.json."""
    env = task_env if task_env is not None else load_task_env(task_dir)
    del env  # reserved for future path-aligned task text
    warnings: list[str] = []

    try:
        source_papers, src, lit_warnings = load_source_papers_for_task(
            task_dir,
            related_work_path=related_work_path,
            max_papers=max_papers,
        )
        warnings.extend(lit_warnings)
        if src is not None:
            warnings.append(f"source_papers seeded from {src}")
    except RelatedWorkError as exc:
        # Allow empty literature only if caller later supplies --instance-json.
        source_papers = []
        warnings.append(f"literature seed skipped: {exc}")

    iid = instance_id or _slug_instance_id(task_dir)
    task1 = build_research_brief(task_dir, task_env)
    task2 = build_task2_prompt(task_dir)
    instance = {
        "target": _task_target(task_dir),
        "instance_id": iid,
        "category": category,
        "authors": [],
        "year": datetime.now().year,
        "url": _task_url(task_dir),
        "abstract": "",
        "source_papers": source_papers,
        "task1": task1,
        "task2": task2,
        "benchmark_task_dir": str(task_dir.resolve()),
    }
    return instance, warnings


def write_instance_files(
    run_root: Path,
    instance: dict[str, Any],
) -> tuple[Path, Path]:
    """Write instance JSON + warped references string under the run root."""
    bench = run_root / ".airesearcher-benchmark"
    bench.mkdir(parents=True, exist_ok=True)
    instance_path = bench / "instance.json"
    instance_path.write_text(
        json.dumps(instance, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    papers = list(instance.get("source_papers") or [])
    write_source_papers_json(bench / "source_papers.json", papers)
    refs_path = bench / "references.txt"
    refs_path.write_text(warp_source_papers(papers) + ("\n" if papers else ""), encoding="utf-8")
    return instance_path, refs_path


def prepare_run_layout(
    task_dir: Path,
    *,
    run_dir: Path | None = None,
    related_work_path: Path | None = None,
    instance_id: str | None = None,
    category: str = "benchmark",
    require_literature: bool = True,
) -> tuple[Path, Path, Path, list[str]]:
    """Create ``workspace/airesearcher_<ts>/`` (or refresh ``--run-dir``).

    Returns ``(run_root, workspace_root, instance_path, warnings)``.
    """
    workspace_root = task_dir / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    task_env = load_task_env(task_dir)
    warnings: list[str] = []

    if run_dir is not None:
        run_root = run_dir.resolve()
        run_root.mkdir(parents=True, exist_ok=True)
    else:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        run_root = workspace_root / f"airesearcher_{timestamp}"
        run_root.mkdir(parents=True, exist_ok=True)

    brief = build_research_brief(task_dir, task_env)
    (run_root / "RESEARCH_BRIEF.md").write_text(brief, encoding="utf-8")
    (run_root / "task_input.md").write_text(brief, encoding="utf-8")
    seed_run_workspace(run_root, task_dir, task_env)

    instance, synth_warnings = synthesize_instance(
        task_dir,
        task_env=task_env,
        related_work_path=related_work_path,
        instance_id=instance_id,
        category=category,
    )
    warnings.extend(synth_warnings)
    if require_literature and not instance.get("source_papers"):
        raise RelatedWorkError(
            f"No source_papers available for {task_dir}. "
            "Provide related_work.json or pass an existing AI-Researcher instance via --instance-json."
        )
    instance_path, _refs = write_instance_files(run_root, instance)
    return run_root, workspace_root, instance_path, warnings


def collect_artifact_paths(run_root: Path) -> dict[str, bool]:
    return {
        "research_brief": (run_root / "RESEARCH_BRIEF.md").is_file(),
        "instance": (run_root / ".airesearcher-benchmark" / "instance.json").is_file(),
        "source_papers": (run_root / ".airesearcher-benchmark" / "source_papers.json").is_file(),
        "metrics": (run_root / "results" / "metrics.json").is_file(),
        "project": (run_root / "project").is_dir()
        and any((run_root / "project").iterdir()),
        "paper": (run_root / "paper").is_dir() and any((run_root / "paper").iterdir()),
    }


def finalize_run_metadata(
    run_root: Path,
    *,
    returncode: int,
    container_id: str | None = None,
    docker_workdir: str | None = None,
    instance_path: Path | None = None,
    log_path: Path | None = None,
) -> Path:
    from run_metering import write_manifest_with_metering

    artifacts = collect_artifact_paths(run_root)
    manifest = {
        "framework": "airesearcher",
        "run_dir": str(run_root),
        "returncode": returncode,
        "docker": {
            "container_id": container_id,
            "workdir": docker_workdir,
        },
        "instance_path": str(instance_path) if instance_path else None,
        "artifacts": artifacts,
        "status": {
            "pipeline": returncode == 0,
            **artifacts,
        },
    }
    return write_manifest_with_metering(
        run_root / "artifacts" / "manifest.json",
        manifest,
        run_root,
        log_path=log_path if log_path and log_path.is_file() else None,
    )
