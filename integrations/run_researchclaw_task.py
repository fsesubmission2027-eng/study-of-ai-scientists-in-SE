#!/usr/bin/env python3
"""Run AutoResearchClaw on an ai_scientist_inputs task (full 23-stage pipeline).

Default ``research.topic`` is the task Research Question only (ARC-native).
Background, dataset paths, novelty policy, and workflow notes go into
``prompts.custom_file`` / ``prompts.extra_prompts.<stage>`` via the per-run
prompt pack. ``research.domains`` is set to software-engineering.

Stages dataset_candidate/ from task.env EXTRA_VOLUME_* (aligned with other tools),
bind-mounts large datasets into per-run HOME/.cache/datasets for ARC's inner Docker
(/workspace/data/), runs researchclaw inside TaskSandbox, and archives idea /
code / results / paper under artifacts/. Does not modify AutoResearchClaw upstream.

Optional ``--skip-literature`` runs Stages 1–2, converts ``related_work.json`` →
``stage-05/shortlist.jsonl``, then resumes at ``KNOWLEDGE_EXTRACT`` (skips Stages 3–5 only).

Pass ``--run-dir <existing researchclaw_*>`` to continue an interrupted run: refreshes
metering/config, reuses artifacts/checkpoints, and appends ``researchclaw_run.log``.
When ``checkpoint.json`` exists, the integration passes ``researchclaw run --resume``
(unless ``--from-stage`` is set explicitly).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
INTEGRATIONS_ROOT = BENCHMARK_ROOT / "integrations"
ORCHESTRATOR_ROOT = BENCHMARK_ROOT / "orchestrator"
AI_SCIENTIST_ROOT = BENCHMARK_ROOT.parent / "AI-Scientist-v2"
DEFAULT_RC_ROOT = Path.home() / "AutoResearchClaw"
DEFAULT_RC_CONFIG_TEMPLATE = INTEGRATIONS_ROOT / "researchclaw_config.benchmark.yaml"
DEFAULT_DOCKER_IMAGE = "researchclaw/benchmark:latest"
DEFAULT_DOCKERFILE = BENCHMARK_ROOT / "docker" / "Dockerfile.researchclaw-lite"
DEFAULT_RC_DOCKERFILE = DEFAULT_RC_ROOT / "researchclaw" / "docker" / "Dockerfile"
DEFAULT_MODEL = "deepseek-v4-pro-0813"  # fallback if credentials file missing

sys.path.insert(0, str(ORCHESTRATOR_ROOT))
sys.path.insert(0, str(INTEGRATIONS_ROOT))

from agent_container import (  # noqa: E402
    BENCHMARK_AGENT_NATIVE_ENV,
    build_container_env,
    launch_agent,
    normalize_umodelverse_model,
    preflight_binary,
    preflight_llm_model_chain,
    preflight_scrub_proxy,
    workdir_for_run,
)
from agent_task_document import build_agent_task_document  # noqa: E402
from path_alignment import (  # noqa: E402
    align_run_dataset_paths,
    load_task_env,
    preflight_dataset_volumes,
    sync_arc_dataset_cache,
)
from researchclaw_literature_seed import (  # noqa: E402
    RelatedWorkError,
    find_related_work_path,
    seed_literature_for_skip,
)
from researchclaw_prompt_pack import (  # noqa: E402
    resolve_research_domains,
    write_researchclaw_prompt_pack,
)
from sandbox import TaskSandbox  # noqa: E402
from seed_staging import stage_seeds_for_agent  # noqa: E402
from benchmark_credentials import (  # noqa: E402
    apply_benchmark_credentials,
    credentials_file_path,
    require_llm_api_key,
    resolve_model,
    resolve_model_list,
)
from task_prompt import (  # noqa: E402
    load_task1_from_md,
    load_task_background_rq_from_md,
    load_research_question_from_md,
)
from transient_retry import (  # noqa: E402
    add_transient_retry_arguments,
    resolve_existing_run_dir,
    retry_launch_on_transient,
)

DEFAULT_SKIP_LIT_FROM_STAGE = "KNOWLEDGE_EXTRACT"
RUN_SCOPING_TO_STAGE = "PROBLEM_DECOMPOSE"

_STAGE_NAMES_BY_ID: dict[int, str] = {
    1: "TOPIC_INIT",
    2: "PROBLEM_DECOMPOSE",
    3: "SEARCH_STRATEGY",
    4: "LITERATURE_COLLECT",
    5: "LITERATURE_SCREEN",
    6: "KNOWLEDGE_EXTRACT",
    7: "SYNTHESIS",
    8: "HYPOTHESIS_GEN",
    9: "EXPERIMENT_DESIGN",
    10: "CODE_GENERATION",
    11: "RESOURCE_PLANNING",
    12: "EXPERIMENT_RUN",
    13: "ITERATIVE_REFINE",
    14: "RESULT_ANALYSIS",
    15: "RESEARCH_DECISION",
    16: "PAPER_OUTLINE",
    17: "PAPER_DRAFT",
    18: "PEER_REVIEW",
    19: "PAPER_REVISION",
    20: "QUALITY_GATE",
    21: "KNOWLEDGE_ARCHIVE",
    22: "EXPORT_PUBLISH",
    23: "CITATION_VERIFY",
}


def build_researchclaw_run_args(
    config_path: Path,
    run_root: Path,
    *,
    skip_preflight: bool,
    from_stage: str | None = None,
    to_stage: str | None = None,
    resume: bool = False,
) -> list[str]:
    """Build ``researchclaw run`` argument list (without the binary prefix)."""
    rc_args = [
        "run",
        "--config",
        str(config_path),
        "--output",
        str(run_root),
        "--auto-approve",
        "--mode",
        "full-auto",
    ]
    if resume:
        rc_args.append("--resume")
    elif from_stage:
        rc_args.extend(["--from-stage", from_stage])
    if to_stage:
        rc_args.extend(["--to-stage", to_stage])
    if skip_preflight:
        rc_args.append("--skip-preflight")
    return rc_args


def resolve_task_topic(
    task_dir: Path,
    topic_mode: str,
    task_env: dict[str, str] | None = None,
) -> str:
    """Resolve ARC ``research.topic``.

    Default ``research-question`` is ARC-native (short RQ). Larger modes remain
    for ablation; task context lives in the prompt pack instead.
    """
    if topic_mode == "research-question":
        return load_research_question_from_md(task_dir)
    if topic_mode == "background-rq":
        return load_task_background_rq_from_md(task_dir)
    if topic_mode == "task-md":
        return load_task1_from_md(task_dir)
    if topic_mode in ("full", "brief"):
        env = task_env if task_env is not None else load_task_env(task_dir)
        return build_agent_task_document(task_dir, env)
    raise ValueError(f"Unknown topic_mode: {topic_mode!r}")


def prepare_run_layout(
    task_dir: Path,
    *,
    topic_mode: str,
    run_dir: Path | None = None,
) -> tuple[Path, str, dict[str, str], dict]:
    """Create or reuse run root, RQ topic, shared brief, and ARC prompt pack.

    Returns ``(run_root, topic, task_env, prompts_cfg)``.
    """
    task_env = load_task_env(task_dir)
    if run_dir is not None:
        run_root = run_dir.resolve()
        run_root.mkdir(parents=True, exist_ok=True)
        (run_root / ".container-home").mkdir(parents=True, exist_ok=True)
        task_input = run_root / "task_input.md"
        if task_input.is_file():
            task_intent = task_input.read_text(encoding="utf-8")
        else:
            task_intent = resolve_task_topic(task_dir, topic_mode, task_env)
            task_input.write_text(task_intent, encoding="utf-8")
        prompts_cfg = load_prompts_cfg_from_run(run_root)
        if not prompts_cfg:
            prompts_cfg = write_researchclaw_prompt_pack(run_root, task_dir, task_env)
        return run_root, task_intent, task_env, prompts_cfg

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_root = task_dir / "workspace" / f"researchclaw_{timestamp}"
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / ".container-home").mkdir(parents=True, exist_ok=True)
    prompts_cfg = write_researchclaw_prompt_pack(run_root, task_dir, task_env)
    task_intent = resolve_task_topic(task_dir, topic_mode, task_env)
    (run_root / "task_input.md").write_text(task_intent, encoding="utf-8")
    return run_root, task_intent, task_env, prompts_cfg


def load_prompts_cfg_from_run(run_root: Path) -> dict | None:
    """Load prompt pack paths from an existing ``config.arc.yaml`` when resuming."""
    config_path = run_root / "config.arc.yaml"
    if not config_path.is_file():
        return None
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    prompts = data.get("prompts") or {}
    custom_file = prompts.get("custom_file") or ""
    extra = prompts.get("extra_prompts") or {}
    if not custom_file and not extra:
        return None
    return {"custom_file": custom_file, "extra_prompts": extra}


def resolve_researchclaw_resume_plan(
    run_root: Path,
    *,
    from_stage_arg: str | None,
) -> tuple[str | None, bool, str]:
    """Return ``(from_stage, use_resume, label)`` for an existing run directory."""
    explicit = (from_stage_arg or "").strip() or None
    if explicit:
        return explicit, False, f"from-stage {explicit}"

    checkpoint_path = run_root / "checkpoint.json"
    summary_path = run_root / "pipeline_summary.json"
    paused_stage: str | None = None
    if summary_path.is_file():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            if summary.get("final_status") == "paused":
                stage_num = summary.get("final_stage")
                if isinstance(stage_num, int):
                    paused_stage = _STAGE_NAMES_BY_ID.get(stage_num)
        except (json.JSONDecodeError, OSError):
            paused_stage = None

    if checkpoint_path.is_file():
        label = "checkpoint resume"
        if paused_stage:
            label = f"checkpoint resume (paused at {paused_stage})"
        return None, True, label

    if paused_stage:
        return paused_stage, False, f"retry paused stage {paused_stage}"

    return None, False, "full pipeline (no checkpoint)"


def load_api_env(env: dict[str, str]) -> bool:
    merged = apply_benchmark_credentials(env)
    env.clear()
    env.update(merged)
    return require_llm_api_key(env)


def modelverse_model_name(model: str) -> str:
    return normalize_umodelverse_model(model)


def resolve_researchclaw_root() -> Path:
    for candidate in (
        os.environ.get("RESEARCHCLAW_ROOT"),
        str(DEFAULT_RC_ROOT),
    ):
        if candidate and (Path(candidate) / "researchclaw" / "cli.py").is_file():
            return Path(candidate).resolve()
    raise FileNotFoundError(
        "Could not find AutoResearchClaw checkout. Set RESEARCHCLAW_ROOT or clone to ~/AutoResearchClaw."
    )


def resolve_researchclaw_bin(rc_root: Path) -> str:
    for candidate in (
        os.environ.get("RESEARCHCLAW_BIN"),
        shutil.which("researchclaw"),
        str(rc_root / ".venv" / "bin" / "researchclaw"),
        str(Path.home() / "arc_env" / "bin" / "researchclaw"),
    ):
        if candidate and Path(candidate).exists():
            return str(Path(candidate).resolve())
    raise FileNotFoundError("Could not find `researchclaw` CLI on PATH.")


def resolve_researchclaw_python(rc_bin: str) -> str:
    """Prefer the arc_env interpreter so shebang→miniconda chains work in sandbox."""
    for candidate in (
        os.environ.get("RESEARCHCLAW_PYTHON"),
        str(Path(rc_bin).resolve().parent / "python3"),
        str(Path.home() / "arc_env" / "bin" / "python3"),
        shutil.which("python3"),
    ):
        if not candidate:
            continue
        path = Path(candidate)
        # Symlinks to miniconda are OK once miniconda is mounted.
        if path.exists() or path.is_symlink():
            return str(path)
    return "python3"


def build_researchclaw_cmd(rc_bin: str, args: list[str]) -> list[str]:
    """Invoke via explicit python to avoid broken shebang when mounts are incomplete."""
    python_bin = resolve_researchclaw_python(rc_bin)
    return [python_bin, rc_bin, *args]

def docker_image_exists(image: str) -> bool:
    proc = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
        text=True,
        check=False,
    )
    return proc.returncode == 0


def resolve_dockerfile(dockerfile: Path | None, *, image: str) -> tuple[Path, Path]:
    """Return (dockerfile_path, build_context_dir)."""
    if dockerfile is not None:
        df = dockerfile.resolve()
        if not df.is_file():
            raise FileNotFoundError(f"Missing Dockerfile: {df}")
        return df, df.parent

    if image in ("researchclaw/benchmark:latest", "researchclaw/benchmark"):
        if DEFAULT_DOCKERFILE.is_file():
            return DEFAULT_DOCKERFILE, DEFAULT_DOCKERFILE.parent

    rc_dockerfile = DEFAULT_RC_DOCKERFILE
    if rc_dockerfile.is_file():
        return rc_dockerfile, rc_dockerfile.parent

    raise FileNotFoundError(
        f"No Dockerfile found for image {image!r}. "
        f"Expected {DEFAULT_DOCKERFILE} or {rc_dockerfile}."
    )


def build_docker_image(image: str, dockerfile: Path | None = None) -> None:
    df_path, context = resolve_dockerfile(dockerfile, image=image)
    if df_path.name == "Dockerfile.researchclaw-lite":
        print(f"[docker] building lite benchmark image {image} (no dataset pre-cache)...")
    else:
        print(
            f"[docker] building {image} from upstream ARC Dockerfile "
            "(CUDA + PyTorch + dataset pre-cache — slow)...",
            file=sys.stderr,
        )
    proc = subprocess.run(
        ["docker", "build", "-f", str(df_path), "-t", image, str(context)],
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"docker build failed for {image}")


def stage_datasets(run_root: Path, task_dir: Path, task_env: dict[str, str]) -> Path:
    """Stage seeds under dataset_candidate/ and prepare ARC HOME dataset mount points."""
    seeds_src = task_dir / "seeds"
    seeds_dest = run_root / "dataset_candidate"
    seeds_dest.mkdir(parents=True, exist_ok=True)
    if seeds_src.is_dir():
        stage_seeds_for_agent(seeds_src, seeds_dest, task_env=task_env)
    align_run_dataset_paths(run_root, task_env)
    prepared = sync_arc_dataset_cache(run_root, task_env)
    for item in prepared:
        print(f"[datasets] {item}")
    return seeds_dest


def resolve_s2_api_key(env: dict[str, str]) -> str:
    return (env.get("S2_API_KEY") or os.environ.get("S2_API_KEY") or "").strip()


def write_run_config(
    run_root: Path,
    *,
    topic: str,
    model: str,
    base_url: str,
    experiment_mode: str,
    template_path: Path,
    docker_image: str,
    s2_api_key: str = "",
    domains: list[str] | None = None,
    prompts_cfg: dict | None = None,
    fallback_models: list[str] | None = None,
) -> Path:
    if not template_path.is_file():
        raise FileNotFoundError(f"Missing config template: {template_path}")
    text = template_path.read_text(encoding="utf-8")
    lines = text.splitlines()
    out: list[str] = []
    in_research = False
    in_llm = False
    in_experiment = False
    in_docker = False
    in_figure_agent = False
    topic_written = False
    domains_written = False
    skip_prompts = False
    for line in lines:
        # Drop template prompts: section; rewritten at the end from prompt pack.
        if line.strip() == "prompts:":
            skip_prompts = True
            continue
        if skip_prompts:
            if line.strip() == "" or line.startswith(" ") or line.startswith("\t"):
                continue
            skip_prompts = False

        stripped = line.strip()
        if stripped == "research:":
            in_research = True
            in_llm = False
            in_experiment = False
        elif stripped == "llm:":
            in_llm = True
            in_research = False
            in_experiment = False
        elif stripped == "experiment:":
            in_experiment = True
            in_research = False
            in_llm = False
            in_docker = False
            in_figure_agent = False
        elif in_experiment and stripped == "docker:":
            in_docker = True
            in_figure_agent = False
        elif in_experiment and stripped == "figure_agent:":
            in_figure_agent = True
            in_docker = False
        elif stripped.endswith(":") and not line.startswith("  "):
            in_research = in_llm = in_experiment = False
            in_docker = in_figure_agent = False
        elif (
            in_experiment
            and stripped.endswith(":")
            and line.startswith("  ")
            and not line.startswith("    ")
        ):
            in_docker = in_figure_agent = False

        if in_research and stripped.startswith("topic:"):
            out.append(f"  topic: {json.dumps(topic)}")
            topic_written = True
            continue
        if in_research and stripped == "domains:":
            domain_list = domains if domains is not None else resolve_research_domains()
            out.append("  domains:")
            for d in domain_list:
                out.append(f"    - {json.dumps(d)}")
            domains_written = True
            continue
        if in_research and domains_written and stripped.startswith("- "):
            continue
        if in_llm and stripped.startswith("base_url:"):
            out.append(f"  base_url: {json.dumps(base_url)}")
            continue
        if in_llm and stripped.startswith("primary_model:"):
            out.append(f"  primary_model: {json.dumps(model)}")
            continue
        if in_llm and stripped.startswith("s2_api_key:"):
            out.append(f"  s2_api_key: {json.dumps(s2_api_key)}")
            continue
        if in_llm and stripped.startswith("- "):
            continue
        if in_llm and stripped == "fallback_models:":
            out.append("  fallback_models:")
            for fb in fallback_models or [model]:
                out.append(f"    - {json.dumps(fb)}")
            continue
        if in_experiment and stripped.startswith("mode:"):
            out.append(f"  mode: {json.dumps(experiment_mode)}")
            continue
        if in_docker and stripped.startswith("image:"):
            out.append(f"    image: {json.dumps(docker_image)}")
            continue
        if in_figure_agent and stripped.startswith("docker_image:"):
            out.append(f"    docker_image: {json.dumps(docker_image)}")
            continue

        out.append(line)

    if not topic_written:
        raise RuntimeError("Failed to inject research.topic into benchmark config template")

    pc = prompts_cfg or {}
    custom_file = pc.get("custom_file") or ""
    extra = pc.get("extra_prompts") or {}
    out.append("")
    out.append("prompts:")
    out.append(f"  custom_file: {json.dumps(custom_file)}")
    out.append("  extra_prompts:")
    if extra:
        for stage, path in sorted(extra.items()):
            out.append(f"    {stage}: {json.dumps(path)}")
    else:
        out.append("    {}")

    config_path = run_root / "config.arc.yaml"
    config_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return config_path


class ExperimentSeedInjector(threading.Thread):
    """Copy small seeds + dataset layout hints into ARC experiment/ trees.

    Large EXTRA_VOLUME_* corpora are bind-mounted under HOME/.cache/datasets and
    appear inside ARC experiment Docker as /workspace/data/<name>/. Only small
    seed files and path metadata are copied into experiment/data/.
    """

    _LAYOUT_FILES = ("dataset_paths.json", "MOUNT_STATUS.json")
    _SKIP_NAMES = frozenset({"README.md"})

    def __init__(
        self,
        run_root: Path,
        seeds_src: Path,
        stop_event: threading.Event,
        *,
        large_dataset_names: set[str] | None = None,
    ) -> None:
        super().__init__(daemon=True)
        self.run_root = run_root
        self.seeds_src = seeds_src
        self.stop_event = stop_event
        self.large_dataset_names = large_dataset_names or set()
        self._injected: set[str] = set()

    def _copy_into(self, exp_dir: Path) -> None:
        key = str(exp_dir.resolve())
        if key in self._injected or not exp_dir.is_dir():
            return
        data_dir = exp_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        copied = False
        if self.seeds_src.is_dir():
            for item in self.seeds_src.iterdir():
                if item.name in self._SKIP_NAMES:
                    continue
                if item.name in self.large_dataset_names:
                    continue
                # Empty bind-mount placeholders on the host — never copy into packages.
                if item.is_dir() and not any(item.iterdir()):
                    continue
                dest = data_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dest, dirs_exist_ok=True)
                else:
                    shutil.copy2(item, dest)
                copied = True
                req_dest = exp_dir / item.name
                if item.name == "requirements.txt" and not req_dest.exists():
                    shutil.copy2(item, req_dest)
            for layout_name in self._LAYOUT_FILES:
                src = self.seeds_src / layout_name
                if src.is_file():
                    shutil.copy2(src, data_dir / layout_name)
                    copied = True
        if copied:
            self._injected.add(key)
            print(f"[seeds] staged into {data_dir}")

    def sync_all(self) -> None:
        for exp_dir in self.run_root.glob("stage-*/experiment"):
            self._copy_into(exp_dir)
        for exp_dir in self.run_root.glob("stage-*/experiment_v*"):
            if exp_dir.is_dir():
                self._copy_into(exp_dir)

    def run(self) -> None:
        while not self.stop_event.is_set():
            self.sync_all()
            self.stop_event.wait(3)


def _copy_tree(src: Path, dest: Path) -> None:
    if not src.exists():
        return
    dest.mkdir(parents=True, exist_ok=True)
    if src.is_file():
        shutil.copy2(src, dest / src.name)
        return
    for item in src.iterdir():
        out = dest / item.name
        if item.is_dir():
            shutil.copytree(item, out, dirs_exist_ok=True)
        else:
            shutil.copy2(item, out)


def _first_existing(*paths: Path) -> Path | None:
    for path in paths:
        if path.exists() and (path.is_file() or any(path.iterdir()) if path.is_dir() else False):
            return path
    return None


def collect_idea_artifact(run_root: Path, task_intent: str) -> dict:
    idea: dict[str, object] = {
        "source": "autoresearchclaw",
        "task_input": task_intent,
    }
    hyp = run_root / "stage-08" / "hypotheses.md"
    if hyp.is_file():
        idea["hypotheses_md"] = hyp.read_text(encoding="utf-8")
    novelty = run_root / "stage-08" / "novelty_report.json"
    if novelty.is_file():
        try:
            idea["novelty_report"] = json.loads(novelty.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            idea["novelty_report_raw"] = novelty.read_text(encoding="utf-8")
    exp_plan = run_root / "stage-09" / "exp_plan.yaml"
    if exp_plan.is_file():
        idea["exp_plan_yaml"] = exp_plan.read_text(encoding="utf-8")
    bench_plan = run_root / "stage-09" / "benchmark_plan.json"
    if bench_plan.is_file():
        try:
            idea["benchmark_plan"] = json.loads(bench_plan.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return idea


def collect_code_artifacts(run_root: Path) -> dict[str, str]:
    artifacts = run_root / "artifacts" / "code"
    artifacts.mkdir(parents=True, exist_ok=True)
    saved: dict[str, str] = {}

    code_src = _first_existing(
        run_root / "deliverables" / "code",
        run_root / "stage-22" / "code",
        run_root / "stage-10" / "experiment",
    )
    if code_src and code_src.is_dir():
        for item in code_src.rglob("*"):
            if not item.is_file():
                continue
            rel = item.relative_to(code_src)
            dest = artifacts / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)
            saved[str(rel)] = str(dest.relative_to(run_root))
    return saved


def collect_result_artifacts(run_root: Path) -> dict[str, object]:
    dest = run_root / "artifacts" / "results"
    dest.mkdir(parents=True, exist_ok=True)
    saved: dict[str, object] = {"runs": []}

    runs_src = _first_existing(
        run_root / "stage-12" / "runs",
        run_root / "stage-13" / "runs",
    )
    if runs_src and runs_src.is_dir():
        for item in sorted(runs_src.iterdir()):
            out = dest / item.name
            if item.is_dir():
                if out.exists():
                    shutil.rmtree(out)
                shutil.copytree(item, out)
            else:
                shutil.copy2(item, out)
            saved["runs"].append(str(out.relative_to(run_root)))

    for name in ("results.json", "analysis.md", "analysis.json"):
        for candidate in run_root.glob(f"stage-*/runs/{name}"):
            shutil.copy2(candidate, dest / candidate.parent.parent.name + "_" + name)
            saved[name] = str((dest / candidate.parent.parent.name + "_" + name).relative_to(run_root))

    return saved


def collect_paper_artifacts(run_root: Path) -> dict[str, str]:
    paper_root = run_root / "artifacts" / "paper"
    paper_root.mkdir(parents=True, exist_ok=True)
    saved: dict[str, str] = {}

    deliverables = run_root / "deliverables"
    for name in ("paper_final.md", "paper.tex", "references.bib"):
        src = deliverables / name
        if src.is_file():
            shutil.copy2(src, paper_root / name)
            saved[name] = str((paper_root / name).relative_to(run_root))

    for fallback, out_name in (
        (run_root / "stage-23" / "paper_final_verified.md", "paper_final.md"),
        (run_root / "stage-22" / "paper_final.md", "paper_final.md"),
        (run_root / "stage-22" / "paper.tex", "paper.tex"),
        (run_root / "stage-22" / "references.bib", "references.bib"),
    ):
        if out_name not in saved and fallback.is_file():
            shutil.copy2(fallback, paper_root / out_name)
            saved[out_name] = str((paper_root / out_name).relative_to(run_root))

    charts = deliverables / "charts"
    if charts.is_dir():
        charts_dest = paper_root / "charts"
        if charts_dest.exists():
            shutil.rmtree(charts_dest)
        shutil.copytree(charts, charts_dest)
        saved["charts"] = str(charts_dest.relative_to(run_root))

    benchmark_paper = run_root / "paper"
    benchmark_paper.mkdir(parents=True, exist_ok=True)
    if (paper_root / "paper_final.md").is_file():
        shutil.copy2(paper_root / "paper_final.md", benchmark_paper / "paper.md")
    if (paper_root / "paper.tex").is_file():
        shutil.copy2(paper_root / "paper.tex", benchmark_paper / "paper.tex")
    if (paper_root / "references.bib").is_file():
        shutil.copy2(paper_root / "references.bib", benchmark_paper / "references.bib")

    return saved


def write_run_manifest(
    run_root: Path,
    *,
    rc_returncode: int,
    idea: dict,
    code_files: dict[str, str],
    results: dict[str, object],
    paper_files: dict[str, str],
) -> Path:
    from run_metering import write_manifest_with_metering

    manifest = {
        "framework": "autoresearchclaw",
        "run_dir": str(run_root),
        "returncode": rc_returncode,
        "artifacts": {
            "idea": "artifacts/idea.json",
            "code": code_files,
            "results": results,
            "paper": paper_files,
        },
        "deliverables": str(run_root / "deliverables"),
        "status": {
            "pipeline": rc_returncode == 0,
            "idea": bool(idea.get("hypotheses_md") or idea.get("exp_plan_yaml")),
            "code": bool(code_files),
            "results": bool(results.get("runs")),
            "paper": bool(paper_files),
        },
    }
    manifest_path = run_root / "artifacts" / "manifest.json"
    log_path = run_root / "researchclaw_run.log"
    return write_manifest_with_metering(
        manifest_path,
        manifest,
        run_root,
        log_path=log_path if log_path.is_file() else None,
    )


def _large_dataset_names(task_env: dict[str, str]) -> set[str]:
    from path_alignment import dataset_symlink_targets

    return {name for name, _ in dataset_symlink_targets(task_env)}


def collect_artifacts_and_manifest(
    run_root: Path,
    *,
    task_intent: str,
    rc_returncode: int,
) -> Path:
    idea = collect_idea_artifact(run_root, task_intent)
    idea_path = run_root / "artifacts" / "idea.json"
    idea_path.parent.mkdir(parents=True, exist_ok=True)
    idea_path.write_text(json.dumps(idea, indent=2, ensure_ascii=False), encoding="utf-8")

    code_files = collect_code_artifacts(run_root)
    result_files = collect_result_artifacts(run_root)
    paper_files = collect_paper_artifacts(run_root)
    manifest_path = write_run_manifest(
        run_root,
        rc_returncode=rc_returncode,
        idea=idea,
        code_files=code_files,
        results=result_files,
        paper_files=paper_files,
    )
    print(f"[idea] artifacts -> {idea_path}")
    print(f"[code] artifacts -> {run_root / 'artifacts' / 'code'}")
    print(f"[results] artifacts -> {run_root / 'artifacts' / 'results'}")
    print(f"[paper] artifacts -> {run_root / 'artifacts' / 'paper'}")
    print(f"[manifest] {manifest_path}")
    return manifest_path


def run_pipeline(task_dir: Path, args: argparse.Namespace) -> int:
    if not shutil.which("docker"):
        print("docker is required for ResearchClaw experiment isolation.", file=sys.stderr)
        return 1

    try:
        rc_root = resolve_researchclaw_root()
        rc_bin = resolve_researchclaw_bin(rc_root)
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    docker_image = args.docker_image
    if args.experiment_mode == "docker" and not docker_image_exists(docker_image):
        if args.build_docker_image:
            try:
                build_docker_image(docker_image, Path(args.dockerfile) if args.dockerfile else None)
            except (FileNotFoundError, RuntimeError) as exc:
                print(str(exc), file=sys.stderr)
                return 1
        else:
            try:
                df_path, _ = resolve_dockerfile(
                    Path(args.dockerfile) if args.dockerfile else None,
                    image=docker_image,
                )
            except FileNotFoundError as exc:
                print(str(exc), file=sys.stderr)
                return 1
            print(
                f"Docker image {docker_image!r} not found. Build the lite image with:\n"
                f"  docker build -f {df_path} -t {docker_image} {df_path.parent}\n"
                "or pass --build-docker-image",
                file=sys.stderr,
            )
            return 1

    env = os.environ.copy()
    if not load_api_env(env):
        print(
            f"Missing OPENAI_API_KEY. Set llm.api_key in {credentials_file_path()} "
            "(or run: python3 integrations/benchmark_credentials.py --init)",
            file=sys.stderr,
        )
        return 1

    from agent_container import _real_upstream_base_url, apply_run_metering_to_env, scrub_base_url

    # Preflight against the real upstream (do not meter the ping).
    upstream_url = _real_upstream_base_url(env)
    base_url = scrub_base_url(env)
    model = modelverse_model_name(
        args.model or resolve_model("researchclaw", env=env)
    )
    fallback_models = [
        modelverse_model_name(item)
        for item in resolve_model_list("researchclaw", list_key="researchclaw_fallback", env=env)
    ]
    deduped: list[str] = []
    seen: set[str] = set()
    for item in fallback_models:
        if not item or item == model or item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    fallback_models = deduped or [model]
    s2_api_key = resolve_s2_api_key(env)

    rc_skip_preflight = bool(args.skip_preflight)
    if not rc_skip_preflight:
        chain: list[str] = []
        seen_chain: set[str] = set()
        for candidate in [model, *fallback_models]:
            if candidate and candidate not in seen_chain:
                seen_chain.add(candidate)
                chain.append(candidate)
        ok_llm, llm_msg = preflight_llm_model_chain(
            base_url=upstream_url,
            api_key=env.get("OPENAI_API_KEY", ""),
            models=chain,
        )
        print(f"[preflight] {llm_msg}")
        if not ok_llm:
            print(
                "[preflight] ResearchClaw built-in preflight uses max_tokens=1, which "
                "umodelverse rejects for openai/gpt-5-mini. Fix model/base_url or pass "
                "--skip-preflight to bypass.",
                file=sys.stderr,
            )
            return 1
        # Avoid ARC preflight (max_tokens=1); benchmark preflight already passed.
        rc_skip_preflight = True

    try:
        existing_run = resolve_existing_run_dir(getattr(args, "run_dir", None))
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    run_root, task_intent, task_env, prompts_cfg = prepare_run_layout(
        task_dir,
        topic_mode=args.topic_mode,
        run_dir=existing_run,
    )
    if existing_run is not None:
        print(f"[prepare] reusing run_dir={run_root}")
    # Route ResearchClaw llm.base_url through the metering proxy for this run.
    env = apply_run_metering_to_env(env, run_root=run_root, for_container=True)
    base_url = scrub_base_url(env)
    seeds_dest = stage_datasets(run_root, task_dir, task_env)
    domains = resolve_research_domains(task_dir)
    config_path = write_run_config(
        run_root,
        topic=task_intent,
        model=model,
        base_url=base_url,
        experiment_mode=args.experiment_mode,
        template_path=Path(args.config_template),
        docker_image=docker_image,
        s2_api_key=s2_api_key,
        domains=domains,
        prompts_cfg=prompts_cfg,
        fallback_models=fallback_models,
    )
    docker_workdir = workdir_for_run(run_root)

    from_stage = (getattr(args, "from_stage", None) or "").strip() or None
    skip_literature = bool(getattr(args, "skip_literature", False))
    related_work_arg = getattr(args, "related_work", None)
    related_work_path = Path(related_work_arg) if related_work_arg else None

    run_phases: list[tuple[str | None, str | None, str, bool]] = []
    if existing_run is not None:
        phase_from, use_resume, resume_label = resolve_researchclaw_resume_plan(
            run_root,
            from_stage_arg=from_stage,
        )
        if not use_resume and phase_from is None and not (run_root / "checkpoint.json").is_file():
            print(
                "[resume] no checkpoint.json in run_dir; starting full pipeline in-place",
                file=sys.stderr,
            )
        run_phases.append((phase_from, None, resume_label, use_resume))
        use_two_phase = False
        resume_from_knowledge = False
    else:
        # --skip-literature: run 1–2, seed shortlist, resume at 6 (skip 3–5 only).
        use_two_phase = skip_literature and (
            not from_stage or from_stage == DEFAULT_SKIP_LIT_FROM_STAGE
        )
        resume_from_knowledge = (
            from_stage == DEFAULT_SKIP_LIT_FROM_STAGE and not use_two_phase
        )

        if resume_from_knowledge:
            try:
                shortlist_path, lit_entries, lit_warnings = seed_literature_for_skip(
                    task_dir,
                    run_root,
                    related_work_path=related_work_path,
                    min_papers=1,
                    write_stubs=True,
                    topic=task_intent,
                    write_goal_stub=True,
                )
            except RelatedWorkError as exc:
                print(f"[literature] {exc}", file=sys.stderr)
                return 1
            for w in lit_warnings[:30]:
                print(f"[literature] warn: {w}")
            if len(lit_warnings) > 30:
                print(f"[literature] warn: ... {len(lit_warnings) - 30} more")
            print(
                f"[literature] seeded {len(lit_entries)} papers → {shortlist_path} "
                f"(from-stage={from_stage})"
            )
        elif skip_literature and not use_two_phase:
            # Custom --from-stage with --skip-literature: seed before single run.
            try:
                shortlist_path, lit_entries, lit_warnings = seed_literature_for_skip(
                    task_dir,
                    run_root,
                    related_work_path=related_work_path,
                    min_papers=1,
                    write_stubs=True,
                    topic=task_intent,
                    write_goal_stub=from_stage == DEFAULT_SKIP_LIT_FROM_STAGE,
                )
            except RelatedWorkError as exc:
                print(f"[literature] {exc}", file=sys.stderr)
                return 1
            for w in lit_warnings[:30]:
                print(f"[literature] warn: {w}")
            if len(lit_warnings) > 30:
                print(f"[literature] warn: ... {len(lit_warnings) - 30} more")
            print(
                f"[literature] seeded {len(lit_entries)} papers → {shortlist_path} "
                f"(from-stage={from_stage})"
            )
        elif related_work_path is not None:
            src = find_related_work_path(task_dir, related_work_path)
            if src is None:
                print(f"[literature] related-work path not found: {related_work_path}", file=sys.stderr)
                return 1
            print(
                f"[literature] note: {src} present but --skip-literature/--from-stage "
                f"{DEFAULT_SKIP_LIT_FROM_STAGE} not set; open search will still run",
                file=sys.stderr,
            )

        if use_two_phase:
            run_phases.append(
                (None, RUN_SCOPING_TO_STAGE, f"Stages 1–2 ({RUN_SCOPING_TO_STAGE})", False)
            )
            run_phases.append(
                (
                    DEFAULT_SKIP_LIT_FROM_STAGE,
                    None,
                    f"Stages 6+ ({DEFAULT_SKIP_LIT_FROM_STAGE})",
                    False,
                )
            )
        else:
            run_phases.append((from_stage, None, "full pipeline", False))

    for key in ("OPENAI_API_KEY", "OPENAI_API_BASE", "OPENAI_BASE_URL", "API_BASE_URL", "S2_API_KEY"):
        if key in env:
            os.environ[key] = env[key]

    stop_event = threading.Event()
    seed_injector = ExperimentSeedInjector(
        run_root,
        seeds_dest,
        stop_event,
        large_dataset_names=_large_dataset_names(task_env),
    )
    seed_injector.start()

    s2_status = "set" if s2_api_key else f"missing (add semantic_scholar.api_key to {credentials_file_path()})"
    print(f"[config] model={model}")
    print(f"[config] base_url={base_url}")
    print(f"[config] s2_api_key={s2_status}")
    print(f"[config] experiment_mode={args.experiment_mode}")
    print(f"[config] run_root={run_root}")
    print(f"[config] dataset_candidate={seeds_dest}")
    print(f"[config] topic_mode={args.topic_mode}")
    print(f"[config] topic_chars={len(task_intent)}")
    print(f"[config] domains={domains}")
    print(f"[config] custom_file={prompts_cfg.get('custom_file')}")
    print(f"[config] extra_prompt_stages={len(prompts_cfg.get('extra_prompts') or {})}")
    print(f"[config] workdir={docker_workdir}")
    if existing_run is not None:
        print(f"[config] resume={run_phases[0][3] if run_phases else False}")
        print(f"[config] resume_label={run_phases[0][2] if run_phases else 'n/a'}")
    elif use_two_phase:
        print(
            f"[config] skip_literature=True → run {RUN_SCOPING_TO_STAGE}, "
            f"seed shortlist, resume {DEFAULT_SKIP_LIT_FROM_STAGE}"
        )
    else:
        print(f"[config] from_stage={from_stage or 'TOPIC_INIT'}")
        print(f"[config] skip_literature={skip_literature}")

    sandbox = TaskSandbox(task_dir, agent_tool="researchclaw")
    returncode = 1
    try:
        container_id = sandbox.start(agent_tool="researchclaw", run_root=run_root)
        print(f"[sandbox] container_id={container_id}")

        ok_bin, bin_msg = preflight_binary(container_id, rc_bin, cwd=run_root)
        print(f"[preflight] {bin_msg}")
        if not ok_bin:
            return 1

        rc_python = resolve_researchclaw_python(rc_bin)
        ok_py, py_msg = preflight_binary(container_id, rc_python, cwd=run_root)
        print(f"[preflight] researchclaw python: {py_msg}")
        if not ok_py:
            return 1

        # Actually execute once — catches broken shebang→miniconda chains.
        probe = subprocess.run(
            [
                "docker",
                "exec",
                "-w",
                docker_workdir,
                container_id,
                rc_python,
                rc_bin,
                "--help",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
            stdin=subprocess.DEVNULL,
        )
        if probe.returncode != 0:
            detail = (probe.stderr or probe.stdout or "").strip().splitlines()
            print(
                "[preflight] researchclaw exec failed: "
                + (detail[-1] if detail else f"exit {probe.returncode}"),
                file=sys.stderr,
            )
            return 1
        print("[preflight] researchclaw exec OK")

        ok_scrub, scrub_msg = preflight_scrub_proxy(container_id, base_url=base_url)
        print(f"[preflight] {scrub_msg}")
        if not ok_scrub:
            return 1

        ok_data, data_msg = preflight_dataset_volumes(
            container_id, sandbox.env, run_root=run_root
        )
        print(f"[preflight] {data_msg}")
        if not ok_data:
            return 1

        # Confirm ARC experiment cache mounts (HOME/.cache/datasets/<name>).
        for name in _large_dataset_names(sandbox.env):
            arc_path = run_root / ".container-home" / ".cache" / "datasets" / name
            probe = (
                "import os,sys;"
                f"sys.exit(0 if os.path.isdir({str(arc_path)!r}) and os.listdir({str(arc_path)!r}) else 1)"
            )
            probe_proc = subprocess.run(
                ["docker", "exec", container_id, "python3", "-c", probe],
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                stdin=subprocess.DEVNULL,
            )
            if probe_proc.returncode != 0:
                print(
                    f"[preflight] ARC dataset cache empty/missing: {arc_path}",
                    file=sys.stderr,
                )
                return 1
            print(f"[preflight] ARC cache OK ({name} -> /workspace/data/{name}/)")

        container_env = build_container_env(
            env,
            agent_tool="researchclaw",
            run_root=run_root,
            task_env=sandbox.env,
            extra={BENCHMARK_AGENT_NATIVE_ENV: "1"},
        )
        log_path = run_root / "researchclaw_run.log"
        for phase_idx, (phase_from, phase_to, phase_label, use_resume) in enumerate(
            run_phases, start=1
        ):
            if use_two_phase and phase_from == DEFAULT_SKIP_LIT_FROM_STAGE:
                try:
                    shortlist_path, lit_entries, lit_warnings = seed_literature_for_skip(
                        task_dir,
                        run_root,
                        related_work_path=related_work_path,
                        min_papers=1,
                        write_stubs=True,
                        topic=task_intent,
                        write_goal_stub=False,
                    )
                except RelatedWorkError as exc:
                    print(f"[literature] {exc}", file=sys.stderr)
                    returncode = 1
                    break
                for w in lit_warnings[:30]:
                    print(f"[literature] warn: {w}")
                if len(lit_warnings) > 30:
                    print(f"[literature] warn: ... {len(lit_warnings) - 30} more")
                print(
                    f"[literature] seeded {len(lit_entries)} papers → {shortlist_path} "
                    f"(after {RUN_SCOPING_TO_STAGE})"
                )

            rc_args = build_researchclaw_run_args(
                config_path,
                run_root,
                skip_preflight=rc_skip_preflight,
                from_stage=phase_from,
                to_stage=phase_to,
                resume=use_resume,
            )
            cmd = build_researchclaw_cmd(rc_bin, rc_args)
            if use_two_phase:
                print(f"[launch] phase {phase_idx}/{len(run_phases)}: {phase_label}")
            elif existing_run is not None:
                print(f"[launch] resume: {phase_label}")
            print("[launch]", " ".join(cmd))
            append_log = bool(existing_run) or (use_two_phase and phase_idx > 1)
            if append_log:
                with log_path.open("a", encoding="utf-8") as log_file:
                    if existing_run and phase_idx == 1:
                        log_file.write(
                            f"\n\n===== Benchmark resume "
                            f"{datetime.now().isoformat(timespec='seconds')} "
                            f"({phase_label}) =====\n\n"
                        )
                    elif use_two_phase:
                        log_file.write(
                            f"\n\n===== Phase {phase_idx}/{len(run_phases)}: "
                            f"{phase_label} =====\n\n"
                        )
            returncode = launch_agent(
                container_id=container_id,
                cmd=cmd,
                cwd=Path(docker_workdir),
                env=container_env,
                log_path=log_path,
                append=append_log,
            )
            if returncode != 0:
                phase_cmd = list(cmd)
                returncode = retry_launch_on_transient(
                    returncode=returncode,
                    log_path=log_path,
                    args=args,
                    label=f"researchclaw:{phase_label}",
                    relaunch=lambda phase_cmd=phase_cmd: launch_agent(
                        container_id=container_id,
                        cmd=phase_cmd,
                        cwd=Path(docker_workdir),
                        env=container_env,
                        log_path=log_path,
                        append=True,
                    ),
                )
            if returncode != 0:
                print(
                    f"[researchclaw] {phase_label} exited with code {returncode}. "
                    f"See {log_path}",
                    file=sys.stderr,
                )
                break
    finally:
        stop_event.set()
        seed_injector.join(timeout=5)
        seed_injector.sync_all()
        try:
            sandbox.destroy()
        except Exception as exc:  # noqa: BLE001
            print(f"[sandbox] destroy warning: {exc}", file=sys.stderr)

    collect_artifacts_and_manifest(
        run_root, task_intent=task_intent, rc_returncode=returncode
    )
    print(f"Done. Full run: {run_root}")
    return returncode


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Run AutoResearchClaw on a benchmark task: full pipeline, Modelverse LLM, "
            "Docker experiment isolation, artifacts/ for idea/code/results/paper."
        )
    )
    parser.add_argument(
        "--task-dir",
        default=str(Path.home() / "ai_scientist_inputs" / "ASE-2025-004_predicting_recheck_success_in_continuous"),
        help="Path to task directory under ai_scientist_inputs/",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override llm model from benchmark_credentials.yaml (researchclaw.models.researchclaw)",
    )
    parser.add_argument(
        "--config-template",
        default=str(DEFAULT_RC_CONFIG_TEMPLATE),
        help="Benchmark ResearchClaw config template",
    )
    parser.add_argument(
        "--experiment-mode",
        choices=("docker", "sandbox"),
        default="docker",
        help="Experiment executor: docker isolates code in ResearchClaw container (default)",
    )
    parser.add_argument(
        "--docker-image",
        default=DEFAULT_DOCKER_IMAGE,
        help="Docker image for experiment.mode=docker (default: researchclaw/benchmark:latest)",
    )
    parser.add_argument(
        "--dockerfile",
        default="",
        help=(
            "Dockerfile path (default: ai_scientist_benchmark/docker/Dockerfile.researchclaw-lite; "
            "upstream ARC Dockerfile only if you set --docker-image researchclaw/experiment:latest)"
        ),
    )
    parser.add_argument(
        "--build-docker-image",
        action="store_true",
        help="Build the experiment image if missing (lite benchmark image by default)",
    )
    parser.add_argument(
        "--full-arc-image",
        action="store_true",
        help="Use upstream researchclaw/experiment:latest (CUDA + dataset pre-cache; slow build)",
    )
    parser.add_argument(
        "--topic-mode",
        choices=("research-question", "background-rq", "task-md", "full", "brief"),
        default="research-question",
        help=(
            "ARC research.topic content. Default research-question = RQ only (ARC-native). "
            "Background/Experiment Setup/Dataset/policy go into prompts.custom_file + "
            "extra_prompts.<stage>. full/brief still dump the shared agent brief into topic "
            "(ablation only)."
        ),
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip LLM preflight entirely (benchmark and ResearchClaw)",
    )
    parser.add_argument(
        "--skip-literature",
        action="store_true",
        help=(
            "Skip ARC Stages 3–5 only: run Stages 1–2, convert task related_work.json → "
            "stage-05/shortlist.jsonl, then resume at KNOWLEDGE_EXTRACT"
        ),
    )
    parser.add_argument(
        "--from-stage",
        default="",
        help=(
            "Pass through to researchclaw run --from-stage (e.g. KNOWLEDGE_EXTRACT). "
            "When set to KNOWLEDGE_EXTRACT without --skip-literature, related_work.json "
            "is seeded and Stages 1–5 are skipped. With --run-dir, overrides automatic "
            "checkpoint resume."
        ),
    )
    parser.add_argument(
        "--run-dir",
        default=None,
        help=(
            "Reuse an existing researchclaw_* run directory. Refreshes metering/config, "
            "appends researchclaw_run.log, and passes --resume when checkpoint.json exists."
        ),
    )
    parser.add_argument(
        "--related-work",
        default="",
        help=(
            "Path to related_work.json / shortlist.json(l) "
            "(default: <task-dir>/related_work.json)"
        ),
    )
    add_transient_retry_arguments(parser)
    args = parser.parse_args()
    if args.full_arc_image:
        args.docker_image = "researchclaw/experiment:latest"
        if not args.dockerfile:
            args.dockerfile = str(DEFAULT_RC_DOCKERFILE)
    args.related_work = args.related_work or None

    task_dir = Path(args.task_dir).resolve()
    if not task_dir.is_dir():
        print(f"Task directory not found: {task_dir}", file=sys.stderr)
        return 1

    return run_pipeline(task_dir, args)


if __name__ == "__main__":
    raise SystemExit(main())
