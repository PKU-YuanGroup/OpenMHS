"""Test fixture: an in-process endpoint whose one job is long-running (plan 3.7).

``x-cap.test.job.v1`` declares ``constraints.long_running``: when a call
outlives its ``deadline_ms`` the endpoint answers ``running`` with an
``operation_id`` and keeps executing; the final receipt lands in the evidence
chain when the job ends.  Served over loopback HTTP by the real
``mhs.server.MHSServer``.
"""

from __future__ import annotations

import threading
import time
import uuid
import warnings
from dataclasses import dataclass
from typing import Any

from mhs import signals
from mhs.bridge.base import Bridge
from mhs.server import Capability, Device, MHSServer, Resource, SafetyEnvelope

JOB = "x-cap.test.job.v1"


class JobBridge(Bridge):
    """``JOB`` sleeps ``ms`` milliseconds (cooperatively cancellable), then counts."""

    def __init__(self, device_id: str) -> None:
        super().__init__(device_id=device_id)
        self.done = 0
        self.lock = threading.Lock()

    def read(self, resource_id: str, fields: Any = None, ctx: Any = None) -> dict[str, Any]:
        with self.lock:
            return {"done": self.done}

    def call(self, capability_id: str, args: Any = None, ctx: Any = None) -> dict[str, Any]:
        end = time.monotonic() + int((args or {}).get("ms", 100)) / 1000.0
        while time.monotonic() < end:
            if ctx is not None and ctx.cancelled():
                raise signals.Cancelled("job cancelled")
            time.sleep(0.01)
        with self.lock:
            self.done += 1
            return {"done": self.done}


@dataclass
class JobEndpoint:
    server: Any
    handle: Any
    url: str
    device_id: str
    bridge: JobBridge

    def close(self) -> None:
        try:
            self.handle.shutdown()
        except Exception:  # noqa: BLE001 - teardown
            pass


def start_job_endpoint(*, auth_tokens: dict[str, dict[str, Any]] | None = None) -> JobEndpoint:
    """Serve the job device; ``auth_tokens`` makes every HTTP request need a bearer token."""
    endpoint_id = f"mhs://job-{uuid.uuid4().hex[:8]}"
    device_id = f"{endpoint_id}/job"
    bridge = JobBridge(device_id)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        device = Device(
            device_id,
            "long-running job",
            mode="simulated",
            resources=[Resource("job", "lab.job")],
            capabilities=[
                Capability(
                    JOB,
                    "job",
                    input_schema={
                        "type": "object",
                        "properties": {"ms": {"type": "integer", "minimum": 0, "maximum": 10000}},
                        "additionalProperties": False,
                    },
                    constraints={"long_running": True, "max_duration_ms": 30000, "cancellable": True},
                )
            ],
            safety=SafetyEnvelope(risk_class="R0"),
            bridge=bridge,
        )
        server = MHSServer(endpoint_id=endpoint_id, devices=[device], log_ready=False,
                           auth_tokens=auth_tokens)
    handle = server.start_http("127.0.0.1", 0)
    return JobEndpoint(server=server, handle=handle, url=str(handle.url), device_id=device_id,
                       bridge=bridge)


__all__ = ["JOB", "JobBridge", "JobEndpoint", "start_job_endpoint"]
