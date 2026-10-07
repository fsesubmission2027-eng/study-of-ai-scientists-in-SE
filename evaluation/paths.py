"""Path alias resolution for cross-framework AI-scientist run directories."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FoundArtifact:
    category: str
    path: Path
    relative: str
    bytes: int
    via: str  # "candidate" | "manifest" | "glob"


def _rel(run_dir: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(run_dir.resolve()))
    except ValueError:
        return str(path)


def _is_junk(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    if any(x in parts for x in {"__pycache__", ".git", "node_modules", ".venv", "venv"}):
        return True
    name = path.name.lower()
    if name.endswith((".pyc", ".pyo", ".so", ".o", ".class")):
        return True
    return False


def _nonempty_file(path: Path, *, min_bytes: int = 1) -> bool:
    try:
        return path.is_file() and path.stat().st_size >= min_bytes and not _is_junk(path)
    except OSError:
        return False


def _first_existing(run_dir: Path, relatives: Iterable[str], *, min_bytes: int = 1) -> Path | None:
    for rel in relatives:
        cand = run_dir / rel
        if _nonempty_file(cand, min_bytes=min_bytes):
            return cand.resolve()
    return None


def _glob_first(
    run_dir: Path,
    patterns: Iterable[str],
    *,
    min_bytes: int = 1,
    prefer_shorter: bool = True,
    blocked: Callable[[str], bool] | None = None,
) -> Path | None:
    hits: list[Path] = []
    for pattern in patterns:
        for path in run_dir.glob(pattern):
            if not _nonempty_file(path, min_bytes=min_bytes):
                continue
            try:
                rel_raw = str(path.relative_to(run_dir))
            except ValueError:
                continue
            if blocked is not None and blocked(rel_raw):
                continue
            resolved = path.resolve()
            rel = _rel(run_dir, resolved)
            if blocked is not None and blocked(rel):
                continue
            hits.append(resolved)
    if not hits:
        return None
    if prefer_shorter:
        hits.sort(key=lambda p: (len(_rel(run_dir, p)), _rel(run_dir, p)))
    return hits[0]


def _load_manifest(run_dir: Path) -> dict:
    path = run_dir / "artifacts" / "manifest.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _manifest_paths(run_dir: Path, manifest: dict) -> list[Path]:
    artifacts = manifest.get("artifacts")
    out: list[Path] = []

    def walk(node: object) -> None:
        if isinstance(node, str) and node.strip():
            cand = run_dir / node
            if cand.exists():
                out.append(cand.resolve())
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    if isinstance(artifacts, dict):
        walk(artifacts)
    return out


IDEA_CANDIDATES = [
    "artifacts/idea.json",
    "artifacts/idea/selected_idea.md",
    "idea-stage/IDEA_REPORT.md",
    "idea-stage/selected_idea.md",
    "IDEA_REPORT.md",
    "selected_idea.md",
    "tiny_idea.json",
    "tiny_idea_from_think.json",
    "session/idea.json",
    "hypotheses.md",
    "stage-08/hypotheses.md",
    "idea.md",
    "IDEA.md",
    "DeepScientist/quests/001/idea.md",
    "plan.md",
    "todos.md",
]

# Directory names that are never experiment artifacts (results / code / paper).
FRAMEWORK_NOISE_DIRS = {
    "dataset_candidate",
    "seeds",
    "downloads",
    "site-packages",
    "skills",
    "templates",
    ".container-home",
    "sandbox",
    "node_modules",
    ".git",
    "__pycache__",
    ".deepscientist_npm",
    ".codex",
    "opencode-home",
    "python-env",
    "uv-cache",
    ".uv-cache",
    "npm-cache",
    ".npm",
    # Benchmark / dataset trees mistaken for agent experiment code
    "checkouts",
}

# Substring markers for framework / toolchain trees (not experiment work).
FRAMEWORK_NOISE_MARKERS = (
    "/.deepscientist_npm/",
    "/deepscientist/runtime/",
    "/.codex/",
    "/opencode-home/",
    "/python-env/",
    "/uv-cache/",
    "/.uv-cache/",
    "/site-packages/",
    "/node_modules/",
    "/.git/",
    "/skills/",
    "/templates/",
    "/sandbox/",
    "/downloads/",
    "/lib/python3",
    "/cpython-",
)

RESULT_PATH_BLOCKLIST = set(FRAMEWORK_NOISE_DIRS)

CODE_GLOBS = [
    "project/**/*.py",
    "project/**/*.sh",
    "analysis/**/*.py",
    "artifacts/code/**/*.py",
    "stage-10/experiment/**/*.py",
    "stage-10/**/*.py",
    "stage-*/**/*.py",
    "experiments/**/*.py",
    "experiment_results/**/*.py",
    "results/**/*.py",
    "code/**/*.py",
    "src/**/*.py",
    "*/src/**/*.py",
    "**/src/**/*.py",
    "scripts/**/*.py",
    "tools/**/*.py",
    "method/**/*.py",
    "models/**/*.py",
    "session/**/*.py",
    "lib/**/*.py",
    "implementations/**/*.py",
    # DeepScientist / quest worktrees (Java tool-type tasks, etc.)
    "**/.ds/worktrees/**/src/**/*.java",
    "**/.ds/worktrees/**/src/**/*.py",
    "**/.ds/worktrees/**/project/**/*.py",
    "**/.ds/worktrees/**/project/**/*.java",
    "**/.ds/worktrees/**/experiments/**/*.py",
    "**/.ds/worktrees/**/experiments/**/*.java",
    "**/quests/**/src/**/*.java",
    "**/quests/**/src/**/*.py",
    "**/quests/**/project/**/*.py",
    "**/quests/**/project/**/*.java",
    "**/quests/**/experiments/**/*.py",
    "**/quests/**/experiments/**/*.java",
    "**/expogen/src/**/*.java",
    # Tool-local packages often live at run-root/<name>/...
    "*/*.py",
    "*/*/*.py",
    # Shell experiment runners
    "experiment_results/**/*.sh",
    "scripts/**/*.sh",
    "project/**/*.java",
    "src/**/*.java",
    "*/src/**/*.java",
    "**/src/**/*.java",
    # EvoScientist / tool harnesses living under results trees
    "artifacts/results/**/harness/**/*.java",
    "artifacts/results/**/*Harness.java",
    "artifacts/code/**/*.java",
]

# Directories that must never count as experiment code.
CODE_PATH_BLOCKLIST = RESULT_PATH_BLOCKLIST | {
    "paper",
    "idea-stage",
    "review-stage",
    "refine-logs",
    ".aris",
    ".aris-benchmark",
    ".claude",
    ".sandbox-home",
    ".sandbox-tmp",
}


def _noise_path_blocked(rel: str, *, extra_dirs: set[str] | None = None) -> bool:
    parts = {p.lower() for p in Path(rel).parts}
    blocked_dirs = RESULT_PATH_BLOCKLIST if extra_dirs is None else (RESULT_PATH_BLOCKLIST | extra_dirs)
    if parts & blocked_dirs:
        return True
    norm = "/" + rel.replace("\\", "/").lower().strip("/") + "/"
    return any(m in norm for m in FRAMEWORK_NOISE_MARKERS)


def _code_path_blocked(rel: str) -> bool:
    parts = {p.lower() for p in Path(rel).parts}
    if parts & CODE_PATH_BLOCKLIST:
        return True
    return _noise_path_blocked(rel)


def _result_path_blocked(rel: str) -> bool:
    return _noise_path_blocked(rel)


def _paper_path_blocked(rel: str) -> bool:
    """Reject skill/template tex and other framework noise as 'the paper'."""
    if _noise_path_blocked(rel):
        return True
    norm = "/" + rel.replace("\\", "/").lower().strip("/") + "/"
    return any(m in norm for m in PAPER_PDF_BLOCK_MARKERS)


def _is_likely_agent_paper_pdf(run_dir: Path, path: Path) -> bool:
    """Heuristic: manuscript PDF, not a figure / arxiv download / chart."""
    try:
        rel = _rel(run_dir, path).replace("\\", "/").lower()
    except Exception:
        return False
    if _paper_path_blocked(rel):
        return False
    name = path.name.lower()
    if name in {"main.pdf", "paper.pdf", "manuscript.pdf", "acl_latex.pdf"}:
        return True
    # Accept PDFs living under a .../paper/ tree (excluding blocked markers).
    parts = Path(rel).parts
    if "paper" in parts and path.stat().st_size >= 10_000:
        # Reject obvious figure-only names
        if any(tok in name for tok in ("bar", "plot", "fig", "chart", "heatmap", "ablation_fig")):
            return False
        return True
    return False


def promote_paper_pdf_to_canonical(run_dir: Path, src: Path) -> Path | None:
    """Copy a deep agent paper PDF to ``paper/main.pdf`` for a stable path."""
    run_dir = run_dir.resolve()
    src = src.resolve()
    dest = run_dir / "paper" / "main.pdf"
    try:
        if dest.is_file() and dest.stat().st_size >= 100:
            # Already have a canonical PDF; keep it unless empty/tiny.
            if dest.resolve() == src:
                return dest
            return dest
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.resolve() == src:
            return dest
        shutil.copy2(src, dest)
        return dest if dest.is_file() and dest.stat().st_size >= 100 else None
    except OSError:
        return None


def pdf_extractable_alnum_chars(pdf_path: Path) -> int | None:
    """Return alphanumeric char count via pdftotext, or None if unavailable."""
    if not shutil.which("pdftotext"):
        return None
    try:
        proc = subprocess.run(
            ["pdftotext", "-q", str(pdf_path), "-"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=60,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    text = proc.stdout or ""
    return sum(1 for c in text if c.isalnum())


def pdf_looks_unreadable(pdf_path: Path, *, min_alnum: int = 200) -> bool:
    """True when the PDF appears to have almost no extractable text."""
    n = pdf_extractable_alnum_chars(pdf_path)
    if n is None:
        return False
    return n < min_alnum


def rebuild_canonical_paper_pdf(run_dir: Path) -> Path | None:
    """Force-rebuild ``paper/main.pdf`` from TeX (preferred) or Markdown.

    Overwrites any existing ``paper/main.pdf``. Used when paperreview.ai rejects
    a broken/empty PDF, or when preflight detects an unreadable PDF.
    If TeX compiles but the PDF is still unreadable (e.g. missing fonts), fall
    back to Markdown via pandoc when available.
    """
    run_dir = run_dir.resolve()
    dest = run_dir / "paper" / "main.pdf"
    dest.parent.mkdir(parents=True, exist_ok=True)

    candidates: list[Path] = []

    tex = find_tex(run_dir)
    if tex is not None:
        compiled = _compile_tex_to_pdf(tex.path)
        if compiled is not None and compiled.is_file() and compiled.stat().st_size >= 500:
            try:
                if compiled.resolve() != dest.resolve():
                    shutil.copy2(compiled, dest)
                if dest.is_file() and dest.stat().st_size >= 500:
                    if not pdf_looks_unreadable(dest):
                        return dest
                    candidates.append(dest)
            except OSError:
                pass

    md = find_paper_md(run_dir)
    if md is not None:
        md_dest = run_dir / "paper" / "main_from_md.pdf"
        try:
            if md_dest.is_file():
                md_dest.unlink()
        except OSError:
            pass
        compiled_md = _compile_md_to_pdf(md.path, md_dest)
        if compiled_md is not None and not pdf_looks_unreadable(compiled_md):
            try:
                shutil.copy2(compiled_md, dest)
                return dest
            except OSError:
                return compiled_md
        if compiled_md is not None:
            candidates.append(compiled_md)

    # Last resort: keep whatever we produced, even if still weak.
    for path in candidates:
        if path.is_file() and path.stat().st_size >= 500:
            try:
                if path.resolve() != dest.resolve():
                    shutil.copy2(path, dest)
                return dest
            except OSError:
                return path
    return None


RESULT_CANDIDATES = [
    "results/metrics.json",
    "experiment_results/metrics.json",
    "artifacts/results/metrics.json",
    "artifacts/results/runs/metrics.json",
    "results/results.json",
    "artifacts/results/results.json",
    "session/data/metrics.json",
]

RESULT_GLOBS = [
    "results/**/*.json",
    "experiment_results/**/*.json",
    "artifacts/results/**/*",
    "stage-12/runs/**/*",
    "stage-13/runs/**/*",
    # DeepScientist / multi-tool eval dumps
    "**/eval_output*/results.json",
    "**/.ds/worktrees/**/results.json",
    "**/.ds/worktrees/**/eval_output*/**/*.json",
    "**/.ds/worktrees/**/experiments/**/output/*.json",
    "**/quests/**/results.json",
    "**/quests/**/experiments/**/output/*.json",
    "**/quests/**/experiments/**/output/**/*.json",
    "artifacts/reports/*.json",
    "**/artifacts/reports/*.json",
    "**/expogen/**/results.json",
    # AI Scientist / similar frameworks often persist final summaries under logs
    "**/draft_summary.json",
    "**/research_summary.json",
    "**/baseline_summary.json",
    "**/ablation_summary.json",
    # AI-Scientist v2 writes numeric experiment dumps here, not metrics.json
    "**/experiment_results/**/*.npy",
]


TEX_CANDIDATES = [
    "paper/main.tex",
    "paper/paper.tex",
    "artifacts/paper/main.tex",
    "artifacts/paper/paper.tex",
    "deliverables/paper.tex",
    "stage-22/paper.tex",
    "latex/main.tex",
    "latex/paper.tex",
    "latex/acl_latex.tex",
    # DeepScientist quest manuscript (common layout)
    "DeepScientist/quests/001/paper/main.tex",
    "DeepScientist/quests/001/paper/latex/main.tex",
]

TEX_GLOBS = [
    "paper/**/*.tex",
    "artifacts/paper/**/*.tex",
    "latex/**/*.tex",
    "deliverables/**/*.tex",
    "**/paper/main.tex",
    "**/paper/paper.tex",
    "**/paper/latex/main.tex",
    "**/main.tex",
]

PDF_CANDIDATES = [
    "paper/main.pdf",
    "paper/paper.pdf",
    "artifacts/paper/main.pdf",
    "deliverables/paper.pdf",
    "latex/main.pdf",
    "latex/acl_latex.pdf",
    "DeepScientist/quests/001/paper/main.pdf",
    "DeepScientist/quests/001/paper/paper.pdf",
    "DeepScientist/quests/001/paper/latex/main.pdf",
]

# Prefer shallow paper/ first; deep globs cover DeepScientist worktrees etc.
PDF_GLOBS = [
    "paper/**/*.pdf",
    "artifacts/paper/**/*.pdf",
    "latex/**/*.pdf",
    "**/paper/main.pdf",
    "**/paper/paper.pdf",
    "**/paper/manuscript.pdf",
    "**/paper/latex/main.pdf",
    "**/paper/build/main.pdf",
    "**/paper/build/paper.pdf",
    "**/paper/draft/paper.pdf",
    "**/main.pdf",
]

# PDFs under these path markers are never the agent manuscript.
PAPER_PDF_BLOCK_MARKERS = (
    "/literature/",
    "/arxiv/pdfs/",
    "/arxiv/",
    "/references/",
    "/related_work/",
    "/site-packages/",
    "/node_modules/",
)

PAPER_MD_CANDIDATES = [
    "paper/draft/exposegen_paper.md",
    "paper/draft/paper.md",
    "paper/draft.md",
    "paper/final_draft.md",
    "paper/paper.md",
    "paper/manuscript.md",
    "paper/main.md",
    "paper/outline.md",
    "paper/latex/paper.md",
    "paper/latex/main.md",
    "artifacts/paper/paper.md",
    "artifacts/paper/draft/paper.md",
    "artifacts/final_report.md",
    # DeepScientist quest manuscripts (paper.md is the common final draft name)
    "DeepScientist/quests/001/paper/paper.md",
    "DeepScientist/quests/001/paper/draft.md",
    "DeepScientist/quests/001/paper/manuscript.md",
    "DeepScientist/quests/001/paper/paper_draft.md",
    "DeepScientist/quests/001/paper/main.md",
    "DeepScientist/quests/001/paper/final_draft.md",
]

PAPER_MD_GLOBS = [
    "paper/draft/*_paper.md",
    "paper/draft/*.md",
    "paper/draft.md",
    "paper/latex/*.md",
    "paper/*.md",
    "paper/**/*.md",
    "artifacts/paper/**/*_paper.md",
    "artifacts/paper/**/*.md",
    # DeepScientist / nested quest paper trees (any quest id / worktree)
    "**/paper/paper.md",
    "**/paper/manuscript.md",
    "**/paper/main.md",
    "**/paper/final_draft.md",
    "**/paper/paper_draft.md",
    "**/paper/draft.md",
    "**/paper/draft/*_paper.md",
    "**/paper/draft/*.md",
    "**/paper/*_paper.md",
    "**/paper/*.md",
    "**/paper/latex/*.md",
]

# Auxiliary DeepScientist / agent markdown under paper/ — not the manuscript body.
PAPER_MD_SKIP_NAMES = frozenset(
    {
        "readme.md",
        "todo.md",
        "notes.md",
        "evidence_ledger.md",
        "paper_experiment_matrix.md",
        "writing_plan.md",
        "outline_selection.md",
        "chainrec_summary.md",
        "experiment_setup.md",
        "findings.md",
        "section.md",
        "impact.md",
        "paper_view.md",
        # Peer-review / planning / lit notes (not the manuscript)
        "review.md",
        "revision_log.md",
        "experiment_todo.md",
        "literature.md",
        "literature_review.md",
        "literature_synthesis.md",
        "idea.md",
        "paper_improvement_log.md",
        "paper_plan.md",
        "paper_writing_report.md",
        "paper_claim_audit.md",
        "paper_skeleton.md",
        "pipeline_report.md",
    }
)

PAPER_MD_PATH_SKIP_MARKERS = (
    "/outline/",
    "/outlines/",
    "/paper/review/",
    "/artifact_deltas/",
)

PAPER_JSON_CANDIDATES = [
    "artifacts/final_report.json",
]

PAPER_JSON_GLOBS = [
    "**/draft_summary.json",
    "**/research_summary.json",
]

BONUS_SPECS: dict[str, list[str]] = {
    "experiment_plan": [
        "EXPERIMENT_PLAN.md",
        "refine-logs/EXPERIMENT_PLAN.md",
        "plan.md",
        "todos.md",
        "stage-09/exp_plan.yaml",
    ],
    "experiment_log": [
        "EXPERIMENT_LOG.md",
        "refine-logs/EXPERIMENT_LOG.md",
        "*_run.log",
    ],
    "review": [
        "AUTO_REVIEW.md",
        "review-stage/AUTO_REVIEW.md",
        "artifacts/peer_review/**/*",
    ],
    "readme": ["README.md", "README_BENCHMARK.md"],
    "narrative": ["NARRATIVE_REPORT.md"],
    "bib": ["paper/references.bib", "artifacts/paper/references.bib", "**/references.bib"],
}


def find_idea(run_dir: Path, *, priority: Iterable[str] | None = None) -> FoundArtifact | None:
    ordered: list[str] = []
    seen: set[str] = set()
    for rel in list(priority or []) + IDEA_CANDIDATES:
        if rel not in seen:
            seen.add(rel)
            ordered.append(rel)
    path = _first_existing(run_dir, ordered, min_bytes=20)
    via = "candidate"
    if path is None:
        path = _glob_first(
            run_dir,
            [
                "**/IDEA_REPORT.md",
                "**/selected_idea.md",
                "**/idea.json",
                "**/hypotheses.md",
                "**/tiny_idea*.json",
            ],
            min_bytes=20,
            blocked=_noise_path_blocked,
        )
        via = "glob"
    if path is None:
        return None
    return FoundArtifact("idea", path, _rel(run_dir, path), path.stat().st_size, via)


def find_code(run_dir: Path) -> list[FoundArtifact]:
    files: list[FoundArtifact] = []
    seen: set[Path] = set()
    run_resolved = run_dir.resolve()
    for pattern in CODE_GLOBS:
        for path in run_dir.glob(pattern):
            suffix = path.suffix.lower()
            min_bytes = 20 if suffix in {".sh"} else 40
            if not path.is_file():
                continue
            # Relative path BEFORE resolve — catches blocked dirs even via symlinks.
            try:
                rel_raw = str(path.relative_to(run_dir))
            except ValueError:
                continue
            if _code_path_blocked(rel_raw):
                continue
            try:
                if path.stat().st_size < min_bytes or _is_junk(path):
                    continue
            except OSError:
                continue
            resolved = path.resolve()
            # Drop symlink targets that escape the run directory.
            try:
                resolved.relative_to(run_resolved)
            except ValueError:
                continue
            if resolved in seen:
                continue
            rel = _rel(run_dir, resolved)
            if _code_path_blocked(rel):
                continue
            if path.name.lower() in {"__init__.py"} and resolved.stat().st_size < 80:
                continue
            # Dataset stubs (e.g. Defects4J Placeholder.java) are not experiment code.
            if path.name.lower() in {"placeholder.java", "placeholder.py"}:
                continue
            seen.add(resolved)
            files.append(FoundArtifact("code", resolved, rel, resolved.stat().st_size, "glob"))
    files.sort(key=lambda f: f.relative)
    return files


def find_results(run_dir: Path) -> list[FoundArtifact]:
    found: list[FoundArtifact] = []
    seen: set[Path] = set()

    for rel in RESULT_CANDIDATES:
        path = run_dir / rel
        if _nonempty_file(path, min_bytes=2) and not _result_path_blocked(rel):
            resolved = path.resolve()
            seen.add(resolved)
            found.append(
                FoundArtifact("results", resolved, _rel(run_dir, resolved), resolved.stat().st_size, "candidate")
            )

    for pattern in RESULT_GLOBS:
        for path in run_dir.glob(pattern):
            if not path.is_file() or _is_junk(path):
                continue
            if path.suffix.lower() not in {".json", ".csv", ".tsv", ".txt", ".md", ".parquet", ".npz", ".npy"}:
                if path.suffix.lower() not in {".json", ".csv"}:
                    continue
            try:
                rel_raw = str(path.relative_to(run_dir))
            except ValueError:
                continue
            if _result_path_blocked(rel_raw):
                continue
            if path.stat().st_size < 2:
                continue
            resolved = path.resolve()
            if resolved in seen:
                continue
            rel = _rel(run_dir, resolved)
            if _result_path_blocked(rel):
                continue
            seen.add(resolved)
            found.append(FoundArtifact("results", resolved, rel, resolved.stat().st_size, "glob"))

    def _rank(rel: str) -> tuple:
        low = rel.lower()
        name = Path(rel).name.lower()
        prefer_eval = 0 if ("eval_output" in low or "metrics" in name or name == "results.json") else 1
        prefer_worktree = 0 if ".ds/worktrees" in low or "/expogen/" in low else 1
        return (prefer_eval, prefer_worktree, rel)

    found.sort(key=lambda f: _rank(f.relative))
    return found


_PAPER_TEX_SKIP_NAMES = {
    "template.tex",
    "sample.tex",
    "example.tex",
    "formatting.tex",
    "acl_lualatex.tex",
    "lualatex.tex",
}


def _is_likely_paper_tex(path: Path) -> bool:
    """Heuristic: real manuscript TeX vs style/template stubs."""
    name = path.name.lower()
    if name in _PAPER_TEX_SKIP_NAMES or name.endswith(".sty"):
        return False
    if _paper_path_blocked(str(path)):
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="replace")[:80_000]
    except OSError:
        return False
    if len(text) < 200:
        return False
    low = text.lower()
    if "\\begin{document}" not in low:
        return False
    if not any(x in low for x in ("\\title{", "\\begin{abstract}", "\\section{", "\\section*")):
        return False
    # ACL / venue instruction-only files without body sections.
    if "\\section{" not in low and "\\section*{" not in low and len(text) < 2500:
        return False
    return True


def iter_paper_tex_paths(run_dir: Path) -> list[Path]:
    """All substantive paper TeX paths under a run (for cite-key extraction)."""
    run_dir = run_dir.resolve()
    hits: list[Path] = []
    seen: set[Path] = set()
    for rel in TEX_CANDIDATES:
        path = run_dir / rel
        if path.is_file() and _is_likely_paper_tex(path):
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                hits.append(resolved)
    for pattern in TEX_GLOBS:
        for path in run_dir.glob(pattern):
            if not path.is_file():
                continue
            try:
                rel_raw = str(path.relative_to(run_dir))
            except ValueError:
                continue
            if _paper_path_blocked(rel_raw):
                continue
            resolved = path.resolve()
            if resolved in seen or not _is_likely_paper_tex(resolved):
                continue
            seen.add(resolved)
            hits.append(resolved)
    hits.sort(key=lambda p: _prefer_paperish(run_dir, p))
    return hits


def _prefer_paperish(run_dir: Path, path: Path) -> tuple:
    rel = _rel(run_dir, path).replace("\\", "/").lower()
    under_paper = 0 if (rel.startswith("paper/") or rel.startswith("artifacts/paper/")) else 1
    under_latex = 0 if rel.startswith("latex/") else 1
    substantive = 0 if _is_likely_paper_tex(path) else 1
    return (under_paper, under_latex, substantive, len(rel), rel)


def _prefer_paper_md(run_dir: Path, path: Path) -> tuple:
    rel = _rel(run_dir, path).replace("\\", "/").lower()
    name = path.name.lower()
    if name in {"draft.md", "paper.md", "final_draft.md", "main.md", "manuscript.md", "paper_draft.md"}:
        name_rank = 0
    elif name.endswith("_paper.md"):
        name_rank = 1
    elif "/draft/" in rel:
        name_rank = 2
    else:
        name_rank = 3
    # Prefer canonical run-root paper/ first, then DeepScientist quest paper/, then worktrees.
    if rel.startswith("paper/") or rel.startswith("artifacts/paper/"):
        under_paper = 0
    elif "/quests/" in rel and "/paper/" in rel and "/.ds/worktrees/" not in rel:
        under_paper = 1
    else:
        under_paper = 2
    return (under_paper, name_rank, len(rel), rel)


def _is_paper_md_auxiliary(rel: str, path: Path) -> bool:
    if path.name.lower() in PAPER_MD_SKIP_NAMES:
        return True
    norm = "/" + rel.replace("\\", "/").lower().strip("/") + "/"
    return any(m in norm for m in PAPER_MD_PATH_SKIP_MARKERS)


def find_tex(run_dir: Path) -> FoundArtifact | None:
    for rel in TEX_CANDIDATES:
        path = run_dir / rel
        if _nonempty_file(path, min_bytes=50) and not _paper_path_blocked(rel):
            resolved = path.resolve()
            return FoundArtifact("paper_tex", resolved, _rel(run_dir, resolved), resolved.stat().st_size, "candidate")

    hits: list[Path] = []
    for pattern in TEX_GLOBS:
        for path in run_dir.glob(pattern):
            if not _nonempty_file(path, min_bytes=50):
                continue
            try:
                rel_raw = str(path.relative_to(run_dir))
            except ValueError:
                continue
            if _paper_path_blocked(rel_raw):
                continue
            resolved = path.resolve()
            rel = _rel(run_dir, resolved)
            if _paper_path_blocked(rel):
                continue
            if not _is_likely_paper_tex(resolved):
                continue
            hits.append(resolved)
    if not hits:
        return None
    hits.sort(key=lambda p: _prefer_paperish(run_dir, p))
    path = hits[0]
    return FoundArtifact("paper_tex", path, _rel(run_dir, path), path.stat().st_size, "glob")


def _compile_tex_to_pdf(tex_path: Path) -> Path | None:
    tex_path = tex_path.resolve()
    tex_dir = tex_path.parent
    pdf_path = tex_path.with_suffix(".pdf")
    tex_name = tex_path.name

    commands: list[list[str]] = []
    if shutil.which("latexmk"):
        commands.append(
            [
                "latexmk",
                "-pdf",
                "-interaction=nonstopmode",
                "-halt-on-error",
                tex_name,
            ]
        )
    if shutil.which("pdflatex"):
        commands.append(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", tex_name])
    if shutil.which("xelatex"):
        commands.append(["xelatex", "-interaction=nonstopmode", "-halt-on-error", tex_name])

    for command in commands:
        try:
            subprocess.run(
                command,
                cwd=tex_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=180,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if pdf_path.is_file() and pdf_path.stat().st_size >= 100:
            return pdf_path
    return None


def _compile_md_to_pdf(md_path: Path, dest_pdf: Path) -> Path | None:
    """Convert a markdown paper draft to PDF via pandoc (preferred for md-only runs)."""
    if not shutil.which("pandoc"):
        return None
    md_path = md_path.resolve()
    dest_pdf = dest_pdf.resolve()
    dest_pdf.parent.mkdir(parents=True, exist_ok=True)

    engines: list[str] = []
    for engine in ("xelatex", "pdflatex", "lualatex"):
        if shutil.which(engine):
            engines.append(engine)
    if not engines:
        engines.append("")  # let pandoc pick default / fail cleanly

    for engine in engines:
        cmd = [
            "pandoc",
            str(md_path),
            "-o",
            str(dest_pdf),
            "-f",
            "markdown",
            "-t",
            "pdf",
            "-V",
            "geometry:margin=1in",
            "--resource-path",
            str(md_path.parent),
        ]
        if engine:
            cmd.extend(["--pdf-engine", engine])
        try:
            subprocess.run(
                cmd,
                cwd=md_path.parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=180,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if dest_pdf.is_file() and dest_pdf.stat().st_size >= 500:
            return dest_pdf
        # Clean failed tiny/empty outputs before next engine attempt.
        try:
            if dest_pdf.is_file():
                dest_pdf.unlink()
        except OSError:
            pass
    return None


def find_pdf(
    run_dir: Path,
    *,
    auto_compile: bool = False,
    promote_to_paper: bool = True,
) -> FoundArtifact | None:
    run_dir = run_dir.resolve()
    for rel in PDF_CANDIDATES:
        path = run_dir / rel
        if _nonempty_file(path, min_bytes=100) and not _paper_path_blocked(rel):
            resolved = path.resolve()
            return FoundArtifact("paper_pdf", resolved, _rel(run_dir, resolved), resolved.stat().st_size, "candidate")

    hits: list[Path] = []
    for pattern in PDF_GLOBS:
        for path in run_dir.glob(pattern):
            if not _nonempty_file(path, min_bytes=100):
                continue
            try:
                rel_raw = str(path.relative_to(run_dir))
            except ValueError:
                continue
            if _paper_path_blocked(rel_raw):
                continue
            resolved = path.resolve()
            if not _is_likely_agent_paper_pdf(run_dir, resolved):
                continue
            hits.append(resolved)
    if not hits:
        if auto_compile:
            tex = find_tex(run_dir)
            if tex is not None:
                compiled = _compile_tex_to_pdf(tex.path)
                if compiled is not None:
                    promoted = (
                        promote_paper_pdf_to_canonical(run_dir, compiled)
                        if promote_to_paper
                        else None
                    )
                    final = promoted or compiled
                    return FoundArtifact(
                        "paper_pdf",
                        final,
                        _rel(run_dir, final),
                        final.stat().st_size,
                        "compiled" if promoted is None else "compiled_promoted",
                    )
            # Markdown-only papers (common for DeepScientist drafts).
            md = find_paper_md(run_dir)
            if md is not None:
                dest = run_dir / "paper" / "main.pdf"
                compiled_md = _compile_md_to_pdf(md.path, dest)
                if compiled_md is not None:
                    return FoundArtifact(
                        "paper_pdf",
                        compiled_md,
                        _rel(run_dir, compiled_md),
                        compiled_md.stat().st_size,
                        "compiled_from_md",
                    )
        return None
    hits.sort(key=lambda p: _prefer_paperish(run_dir, p))
    path = hits[0]
    via = "glob"
    if promote_to_paper:
        rel = _rel(run_dir, path).replace("\\", "/")
        # Promote deep PDFs (not already under top-level paper/) to paper/main.pdf.
        if not (rel.startswith("paper/") or rel.startswith("artifacts/paper/")):
            promoted = promote_paper_pdf_to_canonical(run_dir, path)
            if promoted is not None:
                path = promoted
                via = "glob_promoted"
    return FoundArtifact("paper_pdf", path, _rel(run_dir, path), path.stat().st_size, via)


def find_paper_md(run_dir: Path) -> FoundArtifact | None:
    """Markdown paper drafts (e.g. DeepScientist paper/draft/*.md)."""
    for rel in PAPER_MD_CANDIDATES:
        path = run_dir / rel
        if _nonempty_file(path, min_bytes=200) and not _paper_path_blocked(rel):
            resolved = path.resolve()
            return FoundArtifact("paper_md", resolved, _rel(run_dir, resolved), resolved.stat().st_size, "candidate")

    hits: list[Path] = []
    for pattern in PAPER_MD_GLOBS:
        for path in run_dir.glob(pattern):
            if not _nonempty_file(path, min_bytes=200):
                continue
            try:
                rel_raw = str(path.relative_to(run_dir))
            except ValueError:
                continue
            if _paper_path_blocked(rel_raw) or _is_paper_md_auxiliary(rel_raw, path):
                continue
            resolved = path.resolve()
            rel = _rel(run_dir, resolved)
            if _paper_path_blocked(rel) or _is_paper_md_auxiliary(rel, resolved):
                continue
            hits.append(resolved)
    if not hits:
        return None
    hits.sort(key=lambda p: _prefer_paper_md(run_dir, p))
    path = hits[0]
    return FoundArtifact("paper_md", path, _rel(run_dir, path), path.stat().st_size, "glob")


def _is_likely_paper_json(path: Path) -> bool:
    """Heuristic: structured draft/research summary with manuscript-like fields."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    if len(text) < 200:
        return False
    low = text.lower()
    if not any(k in low for k in ('"experiment_description"', '"significance"', '"description"', '"key_numerical_results"')):
        return False
    return any(k in low for k in ("overall_plan", "abstract", "results", "experiment"))


def find_paper_json(run_dir: Path) -> FoundArtifact | None:
    """JSON draft summaries used by some agent frameworks when no TeX/Markdown exists."""
    for rel in PAPER_JSON_CANDIDATES:
        path = run_dir / rel
        if _nonempty_file(path, min_bytes=200) and not _paper_path_blocked(rel) and _is_likely_paper_json(path):
            resolved = path.resolve()
            return FoundArtifact("paper_json", resolved, _rel(run_dir, resolved), resolved.stat().st_size, "candidate")

    hits: list[Path] = []
    for pattern in PAPER_JSON_GLOBS:
        for path in run_dir.glob(pattern):
            if not _nonempty_file(path, min_bytes=200):
                continue
            try:
                rel_raw = str(path.relative_to(run_dir))
            except ValueError:
                continue
            if _paper_path_blocked(rel_raw):
                continue
            resolved = path.resolve()
            rel = _rel(run_dir, resolved)
            if _paper_path_blocked(rel) or not _is_likely_paper_json(resolved):
                continue
            hits.append(resolved)
    if not hits:
        return None
    hits.sort(key=lambda p: _prefer_paperish(run_dir, p))
    path = hits[0]
    return FoundArtifact("paper_json", path, _rel(run_dir, path), path.stat().st_size, "glob")


def find_paper_document(run_dir: Path) -> FoundArtifact | None:
    """Best textual paper body for LLM axes: real TeX first, else markdown draft."""
    tex = find_tex(run_dir)
    if tex is not None:
        return tex
    md = find_paper_md(run_dir)
    if md is not None:
        return md
    return find_paper_json(run_dir)


def find_bonus(run_dir: Path) -> dict[str, FoundArtifact | None]:
    out: dict[str, FoundArtifact | None] = {}
    for name, patterns in BONUS_SPECS.items():
        hit: Path | None = None
        via = "candidate"
        exact = [p for p in patterns if "*" not in p and "?" not in p]
        globs = [p for p in patterns if "*" in p or "?" in p]
        hit = _first_existing(run_dir, exact, min_bytes=10)
        if hit is not None and _noise_path_blocked(_rel(run_dir, hit)):
            hit = None
        if hit is None and globs:
            hit = _glob_first(run_dir, globs, min_bytes=10, blocked=_noise_path_blocked)
            via = "glob"
        if hit is None:
            out[name] = None
        else:
            out[name] = FoundArtifact(name, hit, _rel(run_dir, hit), hit.stat().st_size, via)
    return out


def _normalize_framework_key(fw: str) -> str:
    """Map manifest / directory aliases onto evaluation profile keys."""
    fw_norm = fw.strip().lower().replace("-", "_")
    if not fw_norm:
        return ""
    aliases = {
        "autoresearchclaw": "researchclaw",
        "auto_researchclaw": "researchclaw",
        "ai_scientist_v2": "ai_scientist",
        "aiscientist": "ai_scientist",
        "ai_scientist_v1": "ai_scientist",
        "tiny-scientist": "tiny_scientist",
        "tinyscientist": "tiny_scientist",
        "deep_scientist": "deepscientist",
        "evo_scientist": "evoscientist",
        "ai_researcher": "airesearcher",
    }
    if fw_norm in aliases:
        return aliases[fw_norm]
    # Prefix forms: "ai_scientist_v2_bench" → ai_scientist, etc.
    for key in (
        "tiny_scientist",
        "ai_scientist",
        "airesearcher",
        "deepscientist",
        "evoscientist",
        "researchclaw",
        "aris",
    ):
        if fw_norm == key or fw_norm.startswith(key + "_"):
            return key
    return fw_norm


def detect_framework(run_dir: Path, manifest: dict | None = None) -> str:
    manifest = manifest if manifest is not None else _load_manifest(run_dir)
    fw = str(manifest.get("framework") or "").strip()
    if fw:
        mapped = _normalize_framework_key(fw)
        return mapped or "unknown"
    name = run_dir.name.lower()
    for key in (
        "aris",
        "evoscientist",
        "researchclaw",
        "deepscientist",
        "tiny_scientist",
        "ai_scientist",
        "airesearcher",
    ):
        if name.startswith(key):
            return key
    return "unknown"
