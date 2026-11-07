"""Test fixtures: in-process real MHS reference endpoints.

``start_endpoint`` builds a reference endpoint with ``mhs.reference`` and serves
it with the real ``mhs.server.MHSServer`` over loopback HTTP.  ``mode`` can be
flipped to ``"hardware"`` to exercise the HOST-001 policy matrix without any
physical hardware.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from mhs.reference import build_endpoint, build_server


@dataclass
class EndpointHandle:
    name: str
    spec: Any
    server: Any
    url: str
    endpoint_id: str
    devices: list[dict]

    def close(self) -> None:
        handle = getattr(self.server, "_http_handle", None)
        if handle is not None:
            try:
                handle.shutdown()
            except Exception:  # noqa: BLE001
                pass
        try:
            self.spec.close()
        except Exception:  # noqa: BLE001
            pass

    def __enter__(self) -> "EndpointHandle":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def start_endpoint(
    name: str = "conveyor",
    *,
    mode: str = "simulated",
    endpoint_id: str | None = None,
) -> EndpointHandle:
    token = uuid.uuid4().hex[:8]
    endpoint = endpoint_id or f"mhs://test-{token}"
    spec = build_endpoint(name, endpoint_id=endpoint, test_profile=(name == "conveyor"))
    for device in spec.devices:
        device["mode"] = mode
    server = build_server(spec, log_ready=False)
    handle = server.start_http("127.0.0.1", 0)
    url = str(getattr(handle, "url", ""))
    if not url:
        handle.shutdown()
        raise RuntimeError("MHS endpoint did not expose a URL")
    return EndpointHandle(
        name=name,
        spec=spec,
        server=server,
        url=url,
        endpoint_id=endpoint,
        devices=[dict(item) for item in spec.devices],
    )


__all__ = ["EndpointHandle", "start_endpoint"]
