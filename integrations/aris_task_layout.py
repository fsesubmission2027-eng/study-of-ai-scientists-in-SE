"""Prepare ARIS run directories from ai_scientist_inputs/task.md."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

from aris_workflow import build_aris_launch_prompt, build_aris_research_brief
from benchmark_task_config import load_task_benchmark_config
from path_alignment import (
    align_run_dataset_paths,
    load_aligned_task_benchmark_config,
    load_task_env,
)
from seed_staging import stage_seeds_for_agent
from agent_task_document import build_agent_task_document

MIN_REVIEW_SCORE = 6
METRICS_GENERATED_BY = "experiment_runner.py"
EXPERIMENT_RUNNER_CMD = "python3 project/experiment_runner.py"

# Prefer the canonical ARIS path, then other common agent write locations.
METRICS_PATH_CANDIDATES = (
    "results/metrics.json",
    "experiment_results/metrics.json",
    "project/metrics.json",
    "artifacts/results/metrics.json",
)

FABRICATION_LOG_PATTERNS = (
    r"realistic experiment results",
    r"create the metrics\.json with realistic",
    r"update the metrics\.json.*address.*review",
    r"update the metrics\.json with (the )?expanded",
)

METRICS_HAND_WRITE_LOG_PATTERN = re.compile(
    r"write_file[^\n]*(?:results|project|experiment_results)/metrics\.json|"
    r"(?:Updated|Wrote|Writing)[^\n]*(?:results|project|experiment_results)/metrics\.json",
    re.I,
)

EXPERIMENT_RUNNER_CHANGE_PATTERN = re.compile(
    r"(?:write_file|edit_file|Edited|Wrote|Updated)[^\n]*experiment_runner\.py",
    re.I,
)

# Agent UI often truncates the bash command line; also accept run banners / save lines.
EXPERIMENT_RUN_PATTERN = re.compile(
    r"python3?\b[^\n]*experiment_runner\.py|"
    r"Results written to \S*metrics\.json|"
    r"Metrics:\s*\S*metrics\.json|"
    r"\[5/5\]\s*Saving results|"
    r"RESULTS SUMMARY|"
    r"Experiment Runner",
    re.I,
)


def build_research_brief(task_dir: Path, task_env: dict[str, str] | None = None) -> str:
    return build_aris_research_brief(task_dir, task_env)


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
        "review-stage",
        "idea-stage",
        "refine-logs",
    ):
        (run_root / sub).mkdir(parents=True, exist_ok=True)

    if seeds.is_dir():
        stage_seeds_for_agent(seeds, run_root / "dataset_candidate", task_env=env)

    cfg = load_aligned_task_benchmark_config(task_dir, env)
    schema = {
        "required_top_level_metrics": cfg.required_metrics,
        "required_provenance": {
            "generated_by": METRICS_GENERATED_BY,
            "experiment_command": EXPERIMENT_RUNNER_CMD,
        },
        "forbidden": (
            "Do not hand-edit results/metrics.json. "
            "Only experiment_runner.py may write it after a full python3 run."
        ),
    }
    (run_root / "dataset_candidate" / "metrics_schema.json").write_text(
        json.dumps(schema, indent=2) + "\n",
        encoding="utf-8",
    )


def install_aris_skills(run_root: Path, aris_repo: Path) -> None:
    installer = aris_repo / "tools" / "install_aris.sh"
    if not installer.is_file():
        raise FileNotFoundError(f"Missing ARIS installer: {installer}")
    proc = subprocess.run(
        ["bash", str(installer), str(run_root), "--quiet"],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "install_aris.sh failed:\n"
            f"stdout={proc.stdout.strip()}\n"
            f"stderr={proc.stderr.strip()}"
        )


def prepare_run_layout(
    task_dir: Path,
    *,
    aris_repo: Path,
    install_skills: bool = True,
    run_dir: Path | None = None,
) -> tuple[Path, Path]:
    workspace_root = task_dir / "workspace"
    task_env = load_task_env(task_dir)
    if run_dir is not None:
        run_root = run_dir.resolve()
        run_root.mkdir(parents=True, exist_ok=True)
        # Refresh briefs without wiping existing experiment artifacts.
        task_input = build_agent_task_document(task_dir, task_env)
        (run_root / "task_input.md").write_text(task_input, encoding="utf-8")
        (run_root / "RESEARCH_BRIEF.md").write_text(
            build_research_brief(task_dir, task_env), encoding="utf-8"
        )
        seed_run_workspace(run_root, task_dir, task_env)
        if install_skills and not (run_root / ".claude" / "skills").exists():
            install_aris_skills(run_root, aris_repo)
        return run_root, workspace_root

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_root = workspace_root / f"aris_{timestamp}"
    run_root.mkdir(parents=True, exist_ok=True)

    task_input = build_agent_task_document(task_dir, task_env)
    (run_root / "task_input.md").write_text(task_input, encoding="utf-8")
    (run_root / "RESEARCH_BRIEF.md").write_text(build_research_brief(task_dir, task_env), encoding="utf-8")

    seed_run_workspace(run_root, task_dir, task_env)

    if install_skills:
        install_aris_skills(run_root, aris_repo)

    return run_root, workspace_root


def _max_review_score(run_root: Path) -> int | None:
    scores: list[int] = []
    candidates = [
        run_root / "review-stage" / "AUTO_REVIEW.md",
        run_root / "AUTO_REVIEW.md",
        run_root / "aris_run.log",
    ]
    patterns = (
        r"Score\s*\**\s*[:=]\s*\**\s*(\d+)\s*/\s*10",
        r"score\s*[=:]\s*(\d+)\s*/\s*10",
        r"final score:\s*(\d+)\s*/\s*10",
        r"\*\*Score\*\*\s*:\s*(\d+)\s*/\s*10",
    )
    for path in candidates:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in patterns:
            scores.extend(int(match) for match in re.findall(pattern, text, flags=re.I))
    return max(scores) if scores else None


def _read_run_log(run_root: Path) -> str:
    log_path = run_root / "aris_run.log"
    if not log_path.is_file():
        return ""
    return log_path.read_text(encoding="utf-8", errors="replace")


def find_metrics_path(run_root: Path) -> Path | None:
    """Return the first existing metrics file among generic ARIS candidates."""
    for rel in METRICS_PATH_CANDIDATES:
        path = run_root / rel
        if path.is_file():
            return path
    return None


def _json_has_metric_key(data: object, key: str) -> bool:
    """True if ``key`` (or a known alias) appears anywhere with a non-null value."""
    from metrics_schema import aliases_for_metric

    wanted = {alias.lower() for alias in aliases_for_metric(key)}
    # Common nesting: F1 vs f1_score, Recall vs recall.
    wanted.update(
        {
            key.lower().replace("_score", ""),
            key.lower().replace("_", ""),
        }
    )

    def walk(node: object) -> bool:
        if isinstance(node, dict):
            for k, v in node.items():
                if str(k).lower() in wanted and v is not None:
                    return True
                if walk(v):
                    return True
        elif isinstance(node, list):
            return any(walk(item) for item in node)
        return False

    return walk(data)


def _validate_metrics_provenance(data: dict, *, metrics_rel: str) -> list[str]:
    issues: list[str] = []
    generated_by = data.get("generated_by")
    if generated_by != METRICS_GENERATED_BY:
        issues.append(
            f'{metrics_rel} must set generated_by="{METRICS_GENERATED_BY}" '
            "(only experiment_runner.py may write metrics after a full run)"
        )
    command = str(data.get("experiment_command") or "")
    if "experiment_runner" not in command:
        issues.append(
            f"{metrics_rel} missing experiment_command referencing experiment_runner.py"
        )
    return issues


def _validate_experiment_integrity_from_log(log_text: str) -> list[str]:
    issues: list[str] = []
    if not log_text.strip():
        return issues

    for pattern in FABRICATION_LOG_PATTERNS:
        if re.search(pattern, log_text, flags=re.I):
            issues.append(
                "aris_run.log indicates hand-authored or fabricated metrics (forbidden phrasing detected)"
            )
            break

    if METRICS_HAND_WRITE_LOG_PATTERN.search(log_text):
        issues.append(
            "metrics.json was written via agent write_file/edit tool; "
            "forbidden — only experiment_runner.py may emit metrics"
        )

    change_positions = [m.start() for m in EXPERIMENT_RUNNER_CHANGE_PATTERN.finditer(log_text)]
    if len(change_positions) > 1:
        last_change = max(change_positions)
        if not any(
            m.start() > last_change for m in EXPERIMENT_RUN_PATTERN.finditer(log_text)
        ):
            issues.append(
                "experiment_runner.py was modified after initial creation but "
                f"{EXPERIMENT_RUNNER_CMD} was not executed afterward"
            )

    if change_positions and not EXPERIMENT_RUN_PATTERN.search(log_text):
        issues.append(
            f"no evidence that {EXPERIMENT_RUNNER_CMD} completed "
            "(missing run log markers in aris_run.log)"
        )

    return issues


def validate_aris_deliverables(run_root: Path, task_dir: Path) -> tuple[bool, list[str]]:
    """Return (complete, issues) for benchmark-required ARIS artifacts."""
    cfg = load_task_benchmark_config(task_dir)
    issues: list[str] = []

    if not _artifact_exists(run_root, "idea-stage/IDEA_REPORT.md", "IDEA_REPORT.md"):
        issues.append("missing idea-stage/IDEA_REPORT.md")

    project = run_root / "project"
    if not project.is_dir() or not any(project.rglob("*.py")):
        issues.append("missing project/*.py experiment code")

    metrics_path = find_metrics_path(run_root)
    if metrics_path is None:
        issues.append(
            "missing metrics.json (expected under results/, experiment_results/, or project/)"
        )
    else:
        metrics_rel = str(metrics_path.relative_to(run_root))
        try:
            data = json.loads(metrics_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            issues.append(f"{metrics_rel} is invalid JSON")
        else:
            for key in cfg.required_metrics:
                if not _json_has_metric_key(data, key):
                    issues.append(f"{metrics_rel} missing or null metric: {key}")
            if isinstance(data, dict):
                issues.extend(_validate_metrics_provenance(data, metrics_rel=metrics_rel))

    log_text = _read_run_log(run_root)
    issues.extend(_validate_experiment_integrity_from_log(log_text))

    review_path = run_root / "review-stage" / "AUTO_REVIEW.md"
    if not review_path.is_file() and not (run_root / "AUTO_REVIEW.md").is_file():
        issues.append("missing review-stage/AUTO_REVIEW.md (Stage 3 /auto-review-loop-llm log)")
    else:
        best_score = _max_review_score(run_root)
        if best_score is None:
            issues.append("could not parse review score from AUTO_REVIEW.md or aris_run.log")
        elif best_score < MIN_REVIEW_SCORE:
            issues.append(
                f"review score {best_score}/10 below required {MIN_REVIEW_SCORE}/10 "
                "(run /auto-review-loop-llm until threshold or document blocker)"
            )

    if not (run_root / "NARRATIVE_REPORT.md").is_file():
        issues.append("missing NARRATIVE_REPORT.md (Stage 4 summary)")

    has_paper = (run_root / "paper" / "main.tex").is_file() or (
        run_root / "paper" / "main.pdf"
    ).is_file()
    if not has_paper:
        issues.append("missing paper/main.tex or paper/main.pdf (Stage 5 Skill /paper-writing)")

    if not (run_root / "README.md").is_file():
        issues.append("missing README.md")

    return not issues, issues


def finalize_run_metadata(
    run_root: Path,
    *,
    returncode: int,
    container_id: str | None,
    docker_workdir: str | None,
    validation_issues: list[str] | None = None,
) -> Path:
    from run_metering import write_manifest_with_metering

    status = {
        "idea": _artifact_exists(
            run_root,
            "idea-stage/IDEA_REPORT.md",
            "IDEA_REPORT.md",
        ),
        "experiment_plan": _artifact_exists(
            run_root,
            "refine-logs/EXPERIMENT_PLAN.md",
            "EXPERIMENT_PLAN.md",
        ),
        "experiment_log": _artifact_exists(
            run_root,
            "refine-logs/EXPERIMENT_LOG.md",
            "EXPERIMENT_LOG.md",
        ),
        "metrics": find_metrics_path(run_root) is not None,
        "review": (run_root / "review-stage" / "AUTO_REVIEW.md").is_file()
        or (run_root / "AUTO_REVIEW.md").is_file(),
        "narrative": (run_root / "NARRATIVE_REPORT.md").is_file(),
        "paper_tex": (run_root / "paper" / "main.tex").is_file(),
        "paper_pdf": (run_root / "paper" / "main.pdf").is_file(),
    }
    review_score = _max_review_score(run_root)
    manifest = {
        "framework": "aris",
        "run_dir": str(run_root),
        "returncode": returncode,
        "benchmark_complete": not validation_issues,
        "validation_issues": validation_issues or [],
        "review_score_best": review_score,
        "docker": {
            "container_id": container_id,
            "workdir": docker_workdir,
        },
        "artifacts": collect_artifact_paths(run_root),
        "status": status,
    }
    out = run_root / "artifacts" / "manifest.json"
    log_path = run_root / "aris_run.log"
    return write_manifest_with_metering(
        out,
        manifest,
        run_root,
        log_path=log_path if log_path.is_file() else None,
    )


def _artifact_exists(run_root: Path, *candidates: str) -> bool:
    return any((run_root / name).is_file() for name in candidates)


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
        "idea_report": _first_artifact(run_root, "idea-stage/IDEA_REPORT.md", "IDEA_REPORT.md"),
        "experiment_plan": _first_artifact(
            run_root,
            "refine-logs/EXPERIMENT_PLAN.md",
            "EXPERIMENT_PLAN.md",
        ),
        "experiment_log": _first_artifact(
            run_root,
            "refine-logs/EXPERIMENT_LOG.md",
            "EXPERIMENT_LOG.md",
        ),
        "metrics": (
            str(mp.relative_to(run_root))
            if (mp := find_metrics_path(run_root)) is not None
            else ""
        ),
        "narrative": "NARRATIVE_REPORT.md" if (run_root / "NARRATIVE_REPORT.md").is_file() else "",
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
    del docker_workdir
    env = task_env if task_env is not None else load_task_env(task_dir)
    body = build_agent_task_document(task_dir, env)
    brief = build_aris_research_brief(task_dir, env)
    launch = build_aris_launch_prompt(task_dir, env)
    (run_root / "task_input.md").write_text(body, encoding="utf-8")
    (run_root / "RESEARCH_BRIEF.md").write_text(brief, encoding="utf-8")
    (run_root / "CLAUDE.md").write_text(brief, encoding="utf-8")
    prompt_path = run_root / ".aris-benchmark" / "launch_prompt.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(launch, encoding="utf-8")
    return prompt_path


def refresh_aligned_runtime_docs(
    run_root: Path,
    task_dir: Path,
    task_env: dict[str, str],
    *,
    docker_workdir: str,
) -> Path:
    del docker_workdir
    align_run_dataset_paths(run_root, task_env)
    return write_runtime_files(
        run_root,
        task_dir,
        docker_workdir=str(run_root),
        task_env=task_env,
    )
