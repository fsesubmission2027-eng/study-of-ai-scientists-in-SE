"""Benchmark run metering: wall-clock time, tokens, and USD cost.

Designed for the integration layer only (no upstream tool changes):

1. Wall time — recorded around ``launch_agent`` / explicit timer helpers.
2. Tokens — OpenAI-compatible traffic is routed through ``metering_proxy.py``,
   which appends usage rows to ``<run_dir>/artifacts/usage_ledger.jsonl``.
3. Cost — computed from ``model_pricing.yaml`` (edit when switching models).

Enable/disable with ``BENCHMARK_METERING=1|0`` (default: enabled).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

INTEGRATIONS_ROOT = Path(__file__).resolve().parent
DEFAULT_PRICING_PATH = INTEGRATIONS_ROOT / "model_pricing.yaml"
DEFAULT_METERING_PORT = 8788
HOST_GATEWAY_ALIAS = "host.docker.internal"
REGISTRY_PATH = Path.home() / ".cache" / "ai_scientist_benchmark" / "metering_registry.json"
PROXY_LOG_PATH = Path.home() / ".cache" / "ai_scientist_benchmark" / "metering_proxy.log"
PROXY_PID_PATH = Path.home() / ".cache" / "ai_scientist_benchmark" / "metering_proxy.pid"

_USAGE_RE = re.compile(
    r"\[Usage:\s*([\d,]+)\s*in\s*[·.]\s*([\d,]+)\s*out\]",
    re.IGNORECASE,
)


def metering_enabled(env: dict[str, str] | None = None) -> bool:
    source = env if env is not None else os.environ
    raw = (source.get("BENCHMARK_METERING") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _local_now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def is_metering_proxy_url(value: str) -> bool:
    lower = (value or "").lower()
    if not lower:
        return False
    if f":{DEFAULT_METERING_PORT}" in lower:
        return True
    return "/m/" in lower and ("/v1" in lower or lower.rstrip("/").endswith("/v1"))


def run_token_for(run_dir: Path) -> str:
    digest = hashlib.sha1(str(run_dir.resolve()).encode("utf-8")).hexdigest()
    return digest[:16]


def ledger_path_for(run_dir: Path) -> Path:
    return run_dir.resolve() / "artifacts" / "usage_ledger.jsonl"


def timing_path_for(run_dir: Path) -> Path:
    return run_dir.resolve() / "artifacts" / "timing.json"


def usage_summary_path_for(run_dir: Path) -> Path:
    return run_dir.resolve() / "artifacts" / "usage_summary.json"


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception:  # noqa: BLE001
        # Minimal fallback parser for our flat pricing file.
        return _parse_pricing_fallback(path)


def _parse_pricing_fallback(path: Path) -> dict[str, Any]:
    """Tiny YAML subset parser so metering works without PyYAML."""
    text = path.read_text(encoding="utf-8")
    default: dict[str, float] = {}
    models: dict[str, dict[str, float]] = {}
    section = None
    current_model: str | None = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if indent == 0 and stripped.endswith(":"):
            section = stripped[:-1]
            current_model = None
            continue
        if section == "default" and ":" in stripped:
            key, val = stripped.split(":", 1)
            try:
                default[key.strip()] = float(val.strip())
            except ValueError:
                pass
            continue
        if section == "models":
            if indent == 2 and stripped.endswith(":"):
                current_model = stripped[:-1].strip().strip("'\"")
                models[current_model] = {}
                continue
            if current_model and indent >= 4 and ":" in stripped:
                key, val = stripped.split(":", 1)
                try:
                    models[current_model][key.strip()] = float(val.strip())
                except ValueError:
                    pass
    return {"default": default, "models": models}


def load_pricing(path: Path | None = None) -> dict[str, Any]:
    return _load_yaml(path or Path(os.environ.get("BENCHMARK_PRICING_FILE") or DEFAULT_PRICING_PATH))


def lookup_pricing(model: str, pricing: dict[str, Any] | None = None) -> tuple[float, float, str]:
    """Return (input_per_mtok, output_per_mtok, matched_key) for flat pricing."""
    data = pricing if pricing is not None else load_pricing()
    models = data.get("models") if isinstance(data.get("models"), dict) else {}
    default = data.get("default") if isinstance(data.get("default"), dict) else {}
    candidates = _model_lookup_candidates(model)
    for key in candidates:
        entry = models.get(key)
        if isinstance(entry, dict):
            return (
                float(entry.get("input_per_mtok") or 0.0),
                float(entry.get("output_per_mtok") or 0.0),
                key,
            )
    return (
        float(default.get("input_per_mtok") or 0.0),
        float(default.get("output_per_mtok") or 0.0),
        "default",
    )


def _model_lookup_candidates(model: str) -> list[str]:
    candidates = [model]
    if model.startswith("modelverse/"):
        candidates.append(model.split("/", 1)[-1])
    if "/" in model:
        candidates.append(model.split("/", 1)[-1])
    return candidates


def _lookup_model_entry(model: str, pricing: dict[str, Any]) -> tuple[dict[str, Any], str] | tuple[None, str]:
    models = pricing.get("models") if isinstance(pricing.get("models"), dict) else {}
    for key in _model_lookup_candidates(model):
        entry = models.get(key)
        if isinstance(entry, dict):
            return entry, key
    return None, "default"


def _parse_hhmm(value: str) -> int:
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def _is_peak_beijing(ts: str | None, peak_windows: list[Any] | None) -> bool:
    if not ts or not peak_windows:
        return False
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(
            timezone(timedelta(hours=8))
        )
    except ValueError:
        return False
    minute_of_day = dt.hour * 60 + dt.minute
    for window in peak_windows:
        if not isinstance(window, (list, tuple)) or len(window) != 2:
            continue
        start = _parse_hhmm(str(window[0]))
        end = _parse_hhmm(str(window[1]))
        if start <= minute_of_day < end:
            return True
    return False


def _cached_tokens_from_event(event: dict[str, Any]) -> int | None:
    raw = event.get("raw_usage")
    if isinstance(raw, dict):
        details = raw.get("prompt_tokens_details")
        if isinstance(details, dict) and details.get("cached_tokens") is not None:
            try:
                return max(0, int(details["cached_tokens"]))
            except (TypeError, ValueError):
                pass
    if event.get("cached_tokens") is not None:
        try:
            return max(0, int(event["cached_tokens"]))
        except (TypeError, ValueError):
            return None
    return None


def _tiered_rates(entry: dict[str, Any], *, peak: bool) -> dict[str, float] | None:
    tier_key = "peak" if peak else "off_peak"
    tier = entry.get(tier_key)
    if not isinstance(tier, dict):
        return None
    cache_rate = tier.get("cache_per_mtok")
    if cache_rate is None:
        return None
    return {
        "input_per_mtok": float(tier.get("input_per_mtok") or 0.0),
        "cache_per_mtok": float(cache_rate),
        "output_per_mtok": float(tier.get("output_per_mtok") or 0.0),
        "currency": str(entry.get("currency") or "CNY").upper(),
        "cny_usd_rate": float(entry.get("cny_usd_rate") or 7.2),
    }


def cost_for_usage_event(
    event: dict[str, Any],
    pricing: dict[str, Any] | None = None,
) -> tuple[float, float, str, bool, str]:
    """Return (cost_usd, cost_cny, matched_key, priced, pricing_mode).

    pricing_mode is ``tiered_cache`` when cache/peak rates apply, else ``flat``.
    """
    pricing = pricing if pricing is not None else load_pricing()
    model = str(event.get("model") or "unknown")
    prompt = int(event.get("prompt_tokens") or 0)
    completion = int(event.get("completion_tokens") or 0)
    cached = _cached_tokens_from_event(event)
    entry, matched = _lookup_model_entry(model, pricing)
    if entry is not None and cached is not None:
        peak = _is_peak_beijing(event.get("ts"), entry.get("peak_hours_beijing"))
        tier = _tiered_rates(entry, peak=peak)
        if tier is not None:
            miss = max(0, prompt - cached)
            cost_cny = (
                cached / 1_000_000.0 * tier["cache_per_mtok"]
                + miss / 1_000_000.0 * tier["input_per_mtok"]
                + completion / 1_000_000.0 * tier["output_per_mtok"]
            )
            rate = tier["cny_usd_rate"] if tier["currency"] == "CNY" else 1.0
            cost_usd = cost_cny / rate if rate > 0 else cost_cny
            priced = matched != "default" or cost_cny > 0
            return cost_usd, cost_cny, matched, priced, "tiered_cache"
    cost_usd, matched, priced = cost_usd_for(model, prompt, completion, pricing)
    return cost_usd, 0.0, matched, priced, "flat"


def cost_usd_for(model: str, prompt_tokens: int, completion_tokens: int, pricing: dict[str, Any] | None = None) -> tuple[float, str, bool]:
    inp, out, matched = lookup_pricing(model, pricing)
    cost = (prompt_tokens / 1_000_000.0) * inp + (completion_tokens / 1_000_000.0) * out
    priced = matched != "default" or (inp > 0 or out > 0)
    return cost, matched, priced


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _proxy_health(port: int = DEFAULT_METERING_PORT) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=2) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return bool(body.get("ok"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, json.JSONDecodeError):
        return False


def ensure_metering_proxy(*, upstream: str, port: int = DEFAULT_METERING_PORT) -> None:
    """Start the metering proxy on the host if it is not already healthy."""
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if _proxy_health(port):
        return

    env = os.environ.copy()
    env["METERING_BIND"] = "0.0.0.0"
    env["METERING_PORT"] = str(port)
    env["METERING_UPSTREAM"] = upstream.rstrip("/")
    env["METERING_REGISTRY"] = str(REGISTRY_PATH)
    # Per-run USD budget cap enforced by the proxy (default $30; 0 disables).
    env["METERING_MAX_COST_USD"] = (os.environ.get("BENCHMARK_MAX_COST_USD") or "30").strip()
    env["METERING_PRICING_PATH"] = str(DEFAULT_PRICING_PATH)

    PROXY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_fh = PROXY_LOG_PATH.open("a", encoding="utf-8")
    proc = subprocess.Popen(  # noqa: S603
        [sys.executable, str(INTEGRATIONS_ROOT / "metering_proxy.py")],
        env=env,
        stdout=log_fh,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    PROXY_PID_PATH.write_text(str(proc.pid), encoding="utf-8")

    for _ in range(40):
        if _proxy_health(port):
            return
        time.sleep(0.1)
    raise RuntimeError(
        f"Metering proxy failed to start on port {port}. See {PROXY_LOG_PATH}"
    )


def _register_token(
    token: str,
    *,
    ledger: Path,
    upstream: str,
    run_dir: Path,
) -> None:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REGISTRY_PATH.open("a+", encoding="utf-8") as fh:
        # Simple file lock via exclusive rewrite under advisory lock when available.
        pass
    data: dict[str, Any]
    if REGISTRY_PATH.is_file():
        try:
            data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {"tokens": {}}
    else:
        data = {"tokens": {}}
    tokens = data.setdefault("tokens", {})
    tokens[token] = {
        "ledger": str(ledger),
        "upstream": upstream.rstrip("/"),
        "run_dir": str(run_dir.resolve()),
        "updated_at": _now_iso(),
    }
    tmp = REGISTRY_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(REGISTRY_PATH)


@dataclass
class MeteringSession:
    run_dir: Path
    token: str
    upstream: str
    ledger_path: Path
    port: int = DEFAULT_METERING_PORT

    def host_base_url(self) -> str:
        return f"http://127.0.0.1:{self.port}/m/{self.token}/v1"

    def container_base_url(self) -> str:
        return f"http://{HOST_GATEWAY_ALIAS}:{self.port}/m/{self.token}/v1"

    def base_url(self, *, for_container: bool) -> str:
        return self.container_base_url() if for_container else self.host_base_url()

    def apply_to_env(self, env: dict[str, str], *, for_container: bool) -> dict[str, str]:
        merged = env.copy()
        base = self.base_url(for_container=for_container)
        for key in (
            "OPENAI_API_BASE",
            "OPENAI_BASE_URL",
            "API_BASE_URL",
            # EvoScientist (and other OpenAI-SDK clients) append /chat/completions
            # to this base; the metering proxy only serves under .../m/<token>/v1.
            "CUSTOM_OPENAI_BASE_URL",
        ):
            merged[key] = base
        merged["BENCHMARK_METERING_TOKEN"] = self.token
        merged["BENCHMARK_METERING_LEDGER"] = str(self.ledger_path)
        return merged


def begin_run_metering(
    run_dir: Path,
    *,
    upstream: str,
    for_container: bool = True,
    port: int = DEFAULT_METERING_PORT,
) -> MeteringSession | None:
    """Register this run with the metering proxy and return a session.

    Returns None when metering is disabled.
    """
    if not metering_enabled():
        return None
    run_dir = run_dir.resolve()
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    ledger = ledger_path_for(run_dir)
    if not ledger.exists():
        ledger.write_text("", encoding="utf-8")
    token = run_token_for(run_dir)
    ensure_metering_proxy(upstream=upstream, port=port)
    _register_token(token, ledger=ledger, upstream=upstream, run_dir=run_dir)
    session = MeteringSession(
        run_dir=run_dir,
        token=token,
        upstream=upstream.rstrip("/"),
        ledger_path=ledger,
        port=port,
    )
    meta = {
        "token": token,
        "upstream": session.upstream,
        "ledger": str(ledger),
        "host_base_url": session.host_base_url(),
        "container_base_url": session.container_base_url(),
        "for_container": for_container,
        "started_at": _now_iso(),
    }
    (run_dir / "artifacts" / "metering.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return session


def start_run_timer(run_dir: Path, *, phase: str = "agent") -> dict[str, Any]:
    run_dir = run_dir.resolve()
    (run_dir / "artifacts").mkdir(parents=True, exist_ok=True)
    path = timing_path_for(run_dir)
    data: dict[str, Any] = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    phases = data.setdefault("phases", {})
    phases[phase] = {
        "started_at": _local_now_iso(),
        "started_at_unix": time.time(),
    }
    data["updated_at"] = _local_now_iso()
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return phases[phase]


def stop_run_timer(
    run_dir: Path,
    *,
    phase: str = "agent",
    returncode: int | None = None,
) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    path = timing_path_for(run_dir)
    data: dict[str, Any] = {}
    if path.is_file():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}
    phases = data.setdefault("phases", {})
    phase_data = phases.get(phase) or {}
    started = float(phase_data.get("started_at_unix") or time.time())
    ended = time.time()
    duration = max(0.0, ended - started)
    phase_data.update(
        {
            "ended_at": _local_now_iso(),
            "ended_at_unix": ended,
            "duration_sec": round(duration, 3),
            "returncode": returncode,
        }
    )
    phases[phase] = phase_data
    # Aggregate wall clock across phases (sum). Also expose primary agent duration.
    total = sum(
        float(item.get("duration_sec") or 0.0)
        for item in phases.values()
        if isinstance(item, dict)
    )
    data["phases"] = phases
    data["duration_sec"] = round(total, 3)
    data["agent_duration_sec"] = float((phases.get("agent") or {}).get("duration_sec") or 0.0)
    data["updated_at"] = _local_now_iso()
    if returncode is not None:
        data["returncode"] = returncode
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return data


def read_ledger_events(run_dir: Path) -> list[dict[str, Any]]:
    path = ledger_path_for(run_dir)
    if not path.is_file():
        return []
    events: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            events.append(row)
    return events


def parse_evoscientist_usage_from_log(log_path: Path) -> list[dict[str, Any]]:
    if not log_path.is_file():
        return []
    events: list[dict[str, Any]] = []
    text = log_path.read_text(encoding="utf-8", errors="replace")
    for match in _USAGE_RE.finditer(text):
        prompt = int(match.group(1).replace(",", ""))
        completion = int(match.group(2).replace(",", ""))
        events.append(
            {
                "ts": None,
                "path": "log:[Usage]",
                "model": "unknown",
                "stream": False,
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": prompt + completion,
                "source": "evoscientist_log",
            }
        )
    return events


def summarize_usage_events(
    events: list[dict[str, Any]],
    *,
    pricing: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pricing = pricing if pricing is not None else load_pricing()
    by_model: dict[str, dict[str, Any]] = {}
    prompt_total = 0
    completion_total = 0
    cached_prompt_total = 0
    cost_total = 0.0
    cost_cny_total = 0.0
    cost_flat_total = 0.0
    tiered_calls = 0
    flat_calls = 0
    priced_calls = 0
    unpriced_calls = 0

    for event in events:
        model = str(event.get("model") or "unknown")
        prompt = int(event.get("prompt_tokens") or 0)
        completion = int(event.get("completion_tokens") or 0)
        cached = _cached_tokens_from_event(event) or 0
        cost, cost_cny, matched, priced, mode = cost_for_usage_event(event, pricing)
        flat_cost, _, _ = cost_usd_for(model, prompt, completion, pricing)
        prompt_total += prompt
        completion_total += completion
        cached_prompt_total += cached
        cost_total += cost
        cost_cny_total += cost_cny
        cost_flat_total += flat_cost
        if mode == "tiered_cache":
            tiered_calls += 1
        else:
            flat_calls += 1
        if priced and matched != "default":
            priced_calls += 1
        else:
            unpriced_calls += 1
        bucket = by_model.setdefault(
            model,
            {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "cached_prompt_tokens": 0,
                "total_tokens": 0,
                "calls": 0,
                "cost_usd": 0.0,
                "cost_cny": 0.0,
                "cost_usd_flat": 0.0,
                "tiered_cache_calls": 0,
                "pricing_key": matched,
            },
        )
        bucket["prompt_tokens"] += prompt
        bucket["completion_tokens"] += completion
        bucket["cached_prompt_tokens"] += cached
        bucket["total_tokens"] += prompt + completion
        bucket["calls"] += 1
        bucket["cost_usd"] = round(float(bucket["cost_usd"]) + cost, 6)
        bucket["cost_cny"] = round(float(bucket.get("cost_cny") or 0.0) + cost_cny, 6)
        bucket["cost_usd_flat"] = round(float(bucket.get("cost_usd_flat") or 0.0) + flat_cost, 6)
        if mode == "tiered_cache":
            bucket["tiered_cache_calls"] = int(bucket.get("tiered_cache_calls") or 0) + 1
        bucket["pricing_key"] = matched

    return {
        "calls": len(events),
        "prompt_tokens": prompt_total,
        "cached_prompt_tokens": cached_prompt_total,
        "completion_tokens": completion_total,
        "total_tokens": prompt_total + completion_total,
        "cost_usd": round(cost_total, 6),
        "cost_cny": round(cost_cny_total, 6),
        "cost_usd_flat": round(cost_flat_total, 6),
        "tiered_cache_calls": tiered_calls,
        "flat_pricing_calls": flat_calls,
        "priced_calls": priced_calls,
        "unpriced_calls": unpriced_calls,
        "by_model": by_model,
        "pricing_file": str(Path(os.environ.get("BENCHMARK_PRICING_FILE") or DEFAULT_PRICING_PATH)),
        "note": (
            "cost_usd uses tiered cache pricing when model_pricing.yaml defines peak/off_peak "
            "cache rates and the ledger row includes raw_usage.prompt_tokens_details.cached_tokens; "
            "cost_usd_flat keeps the legacy flat prompt rate. "
            "Update integrations/model_pricing.yaml when switching models."
        ),
    }


def finalize_run_usage(
    run_dir: Path,
    *,
    extra_events: list[dict[str, Any]] | None = None,
    log_path: Path | None = None,
) -> dict[str, Any]:
    """Aggregate ledger (+ optional log fallback) into usage_summary.json."""
    run_dir = run_dir.resolve()
    events = read_ledger_events(run_dir)
    sources = ["usage_ledger.jsonl"] if events else []
    if extra_events:
        events = list(events) + list(extra_events)
        sources.append("extra_events")
    if not events and log_path is not None:
        fallback = parse_evoscientist_usage_from_log(log_path)
        if fallback:
            events = fallback
            sources.append(str(log_path.name))

    summary = summarize_usage_events(events)
    timing = {}
    tpath = timing_path_for(run_dir)
    if tpath.is_file():
        try:
            timing = json.loads(tpath.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            timing = {}

    payload = {
        "run_dir": str(run_dir),
        "generated_at": _local_now_iso(),
        "sources": sources,
        "timing": {
            "duration_sec": timing.get("duration_sec"),
            "agent_duration_sec": timing.get("agent_duration_sec"),
            "phases": timing.get("phases"),
        },
        "usage": summary,
    }
    out = usage_summary_path_for(run_dir)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return payload


def attach_metering_to_manifest(
    manifest: dict[str, Any],
    run_dir: Path,
    *,
    log_path: Path | None = None,
) -> dict[str, Any]:
    """Mutate/return manifest with timing + usage + cost fields."""
    summary = finalize_run_usage(run_dir, log_path=log_path)
    usage = summary.get("usage") or {}
    timing = summary.get("timing") or {}
    manifest["timing"] = {
        "duration_sec": timing.get("duration_sec"),
        "agent_duration_sec": timing.get("agent_duration_sec"),
        "phases": timing.get("phases"),
    }
    manifest["usage"] = {
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
        "calls": usage.get("calls", 0),
        "by_model": usage.get("by_model", {}),
        "sources": summary.get("sources", []),
    }
    manifest["cost"] = {
        "usd": usage.get("cost_usd", 0.0),
        "currency": "USD",
        "priced_calls": usage.get("priced_calls", 0),
        "unpriced_calls": usage.get("unpriced_calls", 0),
        "pricing_file": usage.get("pricing_file"),
        "note": usage.get("note"),
    }
    return manifest


def write_manifest_with_metering(
    manifest_path: Path,
    manifest: dict[str, Any],
    run_dir: Path,
    *,
    log_path: Path | None = None,
) -> Path:
    attach_metering_to_manifest(manifest, run_dir, log_path=log_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest_path


def record_manual_usage(
    run_dir: Path,
    *,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    source: str = "manual",
) -> None:
    """Append a usage row (e.g. from TinyScientist BudgetChecker monkeypatch)."""
    if not metering_enabled():
        return
    path = ledger_path_for(run_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": _now_iso(),
        "path": source,
        "model": model,
        "stream": False,
        "prompt_tokens": int(prompt_tokens),
        "completion_tokens": int(completion_tokens),
        "total_tokens": int(prompt_tokens) + int(completion_tokens),
        "source": source,
    }
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
