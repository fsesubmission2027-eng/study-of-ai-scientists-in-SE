#!/usr/bin/env python3
"""Run TinyScientist on an ai_scientist_inputs task (in-container execution)."""

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
DEFAULT_MODEL = "deepseek-v4-pro-0813"

sys.path.insert(0, str(ORCHESTRATOR_ROOT))
sys.path.insert(0, str(INTEGRATIONS_ROOT))

from agent_container import (  # noqa: E402
    BENCHMARK_AGENT_NATIVE_ENV,
    BENCHMARK_RUN_ROOT_ENV,
    build_container_env,
    launch_agent,
    load_api_env,
    preflight_python,
    preflight_python_import,
    preflight_runtime_mounts,
    preflight_scrub_proxy,
    print_log_tail,
    reuse_benchmark_run_root,
)
from sandbox import TaskSandbox  # noqa: E402
from seed_staging import shell_copy_agent_seeds, stage_seeds_for_agent  # noqa: E402
from task_to_tiny_idea import task_dir_to_tiny_idea, write_tiny_idea_files  # noqa: E402
from benchmark_credentials import credentials_file_path, resolve_model  # noqa: E402
from transient_retry import add_transient_retry_arguments, retry_launch_on_transient  # noqa: E402


def patch_tiny_scientist_pricing() -> None:
    import tiny_scientist.budget_checker as budget_checker
    import tiny_scientist.utils.pricing as pricing

    if getattr(pricing, "_benchmark_pricing_patched", False):
        return

    from run_metering import cost_usd_for, record_manual_usage

    _original = pricing.calculate_pricing

    def calculate_pricing(model: str, input_tokens: int, output_tokens: int) -> float:
        try:
            return float(_original(model, input_tokens, output_tokens))
        except ValueError:
            cost, _matched, _priced = cost_usd_for(model, int(input_tokens), int(output_tokens))
            return float(cost)

    pricing.calculate_pricing = calculate_pricing  # type: ignore[assignment]
    budget_checker.calculate_pricing = calculate_pricing  # type: ignore[assignment]

    _original_add = budget_checker.BudgetChecker.add_cost

    def add_cost(  # type: ignore[no-untyped-def]
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        task_name: str | None = None,
    ) -> float:
        run_root = os.environ.get("BENCHMARK_RUN_ROOT", "").strip()
        if run_root and (input_tokens or output_tokens):
            try:
                record_manual_usage(
                    Path(run_root),
                    model=model or "unknown",
                    prompt_tokens=int(input_tokens or 0),
                    completion_tokens=int(output_tokens or 0),
                    source="tiny_scientist.BudgetChecker",
                )
            except Exception:  # noqa: BLE001
                pass
        return _original_add(self, model, input_tokens, output_tokens, task_name)

    budget_checker.BudgetChecker.add_cost = add_cost  # type: ignore[assignment]
    pricing._benchmark_pricing_patched = True


def modelverse_model_name(model: str) -> str:
    if model.startswith("openai/"):
        return model
    bare = model.split("/", 1)[-1] if model.startswith("modelverse/") else model
    return f"openai/{bare}"


def load_task_intent(task_dir: Path) -> str:
    """Canonical shared brief (aligned with other benchmark tools)."""
    from agent_task_document import build_agent_task_document
    from path_alignment import load_task_env

    return build_agent_task_document(task_dir, load_task_env(task_dir))


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


def prepare_run_layout(task_dir: Path, *, direct_idea: bool) -> tuple[Path, Path]:
    from agent_task_document import build_agent_task_document
    from path_alignment import load_task_env

    existing = reuse_benchmark_run_root()
    if existing is not None:
        return existing, existing

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_root = task_dir / "workspace" / f"tiny_scientist_{timestamp}"
    run_root.mkdir(parents=True, exist_ok=True)

    seeds = task_dir / "seeds"
    dataset_dir = run_root / "dataset_candidate"
    dataset_dir.mkdir(parents=True, exist_ok=True)
    if seeds.exists():
        stage_seeds_for_agent(seeds, dataset_dir, task_env=load_task_env(task_dir))

    for sub in ("project", "results", "paper"):
        (run_root / sub).mkdir(parents=True, exist_ok=True)

    task_env = load_task_env(task_dir)
    brief = build_agent_task_document(task_dir, task_env)
    (run_root / "RESEARCH_BRIEF.md").write_text(brief, encoding="utf-8")
    (run_root / "task_input.md").write_text(brief, encoding="utf-8")

    if direct_idea:
        write_tiny_idea_files(task_dir, run_root)

    return run_root, run_root


def resolve_tiny_python_bin(container_id: str, *, cwd: Path) -> str:
    for candidate in (
        str(Path.home() / "miniconda3/envs/pure_tiny_env/bin/python"),
        str(Path.home() / "miniconda3/bin/python3"),
        "python3",
    ):
        from agent_container import preflight_binary

        ok, _msg = preflight_binary(container_id, candidate, cwd=cwd)
        if ok:
            return candidate
    return "python3"


def run_container_preflight(container_id: str, *, run_dir: Path, python_bin: str) -> bool:
    ok_mounts, mount_issues = preflight_runtime_mounts(
        container_id, "tinyscientist", cwd=run_dir
    )
    for issue in mount_issues:
        print(f"[preflight] mount: {issue}", file=sys.stderr)
    if not ok_mounts:
        return False

    ok_scrub, scrub_msg = preflight_scrub_proxy(container_id)
    print(f"[preflight] {scrub_msg}")
    if not ok_scrub:
        return False

    script = BENCHMARK_ROOT / "integrations" / "run_tinyscientist_task.py"
    from agent_container import preflight_path

    ok_script, script_msg = preflight_path(container_id, str(script), cwd=run_dir)
    print(f"[preflight] {script_msg}")
    if not ok_script:
        return False

    ok_import, import_msg = preflight_python_import(
        container_id,
        python_bin=python_bin,
        import_stmt="import tiny_scientist; print('ok')",
        cwd=run_dir,
    )
    print(f"[preflight] {import_msg}")
    return ok_import


def normalize_idea(raw: object) -> dict:
    if not raw:
        raise RuntimeError("No idea returned")
    if isinstance(raw, list):
        if not raw:
            raise RuntimeError("think() returned an empty idea list")
        raw = raw[0]
    if not isinstance(raw, dict):
        raise RuntimeError(f"Unexpected idea type: {type(raw)!r}")
    return raw


def has_experiment_field(idea: dict) -> bool:
    experiment = idea.get("Experiment")
    if experiment is None:
        return False
    if isinstance(experiment, dict):
        return bool(experiment)
    if isinstance(experiment, str):
        return bool(experiment.strip())
    return bool(experiment)


def ensure_experiment_field(scientist, idea: dict, *, skip_exp_plan: bool) -> dict:
    if has_experiment_field(idea):
        print("[idea] Experiment field: present")
        return idea

    if skip_exp_plan:
        print("[warn] Idea has no 'Experiment' field (--skip-exp-plan)", file=sys.stderr)
        return idea

    print("[warn] Retrying generate_experiment_plan once...", file=sys.stderr)
    updated_json = scientist.thinker.generate_experiment_plan(json.dumps(idea, ensure_ascii=False))
    idea = json.loads(updated_json)
    if has_experiment_field(idea):
        print("[idea] Experiment field: present (after retry)")
        return idea
    raise RuntimeError("Idea still missing 'Experiment' after retry.")


def save_idea(run_dir: Path, idea: dict) -> Path:
    artifacts = run_dir / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    idea_path = artifacts / "idea.json"
    idea_path.write_text(json.dumps(idea, indent=2, ensure_ascii=False), encoding="utf-8")
    return idea_path


def collect_code_artifacts(run_dir: Path, exp_dir: Path) -> dict[str, str]:
    src = Path(exp_dir)
    dest = run_dir / "artifacts" / "code"
    dest.mkdir(parents=True, exist_ok=True)
    saved: dict[str, str] = {}
    for name in ("experiment.py", "notes.txt"):
        src_file = src / name
        if src_file.is_file():
            out = dest / name
            shutil.copy2(src_file, out)
            saved[name] = str(out.relative_to(run_dir))
    for snap in sorted(src.glob("run_*.py")):
        out = dest / snap.name
        shutil.copy2(snap, out)
        saved[snap.name] = str(out.relative_to(run_dir))
    return saved


def collect_result_artifacts(run_dir: Path, exp_dir: Path) -> dict[str, object]:
    src = Path(exp_dir)
    dest = run_dir / "artifacts" / "results"
    dest.mkdir(parents=True, exist_ok=True)
    saved: dict[str, object] = {"runs": []}

    summary = src / "experiment_results.txt"
    if summary.is_file():
        out = dest / "experiment_results.txt"
        shutil.copy2(summary, out)
        saved["experiment_results.txt"] = str(out.relative_to(run_dir))

    for run_dir_src in sorted(src.glob("run_*")):
        if not run_dir_src.is_dir():
            continue
        run_dest = dest / run_dir_src.name
        if run_dest.exists():
            shutil.rmtree(run_dest)
        shutil.copytree(run_dir_src, run_dest)
        saved["runs"].append(str(run_dest.relative_to(run_dir)))

    return saved


def collect_paper_artifacts(run_dir: Path, pdf_path: str) -> dict[str, str]:
    saved: dict[str, str] = {}
    paper_root = run_dir / "artifacts" / "paper"
    paper_root.mkdir(parents=True, exist_ok=True)

    pdf_src = Path(pdf_path)
    if pdf_src.is_file():
        pdf_dest = paper_root / "paper.pdf"
        shutil.copy2(pdf_src, pdf_dest)
        saved["pdf"] = str(pdf_dest.relative_to(run_dir))

    latex_src = run_dir / "latex"
    latex_dest = paper_root / "latex"
    if latex_src.is_dir():
        if latex_dest.exists():
            shutil.rmtree(latex_dest)
        shutil.copytree(latex_src, latex_dest)
        saved["latex_dir"] = str(latex_dest.relative_to(run_dir))
        for tex_name in ("acl_latex.tex", "iclr2025_conference.tex"):
            tex_file = latex_dest / tex_name
            if tex_file.is_file():
                saved["main_tex"] = str(tex_file.relative_to(run_dir))
                break

    benchmark_paper = run_dir / "paper"
    benchmark_paper.mkdir(parents=True, exist_ok=True)
    if "pdf" in saved:
        shutil.copy2(paper_root / "paper.pdf", benchmark_paper / "paper.pdf")
    if latex_dest.is_dir() and (latex_dest / "custom.bib").is_file():
        main_tex = saved.get("main_tex")
        if main_tex:
            shutil.copy2(run_dir / main_tex, benchmark_paper / "main.tex")
        shutil.copy2(latex_dest / "custom.bib", benchmark_paper / "references.bib")

    return saved


def write_run_manifest(
    run_dir: Path,
    *,
    idea_path: Path,
    code_ok: bool,
    code_files: dict[str, str],
    results: dict[str, object],
    paper_files: dict[str, str] | None,
    paper_ok: bool,
) -> Path:
    from run_metering import write_manifest_with_metering

    manifest = {
        "framework": "tiny_scientist",
        "run_dir": str(run_dir),
        "execution_mode": "in_container",
        "artifacts": {
            "idea": str(idea_path.relative_to(run_dir)),
            "code": code_files,
            "results": results,
            "paper": paper_files or {},
        },
        "status": {"code": code_ok, "paper": paper_ok},
    }
    manifest_path = run_dir / "artifacts" / "manifest.json"
    log_path = run_dir / "tiny_scientist_run.log"
    return write_manifest_with_metering(
        manifest_path,
        manifest,
        run_dir,
        log_path=log_path if log_path.is_file() else None,
    )


def resolve_idea(scientist, task_dir: Path, run_dir: Path, args: argparse.Namespace) -> dict:
    if args.direct_idea:
        idea_path = run_dir / "tiny_idea.json"
        if idea_path.is_file():
            idea = json.loads(idea_path.read_text(encoding="utf-8"))
        else:
            idea = task_dir_to_tiny_idea(task_dir, workspace_rel=".")
        idea = ensure_experiment_field(scientist, idea, skip_exp_plan=args.skip_exp_plan)
        save_idea(run_dir, idea)
        return idea

    intent = load_task_intent(task_dir)
    scientist.thinker.search_papers = args.paper_search
    scientist.thinker.generate_exp_plan = not args.skip_exp_plan

    ideas = scientist.think(intent=intent, num_ideas=1)
    idea = normalize_idea(ideas)
    (run_dir / "tiny_idea_from_think.json").write_text(
        json.dumps(idea, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    idea = ensure_experiment_field(scientist, idea, skip_exp_plan=args.skip_exp_plan)
    save_idea(run_dir, idea)
    return idea


def run_native_pipeline(task_dir: Path, args: argparse.Namespace) -> int:
    from agent_container import apply_run_metering_to_env
    from run_metering import start_run_timer, stop_run_timer

    run_dir, output_dir = prepare_run_layout(task_dir, direct_idea=args.direct_idea)

    env = os.environ.copy()
    if not load_api_env(env, env_file=AI_SCIENTIST_ROOT / ".env"):
        print(
            f"Missing OPENAI_API_KEY. Set llm.api_key in {credentials_file_path()} "
            "(or run: python3 integrations/benchmark_credentials.py --init)",
            file=sys.stderr,
        )
        return 1
    # Inside the container, route via host metering proxy; on bare host use 127.0.0.1.
    # If the outer docker launcher already injected a metering URL, keep it.
    from agent_container import _is_metering_proxy_url

    already_metered = any(
        _is_metering_proxy_url(env.get(key, ""))
        for key in ("OPENAI_BASE_URL", "OPENAI_API_BASE", "API_BASE_URL")
    )
    if not already_metered:
        for_container = Path("/.dockerenv").exists()
        env = apply_run_metering_to_env(env, run_root=run_dir, for_container=for_container)
    env[BENCHMARK_RUN_ROOT_ENV] = str(run_dir)
    for key in (
        "OPENAI_API_KEY",
        "OPENAI_API_BASE",
        "OPENAI_BASE_URL",
        "API_BASE_URL",
        "CUSTOM_OPENAI_BASE_URL",
        BENCHMARK_RUN_ROOT_ENV,
    ):
        if key in env:
            os.environ[key] = env[key]

    patch_tiny_scientist_pricing()
    from tiny_scientist import TinyScientist

    scientist = TinyScientist(
        model=args.model,
        output_dir=str(output_dir),
        budget=args.budget,
        enable_safety_check=not args.skip_safety_check,
        use_docker=False,
    )

    mode = "direct-idea (no think)" if args.direct_idea else "think(full task.md) -> code"
    print(f"[config] model={args.model}")
    print(f"[config] run_dir={run_dir}")
    print(f"[config] mode={mode}")
    print(f"[config] execution=in_container")
    print(f"[config] openai_base={os.environ.get('OPENAI_BASE_URL', '')}")

    start_run_timer(run_dir, phase="agent")
    returncode = 1
    try:
        idea = resolve_idea(scientist, task_dir, run_dir, args)
        idea_path = run_dir / "artifacts" / "idea.json"
        print(f"[idea] Title={idea.get('Title', '(missing)')!r}")

        status, exp_dir = scientist.code(idea=idea)
        print(f"[code] success={status} exp_dir={exp_dir}")
        code_files = collect_code_artifacts(run_dir, exp_dir)
        result_files = collect_result_artifacts(run_dir, exp_dir)

        paper_files: dict[str, str] | None = None
        paper_ok = False
        if not status and not args.continue_on_code_failure:
            write_run_manifest(
                run_dir,
                idea_path=idea_path,
                code_ok=False,
                code_files=code_files,
                results=result_files,
                paper_files=None,
                paper_ok=False,
            )
            returncode = 1
            return returncode

        if args.write_paper:
            try:
                pdf_path, _paper_slug = scientist.write(idea=idea, experiment_dir=exp_dir)
                paper_files = collect_paper_artifacts(run_dir, pdf_path)
                paper_ok = bool(paper_files.get("pdf"))
            except Exception as exc:
                print(f"[write] failed: {exc}", file=sys.stderr)

        manifest_path = write_run_manifest(
            run_dir,
            idea_path=idea_path,
            code_ok=status,
            code_files=code_files,
            results=result_files,
            paper_files=paper_files,
            paper_ok=paper_ok,
        )
        print(f"[manifest] {manifest_path}")
        scientist.get_total_cost()
        print(f"Done. Artifacts: {run_dir / 'artifacts'}")
        returncode = 0
        return returncode
    finally:
        stop_run_timer(run_dir, phase="agent", returncode=returncode)
        # Refresh timing/usage after the timer stops.
        manifest_path = run_dir / "artifacts" / "manifest.json"
        if manifest_path.is_file():
            try:
                from run_metering import attach_metering_to_manifest

                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
                attach_metering_to_manifest(payload, run_dir)
                manifest_path.write_text(
                    json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
                )
            except Exception as exc:  # noqa: BLE001
                print(f"[metering] refresh failed: {exc}", file=sys.stderr)


def run_pipeline(task_dir: Path, args: argparse.Namespace) -> int:
    if args.native or os.environ.get(BENCHMARK_AGENT_NATIVE_ENV) == "1":
        return run_native_pipeline(task_dir, args)

    if not shutil.which("docker"):
        print("docker is required for TinyScientist benchmark runs.", file=sys.stderr)
        return 1

    run_dir, _ = prepare_run_layout(task_dir, direct_idea=args.direct_idea)
    sandbox = TaskSandbox(task_dir, agent_tool="tinyscientist")
    container_id: str | None = None

    host_env = os.environ.copy()
    if not load_api_env(host_env, env_file=AI_SCIENTIST_ROOT / ".env"):
        print(
            f"Missing OPENAI_API_KEY. Set llm.api_key in {credentials_file_path()} "
            "(or run: python3 integrations/benchmark_credentials.py --init)",
            file=sys.stderr,
        )
        return 1

    try:
        container_id = sandbox.start(agent_tool="tinyscientist", run_root=run_dir)
        print(f"[sandbox] container_id={container_id}")
        seed_task_workspace(sandbox, run_dir)

        ok, msg = preflight_python(container_id, run_dir)
        print(f"[preflight] {msg}")
        if not ok:
            return 1

        python_bin = resolve_tiny_python_bin(container_id, cwd=run_dir)
        if not run_container_preflight(container_id, run_dir=run_dir, python_bin=python_bin):
            return 1

        env = build_container_env(
            host_env,
            agent_tool="tinyscientist",
            run_root=run_dir,
            extra={
                BENCHMARK_AGENT_NATIVE_ENV: "1",
                BENCHMARK_RUN_ROOT_ENV: str(run_dir),
            },
        )
        log_path = run_dir / "tiny_scientist_run.log"
        script = str(BENCHMARK_ROOT / "integrations" / "run_tinyscientist_task.py")
        cmd = [
            python_bin,
            script,
            "--native",
            "--task-dir",
            str(task_dir),
            "--model",
            args.model,
        ]
        if args.direct_idea:
            cmd.append("--direct-idea")
        if args.paper_search:
            cmd.append("--paper-search")
        if args.skip_exp_plan:
            cmd.append("--skip-exp-plan")
        if args.skip_safety_check:
            cmd.append("--skip-safety-check")
        if args.skip_write_paper:
            cmd.append("--skip-write-paper")
        if args.continue_on_code_failure:
            cmd.append("--continue-on-code-failure")
        if args.budget is not None:
            cmd.extend(["--budget", str(args.budget)])

        rc = launch_agent(
            container_id=container_id,
            cmd=cmd,
            cwd=run_dir,
            env=env,
            log_path=log_path,
        )
        rc = retry_launch_on_transient(
            returncode=rc,
            log_path=log_path,
            args=args,
            label="tinyscientist",
            relaunch=lambda: launch_agent(
                container_id=container_id,
                cmd=cmd,
                cwd=run_dir,
                env=env,
                log_path=log_path,
                append=True,
            ),
        )
        if rc != 0:
            print(f"[tinyscientist] exited with code {rc}. See {log_path}", file=sys.stderr)
            print_log_tail(log_path)
            return rc

        if args.evaluate:
            code, stdout, stderr = sandbox.evaluate()
            print(stdout.strip())
            if stderr.strip():
                print(stderr.strip(), file=sys.stderr)
            return code
        return 0
    finally:
        print("[sandbox] cleaning up container...")
        sandbox.destroy()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run TinyScientist on a benchmark task.")
    parser.add_argument(
        "--task-dir",
        default=str(Path.home() / "ai_scientist_inputs" / "ASE-2025-004_predicting_recheck_success_in_continuous"),
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override llm model from benchmark_credentials.yaml (models.tinyscientist)",
    )
    parser.add_argument("--budget", type=float, default=None)
    parser.add_argument("--direct-idea", action="store_true")
    parser.add_argument("--paper-search", action="store_true")
    parser.add_argument("--skip-exp-plan", action="store_true")
    parser.add_argument("--skip-safety-check", action="store_true")
    parser.add_argument("--skip-write-paper", action="store_true")
    parser.add_argument("--review-paper", action="store_true")
    parser.add_argument("--continue-on-code-failure", action="store_true")
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument("--native", action="store_true", help=argparse.SUPPRESS)
    add_transient_retry_arguments(parser)
    args = parser.parse_args()
    args.model = modelverse_model_name(
        args.model or resolve_model("tinyscientist")
    )
    args.write_paper = not args.skip_write_paper

    task_dir = Path(args.task_dir).resolve()
    if not task_dir.is_dir():
        print(f"Task directory not found: {task_dir}", file=sys.stderr)
        return 1

    return run_pipeline(task_dir, args)


if __name__ == "__main__":
    raise SystemExit(main())
