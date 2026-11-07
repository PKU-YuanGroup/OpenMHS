"""Fixtures for the round-2 safety/protocol regressions.

Everything here is test-local: a controlled bridge, device/server builders and
small RPC helpers.  Production checks (permits, budgets, idempotency, deadline
dispatch, subscription queueing) are never replaced; the fixtures only supply a
deterministic device and controlled blocking points.
"""
from __future__ import annotations

import copy
import sys
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from mhs import canonical
from mhs.bridge.base import Bridge, make_mhs_error
from mhs.server import Capability, Device, MHSServer, Resource, SafetyEnvelope, action_digest

# ---------------------------------------------------------------------------
# controlled bridge
# ---------------------------------------------------------------------------


class LabBridge(Bridge):
    """A tiny simulated device with per-operation gates.

    Gates let a test hold a bridge call open without sleeping and without
    patching production code.  Counters are the effect oracle: they only change
    when the bridge is actually invoked.
    """

    bridge_id = "round2.lab"

    def __init__(self, device_id: str) -> None:
        super().__init__(device_id=device_id)
        self.state: dict[str, Any] = {
            "tick": 0,
            "dose": 0,
            "door": "closed",
            "valve": "main",
            "latched": False,
        }
        self.gates: dict[str, threading.Event] = {}
        self.counts: dict[str, int] = {}
        self.calls: list[tuple[str, dict[str, Any], str | None]] = []
        self.unknown_pending = True
        self._lock = threading.Lock()

    # -- gate helpers ---------------------------------------------------
    def gate(self, name: str) -> threading.Event:
        event = self.gates.get(name)
        if event is None:
            event = threading.Event()
            self.gates[name] = event
        return event

    def release(self, name: str | None = None) -> None:
        if name is None:
            for event in self.gates.values():
                event.set()
            return
        self.gate(name).set()

    def _hold(self, name: str, timeout: float = 5.0) -> None:
        event = self.gates.get(name)
        if event is not None:
            assert event.wait(timeout), f"bridge gate {name!r} was not released"

    def _count(self, name: str, capability_id: str | None = None,
               args: Mapping[str, Any] | None = None, command_id: str | None = None) -> None:
        with self._lock:
            self.counts[name] = self.counts.get(name, 0) + 1
            if capability_id is not None and capability_id != name:
                self.counts[capability_id] = self.counts.get(capability_id, 0) + 1
            self.calls.append((capability_id or name, dict(args or {}), command_id))
        if capability_id is not None:
            self._hold(capability_id)

    # -- bridge surface -------------------------------------------------
    def read(self, resource_id: str, fields=None, ctx=None):
        self.ensure_open()
        self._count("read", "read")
        state = copy.deepcopy(self.state)
        if resource_id == "aux":
            return {"value": state.get("tick", 0)}
        if fields:
            return {name: state.get(name) for name in fields if name in state}
        return state

    def write(self, resource_id, patch, ctx=None):
        self.ensure_open()
        self._count("write", "write")
        for key, value in dict(patch or {}).items():
            self.state[key] = value
        return {resource_id: copy.deepcopy(self.state)}

    def call(self, capability_id: str, args=None, ctx=None):
        self.ensure_open()
        args = dict(args or {})
        command_id = getattr(ctx, "command_id", None)
        self._count("call", capability_id, args, command_id)
        if capability_id == "cap.test.permit_action.v1":
            self.state["valve"] = str(args.get("gate", "main"))
            return {"output": {"gate": self.state["valve"]},
                    "state": {"world": copy.deepcopy(self.state)}}
        if capability_id == "cap.test.budget.v1":
            ticks = int(args.get("ticks", 0))
            self.state["tick"] += ticks
            return {"output": {"tick": self.state["tick"]},
                    "state": {"world": copy.deepcopy(self.state)}}
        if capability_id == "cap.test.budget_gated.v1":
            ticks = int(args.get("ticks", 0))
            self.state["tick"] += ticks
            return {"output": {"tick": self.state["tick"]},
                    "state": {"world": copy.deepcopy(self.state)}}
        if capability_id == "cap.test.budget_multi.v1":
            ticks = int(args.get("ticks", 0))
            dose = int(args.get("dose", 0))
            self.state["tick"] += ticks
            self.state["dose"] += dose
            return {"output": {"tick": self.state["tick"], "dose": self.state["dose"]},
                    "state": {"world": copy.deepcopy(self.state)}}
        if capability_id in ("cap.test.identity.v1", "cap.test.exclusive_identity.v1"):
            self.state["tick"] += 1
            return {"output": {"tick": self.state["tick"]},
                    "state": {"world": copy.deepcopy(self.state)}}
        if capability_id == "cap.test.unknown.v1":
            if self.unknown_pending:
                self.unknown_pending = False
                raise make_mhs_error(
                    "MHS.OUTCOME.UNKNOWN",
                    "the adapter did not observe the effect (test fixture)",
                    {"retryable": False},
                )
            self.state["tick"] += 1
            return {"output": {"tick": self.state["tick"]},
                    "state": {"world": copy.deepcopy(self.state)}}
        raise make_mhs_error("MHS.CAPABILITY.UNKNOWN", f"unknown capability {capability_id!r}")

    def snapshot(self, device_id=None):
        self.ensure_open()
        self._count("snapshot", "snapshot")
        return {"world": copy.deepcopy(self.state)}

    def restore(self, snapshot):
        self.ensure_open()
        self._count("restore", "restore")
        raw = snapshot
        if isinstance(raw, Mapping) and "state" in raw and isinstance(raw["state"], Mapping):
            raw = raw["state"]
        if isinstance(raw, Mapping) and "world" in raw and isinstance(raw["world"], Mapping):
            raw = raw["world"]
        if not isinstance(raw, Mapping):
            raise make_mhs_error("MHS.RESOURCE.STATE_INVALID", "snapshot must be an object")
        for key, value in raw.items():
            if key in self.state:
                self.state[key] = value
        return {"world": copy.deepcopy(self.state)}

    def interlocks(self):
        self._count("interlocks", "interlocks")
        return [
            {"id": "door_closed", "state": "closed" if self.state["door"] == "closed" else "open",
             "description": "Safety door closed"},
        ]

    def safety_status(self):
        self._count("safety_status", "safety_status")
        return {
            "risk_class": "R1",
            "estop": {"engaged": self.state["latched"], "latching": True},
            "interlocks": self.interlocks(),
            "safe_state": {"description": "stopped", "achieved": True},
        }

    def estop(self, reason="", ctx=None):
        self._count("estop", "estop")
        self.state["latched"] = True
        self.state["valve"] = "main"
        return {"estop": "engaged", "latched": True, "reason": reason}

    def reset(self, ctx=None):
        self._count("reset", "reset")
        self.state["latched"] = False
        return {"reset": True, "latched": False}


# ---------------------------------------------------------------------------
# device / server builders
# ---------------------------------------------------------------------------

FIDELITY = {
    "engine": "round2.lab",
    "fidelity_level": "F0",
    "determinism": {"kind": "exact"},
    "timestep_ms": 1,
    "realtime_factor": 0,
    "reset": "full",
    "snapshot_restore": True,
    "gaps": ["synthetic round-2 test device"],
}

DEFAULT_CAPABILITIES = [
    Capability(
        "cap.test.permit_action.v1", "world", title="Permit-gated action",
        input_schema={"type": "object", "required": ["gate"],
                      "properties": {"gate": {"type": "string", "enum": ["main", "divert"]}}},
        requires_permit=True, exclusive=False, constraints={"max_duration_ms": 1000},
    ),
    Capability(
        "cap.test.budget.v1", "world", title="Budgeted ticks",
        input_schema={"type": "object", "required": ["ticks"],
                      "properties": {"ticks": {"type": "integer", "minimum": 0, "maximum": 100}}},
        exclusive=False, constraints={"max_duration_ms": 1000},
    ),
    Capability(
        "cap.test.budget_gated.v1", "world", title="Budgeted and permit-gated ticks",
        input_schema={"type": "object", "required": ["ticks"],
                      "properties": {"ticks": {"type": "integer", "minimum": 0, "maximum": 100}}},
        requires_permit=True, exclusive=False, constraints={"max_duration_ms": 1000},
    ),
    Capability(
        "cap.test.budget_multi.v1", "world", title="Two-field budget",
        input_schema={"type": "object", "required": ["ticks", "dose"],
                      "properties": {"ticks": {"type": "integer", "minimum": 0, "maximum": 100},
                                     "dose": {"type": "integer", "minimum": 0, "maximum": 100}}},
        exclusive=False, constraints={"max_duration_ms": 1000},
    ),
    Capability(
        "cap.test.identity.v1", "world", title="Identity probe",
        input_schema={"type": "object", "properties": {"value": {"type": "integer"}}},
        exclusive=False, constraints={"max_duration_ms": 2000},
    ),
    Capability(
        "cap.test.exclusive_identity.v1", "world", title="Exclusive identity probe",
        input_schema={"type": "object", "properties": {"value": {"type": "integer"}}},
        exclusive=True, constraints={"max_duration_ms": 2000},
    ),
    Capability(
        "cap.test.unknown.v1", "world", title="Unknown-outcome probe",
        input_schema={"type": "object", "properties": {}},
        exclusive=False, constraints={"max_duration_ms": 1000},
    ),
]


def _world_resource() -> Resource:
    return Resource(
        "world", "world.sim",
        state_schema={"type": "object", "properties": {
            "tick": {"type": "integer", "minimum": 0},
            "dose": {"type": "integer", "minimum": 0},
            "door": {"type": "string", "enum": ["open", "closed"]},
            "valve": {"type": "string", "enum": ["main", "divert"]},
            "latched": {"type": "boolean"},
        }},
        state={"tick": 0, "dose": 0, "door": "closed", "valve": "main", "latched": False},
        hash_exclusions=[],
    )


def make_device(
    suffix: str = "primary",
    *,
    capabilities: Iterable[Capability] | None = None,
    safety: SafetyEnvelope | None = None,
    with_aux: bool = False,
) -> tuple[Device, LabBridge]:
    device_id = f"mhs://localhost/round2/{suffix}"
    bridge = LabBridge(device_id)
    resources = [_world_resource()]
    if with_aux:
        resources.append(Resource("aux", "generic", state_schema={"type": "object"},
                                  state={"value": 0}, hash_exclusions=[]))
    device = Device(
        device_id,
        f"Round-2 {suffix} device",
        mode="simulated",
        resources=resources,
        capabilities=[copy.deepcopy(c) for c in (capabilities or DEFAULT_CAPABILITIES)],
        safety=safety or SafetyEnvelope(risk_class="R1"),
        fidelity=copy.deepcopy(FIDELITY),
        bridge=bridge,
        instance_id=canonical.ulid(),
    )
    return device, bridge


def budget_safety() -> SafetyEnvelope:
    """max=10 ticks / rolling_24h, plus a two-field and a gated rule."""
    return SafetyEnvelope(
        risk_class="R1",
        envelope={
            "cap.test.budget.v1": {"ticks": {"min": 0, "max": 10, "per": "rolling_24h", "unit": "1"}},
            "cap.test.budget_gated.v1": {"ticks": {"min": 0, "max": 10, "per": "rolling_24h", "unit": "1"}},
            "cap.test.budget_multi.v1": {
                "ticks": {"min": 0, "max": 10, "per": "rolling_24h", "unit": "1"},
                "dose": {"min": 0, "max": 5, "per": "rolling_24h", "unit": "1"},
            },
        },
        interlocks=[
            {"id": "door_closed", "description": "Safety door closed", "source": "simulated",
             "required_for": ["cap.test.budget.v1"]},
        ],
    )


def make_server(*devices: Device, log_ready: bool = False) -> MHSServer:
    server = MHSServer("mhs://localhost/round2", list(devices), log_ready=log_ready)
    response = rpc(server, "mhs.hello", protocol_versions=["1.0"])
    assert "result" in response, response
    return server


# ---------------------------------------------------------------------------
# RPC helpers
# ---------------------------------------------------------------------------


def as_dict(response: Any) -> dict[str, Any]:
    """Normalise protocol.Response / plain dict to a plain dict."""
    if isinstance(response, Mapping):
        return dict(response)
    converted = response.to_dict() if hasattr(response, "to_dict") else response
    assert isinstance(converted, Mapping), converted
    return dict(converted)


def rpc(server: MHSServer, method: str, **params: Any) -> dict[str, Any]:
    raw = server.handle({"jsonrpc": "2.0", "id": canonical.ulid(), "method": method,
                         "params": params})
    return as_dict(raw)


def result(response: Mapping[str, Any]) -> dict[str, Any]:
    response = as_dict(response)
    assert "result" in response, response
    return dict(response["result"])


def error_code(response: Mapping[str, Any]) -> str | None:
    response = as_dict(response)
    error = response.get("error")
    if isinstance(error, Mapping):
        data = error.get("data") or {}
        return data.get("mhs_code") or error.get("mhs_code")
    res = response.get("result")
    if isinstance(res, Mapping):
        error = res.get("error") or {}
        if isinstance(error, Mapping):
            return error.get("mhs_code")
    return None


def status_of(response: Mapping[str, Any]) -> str | None:
    res = as_dict(response).get("result")
    return res.get("status") if isinstance(res, Mapping) else None


def open_session(server: MHSServer, device_ids: list[str], *, capabilities: list[str] | None = None,
                 principal_id: str = "agent:round2", mode: str = "simulated",
                 ttl_s: int = 300) -> str:
    response = rpc(
        server, "mhs.session.open",
        principal={"id": principal_id, "kind": "agent"},
        device_ids=list(device_ids), capabilities=capabilities, mode=mode, ttl_s=ttl_s,
    )
    return result(response)["session_id"]


def issue_permit(server: MHSServer, session_id: str, device_id: str, capability_id: str,
                 payload: Mapping[str, Any], *, resource: str | None = None,
                 ttl_s: int = 60) -> dict[str, Any]:
    digest = action_digest(capability_id, resource or "world", dict(payload))
    return rpc(
        server, "mhs.safety.permit",
        session_id=session_id, device_id=device_id, capability_id=capability_id,
        resource=resource, input=dict(payload), input_digest=digest, ttl_s=ttl_s,
    )


def command(server: MHSServer, session_id: str, device_id: str, capability_id: str,
            payload: Mapping[str, Any] | None = None, *, command_id: str | None = None,
            deadline_ms: int = 1000, permit_id: str | None = None,
            resource: str | None = None, expected_revision: int | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {
        "session_id": session_id, "device_id": device_id, "capability_id": capability_id,
        "input": dict(payload or {}), "command_id": command_id or canonical.ulid(),
        "deadline_ms": deadline_ms,
    }
    if permit_id is not None:
        params["permit_id"] = permit_id
    if resource is not None:
        params["resource"] = resource
    if expected_revision is not None:
        params["expected_revision"] = expected_revision
    return rpc(server, "mhs.command", **params)


def command_in_thread(server: MHSServer, **kwargs: Any) -> tuple[threading.Thread, dict[str, Any]]:
    holder: dict[str, Any] = {}

    def run() -> None:
        holder["response"] = command(server, **kwargs)

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, holder


# ---------------------------------------------------------------------------
# deterministic interleaving helpers
# ---------------------------------------------------------------------------


@contextmanager
def thread_trace(predicate: Callable[[Any, str], bool], barrier: threading.Barrier,
                 timeout: float = 0.75):
    """Pause this thread once when *predicate(frame, event)* matches.

    The barrier is released after the configured timeout so a fixed
    implementation (where the other request is legitimately blocked or
    rejected before reaching the hook) never deadlocks the test.
    """
    state = {"hit": False}

    def trace(frame, event, arg):
        if state["hit"]:
            return trace
        try:
            matched = predicate(frame, event)
        except Exception:  # noqa: BLE001 - tracing must never break the test
            matched = False
        if matched:
            state["hit"] = True
            try:
                barrier.wait(timeout=timeout)
            except threading.BrokenBarrierError:
                pass
            sys.settrace(None)
            return None
        return trace

    previous = sys.gettrace()
    sys.settrace(trace)
    try:
        yield
    finally:
        sys.settrace(previous)


def at_function(name: str) -> Callable[[Any, str], bool]:
    return lambda frame, event: event == "call" and frame.f_code.co_name == name


def after_local(name: str, local: str, absent: str | None = None) -> Callable[[Any, str], bool]:
    def predicate(frame, event):
        if event != "line" or frame.f_code.co_name != name:
            return False
        if local not in frame.f_locals:
            return False
        return absent is None or absent not in frame.f_locals

    return predicate


def wait_until(predicate: Callable[[], bool], timeout: float = 3.0, interval: float = 0.005) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def wait_no_threads(prefix: str, timeout: float = 3.0) -> bool:
    return wait_until(
        lambda: not any(t.name.startswith(prefix) and t.is_alive() for t in threading.enumerate()),
        timeout=timeout,
    )


# ---------------------------------------------------------------------------
# cumulative-ledger inspection / seeding
# ---------------------------------------------------------------------------


def usage_key(device_id: str, capability_id: str, field: str, window: str = "rolling_24h"):
    return (f"{device_id}|{capability_id}|{field}", window)


def _entry_amount(item: Any) -> float:
    if isinstance(item, Mapping):
        return float(item.get("amount", 0))
    return float(item[1])


def usage_total(server: MHSServer, device_id: str, capability_id: str, field: str,
                window: str = "rolling_24h") -> float:
    key = usage_key(device_id, capability_id, field, window)
    return sum(_entry_amount(item) for item in server._cumulative_usage.get(key, []))


def add_usage(server: MHSServer, device_id: str, capability_id: str, field: str,
              amount: float, *, age_s: float = 0.0, window: str = "rolling_24h") -> None:
    key = usage_key(device_id, capability_id, field, window)
    lock = getattr(server, "_cumulative_lock", None)
    if lock is not None:
        lock.acquire()
    try:
        usage = server._cumulative_usage.setdefault(key, [])
        timestamp = time.time() - float(age_s)
        if usage and isinstance(usage[0], Mapping):
            usage.append({"t": timestamp, "amount": float(amount), "id": canonical.ulid()})
        elif getattr(server, "_cumulative_lock", None) is not None:
            usage.append({"t": timestamp, "amount": float(amount), "id": canonical.ulid()})
        else:
            usage.append((timestamp, float(amount)))
    finally:
        if lock is not None:
            lock.release()
