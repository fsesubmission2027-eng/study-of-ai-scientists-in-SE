"""Bootstrap EvoScientist research skills for benchmark runs (no custom agent prompt)."""

from __future__ import annotations

from pathlib import Path

from agent_task_document import (
    BENCHMARK_RESUME_CONTINUATION_BRIEF,
    build_agent_task_document,
)

# Full official EvoSkills pack (EvoScientist/EvoSkills repo, skills/ directory).
OFFICIAL_EVOSKILLS_PACK = "EvoScientist/EvoSkills@skills"

# Not workflow steps — only unattended-run constraints required by EvoSci -p single-shot mode
# and experiment-pipeline's Lite/More Effort gate.
BENCHMARK_AUTONOMY_SECTION = """## Benchmark run mode

This is an unattended ai_scientist_benchmark run (`--auto-mode`, `--auto-approve`).
- Do not ask the user for choices or confirmation; use reasonable defaults.
- For code generation, use **Lite** mode (delegate implementation to code-agent).
- Continue until expected artifacts exist or document blockers in persisted workspace artifacts."""


def build_evoscientist_launch_prompt(
    task_dir: Path,
    task_env: dict[str, str] | None = None,
) -> str:
    """Task + dataset + minimal autonomy overlay for benchmark launches."""
    return build_agent_task_document(
        task_dir,
        task_env,
        extra_sections=[BENCHMARK_AUTONOMY_SECTION],
    )


def build_resume_continuation_prompt(task_dir: Path) -> str:
    from metrics_schema import format_required_metrics_prompt_note_for_task

    metrics_note = format_required_metrics_prompt_note_for_task(task_dir)
    return (
        f"{BENCHMARK_RESUME_CONTINUATION_BRIEF}\n"
        "Hard constraints:\n"
        "- Do **not** ask the user for choices/confirmation; use reasonable defaults.\n"
        "- Do **not** propose optional large-scale follow-up experiments while benchmark "
        "deliverables are incomplete.\n"
        "- If background experiments are still running, wait/poll until their result files exist "
        "before Goodbye; do not exit after only announcing that you will monitor.\n"
        "- Write durable artifacts under the host-aligned workdir paths "
        "(results/, project/, paper/, plan.md|todos.md, README.md).\n"
        "Pending gates: use Lite code-generation mode when delegating implementation.\n"
        f"{metrics_note}\n"
    )


DEFAULT_MAX_AUTO_RESUME_ROUNDS = 5
DEFAULT_MAX_IDENTICAL_RESUME_ROUNDS = 2
DEFAULT_BG_WAIT_SEC = 3600.0
DEFAULT_BG_POLL_SEC = 20.0


def _installed_skill_names(skills_dir: Path) -> list[str]:
    if not skills_dir.is_dir():
        return []
    return sorted(
        child.name
        for child in skills_dir.iterdir()
        if child.is_dir() and (child / "SKILL.md").is_file()
    )


def install_research_skills(run_root: Path) -> tuple[bool, str]:
    """Pre-install the full official EvoSkills pack into run_root/skills/."""
    dest = run_root / "skills"
    dest.mkdir(parents=True, exist_ok=True)
    try:
        from EvoScientist.tools.skills_manager import install_skill
    except ImportError as exc:
        return False, f"EvoScientist package not importable for skill install: {exc}"

    result = install_skill(OFFICIAL_EVOSKILLS_PACK, dest_dir=str(dest), global_install=False)
    if not result.get("success"):
        return False, f"skill install failed: {result.get('error', 'unknown error')}"

    if result.get("batch"):
        installed = result.get("installed") or []
        failed = result.get("failed") or []
        if failed:
            failed_desc = "; ".join(
                f"{item.get('name', '?')}: {item.get('error', 'unknown error')}" for item in failed
            )
            return False, f"official EvoSkills batch install failed: {failed_desc}"
        names = [str(item.get("name") or "?") for item in installed]
        return True, f"official EvoSkills OK ({len(names)} skills in {dest})"

    name = str(result.get("name") or "skill")
    return True, f"official EvoSkills OK ({name} in {dest})"


def preflight_research_skills(run_root: Path) -> tuple[bool, str]:
    """Verify official EvoSkills were installed under run_root/skills/."""
    dest = run_root / "skills"
    installed = _installed_skill_names(dest)
    if not installed:
        return False, f"no skills installed under {dest}"
    return True, f"skills preflight OK ({len(installed)} under skills/)"
