# OpenMHS Optional Profiles

OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview ([appendix D](appendix-d-anthropic-mhs.md)).

| Field | Value |
|---|---|
| Document | profiles.md (normative index) |
| Status | OpenMHS 0.9 development draft |
| Editor | The OpenMHS Authors |
| Layer | index of the optional profiles; the rules live in the chapters it points to |
| Precedence | below [core.md](core.md) and [driver-profile.md](driver-profile.md) (README §1) |

[core.md](core.md) is what every endpoint and driver must satisfy. An **optional profile** adds behaviour the SDK implements but that a driver author does not need to know about: a driver never declares a profile, and an endpoint, host or registry claims one by implementing its chapter. This page lists the profiles, the chapters that define them, the requirement areas they own and where the reference implementation lives. Do not confuse them with the *conformance profiles* `MHS-Sim`, `MHS-Device`, `MHS-Bridge`, `MHS-Host` and `MHS-Registry` of [01](01-conformance.md), which name what a conformance report is about. The key words of RFC 2119 and RFC 8174 apply in the chapters, not in this index.

## 1. The profiles

| Profile | What it adds | Defined in | Requirement areas | Reference implementation |
|---|---|---|---|---|
| Sessions and Permits | `mhs.session.*`, grants and their limits, principals, permits and approvals, least privilege | [02](02-wire-protocol.md) §5, [04](04-safety.md) §6-§7 | `SESS`, `SAFE-030`..`SAFE-037` | `mhs.server` (sessions, permits), `mhs.client` |
| Evidence | the hash-chained evidence log, export and offline verification, retention, signing | [02](02-wire-protocol.md) §14, [04](04-safety.md) §8 | `EVID` | `mhs.evidence`, `mhs.canonical`, `mhs.run` (ledger check) |
| Sim, Fidelity and Replay | the dual-world rule, the fidelity contract, determinism, snapshot and restore, recordings and replay, hybrid authority, simulated and physical identity | [05](05-fidelity.md) | `MODE`, `FID` | `mhs.bridge.gymnasium`, `mhs.bridge.mujoco`, `mhs.bridge.replay`, `mhs.reference` |
| Events | subscriptions, `mhs.event` notifications, sequencing, gaps, backpressure, SSE and stdio delivery | [02](02-wire-protocol.md) §8 and §12, [08](08-transports.md) §3.2 | `EVT` | `mhs.server` (`SubscriptionHub`) |
| Host | what an agent harness does with an endpoint: discovery, tool surface, sessions, approvals, evidence ledger, prohibitions | [09](09-host-profile.md) | `HOST` | `mhs.mcp`, `mhs.run`; the OpenAI4S reference host in `integration/openai4s` is an informative annex |
| Registry | registry records, federation, trust, search, privacy, task cards and triage | [07](07-registry.md) | `REG`, `PRIV` | `mhs.registry`, `MHS/registry` |
| Governance | the RFC process, versioning, deprecation, disclosure, licensing, editorial rules | [10](10-governance.md) | `GOV` | none (process) |

**Composition is reserved.** `mhs.composition.run`, `cap.internal.composition_run.v1` and the `COMP` requirements ([02](02-wire-protocol.md) §15.1) describe a deterministic multi-step document executed by an endpoint. No 0.9 endpoint implements it: the reference endpoint answers `MHS.PROTOCOL.METHOD_NOT_FOUND`. The name and the requirements stay reserved so that a later profile can fill them without renumbering. Multi-step procedures in 0.9 are code files ([core.md](core.md) §10.3), which run on the client and cannot do more than the same calls made one by one.

## 2. Which layer is each chapter

README §1 orders the chapters below the Core and the Driver Profile. Each carries a `Layer` row in its header table; sections that belong to a different layer say so.

| Chapter | Layer |
|---|---|
| [01](01-conformance.md) conformance | core (levels, profiles, suite, reports) |
| [02](02-wire-protocol.md) wire protocol | core; §5 Sessions and Permits; §8 and §12 Events; §14 Evidence; §15.1 Composition (reserved) |
| [03](03-capability-registry.md) capability registry | core |
| [04](04-safety.md) safety | core (§1-§5, §9-§10); §6-§7 Sessions and Permits; §8 Evidence |
| [05](05-fidelity.md) fidelity | optional profile: Sim, Fidelity and Replay (MODE-001 to MODE-004 apply to every device) |
| [06](06-adapters.md) adapters | Driver Profile companion: adapters, bridges and bindings |
| [07](07-registry.md) registry | optional profile: Registry |
| [08](08-transports.md) transports | core (stdio, HTTP, MCP, CLI, code API); the WebSocket binding and the SSE delivery rules are Events |
| [09](09-host-profile.md) host | optional profile: Host |
| [10](10-governance.md) governance | optional profile: Governance |

## 3. Sim, Fidelity and Replay in one page

These rules are kept here because the Core points at them ([core.md](core.md) §8):

- **The twin rule.** A simulator is a different device from the hardware it models: it has its own `device_id` and `instance_id`, `mode` `simulated` or `hybrid`, and `models: [physical device_id]` when it models a specific device; a physical manifest never declares `models`; trust, conformance and approvals are never transferred between them; and a call never silently crosses the sim and hardware boundary (FID-045 to FID-049).
- **The fidelity contract.** A simulated or hybrid device carries `fidelity`: `engine`, `fidelity_level` (`F0` to `F3`), `determinism` (`exact`, `seeded`, `statistical`, `none`, with `seed_control`), `timestep_ms`, `realtime_factor`, `reset`, `snapshot_restore`, honest `gaps`, `authority` for a hybrid device, and `validation` for F3 (FID-001, FID-005, FID-006, FID-040 to FID-044). A fake backend is `F0` with gaps.
- **`fidelity.clock`.** An optional member that says who advances simulated time: `lockstep` (only commands advance it; the Gymnasium and MuJoCo family drivers declare it), `free_running` (the simulator runs on its own clock) or `external` (an outside scheduler). A host does not assume wall-clock pacing from `realtime_factor` (FID-013, FID-014).
- **Replay.** A replay device is read-only and serves recorded state; it advertises the `replay.seek` feature (MODE-005, FID-022 to FID-029).
