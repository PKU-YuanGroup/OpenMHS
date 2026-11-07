"""OpenMHS reference SDK (distribution ``openmhs``, import name ``mhs``).

OpenMHS is an independent open-source project, not affiliated with or
endorsed by Anthropic, and not a reimplementation or compatible dialect of
Anthropic's MHS research preview.  Project identifiers live in
:mod:`mhs._ids`.

The package is pure standard library.  Its four surfaces are deliberately
separate:

* :mod:`mhs.client` — talk to any MHS endpoint (stdio or HTTP/SSE);
* :mod:`mhs.server` — implement an MHS endpoint (sessions, safety, receipts,
  evidence) and plug a bridge in;
* :mod:`mhs.bridge` — translate an existing SDK/simulator/engine into
  capabilities;
* :mod:`mhs.conformance` — prove what an endpoint actually supports.

Quick start::

    from mhs import connect

    with connect(["python3", "-m", "mhs.reference", "conveyor", "--stdio"]) as lab:
        device = lab.devices()[0]["device_id"]
        lab.open_session([device], mode="simulated")
        receipt = lab.invoke("cap.world.step.v1", {"ticks": 10})
        print(receipt["status"], receipt["state_hash_after"])
"""

from __future__ import annotations

from ._ids import SDK_VERSION as __version__
from .client import (
    HttpTransport,
    MHSClient,
    SSETransport,
    StdioTransport,
    TransportError,
    connect,
)
from .errors import MHSError
from .protocol import MCP_PROJECTION_VERSION, MHS_PROTOCOL_VERSION, MHS_VERSION
from .server import (
    Capability,
    Device,
    MHSServer,
    Resource,
    SafetyEnvelope,
    SessionManager,
    SubscriptionHub,
)

__all__ = [
    "Capability",
    "Device",
    "HttpTransport",
    "MCP_PROJECTION_VERSION",
    "MHSError",
    "MHSClient",
    "MHS_PROTOCOL_VERSION",
    "MHSServer",
    "MHS_VERSION",
    "Resource",
    "SafetyEnvelope",
    "SessionManager",
    "SSETransport",
    "StdioTransport",
    "SubscriptionHub",
    "TransportError",
    "__version__",
    "connect",
    "serve",
]


def serve(server: MHSServer, *, host: str = "127.0.0.1", port: int = 7400,
          stdio: bool = False) -> None:
    """Serve one :class:`MHSServer` over stdio (T1) or loopback HTTP (T2)."""
    if stdio:
        server.run_stdio()
    else:
        server.run_http(host, port)
