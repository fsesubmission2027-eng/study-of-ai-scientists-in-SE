"""Stage task seeds for agent-visible dataset_candidate (exclude pilot/synthetic samples)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

# Never expose these to the agent workspace (human docs + pilot artifacts).
DEFAULT_EXCLUDE_NAMES = frozenset(
    {
        "README.md",
        "benchmark_config.json",
        "container_setup.sh",
    }
)
DEFAULT_EXCLUDE_GLOBS = ("sample_*", "synthetic_*", "*_pilot.*", "*_pilot_*")


def _load_benchmark_config(seeds_dir: Path) -> dict:
    path = seeds_dir / "benchmark_config.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _exclude_names(seeds_dir: Path) -> set[str]:
    cfg = _load_benchmark_config(seeds_dir)
    names = set(DEFAULT_EXCLUDE_NAMES)
    for item in cfg.get("exclude_from_agent", []):
        names.add(str(item))
    return names


def _should_exclude(name: str, exclude_names: set[str]) -> bool:
    if name in exclude_names:
        return True
    lower = name.lower()
    for pattern in DEFAULT_EXCLUDE_GLOBS:
        if Path(name).match(pattern):
            return True
    if "sample" in lower and lower.endswith(".csv"):
        return True
    if "synthetic" in lower and lower.endswith(".csv"):
        return True
    return False


def agent_seed_sources(seeds_dir: Path) -> list[Path]:
    """Return seed files/dirs that may be copied into dataset_candidate for agents."""
    if not seeds_dir.is_dir():
        return []

    agent_subdir = seeds_dir / "agent"
    if agent_subdir.is_dir() and any(agent_subdir.iterdir()):
        return sorted(p for p in agent_subdir.iterdir() if p.name != ".gitkeep")

    exclude_names = _exclude_names(seeds_dir)
    return sorted(
        p
        for p in seeds_dir.iterdir()
        if p.name != "agent" and not _should_exclude(p.name, exclude_names)
    )


def stage_seeds_for_agent(
    seeds_dir: Path,
    dest_dir: Path,
    *,
    task_env: dict[str, str] | None = None,
) -> list[str]:
    """Copy allowed seed artifacts into dest_dir. Returns staged relative paths."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    staged: list[str] = []
    for src in agent_seed_sources(seeds_dir):
        target = dest_dir / src.name
        if src.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(src, target)
        else:
            shutil.copy2(src, target)
        staged.append(src.name)

    if task_env:
        from path_alignment import align_dataset_paths_file, ensure_dataset_symlinks

        align_dataset_paths_file(dest_dir / "dataset_paths.json", task_env)
        if dest_dir.name == "dataset_candidate":
            ensure_dataset_symlinks(dest_dir.parent, task_env)
    return staged


def shell_copy_agent_seeds(seeds_dir: Path, dest_dir: str) -> str:
    """Bash snippet: copy only agent-visible seeds into dest_dir inside a container."""
    sources = agent_seed_sources(seeds_dir)
    if not sources:
        return f"mkdir -p {dest_dir}"

    parts = [f"mkdir -p {dest_dir}"]
    agent_subdir = seeds_dir / "agent"
    if agent_subdir.is_dir() and any(agent_subdir.iterdir()):
        parts.append(f"cp -r /task/seeds/agent/. {dest_dir}/ 2>/dev/null || true")
        return " && ".join(parts)

    for src in sources:
        parts.append(f"cp -r /task/seeds/{src.name} {dest_dir}/ 2>/dev/null || true")
    return " && ".join(parts)
