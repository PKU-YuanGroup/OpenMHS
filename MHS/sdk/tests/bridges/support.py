"""Fakes and an in-process MHSServer harness for the bridge tests (stdlib only).

Every fake here stands in for an upstream API shape the reviewers hit:

* :class:`AsyncBath` -- an asyncio instrument client (julabo, PyLabRobot);
* :class:`Axis` / :class:`StatusLike` -- an ophyd-style ``set()`` that returns
  a Status object completing later;
* :class:`Thermometer` -- a getter returning a bare float;
* :class:`FakeCartPole` -- a Gymnasium environment with ``Discrete(2)`` actions
  and a ``Box(4)`` observation, wrapped like ``gym.make`` does;
* :class:`FakeMjModel` / :class:`FakeMjData` / :data:`fake_mujoco` -- the
  parts of the MuJoCo API the bridge uses, with ``actuator_ctrlrange``.

:class:`Harness` serves one device through :class:`mhs.server.MHSServer` and
speaks JSON-RPC to it in-process, so the tests exercise the real server path.
"""

from __future__ import annotations

import asyncio
import threading
import time
import types
from typing import Any, Mapping

from mhs import canonical, catalog
from mhs.server import Capability, Device, MHSServer, Resource, SafetyEnvelope

#: Fidelity contract of a device whose transport is replaced by a fake.
FAKE_FIDELITY: dict[str, Any] = {
    "engine": "fake",
    "fidelity_level": "F0",
    "determinism": {"kind": "seeded"},
    "timestep_ms": 0,
    "realtime_factor": 0,
    "reset": "full",
    "snapshot_restore": False,
    "gaps": ["transport replaced by fake backend"],
}

ENDPOINT = "mhs://localhost:7799"


# ---------------------------------------------------------------------------
# catalogue helpers
# ---------------------------------------------------------------------------


def class_schema(capability_id: str) -> dict[str, Any]:
    return catalog.get(capability_id)


def class_capability(capability_id: str, resource: str, **overrides: Any) -> Capability:
    """A Capability carrying the catalogue class contract."""

    entry = class_schema(capability_id)
    kwargs: dict[str, Any] = {
        "input_schema": entry["input_schema"],
        "output_schema": entry["output_schema"],
        "verb": entry.get("verb", "invoke"),
        "constraints": dict(entry.get("constraints") or {}),
    }
    kwargs.update(overrides)
    return Capability(capability_id, resource, **kwargs)


def open_capability(capability_id: str, resource: str, **overrides: Any) -> Capability:
    """A capability with a permissive contract (the bridge is under test)."""

    kwargs: dict[str, Any] = {
        "input_schema": {"type": "object"},
        "output_schema": {"type": "object"},
        "constraints": {"cancellable": True},
        "exclusive": True,
    }
    kwargs.update(overrides)
    return Capability(capability_id, resource, **kwargs)


# ---------------------------------------------------------------------------
# in-process server harness
# ---------------------------------------------------------------------------


class RpcError(AssertionError):
    def __init__(self, error: Mapping[str, Any]):
        self.error = dict(error)
        data = self.error.get("data") or {}
        self.mhs_code = data.get("mhs_code") if isinstance(data, Mapping) else None
        super().__init__(f"{self.mhs_code or self.error.get('code')}: {self.error.get('message')}")


class Harness:
    """Serve one device in-process and drive it with JSON-RPC requests."""

    def __init__(self, device: Device, *, endpoint_id: str = ENDPOINT):
        self.device = device
        self.device_id = device.device_id
        self.server = MHSServer(endpoint_id=endpoint_id, devices=[device])
        self._ids = 0
        self._ids_lock = threading.Lock()
        self.rpc("mhs.hello", {"protocol_versions": ["1.0"], "client": {"name": "bridge-tests", "version": "0"}})
        session = self.rpc(
            "mhs.session.open",
            {"device_ids": [self.device_id], "mode": device.mode, "ttl_s": 120,
             "principal": {"id": "bridge-tests", "kind": "agent"}},
        )
        self.session_id = session["session_id"]

    def rpc(self, method: str, params: Mapping[str, Any]) -> Any:
        with self._ids_lock:
            self._ids += 1
            request_id = self._ids
        response = self.server.handle(
            {"jsonrpc": "2.0", "id": request_id, "method": method, "params": dict(params)}
        )
        if hasattr(response, "to_dict"):
            response = response.to_dict()
        if "error" in response:
            raise RpcError(response["error"])
        return response["result"]

    def command(self, capability_id: str, payload: Mapping[str, Any] | None = None, *,
                deadline_ms: int = 5000, command_id: str | None = None) -> dict[str, Any]:
        return self.rpc(
            "mhs.command",
            {
                "session_id": self.session_id,
                "device_id": self.device_id,
                "capability_id": capability_id,
                "input": dict(payload or {}),
                "command_id": command_id or canonical.ulid(),
                "deadline_ms": deadline_ms,
            },
        )

    def read(self, resource_id: str) -> dict[str, Any]:
        return self.rpc(
            "mhs.resource.read",
            {"session_id": self.session_id, "device_id": self.device_id, "resource_id": resource_id,
             "deadline_ms": 5000},
        )

    def operations(self) -> list[dict[str, Any]]:
        return self.rpc(
            "mhs.operations.list", {"session_id": self.session_id, "device_id": self.device_id}
        )["operations"]

    def cancel(self, operation_id: str) -> dict[str, Any]:
        return self.rpc(
            "mhs.operations.cancel",
            {"session_id": self.session_id, "operation_id": operation_id, "deadline_ms": 2000},
        )

    def operation(self, operation_id: str) -> dict[str, Any]:
        return self.rpc(
            "mhs.operations.get",
            {"session_id": self.session_id, "operation_id": operation_id, "deadline_ms": 5000},
        )

    def estop(self, reason: str = "test") -> dict[str, Any]:
        return self.rpc(
            "mhs.safety.estop",
            {"session_id": self.session_id, "device_id": self.device_id, "reason": reason,
             "deadline_ms": 5000},
        )

    def reset(self) -> dict[str, Any]:
        return self.rpc(
            "mhs.safety.reset",
            {"session_id": self.session_id, "device_id": self.device_id, "deadline_ms": 5000},
        )

    def safety_status(self) -> dict[str, Any]:
        return self.rpc(
            "mhs.safety.status",
            {"session_id": self.session_id, "device_id": self.device_id, "deadline_ms": 5000},
        )

    def wait_running(self, timeout_s: float = 2.0) -> dict[str, Any]:
        """Return the first operation that is not terminal yet."""

        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            for item in self.operations():
                if item.get("state") in ("accepted", "running"):
                    return item
            time.sleep(0.005)
        raise AssertionError("no running operation appeared")


def simulated_device(device_id: str, *, resources: list[Resource], capabilities: list[Capability],
                     bridge: Any, risk_class: str = "R1", **kwargs: Any) -> Device:
    return Device(
        device_id=device_id,
        mode="simulated",
        resources=resources,
        capabilities=capabilities,
        safety=SafetyEnvelope(risk_class=risk_class),
        fidelity=dict(FAKE_FIDELITY),
        bridge=bridge,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# python-object fakes
# ---------------------------------------------------------------------------


class Thermometer:
    """A getter that returns a bare float (DRV-06 scalar return)."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def read_temperature(self) -> float:
        self.calls.append("read_temperature")
        return 22.0


class Heater:
    """A legacy-shaped heater used for the reject-not-clamp checks (ADPT-024)."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.setpoint = 20.0
        self.heating = True

    def set_point(self, celsius: float) -> dict[str, Any]:
        self.calls.append(("set_point", celsius))
        self.setpoint = celsius
        return {"setpoint": celsius}

    def slow(self, seconds: float) -> dict[str, Any]:
        self.calls.append(("slow", seconds))
        time.sleep(float(seconds))
        return {"slept": True}

    def state(self) -> dict[str, Any]:
        return {"setpoint": self.setpoint, "heating": self.heating}

    # safety natives
    def emergency_stop(self) -> None:
        self.calls.append(("emergency_stop", None))
        self.heating = False

    def clear_fault(self) -> None:
        self.calls.append(("clear_fault", None))

    lid_closed = True


class AsyncBath:
    """An asyncio instrument client (julabo-like; LAB-02, FIT-09)."""

    def __init__(self) -> None:
        self.setpoint = 20.0
        self.setup_done = False
        self.closed = False
        self.ramp_done = False
        self.ramp_cancelled = threading.Event()
        self.ramp_started = threading.Event()
        self.loops: set[int] = set()
        self.calls: list[str] = []
        self.stopped = False

    def _loop(self) -> None:
        self.loops.add(id(asyncio.get_running_loop()))

    async def setup(self) -> None:
        self._loop()
        await asyncio.sleep(0)
        self.setup_done = True

    async def bath_temperature(self) -> float:
        self._loop()
        self.calls.append("bath_temperature")
        await asyncio.sleep(0)
        return 22.0

    async def set_point_1(self, value: float) -> float:
        self._loop()
        self.calls.append("set_point_1")
        self.setpoint = float(value)
        return self.setpoint

    async def ramp(self, target: float, seconds: float) -> dict[str, Any]:
        self._loop()
        self.calls.append("ramp")
        self.ramp_started.set()
        try:
            await asyncio.sleep(float(seconds))
        except asyncio.CancelledError:
            self.ramp_cancelled.set()
            raise
        self.ramp_done = True
        self.setpoint = float(target)
        return {"setpoint": self.setpoint}

    async def stop(self) -> None:
        self._loop()
        self.calls.append("stop")
        self.stopped = True

    async def close(self) -> None:
        self.closed = True

    def model(self) -> str:
        """A synchronous native (not awaitable)."""
        return "FP50"


class StatusLike:
    """An ophyd-style Status: ``done``/``success`` plus ``wait(timeout)``."""

    def __init__(self, on_done: Any = None, *, delay: float = 0.05, success: bool = True):
        self.done = False
        self.success = False
        self._event = threading.Event()
        self._on_done = on_done
        self._success = success
        timer = threading.Timer(delay, self._finish)
        timer.daemon = True
        timer.start()

    def _finish(self) -> None:
        if self._success and self._on_done is not None:
            self._on_done()
        self.success = self._success
        self.done = True
        self._event.set()

    def wait(self, timeout: float | None = None) -> None:
        if not self._event.wait(timeout):
            raise TimeoutError("status did not finish in time")
        if not self.success:
            raise RuntimeError("motion failed")


class Axis:
    """ophyd-like positioner whose ``set`` returns a Status (FIT-09)."""

    def __init__(self, *, delay: float = 0.05) -> None:
        self.position = 0.0
        self.delay = delay
        self.statuses: list[StatusLike] = []
        self.limit = 100.0

    def set(self, value: float) -> StatusLike:
        def apply() -> None:
            self.position = float(value)

        status = StatusLike(apply, delay=self.delay, success=abs(float(value)) <= self.limit)
        self.statuses.append(status)
        return status


class LazyStatus:
    """A Status that only completes inside ``wait()`` (fit-lab-instruments/t_pyobj.py)."""

    def __init__(self, on_done: Any) -> None:
        self.done = False
        self._on_done = on_done

    def wait(self, timeout: float | None = None) -> None:
        self._on_done()
        self.done = True


class LazyAxis:
    def __init__(self) -> None:
        self.pos = 0.0

    def set(self, value: float) -> LazyStatus:
        def apply() -> None:
            self.pos = float(value)

        return LazyStatus(apply)


class Pump:
    """A pymeasure-style instrument with a property setter (invoke get/set)."""

    def __init__(self) -> None:
        self._rate = 1.0
        self.writes: list[float] = []

    @property
    def rate(self) -> float:
        return self._rate

    @rate.setter
    def rate(self, value: float) -> None:
        self.writes.append(float(value))
        self._rate = float(value)


# ---------------------------------------------------------------------------
# gymnasium fakes
# ---------------------------------------------------------------------------


class Discrete:
    """Duck-typed ``gymnasium.spaces.Discrete``."""

    def __init__(self, n: int, start: int = 0):
        self.n = int(n)
        self.start = int(start)
        self.shape = ()
        self.dtype = "int64"

    def contains(self, value: Any) -> bool:
        return isinstance(value, int) and self.start <= value < self.start + self.n


class Box:
    """Duck-typed ``gymnasium.spaces.Box`` (1-D)."""

    def __init__(self, low: list[float], high: list[float]):
        self.low = list(low)
        self.high = list(high)
        self.shape = (len(self.low),)
        self.dtype = "float32"


class Dict:
    """Duck-typed ``gymnasium.spaces.Dict``."""

    def __init__(self, spaces: Mapping[str, Any]):
        self.spaces = dict(spaces)


class FakeCartPole:
    """CartPole-like: Discrete(2) actions, Box(4) observation (SIM-03 repro)."""

    def __init__(self, *, terminate_after: int = 50) -> None:
        self.action_space = Discrete(2)
        self.observation_space = Box([-4.8, -1e9, -0.42, -1e9], [4.8, 1e9, 0.42, 1e9])
        self.state = [0.0, 0.0, 0.0, 0.0]
        self.steps = 0
        self.native_steps = 0
        self.terminate_after = terminate_after
        self.seeds: list[Any] = []
        self.closed = False

    def reset(self, seed: int | None = None, options: Any = None):
        self.seeds.append(seed)
        self.steps = 0
        self.state = [0.01 * (seed or 0), 0.0, 0.0, 0.0]
        return list(self.state), {}

    def step(self, action: Any):
        if action not in (0, 1):
            raise ValueError(f"invalid action {action!r}")
        self.steps += 1
        self.native_steps += 1
        self.state[0] += 0.1 if action == 1 else -0.1
        terminated = self.steps >= self.terminate_after
        return list(self.state), 1.0, terminated, False, {}

    # exact state access, as e.g. ManiSkill's get_state_dict/set_state_dict
    def get_state(self) -> dict[str, Any]:
        return {"state": list(self.state), "steps": self.steps}

    def set_state(self, state: Mapping[str, Any]) -> None:
        self.state = list(state["state"])
        self.steps = int(state["steps"])

    def close(self) -> None:
        self.closed = True


class FakeWrapper:
    """Like gymnasium 1.x ``Wrapper``: no ``__getattr__`` forwarding."""

    def __init__(self, env: Any) -> None:
        self.env = env
        self.action_space = env.action_space
        self.observation_space = env.observation_space

    @property
    def unwrapped(self) -> Any:
        return self.env

    def get_wrapper_attr(self, name: str) -> Any:
        if name in self.__dict__:
            return self.__dict__[name]
        return getattr(self.env, name)

    def reset(self, **kwargs: Any):
        return self.env.reset(**kwargs)

    def step(self, action: Any):
        return self.env.step(action)

    def close(self) -> None:
        self.env.close()


class FakeBoxEnv:
    """A continuous-action environment: ``Box`` action with element limits."""

    def __init__(self) -> None:
        self.action_space = Box([-1.0, -2.0], [1.0, 2.0])
        self.observation_space = Dict({"position": Box([-10.0], [10.0]), "mode": Discrete(3)})
        self.position = 0.0
        self.actions: list[Any] = []

    def reset(self, seed: int | None = None, options: Any = None):
        self.position = 0.0
        return {"position": [self.position], "mode": 0}, {}

    def step(self, action: Any):
        self.actions.append(list(action))
        self.position += float(action[0])
        return {"position": [self.position], "mode": 1}, -abs(self.position), False, False, {}


# ---------------------------------------------------------------------------
# mujoco fakes
# ---------------------------------------------------------------------------


class _Opt:
    timestep = 0.002


class FakeMjModel:
    """The MjModel members the bridge reads (two hinge joints, two motors)."""

    def __init__(self) -> None:
        self.opt = _Opt()
        self.nq = 2
        self.nv = 2
        self.nu = 2
        self.na = 0
        self.actuator_ctrlrange = [[-1.0, 1.0], [-0.5, 0.5]]
        self.actuator_ctrllimited = [1, 1]


class FakeMjData:
    def __init__(self, model: FakeMjModel) -> None:
        self.qpos = [0.0] * model.nq
        self.qvel = [0.0] * model.nv
        self.ctrl = [0.0] * model.nu
        self.act: list[float] = []
        self.qacc_warmstart = [0.0] * model.nv
        self.time = 0.0


class _MjtState:
    mjSTATE_TIME = 1
    mjSTATE_QPOS = 2
    mjSTATE_QVEL = 4
    mjSTATE_ACT = 8
    mjSTATE_WARMSTART = 16
    mjSTATE_CTRL = 32
    mjSTATE_INTEGRATION = 63


def _make_fake_mujoco() -> types.SimpleNamespace:
    calls: list[str] = []

    def mj_step(model: FakeMjModel, data: FakeMjData) -> None:
        calls.append("mj_step")
        dt = model.opt.timestep
        for i in range(model.nv):
            data.qvel[i] += data.ctrl[i] * dt
            data.qpos[i] += data.qvel[i] * dt
        data.time += dt

    def mj_resetData(model: FakeMjModel, data: FakeMjData) -> None:
        calls.append("mj_resetData")
        data.qpos[:] = [0.0] * model.nq
        data.qvel[:] = [0.0] * model.nv
        data.ctrl[:] = [0.0] * model.nu
        data.time = 0.0

    def mj_forward(model: FakeMjModel, data: FakeMjData) -> None:
        calls.append("mj_forward")

    def mj_stateSize(model: FakeMjModel, spec: int) -> int:
        return sum(size for bit, size in ((1, 1), (2, model.nq), (4, model.nv),
                                         (8, model.na), (16, model.nv), (32, model.nu)) if spec & bit)

    def mj_getState(model: FakeMjModel, data: FakeMjData, state: Any, spec: int) -> None:
        calls.append("mj_getState")
        values = []
        for bit, part in ((1, [data.time]), (2, data.qpos), (4, data.qvel),
                          (8, data.act), (16, data.qacc_warmstart), (32, data.ctrl)):
            if spec & bit:
                values.extend(part)
        for index, value in enumerate(values):
            state[index] = value

    def mj_setState(model: FakeMjModel, data: FakeMjData, state: Any, spec: int) -> None:
        calls.append("mj_setState")
        values = [float(v) for v in state]
        offset = 0
        for bit, name, size in ((1, "time", 1), (2, "qpos", model.nq), (4, "qvel", model.nv),
                                (8, "act", model.na), (16, "qacc_warmstart", model.nv), (32, "ctrl", model.nu)):
            if spec & bit:
                if name == "time":
                    data.time = values[offset]
                else:
                    getattr(data, name)[:] = values[offset:offset + size]
                offset += size

    return types.SimpleNamespace(
        mj_step=mj_step,
        mj_resetData=mj_resetData,
        mj_forward=mj_forward,
        mj_stateSize=mj_stateSize,
        mj_getState=mj_getState,
        mj_setState=mj_setState,
        mjtState=_MjtState,
        calls=calls,
    )


def fake_mujoco() -> types.SimpleNamespace:
    """A fresh fake ``mujoco`` module (records the calls it receives)."""

    return _make_fake_mujoco()


# ---------------------------------------------------------------------------
# SCPI transcript (a lock-in amplifier, SR860-like)
# ---------------------------------------------------------------------------

IDN = "Stanford_Research_Systems,SR860,003456,v1.47"

LOCKIN_TRANSCRIPT: dict[str, Any] = {
    "transcript": "1.0",
    "name": "sr860-lockin",
    "terminator": "\n",
    "exchanges": [
        {"send": "*IDN?", "recv": IDN},
        {"send": "FREQ?", "recv": "1000.0"},
        {"send": "FREQ 2000"},
        {"send": "FREQ?", "recv": "2000.0"},
        {"send": "OUTP? 0", "recv": "1.25E-6"},
    ],
}
