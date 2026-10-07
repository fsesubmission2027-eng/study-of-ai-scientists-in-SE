#!/usr/bin/env python3
"""Run DeepScientist on an ai_scientist_inputs task inside TaskSandbox (Path C)."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import textwrap
import time
import urllib.request
from datetime import datetime
from pathlib import Path

BENCHMARK_ROOT = Path(__file__).resolve().parents[1]
INTEGRATIONS_ROOT = BENCHMARK_ROOT / "integrations"
ORCHESTRATOR_ROOT = BENCHMARK_ROOT / "orchestrator"
AI_SCIENTIST_ROOT = BENCHMARK_ROOT.parent / "AI-Scientist-v2"
DEFAULT_DS_HOME = Path.home() / "DeepScientist"
DEFAULT_DS_BIN = Path.home() / ".npm-global/bin/ds"
DEFAULT_OPENCODE_BIN = (
    Path.home()
    / ".npm-global/lib/node_modules/@researai/deepscientist/node_modules/.bin/opencode"
)
DEFAULT_PORT = 21099
CONTAINER_DAEMON_HOST = "0.0.0.0"
DEFAULT_MODEL = "modelverse/deepseek-v4-pro-0813"

sys.path.insert(0, str(ORCHESTRATOR_ROOT))
sys.path.insert(0, str(INTEGRATIONS_ROOT))

from deepscientist_docker import (  # noqa: E402
    EXECUTION_MODE_CONTAINER,
    EXECUTION_MODE_DOCKER,
    EXECUTION_MODE_HOST,
    build_benchmark_execution_env,
    build_full_pipeline_kickoff_message,
    build_objectives,
    build_runtime_constraints,
    build_startup_message,
    configure_quest_run_workspace,
    docker_workdir_for_run,
    link_quest_workspace_dirs,
    seed_task_workspace_host,
    write_opencode_scrub_config,
)
from sandbox import TaskSandbox  # noqa: E402
from seed_staging import shell_copy_agent_seeds  # noqa: E402
from agent_task_document import build_agent_task_document, task_title_and_goal
from path_alignment import load_task_env
from agent_container import (  # noqa: E402
    apply_literature_scrub_to_env,
    preflight_scrub_proxy,
    scrub_base_url,
)
from benchmark_credentials import (  # noqa: E402
    apply_benchmark_credentials,
    credentials_file_path,
    require_llm_api_key,
    resolve_model,
)
from transient_retry import (  # noqa: E402
    add_transient_retry_arguments,
    probe_transient_failure,
    resolve_transient_retry_policy,
)


def load_api_env(env: dict[str, str]) -> bool:
    merged = apply_benchmark_credentials(env)
    env.clear()
    env.update(merged)
    return require_llm_api_key(env)


def resolve_ds_bin() -> str:
    for candidate in (
        os.environ.get("DS_BIN"),
        shutil.which("ds"),
        str(DEFAULT_DS_BIN),
    ):
        if candidate and Path(candidate).exists():
            return str(Path(candidate).resolve())
    raise FileNotFoundError(
        "Could not find `ds`. Install @researai/deepscientist and ensure ~/.npm-global/bin is on PATH."
    )


def resolve_ds_repo_root(ds_bin: str) -> Path:
    """Locate the installed @researai/deepscientist package (contains src/skills)."""
    ds_bin_path = Path(ds_bin).resolve()
    for candidate in (
        ds_bin_path.parent.parent,
        Path.home() / ".npm-global/lib/node_modules/@researai/deepscientist",
    ):
        if (candidate / "src" / "skills").is_dir():
            return candidate
    raise FileNotFoundError(
        "Could not locate DeepScientist package root (expected src/skills/). "
        f"Checked near ds bin: {ds_bin_path}"
    )


def stage_writable_ds_repo(ds_repo_root: Path, run_root: Path) -> tuple[Path, str]:
    """Copy the npm package into the run tree so uv can write build artifacts in-container."""
    staged = run_root / ".deepscientist_npm"
    staged_bin = staged / "bin" / "ds.js"
    if staged_bin.is_file():
        return staged, str(staged_bin)
    print(f"[deepscientist] staging npm package to {staged}")
    if staged.exists():
        shutil.rmtree(staged)
    shutil.copytree(ds_repo_root, staged, symlinks=True)
    return staged, str(staged_bin)


def build_ds_subprocess_env(ds_home: Path, ds_repo_root: Path, base_env: dict[str, str]) -> dict[str, str]:
    env = base_env.copy()
    env["DEEPSCIENTIST_HOME"] = str(ds_home.resolve())
    env["DEEPSCIENTIST_REPO_ROOT"] = str(ds_repo_root.resolve())
    return env


def resolve_opencode_bin() -> str:
    for candidate in (
        os.environ.get("OPENCODE_BIN"),
        shutil.which("opencode"),
        str(DEFAULT_OPENCODE_BIN),
    ):
        if candidate and Path(candidate).exists():
            return str(Path(candidate).resolve())
    raise FileNotFoundError("Could not find `opencode` binary for DeepScientist runner.")


def seed_task_workspace(sandbox: TaskSandbox, run_root: Path) -> None:
    from path_alignment import align_run_dataset_paths

    seeds = sandbox.task_dir / "seeds"
    seeds_path = sandbox.seeds_path()
    req = f"{seeds_path}/requirements.txt"
    copy_cmd = shell_copy_agent_seeds(seeds, f"{run_root}/dataset_candidate")
    if (seeds / "requirements.txt").exists():
        sandbox.exec(f"python3 -m pip install -r {req}", workdir=str(run_root))
    sandbox.exec(
        f"mkdir -p {run_root}/dataset_candidate "
        f"{run_root}/project {run_root}/results {run_root}/paper && "
        f"{copy_cmd}",
        workdir=str(run_root),
    )
    align_run_dataset_paths(run_root, sandbox.env)


def _yaml_env_lines(env: dict[str, str]) -> list[str]:
    lines = ["  env:"]
    for key in sorted(env):
        value = env[key].replace('"', '\\"')
        lines.append(f'    {key}: "{value}"')
    return lines


def copy_ds_config_template(
    ds_home: Path,
    *,
    model: str,
    opencode_bin: str,
    path_prefix: str,
    port: int,
    runner_env: dict[str, str] | None = None,
    opencode_config_dir: Path | None = None,
) -> None:
    """Bootstrap per-run DeepScientist home from the user's global install when available."""
    config_dir = ds_home / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    global_config = DEFAULT_DS_HOME / "config"
    if global_config.is_dir():
        for name in ("config.yaml", "connectors.yaml", "plugins.yaml", "mcp_servers.yaml"):
            src = global_config / name
            if src.is_file():
                shutil.copy2(src, config_dir / name)

    opencode_env = dict(runner_env or {})
    if not opencode_env.get("PATH") and path_prefix:
        opencode_env["PATH"] = path_prefix
    opencode_config = (
        str(opencode_config_dir.resolve())
        if opencode_config_dir is not None
        else "~/.config/opencode"
    )

    runners_yaml = config_dir / "runners.yaml"
    runners_lines = [
        "codex:",
        "  enabled: false",
        "  binary: codex",
        "claude:",
        "  enabled: false",
        "  binary: claude",
        "kimi:",
        "  enabled: false",
        "  binary: kimi",
        "opencode:",
        "  enabled: true",
        f"  binary: {opencode_bin}",
        f"  config_dir: {opencode_config}",
        f"  model: {model}",
        "  permission_mode: allow",
        "  default_agent: ''",
        "  variant: ''",
        "  mcp_timeout_ms: 172800000",
        "  retry_on_failure: true",
        "  retry_max_attempts: 4",
        "  retry_initial_backoff_sec: 10.0",
        "  retry_backoff_multiplier: 4.0",
        "  retry_max_backoff_sec: 600.0",
        *_yaml_env_lines(opencode_env),
        "  status: supported_experimental",
        "",
    ]
    runners_yaml.write_text("\n".join(runners_lines), encoding="utf-8")

    config_yaml = config_dir / "config.yaml"
    if not config_yaml.exists():
        config_yaml.write_text(
            "\n".join(
                [
                    f"home: {ds_home}",
                    "default_runner: opencode",
                    "default_locale: zh-CN",
                    "ui:",
                    "  host: 127.0.0.1",
                    f"  port: {port}",
                    "  auth_enabled: false",
                    "  auto_open_browser: false",
                    "  default_mode: web",
                    "",
                ]
            ),
            encoding="utf-8",
        )
    else:
        text = config_yaml.read_text(encoding="utf-8")
        if "default_runner:" in text:
            lines = []
            for line in text.splitlines():
                if line.startswith("default_runner:"):
                    lines.append("default_runner: opencode")
                else:
                    lines.append(line)
            config_yaml.write_text("\n".join(lines) + "\n", encoding="utf-8")


def http_json(method: str, url: str, payload: dict | None = None, timeout: float = 30.0) -> dict:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        body = response.read().decode("utf-8")
        return json.loads(body) if body.strip() else {}


def wait_for_daemon(base_url: str, timeout_sec: float = 180.0) -> None:
    deadline = time.time() + timeout_sec
    last_error = "unknown"
    while time.time() < deadline:
        try:
            payload = http_json("GET", f"{base_url}/api/health", timeout=5.0)
            if payload.get("ok") is True or payload.get("status") == "ok":
                return
            last_error = json.dumps(payload, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
        time.sleep(2.0)
    raise TimeoutError(f"DeepScientist daemon did not become healthy at {base_url}: {last_error}")


def is_port_free(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
            return True
        except OSError:
            return False


def pick_daemon_port(preferred: int, *, host: str = "127.0.0.1", max_tries: int = 32) -> int:
    for offset in range(max_tries):
        port = preferred + offset
        if is_port_free(port, host):
            return port
    raise RuntimeError(f"No free DeepScientist port in range {preferred}-{preferred + max_tries - 1}")


def read_daemon_log_tail(ds_home: Path, *, max_lines: int = 8) -> str:
    for name in ("daemon.jsonl", "daemon.log"):
        path = ds_home / "logs" / name
        if not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        if lines:
            return "\n".join(lines[-max_lines:])
    return ""


def start_daemon(ds_bin: str, ds_home: Path, port: int, env: dict[str, str]) -> None:
    stop_daemon(ds_bin, ds_home, env)
    cmd = [
        ds_bin,
        "--home",
        str(ds_home),
        "--daemon-only",
        "--runner",
        "opencode",
        "--no-browser",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--skip-update-check",
    ]
    print("[deepscientist] starting daemon:", " ".join(cmd))
    proc = subprocess.run(cmd, env=env, check=False, capture_output=True, text=True)
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.stderr.strip():
        print(proc.stderr.strip(), file=sys.stderr)
    if proc.returncode != 0:
        detail = read_daemon_log_tail(ds_home)
        hint = (
            f"\nDaemon log tail:\n{detail}" if detail else ""
        )
        raise RuntimeError(
            f"`ds --daemon-only` failed with exit code {proc.returncode}.{hint}"
        )


def start_daemon_in_container(
    sandbox: TaskSandbox,
    ds_bin: str,
    ds_home: Path,
    port: int,
    env: dict[str, str],
    *,
    ds_repo_root: Path,
    run_root: Path,
) -> None:
    from agent_container import build_container_env

    container_env = build_container_env(
        apply_literature_scrub_to_env(env),
        agent_tool="deepscientist",
        run_root=run_root,
        extra={
            "DEEPSCIENTIST_HOME": str(ds_home.resolve()),
            "DEEPSCIENTIST_REPO_ROOT": str(ds_repo_root.resolve()),
            "DS_SKIP_UPDATE_PROMPT": "1",
        },
    )
    exports = " ".join(
        f"export {key}={shlex.quote(value)};"
        for key, value in sorted(container_env.items())
        if value is not None and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key)
    )
    log_file = ds_home / "logs" / "daemon-container.log"
    log_file.parent.mkdir(parents=True, exist_ok=True)
    shell = (
        f"{exports} cd {shlex.quote(str(run_root.resolve()))} && "
        f"nohup node {shlex.quote(ds_bin)} --home {shlex.quote(str(ds_home.resolve()))} "
        f"--daemon-only --runner opencode --no-browser --host {CONTAINER_DAEMON_HOST} --port {port} "
        f"--skip-update-check >> {shlex.quote(str(log_file))} 2>&1 &"
    )
    print("[deepscientist] starting in-container daemon")
    code, stdout, stderr = sandbox.exec(shell, workdir=str(run_root.resolve()))
    if stdout.strip():
        print(stdout.strip())
    if code != 0:
        detail = (stderr or stdout or "").strip()
        raise RuntimeError(f"Failed to start in-container daemon: {detail}")


def stop_daemon(ds_bin: str, ds_home: Path, env: dict[str, str]) -> None:
    subprocess.run(
        [ds_bin, "--home", str(ds_home), "--stop", "--skip-update-check"],
        env=env,
        check=False,
    )


def stop_all_benchmark_daemons(ds_bin: str, env: dict[str, str]) -> None:
    """Best-effort stop for global and per-run DeepScientist daemons."""
    subprocess.run(
        [ds_bin, "--stop", "--skip-update-check"],
        env=env,
        check=False,
    )
    inputs_root = Path.home() / "ai_scientist_inputs"
    if inputs_root.is_dir():
        for ds_home in inputs_root.glob("*/workspace/deepscientist_*/DeepScientist"):
            if ds_home.is_dir():
                subprocess.run(
                    [ds_bin, "--home", str(ds_home), "--stop", "--skip-update-check"],
                    env=env,
                    check=False,
                )


def build_startup_contract(
    *,
    title: str,
    goal: str,
    launch_markdown: str,
    constraints: str,
    objectives: str,
    run_root: Path,
    execution_mode: str = EXECUTION_MODE_HOST,
) -> dict:
    """Finalized launch contract — skips SetupAgent UI and starts autonomous research directly."""
    return {
        "schema_version": 4,
        "workspace_mode": "autonomous",
        "user_language": "zh",
        "need_research_paper": True,
        "research_intensity": "balanced",
        "decision_policy": "autonomous",
        "launch_mode": "standard",
        "standard_profile": "canonical_research_graph",
        "custom_profile": "freeform",
        "review_followup_policy": "audit_only",
        "baseline_execution_policy": "auto",
        "baseline_source_mode": "skip_until_blocking",
        "execution_start_mode": "execute_immediately",
        "baseline_acceptance_target": "comparison_ready",
        "manuscript_edit_mode": "collaborative",
        "scope": {"kind": "benchmark_task", "paper_required": True},
        "baseline_mode": "allow_degraded_minimal_reproduction",
        "resource_policy": {"gpu_required": False},
        "git_strategy": "branch_per_experiment",
        "runtime_constraints": constraints,
        "objectives": objectives,
        "baseline_urls": "",
        "paper_urls": "",
        "entry_state_summary": "",
        "review_summary": "",
        "review_materials": "",
        "custom_brief": "",
        "launch_form_source": "benchmark",
        "launch_form_recorded_at": datetime.now().astimezone().isoformat(),
        "launch_form": {
            "title": title,
            "goal": goal,
            "baseline_id": "",
            "baseline_variant_id": "",
            "baseline_source_mode": "skip_until_blocking",
            "execution_start_mode": "execute_immediately",
            "baseline_acceptance_target": "comparison_ready",
            "baseline_urls": "",
            "paper_urls": "",
            "runtime_constraints": constraints,
            "objectives": objectives,
            "need_research_paper": True,
            "research_intensity": "balanced",
            "decision_policy": "autonomous",
            "launch_mode": "standard",
            "standard_profile": "canonical_research_graph",
            "custom_profile": "freeform",
            "user_language": "zh",
        },
        "launch_markdown": launch_markdown,
        "project_display": {"template": "experiment", "accent_color": "sage"},
        "benchmark_context": {
            "integration": "ai_scientist_benchmark/run_deepscientist_task.py",
            "host_workspace": str(run_root.resolve()),
            "run_root": str(run_root.resolve()),
            "execution_mode": execution_mode,
            "skip_setup_agent_ui": True,
            "auto_waive_external_baseline": True,
            "full_research_pipeline": True,
        },
    }


def ensure_git_identity(quest_dir: Path) -> None:
    """Avoid checkpoint failures when DeepScientist tries to git-commit quest progress."""
    git_dir = quest_dir / ".git"
    if not git_dir.exists():
        return
    for key, value in (
        ("user.email", "benchmark@local"),
        ("user.name", "AI Scientist Benchmark"),
    ):
        subprocess.run(
            ["git", "-C", str(quest_dir), "config", key, value],
            check=False,
            capture_output=True,
        )


def _stage_skills_ready(python_bin: Path, env: dict[str, str]) -> bool:
    probe = textwrap.dedent(
        """
        import json
        from deepscientist.prompts.builder import current_standard_skills
        skills = current_standard_skills()
        print(json.dumps({"count": len(skills), "skills": list(skills)}))
        """
    ).strip()
    proc = subprocess.run(
        [str(python_bin), "-c", probe],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return False
    try:
        payload = json.loads(proc.stdout.strip() or "{}")
    except json.JSONDecodeError:
        return False
    return int(payload.get("count") or 0) > 0


def wait_for_stage_skills(
    python_bin: Path,
    env: dict[str, str],
    *,
    timeout_sec: float = 60.0,
) -> None:
    deadline = time.time() + timeout_sec
    while time.time() < deadline:
        if _stage_skills_ready(python_bin, env):
            return
        time.sleep(2.0)
    raise TimeoutError(
        "DeepScientist stage skills were not discoverable before baseline waiver. "
        "Ensure DEEPSCIENTIST_REPO_ROOT points at the npm package with src/skills/."
    )


def patch_baseline_gate_waived(quest_dir: Path) -> None:
    """Last-resort fallback when ArtifactService.waive_baseline is unavailable."""
    quest_yaml = quest_dir / "quest.yaml"
    if not quest_yaml.is_file():
        raise FileNotFoundError(f"Missing quest.yaml: {quest_yaml}")
    text = quest_yaml.read_text(encoding="utf-8")
    if "baseline_gate: waived" in text:
        return
    if "baseline_gate: pending" in text:
        text = text.replace("baseline_gate: pending", "baseline_gate: waived", 1)
    elif "baseline_gate:" in text:
        text = re.sub(r"(?m)^baseline_gate:.*$", "baseline_gate: waived", text, count=1)
    else:
        text = text.replace("active_anchor: baseline", "active_anchor: baseline\nbaseline_gate: waived", 1)
    quest_yaml.write_text(text, encoding="utf-8")


def waive_baseline_via_python(
    ds_home: Path,
    quest_id: str,
    reason: str,
    *,
    env: dict[str, str],
) -> dict:
    python_bin = ds_home / "runtime/python-env/bin/python3"
    if not python_bin.exists():
        raise FileNotFoundError(f"DeepScientist python env not found: {python_bin}")

    wait_for_stage_skills(python_bin, env)

    script = textwrap.dedent(
        """
        import json
        import sys
        from pathlib import Path

        from deepscientist.artifact.service import ArtifactService

        home = Path(sys.argv[1])
        quest_id = sys.argv[2]
        reason = sys.argv[3]
        service = ArtifactService(home)
        quest_root = home / "quests" / quest_id
        result = service.waive_baseline(
            quest_root,
            reason=reason,
            auto_advance=True,
        )
        snapshot = result.get("snapshot") if isinstance(result.get("snapshot"), dict) else {}
        print(
            json.dumps(
                {
                    "ok": bool(result.get("ok")),
                    "baseline_gate": result.get("baseline_gate"),
                    "active_anchor": snapshot.get("active_anchor"),
                    "display_status": snapshot.get("display_status") or snapshot.get("status"),
                },
                ensure_ascii=False,
            )
        )
        """
    ).strip()

    last_error = "unknown"
    for attempt in range(1, 4):
        proc = subprocess.run(
            [str(python_bin), "-c", script, str(ds_home), quest_id, reason],
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            payload = json.loads(proc.stdout.strip() or "{}")
            if payload.get("ok"):
                return payload
            last_error = f"waive returned not ok: {proc.stdout.strip()}"
        else:
            last_error = (
                "waive_baseline failed:\n"
                f"stdout={proc.stdout.strip()}\n"
                f"stderr={proc.stderr.strip()}"
            )
        time.sleep(2.0 * attempt)

    quest_dir = ds_home / "quests" / quest_id
    print(f"[deepscientist] warn: ArtifactService.waive_baseline failed, patching quest.yaml: {last_error}")
    patch_baseline_gate_waived(quest_dir)
    return {"ok": True, "baseline_gate": "waived", "active_anchor": "baseline", "fallback": "quest_yaml_patch"}


def auto_launch_quest(
    base_url: str,
    ds_home: Path,
    *,
    ds_subprocess_env: dict[str, str],
    title: str,
    goal: str,
    launch_markdown: str,
    kickoff_message: str,
    constraints: str,
    objectives: str,
    quest_root: Path,
    run_root: Path,
    execution_mode: str = EXECUTION_MODE_HOST,
) -> str:
    startup_contract = build_startup_contract(
        title=title,
        goal=goal,
        launch_markdown=launch_markdown,
        constraints=constraints,
        objectives=objectives,
        run_root=run_root,
        execution_mode=execution_mode,
    )
    payload = http_json(
        "POST",
        f"{base_url}/api/quests",
        {
            "title": title,
            "goal": goal,
            "source": "benchmark",
            "startup_contract": startup_contract,
            "auto_start": False,
        },
        timeout=120.0,
    )
    if not payload.get("ok", True):
        raise RuntimeError(f"Quest creation failed: {json.dumps(payload, ensure_ascii=False)}")
    snapshot = payload.get("snapshot") or {}
    quest_id = str(snapshot.get("quest_id") or "").strip()
    if not quest_id:
        raise RuntimeError(f"Quest creation returned no quest_id: {json.dumps(payload, ensure_ascii=False)}")

    quest_dir = quest_root / quest_id
    if not quest_dir.exists():
        quest_dir = Path(str(snapshot.get("quest_root") or quest_dir))
    link_quest_workspace_dirs(quest_dir, run_root)
    configure_quest_run_workspace(quest_dir, run_root)
    ensure_git_identity(quest_dir)

    waive_reason = (
        "Benchmark task provides only research background and sample data; "
        "no external baseline repository or starter code was supplied. "
        "Waive the external-baseline gate and build the first baseline from dataset_candidate/."
    )
    waive_result = waive_baseline_via_python(
        ds_home,
        quest_id,
        waive_reason,
        env=ds_subprocess_env,
    )
    print(
        "[deepscientist] baseline_gate="
        f"{waive_result.get('baseline_gate')} active_anchor={waive_result.get('active_anchor')}"
    )

    start_payload = http_json(
        "POST",
        f"{base_url}/api/quests/{quest_id}/chat",
        {"text": kickoff_message, "source": "benchmark"},
        timeout=120.0,
    )
    if start_payload.get("ok") is False:
        raise RuntimeError(
            f"Quest kickoff message failed: {json.dumps(start_payload, ensure_ascii=False)}"
        )
    return quest_id


def continue_full_pipeline_quest(
    base_url: str,
    quest_id: str,
    *,
    baseline_already_done: bool = True,
) -> None:
    kickoff = build_full_pipeline_kickoff_message(baseline_already_done=baseline_already_done)
    payload = http_json(
        "POST",
        f"{base_url}/api/quests/{quest_id}/chat",
        {"text": kickoff, "source": "benchmark"},
        timeout=120.0,
    )
    if payload.get("ok") is False:
        raise RuntimeError(
            f"Continue message failed: {json.dumps(payload, ensure_ascii=False)}"
        )
    print(f"[deepscientist] sent full-pipeline continuation to quest={quest_id}")


def wait_for_quest(base_url: str, quest_id: str, timeout_sec: int) -> dict:
    deadline = time.time() + timeout_sec
    last_snapshot: dict = {}
    stable_idle_polls = 0
    while time.time() < deadline:
        snapshot = http_json("GET", f"{base_url}/api/quests/{quest_id}", timeout=30.0)
        last_snapshot = snapshot if isinstance(snapshot, dict) else {}
        status = str(
            last_snapshot.get("display_status")
            or last_snapshot.get("status")
            or ""
        ).strip().lower()
        print(f"[deepscientist] quest={quest_id} status={status or 'unknown'}")
        if status in {"idle", "paused", "completed", "failed", "error"}:
            stable_idle_polls += 1
            if stable_idle_polls >= 3:
                return last_snapshot
        else:
            stable_idle_polls = 0
        time.sleep(20.0)
    raise TimeoutError(
        f"Timed out after {timeout_sec}s waiting for quest `{quest_id}` to settle."
    )


def prepare_run_layout(task_dir: Path) -> tuple[Path, Path, Path]:
    from agent_task_document import build_agent_task_document
    from path_alignment import load_task_env

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_root = task_dir / "workspace" / f"deepscientist_{timestamp}"
    ds_home = run_root / "DeepScientist"
    workspace_root = task_dir / "workspace"
    run_root.mkdir(parents=True, exist_ok=True)
    ds_home.mkdir(parents=True, exist_ok=True)
    task_env = load_task_env(task_dir)
    brief = build_agent_task_document(task_dir, task_env)
    (run_root / "RESEARCH_BRIEF.md").write_text(brief, encoding="utf-8")
    (run_root / "task_input.md").write_text(brief, encoding="utf-8")
    return run_root, ds_home, workspace_root


def main() -> int:
    parser = argparse.ArgumentParser(description="Run DeepScientist in ai_scientist sandbox")
    parser.add_argument(
        "--task-dir",
        default=str(Path.home() / "ai_scientist_inputs" / "ASE-2025-004_predicting_recheck_success_in_continuous"),
        help="Path to task directory under ai_scientist_inputs/",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Override llm model from benchmark_credentials.yaml (models.deepscientist)",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help="DeepScientist daemon port for this run")
    parser.add_argument(
        "--execution-mode",
        choices=(EXECUTION_MODE_HOST, EXECUTION_MODE_DOCKER, EXECUTION_MODE_CONTAINER),
        default=os.getenv("DEEPSCIENTIST_EXECUTION_MODE", EXECUTION_MODE_CONTAINER),
        help=(
            "container: run DeepScientist daemon, opencode, and bash_exec inside TaskSandbox (default). "
            "host: legacy host execution. docker: deprecated alias for container."
        ),
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Block until the quest reaches a settled status (idle/paused/completed/failed)",
    )
    parser.add_argument("--wait-timeout-sec", type=int, default=86400)
    parser.add_argument("--evaluate", action="store_true", help="Run evaluator after the quest settles")
    parser.add_argument(
        "--continue-quest",
        metavar="QUEST_ID",
        help="Send full-pipeline continuation message to an already-running quest on --port, then exit",
    )
    parser.add_argument(
        "--stop-all",
        action="store_true",
        help="Stop all DeepScientist daemons (global + benchmark runs) and exit",
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Stop the DeepScientist daemon and destroy the Docker sandbox when this script exits",
    )
    add_transient_retry_arguments(parser)
    args = parser.parse_args()

    task_dir = Path(args.task_dir).resolve()
    if not task_dir.is_dir():
        print(f"Task directory not found: {task_dir}", file=sys.stderr)
        return 1

    env = os.environ.copy()
    npm_bin = str(Path.home() / ".npm-global/bin")
    env["PATH"] = npm_bin + (":" + env["PATH"] if env.get("PATH") else "")

    if not load_api_env(env):
        print(
            f"Missing OPENAI_API_KEY. Set llm.api_key in {credentials_file_path()} "
            "(or run: python3 integrations/benchmark_credentials.py --init)",
            file=sys.stderr,
        )
        return 1

    args.model = resolve_model("deepscientist", override=args.model, env=env)

    try:
        ds_bin = resolve_ds_bin()
        ds_repo_root = resolve_ds_repo_root(ds_bin)
        opencode_bin = resolve_opencode_bin()
    except FileNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.stop_all:
        stop_all_benchmark_daemons(ds_bin, env)
        print("[deepscientist] stopped all known daemons")
        return 0

    if args.continue_quest:
        base_url = f"http://127.0.0.1:{args.port}"
        try:
            wait_for_daemon(base_url, timeout_sec=15.0)
        except TimeoutError:
            print(
                f"No daemon on {base_url}. Start the quest first or pass the correct --port.",
                file=sys.stderr,
            )
            return 1
        continue_full_pipeline_quest(
            base_url,
            args.continue_quest.strip(),
            baseline_already_done=True,
        )
        print(f"[deepscientist] web_ui={base_url}/quests/{args.continue_quest.strip()}")
        return 0

    run_root, ds_home, _workspace_root = prepare_run_layout(task_dir)
    execution_mode = args.execution_mode
    if execution_mode == EXECUTION_MODE_DOCKER:
        execution_mode = EXECUTION_MODE_CONTAINER
    use_container = execution_mode == EXECUTION_MODE_CONTAINER
    port = pick_daemon_port(args.port)
    if port != args.port:
        print(
            f"[deepscientist] port {args.port} is busy; using {port} instead "
            f"(stop old daemons with --stop-all if needed)",
            file=sys.stderr,
        )
    sandbox = TaskSandbox(task_dir, agent_tool="deepscientist" if use_container else None)
    docker_workdir = docker_workdir_for_run(run_root)

    from agent_container import build_container_env, path_prefix_for

    path_prefix = path_prefix_for("deepscientist") or npm_bin
    if env.get("PATH"):
        path_prefix = f"{path_prefix}:{env['PATH']}" if path_prefix else env["PATH"]

    runner_env = build_benchmark_execution_env(run_root)

    env = apply_literature_scrub_to_env(env)
    from agent_container import apply_run_metering_to_env
    from run_metering import start_run_timer, stop_run_timer, write_manifest_with_metering

    # Meter DeepScientist/OpenCode LLM traffic for this run.
    env = apply_run_metering_to_env(env, run_root=run_root, for_container=use_container)
    scrub_url = scrub_base_url(env)

    base_url = f"http://127.0.0.1:{port}"
    env["OPENAI_API_KEY"] = env["OPENAI_API_KEY"]
    env["DEEPSCIENTIST_HOME"] = str(ds_home)
    env["DEEPSCIENTIST_REPO_ROOT"] = str(ds_repo_root)
    env["DS_SKIP_UPDATE_PROMPT"] = "1"
    ds_subprocess_env = apply_literature_scrub_to_env(
        build_ds_subprocess_env(ds_home, ds_repo_root, env)
    )
    ds_subprocess_env.update(runner_env)

    container_ds_repo = ds_repo_root
    container_ds_bin = ds_bin
    if use_container:
        container_ds_repo, container_ds_bin = stage_writable_ds_repo(ds_repo_root, run_root)
        ds_subprocess_env["DEEPSCIENTIST_REPO_ROOT"] = str(container_ds_repo.resolve())

    task_env = load_task_env(task_dir)
    task_prompt = build_agent_task_document(task_dir, task_env)
    constraints = build_runtime_constraints(
        host_workspace=run_root,
        execution_mode=execution_mode,
        docker_workdir=docker_workdir,
    )
    objectives = build_objectives()
    title, goal = task_title_and_goal(task_dir)
    initial_message = build_startup_message(task_dir, task_env)
    kickoff_message = initial_message

    container_id: str | None = None
    start_run_timer(run_root, phase="agent")
    returncode = 0
    try:
        if use_container:
            sandbox.env["AGENT_PUBLISH_PORTS"] = str(port)
            container_id = sandbox.start(agent_tool="deepscientist", run_root=run_root)
            opencode_config_dir = write_opencode_scrub_config(
                ds_home,
                scrub_base_url=scrub_url,
            )
            runner_env.update(
                build_benchmark_execution_env(
                    run_root,
                    container_id=container_id,
                    docker_workdir=docker_workdir,
                )
            )
            copy_ds_config_template(
                ds_home,
                model=args.model,
                opencode_bin=opencode_bin,
                path_prefix=path_prefix,
                port=port,
                runner_env=runner_env,
                opencode_config_dir=opencode_config_dir,
            )
            print(f"[sandbox] container_id={container_id}")
            seed_task_workspace(sandbox, run_root)
            print(f"[sandbox] seeded {docker_workdir} from {task_dir / 'seeds'}")
            from agent_container import ensure_container_node, preflight_binary, preflight_python, preflight_runtime_mounts

            ok, msg = preflight_python(container_id, run_root)
            print(f"[preflight] {msg}")
            if not ok:
                returncode = 1
                return 1
            ok_node, node_msg = ensure_container_node(container_id)
            print(f"[preflight] {node_msg}")
            if not ok_node:
                returncode = 1
                return 1
            ok_scrub, scrub_msg = preflight_scrub_proxy(container_id, base_url=scrub_url)
            print(f"[preflight] {scrub_msg}")
            if not ok_scrub:
                returncode = 1
                return 1
            ok_bin, bin_msg = preflight_binary(container_id, container_ds_bin, cwd=run_root)
            print(f"[preflight] {bin_msg}")
            if not ok_bin:
                returncode = 1
                return 1
            ok_oc, oc_msg = preflight_binary(container_id, opencode_bin, cwd=run_root)
            print(f"[preflight] {oc_msg}")
            if not ok_oc:
                returncode = 1
                return 1
            ok_mounts, mount_issues = preflight_runtime_mounts(
                container_id, "deepscientist", cwd=run_root
            )
            for issue in mount_issues:
                print(f"[preflight] mount: {issue}", file=sys.stderr)
            if not ok_mounts:
                returncode = 1
                return 1
            start_daemon_in_container(
                sandbox,
                container_ds_bin,
                ds_home,
                port,
                ds_subprocess_env,
                ds_repo_root=container_ds_repo,
                run_root=run_root,
            )
        else:
            opencode_config_dir = write_opencode_scrub_config(
                ds_home,
                scrub_base_url=scrub_url,
            )
            seed_task_workspace_host(run_root, task_dir)
            copy_ds_config_template(
                ds_home,
                model=args.model,
                opencode_bin=opencode_bin,
                path_prefix=path_prefix,
                port=port,
                runner_env=runner_env,
                opencode_config_dir=opencode_config_dir,
            )
            print(f"[sandbox] execution_mode=host run_root={run_root}")
            start_daemon(ds_bin, ds_home, port, ds_subprocess_env)

        wait_for_daemon(base_url)

        auto_transient, max_transient = resolve_transient_retry_policy(args)
        quest_id = ""
        launch_attempt = 0
        while True:
            try:
                quest_id = auto_launch_quest(
                    base_url,
                    ds_home,
                    ds_subprocess_env=ds_subprocess_env,
                    title=title,
                    goal=goal,
                    launch_markdown=initial_message,
                    kickoff_message=kickoff_message,
                    constraints=constraints,
                    objectives=objectives,
                    quest_root=ds_home / "quests",
                    run_root=run_root,
                    execution_mode=execution_mode,
                )
                break
            except Exception as exc:  # noqa: BLE001
                launch_attempt += 1
                probe = probe_transient_failure(
                    returncode=1,
                    log_path=None,
                    stderr_snippet=str(exc),
                )
                if (
                    not auto_transient
                    or not probe.is_transient
                    or launch_attempt > max_transient
                ):
                    raise
                print(
                    f"[retry] deepscientist: quest launch transient "
                    f"({probe.matched or probe.reason}); "
                    f"retry {launch_attempt}/{max_transient}: {exc}",
                    file=sys.stderr,
                )
                time.sleep(min(5 * launch_attempt, 30))

        print(f"[deepscientist] quest_id={quest_id}")
        print(f"[deepscientist] execution_mode={execution_mode}")
        print(f"[deepscientist] web_ui={base_url}/quests/{quest_id}")
        print(f"[deepscientist] ds_home={ds_home}")
        print(f"[deepscientist] run_root={run_root}")
        if use_container:
            print("[deepscientist] execution=in_container (daemon + opencode + bash_exec)")

        if args.wait:
            snapshot = wait_for_quest(base_url, quest_id, args.wait_timeout_sec)
            print(json.dumps(snapshot, ensure_ascii=False, indent=2))
            settle_status = str(
                snapshot.get("display_status") or snapshot.get("status") or ""
            ).strip().lower()
            cont_round = 0
            while (
                settle_status in {"failed", "error", "paused"}
                and auto_transient
                and cont_round < max_transient
            ):
                cont_round += 1
                print(
                    f"[retry] deepscientist: quest settled as {settle_status}; "
                    f"continuation {cont_round}/{max_transient}",
                    file=sys.stderr,
                )
                try:
                    continue_full_pipeline_quest(
                        base_url,
                        quest_id,
                        baseline_already_done=True,
                    )
                except Exception as exc:  # noqa: BLE001
                    probe = probe_transient_failure(
                        returncode=1,
                        log_path=None,
                        stderr_snippet=str(exc),
                    )
                    if not probe.is_transient:
                        print(f"[retry] deepscientist: stop continuation ({exc})", file=sys.stderr)
                        break
                    print(f"[retry] deepscientist: continuation send failed: {exc}", file=sys.stderr)
                    time.sleep(min(5 * cont_round, 30))
                    continue
                snapshot = wait_for_quest(base_url, quest_id, args.wait_timeout_sec)
                print(json.dumps(snapshot, ensure_ascii=False, indent=2))
                settle_status = str(
                    snapshot.get("display_status") or snapshot.get("status") or ""
                ).strip().lower()
            if args.evaluate:
                if use_container and sandbox.container_id:
                    code, stdout, stderr = sandbox.evaluate()
                elif not sandbox.container_id:
                    container_id = sandbox.start(agent_tool="deepscientist", run_root=run_root)
                    seed_task_workspace(sandbox, run_root)
                    code, stdout, stderr = sandbox.evaluate()
                else:
                    code, stdout, stderr = sandbox.evaluate()
                print(stdout.strip())
                if stderr.strip():
                    print(stderr.strip(), file=sys.stderr)
                result_path = task_dir / "evaluator" / "results" / "result.json"
                if result_path.exists():
                    print(json.dumps(json.loads(result_path.read_text(encoding="utf-8")), indent=2, ensure_ascii=False))
                if code != 0:
                    returncode = code
                    return code
        else:
            print("[deepscientist] Quest launched: full pipeline mode (idea → experiment → analysis → write).")
            print("[deepscientist] Monitor progress at the web UI URL above, or rerun with --wait.")
            print(f"[deepscientist] To nudge an existing quest: --continue-quest 001 --port {port}")
            if use_container:
                print("[deepscientist] Daemon and Docker sandbox stay up until you stop them or rerun with --cleanup.")
            else:
                print("[deepscientist] Daemon stays up (no Docker). Use --cleanup to stop the daemon.")

        print(f"Done. Run root: {run_root}")
        returncode = 0
        return 0
    except KeyboardInterrupt:
        print("\n[deepscientist] interrupted", file=sys.stderr)
        returncode = 130
        return 130
    finally:
        stop_run_timer(run_root, phase="agent", returncode=returncode)
        try:
            write_manifest_with_metering(
                run_root / "artifacts" / "manifest.json",
                {
                    "framework": "deepscientist",
                    "run_dir": str(run_root),
                    "returncode": returncode,
                    "quest_id": locals().get("quest_id"),
                    "execution_mode": execution_mode,
                    "status": {"launched": True},
                },
                run_root,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[metering] failed to write manifest: {exc}", file=sys.stderr)
        if args.cleanup:
            stop_daemon(ds_bin, ds_home, env)
            if sandbox.container_id:
                print("[sandbox] cleaning up container...")
                sandbox.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
