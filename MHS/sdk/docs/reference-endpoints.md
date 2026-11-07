# Reference endpoints (protocol fixtures)

`mhs.reference` ships four deterministic, stdlib-only endpoints. They are **protocol fixtures, not driver
templates**. They exercise discovery, sessions, revisions, idempotency, receipts, interlocks, permits,
snapshot/restore, evidence chains, replay and the conformance suite. Their bridges and manifests are written by hand
and still drift from some catalogue classes (see the last section). Never copy them into a driver package: write a
driver with `mhs.driver` ([driver-authoring.md](driver-authoring.md)), as in `MHS/sdk/examples/thermostat`.

## Launch

```sh
export PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=MHS/sdk/src
python3 -m mhs.reference conveyor --port 7400                  # HTTP on 127.0.0.1
python3 -m mhs.reference conveyor --port 7400 --test-profile   # adds x-cap.mhs-test.* fault injection
python3 -m mhs.reference lab --port 7401
python3 -m mhs.reference arm --port 7402 --noise --seed 42
python3 -m mhs.reference replay --port 7403 --bundle MHS/sdk/docs/reports/replay-bundle-conveyor.json
python3 -m mhs.reference conveyor --stdio                      # newline-delimited JSON-RPC on stdin/stdout
```

Each line starts one server and runs until interrupted. Before serving, the HTTP form prints one ready line on
stdout, and `--stdio` prints it on stderr:

```json
{"mhs_ready": true, "transport": "http", "endpoint_id": "mhs://localhost:7400",
 "url": "http://127.0.0.1:7400", "devices": [{"device_id": "mhs://localhost:7400/lab/conveyor-workcell",
 "mode": "simulated", "capabilities": ["cap.world.step.v1"]}], "profile": "MHS-Sim", "name": "conveyor",
 "test_profile": false}
```

The descriptor is at `GET /.well-known/mhs.json`, JSON-RPC at `POST /mhs/v1/rpc` and events at
`GET /mhs/v1/events`. `--port 0` picks a free port and reports it in the ready line.

## What every fixture shares

- **Verbs**: each binding serves the verb of its catalogue class. `hello`, `devices.list` and `devices.get` publish
  it: for example `cap.world.state.v1` is `read`, `cap.actuation.valve.v1` and `cap.world.seed.v1` are `write`,
  `cap.world.step.v1` is `invoke`. A read never advances the revision and stays callable while latched. `x-cap`
  extensions are `invoke`.
- **MCP tool names** come from the device id and the capability id, for example
  `mhs__lab_conveyor_workcell__world_state`. They are unchanged by the 0.9 fixes.
- **Identity**: `vendor` is `OpenMHS reference fixture`, and `provenance.adapter_id` is
  `openmhs:reference.<device>` (prefix `mhs._ids.ADAPTER_ID_PREFIX`).
- **Conformance claim**: a device publishes `conformance` only when the report that backs it can be read, either
  from the directories in `MHS_CONFORMANCE_REPORTS` (`os.pathsep`-separated, reports looked up by file name) or
  from the source checkout. An installed package without the reports publishes no claim.
- **Cancellation**: a cancelled call raises `mhs.signals.Cancelled`, so its receipt is `cancelled`.
- The runtime serves them in compatibility mode. The remaining drift is reported as `MHSStrictWarning` findings.

## `conveyor`: deterministic workcell

Device `…/lab/conveyor-workcell`, mode `simulated`, risk `R1`, fidelity F0 exact (integer 1 ms ticks). Report
[`MHS/conformance/reports/conveyor-cl4.json`](../../conformance/reports/conveyor-cl4.json): MHS-Sim CL4.

| Capability | Verb | Semantics |
|---|---|---|
| `cap.world.step.v1` | invoke | advance the simulation by `ticks` (1..10000) |
| `cap.world.state.v1` | read | the complete world state |
| `cap.actuation.valve.v1` | write | diverter `gate` `main`/`divert` (permit-gated, door interlock) |
| `cap.motion.stop.v1` | invoke | drive stopped, gate to main: the declared safe state |
| `cap.world.snapshot.v1`, `cap.world.restore.v1` | invoke | exact snapshot and restore |
| `x-cap.mhs-reference.start.v1` | invoke | start the drive at `speed_mm_s` (0..200) |
| `x-cap.mhs-reference.feed.v1` | invoke | place 1..32 parts on the infeed when it is clear |

`--test-profile` adds `x-cap.mhs-test.fault_inject.v1` (`jam`, `sensor_fault`, `lost_receipt`),
`x-cap.mhs-test.set_door.v1` and the bounded, cancellable `x-cap.mhs-test.delay.v1`. Only that profile binds them,
and only that profile declares their envelope. `lost_receipt` applies the effect and then raises
`MHS.OUTCOME.UNKNOWN` (receipt `unknown`; do not retry blindly). Opening the door or an e-stop latches the
workcell, and `mhs.safety.reset` releases the latch only with the door closed.

## `lab`: pipette, plate reader and sample mover

One endpoint, three simulated devices on one bench. Report
[`MHS/conformance/reports/lab-cl4.json`](../../conformance/reports/lab-cl4.json): MHS-Sim CL4.

| Device | Risk | Capabilities (verb) |
|---|---|---|
| `…/lab/liquid-handler` | R2 | `cap.fluid.aspirate.v1`, `cap.fluid.dispense.v1`, `cap.fluid.transfer.v1` (invoke; integer µL, consumable tips), `cap.fluid.level.v1` (read), `cap.motion.stop.v1` |
| `…/lab/plate-reader` | R0 | `cap.measure.spectrum.v1` (invoke; 1..16 wavelengths 400..800 nm, a pure function of well volume) |
| `…/lab/sample-mover` | R1 | `cap.sample.move.v1` (invoke; `to` = `liquid_handler`, `reader`, `output`), `cap.motion.stop.v1` |

The plate reader has no actuator. Its safe state is "reader idle" with an empty `achieved_by`, so its e-stop
completes. Preconditions are refused as receipts: the plate must be on the deck to pipette and on the reader to
measure. A session over several devices names `device_id` on every command:

```python
import warnings

from mhs.reference import build_endpoint, build_server
from mhs.testing import client_for

warnings.simplefilter("ignore")      # the fixtures' documented drift is reported as MHSStrictWarning
spec = build_endpoint("lab")
lab = client_for(build_server(spec, log_ready=False))
ids = {device["device_id"].rsplit("/", 1)[-1]: device["device_id"] for device in lab.devices()}
session = lab.open_session(ttl_s=600)["session_id"]    # one session over the three devices
lab.invoke("cap.fluid.transfer.v1", {"source_well": "A1", "destination_well": "B1", "volume_ul": 25},
           device_id=ids["liquid-handler"], session_id=session)
lab.invoke("cap.sample.move.v1", {"plate_id": "plate-001", "to": "reader"},
           device_id=ids["sample-mover"], session_id=session)
od = lab.invoke("cap.measure.spectrum.v1", {"plate_id": "plate-001", "wavelengths_nm": [600], "well_ids": ["B1"]},
                device_id=ids["plate-reader"], session_id=session)
print(od["output"]["readings"][0]["absorbance_mAU"])
spec.close()
```

## `arm`: 2-DOF planar arm

Device `…/robot/arm-2dof`, risk `R1`, F0 analytic, with integer millidegrees and micrometres. Report
[`MHS/conformance/reports/arm-cl4.json`](../../conformance/reports/arm-cl4.json): MHS-Sim CL4. The seeded-noise
configuration cites its own report,
[`MHS/sdk/docs/reports/conformance-arm-2dof-seeded.json`](reports/conformance-arm-2dof-seeded.json) (CL4).

| Capability | Verb | Semantics |
|---|---|---|
| `cap.motion.joint_position.v1` | invoke | `joint_positions_deg` [q1, q2]; the envelope is ±135° per joint, and the model itself refuses q1 beyond ±90° |
| `cap.motion.cartesian_pose.v1` | invoke | planar `x_mm`/`y_mm` (±450) via closed-form IK, `elbow` `down`/`up` |
| `cap.motion.home.v1`, `cap.motion.stop.v1` | invoke | joints to zero / stop at the current pose (the safe state) |
| `cap.world.state.v1` | read | joints, pose, mode and determinism counters |
| `cap.world.snapshot.v1`, `cap.world.restore.v1` | invoke | exact snapshot and restore, PRNG state included |
| `cap.world.seed.v1` | write | xorshift32 seed of the `--noise` mode |

With `--noise` the fidelity contract declares `determinism: seeded` (`seed_control: parameter`): the same seed
reproduces the same poses.

## `replay`: a recorded session, read-only

`--bundle <file>` serves a recording as a `mode: replay` device. Reads, snapshots and restores of a recorded
revision work, and every `mhs.command` is refused with `MHS.MODE.READ_ONLY`. Report
[`MHS/sdk/docs/reports/conformance-replay-recorded.json`](reports/conformance-replay-recorded.json): CL2 (with
nothing to actuate, `SAFE-014` has nothing to probe). Record a bundle from any fixture and serve it:

```python
import tempfile
import warnings
from pathlib import Path

from mhs.reference import build_endpoint, build_server
from mhs.reference.replay import build_replay_bundle
from mhs.testing import client_for

warnings.simplefilter("ignore")
spec = build_endpoint("conveyor")
client = client_for(build_server(spec, log_ready=False))
client.open_session(ttl_s=600)
path = Path(tempfile.mkdtemp()) / "replay-bundle.json"
build_replay_bundle(client, commands=[
    {"capability_id": "cap.world.step.v1", "input": {"ticks": 200}},
    {"capability_id": "cap.world.step.v1", "input": {"ticks": 400}},
], path=path)
spec.close()

replay = build_endpoint("replay", bundle=str(path))
client = client_for(build_server(replay, log_ready=False))
session = client.open_session(ttl_s=600)["session_id"]
refused = client.invoke("cap.world.step.v1", {"ticks": 1}, session_id=session)
assert (refused["status"], refused["error"]["mhs_code"]) == ("rejected", "MHS.MODE.READ_ONLY")
replay.close()
```

## Known drift (realigned after the pilot)

These bindings keep their field names and MCP tool names until the post-pilot class realignment. Conformance
reports them as the advisory tests `CAP-016` (schema drift) and `TCAP-002` (resource kind). Strict mode would
refuse them, so the fixtures run in compatibility mode.

| Endpoint | Capability | Drift |
|---|---|---|
| conveyor | `cap.actuation.valve.v1` | input `gate` (class: `position`/`outlet`/`state`); bound to a `world.sim` resource |
| conveyor | `cap.motion.stop.v1` | bound to a `world.sim` resource (class kinds: arm, mobile base, axis) |
| lab | `cap.fluid.aspirate.v1`, `cap.fluid.dispense.v1`, `cap.fluid.transfer.v1` | inputs `source_well`/`destination_well`/`volume_ul` (class: `source`/`target`/`volume`) |
| lab | `cap.fluid.level.v1` | input `well_ids` (class: `container`, `method`) |
| lab | `cap.measure.spectrum.v1` | inputs `plate_id`/`wavelengths_nm`/`well_ids` (class: `wavelength_min`/`wavelength_max` required) |
| lab | `cap.sample.move.v1` | inputs `plate_id`, `to` as a string (class: `sample_id`, `from`/`to` objects) |
| lab | `cap.motion.stop.v1` | bound to a `lab.pipette` and a `lab.labware` resource |
| arm | `cap.motion.joint_position.v1` | input `joint_positions_deg` in degrees (class: `joint_positions` in rad) |
| arm | `cap.motion.cartesian_pose.v1` | inputs `x_mm`/`y_mm`/`elbow` (class: `position{x,y,z}`) |
| arm | `cap.world.state.v1`, `cap.world.snapshot.v1`, `cap.world.restore.v1`, `cap.world.seed.v1` | bound to a `robot.arm` resource (class kind: `world.sim`) |

Outputs that do not have the class shape yet (compatibility mode completes them with a warning): `cap.world.state.v1`
(no `state` member), `cap.world.step.v1` (no `observation`), `cap.actuation.valve.v1` (no `position`),
`cap.fluid.level.v1` (no `level_mm`), `cap.fluid.transfer.v1` (no `transferred_volume`) and
`cap.motion.joint_position.v1` (no `joint_positions`).

Fixed in 0.9: every binding serves its catalogue verb; the conveyor's `ticks` start at the class minimum 1; the
test-profile delay envelope exists only in the test profile; the plate reader's `achieved_by` no longer names an
unbound class (its e-stop used to fail with `SAFE_STATE_UNREACHED`); the plate, plate reader and bench resources use
catalogue kinds (`lab.labware`, `instrument.spectrophotometer`).
