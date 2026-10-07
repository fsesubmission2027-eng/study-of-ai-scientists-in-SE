#!/usr/bin/env python3
"""OpenAI-compatible reverse proxy that records token usage per benchmark run.

URL shape (preferred)::

    http://127.0.0.1:8788/m/<token>/v1/chat/completions

The token is registered by ``run_metering.begin_run_metering`` and maps to a
per-run JSONL ledger under ``<run_dir>/artifacts/usage_ledger.jsonl``.

Also accepts plain ``/v1/...`` when ``METERING_DEFAULT_LEDGER`` is set.
"""

from __future__ import annotations

import json
import os
import sys
import threading
import traceback
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

BIND = os.environ.get("METERING_BIND", "0.0.0.0")
PORT = int(os.environ.get("METERING_PORT", "8788"))
DEFAULT_UPSTREAM = os.environ.get(
    "METERING_UPSTREAM", "https://api-sg.umodelverse.ai/v1"
).rstrip("/")
REGISTRY_PATH = Path(
    os.environ.get(
        "METERING_REGISTRY",
        str(Path.home() / ".cache" / "ai_scientist_benchmark" / "metering_registry.json"),
    )
)
DEFAULT_LEDGER = (os.environ.get("METERING_DEFAULT_LEDGER") or "").strip()

# Per-run USD budget cap. When cumulative spend on a ledger reaches this value,
# further model calls are refused with HTTP 403 so the agent stops. 0 disables.
MAX_COST_USD = float(os.environ.get("METERING_MAX_COST_USD", "0") or 0.0)
PRICING_PATH = (os.environ.get("METERING_PRICING_PATH") or "").strip()

_registry_lock = threading.Lock()
_ledger_locks: dict[str, threading.Lock] = {}
_ledger_locks_guard = threading.Lock()

# Cumulative USD spend per ledger path (lazily seeded from the ledger file).
_ledger_cost: dict[str, float] = {}
_ledger_cost_guard = threading.Lock()

# Pricing lookup + cost function, imported lazily from run_metering.
_PRICING: dict[str, Any] | None = None
_COST_FN = None


def _load_pricing_and_cost() -> None:
    global _PRICING, _COST_FN
    if _COST_FN is not None:
        return
    try:
        if str(Path(__file__).resolve().parent) not in sys.path:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
        from run_metering import cost_for_usage_event, load_pricing

        _COST_FN = cost_for_usage_event
        _PRICING = load_pricing(Path(PRICING_PATH) if PRICING_PATH else None)
    except Exception:  # noqa: BLE001
        _COST_FN = None
        _PRICING = {}


def _cost_of(
    model: str,
    prompt: int,
    completion: int,
    *,
    cached: int | None = None,
    ts: str | None = None,
    raw_usage: dict[str, Any] | None = None,
) -> float:
    _load_pricing_and_cost()
    if _COST_FN is None:
        return 0.0
    try:
        event = {
            "model": model,
            "prompt_tokens": int(prompt or 0),
            "completion_tokens": int(completion or 0),
            "ts": ts,
            "raw_usage": raw_usage,
        }
        if cached is not None:
            event["cached_tokens"] = cached
        cost_usd, _, _, _, _ = _COST_FN(event, _PRICING)
        return float(cost_usd)
    except Exception:  # noqa: BLE001
        return 0.0


def _sum_ledger_cost(ledger: str) -> float:
    path = Path(ledger)
    if not path.is_file():
        return 0.0
    total = 0.0
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            total += _cost_of(
                str(row.get("model") or ""),
                row.get("prompt_tokens") or 0,
                row.get("completion_tokens") or 0,
                raw_usage=row.get("raw_usage") if isinstance(row.get("raw_usage"), dict) else None,
                ts=row.get("ts"),
            )
    except OSError:
        return total
    return total


def _cumulative_cost(ledger: str) -> float:
    with _ledger_cost_guard:
        if ledger not in _ledger_cost:
            _ledger_cost[ledger] = _sum_ledger_cost(ledger)
        return _ledger_cost[ledger]


def _add_cost(ledger: str, cost: float) -> float:
    with _ledger_cost_guard:
        base = _ledger_cost.get(ledger)
        if base is None:
            base = _sum_ledger_cost(ledger)
        base += cost
        _ledger_cost[ledger] = base
        return base


def _budget_exceeded(ledger: str | None) -> bool:
    if not ledger or MAX_COST_USD <= 0:
        return False
    return _cumulative_cost(ledger) >= MAX_COST_USD


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_registry() -> dict[str, Any]:
    if not REGISTRY_PATH.is_file():
        return {"tokens": {}}
    try:
        data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"tokens": {}}
    if not isinstance(data, dict):
        return {"tokens": {}}
    tokens = data.get("tokens")
    if not isinstance(tokens, dict):
        data["tokens"] = {}
    return data


def resolve_route(path: str) -> tuple[str, str | None, str]:
    """Return (upstream_suffix_path, ledger_path|None, upstream_base).

    ``path`` is the request path without query string.
    """
    registry = _load_registry()
    tokens: dict[str, Any] = registry.get("tokens") or {}

    # /m/<token>/v1/...
    parts = path.split("?")[0].split("/")
    # ['', 'm', token, 'v1', ...]
    if len(parts) >= 4 and parts[1] == "m" and parts[3] == "v1":
        token = parts[2]
        entry = tokens.get(token) or {}
        ledger = entry.get("ledger")
        upstream = (entry.get("upstream") or DEFAULT_UPSTREAM).rstrip("/")
        suffix = "/" + "/".join(parts[3:])  # /v1/...
        return suffix, str(ledger) if ledger else None, upstream

    # plain /v1/...
    if path.startswith("/v1/") or path == "/v1":
        ledger = DEFAULT_LEDGER or None
        return path, ledger, DEFAULT_UPSTREAM

    return path, DEFAULT_LEDGER or None, DEFAULT_UPSTREAM


def upstream_url(upstream_base: str, suffix: str) -> str:
    if suffix.startswith("/v1/"):
        return upstream_base.rstrip("/") + suffix[len("/v1") :]
    if suffix == "/v1":
        return upstream_base.rstrip("/")
    return upstream_base.rstrip("/") + suffix


def _ledger_lock(path: str) -> threading.Lock:
    with _ledger_locks_guard:
        lock = _ledger_locks.get(path)
        if lock is None:
            lock = threading.Lock()
            _ledger_locks[path] = lock
        return lock


def append_usage(ledger: str | None, record: dict[str, Any]) -> None:
    if not ledger:
        return
    path = Path(ledger)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=False) + "\n"
    with _ledger_lock(str(path)):
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)
    # Keep the in-memory budget counter in sync with what we just billed.
    _add_cost(
        str(path),
        _cost_of(
            str(record.get("model") or ""),
            record.get("prompt_tokens") or 0,
            record.get("completion_tokens") or 0,
            raw_usage=record.get("raw_usage") if isinstance(record.get("raw_usage"), dict) else None,
            ts=record.get("ts"),
        ),
    )


def extract_usage_from_json(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    usage = payload.get("usage")
    if not isinstance(usage, dict):
        return None
    prompt = usage.get("prompt_tokens")
    if prompt is None:
        prompt = usage.get("input_tokens")
    completion = usage.get("completion_tokens")
    if completion is None:
        completion = usage.get("output_tokens")
    total = usage.get("total_tokens")
    try:
        prompt_i = int(prompt or 0)
        completion_i = int(completion or 0)
        total_i = int(total) if total is not None else prompt_i + completion_i
    except (TypeError, ValueError):
        return None
    return {
        "prompt_tokens": prompt_i,
        "completion_tokens": completion_i,
        "total_tokens": total_i,
        "raw_usage": usage,
    }


def extract_usage_from_sse(body: bytes) -> dict[str, Any] | None:
    """Scan SSE / stream chunks for a final usage object."""
    text = body.decode("utf-8", errors="replace")
    last: dict[str, Any] | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if not data or data == "[DONE]":
            continue
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            continue
        usage = extract_usage_from_json(payload)
        if usage:
            last = usage
            # Some providers only put usage on the final chunk.
    return last


def model_from_request(raw: bytes) -> str:
    try:
        data = json.loads(raw.decode("utf-8") if raw else "{}")
    except json.JSONDecodeError:
        return ""
    if isinstance(data, dict):
        return str(data.get("model") or "")
    return ""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _read_body(self) -> bytes:
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length <= 0:
            return b""
        return self.rfile.read(length)

    def _send_bytes(
        self,
        code: int,
        body: bytes,
        content_type: str,
        extra: dict[str, str] | None = None,
    ) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        if extra:
            for key, value in extra.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _proxy(self, method: str) -> None:
        path_only = self.path.split("?", 1)[0]
        qs = ""
        if "?" in self.path:
            qs = "?" + self.path.split("?", 1)[1]

        suffix, ledger, upstream = resolve_route(path_only)
        target = upstream_url(upstream, suffix) + qs
        raw = self._read_body() if method in {"POST", "PUT", "PATCH"} else b""
        model = model_from_request(raw) if raw else ""

        # Enforce the per-run USD budget cap before spending more upstream tokens.
        if method == "POST" and _budget_exceeded(ledger):
            spent = _cumulative_cost(ledger)
            err = json.dumps(
                {
                    "error": {
                        "message": (
                            f"benchmark budget cap reached: ${spent:.2f} >= "
                            f"${MAX_COST_USD:.2f} (METERING_MAX_COST_USD). "
                            "Stopping run to avoid further spend."
                        ),
                        "type": "permission_error",
                        "code": "budget_exceeded",
                        "param": None,
                    }
                }
            ).encode()
            self._send_bytes(403, err, "application/json")
            return

        headers: dict[str, str] = {}
        for key in (
            "Authorization",
            "Content-Type",
            "Accept",
            "User-Agent",
            "OpenAI-Organization",
            "x-api-key",
            "api-key",
        ):
            val = self.headers.get(key)
            if val:
                headers[key] = val
        if "Authorization" not in headers and self.headers.get("api-key"):
            headers["Authorization"] = f"Bearer {self.headers.get('api-key')}"
        if "Authorization" not in headers and self.headers.get("x-api-key"):
            headers["Authorization"] = f"Bearer {self.headers.get('x-api-key')}"

        wants_stream = False
        if method == "POST" and raw:
            try:
                data = json.loads(raw.decode("utf-8"))
                if isinstance(data, dict):
                    wants_stream = bool(data.get("stream") is True)
            except json.JSONDecodeError:
                pass

        req = Request(
            target,
            data=raw if method in {"POST", "PUT", "PATCH"} else None,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(req, timeout=600) as resp:  # noqa: S310
                ctype = resp.headers.get("Content-Type", "application/json")
                is_sse = wants_stream or "text/event-stream" in (ctype or "")
                if is_sse:
                    chunks: list[bytes] = []
                    self.send_response(resp.status)
                    self.send_header("Content-Type", ctype or "text/event-stream")
                    self.send_header("Cache-Control", "no-cache")
                    self.send_header("Connection", "close")
                    self.send_header("X-Accel-Buffering", "no")
                    self.end_headers()
                    while True:
                        chunk = resp.read(4096)
                        if not chunk:
                            break
                        chunks.append(chunk)
                        self.wfile.write(chunk)
                        self.wfile.flush()
                    usage = extract_usage_from_sse(b"".join(chunks))
                    if usage:
                        append_usage(
                            ledger,
                            {
                                "ts": _now(),
                                "path": path_only,
                                "model": model,
                                "stream": True,
                                **usage,
                            },
                        )
                else:
                    resp_body = resp.read()
                    self._send_bytes(resp.status, resp_body, ctype)
                    if method == "POST":
                        try:
                            payload = json.loads(resp_body.decode("utf-8"))
                        except (UnicodeDecodeError, json.JSONDecodeError):
                            payload = None
                        usage = extract_usage_from_json(payload)
                        if usage:
                            append_usage(
                                ledger,
                                {
                                    "ts": _now(),
                                    "path": path_only,
                                    "model": model,
                                    "stream": False,
                                    **usage,
                                },
                            )
        except HTTPError as exc:
            err_body = exc.read() if exc.fp is not None else str(exc).encode()
            ctype = (
                exc.headers.get("Content-Type", "application/json")
                if exc.headers
                else "application/json"
            )
            self._send_bytes(exc.code, err_body, ctype)
        except URLError as exc:
            msg = json.dumps({"error": f"upstream unreachable: {exc}"}).encode()
            self._send_bytes(502, msg, "application/json")
        except Exception as exc:  # noqa: BLE001
            msg = json.dumps(
                {"error": str(exc), "trace": traceback.format_exc()[-1000:]}
            ).encode()
            self._send_bytes(500, msg, "application/json")

    def do_GET(self) -> None:  # noqa: N802
        path_only = self.path.split("?", 1)[0]
        if path_only in {"/", "/health", "/v1/health"} or path_only.endswith("/health"):
            body = json.dumps(
                {
                    "ok": True,
                    "service": "benchmark-metering-proxy",
                    "upstream_default": DEFAULT_UPSTREAM,
                    "listen": f"http://{BIND}:{PORT}",
                    "registry": str(REGISTRY_PATH),
                }
            ).encode()
            self._send_bytes(200, body, "application/json")
            return
        self._proxy("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._proxy("POST")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()


def main() -> int:
    REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer((BIND, PORT), Handler)
    print(
        f"[metering] listening on http://{BIND}:{PORT} "
        f"upstream_default={DEFAULT_UPSTREAM} registry={REGISTRY_PATH}",
        flush=True,
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[metering] shutting down", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
