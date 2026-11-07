# MHS-004 — Safety, Permits, Sessions, Audit and Threat Model

| Field | Value |
|---|---|
| Document | MHS-004 (normative) |
| Status | OpenMHS 0.9 development draft |
| Editor | The OpenMHS Authors |
| Layer | core (§1-§5, §9-§10); §6-§7 Sessions and Permits; §8 Evidence ([profiles.md](profiles.md) §2) |
| Normative base | [core.md](core.md) §4 to §6 and §11; overview in [00-architecture.md](00-architecture.md) §6 and §15 (informative) |
| Companion schemas | [`device.schema.json`](../schema/device.schema.json) `safety`, [`defs.schema.json`](../schema/defs.schema.json) `interlockState`, `effect`, `approval`, [`receipt.schema.json`](../schema/receipt.schema.json) |

This document specifies how MHS endpoints enforce safety, how permits and
sessions bound authority, how the evidence chain is built and verified, and what
MHS explicitly does **not** certify. The wire forms of the `mhs.safety.*` methods
are in [MHS-002](02-wire-protocol.md) §11; this document is normative for their
semantics. The word "safety" in this document always means *the MHS envelope*, not
a safety-rated control function.

The key words MUST, MUST NOT, REQUIRED, SHOULD, SHOULD NOT, MAY and OPTIONAL are
to be interpreted as described in RFC 2119 and RFC 8174.

---

## 1. Position: what MHS enforces, and what it does not certify

**SAFE-001** (wire form in [MHS-002](02-wire-protocol.md) §11.1 — `safety.status`) is
the read method; **SAFE-002…SAFE-004** (e-stop, reset, permit wire forms) are
defined there. This chapter starts at SAFE-005.

MHS enforces an **envelope**: declared limits, interlock preconditions, permits,
revision expectations and concurrency leases, evaluated by the endpoint before any
effect and by the device while an effect is running. That is a useful second line
of defence against a confused or prompt-injected agent.

MHS is **not**:

- a safety-rated channel, a safety instrumented function, or a substitute for a
  hardware emergency stop;
- a certification of any device, process or experiment;
- a risk assessment;
- a guarantee that a declared limit is the correct limit for the user's process;
- a guarantee that a driver, bridge or simulator faithfully implements physics.

**SAFE-005.** Every requirement in this chapter that concerns physical protection
MUST be read together with §10: the endpoint is a *software* interlock layer. A
device that needs a protective function MUST implement that function in
independent hardware or a certified safety system; MHS MAY mirror it but MUST NOT
provide it.

**SAFE-006.** A device manifest MUST declare `safety.risk_class`, `safety.estop`
and `safety.safe_state`
([`device.schema.json`](../schema/device.schema.json)). An endpoint serving a
device without these fields MUST fail schema validation and MUST NOT claim CL1.

---

## 2. Risk classes

### 2.1 Definitions

Risk classes describe the worst credible consequence of the capability set, not
the difficulty of integration.

| Class | Definition | Typical examples | Minimum controls |
|---|---|---|---|
| **R0** | Data only; no physical effect. | temperature read, camera capture, simulated state read, isolated simulation stepping | None beyond access control. |
| **R1** | Low energy, reversible, bounded. A wrong action is recoverable without injury or irreplaceable loss. | small joint motion in free space, LED illumination, opening/closing a valve with a declared state | Session + envelope. |
| **R2** | High energy, irreversible, or destructive if wrong. | pipetting into a plate, centrifuge, plate transfer, laser above class 1, heating, mobile-base transit | Session + envelope + audit + (per class) permit. |
| **R3** | Hazardous to people, environment or irreplaceable samples; requires human presence and/or permit. | high-force contact, biological/radiological handling, high voltage, class 3B+ laser, heating above declared safe limits, person-in-workspace mobile operation | Session + envelope + permit + named responsible human + physical e-stop within reach. |

R0 does not imply that a command is read-only. The machine-readable catalogue
classifies `cap.world.step.v1`, `cap.world.reset.v1` and `cap.world.seed.v1` as R0
when their effects are confined to simulated state. Session, schema, envelope,
cancellation and evidence requirements still apply where the protocol or binding
requires them. A simulated or hybrid label never lowers the risk of a binding
that can affect physical equipment; that binding follows its actual hazards.

This corrects the former placement of simulation stepping in the R1 examples to
match the higher-precedence catalogue; no catalogue risk or runtime control is
changed by this clarification.

**SAFE-007.** A device's declared `risk_class` MUST be the maximum over its bound
capabilities' class-level `risk_class` after binding elevation
([MHS-003](03-capability-registry.md) CAP-017). An endpoint MUST NOT lower a
device's risk class to make a session easier to open.

**SAFE-008.** A binding MAY raise a class risk level (for example
`cap.optics.set_power.v1` from R2 to R3 on a class 3B source) but MUST NOT lower
it. The binding's elevated value MUST be visible in `devices.get` and in the
generated profile ([MHS-009](09-host-profile.md) §4).

**SAFE-009.** Risk class R3 on `mode: "hardware"` MUST require:
(a) a permit for every R3 capability, (b) a named human principal in the session
approvals, and (c) the device declaring `access.requires_human_present: true`
when physical presence is a precondition. A session that cannot satisfy this MUST
be refused with `MHS.SAFETY.APPROVAL_REQUIRED`.

**SAFE-010.** Risk classes MUST be exposed in `hello.devices[*].risk_class`,
`devices.get`, `safety.status`, and any host UI that lists capabilities. An agent
that cannot see the risk class cannot reason about it
([MHS-009](09-host-profile.md) HOST-013).

---

## 3. The safety envelope

### 3.1 Components

An envelope is the tuple:

```text
E = ( session, mode, input-schema, limits, interlocks, permits, revision, lease )
```

evaluated by the endpoint in the order below. Each component is fail-closed: a
component that cannot be evaluated is a rejection, never an assumption of safety.

### 3.2 Evaluation order (normative)

**SAFE-011.** The endpoint MUST evaluate a command in the exact order of
[core.md](core.md) CORE-060 before executing any effect, and MUST reject at the first
failure without side effects. The order is: (1) principal; (2) session and grants;
(3) binding `(capability_id, resource)`; (4) `command_id` replay or reuse; (5) the
e-stop latch; (6) mode, hybrid authority and arming; (7) structure (the served
schema without the bounds of limited fields); (8) limits, then `LIMITS_UNSET`;
(9) the remaining schema bounds; (10) the permit, then cumulative budgets;
(11) interlocks; (12) the device lock, `expected_revision`, dispatch. This replaces
the earlier list, which put interlocks before the permit and the schema before the
limits:
**permit validity precedes interlock evaluation, and limits precede the schema's own bounds.**
Capability-level preconditions (a tip attached, a plate
present) are declared as interlocks or checked by the bridge and reported as
`MHS.DEVICE.PRECONDITION_UNMET`.

**SAFE-012.** An interlock whose state cannot be read MUST be treated as `open`
for evaluation purposes and reported as `unknown` in the error data. The endpoint
MUST NOT treat `unknown` as `closed`.

**SAFE-013.** If an interlock changes to `open` while an operation is running, the
endpoint MUST stop the affected motion/output and transition the device to its
declared `safe_state` within the operation's declared cancellation budget. The
receipt MUST be `failed` (interlock trip) or `cancelled` (client cancellation), and
the effects observed before the trip MUST be recorded.

### 3.3 Limits

Limits have one grammar and one engine ([core.md](core.md) §4). A limit rule is the
closed object `{min, max, allowed, unit, reason, source, ref, names, per}`, keyed by a
limit path (`field`, `a.b`, `a[*]`, `a[3]`); `min` and `max` are scalars (applied to
every element of a numeric array) or one value per element of a fixed-length array;
`per` names the window of a cumulative budget (`session`, `rolling_1h`,
`rolling_24h`, `rolling_7d`). `device.safety.envelope` maps a capability id (`cap.<class>.v<N>`,
`x-cap.<owner>.<name>.v<N>`) or a pattern (`cap.<class>.*`, `cap.*`) to such a map;
any other key is a manifest error. The effective limits of a binding are the
intersection of the class limits, the binding's `limits`, the device envelope and the
operator overlay (`site-limits.json`), which can only narrow and which supplies the
bounds a driver marked `operator_required` ([core.md](core.md) CORE-042). Limits that
cannot be enforced as written refuse the endpoint at start-up, or, for a device or an
envelope that changes later, answer `MHS.ADAPTER.MANIFEST_INVALID` (`limits_invalid`)
on every binding except the stop classes (CORE-043).

**SAFE-014.** An input that violates a limit MUST be rejected with a `rejected`
receipt and `MHS.SAFETY.ENVELOPE_VIOLATION`, before any native call, also where the
class schema repeats the bound (the limit is evaluated first, CORE-045).
`error.data.details` MUST name the concrete path, the kind of violation, the bound, the
supplied value, the unit and the source of the bound (`{path, kind, bound, value, unit,
source}`, with every violation in `violations[]`; CORE-044). Every array element and
every nested leaf is checked. Limits apply to permit-gated bindings, to the stop classes
and to `safe_state.achieved_by` actions, and are checked before the permit: refusing an
out-of-limit input on the permit instead is non-conforming. A call that sets a field
whose bound is `operator_required` and unfilled, or (strict mode, hardware or hybrid
device at R1 or above) a numeric input no limit covers, is refused
`MHS.SAFETY.LIMITS_UNSET` ([core.md](core.md) CORE-046); stop classes are never refused
for a missing bound. *Coverage rule for the conformance test:* SAFE-014 passes only when
every limited path is shown refused: both sides of a range, the members of an `allowed`
set and the values above, below and between numeric members, the first and last element
of an array and every element of a per-element bound; a fixture may supply the probes
(`out_of_envelope`), and a class-default limit on a field the schema rejects for every
input is not applicable ([MHS-001](01-conformance.md) §4.4).

**SAFE-015.** Limits MUST be enforced in the declared unit and against the
*converted* value. A bridge that converts units MUST convert before comparing; it
MUST NOT compare a native value against a limit expressed in another unit.

**SAFE-016.** Cumulative limits (laser on-time, motor travel, pump volume, thermal
dose) MUST be tracked over the declared window, MUST survive session close within
the retention window, and MUST return `MHS.SAFETY.CUMULATIVE_LIMIT` with
`data.details.used`, `data.details.limit` and the window name. The supported
window names are `session`, `rolling_1h`, `rolling_24h` and `rolling_7d`; an
endpoint that cannot enforce a declared window MUST refuse to start rather than
silently weakening it to a per-call bound. Accounting MUST be reserved before
the effect and shared across sessions of the same endpoint; the amount drawn is the
sum of the magnitudes of the addressed values (a negative value never refunds a
budget), budgets are pooled per class and the smallest wins, and with a `state_dir`
draws and releases are journalled so that a restart does not refill a window
([core.md](core.md) CORE-047, CORE-170).

**SAFE-017.** A capability's declared `max_duration_ms` is part of the envelope and
bounds the execution (the response deadline does not, PROTO-011). A cancellable
operation that reaches it without completing MUST be asked to stop
(`cancellation.reason` `max_duration_ms exceeded`) and the caller receives `cancelled`
when it stops within the 0.25 s grace, otherwise `unknown` with `MHS.OUTCOME.TIMEOUT`
(`details.reason` `max_duration_exceeded`); an operation MUST NOT continue
unboundedly ([core.md](core.md) CORE-100, CORE-101).

### 3.4 Envelope and optimistic concurrency

**SAFE-018.** Order matters: `expected_revision` is checked **after** the safety
checks, so that a stale client cannot learn a device's current revision by
probing safety limits, and so that a permit is never consumed by a request that
is rejected for a revision conflict. Implementations MUST keep this order even
when it costs a round trip.

**SAFE-019.** A rejected request MUST NOT consume a permit, advance the revision,
create an accepted receipt or mutate the idempotency store's outcome mapping.

### 3.5 Who enforces what

The envelope is enforced by the endpoint, never by the driver. [core.md](core.md)
CORE-070 lists what the core owns (grants, idempotency, the latch, limits, permits,
interlock evaluation, the device lock, revisions, receipts), and CORE-071 to CORE-073
what a bridge or driver supplies and must not do: it translates, reports interlock
state and the native stop, raises the signals `Cancelled`, `DriverFailed`, `Busy` and
`OutcomeUnknown`, and never clamps, retries an actuation, swallows a native failure,
advances a revision or makes a receipt. A bridge's `estop` runs concurrently with a
running call, takes none of its locks and advances an e-stop epoch, so that an
actuation queued behind the e-stop is refused `ESTOP_ENGAGED` instead of following it.

---

## 4. Interlock contract

### 4.1 Declaration

```json
{
  "id": "door_closed",
  "description": "Safety door is closed",
  "source": "hardware",
  "required_for": ["cap.motion.*", "cap.actuation.*", "cap.optics.*"]
}
```

`source` ∈ `hardware | software | operator | simulated`.

**SAFE-020.** An interlock MUST have a stable `id`, a human description and a
`source`. Its `required_for` list of capability ids or patterns, when present, MUST be
non-empty: an empty list is rejected at manifest validation (it gates nothing). An
interlock that gates nothing and exists to be shown to the operator is *informative*
and omits `required_for` altogether; SAFE-026 requires `safety.status` to report it
like any other ([core.md](core.md) CORE-073).

**SAFE-021.** Interlock state values are exactly `closed`, `open`, `unknown`
([`defs.schema.json`](../schema/defs.schema.json) `interlockState`). `closed`
permits actuation; `open` and `unknown` forbid it.

**SAFE-022.** A `hardware` interlock MUST be read from a hardware input or a
safety relay, not inferred from software state. If the driver cannot read it, it
MUST report `unknown`.

**SAFE-023.** A `software` interlock MAY be inferred from device state, but the
manifest MUST document the inference in the interlock `description` and the
adapter's safety notes ([MHS-006](06-adapters.md) §10). A software interlock MUST
NOT be the only protection for an R3 hazard.

**SAFE-024.** An `operator` interlock represents a human action or presence
requirement (door key, two-hand control, badge-in-zone). The endpoint MUST NOT
auto-clear it; only `mhs.safety.reset` after the human action, or a new operator
input, clears it.

**SAFE-025.** A `simulated` interlock exists to exercise the same state machine in
simulation. Simulated interlocks MUST be reported as `simulated` in
`safety.status`; a simulator MUST NOT claim hardware interlocks.

**SAFE-026.** `safety.status` MUST report every interlock that exists, including
informative ones (no `required_for`) and those whose state is `unknown`; hosts MUST show
open and unknown interlocks on the approval surface, not only the ones blocking
the current capability.

**SAFE-027.** An endpoint MUST NOT expose a method that sets an interlock state
directly. Interlocks are inputs from the equipment side. Test harnesses MAY inject
simulated interlocks only through a capability in the `x-cap` namespace that is
absent in production manifests.

---

## 5. Emergency stop and reset

### 5.1 E-stop contract

The device manifest declares:

*Abridged example — ellipses (`…`), alternations (`a|b`) and bare fragments are illustrative; this block is not a complete JSON document.*

```jsonc
"estop": {"kind": "hardware|software|both", "latching": true,
          "latency_ms": 50, "reset": "mhs.safety.reset",
          "physical_ref": "workcell door post, red mushroom button"}
```

**SAFE-028.** The e-stop MUST take effect within `latency_ms`: motion stops,
outputs go to the declared `safe_state`, and the device latches if
`latching: true`. The receipt MUST record `latency_ms` actually observed and
`safe_state_achieved`.

**SAFE-029.** Every device declares `safe_state` as
`{description, achieved_by[]}`. `achieved_by` MUST name the capabilities or
actions that bring the device to that state, and each named capability MUST be
exempt from the e-stop latch, permits, cumulative budgets and the device lock so that
it is always callable ([core.md](core.md) CORE-075); its schema, limits and
interlocks still apply, and so does arming, from which the e-stop path itself is
exempt because it runs these actions on its own. An id named in `achieved_by` MUST be
a bound capability: a hardware or hybrid device with an unbound id is refused at
start-up, a simulated one reports it as a failed action on every e-stop
(`safe_state_unbound`).

**SAFE-040.** `mhs.safety.estop` MUST engage the same latch as
`cap.motion.estop.v1` and MUST be callable with `deadline_ms` no larger than the
declared e-stop latency + 1000 ms. The e-stop path MUST NOT queue behind ordinary
commands, permits or rate limits: it MUST preempt or interrupt a running operation
without waiting for its natural completion. **The latch is set first**, under the
endpoint lock and before any bridge I/O, and persisted when the endpoint has a
`state_dir`; then running operations are cancelled, the native stop runs, then the
`safe_state.achieved_by` actions ([core.md](core.md) CORE-074). If the endpoint cannot
confirm engagement within that budget (or any step fails), it MUST return a `failed`
receipt with `MHS.SAFETY.SAFE_STATE_UNREACHED` (`details.reason` `timeout`,
`native_failed`, `action_failed`, `safe_state_unbound`, `no_stop_path`,
`bridge_reports_unsafe` or `command_in_flight`: on a device that declares a
re-enable, an effectful command in flight when the e-stop landed has not settled, CORE-086; once
those commands settled, a stop that has not answered is a `timeout`), MUST keep the latch engaged and MUST keep trying in the
background ([core.md](core.md) CORE-077). While latched, every effectful command is
refused `MHS.SAFETY.ESTOP_ENGAGED` (CORE-075).

**SAFE-041.** `mhs.safety.reset` MUST be refused with
`MHS.SAFETY.RESET_REFUSED` while any declared interlock that is not `reset_exempt`
reads `open` or `unknown` (an unreported or unreadable interlock counts as
`unknown`), and MUST report the blocking interlocks. It is also refused while an
effectful operation that ignored cancellation is still running (`operation_running`)
and while a native e-stop attempt is still in flight (`stop_path_pending`), and on a
hardware or hybrid device it is accepted only from an authenticated operator in strict
mode ([core.md](core.md) CORE-080, CORE-083). `reset` MUST NOT clear software-only
state that the device does not declare resettable.

**SAFE-042.** Releasing the e-stop, closing the door or clearing an interlock MUST
NOT restart any motion or output. After reset, a **new** start command is
required. A device that auto-resumes is non-conformant. A reset MAY re-establish
communication (reconnect a socket, re-attach a client object, reopen a handle) only
when that changes nothing on the device; anything that may energise the device,
enable motion or start a process that may initialise hardware is never a reset step.
A device whose stop leaves it disabled (a drive switched off) MAY declare the command
that re-enables it as `safety.estop.reenable` ([core.md](core.md) CORE-086); its
reset only releases the latch and MUST NOT run that command or re-enable the device
by any other means, and any native recovery it needs, fault clearing included,
belongs in that command. The SDK refuses an `@reset` hook on a decorated driver that
declares a re-enable, and a family reset binding on the re-enable's native target; a
family reset binding that re-arms the device through another target is the author's
obligation, checked by review (CORE-086). A device whose stop cannot be undone
within the endpoint declares a terminal e-stop (SAFE-048). The re-enable is refused
`MHS.SAFETY.ESTOP_ENGAGED` while the device is latched, and the conformance test
sends it after the reset and before its recovery command (TSAFE-001).

**SAFE-043.** Reset MUST be idempotent in effect: a second reset with no
intervening engagement MUST return a `rejected` receipt with
`MHS.SAFETY.RESET_REFUSED` and `data.details.reason = "not_latched"` rather than
pretending to clear something. A reset is refused with `estop_during_reset` when an
e-stop engaged while it ran; once the bridge's reset has run, a refusal is a `failed`
receipt that advances the revision ([core.md](core.md) CORE-081).

**SAFE-044.** The e-stop MUST be logged as `effects: [{kind: "safety.estop",
summary, reversible: false, severity: "R0"}]`; `severity` describes the
consequence avoided, and the receipt MUST NOT claim that safety was achieved
beyond the declared `safe_state`.

### 5.2 Independence

**SAFE-045.** A hardware e-stop MUST exist independently of MHS for every
hardware or hybrid device at risk class R2 or R3. The manifest MUST declare an e-stop
`kind` of `hardware` or `both` together with a `physical_ref` that says where the
independent stop is documented, or the device MUST name a non-empty
`safe_state.achieved_by`. A `software`-only e-stop with neither (or a `hardware` kind
with no `physical_ref`) on an R2/R3 hardware or hybrid device is a conformance failure at
CL3 and, in strict mode, a refusing finding at start-up ([core.md](core.md) CORE-161).

**SAFE-046.** The MHS e-stop path MUST NOT be the only path to stop the device; a
network failure, endpoint crash or host crash MUST leave the device able to be
stopped by the physical e-stop. This is a design requirement on the device and
adapter, and it is stated in every manifest and every report.

**SAFE-047.** An endpoint MUST declare its e-stop kind truthfully. Claiming
`both` when no hardware input exists is a conformance failure and a safety defect
reportable under [MHS-010](10-governance.md) §7.

### 5.3 Terminal e-stop

**SAFE-048.** A device whose native stop cannot be undone without a new native
session (a reconnection, reopening or re-initialisation that may change the device,
[core.md](core.md) CORE-087; for example, a stop that closes the instrument session
for good where the upstream requires a new initialisation that resets the
instrument) MUST declare `safety.estop.terminal` with
that reason, and its reset MUST NOT reopen or reinitialise the device to emulate a
recovery. After the endpoint has started the stop path of such a device, every
`mhs.safety.reset` of the device on that endpoint MUST be refused with a `rejected`
receipt, `MHS.SAFETY.RESET_REFUSED`, `details.reason` `terminal_estop` and
`details.terminal` the declared reason, without calling the bridge; the latch is kept
and every effectful command stays refused until that endpoint ends
([core.md](core.md) CORE-087). Recovery is a new endpoint, on which an operator
resets the latch it restores (SAFE-065) until a stop path starts there, a replay of
the latching e-stop's `command_id` included. A terminal e-stop has no `reenable`, and
declaring a terminal stop that a reset can undo, or a re-enable that the reset runs,
is a safety defect like an untruthful e-stop kind (SAFE-047).

### 5.4 Sensed-confirmation stop (simulated devices only)

**SAFE-049.** A simulated device whose only stop is a request whose acknowledgement proves
nothing (a land, mode, zero-velocity or motor-cut request) MAY declare a sensed-confirmation
stop ([core.md](core.md) CORE-088): its e-stop sends the request and is achieved only when a
confirming sensed state (for example landed and disarmed, or standstill on odometry) is read
from fresh samples, `consecutive` of them on subscriptions opened after the
request and published after those subscriptions were (what a new subscription may receive from
before it existed never counts: on ROS 1 the bridge has no proven offset between the producer clock and its wall clock, so a producer stamp is not a freshness proof: every ROS 1 stamp sample is discarded and does not refresh counted freshness, including a stamp one second ahead, a ROS simulation clock, a delayed latch, a frame already in a client buffer, and a sample from a transport that cannot report its buffer; an empty queue, a socket poll, a client library buffer, a continuation flag, and a fixed lead are not that proof; on ROS 2 a
declared transient-local history), within `confirm_within_ms`; otherwise the e-stop MUST be a `failed` receipt
`MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch engaged and the background retry of SAFE-040,
which sends the request again. The request alone is never a stop. When the declaration names an exclusion on a request topic, silence, a subscription error, a sample whose watched fields are not all zero, and a sample the exclusion ring drops each refuse the confirmation; a dropped sample was not inspected, so the tail that remains is not a passive command. Only a passive sample observed on that subscription after it opened, and still fresh at the commit, is evidence the competing command is absent. A source is
producer-stamped, or, when its producer does not stamp, fresh by arrival from a cited volatile
ROS 2 publisher with `min_interval_ms` (a sample closer than that restarts the count; a replay
spaced at least that far apart is not detected, so arrival freshness is refused for a
transient-local publisher and for ROS 1). Only a device of mode
`simulated` may declare it: real hardware, real MAVLink vehicles included, never may, and an
endpoint refuses such a declaration on any other device; only what the endpoint serves (a
served manifest of mode `simulated` that declares the confirmation) lets a confirmation stand
for a stop, never an argument a package passes. Its reset re-confirms the sensed state without
sending the request and is refused while that state does not hold; it never resumes anything
(SAFE-042). Its thresholds, and the history of each ROS 2 source's publisher, are cited or
supplied by the operator for the deployment, never invented, and the e-stop receipt MUST NOT
claim more than the declared safe state and the confirmation window (SAFE-044). The SDK cannot
prove that a ROS graph is simulated: a stack that can also drive a real vehicle with another
endpoint (MAVROS, cflib) says so, and serving it as hardware is out of scope.

---

## 6. Permits and approvals

### 6.1 When a permit is required

`device.safety.requires_permit` lists class patterns (for example
`cap.optics.*`, `cap.thermal.setpoint.v1`). A capability whose class declares
`safety.requires_permit: true` is also gated, and a binding MAY gate more.

**SAFE-030.** A gated capability invoked without a permit MUST receive a
`rejected` receipt with `MHS.SAFETY.PERMIT_INVALID` and
`data.remediation` describing how to obtain one. No effect, no revision advance.

**SAFE-031.** A permit MUST be bound to the exact `input_digest`. Presenting a
permit with a different input MUST be rejected with
`MHS.SAFETY.PERMIT_INVALID` and the mismatch MUST be logged. Reusing a consumed
permit MUST be rejected the same way (single-use). The unused-check, all scope
checks and the single-use consumption MUST be one atomic transition with
respect to concurrent requests: among any number of concurrent presentations of
one permit, at most one may proceed to effect. A pre-effect refusal (schema,
limit, interlock, revision conflict) MUST NOT consume the permit.

### 6.2 Issuance

**SAFE-032.** `mhs.safety.permit` MUST require a valid session and MUST record
`approvals[]` — opaque records `{principal, method, approved_at, evidence_ref}`
with `method` ∈ `human_click | policy_rule | dual_control | auto`
([`defs.schema.json`](../schema/defs.schema.json) `approval`). The endpoint MUST
validate that the approval principal is authorised to approve; it MUST NOT
accept an approval record as a bare string, and MUST NOT infer human authority
from a client-supplied `human:` principal string. An endpoint that cannot
authenticate approvals (no trusted approval-authority verifier configured) MUST
fail closed for R3 hardware sessions and, in strict mode, for permits on hardware
devices (and hardware-authority resources of hybrid devices) at R2 or above, with
`MHS.SAFETY.APPROVAL_REQUIRED` ([core.md](core.md) CORE-084). Where the method accepts an exact `input` it MUST
verify the supplied `input_digest` recomputes from `{capability_id, resource,
input}` (PROTO-036).

**SAFE-033.** The permit `scope` MUST include `device_id`, `capability_id`,
`resource?`, `input_digest`, `principal`, `expires_at` and `single_use`. The
permit MUST also be bound to the issuing `session_id`; a presentation in another
session, for another device or for another resource MUST be rejected with
`MHS.SAFETY.PERMIT_INVALID` before the permit is consumed. Issuance MUST reject a
resource that does not exist or is not the capability's bound resource. The
permit MUST expire no later than its TTL; the recommended maximum for human
approval of a physical action is 300 s.

**SAFE-034.** For R3 hardware capabilities the endpoint MUST require at least one
`human_click` or `dual_control` approval naming a human principal. `auto`
approvals MUST NOT satisfy an R3 requirement.

**SAFE-035.** Permit issuance MUST be auditable: the approval decision (who, when,
which input digest was displayed) MUST appear in the evidence log as its own
receipt (`cap.internal.safety_permit.v1` evidence event) even though
`mhs.safety.permit` returns a permit object rather than a command receipt.

**SAFE-036.** Revocation: `mhs.safety.estop`, session close and session expiry MUST
revoke all outstanding permits for that session. A revoked permit MUST NOT be
usable.

**SAFE-037.** The approval UI requirement is normative for hosts
([MHS-009](09-host-profile.md) §6): the human MUST see the human-readable
rendering of exactly the input whose `input_digest` is being approved, the
capability semantic summary, the resource, the device and the risk class. An
approval collected without that rendering is invalid.

---

## 7. Sessions, principals and least privilege

### 7.1 Principals

A principal is `{id, kind, display_name?, contact?}` with
`kind ∈ human | agent | service` ([`defs.schema.json`](../schema/defs.schema.json)).

**SESS-007.** The endpoint MUST authenticate the transport caller and map it to a
principal; it MUST NOT trust a `principal` object supplied in `session.open`
without authenticating the caller's authority to act as that principal. Local
stdio endpoints MAY treat the launching process as the principal
([core.md](core.md) CORE-150).

**SESS-008.** `session.open` MUST grant the intersection of requested
capabilities and the device's access policy, and grants MUST be minimal. The
grant list returned MUST be exactly what the session can invoke; a capability not
granted MUST be rejected with `MHS.SESSION.CAPABILITY_NOT_GRANTED`, not silently
denied.

**SESS-009.** A session MUST NOT observe another session's private resources; for
simulators, session isolation SHOULD be an independent world instance, and the
device manifest MUST declare whether state is shared (`x-mhs-shared-state: true`)
when it is not isolated.

**SESS-010.** Session expiry MUST release leases and transition running
operations to cancellation-to-safe-state. The endpoint MUST reject calls on the
expired session with `MHS.SESSION.EXPIRED` and MUST retain the session's receipts
in the evidence chain.

**SESS-011.** A session MUST NOT gain capabilities after open without re-opening.
A host MUST open a new least-privilege session for a new task rather than reusing a
broad one.

**SESS-012.** A session requesting `mode: "hardware"` on a device whose
`access.requires_human_present` is true MUST include an approval naming a human
principal who is present; the endpoint MUST NOT infer presence from prior
sessions.

---

## 8. Audit and evidence chain

### 8.1 Chain construction

**EVID-010.** Every receipt MUST be appended to the endpoint's evidence log with
a link:

```text
digest_0     = sha256(JCS(genesis_document))
digest_i     = sha256(JCS(receipt_i without "evidence") || digest_{i-1})
receipt_i.evidence = {seq: i, prev_digest: digest_{i-1}, digest: digest_i}
```

`genesis_document` is an endpoint-level record
`{endpoint_id, created_at, mhs_version, instance_salt}` whose digest is published
in `evidence.export.endpoint_info.genesis_digest` and in the endpoint descriptor.
`seq` MUST be a contiguous integer starting at 1.

**EVID-011.** The chain MUST be append-only. An endpoint MUST NOT rewrite, delete
or reorder receipts. If the underlying store cannot append, it MUST fail the
mutation rather than lose the audit record.

**EVID-012.** Receipts for `rejected` outcomes MUST be chained like all others;
a rejection is evidence of a refused action. `unknown` receipts MUST be chained
and MUST remain resolvable.

**EVID-013.** `evidence.seq` MUST be per-endpoint, not per-session, so that
receipts from different sessions interleave in one chain.

**EVID-014.** The endpoint MUST include `evidence` in every receipt it returns
once the receipt is terminal; a non-terminal (`accepted`, `running`) receipt MAY
omit the link and MUST carry it in later `operations.get` responses.

### 8.2 Verification

**EVID-015.** `mhs.evidence.verify` (and the reference SDK's `verify_bundle`) MUST
implement this algorithm and MUST report every failure found, not the first:

```text
check bundle_version supported
check genesis_digest == endpoint_info.genesis_digest
prev = genesis_digest
for each receipt in bundle.receipts ordered by evidence.seq:
    check evidence.seq == expected_seq (contiguous from bundle start)
    check evidence.prev_digest == prev
    body = receipt without "evidence"
    check evidence.digest == sha256(JCS(body) || prev)
    check receipt validates against receipt.schema.json
    prev = evidence.digest
check bundle.head_digest == prev
if signature present: check JWS over head_digest with the endpoint key
return {valid, checked, head_digest, errors[]}
```

**EVID-016.** A single modified byte in any receipt body, a reordered receipt, a
deleted receipt or a changed `prev_digest` MUST make verification fail with
`MHS.EVIDENCE.CHAIN_BROKEN` and MUST identify the first failing `seq`.

**EVID-017.** A bundle MAY be signed with a detached JWS (`EdDSA` or `ES256`) over
the `head_digest`; the signing key MUST be resolvable from the registry by
`key_id`. Verification without the key MUST report `signature: "unverifiable"`,
not success and not a chain failure.

**EVID-018.** Retention: receipts MUST be retained for at least 30 days by
default (`hello.limits.receipt_retention_days`) and the configured retention MUST
be advertised. Deletion before retention expiry MUST be impossible through the
protocol.

**EVID-019.** If an endpoint truncates history (retention expiry, storage
pressure), it MUST insert a `MHS.EVIDENCE.TRUNCATED` marker receipt whose `output`
names the first retained `seq` and the reason. A bundle that begins after a
truncation MUST carry `truncation: {first_retained_seq, reason}` so a verifier
does not report a false gap.

**EVID-020.** Evidence MUST NOT contain secrets. Adapters MUST declare
`redaction` JSON pointers ([`adapter.schema.json`](../schema/adapter.schema.json))
and the endpoint MUST scrub those fields from receipts, errors and logs, recording
them in `receipt.redacted_fields`.

**EVID-021.** Telemetry is referenced, never embedded: `telemetry_ref` is an
artifact reference; raw high-rate streams MUST NOT be in the evidence chain
([02](02-wire-protocol.md) PROTO-012).

**EVID-022.** The evidence chain proves *internal consistency and tamper
evidence relative to the genesis record*. It does not prove that the receipts are
true, that the device is safe, or that the endpoint was not compromised before
genesis. Documents and UIs MUST state this limitation.

---

## 9. Threat model

### 9.1 Assets

1. **Physical integrity** of people, equipment, samples and environment.
2. **Integrity of evidence** (who did what, with which input, with what outcome).
3. **Confidentiality** of credentials, sample metadata and unpublished protocols.
4. **Availability** of the endpoint for legitimate operation.

### 9.2 Adversaries and threats

| Threat | Example | Mitigation in MHS | Residual risk |
|---|---|---|---|
| Spoofed principal | A container pretends to be `human:alice` over a shared HTTP endpoint. | Transport auth required off-loopback; principal mapping at endpoint; R3 approvals name authenticated humans. | Stolen bearer token. |
| Confused deputy | An agent with broad grants is tricked into calling a gated capability. | Least-privilege sessions; grants fixed at open; permits bound to input digest; endpoint-side envelope. | Agent still has whatever was granted. |
| Prompt injection | Retrieved text tells the model to disable a limit. | Limits are endpoint-side; no method sets envelope or interlock state; permit input rendering shown to human. | Model can still choose a dangerous *allowed* input. |
| Replay of commands | Network attacker resends `mhs.command`. | `command_id` + `input_digest` idempotency; TLS; expected revisions for state-sensitive operations. | Replay of a still-valid command to a different session is prevented only if command scoping is enforced. |
| Replay of permits | Old permit reused for a new input. | Permit bound to `input_digest`, single-use, TTL, session-scoped. | Collusion/endpoint compromise. |
| E-stop spoofing / suppression | Fake `safety.status` telling the host all is well. | E-stop and interlocks are endpoint/equipment state; host must not trust its own model; physical e-stop independent. | Compromised endpoint can lie; physical e-stop remains. |
| Evidence tampering | Editing a receipt to hide an action. | Hash chain, optional signature, offline verify, append-only. | Compromised endpoint with key access can re-chain from genesis; signed bundles and external copies limit this. |
| Malicious adapter | Adapter manifest maps a "read" to a destructive native call. | `native` recorded; adapter review; class risk floor cannot be lowered; shims must be declared; conformance tests. | A sufficiently deceptive shim can still misbehave. |
| Supply chain | A bridge dependency is compromised. | Adapter pins commits and licenses; bridges refuse incompatible licenses; packaging declares dependencies. | Transitive dependencies. |
| Denial of service | Flood of commands starves a real operation. | Rate limits, concurrency leases, bounded queues, backpressure. | Network-level attacks. |
| Information disclosure | Receipt or log leaks a token or sample identity. | Redaction rules, evidence scrubbing, telemetry refs, privacy rules ([MHS-007](07-registry.md) §9). | Misconfigured redaction. |
| Unsafe simulation transfer | Sim-tested plan executed on hardware without disclosure. | Mode declared in manifest and session; mismatch is an error; sim identity distinct; gap disclosure required. | Operator ignoring the gap list. |

### 9.3 Security requirements

**SAFE-060.** Non-loopback transports MUST use TLS and either bearer
authentication or mTLS. Tokens MUST be opaque, MUST NOT be logged, and MUST be
revocable. The reference endpoint does not terminate TLS itself: it refuses to
serve a non-loopback address without `auth_tokens` and expects to run behind a
TLS-terminating proxy ([core.md](core.md) CORE-152).

**SAFE-061.** A command MUST be attributable to the authenticated principal at
the endpoint; a receipt MUST carry `principal`. An endpoint MUST NOT accept a
`principal` claim in `mhs.command` params.

**SAFE-062.** R3 capabilities MUST require an approval record with a human
principal per invocation; a session-level approval is not a substitute for a
per-input permit ([MHS-009](09-host-profile.md) §6).

**SAFE-063.** Error responses and logs MUST be redacted according to the adapter's
`redaction` rules; a redaction failure is a conformance failure.

**SAFE-064.** An endpoint MUST NOT provide a method that disables the envelope,
permits, interlocks, e-stop or the evidence chain. Configuration that weakens
safety MUST be a deployment decision outside the protocol, documented in the
device manifest and visible to hosts.

**SAFE-065.** A device that has been e-stopped MUST remain latched across
reconnects, process restarts (for latching e-stops declared as persistent), and
session churn; latching state MUST be persisted by the endpoint or the hardware.
The reference endpoint writes `latch.json` atomically before any bridge I/O when it
has a `state_dir`; a restored latch is unconfirmed until the next e-stop; an unreadable
or missing latch file next to receipts starts the devices latched ([core.md](core.md)
CORE-171). Without a `state_dir` the latch is memory-only and a hardware backend is
refused (CORE-154).

---

## 10. Disclosure: `MHS.SAFETY.NOT_CERTIFIED` and what MHS does not certify

**SAFE-050.** Every endpoint MUST include `MHS.SAFETY.NOT_CERTIFIED` in
`mhs.hello.features` and SHOULD include it in the endpoint descriptor
`features[]`. The absence of this feature MUST fail the CL3 conformance test and
MUST be treated by hosts as a protocol violation.

**SAFE-051.** Every host MUST display, on the same surface where it shows device
capabilities or asks for approval, a statement that MHS is not a safety-rated
channel and that the hardware emergency stop is independent
([MHS-009](09-host-profile.md) §5).

**SAFE-052.** Reports, badges, registry records and documentation MUST NOT state or
imply that MHS conformance is a safety certification. The permitted wording is in
[MHS-001](01-conformance.md) §8.4–§8.5.

**SAFE-053.** MHS does not certify: mechanical, electrical or functional safety;
biological or chemical containment; radiation safety; electrical installation
compliance; clinical or diagnostic validity; data quality; metrological
traceability; or fitness for a particular experiment. Each is the responsibility
of the device vendor, the laboratory and the relevant regulator.

**SAFE-054.** An endpoint MUST report its protocol-level safety posture honestly:
`estop.kind`, `estop.latching`, interlock `source` values, and the absence of
hardware interlocks must be visible; an agent MUST be able to distinguish
"simulated interlock" from "hardware interlock" from `safety.status`.

**SAFE-055.** A host MUST NOT retry an `unknown` outcome, MUST NOT bypass a permit
because a policy engine is unavailable, and MUST fail closed on missing safety
status. It MUST surface `MHS.SAFETY.NOT_CERTIFIED` and the device's
`fidelity.gaps` before the first actuation of a session.

---

## 11. Conformance hooks

| Requirement | Conformance test | What is checked |
|---|---|---|
| SAFE-009 | SAFE-009 | R3 hardware session without human approval is refused. |
| SAFE-011 | SAFE-011 | Interlock open blocks actuation; error carries interlock list; revision unchanged. |
| SAFE-012 | SAFE-012 | Interlock unknown blocks actuation (fail closed). |
| SAFE-014 | SAFE-014 | Envelope violation names field, limit, value, unit. |
| SAFE-016 | SAFE-016 | Cumulative budget enforced and reported. |
| SAFE-018 | SAFE-018 | Revision conflict does not consume a permit. |
| SAFE-026 | SAFE-026 | `safety.status` lists unknown/open interlocks. |
| SAFE-027 | SAFE-027 | No interlock-writing method exists (static method scan). |
| SAFE-030 | SAFE-030 | Gated capability without permit rejected. |
| SAFE-031 | SAFE-031 | Permit for another input digest rejected; reuse rejected. |
| SAFE-040 | SAFE-040 | E-stop within latency; latched; receipted. |
| SAFE-041 | SAFE-041 | Reset with open interlock refused. |
| SAFE-042 | SAFE-042 | Release does not restart; new command required; a declared re-enable is refused while latched and accepted after the reset (TSAFE-001). |
| SAFE-045 | SAFE-045 | R2/R3 hardware declares hardware or both e-stop. |
| SAFE-048 | TSAFE-001 | After a declared terminal e-stop the reset is refused (`terminal_estop`, the declared reason, no bridge call) and the latch is kept; later tests run on a new endpoint. |
| SAFE-049 | none (acceptance gates G3 `SENSED_STOP_CARD`, `SENSED_SERVED`, `SENSED_ROUTE`, `SENSED_FIXTURE`; G6 `SENSED_FAIL_OPEN`; G7 `ROS_FILL_REF_NOT_SHOWN`, `ROS_HISTORY_NOT_SHOWN`) | Not a conformance-suite test: the acceptance gate checks that withheld, frozen or nulled samples leave a sensed-confirmation stop `SAFE_STATE_UNREACHED` and latched, that the served manifest is simulated on the SDK's route, and that cited fill lines and publisher histories show what they claim; SAFE-028 and TSAFE-001 run on the package's converging fake. |
| SAFE-050 | SAFE-050 | `MHS.SAFETY.NOT_CERTIFIED` present; CL3 fails otherwise. |
| SAFE-060 | SAFE-060 | Non-loopback without TLS rejected. |
| SAFE-062 | SAFE-062 | R3 permit requires human approval method. |
| EVID-010 | EVID-010 | Chain recomputes from genesis. |
| EVID-011 | EVID-011 | Append-only: tampering detected. |
| EVID-016 | EVID-016 | One-byte modification breaks verification with first failing seq. |
| EVID-019 | EVID-019 | Truncation marker prevents false gap. |

The negative tests in [MHS-001](01-conformance.md) §4.3 are mandatory for these
requirements.

---

## 12. Informative: constructing a device safety declaration

This section is informative.

1. Start from the capability catalogue: list the bound classes and take the
   maximum risk class.
2. For each hazard in `semantics.hazards`, ask what could cause it and whether the
   envelope prevents it. If prevention depends on a sensor, that sensor is an
   interlock with `source: "hardware"`.
3. Declare `safe_state` concretely: "conveyor stopped, diverter at main, outputs
   off" beats "safe".
4. Declare the physical e-stop and where it is: `physical_ref` is a documentation
   obligation to the operator.
5. Write the envelope limits with units and reasons; a limit without a reason is
   indistinguishable from an arbitrary one and will be raised by someone.
6. Decide which capabilities need permits. R3 always; R2 where the consequence is
   irreversible and the input has a wide space (laser power, centrifuge speed,
   high voltage).
7. Test the interlock and e-stop state machine in simulation first; the same
   states must be exercised by the conformance suite on the real endpoint.
