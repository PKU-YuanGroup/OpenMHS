# MHS-006 — Adapters, Bridges and Integration Recipes

| Field | Value |
|---|---|
| Document | MHS-006 (normative) |
| Status | OpenMHS 0.9 development draft |
| Editor | The OpenMHS Authors |
| Layer | Driver Profile companion: adapters, bridges and bindings ([profiles.md](profiles.md) §2) |
| Normative base | [driver-profile.md](driver-profile.md) and [core.md](core.md) §6; overview in [00-architecture.md](00-architecture.md) §9 (informative) |
| Data contract | [`adapter.schema.json`](../schema/adapter.schema.json), [`device.schema.json`](../schema/device.schema.json) |
| Worked example | [`../schema/examples/adapter.gymnasium-cartpole.json`](../schema/examples/adapter.gymnasium-cartpole.json) |

OpenMHS integrates existing SDKs, simulators and protocols through a generic
**bridge runtime** and a small per-repository description of what exists and how it
maps. **The default deliverable is a Driver class** ([driver-profile.md](driver-profile.md)):
one `mhs.driver.Driver` subclass (or a config-only family subclass) per upstream
repository, with sourced limits and facts, built on the bridge families of §5. The
declarative route, an **adapter manifest** with a `bindings.json` read by the same
bridges, remains valid and optional; `mhs.adapter.load` serves both in strict mode.
Either way the bridge executes the mapping and speaks the contract plane, and the
core ([core.md](core.md)) enforces every safety rule.

The key words MUST, MUST NOT, REQUIRED, SHOULD, SHOULD NOT, MAY and OPTIONAL are
to be interpreted as described in RFC 2119 and RFC 8174.

---

## 1. Two artifacts per integration

This chapter describes the declarative route. The three artifacts below are those
of an `mhs-adapter.json` integration; a Driver package carries the same information
as class attributes and decorators, and the bindings it needs are generated from
them.

1. **`mhs-adapter.json`** — the declarative manifest, validated by
   [`adapter.schema.json`](../schema/adapter.schema.json). It declares identity,
   family, upstream source, runtime, lifecycle, the device manifests the adapter
   publishes, safety summary, evidence state, tier and packaging metadata.
2. **`mhs/bindings.json`** — the declarative per-capability mapping consumed by
   the bridge (§7). It is adapter-local data, keyed by device and capability, and
   is referenced from the manifest (`bridges[].config.bindings_ref`).
3. Optionally, a **shim** (small Python/JS module) for behaviour the declarative
   mapping cannot express (§8).

An adapter MAY declare several devices: a workcell simulator can expose a robot,
a plate reader and a liquid handler from one process, each as a separate device
with its own manifest, identity and safety declaration.

> **Normative clarification.** The published schemas close the objects of an adapter:
> a device manifest inside `devices[]` MUST validate against
> [`device.schema.json`](../schema/device.schema.json), and a device capability
> has no `binding` member. OpenMHS 0.9 therefore places bindings in `mhs/bindings.json`
> (§1 item 2) and requires a concrete ULID `instance_id` in adapter device
> manifests (ADPT-004). The informative overview ([00-architecture.md](00-architecture.md)
> §9.2) shows the same shape.

**ADPT-001.** An adapter MUST ship a valid `mhs-adapter.json` and, when any
capability needs a mapping to a native call, a valid `mhs/bindings.json`. The
manifest MUST validate against [`adapter.schema.json`](../schema/adapter.schema.json);
each entry of `devices[]` MUST validate against
[`device.schema.json`](../schema/device.schema.json).

**ADPT-002.** `adapter_id` MUST be stable and immutable for the integration. It
MUST match `^[a-z0-9][a-z0-9_.-]{2,127}$` and SHOULD be
`<reverse-dns-or-org>.<repo>.<variant>`. Renaming an adapter is a new adapter.

**ADPT-003.** `family` MUST be one of the enum values in
[`adapter.schema.json`](../schema/adapter.schema.json) (§5); `other` is a
last resort and MUST be accompanied by a `title` and `description` in the
registry record.

---

## 2. Manifest reference

The table mirrors [`adapter.schema.json`](../schema/adapter.schema.json). All
objects are closed: unknown keys are validation failures.

| Field | Required | Content and rules |
|---|---|---|
| `$schema` | no | Schema URI for editors; ignored at runtime. |
| `mhs_adapter` | yes | `1.0` — the MHS adapter format version. |
| `adapter_id` | yes | §1, ADPT-002. |
| `title` | no | ≤160 chars, human. |
| `family` | yes | Bridge family (§5). |
| `source` | yes | `{repo, commit?, path?, license, redistributable?, local_path?}`. `repo` and `license` are required. |
| `runtime` | yes | `{kind: python|node|binary|docker|external, python?, install[], entry, env?, gpu?, requirements[]}`. |
| `lifecycle` | no | `{start{kind: process|in_process|external, command[], cwd?, env?}, ready{method: mhs.hello, deadline_ms}, stop{kind: terminate|mhs.session.close, grace_s}}`. |
| `devices` | yes | Full device manifests (§3). |
| `bridges` | no | `[{bridge_id, kind, version?, config?}]` — which bridge runtime(s) execute the adapter; `config.bindings_ref` names the bindings file. |
| `safety` | no | `{risk_class?, notes?, estop?}` — adapter-level summary; per-device safety is authoritative. |
| `conformance_target` | no | `{profile, level}` the adapter aims at. |
| `conformance` | no | Achieved claim pointer (report digest, issuer kind). |
| `evidence` | when runnable+ | `{state, read_by, entry_points[], verified_at?, notes?}`. |
| `stability` | no | `stable | fragile | experimental`. |
| `tier` | no | `A | B | C | D | X` (§9). |
| `redaction` | no | JSON pointers whose values never appear in evidence or logs. |
| `registry` | no | `{package_id, homepage, docs, maintainers[]}`. |
| `x-vendor` | no | Vendor extension object. |

**ADPT-004.** Each `devices[]` entry MUST be a complete device manifest,
including a concrete ULID `instance_id`. Adapters are packaged with a generated
instance ULID which the bridge MUST reuse in `hello`; if the bridge must generate a
new instance (first run, clone), it MUST persist it and MUST update the served
manifest consistently. A placeholder that changes every start makes replay
evidence and registry claims unstable and is a conformance failure.

**ADPT-005.** `devices[].mode` and the presence/absence of `fidelity` MUST follow
[`device.schema.json`](../schema/device.schema.json) and
[MHS-005](05-fidelity.md) §2. A simulated device MUST carry the fidelity contract
in the adapter manifest, not only at runtime.

**ADPT-006.** `source.repo` and `source.license` MUST be present and truthful.
`source.commit` MUST be pinned for every adapter whose `evidence.state` is
`runnable` or higher; unpinned runnable adapters MUST be rejected by the registry
(`MHS.ADAPTER.SOURCE_UNPINNED`).

**ADPT-007.** `source.redistributable` MUST reflect the licence, not the author's
intent. If redistribution is not allowed, the adapter MUST be distributed as a
patch/manifest that the user applies locally, and `local_path` MAY be used. An
adapter or a driver MUST NOT vendor, copy or redistribute upstream code; it names the
upstream by repository and pinned commit and imports it from the user's own
installation ([driver-profile.md](driver-profile.md) DRV-003, DRV-042).

**ADPT-008.** Running upstream code locally is allowed whatever its licence: a
bridge or loader MUST NOT refuse to execute an adapter, and the SDK does not, because
of a licence class. The licence is recorded truthfully (ADPT-006; `license_spdx` and
`license_class` in a task card and in `driver.lock.json`) and gates **publication**
only: a package whose licence class is network-copyleft, source-available,
proprietary or unknown is marked `publish_review: required` and its owner decides
before it is published. `MHS.ADAPTER.LICENSE_BLOCKED` is reserved for a deployment
policy that blocks an adapter; the 0.9 SDK never raises it. This resolves the
apparent conflict between ADPT-007 and ADPT-008.

**ADPT-009.** `runtime.install` MUST list deterministic, pinned installation steps
(version pins or lockfiles). `runtime.entry` MUST name the bridge/shim entry point
unambiguously (`module:function` or path). `runtime.env` MUST contain declarations
of required environment variables, never secret values.

**ADPT-010.** `lifecycle` MUST describe how the endpoint is started and stopped
when the manifest is used by a host or the conformance suite. Absent lifecycle
means "external process; start it yourself", and the registry MUST state that.

---

## 3. Device manifests inside adapters

**ADPT-011.** A device manifest inside an adapter MUST declare real
`capabilities[]` with `native` strings for every bound capability; a manifest
that lists capability classes it cannot map is a false declaration and MUST be
rejected at `evidence.state: "runnable"` or above (ADPT-043).

**ADPT-012.** `provenance` SHOULD link the device to the adapter
(`adapter_id`), the source repo/commit, and the code paths that implement it. It
is the audit trail a reviewer uses to decide whether to trust the mapping.

**ADPT-013.** A device manifest MUST carry `access` restrictions when the
upstream API can control multiple instruments: the adapter MUST NOT publish a
device that other users of the same software instance can also actuate.

**ADPT-014.** Resource state schemas MUST describe the device state as exposed by
the bridge, and `hash_exclusions` MUST list every volatile field (timestamps,
counters, `mono_ms`). A state schema with an undeclared volatile field produces
nondeterministic `state_hash` values and is a conformance failure for CL2+.

---

## 4. Capability bindings (`mhs/bindings.json`)

### 4.1 Shape

The document below is valid against [`bindings.schema.json`](../schema/bindings.schema.json):

```json
{
  "mhs_bindings": "1.0",
  "adapter_id": "org.example.robosuite-lift",
  "bindings": [
    {
      "device_id": "mhs://localhost:7401/robosuite/Lift",
      "capability_id": "cap.world.step.v1",
      "resource": "world",
      "binding": {
        "bridge": "gymnasium",
        "kind": "declarative",
        "native": "gymnasium.Env.step",
        "args": {
          "action": {"from": "input.action", "type": "integer", "enum_map": {"left": 0, "right": 1}}
        },
        "result": {
          "map": {"observation": "output.observation", "reward": "output.reward",
                  "terminated": "output.terminated", "truncated": "output.truncated"}
        },
        "constants": {"expected_revision": "ignore"},
        "units": {"input.action": {"from": "1", "to": "1", "factor": 1}},
        "clamp": {"input.action": {"min": 0, "max": 1}},
        "errors": [
          {"native": "^AssertionError$", "mhs_code": "MHS.DEVICE.PRECONDITION_UNMET",
           "retryable": false}
        ],
        "concurrency": "exclusive",
        "timeout_ms": 5000
      }
    }
  ]
}
```

**ADPT-020.** A binding MUST name `device_id`, `capability_id`, `resource`,
`bridge` and `native`. `native` MUST be the precise native symbol: module and
class/function, or protocol command/register. A natural-language description is
not a symbol.

**ADPT-021.** Declarative mappings are limited to the following primitives, all
of which MUST be declarative data:
`field path mapping`, `unit conversion` (factor/offset with explicit UCUM
from/to), `enumeration mapping`, `constant injection`, `clamping to declared
ranges`, `error-code mapping`. Anything else is a shim (§8).

**ADPT-022.** A binding MUST declare how the native result is shaped into the
capability output (`result.map`, mapping capability output fields to paths in the
native result) and, when the native call raises rather than returns, how errors
are mapped (`errors[]`, ordered by appearance; the first matching `native` regex
wins). Unmapped exceptions MUST surface as `MHS.ADAPTER.SHIM_FAILED` with a
redacted message (the native message is never forwarded); the other native signals
are `DriverFailed`, `Busy`, `OutcomeUnknown` and `Cancelled` ([core.md](core.md)
CORE-071). A result path of `output` or `output.$` is the raw native return and
`output.x` its member `x`; every `result.map` target MUST exist in the capability's
output schema, and a bridge returns the capability output itself, never an
`{"output", "state"}` wrapper. A native call that exceeds its `timeout_ms` or the
remaining execution budget is an **unknown** outcome (`MHS.OUTCOME.UNKNOWN`,
non-retryable), never a retryable failure. The canonical document is validated by
[`bindings.schema.json`](../schema/bindings.schema.json); the executable loader is
`mhs.bridge.bindings.load_bindings`. Every external input to that loader — a file
path, a JSON string or a plain mapping — MUST first be validated against the
schema and then normalized to the executable shape. The loader's internal
normalized shape is not an external document format and MUST NOT be accepted
from caller-controlled JSON/mappings. A valid `timeout_ms` MUST survive
normalization unchanged (never an absent/unbounded value); a loader that cannot
locate the normative schema set MUST fail closed.

**ADPT-023.** Unit conversion in a binding MUST be explicit and MUST use the
class's declared UCUM unit. A binding that passes native units through unchanged
because "they match" MUST say so (`from == to`); implicit identity conversion is
prohibited.

**ADPT-024.** A `clamp` is a limit, not a correction: an input outside it MUST be
rejected with `MHS.SAFETY.ENVELOPE_VIOLATION` before the native call, always, and
nothing is ever silently truncated or adjusted. The clamp bounds are checked by the
same engine as every other limit ([core.md](core.md) CORE-048), so a clamp inside a
wider envelope does not turn an out-of-range value into an in-range one: the value is
refused, because a silent clamp hides a dangerous intent and produces a receipt
describing an action the caller did not request. A clamp's `unit` is the unit after
the binding's conversion (the conversion's `to` unit); a mismatch is a manifest error
(`MHS.ADAPTER.MANIFEST_INVALID`).

**ADPT-025.** A binding MUST declare `concurrency` matching or stricter than the
class default and MUST declare a `timeout_ms` no greater than the class
`max_duration_ms`. A binding that can block indefinitely is invalid.

### 4.2 Mapping determinism

**ADPT-026.** Bindings MUST be side-effect free outside the native call: no
implicit retries, no "helpful" state fixes, no auto-homing. If a capability
requires a setup step (home, attach tip), that step MUST be a separate capability
or a declared precondition, not a hidden action inside mapping.

**ADPT-027.** A binding MUST NOT access network resources other than the ones
declared in `runtime`/device notes; a bridge that phones home is a supply-chain
defect.

---

## 5. Bridge families

A bridge is a reusable runtime per family; the adapter supplies mapping. The
family enum in [`adapter.schema.json`](../schema/adapter.schema.json) is
normative. Families, grouped:

| Group | Families | Typical mode | Notes |
|---|---|---|---|
| Simulation | `gymnasium`, `dm-env`, `mujoco`, `pybullet`, `isaac-sim`, `isaac-lab`, `isaac-gym`, `gazebo`, `webots`, `unity`, `sapien`, `drake`, `brax-mjx`, `habitat`, `airsim` | simulated | World/reset/step mapping; fidelity contract required. |
| Robotics middleware | `ros2`, `ros1` | hardware / simulated / hybrid | Topic/service/action mapping; careful with action cancellation and QoS. |
| Robot hardware SDKs | `lerobot-real`, `python-object` | hardware | Thin SDK wrapping; safety envelope is the adapter's responsibility. |
| Lab instruments | `sila2`, `opentrons`, `micromanager`, `flowchem`, `madsci`, `pylabrobot`, `bluesky-ophyd`, `qcodes` | hardware / simulated | Instrument command mapping, observables and progress. |
| Electrical / serial | `scpi-visa`, `serial` | hardware | SCPI query/response and raw serial framing; strict bounded reads. |
| Generic | `http-api`, `mcp-proxy`, `cli-process`, `docker`, `python-object` | any | Wrap a REST API, an existing MCP server, a CLI or a container. |
| Replay | `replay` | replay | Serves a recorded evidence bundle read-only. |
| Fallback | `other` | any | Requires registry review; not eligible for CL3+ without a documented bridge. |

**ADPT-030.** A bridge MUST implement the contract plane generically for its
family: it MUST NOT contain per-repository branches. Device-specific knowledge
belongs in the adapter manifest/bindings; a bridge with `if repo == …` is a driver
in disguise and MUST be reclassified as a shim or a new family.

**ADPT-031.** A bridge MUST implement deadlines and cancellation for every family
whose native API supports them, and MUST report `MHS.OPERATION.NOT_CANCELLABLE`
(or omit the cancellable flag) when it does not. It MUST NOT claim cancellability
it cannot honour.

**ADPT-032.** A bridge MUST be safe to run headless: no GUI requirement, no
interactive prompt, no unbounded log buffering. It MUST write logs to stderr (T1)
or the log stream, never to stdout on the protocol channel
([MHS-008](08-transports.md) §2).

**ADPT-033.** A bridge MUST report readiness through `mhs.hello` (or fail the
lifecycle `ready` deadline) and MUST NOT accept commands before its devices are
initialised and their current state is readable.

---

## 6. Lifecycle and readiness

### 6.1 Start

`lifecycle.start.kind`:

- `process` — the host launches `command`; the bridge serves T1 stdio or binds a
  port. `cwd` and `env` are defaults for the child.
- `in_process` — the bridge is imported into the host process (Python code API);
  it MUST NOT block the host's event loop.
- `external` — the endpoint already runs; the manifest documents how.

**ADPT-034.** For `process`, the adapter MUST specify a start command that works
from a clean checkout after `runtime.install`. The command MUST NOT require
interactive input, and its working directory MUST be declared when relative paths
are used.

### 6.2 Ready

**ADPT-035.** Readiness is `mhs.hello` answering within
`lifecycle.ready.deadline_ms`. A bridge that is not ready MUST either not bind its
transport or answer `hello` with a `MHS.DEVICE.NOT_READY` error and a retry hint.
Serving partial device lists before initialisation is prohibited.

**ADPT-036.** The `hello` reported by a bridge MUST match the adapter manifest's
device manifests for identity, mode, capabilities and safety. A mismatch is
`MHS.INTERNAL.SCHEMA_DRIFT` and MUST fail conformance.

### 6.3 Stop

**ADPT-037.** `lifecycle.stop.kind: "terminate"` MUST send SIGTERM, wait
`grace_s`, then force-kill; before terminating, the bridge MUST stop actuators to
their `safe_state` and close sessions. `stop.kind: "mhs.session.close"` MUST close
sessions gracefully and leave the device in its declared safe state.

**ADPT-038.** A bridge MUST NOT leave a device running after the process exits
where the device has a stop path (for example a pump or laser). Where it cannot
guarantee this (a fire-and-forget serial command), the adapter MUST declare the
limitation in `safety.notes` and the device profile.

---

## 7. Mapping rules in detail

### 7.1 Field paths

Paths are dot-separated names rooted at `input` or `output` (and `args` or `result`
in a binding's own sections), with array indices as `[n]` or `[*]` (all elements).
The grammar is that of [core.md](core.md) CORE-041 (`field`, `a.b`, `a[*]`, `a[3]`,
identifier segments only). A path that is exactly `input`, `output`, `args`, `result`
or `$` is the whole value; one `input.`, `output.` or `args.` prefix is stripped, after
which only `$` is the whole value again (`output.$`), and `input.output` and
`output.result` are ordinary fields. A mapping target MUST exist in the capability
schema; mapping to an undeclared field, or leaving a required output property
unmapped, is a validation failure at load time (`MHS.ADAPTER.MANIFEST_INVALID`),
except `sampled_at`, which the bridge stamps, and `revision`, which the endpoint adds.
A mapped path that is absent in the native return is `MHS.CAPABILITY.OUTPUT_INVALID`
unless the output schema makes the target optional.

### 7.2 Transforms

| Primitive | Form | Rules |
|---|---|---|
| Path map | `{"from": "input.a.b"}` | Read/write exact path; `[*]` fans out. |
| Unit | `{"from": "mm", "to": "m", "factor": 0.001}` or `{"from":"Cel","to":"K","offset":273.15}` | From/to MUST be the native and class UCUM codes. A `clamp` or envelope `unit` is the unit after this conversion (the `to` unit); a mismatch is a manifest error. |
| Enum | `{"map": {"closed": 0, "open": 1}}` | Total over the schema enum; unknown value → `MHS.ADAPTER.SHIM_FAILED`. |
| Constant | `{"value": true}` | Injects a fixed argument; MUST be documented in bindings. |
| Clamp | `{"min": …, "max": …}` | A limit: an input outside it is rejected with `ENVELOPE_VIOLATION`, never clamped (ADPT-024). |
| Error | `{"native": regex, "mhs_code": "MHS.…", "retryable": false}` | Ordered; first match wins; unmatched → `MHS.ADAPTER.SHIM_FAILED`. |

**ADPT-040.** Transforms MUST be total: every input path that the class declares
either maps to a native argument (including wildcards `[n]`/`[*]`), is injected
as a constant (`{"value": …}` or `constants{target: value}`), or is explicitly
declared `"unsupported": true` with a reason. An unmapped required input is a
manifest error (`MHS.ADAPTER.MANIFEST_INVALID`).

### 7.3 Native invocation forms

Bindings are declarative but the bridge needs an invocation shape, given by the
binding's `invoke` field (a member of the canonical bridge grammar; the closed
`bindings.schema.json` of this draft does not list it yet; open item in the 0.9 change notes,
`MHS/changes/WP-09.md`). The recognised forms are:

| `invoke` | Meaning |
|---|---|
| `call` (default) | call the native function or method; awaitables, futures and Status-like returns are awaited, bounded by the binding's `timeout_ms` and the remaining execution budget |
| `get`, `set` | read or write a property |
| `await` | the native MUST return an awaitable |
| `status` | the native MUST return a Status-like object (`wait(timeout)` or `done`/`success`) or an awaitable |
| `query`, `write` | request/response protocols such as SCPI or serial: the native is the target's request method, called with the formatted `command` template; `parse` turns a text reply into a value |

A native call whose bound expires is abandoned and is an unknown outcome (ADPT-022).
Long-running action protocols with feedback (ROS 2 actions, SiLA 2 commands) are
reserved for post-pilot bridges; anything else is a shim.

`parse` kinds are `raw`, `str`, `float`, `int`, `bool` and `regex` (`pattern`,
`group`). `bool` is strict: `1`, `ON`, `TRUE` (or the declared `true` token) and `0`,
`OFF`, `FALSE` (or the declared `false` token) are accepted, a custom `true` token
needs a `false` token, and any other reply is a parse error. An interlock reading
parses the whole reply: `int`, `float` and `regex` parses are anchored (`ERR 1` never
reads 1), a boolean `closed_when` needs a `bool` parse, and an unrecognised reply
reads `unknown`, never the closed value, so a reset stays refused
([core.md](core.md) CORE-072). String arguments with a line break or control
character (and `;` for SCPI) are refused `MHS.CAPABILITY.INPUT_INVALID`, so an input
cannot inject a second command; NaN and infinite inputs never reach a native call.

---

## 8. Shims

**ADPT-041.** A shim is REQUIRED when the native behaviour is not expressible with
the declarative primitives: stateful handshakes, response parsing, multi-call
sequences that must be one receipt, custom unit models, or vendor SDK callbacks.
The adapter MUST declare `binding.kind: "shim"` and `binding.shim` as a
`path:function` reference inside the adapter's `mhs/` directory.

**ADPT-042.** A shim MUST be small, dependency-light and deterministic given its
inputs and device state; it MUST NOT bypass the bridge's envelope or the receipt
machinery (the server core, not the shim, creates receipts).

**ADPT-043.** A shim MUST NOT import private upstream modules without declaring
`stability: "fragile"` and recording the imported symbols in
`evidence.entry_points`. A fragile adapter MUST be re-verified on every upstream
upgrade and the registry MUST show the fragility.

**ADPT-044.** A shim MUST fail closed: an unexpected native response produces a
`failed` receipt with `MHS.ADAPTER.SHIM_FAILED` and `data.details` naming the shim
and a redacted message. It MUST NOT translate an unknown response into success.

---

## 9. Integration tiers and effort

| Tier | Definition | Typical effort | Target level |
|---|---|---|---|
| **A** | Runnable backend with a clear entry point; manifest + bridge flags get you to CL2. | 0.5–2 dev-days | CL2–CL3 |
| **B** | Wrap-able library/SDK; needs a thin shim or family support. | 2–5 dev-days | CL2–CL3 |
| **C** | Engine or asset only; needs a scenario/model to become a device. | 5–15 dev-days | CL1–CL2 |
| **D** | Peripheral/tooling; not a device (visualiser, docs, dataset, CI helper). Not targeted. | — | — |
| **X** | Not integrable (empty upstream, inaccessible, licence-forbidden). | — | — |

**ADPT-050.** `tier` MUST reflect the work needed to reach the adapter's
`conformance_target`, not the repository's popularity. A tier MUST be accompanied
by evidence in the registry record (`integration.next_action`, `blockers`,
`scenario_required`).

**ADPT-051.** `tier: "D"` and `tier: "X"` repositories MUST NOT be listed as
MHS-capable; they MAY appear in the registry as catalogued context with
`capabilities_offered: []` and an explanation.

---

## 10. Adapter states

States are ordered and each transition is backed by evidence:

| State | Evidence | Meaning |
|---|---|---|
| `declared` | manifest validates | The mapping is claimed; not yet run. |
| `packaged` | manifest + bindings + shim packaged under `mhs/`; install steps pinned | Someone else could try it. |
| `runnable` | endpoint boots; `hello`/`devices`/`read` work; evidence `runtime_tested` | The mapping works for observation at least. |
| `conformant` | conformance report at target profile/level | The endpoint passes the executable suite. |
| `certified` | `conformant` + third-party verified report + registry signature | Independent verification. |

**ADPT-052.** `evidence.state` MUST be the highest state actually demonstrated in
the repository, and `evidence.read_by` MUST record how the mapping was verified
(`static_analysis | agent_read | runtime`). A manifest with `state: "runnable"`
and no runtime evidence is non-conformant and MUST be rejected by the registry
([MHS-007](07-registry.md) §6).

**ADPT-053.** "Certified" in the adapter state vocabulary means third-party
verified conformance, not product safety certification. Registry and site MUST
label it accordingly.

Driver packages ([driver-profile.md](driver-profile.md)) add two evidence states to
the registry record (`registry-record.schema.json`, `evidence.state`):
`contract_checked`, the acceptance gate passed on a fake or simulator backend (never
an MHS-Device level), and `hardware_checked`, an operator ran the hardware check
under supervision. Neither is a safety certification.

---

## 11. Packaging convention (`mhs/`)

An adapter is packaged either inside the upstream repository under `mhs/`, or in a
companion repository. The convention is:

```text
mhs/
  mhs-adapter.json      # manifest, validates against adapter.schema.json
  bindings.json         # capability mappings, "mhs_bindings": "1.0"
  devices/              # optional: one device manifest per file, if split
  shims/
    __init__.py
    <shim>.py           # declared shims only
  README.md             # how to run, what is verified, what is not
```

**ADPT-054.** The adapter MUST NOT modify upstream source when a shim suffices.
When an upstream patch is required, it MUST be delivered as a patch file under
`mhs/patches/` with the upstream commit it applies to, and `stability` MUST be
`fragile`.

**ADPT-055.** The manifest's `source.path` MUST point at the `mhs/` directory; the
registry MUST resolve the adapter files relative to that path only. Adapter code
MUST NOT write outside its working directory, the runtime's cache directory, or
paths declared in `lifecycle.start.cwd`.

**ADPT-056.** Adapters MUST be removable: deleting `mhs/` (and uninstalling the
declared runtime) MUST leave the upstream repository buildable and unchanged.

---

## 12. Ten worked micro-recipes

Each recipe is a compact integration sketch. Symbols are the upstream public API
surface; a recipe is not a substitute for the adapter's `native` entries. The recipes
are grounded in source-level reconnaissance of the corpus repositories (file:line
evidence for the native surfaces, kept with the private research material); the
registry's family recipes ([MHS-007](07-registry.md) §3) expand them per corpus family.

### 12.1 Gymnasium environment → MHS-Sim (tier A, E1, target CL2–CL3)

```yaml
family: gymnasium
mode: simulated
devices: one device, resource kind world.sim
bindings:
  cap.world.reset.v1  -> gymnasium.Env.reset(seed=seed)
  cap.world.step.v1   -> gymnasium.Env.step(action)      # action from input.action
  cap.world.state.v1  -> gymnasium.Env.unwrapped.state   # list -> observation
  cap.world.render.v1 -> gymnasium.Env.render(mode="rgb_array")
fidelity: {engine: <engine-name>, fidelity_level: F0/F1, determinism: seeded,
           seed_control: reset_required, timestep_ms: <dt>, reset: full,
           snapshot_restore: false, gaps: [...]}
safety: risk R0/R1; software e-stop = stop stepping; no permits
pitfalls: reset returns (obs, info) — map tuple explicitly; action space discrete vs Box;
          render may open a window with mode="human" (use rgb_array).
```

### 12.2 MuJoCo model → MHS-Sim (tier B, E2, target CL2–CL4)

```yaml
family: mujoco
mode: simulated
bindings:
  cap.motion.joint_position.v1 -> mujoco.MjModel/MjData + actuator ctrl write
  cap.world.step.v1            -> mj_step after mj_forward
  cap.world.state.v1           -> qpos/qvel/ctrl flattened into state schema
fidelity: {engine: mujoco, fidelity_level: F1, determinism: exact,
           timestep_ms: m.opt.timestep*1000, reset: full, snapshot_restore: true,
           gaps: ["no actuator saturation", "no sensor noise"]}
shim: needed to translate qpos to declared joints and to clamp ctrl to actuator ranges
pitfalls: do not expose qpos order as a contract; declare joint order in resource state.
```

### 12.3 Generic Python SDK object → MHS endpoint (tier B, E2)

```yaml
family: python-object
bridges: [{bridge_id: pyobj, kind: python-object, version: 1.0.0,
           config: {import: "vendor_sdk:Controller", ctor: {port: "${VENDOR_PORT}"}}}]
bindings:
  cap.measure.voltage.v1 -> Controller.get_voltage()  -> output.voltage
  cap.thermal.setpoint.v1 -> Controller.set_temperature(Celsius)  # unit map Cel->Cel
  cap.device.self_test.v1 -> Controller.bist() -> {passed, checks}
pitfalls: SDK connect() in constructor can block forever — do it in lifecycle.ready with a deadline;
          vendor exceptions must be mapped, not leaked.
```

### 12.4 ROS 2 node → MHS (tier B, E2–E3, hardware/sim)

```yaml
family: ros2
mode: hardware or simulated (declared per launch configuration, not per session)
bindings:
  cap.motion.cartesian_pose.v1 -> rclpy action MoveToPose; feedback -> progress
  cap.motion.stop.v1           -> publish zero velocity + cancel goal
  cap.sensing.image.v1         -> sensor_msgs/Image subscription, latest frame -> artifact
fidelity (sim only): {engine: "gazebo", fidelity_level: F1, ...}
pitfalls: action cancellation must be reported as cancelled only after the goal result;
          QoS reliability and queue depth must be declared; timestamps are not state.
```

### 12.5 SCPI instrument over PyVISA (tier B, E2, hardware)

```yaml
family: scpi-visa
mode: hardware
bindings:
  cap.measure.voltage.v1 -> "*MEAS:VOLT:DC?" query, parse float, unit V
  cap.identification... not a core class; use cap.device.describe.v1 with native "*IDN?"
  cap.actuation.gpio.v1  -> "OUTP:STAT {value}" write
fidelity: absent (hardware)
safety: risk R1; envelope from instrument manual; interlock impossible in SCPI — declare gap in safety.notes
pitfalls: read termination per instrument (\\n vs \\r\\n); response time unbounded — set timeout_ms and
          bounded reads; never issue "*RST" as part of a read.
```

### 12.6 Raw serial device (tier B, E2)

```yaml
family: serial
bindings:
  cap.actuation.pump.v1 -> write "PUMP:RATE {rate};RUN {dur}" then read "OK"
shim: response parser and command/ack state machine
safety: risk R1/R2; add a watchdog: if ack missing, stop and fail receipt
pitfalls: no framing standard — the shim must enforce line length and timeout;
          do not read unboundedly; declare the command vocabulary in notes.
```

### 12.7 SiLA 2 instrument / Opentrons connector (tier A–B, E2, hardware)

```yaml
family: sila2
bindings:
  cap.fluid.aspirate.v1 -> SiLA 2 command Aspirate with observable progress -> progress
  cap.sample.move.v1    -> SiLA 2 command MoveLabware
fidelity: absent; safety: R2, require permit for transfer, declare tip/liquid preconditions
pitfalls: SiLA 2 commands are long-running with observable execution state — map to operations,
          not to blocking calls; cancellation must be honoured through the SiLA command;
          feature definitions provide the native schema — use it to build bindings.
```

### 12.8 Micro-Manager / pymmcore imaging (tier B, E2, hardware)

```yaml
family: micromanager
bindings:
  cap.imaging.capture.v1    -> core.snapImage(); core.getImage() -> artifact
  cap.imaging.focus.v1      -> core.setPosition(stage); core.waitForDevice("Core")
  cap.imaging.illumination.v1 -> core.setProperty(shutter, "State", value)
  cap.sample.move.v1        -> core.setXYPosition(x, y)
pitfalls: device property names differ per configuration — declare the config in bindings constants;
          images are large — always artifact refs; exposure changes are state writes.
```

### 12.9 FlowChem or MADSci HTTP service (tier A–B, E1–E2)

```yaml
family: http-api (or flowchem/madsci family)
bindings:
  cap.actuation.pump.v1 -> POST /pump/infuse {rate: "1 ml/min", volume: "10 ml"}
  cap.measure.temperature.v1 -> GET /temperature -> float with unit Cel
  cap.thermal.setpoint.v1 -> PUT /temperature {value: 25}
pitfalls: the REST surface is per-component and per-device; one HTTP service may host many
          components -> expose one MHS device per addressable component; unit-bearing strings
          must be parsed and converted once, in the binding.
```

### 12.10 MCP server re-exposed with MHS semantics (tier B, E2)

```yaml
family: mcp-proxy
bridges: [{bridge_id: mcp, kind: mcp-proxy, config: {command: ["python","-m","lab.mcp"]}}]
bindings:
  cap.fluid.transfer.v1 -> MCP tool "transfer" with input JSON; structuredContent -> output
safety: R1 unless the MCP tool can move hardware; if so R2 and a permit
pitfalls: MCP tools are schema-typed but not hardware-typed — the adapter must add units, risk,
          preconditions, receipts; progress notifications map to MCP progress tokens;
          errors map from MCP isError into receipts, not transport exceptions.
```

**ADPT-060.** A recipe MUST live in the registry as a family recipe record, not
only in documentation, and MUST name the bridge flags used and the capabilities
mapped. The ten recipes above are the OpenMHS 0.9 baseline set; the registry's family
files expand them per corpus family ([MHS-007](07-registry.md) §3).

---

## 13. Security and licensing

**ADPT-061.** Adapter manifests MUST NOT contain secrets. Credentials are
environment variable names in `runtime.env` and are resolved by the operator.

**ADPT-062.** A bridge MUST NOT execute an adapter-provided `command` from
network input. `lifecycle.start.command` is operator-controlled configuration; the
only network-triggerable execution is a declared capability whose class explicitly
authorises it (`cap.compute.submit.v1`, `cap.process.run.v1`) and whose envelope
bounds it.

**ADPT-063.** Adapters MUST pin dependencies and MUST declare licences for the
adapter's own files. The registry MUST expose upstream licence and adapter licence
separately when they differ.

**ADPT-064.** A bridge MUST refuse a `native` symbol that is not reachable through a
public import path (leading underscore or private submodule) unless
`stability: "fragile"` and `evidence.entry_points` record the symbol; a private
symbol is a broken upgrade away from a false claim.

---

## 14. Requirements traceability

The conformance suite executes ADPT-005 (`traceability.json`); the other ADPT
requirements are profile obligations of a bridge or driver and are checked as
follows. No ADPT requirement other than ADPT-005 has a suite test of its own.

| Requirement | Checked by |
|---|---|
| ADPT-001, ADPT-006 | `mhs.adapter.load` validates `mhs-adapter.json` and its devices against the schemas; the driver gate G1 and G2 check the package files and the lock (pinned commit, licence). |
| ADPT-005 | Suite test ADPT-005: mode and fidelity presence. |
| ADPT-020 to ADPT-024 | The fail-closed bindings loader `mhs.bridge.bindings.load_bindings`, and gate G6 for ADPT-024 (an out-of-limit input is refused with zero native calls). |
| ADPT-007, ADPT-008 | No automated check: nothing refuses a load by licence class ([driver-profile.md](driver-profile.md) DRV-042). |
| ADPT-052 | Registry validation of the claimed evidence state ([MHS-007](07-registry.md)). |
| the rest | Review and the registry's validation; listed as out of profile for `MHS-Sim` in `applicability.json`. |

The complete conformance ladder is in [MHS-001](01-conformance.md); the registry
record format that stores adapter metadata is in [MHS-007](07-registry.md).
