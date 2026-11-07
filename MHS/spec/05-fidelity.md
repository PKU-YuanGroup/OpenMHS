# MHS-005 — Modes, Fidelity Contract, Determinism and Replay

| Field | Value |
|---|---|
| Document | MHS-005 (normative) |
| Status | OpenMHS 0.9 development draft |
| Editor | The OpenMHS Authors |
| Layer | optional profile: Sim, Fidelity and Replay (MODE-001 to MODE-004 apply to every device) ([profiles.md](profiles.md) §2) |
| Normative base | [core.md](core.md) §8; overview in [00-architecture.md](00-architecture.md) §7 (informative) |
| Data contracts | [`device.schema.json`](../schema/device.schema.json) `mode`, `fidelity`, `models`; [`defs.schema.json`](../schema/defs.schema.json) `mode`, `determinism` |

MHS treats simulation and hardware as the same contract with two declared worlds.
This document defines the mode system, the fidelity contract, determinism claims,
the replay protocol, hybrid authority, validation methodology, gap disclosure and
identity separation. It details [core.md](core.md) §8 and MUST NOT
contradict it.

The key words MUST, MUST NOT, REQUIRED, SHOULD, SHOULD NOT, MAY and OPTIONAL are
to be interpreted as described in RFC 2119 and RFC 8174.

---

## 1. The dual-world rule

**MODE-001.** There is exactly one object model, one wire protocol and one
capability vocabulary for physical and simulated devices. The only permitted
differences are the declared `mode` and, for simulated/hybrid devices, the
fidelity contract. Nothing in the protocol may branch on "sim vs real"
([00-architecture.md](00-architecture.md) A1, informative). Tools, clients and hosts use the same code
path; a host that special-cases simulators in its control flow is non-conformant.

**MODE-002.** `mode` MUST be declared in the device manifest, requested again in
every `session.open`, returned in every session grant and receipt, and MUST equal
one of `hardware`, `simulated`, `hybrid`, `replay`
([`defs.schema.json`](../schema/defs.schema.json) `mode`). A session requesting a
mode other than the device's declared mode MUST be rejected with
`MHS.SESSION.MODE_MISMATCH`; a mismatch is never resolved by falling back.

**MODE-003.** A device MUST NOT change its declared mode at runtime. Switching
from a simulator to hardware is a different endpoint and a different device, not a
flag on an existing session. An endpoint that reloads its manifest MAY change a
device's mode, and hosts MUST treat that as a new device instance with a new
`instance_id`.

**MODE-004.** `mhs.hello`, `devices.get`, `safety.status` and every receipt MUST
report `mode`; a host MUST display it next to any command affordance and MUST
refuse to present a simulated device as hardware. The generated device profile
MUST carry the mode in `profile.operating_notes`.

**MODE-005.** In `replay` mode, all mutations MUST be rejected with
`MHS.MODE.READ_ONLY`. Permitted operations are reads, `world.state`, snapshots of
the recorded state, subscription to recorded streams, and seeking by revision or
timestamp. A replay endpoint MUST serve the recorded state for a revision, not
recompute it.

**MODE-006.** A `hybrid` device MUST declare, per resource, which side is truth
(`fidelity.authority`, §6). Without an authority declaration a hybrid device MUST
fail manifest validation.

---

## 2. The fidelity contract

### 2.1 Required shape

For `mode ∈ {simulated, hybrid}` the manifest MUST carry a `fidelity` object
([`device.schema.json`](../schema/device.schema.json)); for `mode: "hardware"` the
field MUST be absent.

| Field | Required for | Meaning |
|---|---|---|
| `engine` | sim/hybrid | Engine or model family: `mujoco`, `pybullet`, `gazebo`, `isaac`, `webots`, `unity`, `drake`, `genesis`, `analytic`, `custom`, or a more specific string. |
| `fidelity_level` | sim/hybrid | `F0`–`F3` (§2.3). |
| `determinism{kind, seed_control?, notes?}` | sim/hybrid | `exact | seeded | statistical | none` (§3). |
| `timestep_ms` | sim/hybrid | Fixed physics/step interval; `0` only for event-driven analytic models, with a note. |
| `realtime_factor` | sim/hybrid | Simulated seconds per wall-clock second at nominal load; `0` means "not paced". |
| `clock` | optional | Who advances simulated time: `lockstep` (only commands advance it; the Gymnasium and MuJoCo family drivers declare this), `free_running` (the simulator runs on its own clock) or `external` (an outside scheduler). It does not imply wall-clock pacing (FID-013, FID-014). |
| `reset` | sim/hybrid | `full | partial | none`. |
| `snapshot_restore` | sim/hybrid | Whether `mhs.snapshot`/`mhs.restore` are supported. |
| `authority` | hybrid | Object mapping resource id to `hardware | model` (§6). |
| `validation` | F3 (and SHOULD for F2) | `against_device`, `metrics`, `evidence_ref`, `validated_at` (§7). |
| `gaps` | sim/hybrid when non-empty | Array of strings; REQUIRED when the model has known omissions (§8). |

**FID-001.** A simulated or hybrid device without a valid fidelity contract MUST
fail schema validation and MUST NOT be claimed above CL0. A hardware device with
a `fidelity` block MUST fail validation
([`device.schema.json`](../schema/device.schema.json) `allOf` rules).

**FID-002.** The contract MUST describe the *model as deployed*, not the engine's
generic capabilities. "MuJoCo" is an engine, not a fidelity claim; the claim is
the level, the timestep, the determinism kind, the gaps and (for F3) the
validation record.

**FID-003.** `fidelity` MUST be immutable for the lifetime of a `device_id` +
`instance_id` pair. Changing the model, timestep or gaps requires a new
`instance_id` and a new conformance report; a changed contract under a stable
identity invalidates every prior replay claim.

**FID-004.** A bridge that cannot determine a required fidelity field MUST refuse
to serve the device rather than invent one (`MHS.FIDELITY.CONTRACT_REQUIRED`).

### 2.2 Where the contract is exposed

**FID-005.** The fidelity contract MUST be returned by `devices.get` and
`hello.devices[*]` (at least the level, engine, determinism kind and gaps count),
MUST be available to the model in the generated profile, and MUST be repeated in
`session.open`'s `safety_context` or a sibling `fidelity_context` when the device
is simulated or hybrid.

### 2.3 Fidelity levels

| Level | Claim | Requirements |
|---|---|---|
| **F0** | Kinematic/analytic. No dynamics: positions, durations and state transitions are modelled directly. | `engine` and `timestep_ms` declared; no claim about forces or contacts; `gaps` MUST mention absence of dynamics. |
| **F1** | Rigid-body dynamics with contacts. | F0 requirements plus a declared physics engine, timestep, and at least one gap about contact or actuator fidelity. Validation not required. |
| **F2** | Actuator, sensor and noise dynamics modelled. | F1 requirements plus declared actuator model, sensor model and noise model in `gaps`/notes; determinism kind declared. |
| **F3** | Validated against the referenced physical device with reported metrics. | F2 requirements plus `validation` with `against_device`, `metrics`, `evidence_ref`, `validated_at`; re-validation triggers in §7. |

**FID-006.** An F3 claim without a `validation` record that names the physical
device and reports at least one quantitative metric (for example pose RMSE,
volume error, temperature tracking error) MUST be treated as F2 and MUST fail the
FID-030 test. A vendor MUST NOT claim F3 because the engine is "high-fidelity".

**FID-007.** Fidelity levels are ordinal but not linear: an F1 model can be more
useful than an F3 model for a task the F3 model does not cover. The level is a
claim about *what was modelled and validated*, and `gaps` qualify it. An agent MUST
read `gaps` and MUST NOT treat F3 as "correct for my experiment".

---

## 3. Determinism claims

### 3.1 Kinds

| `determinism.kind` | Meaning | Host may assume |
|---|---|---|
| `exact` | Same initial state + same command sequence ⇒ bit-identical state hashes, with no hidden randomness or timing dependence. | Replay equality (§5). Required for CL4 replay claims on simulated devices. |
| `seeded` | Same seed + same command sequence ⇒ identical state hashes, **provided** the documented seed control is used. | Replay equality when the seed is recorded and replayed. |
| `statistical` | Results vary run to run within a declared distribution. | Only distributional claims; no hash equality. |
| `none` | No determinism claim. | No replay equality; evidence is a record, not a replicable experiment. |

**FID-008.** `seed_control` MUST be declared for `seeded`:
`parameter` (a seed can be set at any time),
`reset_required` (the seed must be supplied on reset), or `none`. For
`reset_required` the endpoint MUST return `MHS.FIDELITY.SEED_REQUIRED` when
`world.reset` is called without a seed if the device claims deterministic replay.

**FID-009.** `determinism.kind = exact` MUST NOT be claimed by a device that runs
wall-clock-paced physics, uses unordered iteration over floating-point state, or
draws from an unseeded RNG. It SHOULD be supported by a test that steps the same
sequence twice and compares hashes (`FID-025`).

**FID-010.** A `simulated` or `hybrid` manifest with no `fidelity.determinism.kind`
MUST fail validation; a device claiming CL4 replay with `kind` other than `exact`
or `seeded` MUST fail `FID-025` by definition (no equality claim is possible).

### 3.2 Seeds in receipts

**FID-011.** When a receipt's outcome depends on a seed, the receipt MUST carry
`seed`. A reset or a seeded step whose receipt lacks `seed` is non-conformant for
`seeded` determinism.

**FID-012.** The seed MUST be echoed by `cap.world.seed.v1` / `cap.world.reset.v1`
in their output, and MUST be recorded even when the caller did not supply one (the
endpoint's default seed is then reported).

### 3.3 Realtime factor and timing

**FID-013.** `realtime_factor` MUST be reported and hosts MUST NOT assume that one
simulated second takes one wall-clock second. `realtime_factor: 0` means the
simulation is not wall-clock paced (as fast as possible or externally driven).

**FID-014.** A simulated device MUST NOT be used to reason about wall-clock timing
or control-loop latency unless `realtime_factor > 0` and the manifest notes say
the model includes timing. `gaps` MUST state "no wall-clock pacing" when it does
not.

**FID-015.** `timestep_ms` defines the unit of `cap.world.step.v1`'s `ticks` input;
a receipt MUST report `ticks` and the endpoint MUST compute the simulated duration
as `ticks × timestep_ms` and MUST expose it in the step receipt output or notes. When
the native model separates the physics timestep from the control period (decimation,
`control_freq`/`model_timestep`, `control_decimation`), the adapter MUST declare both
numbers in the device profile `operating_notes` and in the binding notes, and
`timestep_ms` MUST name the physics timestep; a client that needs the control period
reads the notes. OpenMHS 0.9 does not add a second mandatory fidelity field, because the
fidelity object is closed ([`device.schema.json`](../schema/device.schema.json)).

The reference SDK's opt-in `physics_ticks_v1` implementation places its binding
and receipt timing notes in `x-vendor.openmhs_simulation_timing`, using the
existing extension object. Its receipt `progress.ticks` reports verified
completed physics ticks for that command, distinct from the requested count and
the episode's accumulated tick. After an unresolved call or accounting failure,
the notes distinguish that lower bound from an unknown exact count/duration;
they do not substitute zero or requested duration for unobserved work. A final
receipt can reconcile an earlier unresolved receipt. Existing
`x-vendor.duration_ms` remains elapsed wall-clock time. This SDK convention adds
no field to the closed fidelity or stable step-output schemas and does not
assert that unconfigured backends implement physics-tick accounting.

---

## 4. Determinism testing

**FID-016.** A determinism test MUST: (a) obtain a fresh or reset world,
(b) set/record the seed, (c) apply a fixed command sequence, (d) record
`state_hash` after every mutation, (e) repeat from the same start, and (f) compare
the hash sequences for exact equality.

**FID-017.** The test MUST run the sequence at least twice and MUST report the
seed, the command sequence digest, the compared revisions and the first
divergence (if any). A divergence is a failure, not a warning, for
`kind ∈ {exact, seeded}`.

**FID-018.** The test MUST also verify that nondeterminism is *not* introduced by
the transport or session lifecycle: a reconnect or a second session MUST produce
the same sequence from the same seed.

**FID-019.** For `statistical` determinism the suite MUST run the sequence N ≥ 5
times and report the distribution (min/max/mean of the observed metric); it MUST
NOT report hash equality.

**FID-020.** The suite MUST record the determinism test transcript as an artifact
and reference it from the CL4 report; a CL4 sim claim without a transcript is
incomplete ([MHS-001](01-conformance.md) §5.1).

---

## 5. Replay

### 5.1 What replay is

A replay endpoint serves a recorded session or evidence bundle as a read-only MHS
device. It makes the experiment reproducible as an *artifact*, not by re-running
the simulator: the recorded states and receipts are the evidence, and the replay
endpoint answers reads and snapshots with those recorded values.

### 5.2 Recording requirements

**FID-021.** A recording is an evidence bundle ([MHS-004](04-safety.md) §8) plus
the per-revision state documents needed to serve `mhs.resource.read` at each
recorded revision. The recording MUST include: the device manifest digest, the
fidelity contract, the seed(s), the command sequence (receipts with inputs), and
the `state_hash` sequence.

**FID-022.** A replay endpoint's device manifest MUST have `mode: "replay"`, a
distinct `device_id`/`instance_id` from the source device, `models: [source
device_id]`, and `provenance` naming the recording bundle digest.

**FID-023.** A replay device MAY declare `fidelity` inherited from the recording;
it MUST NOT claim a higher fidelity level than the recording. `snapshot_restore`
MUST be true for seeking; `reset` MUST be `partial` (seek to recorded start) or
`none`.

### 5.3 Replay protocol

**FID-024.** The replay endpoint MUST support, at minimum:
`hello` (advertising `replay.seek`), `devices.get`, `resource.read` (with
`filter.revision` for seeking), `resource.write` → `MHS.MODE.READ_ONLY`,
`command` → `MHS.MODE.READ_ONLY`, `snapshot`, `restore` → `MHS.MODE.READ_ONLY`,
`subscribe` for recorded streams (finite, ending with a control event
`{"type":"replay_end"}`), `evidence.export` of the recording, and
`resource.read` of the recorded state at the recorded revisions.

Seeking is a read: `mhs.resource.read` with `fields` may be accompanied by a
replay-specific `revision` in `filter`; an out-of-range revision MUST return
`MHS.RESOURCE.UNKNOWN` with the recorded range. (The filter extension is declared
in the replay endpoint's `hello.features` as `replay.seek`.)

**FID-025.** A replay verification test MUST execute the recorded command sequence
against the recorded start state and compare `state_hash` at every recorded
revision. For `determinism.kind ∈ {exact, seeded}` the comparison MUST be exact
and a single mismatch MUST fail the test (`MHS.FIDELITY.REPLAY_DIVERGENCE`). For
other kinds the test MUST report divergence as expected and MUST NOT claim
replay verification.

**FID-026.** Replay MUST NOT execute physical effects. A replay endpoint MUST NOT
be connectable to hardware, and its adapter MUST declare that it launches no
device drivers (`runtime.kind` process/local only).

**FID-027.** A replay record MUST declare its provenance and MUST be immutable;
editing a recording invalidates its digest and with it the replay claim.

### 5.4 Replay and evidence

**FID-028.** The replay endpoint's evidence chain is a copy of the recording's
chain, not a new chain that re-signs the same events. Its `genesis_digest` MUST be
the recorded genesis; a replayed receipt MUST NOT be presented as a new execution.
`evidence.verify` on a replay bundle MUST return the recording's validity. Every
non-genesis frame MUST be bound to exactly one matching source receipt
(`command_id`, device, revision and `state_hash_after`); a frame whose served
state contradicts its receipt is a corrupt recording and MUST be rejected before
the replay endpoint is constructed. The initial frame's provenance (pre-command
state) MUST be defined and validated separately, not faked as an execution.

**FID-029.** A host in replay mode MUST NOT display replay actions as live
control; every command affordance SHOULD be disabled and the mode banner MUST say
`replay`.

---

## 6. Hybrid authority

**FID-030.** A hybrid device (digital twin following hardware, or hardware
following a model) MUST declare `fidelity.authority`: an object mapping each
resource id to `hardware` or `model`. The truth side for each resource is then
unambiguous. The object MUST cover exactly the device's declared resources; a
string, a missing field on a hybrid manifest, or an object with unknown/missing
resource keys is a schema/semantic failure and the endpoint MUST refuse to start.

**FID-031.** For a resource whose authority is `hardware`, the model MUST
synchronise from the hardware and MUST NOT drive it; commands that would change
the hardware through the model MUST be rejected with
`MHS.SAFETY.ENVELOPE_VIOLATION` or `MHS.MODE.READ_ONLY` as appropriate. For
authority `model`, the model state is truth and hardware follows the model; the
endpoint MUST still enforce the hardware's envelope.

**FID-032.** Divergence between the two sides MUST be measured and reported in
the device state (for example `divergence` fields with a tolerance) and MUST be
exposed in `resource.read` and in the fidelity notes. A hybrid endpoint MUST
declare what happens on divergence: `halt` (stop following), `resync` (model
overwritten from hardware) or `alarm` (report and continue). The chosen behaviour
MUST be in `fidelity.gaps` or `semantics.notes`.

**FID-033.** A hybrid device MUST report `mode: "hybrid"` even when one side is
temporarily unavailable; a fallback to pure simulation or pure hardware without a
new session and a declarative mode change is a conformance failure
([00-architecture.md](00-architecture.md) A6: no silent simulation, informative).

**FID-034.** Hybrid safety follows the stricter side: the hardware envelope and
interlocks apply to all commands, and the model MUST NOT be used to justify
bypassing a hardware interlock.

---

## 7. Validation methodology (F3)

**FID-035.** An F3 validation record MUST name the physical device (by
`device_id` or vendor/model/serial), the metric(s), the test protocol, the result
and the date. It MUST reference an evidence artifact by digest
(`validation.evidence_ref`).

**FID-036.** Metrics MUST be quantitative and task-relevant. Examples: pose RMSE
in mm/deg, volume error in µL over the working range, temperature tracking error
in K, cycle-time error, spectral peak position error. "Looks the same" is not a
metric.

**FID-037.** Validation MUST state the operating envelope it covers (speeds,
loads, temperatures, sample volumes). Extrapolation outside that envelope is a
gap and MUST be listed.

**FID-038.** Re-validation is REQUIRED when: the model changes, the physics
engine or timestep changes, the physical device's firmware/hardware changes
materially, or the validation is older than 24 months. The `validated_at` date and
a re-validation trigger note SHOULD be in `validation.metrics` or the device
profile.

**FID-039.** A vendor MUST publish the validation methodology description
(protocol, instruments, acceptance criteria) alongside the metrics; a metric
without a methodology is marketing.

---

## 8. Gap disclosure

**FID-040.** `fidelity.gaps` MUST list known omissions that could affect an
agent's decision: missing physics, missing sensor modalities, unmodelled noise,
unmodelled wear, restricted operating envelope, no wall-clock pacing, simplified
actuator dynamics, excluded phenomena.

**FID-041.** `gaps` MUST be non-empty for F0/F1/F2 devices (there is always
something not modelled); an empty array is permitted only for F3 with a validation
envelope that covers the advertised use. An empty array on F0 is a conformance
failure.

**FID-042.** Hiding a known fidelity gap is a conformance failure and, where it
misleads an operator about hardware equivalence, a safety defect reportable under
[MHS-010](10-governance.md) §7.

**FID-043.** Hosts MUST show the gaps to the model before the first actuation in a
session and MUST keep them accessible in the device profile; the model's context
MUST NOT be limited to the summary line. An agent that plans hardware actions based
on a model MUST be shown the gap list and the mode
([MHS-009](09-host-profile.md) §4).

**FID-044.** Gap text SHOULD be phrased as a capability statement, not a disclaimer
("rigid contacts only; no suction or adhesion", "no camera noise or lens
distortion"). It is model context, not legal text.

---

## 9. Simulated and physical identity

**FID-045.** A simulator MUST NOT claim the identity of the hardware it models.
A simulated device's `device_id` and `instance_id` MUST differ from the physical
device's, its `mode` MUST be `simulated` or `hybrid`, and it MUST declare
`models: [physical device_id]` when it models a specific device
([00-architecture.md](00-architecture.md) §7.1, informative).

**FID-046.** A physical device's manifest MUST NOT declare `models`. The relation
is one-directional: a model points at reality, not the reverse.

**FID-047.** `provenance` MUST record the adapter, source repo, source commit and
generated-by information for simulated devices, so that a host can trace a simulator
to the code that implements it ([`device.schema.json`](../schema/device.schema.json)
`provenance`).

**FID-048.** A host MUST NOT transfer trust between a simulator and its modelled
device: conformance, evidence and approvals are per `device_id`/`instance_id`. A
report for a simulator MUST NOT be cited as evidence about the hardware.

**FID-049.** Capability calls MUST NOT silently cross the sim/hardware boundary.
An endpoint serving both a simulator and a hardware device MUST expose them as
separate devices with separate capabilities and MUST reject a command whose
`device_id` and session mode disagree.

---

## 10. Conformance hooks

| Requirement | Test | Checks |
|---|---|---|
| MODE-002 | MODE-002 | Session mode mismatch rejected with `MHS.SESSION.MODE_MISMATCH`. |
| MODE-005 | MODE-005 | Mutation in replay rejected with `MHS.MODE.READ_ONLY`; state unchanged. |
| MODE-006 | MODE-006 | Hybrid manifest without `authority` fails validation. |
| FID-001 | FID-001 | Sim/hybrid manifest requires fidelity; hardware forbids it. |
| FID-006 | FID-006 | F3 without validation record fails. |
| FID-010 | FID-010 | Missing determinism kind fails; CL4 replay with `statistical` fails. |
| FID-016 | FID-016 | Determinism test procedure runs and reports seed/hashes. |
| FID-025 | FID-025 | Replay comparison: same seed ⇒ identical `state_hash` sequence. |
| FID-028 | FID-028 | Replay bundle verifies against recorded genesis. |
| FID-041 | FID-041 | F0/F1/F2 devices carry non-empty gaps. |
| FID-043 | FID-043 | Host surface exposes gaps before actuation. |
| FID-045 | FID-045 | Simulated identity differs from modelled device; `models` declared. |

The mandatory negative list is in [MHS-001](01-conformance.md) §4.3. The reference
conformance suite implements these ids; the reference devices in `MHS/sdk/` include
a deterministic conveyor (exact) and a seeded arm profile to exercise both
determinism kinds.

---

## 11. Informative: what an agent should do with this chapter

This section is informative.

1. Read `mode` first. If it is `simulated` or `hybrid`, read `gaps` before
   planning: the model's physics is what you can reason about, not the hardware's.
2. Read `determinism.kind`. `exact`/`seeded` means a plan can be verified by
   replay; `statistical` means results need repeated runs; `none` means evidence
   is a record, not a reproducible experiment.
3. Read `realtime_factor`. A factor of 0 means the simulation does not model time;
   do not use it for timing reasoning.
4. For hybrid, read `authority` and never assume the model knows what the hardware
   is doing on a resource the hardware owns.
5. For F3, read the validation envelope: a validated model outside its envelope is
   an F0 model with a nice document.
6. When the gap list is long, prefer conservative motions and small steps; the
   envelope still protects the device, but the model will not predict the
   consequences well.
7. When the same scenario must run on hardware, re-open a session with
   `mode: "hardware"` on the hardware endpoint and re-check the risk class; the
   session that drove the simulator cannot follow you.
