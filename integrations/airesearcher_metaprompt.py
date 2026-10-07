"""Synthesize AI-Researcher ``metaprompt`` modules from any task package.

Upstream InnoFlow does::

    importlib.import_module(f"benchmark.process.dataset_candidate.{category}.metaprompt")

and reads ``DATASET`` / ``BASELINE`` / ``COMPARISON`` / ``EVALUATION`` / ``REF``.
Official categories only exist for a few ML domains. Benchmark tasks use a
generic ``--category`` (default ``benchmark``) and have no such module.

This helper builds those fields from ``task.md`` + ``seeds/agent/*`` and
installs them into ``sys.modules`` so the upstream import succeeds without
editing AI-Researcher sources.
"""

from __future__ import annotations

import importlib
import json
import re
import sys
import types
from pathlib import Path
from typing import Any


_FENCE_SECTION = re.compile(
    r"###\s+(?P<title>Datasets|Baselines|Metrics)\s*\n```(?P<body>[\s\S]*?)```",
    re.IGNORECASE,
)


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _extract_setup_sections(task_md: str) -> dict[str, str]:
    found: dict[str, str] = {}
    for m in _FENCE_SECTION.finditer(task_md or ""):
        key = m.group("title").strip().lower()
        found[key] = m.group("body").strip()
    return found


def _dataset_paths_blob(task_dir: Path, run_root: Path | None) -> str:
    candidates = []
    if run_root is not None:
        candidates.append(run_root / "dataset_candidate" / "dataset_paths.json")
    candidates.append(task_dir / "seeds" / "agent" / "dataset_paths.json")
    for path in candidates:
        data = _load_json(path)
        if data is None:
            continue
        return json.dumps(data, ensure_ascii=False, indent=2)
    return ""


def _metrics_json_blob(task_dir: Path, run_root: Path | None) -> str:
    candidates = []
    if run_root is not None:
        candidates.append(run_root / "dataset_candidate" / "metrics.json")
    candidates.append(task_dir / "seeds" / "agent" / "metrics.json")
    for path in candidates:
        data = _load_json(path)
        if data is None:
            continue
        return json.dumps(data, ensure_ascii=False, indent=2)
    return ""


def _research_question(task_md: str) -> str:
    m = re.search(
        r"##\s+Research Question\s*\n(?P<body>[\s\S]*?)(?=\n## |\Z)",
        task_md or "",
        flags=re.IGNORECASE,
    )
    if not m:
        return ""
    return m.group("body").strip()


def build_metaprompt_fields(
    task_dir: Path,
    *,
    run_root: Path | None = None,
) -> dict[str, str]:
    """Build the five upstream metaprompt string fields (+ optional TASK)."""
    task_dir = Path(task_dir).resolve()
    run_root = Path(run_root).resolve() if run_root else None

    task_md = _read_text(task_dir / "task.md")
    sections = _extract_setup_sections(task_md)
    rq = _research_question(task_md)
    paths_blob = _dataset_paths_blob(task_dir, run_root)
    metrics_blob = _metrics_json_blob(task_dir, run_root)
    seeds_readme = _read_text(task_dir / "seeds" / "README.md")
    brief = ""
    if run_root is not None:
        brief = _read_text(run_root / "RESEARCH_BRIEF.md")
    if not brief:
        brief = _read_text(task_dir / "task.md")

    datasets = sections.get("datasets", "").strip()
    baselines = sections.get("baselines", "").strip()
    metrics = sections.get("metrics", "").strip()

    dataset_parts = [
        "Use the task's own dataset policy (from task.md / seeds). "
        "Prefer files under `dataset_candidate/` in the workplace.",
    ]
    if datasets:
        dataset_parts.append("### Datasets (from task.md)\n" + datasets)
    if paths_blob:
        dataset_parts.append(
            "### dataset_paths.json\n"
            "```json\n"
            f"{paths_blob}\n"
            "```\n"
            "Follow `layout` / path keys when present. "
            "If the layout is synthetic/constructable, generate the required "
            "data under the stated directories instead of inventing a substitute corpus."
        )
    elif not datasets:
        dataset_parts.append(
            "No pre-packaged corpus was found. If the task requires data, "
            "construct or obtain it as described in the research brief / task.md, "
            "and keep artifacts under `dataset_candidate/`."
        )
    if seeds_readme.strip():
        # Keep short — seeds README can be long.
        dataset_parts.append(
            "### Seeds notes (excerpt)\n" + seeds_readme.strip()[:2500]
        )

    baseline_text = baselines or (
        "Use the baselines listed in the research brief / task.md. "
        "If none are listed, choose lightweight, reproducible baselines "
        "appropriate for the task and document them."
    )

    comparison_parts = [
        "Compare your method against the listed baselines on the stated metrics.",
        "Report results under `results/` (e.g. `results/metrics.json`) with "
        "enough provenance to reproduce the numbers.",
    ]
    if baselines:
        comparison_parts.insert(0, "### Baselines\n" + baselines)
    if metrics:
        comparison_parts.append("### Metrics\n" + metrics)

    evaluation_parts = [
        "Evaluate using the task metrics. Persist final numbers under `results/`.",
    ]
    if metrics:
        evaluation_parts.append("### Metrics (from task.md)\n" + metrics)
    if metrics_blob:
        evaluation_parts.append(
            "### metrics.json schema\n```json\n" + metrics_blob + "\n```"
        )

    ref_parts = [
        "Primary guidance is the workplace research brief (`RESEARCH_BRIEF.md` / task prompt) "
        "and `related_work.json` / prepared source papers.",
    ]
    if rq:
        ref_parts.append("### Research question\n" + rq)
    # Keep a short brief pointer rather than dumping the whole document again.
    if brief.strip():
        ref_parts.append(
            "See `RESEARCH_BRIEF.md` in the workplace for the full agent-facing task document."
        )

    task_line = rq.splitlines()[0].strip() if rq else task_dir.name
    if len(task_line) > 240:
        task_line = task_line[:237] + "..."

    return {
        "TASK": task_line,
        "DATASET": "\n\n".join(dataset_parts).strip() + "\n",
        "BASELINE": baseline_text.strip() + "\n",
        "COMPARISON": "\n\n".join(comparison_parts).strip() + "\n",
        "EVALUATION": "\n\n".join(evaluation_parts).strip() + "\n",
        "REF": "\n\n".join(ref_parts).strip() + "\n",
    }


def render_metaprompt_py(fields: dict[str, str]) -> str:
    """Render a Python module source matching upstream metaprompt shape."""

    def _assign(name: str, value: str) -> str:
        return f"{name} = {value!r}\n"

    parts = [
        "# Auto-generated by ai_scientist_benchmark integrations/airesearcher_metaprompt.py\n",
        "# Do not edit AI-Researcher upstream; this shadows import for the current process.\n\n",
        _assign("TASK", fields.get("TASK", "")),
        "\n",
        _assign("DATASET", fields.get("DATASET", "")),
        "\n",
        _assign("BASELINE", fields.get("BASELINE", "")),
        "\n",
        _assign("COMPARISON", fields.get("COMPARISON", "")),
        "\n",
        _assign("EVALUATION", fields.get("EVALUATION", "")),
        "\n",
        _assign("REF", fields.get("REF", "")),
    ]
    return "".join(parts)


def _ensure_pkg(namespace: str) -> types.ModuleType:
    if namespace in sys.modules:
        mod = sys.modules[namespace]
        if not isinstance(mod, types.ModuleType):
            raise TypeError(f"{namespace} is not a module")
        return mod
    # Prefer real packages (AI-Researcher ships ``benchmark``).
    try:
        mod = importlib.import_module(namespace)
        return mod
    except ModuleNotFoundError:
        mod = types.ModuleType(namespace)
        mod.__path__ = []  # type: ignore[attr-defined]
        sys.modules[namespace] = mod
        parent, _, child = namespace.rpartition(".")
        if parent:
            parent_mod = _ensure_pkg(parent)
            setattr(parent_mod, child, mod)
        return mod


def install_task_metaprompt(
    *,
    category: str,
    task_dir: Path,
    run_root: Path | None = None,
    force: bool = True,
) -> types.ModuleType:
    """Install ``benchmark.process.dataset_candidate.<category>.metaprompt``.

    Always synthesizes from the task package so arbitrary SE / science tasks
    work. Set ``force=False`` to keep an already-imported upstream module.
    """
    category = (category or "benchmark").strip() or "benchmark"
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", category):
        raise ValueError(f"invalid AI-Researcher category for import: {category!r}")

    module_name = f"benchmark.process.dataset_candidate.{category}.metaprompt"
    if module_name in sys.modules and not force:
        return sys.modules[module_name]

    fields = build_metaprompt_fields(task_dir, run_root=run_root)
    source = render_metaprompt_py(fields)

    if run_root is not None:
        out_dir = Path(run_root) / ".airesearcher-benchmark"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "metaprompt.py"
        out_path.write_text(source, encoding="utf-8")
        (out_dir / "metaprompt_category.txt").write_text(category + "\n", encoding="utf-8")

    # Ensure parent packages exist, then inject category package + metaprompt.
    dc = _ensure_pkg("benchmark.process.dataset_candidate")
    cat_name = f"benchmark.process.dataset_candidate.{category}"
    cat_mod = types.ModuleType(cat_name)
    cat_mod.__path__ = []  # type: ignore[attr-defined]
    sys.modules[cat_name] = cat_mod
    setattr(dc, category, cat_mod)

    meta = types.ModuleType(module_name)
    for key, value in fields.items():
        setattr(meta, key, value)
    meta.__file__ = (
        str(Path(run_root) / ".airesearcher-benchmark" / "metaprompt.py")
        if run_root is not None
        else f"<airesearcher_metaprompt:{category}>"
    )
    sys.modules[module_name] = meta
    setattr(cat_mod, "metaprompt", meta)

    print(
        f"[airesearcher] installed task metaprompt as {module_name} "
        f"(from {Path(task_dir).name})",
        flush=True,
    )
    return meta
