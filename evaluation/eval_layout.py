"""Output layout for evaluation artifacts.

Default root is a sibling of ``ai_scientist_inputs``::

    ~/ai_scientist_inputs/<task>/workspace/<run>/...
    ~/ai_scientist_evals/<task>/<run>/evaluation.json
    ~/ai_scientist_evals/<task>/original_claims.json
    ~/ai_scientist_evals/<task>/solution_space.json
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_EVALS_DIRNAME = "ai_scientist_evals"
DEFAULT_INPUTS_DIRNAME = "ai_scientist_inputs"


def default_evals_root() -> Path:
    """Return ``<parent-of-ai_scientist_inputs>/ai_scientist_evals`` when possible."""
    override = (os.environ.get("BENCHMARK_EVALS_ROOT") or "").strip()
    if override:
        return Path(override).expanduser().resolve()

    home = Path.home()
    inputs = home / DEFAULT_INPUTS_DIRNAME
    if inputs.is_dir():
        return (inputs.parent / DEFAULT_EVALS_DIRNAME).resolve()
    return (home / DEFAULT_EVALS_DIRNAME).resolve()


def task_name_from_dir(task_dir: Path) -> str:
    return task_dir.resolve().name


def run_name_from_dir(run_dir: Path) -> str:
    return run_dir.resolve().name


def task_eval_dir(task_dir: Path, *, evals_root: Path | None = None) -> Path:
    root = (evals_root or default_evals_root()).resolve()
    return root / task_name_from_dir(task_dir)


def run_eval_dir(
    run_dir: Path,
    *,
    task_dir: Path | None = None,
    evals_root: Path | None = None,
) -> Path:
    """``<evals_root>/<task>/<run>/``."""
    root = (evals_root or default_evals_root()).resolve()
    if task_dir is None:
        # .../<task>/workspace/<run>
        if run_dir.parent.name == "workspace":
            task_dir = run_dir.parent.parent
        else:
            task_dir = run_dir.parent
    return root / task_name_from_dir(task_dir) / run_name_from_dir(run_dir)


def evaluation_json_path(
    run_dir: Path,
    *,
    task_dir: Path | None = None,
    evals_root: Path | None = None,
) -> Path:
    return run_eval_dir(run_dir, task_dir=task_dir, evals_root=evals_root) / "evaluation.json"


def original_claims_path(
    task_dir: Path,
    *,
    evals_root: Path | None = None,
) -> Path:
    return task_eval_dir(task_dir, evals_root=evals_root) / "original_claims.json"


def solution_space_path(
    task_dir: Path,
    *,
    evals_root: Path | None = None,
) -> Path:
    return task_eval_dir(task_dir, evals_root=evals_root) / "solution_space.json"
