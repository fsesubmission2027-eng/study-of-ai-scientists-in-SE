#!/usr/bin/env python3
"""Run AI-Scientist-v2 on an ai_scientist_inputs task inside TaskSandbox (in-container)."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
AI_SCIENTIST_ROOT = BENCHMARK_ROOT.parent / "AI-Scientist-v2"
ORCHESTRATOR_ROOT = BENCHMARK_ROOT / "orchestrator"
INTEGRATIONS_ROOT = BENCHMARK_ROOT / "integrations"
BFTS_CONFIG_TEMPLATE = INTEGRATIONS_ROOT / "bfts_config.task.yaml"
DEFAULT_FEEDBACK_MODEL = "deepseek-v4-flash-0731"
DEFAULT_VLM_MODEL = "gpt-4o-mini"

sys.path.insert(0, str(ORCHESTRATOR_ROOT))
sys.path.insert(0, str(INTEGRATIONS_ROOT))

from agent_container import (  # noqa: E402
    BENCHMARK_AGENT_NATIVE_ENV,
    BENCHMARK_RUN_ROOT_ENV,
    build_container_env,
    launch_agent,
    load_api_env,
    preflight_binary,
    preflight_path,
    preflight_python,
    preflight_runtime_mounts,
    preflight_scrub_proxy,
    print_log_tail,
    resolve_aiscientist_python,
    reuse_benchmark_run_root,
    scrub_base_url,
)
from sandbox import TaskSandbox  # noqa: E402
from seed_staging import shell_copy_agent_seeds, stage_seeds_for_agent  # noqa: E402
from task_to_idea import write_task_idea_files  # noqa: E402
from benchmark_credentials import credentials_file_path, resolve_model  # noqa: E402
from transient_retry import add_transient_retry_arguments, retry_launch_on_transient  # noqa: E402


def benchmark_runtime_env(
    env: dict[str, str],
    *,
    run_root: Path,
) -> dict[str, str]:
    """Writable cache dirs for matplotlib/fontconfig inside read-only container mounts."""
    merged = env.copy()
    cache_root = run_root / ".cache"
    mpl_dir = run_root / ".matplotlib"
    cache_root.mkdir(parents=True, exist_ok=True)
    mpl_dir.mkdir(parents=True, exist_ok=True)
    merged.setdefault("MPLCONFIGDIR", str(mpl_dir))
    merged.setdefault("XDG_CACHE_HOME", str(cache_root))
    merged.setdefault("FC_CACHEDIR", str(cache_root / "fontconfig"))
    Path(merged["FC_CACHEDIR"]).mkdir(parents=True, exist_ok=True)
    return merged


def seed_task_workspace(sandbox: TaskSandbox, workspace_root: Path) -> None:
    seeds = sandbox.task_dir / "seeds"
    seeds_path = sandbox.seeds_path()
    req = f"{seeds_path}/requirements.txt"
    copy_cmd = shell_copy_agent_seeds(seeds, f"{workspace_root}/dataset_candidate")
    if (seeds / "requirements.txt").exists():
        sandbox.exec(f"python3 -m pip install -r {req}", workdir=str(workspace_root))
    sandbox.exec(
        f"mkdir -p {workspace_root}/dataset_candidate "
        f"{workspace_root}/project {workspace_root}/results {workspace_root}/paper && "
        f"{copy_cmd}",
        workdir=str(workspace_root),
    )


_WRITEUP_LATEX_TEMPLATES = ("blank_icbinb_latex", "blank_icml_latex")


def ensure_writeup_latex_templates(run_root: Path) -> None:
    """Expose AI-Scientist latex templates under run_root for relative-path writeup.

    ``perform_*_writeup.py`` copies from ``ai_scientist/blank_*_latex`` relative to
    cwd. Benchmark launches with ``cwd=run_root`` so experiments stay in the task
    workspace; symlink the upstream templates here instead of changing cwd.
    """
    dest_pkg = run_root / "ai_scientist"
    dest_pkg.mkdir(parents=True, exist_ok=True)
    linked: list[str] = []
    for name in _WRITEUP_LATEX_TEMPLATES:
        src = (AI_SCIENTIST_ROOT / "ai_scientist" / name).resolve()
        if not src.is_dir():
            print(f"[preflight] missing writeup template: {src}", file=sys.stderr)
            continue
        dest = dest_pkg / name
        if dest.is_symlink():
            if dest.resolve() == src:
                linked.append(name)
                continue
            dest.unlink()
        elif dest.exists():
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()
        dest.symlink_to(src, target_is_directory=True)
        linked.append(name)
    if linked:
        print(
            f"[preflight] writeup latex templates linked under {dest_pkg}: "
            + ", ".join(linked)
        )


def write_run_bfts_config(
    run_dir: Path,
    code_model: str,
    feedback_model: str,
    vlm_model: str,
) -> None:
    if not BFTS_CONFIG_TEMPLATE.is_file():
        raise FileNotFoundError(f"Missing BFTS template: {BFTS_CONFIG_TEMPLATE}")

    tool_call_sections = {"feedback", "select_node", "summary"}

    lines = BFTS_CONFIG_TEMPLATE.read_text(encoding="utf-8").splitlines()
    section = None
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped == "report:":
            section = "report"
        elif stripped == "code:":
            section = "code"
        elif stripped == "feedback:":
            section = "feedback"
        elif stripped == "select_node:":
            section = "select_node"
        elif stripped == "summary:":
            section = "summary"
        elif stripped == "vlm_feedback:":
            section = "vlm_feedback"
        elif stripped.endswith(":") and not line.startswith("  "):
            section = None

        if stripped.startswith("model:"):
            if section == "code":
                line = f"    model: {code_model}"
            elif section == "report":
                line = f"  model: {code_model}"
            elif section in tool_call_sections:
                line = f"    model: {feedback_model}"
            elif section == "vlm_feedback":
                line = f"    model: {vlm_model}"
        out.append(line)

    (run_dir / "bfts_config.yaml").write_text("\n".join(out) + "\n", encoding="utf-8")


def run_ideation(
    *,
    task_dir: Path,
    session_dir: Path,
    model: str,
    env: dict[str, str],
    num_reflections: int,
    max_num_generations: int,
) -> tuple[int, Path]:
    """Run v2 perform_ideation_temp_free; write session/idea.json."""
    from agent_task_document import build_agent_task_document
    from path_alignment import load_task_env

    sys.path.insert(0, str(AI_SCIENTIST_ROOT))
    from ai_scientist.api_config import load_env_file
    from ai_scientist.llm import create_client
    from ai_scientist.perform_ideation_temp_free import generate_temp_free_idea

    load_env_file()
    for key, value in env.items():
        if value is not None:
            os.environ.setdefault(key, value)

    task_env = load_task_env(task_dir)
    task_doc = build_agent_task_document(task_dir, task_env)
    workshop_path = session_dir / "ideation_workshop.md"
    workshop_path.write_text(f"# Research workshop\n\n{task_doc.strip()}\n", encoding="utf-8")

    idea_path = session_dir / "idea.json"
    ideation_log = session_dir / "ideation.log"
    print(f"[ideation] workshop={workshop_path} model={model} reflections={num_reflections}")

    with ideation_log.open("w", encoding="utf-8") as log_file:

        def _log(msg: str) -> None:
            print(msg)
            log_file.write(msg + "\n")
            log_file.flush()

        client, client_model = create_client(model)
        _log(f"[ideation] client model={client_model}")
        try:
            ideas = generate_temp_free_idea(
                idea_fname=str(idea_path),
                client=client,
                model=client_model,
                workshop_description=workshop_path.read_text(encoding="utf-8"),
                max_num_generations=max_num_generations,
                num_reflections=num_reflections,
                reload_ideas=False,
            )
        except Exception as exc:
            _log(f"[ideation] failed: {exc}")
            return 1, idea_path

        if not ideas:
            _log("[ideation] no ideas returned; falling back to task_to_idea seed")
            from task_to_idea import task_dir_to_idea

            ideas = [task_dir_to_idea(task_dir)]

        idea_path.write_text(json.dumps(ideas, indent=2, ensure_ascii=False), encoding="utf-8")
        _log(f"[ideation] wrote {idea_path}")
        return 0, idea_path


def prepare_run_layout(
    task_dir: Path, code_model: str, feedback_model: str, vlm_model: str
) -> tuple[Path, Path]:
    from agent_task_document import build_agent_task_document
    from path_alignment import load_task_env

    existing = reuse_benchmark_run_root()
    if existing is not None:
        session_dir = existing / "session"
        if session_dir.is_dir() and (existing / "bfts_config.yaml").is_file():
            ensure_writeup_latex_templates(existing)
            return existing, session_dir

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_root = task_dir / "workspace" / f"ai_scientist_{timestamp}"
    session_dir = run_root / "session"
    session_dir.mkdir(parents=True, exist_ok=True)
    run_root.mkdir(parents=True, exist_ok=True)

    data_dir = session_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    seeds = task_dir / "seeds"
    if seeds.exists():
        stage_seeds_for_agent(seeds, data_dir, task_env=load_task_env(task_dir))

    task_env = load_task_env(task_dir)
    brief = build_agent_task_document(task_dir, task_env)
    (run_root / "RESEARCH_BRIEF.md").write_text(brief, encoding="utf-8")
    (run_root / "task_input.md").write_text(brief, encoding="utf-8")

    write_run_bfts_config(run_root, code_model, feedback_model, vlm_model)
    ensure_writeup_latex_templates(run_root)
    return run_root, session_dir


def build_launch_command(
    launch_cwd: Path,
    session_dir: Path,
    args: argparse.Namespace,
    model: str,
    *,
    python_bin: str = "python3",
) -> list[str]:
    ideas_json = session_dir / "idea.json"
    return [
        python_bin,
        str(AI_SCIENTIST_ROOT / "launch_scientist_bfts.py"),
        "--load_ideas",
        str(ideas_json),
        "--idea_idx",
        "0",
        "--model_writeup",
        model,
        "--model_citation",
        model,
        "--model_review",
        model,
        "--model_agg_plots",
        model,
        "--model_writeup_small",
        model,
        "--num_cite_rounds",
        str(args.num_cite_rounds),
        *([] if not args.skip_writeup else ["--skip_writeup"]),
        *([] if not args.skip_review else ["--skip_review"]),
    ]


def run_container_preflight(
    container_id: str,
    *,
    run_root: Path,
    python_bin: str,
) -> bool:
    ok_mounts, mount_issues = preflight_runtime_mounts(
        container_id, "aiscientist", cwd=run_root
    )
    for issue in mount_issues:
        print(f"[preflight] mount: {issue}", file=sys.stderr)
    if not ok_mounts:
        return False

    ok_scrub, scrub_msg = preflight_scrub_proxy(container_id)
    print(f"[preflight] {scrub_msg}")
    if not ok_scrub:
        return False

    bfts_script = AI_SCIENTIST_ROOT / "launch_scientist_bfts.py"
    ok_bfts, bfts_msg = preflight_binary(container_id, str(bfts_script), cwd=run_root)
    print(f"[preflight] {bfts_msg}")
    if not ok_bfts:
        return False

    ok_cfg, cfg_msg = preflight_path(container_id, str(run_root / "bfts_config.yaml"), cwd=run_root)
    print(f"[preflight] {cfg_msg}")
    return ok_cfg


def run_full_pipeline(args: argparse.Namespace) -> int:
    from agent_container import _is_metering_proxy_url, apply_run_metering_to_env
    from run_metering import start_run_timer, stop_run_timer, write_manifest_with_metering

    task_dir = Path(args.task_dir).resolve()
    run_root, session_dir = prepare_run_layout(
        task_dir, args.model, args.feedback_model, args.vlm_model
    )

    from agent_container import ensure_aiscientist_experiment_env

    env = os.environ.copy()
    env["AI_SCIENTIST_ROOT"] = str(AI_SCIENTIST_ROOT)
    env["AI_SCIENTIST_MODEL"] = args.model
    for key in ("OPENAI_API_KEY", "OPENAI_API_BASE", "OPENAI_BASE_URL", "API_BASE_URL", "S2_API_KEY"):
        if key in os.environ:
            env[key] = os.environ[key]
    env = benchmark_runtime_env(env, run_root=run_root)
    # Writable HOME + task venv Python for BFTS Interpreter (generic; no task id hardcoding).
    env = ensure_aiscientist_experiment_env(
        env, run_root=run_root, task_dir=task_dir
    )
    env.setdefault("OPENAI_API_BASE", scrub_base_url(env))

    if not load_api_env(env, env_file=AI_SCIENTIST_ROOT / ".env"):
        print(
            f"Missing OPENAI_API_KEY. Set llm.api_key in {credentials_file_path()} "
            "(or run: python3 integrations/benchmark_credentials.py --init)",
            file=sys.stderr,
        )
        return 1

    already_metered = any(
        _is_metering_proxy_url(env.get(key, ""))
        for key in ("OPENAI_BASE_URL", "OPENAI_API_BASE", "API_BASE_URL")
    )
    if not already_metered:
        env = apply_run_metering_to_env(
            env,
            run_root=run_root,
            for_container=Path("/.dockerenv").exists(),
        )
    env[BENCHMARK_RUN_ROOT_ENV] = str(run_root)
    for key in (
        "OPENAI_API_KEY",
        "OPENAI_API_BASE",
        "OPENAI_BASE_URL",
        "API_BASE_URL",
        "CUSTOM_OPENAI_BASE_URL",
        BENCHMARK_RUN_ROOT_ENV,
        "HOME",
        "PYTHONUSERBASE",
        "PIP_CACHE_DIR",
        "AI_SCIENTIST_EXPERIMENT_PYTHON",
        "PATH",
    ):
        if key in env:
            os.environ[key] = env[key]
    if env.get("AI_SCIENTIST_EXPERIMENT_PYTHON"):
        print(
            f"[preflight] experiment python: {env['AI_SCIENTIST_EXPERIMENT_PYTHON']}"
        )

    python_bin, python_msg = resolve_aiscientist_python(
        host_env=env,
        ai_scientist_root=AI_SCIENTIST_ROOT,
    )
    if not python_bin:
        print(python_msg, file=sys.stderr)
        return 1
    print(f"[preflight] {python_msg}")

    start_run_timer(run_root, phase="agent")
    returncode = 1
    try:
        if args.skip_ideation:
            print("[ideation] skipped (--skip-ideation); using task_to_idea seed")
            write_task_idea_files(task_dir, session_dir)
        elif (session_dir / "idea.json").is_file():
            print(f"[ideation] reusing existing {session_dir / 'idea.json'}")
        else:
            rc, idea_path = run_ideation(
                task_dir=task_dir,
                session_dir=session_dir,
                model=args.model,
                env=env,
                num_reflections=args.ideation_reflections,
                max_num_generations=args.ideation_generations,
            )
            if rc != 0:
                returncode = rc
                return rc
            print(f"[ideation] complete -> {idea_path}")

        ensure_writeup_latex_templates(run_root)
        cmd = build_launch_command(
            run_root, session_dir, args, args.model, python_bin=python_bin
        )
        print("[launch] BFTS:", " ".join(cmd))
        proc = __import__("subprocess").run(cmd, cwd=run_root, env=env, check=False)
        returncode = int(proc.returncode)
        if returncode != 0:
            return returncode
        print(f"Done. Artifacts: {run_root / 'experiments'} (ideation: {session_dir})")
        returncode = 0
        return 0
    finally:
        stop_run_timer(run_root, phase="agent", returncode=returncode)
        write_manifest_with_metering(
            run_root / "artifacts" / "manifest.json",
            {
                "framework": "ai_scientist_v2",
                "run_dir": str(run_root),
                "returncode": returncode,
                "status": {"pipeline": returncode == 0},
            },
            run_root,
        )


def run_native(args: argparse.Namespace) -> int:
    return run_full_pipeline(args)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AI-Scientist-v2 in ai_scientist sandbox")
    parser.add_argument(
        "--task-dir",
        default=str(Path.home() / "ai_scientist_inputs" / "ASE-2025-004_predicting_recheck_success_in_continuous"),
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override code model from benchmark_credentials.yaml (models.aiscientist_code)",
    )
    parser.add_argument(
        "--feedback-model",
        default=None,
        help="Override feedback model from benchmark_credentials.yaml (models.aiscientist_feedback)",
    )
    parser.add_argument(
        "--vlm-model",
        default=None,
        help="Override VLM model from benchmark_credentials.yaml (models.aiscientist_vlm)",
    )
    parser.add_argument("--num-cite-rounds", type=int, default=5)
    parser.add_argument("--skip-writeup", action="store_true")
    parser.add_argument("--skip-review", action="store_true")
    parser.add_argument("--skip-ideation", action="store_true", help="Skip v2 ideation; seed idea.json from task.md")
    parser.add_argument(
        "--ideation-reflections",
        type=int,
        default=int(os.getenv("AI_SCIENTIST_IDEATION_REFLECTIONS", "3")),
    )
    parser.add_argument(
        "--ideation-generations",
        type=int,
        default=int(os.getenv("AI_SCIENTIST_IDEATION_GENERATIONS", "1")),
    )
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument("--native", action="store_true", help=argparse.SUPPRESS)
    add_transient_retry_arguments(parser)
    args = parser.parse_args()
    args.model = args.model or resolve_model("aiscientist", role="code")
    args.feedback_model = args.feedback_model or resolve_model("aiscientist", role="feedback")
    args.vlm_model = args.vlm_model or resolve_model("aiscientist", role="vlm")

    if not AI_SCIENTIST_ROOT.is_dir():
        print(f"Missing AI-Scientist-v2 checkout: {AI_SCIENTIST_ROOT}", file=sys.stderr)
        return 1

    task_dir = Path(args.task_dir).resolve()
    if not task_dir.is_dir():
        print(f"Task directory not found: {task_dir}", file=sys.stderr)
        return 1

    if args.native or os.environ.get(BENCHMARK_AGENT_NATIVE_ENV) == "1":
        return run_native(args)

    if not shutil.which("docker"):
        print("docker is required for AI-Scientist-v2 benchmark runs.", file=sys.stderr)
        return 1

    run_root, session_dir = prepare_run_layout(
        task_dir, args.model, args.feedback_model, args.vlm_model
    )
    sandbox = TaskSandbox(task_dir, agent_tool="aiscientist")
    container_id: str | None = None

    try:
        container_id = sandbox.start(agent_tool="aiscientist", run_root=run_root)
        print(f"[sandbox] container_id={container_id}")

        seed_task_workspace(sandbox, run_root)
        print(f"[sandbox] seeded dataset_candidate under {run_root}")

        ok, msg = preflight_python(container_id, run_root)
        print(f"[preflight] {msg}")
        if not ok:
            return 1

        host_env = os.environ.copy()
        if not load_api_env(host_env, env_file=AI_SCIENTIST_ROOT / ".env"):
            print(
                f"Missing OPENAI_API_KEY. Set llm.api_key in {credentials_file_path()} "
                "(or run: python3 integrations/benchmark_credentials.py --init)",
                file=sys.stderr,
            )
            return 1

        python_bin, python_msg = resolve_aiscientist_python(
            host_env=host_env,
            container_id=container_id,
            cwd=run_root,
            ai_scientist_root=AI_SCIENTIST_ROOT,
        )
        if not python_bin:
            print(python_msg, file=sys.stderr)
            return 1
        print(f"[preflight] {python_msg}")

        if not run_container_preflight(container_id, run_root=run_root, python_bin=python_bin):
            return 1

        env = build_container_env(
            host_env,
            agent_tool="aiscientist",
            run_root=run_root,
            task_env=sandbox.env,
            extra={
                BENCHMARK_RUN_ROOT_ENV: str(run_root),
                "AI_SCIENTIST_ROOT": str(AI_SCIENTIST_ROOT),
                "AI_SCIENTIST_MODEL": args.model,
            },
        )
        env = benchmark_runtime_env(env, run_root=run_root)
        if env.get("AI_SCIENTIST_EXPERIMENT_PYTHON"):
            print(
                f"[preflight] experiment python: {env['AI_SCIENTIST_EXPERIMENT_PYTHON']}"
            )
        log_path = run_root / "ai_scientist_run.log"
        native_script = str(BENCHMARK_ROOT / "integrations" / "run_aiscientist_task.py")
        cmd = [
            python_bin,
            native_script,
            "--native",
            "--task-dir",
            str(task_dir),
            "--model",
            args.model,
            "--feedback-model",
            args.feedback_model,
            "--vlm-model",
            args.vlm_model,
            "--num-cite-rounds",
            str(args.num_cite_rounds),
            "--ideation-reflections",
            str(args.ideation_reflections),
            "--ideation-generations",
            str(args.ideation_generations),
        ]
        if args.skip_ideation:
            cmd.append("--skip-ideation")
        if args.skip_writeup:
            cmd.append("--skip-writeup")
        if args.skip_review:
            cmd.append("--skip-review")
        print("[launch] in-container pipeline:", " ".join(cmd[:8]), "...")
        rc = launch_agent(
            container_id=container_id,
            cmd=cmd,
            cwd=run_root,
            env=env,
            log_path=log_path,
        )
        rc = retry_launch_on_transient(
            returncode=rc,
            log_path=log_path,
            args=args,
            label="aiscientist",
            relaunch=lambda: launch_agent(
                container_id=container_id,
                cmd=cmd,
                cwd=run_root,
                env=env,
                log_path=log_path,
                append=True,
            ),
        )
        from run_metering import write_manifest_with_metering

        write_manifest_with_metering(
            run_root / "artifacts" / "manifest.json",
            {
                "framework": "ai_scientist_v2",
                "run_dir": str(run_root),
                "returncode": rc,
                "status": {"pipeline": rc == 0},
            },
            run_root,
            log_path=log_path if log_path.is_file() else None,
        )
        if rc != 0:
            print(f"[aiscientist] exited with code {rc}. See {log_path}", file=sys.stderr)
            print_log_tail(log_path)
            return rc

        if args.evaluate:
            code, stdout, stderr = sandbox.evaluate()
            print(stdout.strip())
            if stderr.strip():
                print(stderr.strip(), file=sys.stderr)
            result_path = task_dir / "evaluator" / "results" / "result.json"
            if result_path.exists():
                print(json.dumps(json.loads(result_path.read_text(encoding="utf-8")), indent=2, ensure_ascii=False))
            if code != 0:
                return code

        print(f"Done. Artifacts: {run_root / 'experiments'} (ideation: {session_dir})")
        return 0
    finally:
        print("[sandbox] cleaning up container...")
        sandbox.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
