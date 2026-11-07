# MHS-C — End-to-End Examples and Transcripts

| Field | Value |
|---|---|
| Document | MHS-C (informative) |
| Status | OpenMHS 0.9 development draft |
| Editor | The OpenMHS Authors |
| Layer | appendix: informative, never overrides a requirement ([profiles.md](profiles.md) §2) |
| Normative sources | [core.md](core.md), [MHS-002](02-wire-protocol.md), [MHS-003](03-capability-registry.md), [MHS-004](04-safety.md), [MHS-005](05-fidelity.md), [MHS-008](08-transports.md) |

This appendix contains five end-to-end examples: (1) a simulated conveyor workcell at CL4 exercising receipts,
idempotency, limits, interlocks, permits, the e-stop and evidence; (2) a lab of three devices driven by one code file;
(3) a simulated arm with a fidelity contract, determinism, snapshots and a replay endpoint; (4) a hybrid digital twin; and
(5) an MCP projection session.

Examples are informative: they show how the normative documents compose. Every block marked `# runnable` is executed
against the SDK, from the repository root, by `python3 MHS/sdk/tools/spec_doctest.py MHS/spec`; it is the authoritative
reproduction of the exchange next to it. The JSON blocks are **abridged** excerpts of what those runs return (fields are
omitted for readability, and identifiers, timestamps and digests change from run to run); a result is the bare
receipt, with no wrapper ([core.md](core.md) CORE-093). `[MHS-C-001]` to `[MHS-C-005]` are example labels, not requirements.

The reference endpoints used here are protocol fixtures, not driver templates: they predate the capability catalogue and
run in compatibility mode ([core.md](core.md) CORE-160), so a few of their input fields differ from the catalogue classes
and the SDK prints drift warnings that the runnable blocks silence. A driver package is the way to write a new endpoint
([driver-profile.md](driver-profile.md)).

---

## 1. Simulated conveyor workcell: a CL4 session with idempotency, a limit, an interlock, a permit, an e-stop and evidence

**Subject.** The reference conveyor endpoint (`python3 -m mhs serve conveyor --port 7400`; in the blocks below it is built
in process with the test profile, whose `x-cap.mhs-test.*` hooks open the door interlock). Its device manifest is
[`device.conveyor-workcell.json`](../schema/examples/device.conveyor-workcell.json): mode `simulated`, risk R1, fidelity
F0/exact, a software e-stop, `world.step` capped at 10 000 ticks. One device,
`mhs://localhost:7400/lab/conveyor-workcell`, one resource, `workcell`.

### 1.1 Hello and a session

```json
{"jsonrpc":"2.0","id":1,"method":"mhs.hello","params":{
  "client":{"name":"openai4s","version":"2.4.0"},"protocol_versions":["1.0"]}}
```

```json
{"jsonrpc":"2.0","id":1,"result":{
  "server":{"name":"mhs-reference-server","version":"0.9.0.dev0"},
  "implementation":{"name":"openmhs","version":"0.9.0.dev0"},
  "spec_version":"0.9","mhs_version":"1.0","protocol_versions":["1.0"],
  "endpoint_id":"mhs://localhost:7400",
  "devices":[{"device_id":"mhs://localhost:7400/lab/conveyor-workcell","mode":"simulated","risk_class":"R1","…":"…"}],
  "limits":{"max_request_bytes":1048576,"max_batch":64,"receipt_store":"memory","max_command_deadline_ms":600000,"…":"…"},
  "conformance":[{"profile":"MHS-Sim","level":"CL4","report_digest":"sha256:e248…"}],
  "features":["MHS.SAFETY.NOT_CERTIFIED","deterministic-simulation","evidence-chain","batch","sse","…"],
  "safety":{"certified":false,"notice":"MHS.SAFETY.NOT_CERTIFIED"}}}
```

The host knows, before any command, the mode, the risk class, the device's own conformance claim (a profile, a level and the
digest of the report behind it) and the mandatory safety disclaimer (PROTO-018, SAFE-050). A session is opened in the device's own mode with the grants the task needs:

```json
{"jsonrpc":"2.0","id":2,"method":"mhs.session.open","params":{
  "principal":{"id":"agent:openai4s/session-7","kind":"agent"},
  "device_ids":["mhs://localhost:7400/lab/conveyor-workcell"],
  "capabilities":["cap.world.*","cap.actuation.valve.v1","cap.motion.*"],
  "mode":"simulated","ttl_s":600}}
```

```json
{"jsonrpc":"2.0","id":2,"result":{
  "session_id":"mhs_s_01M610SWZKFE9BPHFBP22QFP2H74b5fd1a18e509bd",
  "granted":[{"device_id":"mhs://localhost:7400/lab/conveyor-workcell","capability_id":"cap.world.step.v1","resource":"workcell"},
             {"…":"one entry per granted binding"}],
  "mode":"simulated","expires_at":"2026-10-20T07:55:00.000Z","…":"…"}}
```

### 1.2 A command, its receipt, its replay and a reused id

```json
{"jsonrpc":"2.0","id":4,"method":"mhs.command","params":{
  "session_id":"mhs_s_01M6…","device_id":"mhs://localhost:7400/lab/conveyor-workcell",
  "capability_id":"cap.world.step.v1","input":{"ticks":10},
  "command_id":"01J8ZQ3V6Y7M2N4P6R8S0T2V4Y","deadline_ms":5000}}
```

```json
{"jsonrpc":"2.0","id":4,"result":{
  "receipt_id":"01M610SWZN8Y095P1Y1CGVF7EJ","command_id":"01J8ZQ3V6Y7M2N4P6R8S0T2V4Y",
  "capability_id":"cap.world.step.v1","resource_ids":["workcell"],"status":"completed","mode":"simulated",
  "state_revision_before":0,"state_revision_after":1,"replayed":false,
  "output":{"tick":10,"sensors":{"infeed":"clear","diverter":"clear"},"…":"…"},
  "operation_id":"op_01M610SWZMTE3HZNN9M6DC0KA9",
  "evidence":{"seq":1,"prev_digest":"sha256:…","digest":"sha256:…"},"…":"…"}}
```

Sending the same `command_id` with the same input returns the retained receipt, `"replayed": true`, and runs nothing (OP-003). The
same id with another input is refused and leaves the retained receipt alone (OP-004):

```json
{"jsonrpc":"2.0","id":6,"result":{
  "status":"rejected",
  "error":{"mhs_code":"MHS.CONFLICT.COMMAND_ID_REUSE","message":"command_id was already used with different input",
           "retryable":false,"details":{"command_id":"01J8ZQ3V6Y7M2N4P6R8S0T2V4Y"},"remediation":"Use a new ULID for a new command."},
  "…":"…"}}
```

### 1.3 A limit

A step of 20 000 ticks is outside the envelope. It is refused before the bridge is called, with the violation's path, kind,
bound, value, unit and source ([core.md](core.md) CORE-044), and the revision does not move (OP-002, SAFE-014):

```json
{"jsonrpc":"2.0","id":7,"result":{
  "status":"rejected","state_revision_before":1,"state_revision_after":1,
  "error":{"mhs_code":"MHS.SAFETY.ENVELOPE_VIOLATION","retryable":false,
           "details":{"path":"ticks","kind":"max","bound":10000,"value":20000,"source":"binding","limit_path":"ticks",
                      "violations":[{"path":"ticks","kind":"max","bound":10000,"value":20000,"source":"binding"}]},
           "remediation":"Adjust the input to the declared envelope."},
  "…":"…"}}
```

### 1.4 An interlock, and a latch the device reports itself

With the door open (the test hook `x-cap.mhs-test.set_door.v1`), a step is refused by the interlock, and an interlock that
cannot be read counts as open (SAFE-012):

```json
{"jsonrpc":"2.0","id":9,"result":{
  "status":"rejected","state_revision_before":2,"state_revision_after":2,
  "error":{"mhs_code":"MHS.SAFETY.INTERLOCK_OPEN","retryable":false,
           "interlocks":[{"id":"door_closed","state":"open"}],"remediation":"Close/clear the interlock, then reset if latched."},
  "…":"…"}}
```

Opening the door also latched the workcell itself: it reports a latch of its own through its safety status, so `latched`
is true although no e-stop was engaged ([core.md](core.md) CORE-080). A reset is refused while the interlock reads open and
completes once the door is closed again; it starts nothing:

```json
{"jsonrpc":"2.0","id":10,"result":{"capability_id":"cap.internal.safety_reset.v1","status":"rejected",
  "error":{"mhs_code":"MHS.SAFETY.RESET_REFUSED","retryable":false,"details":{"reason":"interlock_open"},
           "interlocks":[{"id":"door_closed","state":"open"}]},"…":"…"}}
```

### 1.5 A permit

`cap.actuation.valve.v1` is permit-gated. Without a permit the command is refused `MHS.SAFETY.PERMIT_INVALID`. A permit is bound
to the exact input digest, one binding and one session, expires, and is single-use (SAFE-030 to SAFE-033). The approval
principal below is a client-supplied string, so the endpoint records the approval with method `policy_rule`, not
`human_click`: an endpoint cannot infer human authority from a string (SAFE-032).

```json
{"jsonrpc":"2.0","id":11,"result":{
  "permit_id":"permit_01M610WQPGJR97A98TQN4J8BKG_882c9f7273ffff6a","capability_id":"cap.actuation.valve.v1",
  "resource":"workcell","input_digest":"sha256:ad6c…","single_use":true,"expires_at":"2026-10-20T07:47:00.000Z",
  "scope":{"device_id":"mhs://localhost:7400/lab/conveyor-workcell","principal":"…","…":"…"}}}
```

The command with `permit_id` completes; presenting the same permit again is `MHS.SAFETY.PERMIT_INVALID`.

### 1.6 E-stop and reset

The e-stop needs no session and no deadline. It latches first and its receipt is the bare receipt of
`cap.internal.safety_estop.v1` ([core.md](core.md) CORE-074, CORE-093):

```json
{"jsonrpc":"2.0","id":14,"result":{
  "capability_id":"cap.internal.safety_estop.v1","status":"completed","state_revision_before":2,"state_revision_after":3,
  "output":{"estop":"engaged","latched":true,"latency_ms":0,"latch_latency_ms":0,"safe_state_achieved":true,
            "safe_state":{"description":"Conveyor stopped, diverter gate in main position, no parts moving",
                          "achieved_by":["cap.motion.stop.v1"]},"cancelled_operations":[]},
  "effects":[{"kind":"safety.estop","summary":"emergency stop engaged","reversible":false,"severity":"R0"}],"…":"…"}}
```

While latched every effectful command is refused before the schema is read (CORE-075), and the revision stays put; a reset
releases the latch, clears nothing but the latch and starts nothing (SAFE-042); a second reset has nothing to release (SAFE-043):

```json
{"jsonrpc":"2.0","id":15,"result":{"status":"rejected","error":{"mhs_code":"MHS.SAFETY.ESTOP_ENGAGED","retryable":false,
  "remediation":"Reset after clearing interlocks; issue a new start command."},"state_revision_before":2,"state_revision_after":2,"…":"…"}}
{"jsonrpc":"2.0","id":16,"result":{"capability_id":"cap.internal.safety_reset.v1","status":"completed",
  "output":{"reset":true,"estop":"released","latched":false,"cleared_interlocks":["door_closed"],"resumed":false},"…":"…"}}
{"jsonrpc":"2.0","id":17,"result":{"status":"rejected","error":{"mhs_code":"MHS.SAFETY.RESET_REFUSED","retryable":false,
  "details":{"reason":"not_latched"}},"…":"…"}}
```

```python
# runnable
import warnings

warnings.simplefilter("ignore")

from mhs import canonical
from mhs.reference import build_endpoint, build_server
from mhs.testing import client_for

server = build_server(build_endpoint("conveyor", endpoint_id="mhs://localhost:7400", test_profile=True), log_ready=False)
client = client_for(server)
hello = client.hello()
assert hello["spec_version"] == "0.9" and hello["conformance"][0]["level"] == "CL4"
assert "MHS.SAFETY.NOT_CERTIFIED" in hello["features"]
device = hello["devices"][0]["device_id"]
session = client.open_session(device_ids=[device], capabilities=["cap.world.*", "cap.actuation.valve.v1", "cap.motion.*",
                                                                 "x-cap.mhs-test.set_door.v1"])["session_id"]


def invoke(capability, payload, **options):
    return client.invoke(capability, payload, device_id=device, session_id=session, **options)


# 1.2 command, replay, reuse
command_id = canonical.ulid()
first = invoke("cap.world.step.v1", {"ticks": 10}, command_id=command_id)
assert first["status"] == "completed" and first["state_revision_after"] == first["state_revision_before"] + 1
assert first["replayed"] is False and "receipt" not in first          # the result is the bare receipt
again = invoke("cap.world.step.v1", {"ticks": 10}, command_id=command_id)
assert again["replayed"] is True and again["receipt_id"] == first["receipt_id"]
reused = invoke("cap.world.step.v1", {"ticks": 11}, command_id=command_id)
assert reused["status"] == "rejected" and reused["error"]["mhs_code"] == "MHS.CONFLICT.COMMAND_ID_REUSE"

# 1.3 a limit: checked before the schema, zero effect
over = invoke("cap.world.step.v1", {"ticks": 20000})
assert over["error"]["mhs_code"] == "MHS.SAFETY.ENVELOPE_VIOLATION"
assert over["error"]["details"]["path"] == "ticks" and over["error"]["details"]["bound"] == 10000
assert over["state_revision_after"] == over["state_revision_before"]

# 1.4 an interlock, and a latch the device reports itself
assert invoke("x-cap.mhs-test.set_door.v1", {"state": "open"})["status"] == "completed"
blocked = invoke("cap.world.step.v1", {"ticks": 1})
assert blocked["error"]["mhs_code"] == "MHS.SAFETY.INTERLOCK_OPEN"
assert blocked["state_revision_after"] == blocked["state_revision_before"]
refused = client.reset(device_id=device, session_id=session)
assert refused["error"]["mhs_code"] == "MHS.SAFETY.RESET_REFUSED" and refused["error"]["details"]["reason"] == "interlock_open"
assert invoke("x-cap.mhs-test.set_door.v1", {"state": "closed"})["status"] == "completed"
assert client.reset(device_id=device, session_id=session)["status"] == "completed"
assert invoke("cap.world.step.v1", {"ticks": 1})["status"] == "completed"

# 1.5 a permit: bound to the input, single-use
assert invoke("cap.actuation.valve.v1", {"gate": "divert"})["error"]["mhs_code"] == "MHS.SAFETY.PERMIT_INVALID"
approval = {"principal": "human:alice", "method": "human_click", "approved_at": "2026-10-20T07:46:00Z",
            "evidence_ref": "ui://approval/1"}
permit = client.permit("cap.actuation.valve.v1", {"gate": "divert"}, device_id=device, session_id=session,
                       approvals=[approval])
assert permit["single_use"] is True
assert invoke("cap.actuation.valve.v1", {"gate": "divert"}, permit_id=permit["permit_id"])["status"] == "completed"
assert invoke("cap.actuation.valve.v1", {"gate": "divert"},
              permit_id=permit["permit_id"])["error"]["mhs_code"] == "MHS.SAFETY.PERMIT_INVALID"

# 1.6 e-stop latches first; reset releases it and resumes nothing
stop = client.estop("lid lifted", device_id=device, session_id=session)
assert stop["status"] == "completed" and stop["output"]["latched"] is True and stop["output"]["safe_state_achieved"] is True
latched = invoke("cap.world.step.v1", {"ticks": 1})
assert latched["error"]["mhs_code"] == "MHS.SAFETY.ESTOP_ENGAGED"
assert latched["state_revision_after"] == latched["state_revision_before"]
released = client.reset(device_id=device, session_id=session)
assert released["status"] == "completed" and released["output"]["resumed"] is False
nothing = client.reset(device_id=device, session_id=session)
assert nothing["error"]["mhs_code"] == "MHS.SAFETY.RESET_REFUSED" and nothing["error"]["details"]["reason"] == "not_latched"
server.close()
```

### 1.7 Evidence export and offline verification

Every receipt, the rejected ones included, is appended to the endpoint's hash chain before it is returned (EVID-010, EVID-012).
`mhs.evidence.export` returns the chain and `verify` recomputes it offline; one changed byte in one receipt breaks it at the
first affected `seq` (EVID-016):

```json
{"bundle_version":"1.0.0","endpoint_info":{"endpoint_id":"mhs://localhost:7400","genesis_digest":"sha256:…"},
 "receipts":[{"receipt_id":"01M6…","status":"completed","evidence":{"seq":1,"prev_digest":"sha256:…","digest":"sha256:…"},"…":"…"},
             {"…":"one receipt per command, in evidence order"}],
 "head_digest":"sha256:7d64…","count":8,"truncation":null,"signature":null}
```

```json
{"valid":true,"checked":8,"head_digest":"sha256:7d64…","errors":[],"signature":"absent","schema":"validated"}
{"valid":false,"checked":8,"errors":[{"seq":3,"mhs_code":"MHS.EVIDENCE.CHAIN_BROKEN","detail":"digest mismatch (recomputed …)"}]}
```

### 1.8 A conformance report

The same reference endpoint, run in process by the suite, achieves CL4 for the profile `MHS-Sim`; the report carries
`disclaimers` (`not_certified`, `not_affiliated`, `simulation_only`, `self_issued`) and is valid against
[`conformance-report.schema.json`](../schema/conformance-report.schema.json). [MHS-001](01-conformance.md) §7.1 shows a
complete report. The level is a behavioural test result, not a safety certification.

```python
# runnable
import copy
import warnings

warnings.simplefilter("ignore")

from mhs.conformance import validate_report
from mhs.conformance.inprocess import reference_factory, run_suite_inprocess
from mhs.evidence import verify_bundle
from mhs.reference import build_endpoint, build_server
from mhs.testing import client_for

# 1.7 evidence: the chain verifies, and one changed receipt breaks it at its seq
server = build_server(build_endpoint("conveyor", endpoint_id="mhs://localhost:7400", test_profile=True), log_ready=False)
client = client_for(server)
device = client.hello()["devices"][0]["device_id"]
session = client.open_session(device_ids=[device])["session_id"]
for ticks in (3, 4, 20000):                                    # two completions and one rejection: all are chained
    client.invoke("cap.world.step.v1", {"ticks": ticks}, device_id=device, session_id=session)
bundle = client.export_evidence()
assert verify_bundle(bundle)["valid"] is True
statuses = [receipt["status"] for receipt in bundle["receipts"]]
assert statuses == ["completed", "completed", "rejected"]
tampered = copy.deepcopy(bundle)
tampered["receipts"][1]["status"] = "failed"
broken = verify_bundle(tampered)
assert broken["valid"] is False and broken["errors"][0]["mhs_code"] == "MHS.EVIDENCE.CHAIN_BROKEN"
assert broken["errors"][0]["seq"] == 2
server.close()

# 1.8 the suite, in process, against fresh reference endpoints
report = run_suite_inprocess(reference_factory("conveyor"), profile="MHS-Sim", level="CL4")
assert validate_report(report) == []
assert report["level_achieved"] == "CL4"
assert {item["id"] for item in report["disclaimers"]} >= {"not_certified", "self_issued"}
```

---

## 2. A lab of three devices driven by one code file

**Subject.** The reference `lab` endpoint (`python3 -m mhs serve lab --port 7401`): three simulated devices,
`liquid-handler`, `sample-mover` and `plate-reader`, one session each, opened by `mhs.run.lab` in the device's own mode. A code
file chains commands across devices and has no more authority than the same calls made one by one ([core.md](core.md) CORE-140).
With `check=True`, the default, the first receipt that is not `completed` raises `MHSRejected`, so the file stops at the
first refusal instead of carrying on. Composition (`mhs.composition.run`) is reserved in 0.9 ([profiles.md](profiles.md) §1);
a code file is the way to run a procedure across devices.

```python
# assay.py, run as `python3 -m mhs run assay.py http://127.0.0.1:7401`
from mhs.run import lab

PLATE = "plate-001"


def assay(bench, volume_ul=50):
    bench["liquid-handler"].invoke("cap.fluid.transfer.v1",
                                   {"source_well": "A1", "destination_well": "B1", "volume_ul": volume_ul})
    bench["sample-mover"].invoke("cap.sample.move.v1", {"plate_id": PLATE, "to": "reader"})
    return bench["plate-reader"].invoke("cap.measure.spectrum.v1", {"plate_id": PLATE, "wavelengths_nm": [562]})
```

The run leaves a ledger, `.mhs-run/<run id>.json`, listing every receipt; checking it against the endpoint's own evidence
fails when a receipt is missing or differs ([core.md](core.md) CORE-141):

```json
{"ledger_version":1,"run_id":"01M610XD75NF8Z6PKMK4C9D3VG","script":"assay.py","outcome":"completed",
 "endpoints":[{"endpoint_id":"mhs://localhost:7401","transport":"inprocess"}],
 "receipts":[{"receipt_id":"01M6…","device_id":"mhs://localhost:7401/lab/liquid-handler","capability_id":"cap.fluid.transfer.v1","status":"completed"},
             {"…":"…"}],"lost":[],"…":"…"}
```

```python
# runnable
import pathlib
import tempfile
import warnings

warnings.simplefilter("ignore")

from mhs.reference import build_endpoint, build_server
from mhs.run import lab, verify_ledger
from mhs.testing import client_for

server = build_server(build_endpoint("lab", endpoint_id="mhs://localhost:7401", test_profile=False), log_ready=False)
with tempfile.TemporaryDirectory() as directory:
    with lab(server, ledger=directory) as bench:
        bench["liquid-handler"].invoke("cap.fluid.transfer.v1",
                                       {"source_well": "A1", "destination_well": "B1", "volume_ul": 50})
        bench["sample-mover"].invoke("cap.sample.move.v1", {"plate_id": "plate-001", "to": "reader"})
        spectrum = bench["plate-reader"].invoke("cap.measure.spectrum.v1",
                                                {"plate_id": "plate-001", "wavelengths_nm": [562]})
        assert spectrum["status"] == "completed" and len(bench.receipts) == 3
    (ledger,) = pathlib.Path(directory).glob("*.json")
    checked = verify_ledger(ledger, client_for(server).export_evidence())
    assert checked["valid"] is True and checked["checked"] == 3
server.close()
```

---

## 3. A simulated arm: fidelity contract, determinism, snapshots and replay

**Subject.** The reference `arm` endpoint: a planar two-joint arm, mode `simulated`, fidelity F0, `determinism.kind` `exact`, with
`snapshot_restore` true and honest gaps (no dynamics, inertia, gravity or contact). Nothing may present it as the physical arm it
models (FID-045, FID-049). An excerpt of what `mhs.devices.get` returns:

```json
{"device_id":"mhs://localhost:7402/robot/arm-2dof","mode":"simulated",
 "fidelity":{"engine":"analytic","fidelity_level":"F0","determinism":{"kind":"exact","seed_control":"none"},
             "timestep_ms":0,"realtime_factor":0,"reset":"full","snapshot_restore":true,
             "gaps":["Planar 2-DOF rigid-link kinematics only: no dynamics, inertia, gravity or contact","…"]}}
```

A fresh arm given the same command reaches the same state hash on every run, which is what makes the replay test of FID-025
possible. A joint outside its travel is refused as a limit, before the bridge:

```json
{"status":"rejected","error":{"mhs_code":"MHS.SAFETY.ENVELOPE_VIOLATION","details":{"path":"joint_positions_deg[1]",
 "kind":"max","bound":135,"value":200,"unit":"deg","source":"binding","limit_path":"joint_positions_deg"}},"…":"…"}
```

A recording of a live endpoint can be served read-only. The replay endpoint reports mode `replay`, advertises `replay.seek`, serves
the recorded state for a revision, and refuses every command with `MHS.MODE.READ_ONLY` (MODE-005, FID-024):

```json
{"status":"rejected","mode":"replay","error":{"mhs_code":"MHS.MODE.READ_ONLY","retryable":false,"…":"…"},"…":"…"}
```

```python
# runnable
import json
import pathlib
import tempfile
import warnings

warnings.simplefilter("ignore")

from mhs import connect
from mhs.reference import build_endpoint, build_server
from mhs.reference.replay import build as build_replay, build_replay_bundle
from mhs.testing import client_for


def fresh_arm():
    server = build_server(build_endpoint("arm", endpoint_id="mhs://localhost:7402"), log_ready=False)
    client = client_for(server)
    device = client.hello()["devices"][0]["device_id"]
    return server, client, device, client.open_session(device_ids=[device])["session_id"]


hashes = []
for _ in range(2):                                              # determinism: same command, same state hash
    server, client, device, session = fresh_arm()
    receipt = client.invoke("cap.motion.joint_position.v1", {"joint_positions_deg": [30, -45]},
                            device_id=device, session_id=session)
    assert receipt["status"] == "completed"
    hashes.append(receipt["state_hash_after"])
    server.close()
assert hashes[0] == hashes[1]

server, client, device, session = fresh_arm()
manifest = client.request("mhs.devices.get", {"device_id": device})
assert manifest["mode"] == "simulated" and manifest["fidelity"]["fidelity_level"] == "F0"
assert manifest["fidelity"]["determinism"]["kind"] == "exact" and manifest["fidelity"]["gaps"]
over = client.invoke("cap.motion.joint_position.v1", {"joint_positions_deg": [30, 200]}, device_id=device, session_id=session)
assert over["error"]["mhs_code"] == "MHS.SAFETY.ENVELOPE_VIOLATION" and over["error"]["details"]["path"] == "joint_positions_deg[1]"
snapshot = client.snapshot(device_id=device, session_id=session)       # snapshot, move, restore
client.invoke("cap.motion.joint_position.v1", {"joint_positions_deg": [10, 10]}, device_id=device, session_id=session)
restored = client.restore(snapshot, device_id=device, session_id=session)
assert restored["status"] == "completed" and restored["state_hash_after"] == snapshot["state_hash"]
server.close()

# replay: record a live conveyor, then serve the recording read-only
live = build_server(build_endpoint("conveyor", endpoint_id="mhs://localhost:7400", test_profile=True), log_ready=False)
handle = live.start_http("127.0.0.1", 0)
recorder = connect(handle.url)
bundle = build_replay_bundle(recorder, commands=[{"capability_id": "cap.world.step.v1", "input": {"ticks": 5}}])
recorder.close()
handle.shutdown()
live.close()
with tempfile.TemporaryDirectory() as directory:
    path = pathlib.Path(directory) / "bundle.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")
    replay = build_server(build_replay("mhs://replay.local:7400", bundle_path=path), log_ready=False)
    viewer = client_for(replay)
    assert "replay.seek" in viewer.hello()["features"]
    recorded = viewer.hello()["devices"][0]["device_id"]
    replay_session = viewer.open_session(device_ids=[recorded], mode="replay")["session_id"]
    refused = viewer.invoke("cap.world.step.v1", {"ticks": 1}, device_id=recorded, session_id=replay_session)
    assert refused["status"] == "rejected" and refused["error"]["mhs_code"] == "MHS.MODE.READ_ONLY"
    replay.close()
```

---

## 4. A hybrid digital twin: declared authority

**Subject.** A device whose mode is `hybrid`: a twin that follows a real arm. It must declare, for each of its resources, which side is
truth, in `fidelity.authority` (MODE-006, FID-030). Without it the manifest fails validation and the endpoint does not start. This
excerpt of its manifest is abridged and is not run:

```json
{"device_id":"mhs://lab.example/twin/arm-7","mode":"hybrid","models":["mhs://lab.example/robot/arm-7"],
 "resources":[{"resource_id":"hardware_arm","kind":"robot.arm"},{"resource_id":"model_arm","kind":"robot.arm"}],
 "fidelity":{"engine":"mujoco","fidelity_level":"F2","determinism":{"kind":"seeded","seed_control":"parameter"},
             "authority":{"hardware_arm":"hardware","model_arm":"model"},
             "gaps":["Model friction is fitted on three trajectories only"],"…":"…"}}
```

A command that would move the hardware through the model is refused with `MHS.SAFETY.ENVELOPE_VIOLATION`
(`details.authority` `hardware`), and only a catalogued read class may touch a hardware-authority resource ([core.md](core.md)
CORE-112). The hardware envelope and interlocks apply to every command of a hybrid device (FID-034), and the device keeps
`mode: "hybrid"` even when one side is unavailable (FID-033).

---

## 5. An MCP projection session

**Subject.** `mhs.mcp` in front of the tutorial thermostat driver (`python3 -m mhs serve MHS/sdk/examples/thermostat --mcp`; in the
block below the projection is driven in process). The host policy is the default of a direct launch: enabled, no hardware, no
operator tools, no external sessions ([core.md](core.md) CORE-130).

`tools/list` shows the fixed discovery and safety tools and one tool per binding; `mhs__reset` and `mhs__permit` are not listed:

```json
{"jsonrpc":"2.0","id":2,"result":{"tools":[
  {"name":"mhs__devices"},{"name":"mhs__inspect"},{"name":"mhs__read"},{"name":"mhs__safety"},
  {"name":"mhs__operations"},{"name":"mhs__evidence"},{"name":"mhs__estop"},
  {"name":"mhs__tutorial_thermostat_fake__thermal_setpoint",
   "description":"… Mode: simulated. Risk R2. Enforced limits: … Interlocks: lid_closed …",
   "annotations":{"readOnlyHint":false,"destructiveHint":true,"idempotentHint":true,"openWorldHint":false},
   "inputSchema":{"type":"object","properties":{"target_temperature":{"type":"number"},"session_id":{"type":"string"},"…":"…"}}},
  {"…":"…"}]}}
```

A call is exactly one `mhs.command`. A refusal by the endpoint is an outcome, not a tool malfunction: it comes back as a successful
tool call whose `structuredContent.receipt` is the `rejected` receipt. Only input that does not match the schema, a policy refusal
or a lapsed session is `isError: true`, and nothing is sent in the first case ([MHS-008](08-transports.md) TPT-038):

```json
{"jsonrpc":"2.0","id":4,"result":{"isError":false,
  "content":[{"type":"text","text":"MHS cap.thermal.setpoint.v1 rejected … (receipt …)\n{…the complete receipt…}"}],
  "structuredContent":{"receipt":{"status":"rejected","error":{"mhs_code":"MHS.SAFETY.ENVELOPE_VIOLATION","…":"…"},"…":"…"},"mhs_error":{"…":"…"}}}}
{"jsonrpc":"2.0","id":5,"result":{"isError":true,
  "content":[{"type":"text","text":"MHS.CAPABILITY.INPUT_INVALID: $.target_temperature: expected number, got string (nothing was sent to the device; …)"}]}}
```

```python
# runnable
import warnings

warnings.simplefilter("ignore")

from mhs.adapter import load
from mhs.mcp import MCPProjection
from mhs.testing import client_for

server = load("MHS/sdk/examples/thermostat", backend="fake")
projection = MCPProjection(client_for(server))
counter = [0]


def call(method, params=None):
    counter[0] += 1
    message = {"jsonrpc": "2.0", "id": counter[0], "method": method}
    if params is not None:
        message["params"] = params
    return projection.handle_message(message)


init = call("initialize", {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "demo-host", "version": "1.0"}})
assert init["result"]["protocolVersion"] == "2025-06-18" and init["result"]["serverInfo"]["name"].startswith("mhs-mcp")
projection.handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"})
tools = {tool["name"]: tool for tool in call("tools/list")["result"]["tools"]}
assert {"mhs__devices", "mhs__estop", "mhs__evidence"} <= set(tools)
assert "mhs__reset" not in tools and "mhs__permit" not in tools          # operator tools are hidden by default
setpoint = next(name for name in tools if name.endswith("thermal_setpoint"))
assert len(tools[setpoint]["description"].encode()) <= 2048

done = call("tools/call", {"name": setpoint, "arguments": {"target_temperature": 30}})["result"]
assert done["isError"] is False and done["structuredContent"]["receipt"]["status"] == "completed"
refused = call("tools/call", {"name": setpoint, "arguments": {"target_temperature": 400}})["result"]
assert refused["isError"] is False                                         # a rejected receipt is not a tool error
assert refused["structuredContent"]["receipt"]["error"]["mhs_code"] == "MHS.SAFETY.ENVELOPE_VIOLATION"
invalid = call("tools/call", {"name": setpoint, "arguments": {"target_temperature": "hot"}})["result"]
assert invalid["isError"] is True and invalid["content"][0]["text"].startswith("MHS.CAPABILITY.INPUT_INVALID")
hidden = call("tools/call", {"name": "mhs__reset", "arguments": {}})["result"]
assert hidden["isError"] is True and "MHS.AUTH.FORBIDDEN" in hidden["content"][0]["text"]
server.close()
```

---

## 6. What the examples demonstrate

| Property | Example | Requirements |
|---|---|---|
| Receipts are the result; bare, with revisions and evidence links | 1.2, 1.7 | PROTO-029, PROTO-036, OP-001, OP-007, EVID-010 |
| Idempotency and reuse of a `command_id` | 1.2 | OP-003, OP-004, OP-005 |
| Limits are checked first, element by element, and refuse with details | 1.3, 3 | SAFE-014, [core.md](core.md) CORE-044 |
| Interlocks fail closed; a device-reported latch needs a reset | 1.4 | SAFE-011, SAFE-012, SAFE-041, [core.md](core.md) CORE-080 |
| Permits are single-use and bound to the input | 1.5 | SAFE-030 to SAFE-033 |
| The e-stop latches first, refuses effectful commands, and a reset starts nothing | 1.6 | SAFE-040 to SAFE-043, [core.md](core.md) CORE-074 to CORE-082 |
| Rejected receipts are chained; a tampered chain fails offline | 1.7 | EVID-010, EVID-012, EVID-016 |
| A behavioural level with its disclaimers | 1.8 | CON-002, SAFE-052 |
| Several devices, one code path, a verifiable ledger | 2 | [core.md](core.md) CORE-140, CORE-141 |
| Fidelity contract, determinism, snapshots, read-only replay | 3 | FID-001, FID-025, MODE-005, PROTO-034 |
| Declared authority of a hybrid twin | 4 | MODE-006, FID-030, FID-031, FID-034 |
| An MCP session: operator tools hidden, a refusal is not a tool error | 5 | TPT-038, TPT-044, [core.md](core.md) CORE-130 |

None of these results is a safety certification. They show how the contract behaves; the hardware e-stop, the safety system and
the operator's judgement remain independent (SAFE-005, SAFE-046).
