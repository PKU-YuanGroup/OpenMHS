OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Bridge families: the canonical grammar

A bridge translates between the contract plane and one equipment family. The runtime (`mhs.server`) enforces every
safety rule: limits, interlocks, the e-stop latch, permits, receipts and revisions. A per-repository driver uses a
bridge through its family driver class ([driver-authoring.md](driver-authoring.md)). The class attributes
`commands`, `reads`, `writes` and `safety_bindings` are the bridge maps below. An `mhs-adapter.json` loaded by
`mhs.adapter.load` carries the same maps in `bridges[].config`. This page documents only the canonical grammar.
The deprecated in-process shape (`"grammar": "legacy"`) is not documented and must not be used.

| Module | Family driver | Native side | Fake backend |
|---|---|---|---|
| `bridge/python.py` | `PythonObjectDriver` | a Python object (sync or async SDK) | a package class with the upstream methods |
| `bridge/serial.py` | `SerialDriver` | a line-oriented serial port (`pyserial`, imported lazily) | a pyserial-like object (`mhs.bridge.serial.FakeSerial`) or a transcript |
| `bridge/scpi.py` | `ScpiDriver` | SCPI over a TCP socket (stdlib) or `pyvisa` | an object with `write/read/query`, or a transcript |
| `bridge/gymnasium.py` | `GymnasiumDriver` | a Gymnasium environment (`env_id`) | a fake environment or the upstream environment |
| `bridge/mujoco.py` | `MujocoDriver` | a MuJoCo model (`mujoco`, imported lazily) | a fake `mujoco` module |
| `bridge/replay.py` | none | a recorded evidence bundle (read-only) | not applicable |

Bridge modules are libraries. `python3 -m mhs.bridge.<name>` prints `use: mhs serve <driver-dir|mhs-adapter.json>`
and exits 2.

## Rules shared by every family

- **Reject, never clamp.** A value outside a `clamp` or limit is refused with `MHS.SAFETY.ENVELOPE_VIOLATION`
  before any native call. Nothing is truncated. Declare limits on the driver's fields; the runtime checks them.
- **Units** are UCUM codes from `mhs.units`. They are converted once, at the boundary. `%` is the ratio 0.01. A
  `clamp` `unit` must be the conversion's `to` unit, and an unknown or mismatched unit is a load error.
- **Inputs** may not be NaN or infinite. A string argument with a line break or a control character (and `;` for
  SCPI) is refused with `MHS.CAPABILITY.INPUT_INVALID`, so an input cannot inject a second command.
- **Every native call is bounded** by its `timeout_ms` and the request deadline. When the bound expires the outcome
  is `unknown` (`MHS.OUTCOME.UNKNOWN`, not retryable), never a retryable failure.
- **Errors**: `errors` rules map native exceptions to registered codes (the driver subset under `strict`). An
  unmapped exception is `MHS.ADAPTER.SHIM_FAILED` with a redacted message.
- **E-stop**: the e-stop never waits for a running call. An actuation that has not reached the wire (or the native
  call) when the e-stop fires is refused with `MHS.SAFETY.ESTOP_ENGAGED` and never sent. Serial and SCPI write the
  stop command under a short wire lock, so no actuating request follows it on the wire.
- **`parse` kinds** are `raw`, `str`, `float`, `int`, `bool` and `regex` (`pattern`, `group`). `bool` is strict:
  `1`, `ON`, `TRUE` (or the declared `true` token) and `0`, `OFF`, `FALSE` (or the declared `false` token); a custom
  `true` token needs a `false` token. Any other reply is a parse error.
- **Interlocks** (`safety_bindings.interlocks`) read `closed`, `open` or `unknown`. A boolean `closed_when`
  (default `true`, or `false` for an inverted query such as `DOOR:OPEN?`) needs `parse: {"kind": "bool"}`, and a
  `bool` parse needs a boolean `closed_when`. `int`, `float` and `regex` parses must match the whole reply (anchor a
  `pattern` with `^...$`), so `ERR 1` never reads 1. An unrecognised reply is `unknown`. `unknown` blocks like
  `open`, and a reset is refused unless every interlock is `closed`.

## python-object (`PythonObjectDriver`)

Each `commands` entry is one canonical binding:

| Key | Rule |
|---|---|
| `native` | required: the method or attribute of the backend object |
| `invoke` | `call` (default; awaitables, futures and Status-like returns are awaited), `get`, `set`, `await`, `status`, `query`, `write` |
| `args` | `{name: {"from": "input.<field>", "type", "unit": {"from", "to"}, "enum_map", "clamp", "required", "default"}}` |
| `result` | required: `{"map": {<output field>: <path>}}`, non-empty; `output.$` is the raw native return, `output.x` its member `x` |
| `errors` | `[{"native": "ValueError", "mhs_code": "MHS.CAPABILITY.INPUT_INVALID", "retryable": false}]` |
| `concurrency` | required: `shared`, `serialized` or `exclusive` |
| `timeout_ms` | required: the bound of the native call |
| `command`, `parse` | the request text and its parser, for `invoke` `query`/`write` |

`reads` maps a parameter to `{"native", "invoke"}` (a getter). `writes` maps a parameter to `{"native", "invoke"}`
(`set` for a property, `call` or `await` for a method that takes the value). `safety_bindings` take
`{"estop", "safe_state", "reset"}` calls (`native`, `invoke`, `timeout_ms`) and `interlocks`
(`{"id", "native", "invoke", "parse", "closed_when", "blocks"}`). `blocks` lists the capability ids an interlock
gates.

```python
from mhs.driver import Action, Field, Limit, PythonObjectDriver, build_server, close_server
from mhs.testing import client_for


class FakeJulabo:                    # stands in for the upstream class julabo.device:JulaboCF
    def __init__(self, **_options):
        self.temperature, self.target, self.circulating = 21.5, 20.0, True

    async def bath_temperature(self):   # async natives are awaited on the driver's event loop
        return self.temperature

    async def set_point_1(self, value):
        self.target = value

    async def identification(self):
        return "JULABO CF41 (fake)"

    async def stop(self):
        self.circulating = False


class Julabo(PythonObjectDriver):
    device_id, device_kind, mode, risk = "julabo", "thermal.zone", "hardware", "R1"
    native = "julabo.device:JulaboCF"
    backends = {"fake": FakeJulabo}
    safe_state = "circulation stopped"
    parameters = {
        "temperature": Field("number", unit="Cel", description="Bath temperature"),
        "setpoint": Field("number", unit="Cel", writable=True, description="Working setpoint 1",
                          limit=Limit(min=-20, max=150, source="upstream_code", ref="julabo/device.py:88")),
    }
    reads = {"temperature": {"native": "bath_temperature", "invoke": "await"}}
    writes = {"setpoint": {"native": "set_point_1", "invoke": "await"}}
    commands = {"x-cap.julabo.identify.v1": {"native": "identification", "invoke": "await", "concurrency": "shared",
                                             "timeout_ms": 2000, "result": {"map": {"identity": "output.$"}}}}
    actions = {"x-cap.julabo.identify.v1": Action(name="identify", description="Identify the circulator",
                                                  output={"identity": Field("string", description="Model string")})}
    safety_bindings = {"estop": {"native": "stop", "invoke": "await"}}


driver = Julabo(backend="fake")
server = build_server(driver)
client = client_for(server)
device_id = client.hello()["devices"][0]["device_id"]
session = client.open_session(device_ids=[device_id])["session_id"]


def configure(value):
    return client.invoke("cap.device.configure.v1", {"setpoint": value}, device_id=device_id, session_id=session)


assert configure(37)["status"] == "completed"
assert configure(200)["error"]["mhs_code"] == "MHS.SAFETY.ENVELOPE_VIOLATION"
assert client.invoke("x-cap.julabo.identify.v1", {}, device_id=device_id,
                     session_id=session)["output"] == {"identity": "JULABO CF41 (fake)"}
client.estop("demo", device_id=device_id, session_id=session)
assert driver.native.circulating is False
close_server(server)
```

## serial (`SerialDriver`)

| Map | Entry |
|---|---|
| `commands` | `{"command": "TEMP?", "args", "parse", "response": true, "result": {"map": ...}}`; a parsed reply is `{"value": ...}` (`{<parse.field>: ...}` when `field` is set, `{"raw": ...}` for `raw`), so map `output.value` |
| `reads` | `{param: {"command": "RATE?", "parse": {...}}}` |
| `writes` | `{param: {"command": "RATE {value}", "type": "number", "response": true}}` |
| `safety_bindings` | `estop` `{"command"}` (written, no response read), `safe_state` `{"command": [..]}`, `reset` `{"command", "response"}`, `interlocks` `[{"id", "command", "parse", "closed_when"}]` |

The line settings are class attributes: `port`, `baudrate`, `timeout_s`, `terminator`, `encoding`, `bytesize`,
`parity` and `stopbits`. Only the hardware view opens the port. A `transcript = "fixtures/session.json"` attribute
replays a recording strictly: an unread response or a different request raises.

```python
from mhs.bridge.serial import FakeSerial
from mhs.driver import Action, Field, Limit, SerialDriver, build_server, close_server
from mhs.testing import client_for


class FakePump(FakeSerial):          # pyserial-like: answers each command line from a table
    def __init__(self, **_options):
        super().__init__({"*IDN?": "ACME,P1,0,1.0\r\n", "RATE?": "1.5\r\n", "DOOR?": "1\r\n"}, default="OK\r\n")


class Pump(SerialDriver):
    device_id, device_kind, mode, risk = "pump", "fluid.pump", "hardware", "R1"
    native = "acme_pump.serial:Pump"
    backends = {"fake": FakePump}
    safe_state = "pump stopped"
    terminator = "\r\n"
    parameters = {"rate": Field("number", unit="mL/min", writable=True, description="Flow rate",
                                limit=Limit(min=0, max=10, source="vendor_doc", ref="manual.md:20"))}
    reads = {"rate": {"command": "RATE?", "parse": {"kind": "float"}}}
    writes = {"rate": {"command": "RATE {value}", "type": "number"}}
    commands = {"x-cap.acme.identify.v1": {"command": "*IDN?", "parse": {"kind": "str"},
                                           "result": {"map": {"identity": "output.value"}}}}
    actions = {"x-cap.acme.identify.v1": Action(name="identify", description="Identify the pump",
                                                output={"identity": Field("string", description="*IDN? reply")})}
    safety_bindings = {"estop": {"command": "STOP"},
                       "interlocks": [{"id": "door", "command": "DOOR?", "parse": {"kind": "int"}, "closed_when": 1,
                                       "blocks": ["cap.device.configure.v1"]}]}


server = build_server(Pump(backend="fake"))
client = client_for(server)
device_id = client.hello()["devices"][0]["device_id"]
session = client.open_session(device_ids=[device_id])["session_id"]
assert client.invoke("cap.device.configure.v1", {"rate": 2.5}, device_id=device_id,
                     session_id=session)["status"] == "completed"
assert client.safety_status(device_id)["interlocks"][0]["state"] == "closed"
close_server(server)
```

## SCPI (`ScpiDriver`)

| Map | Entry |
|---|---|
| `commands` | `{"query": "FREQ?"` or `"write": "FREQ {value:g}", "args", "parse", "result", "opc", "errors", "check_errors"}`; a parsed query maps `output.$` |
| `reads` | `{param: {"query": "FREQ?", "parse": {...}}}` |
| `writes` | `{param: {"write": "FREQ {value:g}", "type": "number"}}` |
| `idn`, `error_query` | `{"expect": "<regex>"}` checked against `*IDN?` on connect; `SYST:ERR?` read after writes |
| `safety_bindings` | `estop`/`safe_state` `{"write": "OUTP OFF"}` (or a list), `interlocks` `[{"id", "query", "parse", "closed_when"}]` |

Templates are `str.format` strings with plain named fields. A query is written and then read in two steps. The
hardware view connects to `host`/`port` (raw SCPI, often port 5025) or `visa_resource`.

```python
from mhs.driver import Action, Field, Limit, ScpiDriver, build_server, close_server
from mhs.testing import client_for


class FakeLockin:                    # a fake transport: write/read/query of text lines
    def __init__(self, **_options):
        self.freq, self.out, self.pending = 1000.0, "ON", []

    def write(self, line, *, timeout_s=None):
        if line.startswith("FREQ "):
            self.freq = float(line.split()[1])
        elif line == "OUTP OFF":
            self.out = "OFF"
        elif line.endswith("?"):
            self.pending.append({"*IDN?": "Stanford_Research_Systems,SR860,0,1.0",
                                 "FREQ?": f"{self.freq:g}"}.get(line, ""))

    def read(self, *, timeout_s=None):
        return self.pending.pop(0)

    def query(self, line, *, timeout_s=None):
        self.write(line)
        return self.read()

    def close(self):
        pass


class Lockin(ScpiDriver):
    device_id, device_kind, mode, risk = "lockin", "instrument", "hardware", "R1"
    native = "srsinst.sr860:SR860"
    backends = {"fake": FakeLockin}
    safe_state = "signal output off"
    idn = {"expect": "^Stanford_Research_Systems,SR860"}
    parameters = {"frequency": Field("number", unit="Hz", writable=True, description="Reference frequency",
                                     limit=Limit(min=0.001, max=500000, source="vendor_doc", ref="manual.pdf:112"))}
    reads = {"frequency": {"query": "FREQ?", "parse": {"kind": "float"}}}
    writes = {"frequency": {"write": "FREQ {value:g}", "type": "number"}}
    commands = {"x-cap.srs.identify.v1": {"query": "*IDN?", "parse": {"kind": "str"},
                                          "result": {"map": {"identity": "output.$"}}}}
    actions = {"x-cap.srs.identify.v1": Action(name="identify", description="Identify the instrument",
                                               output={"identity": Field("string", description="*IDN? reply")})}
    safety_bindings = {"estop": {"write": "OUTP OFF"}}


driver = Lockin(backend="fake")
server = build_server(driver)
client = client_for(server)
device_id = client.hello()["devices"][0]["device_id"]
session = client.open_session(device_ids=[device_id])["session_id"]
assert client.invoke("cap.device.configure.v1", {"frequency": 2000}, device_id=device_id,
                     session_id=session)["status"] == "completed"
assert client.read("main", device_id=device_id, session_id=session)["state"] == {"frequency": 2000.0}
client.estop("demo", device_id=device_id, session_id=session)
assert driver.native.out == "OFF"
close_server(server)
```

## Transcripts

`mhs.testing.Transcript` replays recorded exchanges strictly: requests in the recorded order and with the recorded
text, every recorded response read before the next request (unless `"recv_optional": true`). Any divergence
raises `TranscriptDivergence`. `.line_transport()` serves `ScpiBridge`, `.serial()` serves `SerialBridge`, and
`.recorder(live)` records a real session. The runtime reads the state for every receipt, so a strict transcript of
a full driver must include those reads. Stateful fakes are usually simpler.

```python
from mhs.bridge.base import BridgeContext
from mhs.bridge.scpi import ScpiBridge
from mhs.testing import Transcript, TranscriptDivergence

session = Transcript([{"send": "*IDN?", "recv": "Stanford_Research_Systems,SR860,0,1.0"},
                      {"send": "FREQ?", "recv": "1000"}])
bridge = ScpiBridge({"idn": {"expect": "^Stanford_Research_Systems,SR860"},
                     "commands": {"x-cap.srs.frequency.v1": {
                         "resource": "lockin", "query": "FREQ?", "parse": {"kind": "float"},
                         "result": {"map": {"frequency": "output.$"}}}}},
                    transport=session.line_transport())
assert bridge.call("x-cap.srs.frequency.v1", {}, BridgeContext()) == {"frequency": 1000.0}
session.assert_complete()
try:
    bridge.call("x-cap.srs.frequency.v1", {}, BridgeContext())   # not in the recording
    raise AssertionError("expected a divergence")
except TranscriptDivergence:
    pass
bridge.close()
```

## Gymnasium and MuJoCo (`GymnasiumDriver`, `MujocoDriver`)

The simulator families are configuration only. Gymnasium takes `env_id` (and `autoreset`). The bridge derives the
`cap.world.step.v1` schema and limits from the spaces:

- `Discrete(n)` is `{"index": i}`. `Box` is `{"values": [...]}`, with per-element limits from `low`/`high`.
  `MultiDiscrete` and `MultiBinary` are `{"values": [ints]}` with element limits.
- The derived limits say where the space came from. They are `upstream_code` (`ref` `<env_id>:action_space`) when
  the bridge built the environment itself (`gym.make(env_id)`, `env_spec`). A pre-built `env=` (a driver's fake
  backend) gives them no source, only a `ref` that names `env_origin`. `action_space_ref="path:LINE"` (the
  driver's attribute of the same name) cites the upstream line that defines the space instead; see
  [driver-authoring.md](driver-authoring.md) section 5.
- A `Dict` maps to named fields, and nested `Dict` members are bounded member by member. `Tuple` is
  `{"items": [...]}`, with structure but no element limits (a simulation-only residual).
- A step input is `{"ticks", "action"}`. The bridge steps `ticks` times, stops at a terminal state unless
  `autoreset`, and returns `{observation, reward, terminated, truncated, tick, state_hash}`. The seed and reset
  classes are `cap.world.seed.v1` (`{seed}` -> `{seed, accepted}`) and `cap.world.reset.v1`. Snapshots are offered
  only when the environment has `get_state`/`set_state`.
- Per-backend profiles: physics timing ([simulation-timing.md](simulation-timing.md), including resets that
  integrate physics), JSON checkpoints and their explicit opt-out ([gym-checkpoints.md](gym-checkpoints.md)),
  asynchronous environments and dm_env environments ([gym-live-routes.md](gym-live-routes.md)), and environments
  built in an isolated simulator host process ([sim-host.md](sim-host.md)).
- While a native step, reset or checkpoint call is in flight, neither family reports the safe state achieved; the
  endpoint's e-stop waits for it at most its budget, otherwise answers `SAFE_STATE_UNREACHED` and retries in the
  background ([gym-live-routes.md](gym-live-routes.md), "Synchronous simulators and the e-stop").

MuJoCo checks `action.ctrl` against `actuator_ctrlrange` before writing `data.ctrl`. An actuator the model gives no
control range (`ctrllimited` false, or no `ctrlrange` under `autolimits`; MuJoCo then leaves its control unclamped) is
`operator_required`: the whole `action.ctrl` when no actuator has a range, else one rule per element
(`action.ctrl[N]`, the model's range or `operator_required`). The endpoint refuses a step that sets such a control with
`MHS.SAFETY.LIMITS_UNSET` before the native step until the operator's `site-limits.json` bounds it (a step without
`action` keeps the controls), and the bridge itself never writes a non-finite control. It steps `ticks` times, snapshots
the full integration state (`mj_getState`), and reads the time step from `model.opt.timestep`. The `world` state is
`{time_ms, qpos, qvel, ctrl, tick, timestep_ms, seed}`, and `MujocoDriver` declares exactly these fields, so a package
declares no state of its own (before 0.9.0.dev0 of 2026-10-29 the family declared only `observation` and `tick`, and every
MuJoCo package failed `G6.READ_INVALID`).

```python
from mhs.driver import GymnasiumDriver, build_server, close_server
from mhs.testing import client_for


class Discrete:                      # duck-typed gymnasium.spaces.Discrete
    def __init__(self, n):
        self.n, self.start, self.shape, self.dtype = n, 0, (), "int64"


class Box:                           # duck-typed gymnasium.spaces.Box
    def __init__(self, low, high):
        self.low, self.high, self.shape, self.dtype = low, high, (len(low),), "float32"


class FakeCartPole:                  # in a package: fake.py, or the upstream's own environment
    def __init__(self, **_options):
        self.action_space = Discrete(2)
        self.observation_space = Box([-4.8, -1e9], [4.8, 1e9])
        self.x = 0.0

    def reset(self, seed=None, options=None):
        self.x = 0.0
        return [self.x, 0.0], {}

    def step(self, action):
        self.x += 0.1 if action == 1 else -0.1
        return [self.x, 0.0], 1.0, abs(self.x) > 2.4, False, {}

    def close(self):
        pass


class CartPole(GymnasiumDriver):
    device_id = "cartpole"
    env_id = "CartPole-v1"
    native = "gymnasium.envs.classic_control.cartpole:CartPoleEnv"
    backends = {"fake": FakeCartPole}
    safe_state = "episode reset"


server = build_server(CartPole(backend="fake"))
client = client_for(server)
device_id = client.hello()["devices"][0]["device_id"]
session = client.open_session(device_ids=[device_id])["session_id"]


def step(action, ticks):
    return client.invoke("cap.world.step.v1", {"ticks": ticks, "action": action}, device_id=device_id,
                         session_id=session)


assert step({"index": 1}, 5)["output"]["tick"] == 5
assert step({"index": 2}, 1)["error"]["mhs_code"] == "MHS.SAFETY.ENVELOPE_VIOLATION"   # outside Discrete(2)
close_server(server)
```

## `mhs-adapter.json`

`mhs.adapter.load(path)` also serves an `mhs-adapter.json` whose `bridges[].config` holds the maps above. A
`serial`, `scpi` or `scpi-visa` bridge has no fake transport, so its device must be `hardware` or `hybrid`, and
`load` refuses a simulated one. A `driver` bridge names a driver directory (one with `driver.py`).
`python3 -m mhs.driver export <dir>` writes the interop form of a driver package.
