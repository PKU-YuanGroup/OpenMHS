"""Shared fixtures for the endpoint safety tests (WP-04).

Two kinds of subject are used:

* the reference conveyor with its test profile (what the reviewer repros under
  ``mhs-review-scratch/sdk-core`` drove), and
* a small stub bridge that records every native call, so a test can prove that
  the runtime itself (not a well-behaved reference bridge) enforces the rule.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Iterable, Mapping

from mhs import canonical
from mhs.bridge.base import Bridge
from mhs.reference import build_endpoint, build_server
from mhs.server import Capability, Device, MHSServer, Resource, SafetyEnvelope

DEVICE_ID = "mhs://localhost/safety/stub"
STOP = "cap.motion.stop.v1"
MOVE = "cap.motion.move.v1"
LONG = "x-cap.test.long.v1"
READ = "cap.world.state.v1"

FIDELITY = {
    "engine": "tests.safety.stub",
    "fidelity_level": "F0",
    "determinism": {"kind": "exact"},
    "timestep_ms": 1,
    "realtime_factor": 0,
    "reset": "full",
    "snapshot_restore": True,
    "gaps": ["synthetic safety test device"],
}


class Rpc:
    """In-process JSON-RPC caller with thread-safe request ids."""

    def __init__(self, server: MHSServer) -> None:
        self.server = server
        self._lock = threading.Lock()
        self._n = 0

    def raw(self, method: str, **params: Any) -> dict[str, Any]:
        with self._lock:
            self._n += 1
            request_id = self._n
        response = self.server.handle(
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
        )
        return response.to_dict() if hasattr(response, "to_dict") else dict(response)

    def __call__(self, method: str, **params: Any) -> dict[str, Any]:
        response = self.raw(method, **params)
        if "error" in response:
            raise AssertionError(f"{method} returned a protocol error: {response['error']}")
        return response["result"]


def error_code(result: Mapping[str, Any]) -> str | None:
    """mhs_code of a receipt or of a JSON-RPC error response."""
    error = result.get("error")
    if not isinstance(error, Mapping):
        return None
    if "mhs_code" in error:
        return error.get("mhs_code")
    return (error.get("data") or {}).get("mhs_code")


def wait_until(predicate: Callable[[], bool], timeout: float = 3.0, step: float = 0.002) -> bool:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(step)
    return bool(predicate())


def conveyor(**_: Any) -> tuple[MHSServer, Rpc, Device, str]:
    """The reference conveyor (test profile), initialised, with a simulated session."""
    spec = build_endpoint("conveyor", endpoint_id="mhs://localhost/x", test_profile=True)
    server = build_server(spec, log_ready=False)
    rpc = Rpc(server)
    rpc("mhs.hello", protocol_versions=["1.0"])
    device = next(iter(server.devices.values()))
    session = rpc("mhs.session.open", mode="simulated")["session_id"]
    return server, rpc, device, session


class StubBridge(Bridge):
    """Records native calls; every safety hook can be replaced per test."""

    bridge_id = "tests.safety.stub"

    def __init__(self, device_id: str = DEVICE_ID) -> None:
        super().__init__(device_id=device_id)
        self.state: dict[str, Any] = {"pos": 0, "moving": False, "stopped": True, "door": "closed"}
        self.calls: list[str] = []
        self.interlock_states: dict[str, str] = {}
        self.interlocks_error: BaseException | None = None
        self.fail_actions: set[str] = set()
        self._calls_lock = threading.Lock()

    def _record(self, name: str) -> None:
        with self._calls_lock:
            self.calls.append(name)

    def count(self, name: str) -> int:
        with self._calls_lock:
            return sum(1 for item in self.calls if item == name)

    def read(self, resource_id: str, fields=None, ctx=None):  # noqa: ANN001
        return dict(self.state)

    def call(self, capability_id: str, args=None, ctx=None):  # noqa: ANN001
        self._record(capability_id)
        args = dict(args or {})
        if capability_id in self.fail_actions:
            raise RuntimeError(f"{capability_id} failed in the test fixture")
        if capability_id == STOP:
            self.state["moving"] = False
            self.state["stopped"] = True
            return {"stopped": True}
        if capability_id in ("cap.thermal.off.v1", "x-cap.test.pump_off.v1"):
            return {"off": True}
        if capability_id == MOVE:
            self.state["pos"] = int(args.get("pos", 0))
            return {"pos": self.state["pos"]}
        if capability_id == LONG:
            duration = int(args.get("ms", 500))
            self.state["moving"] = True
            slept = 0
            while slept < duration:
                if ctx is not None and ctx.cancel_event is not None and ctx.cancel_event.is_set():
                    self.state["moving"] = False
                    return {"status": "cancelled", "slept_ms": slept}
                time.sleep(0.005)
                slept += 5
            self.state["moving"] = False
            self.state["pos"] += 1
            return {"slept_ms": slept}
        if capability_id == READ:
            return dict(self.state)
        return {"ok": True}

    def interlocks(self):
        self._record("interlocks")
        if self.interlocks_error is not None:
            raise self.interlocks_error
        return [{"id": key, "state": value} for key, value in self.interlock_states.items()]

    def reset(self, ctx=None):  # noqa: ANN001
        self._record("reset")
        return {"reset": True}


class NativeStopBridge(StubBridge):
    """A stub with a native e-stop."""

    def estop(self, reason: str = "", ctx: Any = None) -> Any:
        self._record("estop")
        self.state["moving"] = False
        return {"estop": "engaged"}


def stub_capabilities(*, stop_exclusive: bool = False, extra: Iterable[Capability] = ()) -> list[Capability]:
    caps = [
        Capability(MOVE, "axis", input_schema={"type": "object", "properties": {"pos": {"type": "integer"}}},
                   exclusive=True),
        Capability(STOP, "axis", input_schema={"type": "object", "properties": {}}, exclusive=stop_exclusive),
        Capability(LONG, "axis",
                   input_schema={"type": "object", "properties": {"ms": {"type": "integer"}}},
                   exclusive=True, constraints={"cancellable": True, "max_duration_ms": 5000}),
        Capability(READ, "axis", input_schema={"type": "object", "properties": {}}, verb="read"),
    ]
    caps.extend(extra)
    return caps


def stub_server(
    bridge: StubBridge | None = None,
    *,
    mode: str = "simulated",
    safety: SafetyEnvelope | None = None,
    capabilities: list[Capability] | None = None,
    **server_kwargs: Any,
) -> tuple[MHSServer, Rpc, Device, StubBridge]:
    bridge = bridge if bridge is not None else StubBridge()
    device = Device(
        DEVICE_ID,
        "Safety stub",
        mode=mode,
        resources=[Resource("axis", "motion.axis", state_schema={"type": "object"})],
        capabilities=capabilities if capabilities is not None else stub_capabilities(),
        safety=safety or SafetyEnvelope(
            risk_class="R1",
            estop={"kind": "software", "latching": True, "latency_ms": 50},
            safe_state={"description": "axis stopped", "achieved_by": [STOP]},
        ),
        fidelity=dict(FIDELITY) if mode in ("simulated", "hybrid") else None,
        bridge=bridge,
    )
    server = MHSServer("mhs://localhost/safety", [device], log_ready=False, **server_kwargs)
    rpc = Rpc(server)
    rpc("mhs.hello", protocol_versions=["1.0"])
    return server, rpc, device, bridge


def release_retry(server: MHSServer, rpc: Rpc, device: Device, session: str) -> None:
    """Test cleanup: reset a latched device so its background e-stop retry thread ends."""
    for _ in range(50):
        if not server._latched[device.device_id]:
            return
        rpc.raw("mhs.safety.reset", session_id=session, deadline_ms=1000)
        time.sleep(0.02)


def open_session(rpc: Rpc, device: Device, **params: Any) -> str:
    params.setdefault("mode", device.mode)
    return rpc("mhs.session.open", device_ids=[device.device_id], **params)["session_id"]


def ulid() -> str:
    return canonical.ulid()


def in_thread(fn: Callable[[], Any]) -> tuple[threading.Thread, dict[str, Any]]:
    holder: dict[str, Any] = {}

    def run() -> None:
        started = time.monotonic()
        try:
            holder["result"] = fn()
        except BaseException as exc:  # noqa: BLE001 - surfaced by the test
            holder["error"] = exc
        holder["elapsed"] = time.monotonic() - started

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, holder
