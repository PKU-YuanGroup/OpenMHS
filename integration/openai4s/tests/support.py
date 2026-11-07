"""Shared helpers for the tests that need a real MHS reference endpoint."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

_HERE = Path(__file__).resolve()
_REPO_ROOT = _HERE.parents[3]
_SDK_SRC = _REPO_ROOT / "MHS" / "sdk" / "src"


def child_env() -> dict[str, str]:
    env = os.environ.copy()
    parts = [str(_SDK_SRC)]
    if env.get("PYTHONPATH"):
        parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(parts)
    env.setdefault("PYTHONUNBUFFERED", "1")
    return env


def launch_http_reference(name: str, *, port: int = 0, timeout: float = 20.0) -> tuple[subprocess.Popen, str, dict]:
    """Launch ``python -m mhs.reference <name> --port N`` and wait for ready."""
    proc = subprocess.Popen(
        [sys.executable, "-m", "mhs.reference", name, "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=child_env(),
    )
    box: "queue.Queue[str]" = queue.Queue()

    def reader() -> None:
        try:
            box.put(proc.stdout.readline() if proc.stdout is not None else "")
        except Exception:  # noqa: BLE001
            box.put("")

    threading.Thread(target=reader, daemon=True).start()
    try:
        line = box.get(timeout=timeout)
    except queue.Empty:
        stop_process(proc)
        raise AssertionError(f"{name} endpoint was not ready within {timeout:.0f}s")
    if not line:
        tail = ""
        try:
            if proc.stderr is not None:
                tail = proc.stderr.read()[-800:]
        except Exception:  # noqa: BLE001
            pass
        stop_process(proc)
        raise AssertionError(f"{name} endpoint exited before ready: {tail}")
    payload: dict[str, Any] = json.loads(line)
    if not payload.get("mhs_ready") or not payload.get("url"):
        stop_process(proc)
        raise AssertionError(f"{name} ready event incomplete: {payload}")
    return proc, str(payload["url"]), payload


def stop_process(proc: subprocess.Popen | None) -> None:
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
    except Exception:  # noqa: BLE001
        pass
    for stream in (proc.stdout, proc.stderr):
        try:
            if stream is not None:
                stream.close()
        except Exception:  # noqa: BLE001
            pass


def sdk_projection_available() -> bool:
    try:
        import mhs.client  # noqa: F401
        import mhs.mcp  # noqa: F401
        import mhs.server  # noqa: F401

        from openai4s.mcp_client import MCPManager  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


__all__ = [
    "child_env",
    "launch_http_reference",
    "sdk_projection_available",
    "stop_process",
]
