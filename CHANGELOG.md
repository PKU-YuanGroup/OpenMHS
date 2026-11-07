OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Changelog

All notable changes to OpenMHS are recorded here. OpenMHS 0.9 is a first public preview (2026-11-06): specification 0.9, SDK `0.9.0.dev0`,
wire revision 1. Nothing here is a safety certification; OpenMHS is a supervisory software contract and never replaces a
hardware emergency stop.

## 0.9.0.dev0, first public preview (2026-11-06)

The first optimized draft. An independent review of the earlier implementation (189 verified findings across the
specification, the SDK, the registry and 2,967 corpus repositories) led to the changes below. The review record is kept
privately; the per-step change fragments (`MHS/changes/`) are listed at the end of this file.

### November 2026: the driver corpus

- 842 registry cards are done: 746 driver packages pass the gate on fake `contract_checked` evidence, 85 are
  blocked (each with its reason and what would change it in `MHS/handoff/BLOCKED.md`) and 11 are proposed skips. No
  package was run on hardware and no `reviewed_by` signature exists: a hardware backend needs a human reviewer first.
- SDK and gate work behind those packages: companion-source citations and version-locked companion clones, sensed
  confirmation stops for simulators (with BL-17: every ROS 1 stamp sample is discarded, so six ROS 1 records are
  blocked until a fresh source exists), an isolated-process simulator host, file artifacts for direct drivers, list
  read-backs of several named elements, an opt-in hardware-companion stop checker, Gymnasium e-stop latch fixes and
  more; every record is in `MHS/changes/` and indexed at the end of this file.
- Licence: from this preview the code, schemas and tooling are MIT-licensed (copyright PKU-YUAN-Lab; earlier drafts
  said Apache-2.0); specification text and registry data stay CC BY 4.0.
- Driver packages were written by models (Claude, Grok, DeepSeek) and reviewed by a different model (Claude, Codex);
  each package's `RESULT.json` names its author and reviewers. The one remaining strict-collection warning is the
  thorlabs_mcm3000 citation of a vendor PDF page, which a machine cannot read.

### Safety and security: behaviour changes, read these first

These replace behaviour that failed open. A deployment or test that relied on the old behaviour must change.

- **Limits are enforced exactly as declared.** One limits engine checks every array element and every nested field, combines the
  class bounds, the binding limits, the device envelope and the operator's narrow-only overlay by taking the strictest, and
  refuses a misspelled key or a widening overlay at load time. A value outside a limit is refused as
  `MHS.SAFETY.ENVELOPE_VIOLATION` and never reaches the native layer. Before, limits on arrays and nested fields (joint
  angles, per-channel voltages, positions) were silently ignored.
- **Hardware inputs need a bound.** A numeric write or action input of a hardware or hybrid device at risk R1 or above must
  carry a sourced limit or be marked `operator_required`; until the operator supplies the bound every such call is refused
  with `MHS.SAFETY.LIMITS_UNSET`.
- **The e-stop latches first.** The latch is set before any I/O, running operations are cancelled, and the native stop runs in a
  bounded worker. A stop that fails or hangs gives a `failed` receipt `MHS.SAFETY.SAFE_STATE_UNREACHED`, the latch stays and the
  stop is retried. On stdio and MCP, e-stop and cancel take a priority path. The latch survives a restart (`state_dir`) and the
  server refuses to start unlatched if the latch file is unreadable.
- **Reset is guarded.** It is refused while nothing is latched, while any interlock is open or unknown, and while a stop attempt
  is still running. A hardware reset needs an operator principal. The MCP projection no longer exposes `reset` or `permit` by
  default, rejects a session id it did not open, and labels its sessions as agent sessions.
- **HTTP is hardened.** Host and Origin allowlists, a required `Content-Type`, no non-loopback bind without a token, and the
  schema endpoint serves only shipped schemas (before, it could read any local JSON file).
- **Receipts and revisions.** Reads never bump the revision; `expected_revision` is checked under the device lock; operation
  ids are full 26-character ULIDs; a bridge exception or native timeout becomes a `failed` or `unknown` receipt (`unknown`
  and not retryable on a timeout), never a silent success; clamping is replaced by rejection.
- **Long-running work.** The client deadline bounds only the wait for the response; a long-running action returns `running`
  with an `operation_id` and is not cancelled by the deadline. Exactly one terminal receipt per `command_id`.
- **Honest conformance.** The suite now tests the driver rather than the SDK: probes are chosen by catalogue verb (not by
  declaration order), inputs respect the envelope, outputs are validated, a hardware subject is never actuated without
  `--allow-actuation`, `SAFE-014` must see a safety refusal for every limited path, reports recompute and verify
  (`python -m mhs.conformance verify`), and `hello` no longer claims a conformance level for a device that has none.
- **Interlocks fail closed.** A malformed or unparsable interlock reply reads as unknown, which blocks like open.

### Added

- **Driver packages and the gate.** `mhs.driver`: a `Driver` base class with `@read`, `@write`, `@action`, `@estop`,
  `@interlock`, `@reset`; config-only family drivers for Python objects, serial, SCPI, Gymnasium and MuJoCo; a generated
  reference file (what a device measures, what can be adjusted, which limits are enforced); and the single acceptance command
  `python3 -m mhs.driver check <dir> --backend fake` (gates G1 to G9) with `new`, `reference`, `export` and `catalog`. Evidence
  from a fake is `contract_checked`, never an MHS-Device level.
- **Control surfaces.** `mhs serve`, `mhs run` (code files with a receipt ledger), `mhs discover`, a complete CLI with documented
  exit codes, a hardened MCP projection with policy flags, annotations and effective limits in the tool descriptions.
- **Read/write primitive.** `cap.device.configure.v1` and named parameters.
- **Registry as a work queue.** Deterministic triage of all 2,967 repositories (driver, family member, bridge runtime,
  reference, skip, recon), one task card per repository with a pinned commit and licence class, curated overrides, and a rank
  formula. The generated adapter skeletons were archived.
- **The DeepSeek handoff kit** (`MHS/handoff/`): prompt, playbook, waves, sandbox rules, review checklist, a 20-repository
  pilot, and the tools `dispatch`, `prepare`, `render_prompt`, `collect` and `show_refs`; four exemplar driver packages
  (`MHS/drivers/`) for a lab instrument, a SCPI instrument, a robot arm and a simulator.
- **Schemas and catalogue.** Typed limit rules, reference, site-limits, driver-lock, driver-result, check-report, task-card
  and discovery schemas; catalogue status and examples; a UCUM unit engine; a uniform error registry with a driver subset.
- **Open-source hygiene.** Apache-2.0 and CC-BY-4.0 licence files, `NOTICE`, `SECURITY.md`, `CODE_OF_CONDUCT.md`,
  `CONTRIBUTING.md`, an allowlist `.gitignore`, CI, `tools/oss_export_check.py`, and a wheel that carries its schemas.

### Changed

- **Identity.** The project is OpenMHS, an independent draft; it uses no Anthropic domain, name or branding. Identifiers live in
  `mhs/_ids.py`; the schema namespace is a placeholder (`https://openmhs.invalid/schema/0.9/`) until an owner picks one. The
  import name stays `mhs` and the wire stays revision 1.
- **Specification.** `core.md` and `driver-profile.md` are normative and short; the architecture overview is informative; the
  precedence rule no longer lets the stalest document win.
- **Registry.** Risk comes from the capability catalogue only; hardware-capable repositories are hardware first, never recorded as
  simulation only; the site generator takes its URL as a parameter and publishes nothing under Anthropic's domain.

### Removed

- The 1,967 generated adapter manifest skeletons (moved to the private archive), the registry's private risk table, launch
  commands that named modules which did not exist, the `mhs.registry.search` endpoint method (it always crashed), and dead
  helpers in the server. `mhs.conformance.report` no longer returns hard-coded passes: it returns the last stored report, or
  every test as not run.

### Known limits and post-pilot work

- The strict mode (catalogue enforcement, output validation, arming, operator-only hardware reset) is the default for driver
  packages and `mhs serve <dir>`; the legacy `MHSServer(...)` constructor stays in compatibility mode (warnings) for 0.9 and the
  default flips after the pilot.
- 246 task cards wait for helpers that do not exist yet (ROS 186, ophyd, tag-bridge, QCoDeS, Micro-Manager, PyLabRobot,
  HTTP, SiLA 2, MCP-client, MAVLink, LeRobot). Images, spectra and other large data have no artifact transport yet.
- Nothing has run against real hardware. All four exemplar drivers are model-written and not human-reviewed, so their hardware
  backends are refused by design; the container recipe in `MHS/handoff/SANDBOX.md` and the recon-task format are untested.

## Change fragments

One section per file in `MHS/changes/`. The fragments are the detailed record of each step.

<!-- BEGIN FRAGMENTS (generated by tools/build_changelog.py; edit the fragment, not this block) -->

### WP-01 — Identity, licensing, packaging and site rebrand

[`MHS/changes/WP-01.md`](MHS/changes/WP-01.md): Findings addressed: AF-01, OSS-01, OSS-02, OSS-03, OSS-10, OSS-12 (security policy and code of conduct), OSS-14 (version line, build debris ignores), SC-07 (namespace part), SC-09, SDK-05 (store part), SDK-13 (packaging part), SPEC-13 (SDK/site part), TESTS-07 (site freshness and capability-id gate), MISSED: "installed wheel drops conformance JSON", "CC BY grant purports to cover Anthropic quotations", "site build silently substitutes a synthetic registry".

### WP-02 — Catalogue, schemas and error registry (data contracts)

[`MHS/changes/WP-02.md`](MHS/changes/WP-02.md): Findings addressed: SPEC-13 and SC-07 (schema namespace, x- extension rule), SPEC-02 / SC-03 / DRV-02 / FIT-ROS-01 / SIM-01 (data half: typed, closed limit rules keyed by limit paths), SPEC-10 (unsatisfiable or unenforced schema MUSTs, too few examples), SC-04 / FIT-02 / FIT-07 / DRV-09 (verb in the manifest and the generic `cap.device.configure.v1` write class), SC-05 (deprecated protocol duplicates, experimental unused classes, resource-kind vocabulary), SC-06 (class input ...

### WP-03 — Safety library: limits engine, units, catalogue resolver, reference renderer, signals

[`MHS/changes/WP-03.md`](MHS/changes/WP-03.md): Findings addressed (library half; the server and bridges adopt these modules in WP-04/WP-05): SPEC-02, SC-03, SDK-03, DRV-02, FIT-03, FIT-ROS-01, SIM-01 (limit grammar, array/nested/per-element enforcement, typo-proof rules, intersection instead of last-writer-wins); SC-01, TESTS-02, SPEC-05, SC-02, AF-06 (the catalogue becomes binding: class verb, risk floor, permit, limits, kinds and a drift report); FIT-08 (lab-instruments and long-tail), FIT-ROS-07, SC-11 (unit table ...

### WP-04 — Server safety core and runtime semantics

[`MHS/changes/WP-04.md`](MHS/changes/WP-04.md): Sub-steps are serialized; each section below is one merged step.

### WP-05 — Bridges and pilot family runtimes

[`MHS/changes/WP-05.md`](MHS/changes/WP-05.md): Findings addressed: SIM-03 (Gymnasium/MuJoCo bridges cannot drive their families under the class contracts), FIT-09 and LAB-02 (no async, Status or property support in the python-object bridge; SCPI templates inexpressible), DRV-06 (a scalar native return cannot be mapped; misspelled result paths give empty outputs), FIT-ROS-08 (bridge half: result targets checked against the output schema), FIT-08 (lab instruments and long tail: `%` and compound units, async, timeouts) ...

### WP-06 — Driver API, adapter loader, acceptance gate and reference fixtures

[`MHS/changes/WP-06.md`](MHS/changes/WP-06.md): Findings addressed: DRV-01 / DRV-04 / REGQ-02 / SIM-02 (no per-repo driver contract and no loader: `mhs.adapter.load` now serves a driver directory or an `mhs-adapter.json`; the CLI `serve` wiring is WP-08), SC-04 / DRV-09 / FIT-02 (read/write primitives: `@read` parameters are `readOnly` state served by `mhs.resource.read`, `@write` parameters bind `cap.device.configure.v1`), DRV-10 / AF-02 (reference file built from the class: facts, tags, method names ...

### WP-07 — Conformance as an honest gate

[`MHS/changes/WP-07.md`](MHS/changes/WP-07.md): Findings addressed: DRV-08 and CONF-02 (the suite tested the SDK, not the driver: a do-nothing driver reached CL3, a no-op e-stop passed, garbage output passed), TESTS-03 and CONF-01 (level depended on capability order; input synthesis ignored the envelope, invented strings and could not vary inputs), CONF-05 and FIT-13 (hardware actuated without opt-in, hardware e-stops fired, permits self-issued, CL4 unreachable for hardware), CONF-06 (SAFE-014 only ever hit the schema ...

### WP-08 — Agent surfaces (MCP, CLI, code files, discovery) and the OpenAI4S reference host

[`MHS/changes/WP-08.md`](MHS/changes/WP-08.md): Findings addressed: SURF-01 (the model could self-permit and reset through MCP), SURF-02 (a foreign `session_id` was passed through; projection sessions were `service`), SURF-04 (every tool failed after the 3600 s session TTL), SURF-05 (input-schema refusals were JSON-RPC errors), SURF-06 (no annotations, no parameter descriptions, unbounded `mhs__evidence` and `mhs__devices`, `retryToken` rejected as "not a ULID"), SURF-07 (oldest protocol version answered, `resources/read` ...

### WP-09 — Specification realignment: one trustworthy spec for the SDK as it is

[`MHS/changes/WP-09.md`](MHS/changes/WP-09.md): MHS/spec now describes the 0.9 SDK as it behaves: a short normative `core.md` (87 `CORE-nnn` rules), a `driver-profile.md` and a `profiles.md`, a README that fixes the precedence (schemas, core, driver profile, chapters 01 to 10, appendices, informative `00-architecture.md`), the earlier followups written into their chapters, a `spec_doctest.py` that runs the examples and lints the ids, and no legacy names outside appendix D.

### WP-10 — Registry as catalogue + triage + task cards + overlays

[`MHS/changes/WP-10.md`](MHS/changes/WP-10.md): Findings addressed: REGQ-01 (no work-queue decision, no card shape), REGQ-05 and FIT-11 (keyword-regex capability hints), REGQ-08 and MISSED-7 (name collisions and corpus noise; simulator families need a structural marker), REGQ-09, FIT-09 and MISSED-6 (forks, duplicates, no commit pin, git remote as identity), FIT-01 (lab instruments and long tail: transports, frameworks, driver packs and non-devices modelled as devices), FIT-02 (robots/ROS) and FIT-ROS-13 (no integration ...

### WP-11 — Exemplar drivers and the DeepSeek handoff kit

[`MHS/changes/WP-11.md`](MHS/changes/WP-11.md): Step 11a builds two of the four exemplar packages at their real per-repo paths. Both pass `python3 -m mhs.driver check <dir> --backend fake`. The other two exemplars (xArm, Gymnasium) and the handoff kit (`MHS/handoff/**`, `MHS/drivers/README.md`, `CONTRIBUTING.md`) are later steps. An earlier attempt at these packages was lost in a temp-dir cleanup, so they were rebuilt here from the current tree.

### WP-12 — Archive, open-source allowlist, CI, export check and changelog

[`MHS/changes/WP-12.md`](MHS/changes/WP-12.md): Written by the orchestrator (not a subagent). Findings addressed: OSS-05, OSS-06, OSS-08, OSS-09, OSS-10, OSS-11, OSS-14, TESTS-05, TESTS-07, and the WP-12 follow-ups of WP-01, WP-04, WP-07, WP-08, WP-10 and WP-11.

### MERGE-B — WP-04 + WP-05 + WP-07 merged into the project tree

[`MHS/changes/MERGE-B.md`](MHS/changes/MERGE-B.md): This step merged three isolated workspaces back into the project root:

### MERGE-C2 — WP-08 and WP-10 merged into the project root

[`MHS/changes/MERGE-C2.md`](MHS/changes/MERGE-C2.md): Two isolated workspaces were merged into the repository root:

### RESIDUAL-B — open verifier issues of workflow B (WP-04, WP-05, WP-07)

[`MHS/changes/RESIDUAL-B.md`](MHS/changes/RESIDUAL-B.md): This step works through the 22 issues the independent verifiers of WP-04, WP-05 and WP-07 left open (the list kept in the private planning record; 7 of them blockers or majors). For each issue it did the following:

### CLEANUP — final clean-up of the site, the generated data and the leftovers of earlier steps

[`MHS/changes/CLEANUP.md`](MHS/changes/CLEANUP.md): Written by the orchestrator after the exemplar drivers, the handoff kit and the archive step. It closes the follow-ups that the earlier steps assigned to "final cleanup": the site no longer states a class status that the catalogue contradicts, its checker notices a stale build of any page and not only of a download, the Pages template works in a clean clone, and the sync tool refuses to prune a directory it did not create.

### FINAL-REVIEW — a rehearsal of the handoff kit, and the fixes it led to

[`MHS/changes/FINAL-REVIEW.md`](MHS/changes/FINAL-REVIEW.md): A model played the part of the one that will run the kit and integrated two pilot repositories (a serial R2 pump and a simulator) from the prompt and the playbook alone. Both packages passed the gate, and the run exposed gaps in the kit: a gate message that pushed towards falsifying a command, a `--strict` check that could never pass, a CI contradiction for driver pull requests, and prompt and playbook rules that were missing. They are fixed below. The record is ...

### Three ROS 1 sensed-stop records blocked until the BL-17 fix lands

[`MHS/changes/BL17-ROS1-SENSED-BLOCKS.md`](MHS/changes/BL17-ROS1-SENSED-BLOCKS.md): On 2026-11-06 the user chose to block darienmt/px4-sitl-ros-example, tfly6/opendrone and derek-th-wang/quadruped_ctrl (each a simulator at risk R2) on `SDK_BUG`, failing closed. The review of the p5-sdk-stampless unit (Codex gpt-6.1-sol, round 5, of work by Grok grok-4.7) accepted an SDK change for backlog item BL-17: on ROS 1 a topic latched by several publishers replays one stale sample per publisher on subscription, and the current discard-first rule discards only one, so ...

### BLINDVLA-ACTION — BlindVLA's fake serves ManiSkill's normalised action, -1 to 1 per value

[`MHS/changes/BLINDVLA-ACTION.md`](MHS/changes/BLINDVLA-ACTION.md): SQUINT-ACTION found that the fake of `gh.cognitiveaisystems/blindvla` (`Empty-v1`) serves the raw ranges of the Panda's `pd_joint_delta_pos` controllers as its action bounds, while the ManiSkill that BlindVLA vendors normalises both controllers (`MHS/changes/SQUINT-ACTION.md`, "Found, not fixed"). A reading of the clone at the pinned commit `06855fcb91d65c88ca351a2d45af0be860a91987` confirms it. The fake now serves `Box(-1, 1, (8,))` and clips and scales each value in ...

### BlindVLA mimic finger target

[`MHS/changes/BLINDVLA-MIMIC.md`](MHS/changes/BLINDVLA-MIMIC.md): The Empty-v1 fake assigned the gripper target to one finger and its negative to the other. Pinned `06855fcb91d65c88ca351a2d45af0be860a91987`, `ManiSkill/mani_skill/agents/controllers/pd_joint_pos.py:84-86`, broadcasts the same absolute action target to both joints. The fake now follows that relation, and tests check both coordinates for positive, zero and negative normalized commands.

### Companion locks: fetched companion clones, a stall read-back and a list-element read-back

[`MHS/changes/COMPANION-LOCKS.md`](MHS/changes/COMPANION-LOCKS.md): A companion source may now be a clone fetched at one pinned commit under `work/companions` and listed in its `LOCK.json` (a `lock` alias in the reviewed override). Gate G1 checks the clone's LOCK.json entry, HEAD, untracked files and write bits, and `tools/fetch_companions.py` puts the clones back, offline first. Two read-back forms join the companion-cited e-stop: a stall read-back (E1: the world's simulation time, read at least twice, must not advance) and a list-element ...

### Companion sources: a simulator package's stop may cite the simulator's own repository

[`MHS/changes/COMPANION-SOURCES.md`](MHS/changes/COMPANION-SOURCES.md): A task card may now declare reviewed companion sources (`companions`): corpus repositories cloned locally at their corpus-lock commit, such as the simulator whose world control is a simulator package's only stop. Only the e-stop binding, its read-back (`safety_bindings.safe_state`, which must read the stopped state back), the command of the one action declared `reenable=True` and facts may cite them, as `companion:<alias>/<path>:<LINE>`; the gate checks each clone, its HEAD ...

### Companion topic read-back: a fresh-sample world-state read-back, operator-run bridges and three gz-sim packages

[`MHS/changes/COMPANION-TOPIC-READBACK.md`](MHS/changes/COMPANION-TOPIC-READBACK.md): A companion-cited e-stop may now be confirmed by a boolean world-state flag read from fresh topic samples (E2: gz-sim's `WorldStatistics.paused`, since the reply of its world control confirms nothing), and a ROS driver may declare the ros_gz bridges its operator must run (E3: `operator_bridges`, checked by gate G7 and listed in the reference file). Three gz-sim simulator packages pass with the WorldControl pause as their stop: linorobot2, VRX and TortoiseBot. ...

### Preserve missing-stop semantics in hardware-driver fakes

[`MHS/changes/DRIVER-UNBOUND-SAFETY.md`](MHS/changes/DRIVER-UNBOUND-SAFETY.md): A direct Driver with a hardware control contract and no declared stop could return an achieved safe state when served through its fake backend. The server used simulated-mode software-latch behavior even when an earlier native call remained active. Direct Driver safety status now explicitly reports unconfirmed safety for hardware profiles with resolved risk R1 or higher and effectful capabilities, writable parameters or a reset hook but neither an estop method nor a ...

### DUCKIETOWN-ACTION — gym-duckietown's two action values are a velocity and a steering angle

[`MHS/changes/DUCKIETOWN-ACTION.md`](MHS/changes/DUCKIETOWN-ACTION.md): GYM-SPACE-REF-2 found that `gh.duckietown/gym-duckietown` calls the two values of the `MultiMap-v0` action wheel torques, while the environment the package serves reads them as a velocity and a steering angle (`MHS/changes/GYM-SPACE-REF-2.md`, "Found, not fixed"). A reading of the clone at the pinned commit `c76a7fec7f739db4f624f40ca83ce99383665558` confirms it. The Facts, `facts.md`, the driver's docstring and the fake now say so, and the fake converts the two values to ...

### Duckietown status messages

[`MHS/changes/DUCKIETOWN-MESSAGES.md`](MHS/changes/DUCKIETOWN-MESSAGES.md): The MultiMap fake used internal episode codes in `info["Simulator"]["msg"]`. Pinned upstream `c76a7fec7f739db4f624f40ca83ce99383665558`, `src/gym_duckietown/simulator.py:1681,1687-1705`, exposes an empty string during an episode and explanatory sentences for an invalid pose or the step limit. The fake now copies those observable messages.

### Emergency-stop retry and confirmation lifecycle

[`MHS/changes/ESTOP-CONFIRMATION.md`](MHS/changes/ESTOP-CONFIRMATION.md): An initial failed native stop now keeps its required background retry even when writing the initial receipt fails. The recording error still reaches the caller. A background confirmation settles its original command ids only after its own receipt is recorded; an evidence failure retains those ids and the bounded retry instead of escaping from the worker and claiming confirmation in a finally block.

### Observe one coherent e-stop attempt in the confirmation regression

[`MHS/changes/ESTOP-CONFIRMATION-TEST-ORDERING.md`](MHS/changes/ESTOP-CONFIRMATION-TEST-ORDERING.md): The back-to-back e-stop regression now takes the server lock when checking that the background retry has completed. The retry can enter its native bridge before its newly created attempt is published; an unlocked observer could combine the previous completed attempt with the new bridge call count and start its next request too early. That request could legitimately share the still-pending successful retry, causing a false test failure.

### ESTOP-FAILSAFE — an emergency stop is recognised by what it asks for, and a stop that names no device stops them all

[`MHS/changes/ESTOP-FAILSAFE.md`](MHS/changes/ESTOP-FAILSAFE.md): Two behaviours of the e-stop that the specification realignment (WP-09) recorded as known limitations, decided by the maintainer in the fail-safe direction: a request whose `method` is `mhs.safety.estop` now latches although its JSON-RPC envelope is defective, and an e-stop that names no device on an endpoint that serves several devices stops every device instead of being refused. An e-stop without the bearer token stays refused. Written test first ...

### Flag stale limit prose during package collection

[`MHS/changes/FACTS-LIMITS-ADVISORY.md`](MHS/changes/FACTS-LIMITS-ADVISORY.md): Package `facts.md` pages can retain obsolete action-space references after their generated contracts change. The collector now adds a bounded `FACTS_LIMITS_REVIEW` advisory when a recognizable limits paragraph disagrees with the step-bound references in `reference.json`. It does not interpret arbitrary prose as proof, change limits, accept warnings, or replace source review.

### Input-bound permits for the positive operator-overlay control

[`MHS/changes/G6-OPERATOR-OVERLAY-PERMIT.md`](MHS/changes/G6-OPERATOR-OVERLAY-PERMIT.md): G6 used to reject a correctly declared action with both an operator-required input and a required permit: its positive overlay supplied the permitted input but omitted the permit. The positive simulated-endpoint control now obtains one bounded, exact-input, single-use permit through the stock server before sending the command. Missing and partial overlays still run without permits and must refuse before any actuation.

### Controlled GNSDO fake clock

[`MHS/changes/GNSDO-CONTROLLED-CLOCK.md`](MHS/changes/GNSDO-CONTROLLED-CLOCK.md): The package fake previously read the host clock. Crossing a second between two post-reset reads changed only ptime_time and state_hash, causing intermittent TSAFE-001 failures in G8 or nested G9. A stock RPC boundary probe reproduced that change with no new command or revision.

### Explicit Gym checkpoints and retained restore ownership

[`MHS/changes/GYM-CHECKPOINTS.md`](MHS/changes/GYM-CHECKPOINTS.md): Gym snapshot support now requires a declared, backend-specific bounded JSON profile. The native checkpoint is part of the served world resource and normal state hash. The endpoint validates identities, aliases, digests, exact resource keys and schemas before effects, then checks the actual restored state. Hidden state, RNG completeness and native determinism still require package evidence. See `sdk/docs/gym-checkpoints.md` for the profile and its limits.

### GYM-DICT-KEYS — preserve literal native keys through bounded action fields

[`MHS/changes/GYM-DICT-KEYS.md`](MHS/changes/GYM-DICT-KEYS.md): Gymnasium Dict action keys such as `action.left_arm` previously became the limit path `action.action.left_arm`. The limit engine interpreted the dots as nested fields, although the native environment expected one literal key. A literal key could also collide with a genuinely nested Dict member.

### GYM-FACTS-SOURCE — the Gymnasium facts.md pages give the step bound's present source

[`MHS/changes/GYM-FACTS-SOURCE.md`](MHS/changes/GYM-FACTS-SOURCE.md): DUCKIETOWN-ACTION found 117 Gymnasium `facts.md` pages whose Limits paragraph still gives the step bound the source `<env_id>:action_space`, which no reference has said since GYM-LIMITS (`MHS/changes/DUCKIETOWN-ACTION.md`, "Found, not fixed"). Each page now says what its `reference.json` says: no source and the fake backend's space, or `upstream_code` and the line its `action_space_ref` cites. Only `facts.md` changed, and no gate digest did.

### GYM-LIMITS — action limits derived from a Gymnasium fake no longer claim to be upstream code

[`MHS/changes/GYM-LIMITS.md`](MHS/changes/GYM-LIMITS.md): Wave D found that the Gymnasium bridge labels every bound it derives from an action space `source: upstream_code`, whichever object supplied the space (`MHS/changes/WAVE-D.md`, "Found, not fixed"). Driver packages render their reference on the fake backend, so 207 Gymnasium packages published their fake's action bounds as upstream code, many of them placeholder test data. Those bounds now carry no source and a `ref` that names the fake backend. A driver can cite the upstream ...

### GYM-LIVE-ROUTES — asynchronous environments, dm_env environments and resets that integrate physics

[`MHS/changes/GYM-LIVE-ROUTES.md`](MHS/changes/GYM-LIVE-ROUTES.md): Three opt-in Gymnasium profiles serve live routes the synchronous bridge could not: an owned event loop for `async def step` (`asyncio_owned_loop_v1`), a dm_env adapter that maps a `TimeStep` explicitly (`dm_env_v1`), and physics timing for resets that integrate physics, with an explicit checkpoint opt-out. Undeclared backends keep their behavior and gate digests. ProjectAirSim and SimplerEnv pass after review; RoboPianist stays blocked.

### GYM-SPACE-REF — Gymnasium packages whose fake copies the upstream action space cite it

[`MHS/changes/GYM-SPACE-REF.md`](MHS/changes/GYM-SPACE-REF.md): GYM-LIMITS stopped the Gymnasium bridge labelling the bounds it derives from a package's fake `upstream_code` and added `GymnasiumDriver.action_space_ref` for a fake that copies the upstream space (`MHS/changes/GYM-LIMITS.md`). This change read the fake's action space of each of the 207 packages against the upstream line it cites: 71 now set `action_space_ref`, so their step bounds are `upstream_code` again with a ref that G4 checks. G4 learnt to read `Discrete(n)`.

### GYM-SPACE-REF-2 — G4 reads `np.ones(n)`, and four placeholder action spaces turn out to be copies

[`MHS/changes/GYM-SPACE-REF-2.md`](MHS/changes/GYM-SPACE-REF-2.md): GYM-SPACE-REF set `action_space_ref` on 71 of the 207 Gymnasium packages and left two lines of work (`MHS/changes/GYM-SPACE-REF.md`, "Found, not fixed"). This change takes both. G4 now reads `np.ones(n)` and `-np.ones([n])` as 1 and -1, so gymfc and pybullet_multigoal_gym cite their `Box`, and a model review of five fakes that marked an upstream-looking space `# placeholder` found four exact copies, which now cite their line; squint's is not the upstream's space.

### Helper integration: five helper families, the AS7265x repair and reviewed card corrections

[`MHS/changes/HELPER-INTEGRATION.md`](MHS/changes/HELPER-INTEGRATION.md): This change composes the work of five agents into one source change against the registry state of 2026-11-04: the `mcp-client`, `pylabrobot`, `qcodes`, `ophyd` and `tag-bridge` families become available, each with one exemplar package; gate G4 reads a literal `range()`; the AS7265x package is repaired; registry overrides gain reviewed capability classes and an added publication review; and reviewed overrides re-route the cards the helper work found misrouted. Every exemplar ...

### Helper wave 1: the 33 cards the helper integration opened, reviewed by Claude (21 contracts, 11 blocks, 1 skip)

[`MHS/changes/HELPER-WAVE-1.md`](MHS/changes/HELPER-WAVE-1.md): The [helper integration](HELPER-INTEGRATION.md) made 33 cards dispatchable: 10 Ophyd, 8 QCoDeS, 5 PyLabRobot, 3 MCP-client and 3 tag-bridge cards, two cards re-routed to python-object, and the re-dispatch of the code-less blocked packages neuracoreai/bigym (now Gymnasium) and misterblue/ros2_raspicam_node (now an R0 camera card through a reviewed capability-class override). The user had authorized these author runs on 2026-11-04 together with the ROS wave. DeepSeek ...

### Helper wave 2: the 15 waiting cards the phase-2 routing opened, reviewed by Claude and verified by a second model (9 contracts, 6 blocks)

[`MHS/changes/HELPER-WAVE-2.md`](MHS/changes/HELPER-WAVE-2.md): The model review of the waiting cards (phase 2, 2026-11-05) routed 15 of the 62 cards that waited for a helper family at takeover to reviewed direct-driver overrides (`MHS/registry/overrides/waiting-routing.json`): lab robots and liquid handlers (Opentrons OT-2 and Flex, the ad-sdl OT-2, PAL, BMG and UR modules, a Tecan Fluent connector, an OT-2 controller over SSH), stages and microscopes (openuc2 ImSwitch, the TALOS transfer stage, a pycromanager control app, a Prior ...

### Finite HTTP workflow helper

[`MHS/changes/HTTP-FINITE-HELPER.md`](MHS/changes/HTTP-FINITE-HELPER.md): This change adds a config-only `HttpDriver` and an `ot2-run-v1` request profile. A controlled injected peer executes the complete selected upload/create/play/poll/pause/resume/cancel workflow, owned-run observations and bounded log artifacts. The helper validates finite requests and responses, keeps late requests and IDs owned after local timeouts, reserves an independent stop lane, and defers transport cleanup until retained requests return. No native HTTP transport exists ...

### Detach public in-process replies from retained receipts

[`MHS/changes/INPROCESS-RECEIPT-OWNERSHIP.md`](MHS/changes/INPROCESS-RECEIPT-OWNERSHIP.md): An in-process caller could mutate nested output, error or artifact metadata in a returned response and change the server's subsequent command replay or operation lookup. The original artifact bytes and stored descriptor remained intact, but the retained response no longer matched the committed evidence.

### Klintan USB camera primary image and calibration observations

[`MHS/changes/KLINTAN-PRIMARY-CAMERA.md`](MHS/changes/KLINTAN-PRIMARY-CAMERA.md): OpenMHS is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

### L04 — cited local ones-based Box bounds

[`MHS/changes/L04-ONES-CITATIONS.md`](MHS/changes/L04-ONES-CITATIONS.md): G4 previously read `high = np.ones(n)` as showing 1, but a following `Box(-high, high)` did not show -1. It now adds bounded source-only AST evidence for a complete cited span containing these straight-line definitions and their Box. The existing literal, angle, unit, magnitude, Discrete and direct-ones readers retain their previous behavior.

### Local image artifacts

[`MHS/changes/LOCAL-IMAGE-ARTIFACTS.md`](MHS/changes/LOCAL-IMAGE-ARTIFACTS.md): Image capabilities can now return a primary image that the calling MCP session can retrieve. The endpoint owns an explicitly enabled, bounded temporary store; drivers stage bytes through their execution context and return the corresponding image reference. Successful output validation and evidence recording publish the grant and retained receipt together. Failed, cancelled, expired or invalid executions cannot expose staged bytes. Replaying a command reuses its original ...

### Finite MCP controlled-client helper

[`MHS/changes/MCP-CONTROLLED-CLIENT.md`](MHS/changes/MCP-CONTROLLED-CLIENT.md): OpenMHS is independent and is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

### Owned controlled MCP stdio and terminal proof revocation

[`MHS/changes/MCP-OWNED-STDIO.md`](MHS/changes/MCP-OWNED-STDIO.md): OpenMHS is independent and is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

### Declared MuJoCo checkpoint state

[`MHS/changes/MUJOCO-CHECKPOINTS.md`](MHS/changes/MUJOCO-CHECKPOINTS.md): MuJoCo resource reads and snapshots now share one declared world document, including a readonly native checkpoint. The endpoint validates its schema, identity, digests and public/native component agreement before restore and verifies the actual restored state. Complete native integration state and an explicitly limited basic fallback are separate profiles. State API presence no longer implies seeded or exact determinism. See `sdk/docs/mujoco-checkpoints.md`.

### MUJOCO-UNBOUNDED-ACTUATORS — a MuJoCo actuator without a control range is operator_required, not unbounded

[`MHS/changes/MUJOCO-UNBOUNDED-ACTUATORS.md`](MHS/changes/MUJOCO-UNBOUNDED-ACTUATORS.md): The MuJoCo bridge published an actuator that declares no control range inside the derived `action.ctrl` limit as

### NATIVE-FILE-ARTIFACTS — files a native wrote, published as artifacts; the dodal Eiger re-authored

[`MHS/changes/NATIVE-FILE-ARTIFACTS.md`](MHS/changes/NATIVE-FILE-ARTIFACTS.md): A direct driver can now publish files that its native wrote to disk through the endpoint's existing local artifact store: `mhs.file_artifacts.NativeFileDirectory` reads bounded regular files of one declared directory without following links and publishes one file or a deterministic ZIP bundle, with the sha256 and media type of every file in the receipt. With it, and with a stop route that carries the operator's `DetectorParams`, the blocked dodal Eiger package (triage class ...

### Record nested native operations

[`MHS/changes/NESTED-NATIVE-RECORDING.md`](MHS/changes/NESTED-NATIVE-RECORDING.md): G6 previously recorded only calls and assignments at the root native object. Calls such as `self.native.motor.stop()` escaped its observation and failure injection. The recorder now shares one event log across nested proxies, preserves identity/aliases and cycles, records full member paths, unwraps arguments, and uses bounded cached proxies.

### Gate digests of sixteen code-less records re-recorded

[`MHS/changes/NONPASSING-DIGEST-REFRESH.md`](MHS/changes/NONPASSING-DIGEST-REFRESH.md): Sixteen records that hold no driver code (eight `skip-proposed` with `NOT_A_DEVICE`, seven `blocked` with `HELPER_MISSING` and one `blocked` with `NO_HARDWARE_FREE_PATH`) carried a gate digest that no longer matched the gate's output, or no gate entry at all. On 2026-11-06 the orchestrator, Claude (claude-opus-5-5, a model and not a human), re-ran the gate of each in the project's validation environment and recorded what it reports: the gate fails G1, G2, G3 and G9 because ...

### Required permit for the positive cancellation control

[`MHS/changes/OP011-CANCELLATION-PERMIT.md`](MHS/changes/OP011-CANCELLATION-PERMIT.md): OP-011 previously sent its positive cancellable operation without a required permit, so a correctly declared permit-gated action failed before returning an operation handle. The control now resolves the selected capability and resource together, obtains the exact-input permit through the existing suite policy, and then runs the unchanged cancellation assertions. Missing, wrong-input and reused permits still return PERMIT_INVALID with zero native or bridge actuation. Ungated ...

### Explicit operation cancellation respects the admitted binding

[`MHS/changes/OPERATION-CANCELLABILITY.md`](MHS/changes/OPERATION-CANCELLABILITY.md): The server previously signalled every running operation when a client called `mhs.operations.cancel`, even when its capability declared `cancellable: false` or omitted the flag. It now captures the resolved binding's cancellation flag when starting the operation and returns `MHS.OPERATION.NOT_CANCELLABLE` before changing a noncancellable operation's event, reason or receipt. Bindings remain identified by capability and resource; later capability metadata does not grant ...

### Ophyd and QCoDeS family exemplars

[`MHS/changes/OPHYD-QCODES-EXEMPLARS.md`](MHS/changes/OPHYD-QCODES-EXEMPLARS.md): The registry families `ophyd` and `qcodes` waited on `helper:ophyd` and `helper:qcodes` although `OphydDriver` and `QcodesDriver` existed: no complete package showed the helpers on a real upstream class. Each family now has an exemplar package that passes the full G1-G9 fake gate and `collect.py --strict`, and the triage family table names the helper and the exemplar.

### P5-BACKLOG-PACKAGES-BL04 — item 12 on passing packages outside the ROS family

[`MHS/changes/P5-BACKLOG-PACKAGES-BL04.md`](MHS/changes/P5-BACKLOG-PACKAGES-BL04.md): Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 as unit BL-04 extended of p5-backlog-packages. Run id `ext-p5-backlog-packages--bl04-20261105`. `reviewed_by` stays null on every package. No hardware, ROS graph, Gazebo, PX4 or simulator run is claimed. Every gate result below is `contract_checked` on the package fake.

### P5 backlog packages, BL-12

[`MHS/changes/P5-BACKLOG-PACKAGES-BL12.md`](MHS/changes/P5-BACKLOG-PACKAGES-BL12.md): Unit BL-12 repairs two passing lab packages. Both used to send `*RST` from the safety reset. The clones do not state the effect on the output, so SAFE-042 (`MHS/spec/04-safety.md`, the paragraph that begins "SAFE-042") forbids that call as a reset step. Each package now offers the upstream reset method as an ordinary command. The safety reset sends nothing. `authored_by` is unchanged. `reviewed_by` stays null. Evidence is `contract_checked` on the fake backend. No hardware ...

### BL-19: gh.squad-lab/qcdrivers e-stop confirmation

[`MHS/changes/P5-BACKLOG-PACKAGES-BL19.md`](MHS/changes/P5-BACKLOG-PACKAGES-BL19.md): Repair of the passing package `MHS/drivers/labs/squad-lab__qcdrivers` (gh.squad-lab/qcdrivers, device `squad-ad75019-mux`, risk R1). Grok (grok-4.7, a model and not a human) did this repair on 2026-11-05, run `ext-p5-backlog-packages--bl19-20261105`. `authored_by` stays the re-author recorded in `driver.lock.json` (claude-opus-5-5, run `p3-reauthor-qcdrivers`, 2026-11-05). `reviewed_by` stays null. This is not a re-author: the package directory was not moved aside. The ...

### P5 backlog packages, BL-22: no unpause on three Gazebo simulations

[`MHS/changes/P5-BACKLOG-PACKAGES-BL22.md`](MHS/changes/P5-BACKLOG-PACKAGES-BL22.md): Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 for unit BL-22. `reviewed_by` stays null. This unit repairs three passing packages. It does not re-author them: `authored_by` is unchanged, and no package directory was moved aside.

### Gymnasium e-stop latch and stop-attempt generation

[`MHS/changes/P5-BACKLOG-SDK-GYM.md`](MHS/changes/P5-BACKLOG-SDK-GYM.md): GymnasiumBridge now gives each e-stop and each close a stop-attempt id, so only the latest attempt can clear an unconfirmed stop, and it latches effectful world calls until the safety reset. A confirmed stop still has an empty safety status. Reads stay available. This records BL-20 and BL-24. No passing package digest is intended to move.

### P5-BACKLOG-SDK-MISC — Ophyd export family, stop-once stamp test, MuJoCo recipe note

[`MHS/changes/P5-BACKLOG-SDK-MISC.md`](MHS/changes/P5-BACKLOG-SDK-MISC.md): Grok (grok-4.7, a model and not a human) authored this record on 2026-11-05. `reviewed_by` stays null. Run id `ext-p5-backlog-sdk--misc-20261105`. This unit is BL-01, BL-02 and BL-03 from `result.backlog.items`. BL-20 and BL-24 are another unit; their files were left alone. No driver package was re-authored, and no `RESULT.json` note was edited.

### P5-GZ-PAUSE for gh.ad-sdl/sdl-simulation

[`MHS/changes/P5-GZ-PAUSE-AD-SDL-SDL-SIMULATION.md`](MHS/changes/P5-GZ-PAUSE-AD-SDL-SDL-SIMULATION.md): Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 as the external unit `ext-p5-gz-pause--ad-sdl__sdl-simulation` (run id `ext-p5-gz-pause--ad-sdl__sdl-simulation-20261105`). This is a repair of the package authored by deepseek-v4.1-flash:1017 (run ros-wave-c-144, 2026-11-05). `authored_by` is unchanged. `reviewed_by` stays null. No hardware, Gazebo world, ROS graph or human review is involved: the gate evidence is `contract_checked` on the fake only.

### Gazebo pause for coppolam/ros_mav_swarm_simulator

[`MHS/changes/P5-GZ-PAUSE-COPPOLAM-ROS_MAV_SWARM_SIMULATOR.md`](MHS/changes/P5-GZ-PAUSE-COPPOLAM-ROS_MAV_SWARM_SIMULATOR.md): The coppolam/ros_mav_swarm_simulator package now pauses the Gazebo world with `/gazebo/pause_physics` and confirms it by reading `/gazebo/get_physics_properties` with `pause == true`. It does not unpause. The fake-backend gate passes (evidence `contract_checked` only). Risk stays R2, and `publish_review` stays required because the licence is NOASSERTION.

### cpezzato/panda_simulation: Gazebo world pause with a paused-flag read-back

[`MHS/changes/P5-GZ-PAUSE-CPEZZATO-PANDA_SIMULATION.md`](MHS/changes/P5-GZ-PAUSE-CPEZZATO-PANDA_SIMULATION.md): `robots/cpezzato__panda_simulation` moves from `blocked` (`HELPER_MISSING`) to `pass`. The stop is the fetched Kinetic companion service `/gazebo/pause_physics`, confirmed only when `/gazebo/get_physics_properties` reads `pause` true. The package offers no unpause. Evidence is `contract_checked` on the fake backend. No Gazebo process, ROS graph, hardware run or human review is claimed. `reviewed_by` stays null.

### rodriguesrenato/warehouse_robot_simulation: Gazebo world pause with a paused-flag read-back

[`MHS/changes/P5-GZ-PAUSE-RODRIGUESRENATO-WAREHOUSE_ROBOT_SIMULATION.md`](MHS/changes/P5-GZ-PAUSE-RODRIGUESRENATO-WAREHOUSE_ROBOT_SIMULATION.md): `robots/rodriguesrenato__warehouse_robot_simulation` moves from `blocked` (`HELPER_MISSING`) to `pass`. The stop is the already fetched Melodic companion service `/gazebo/pause_physics`, confirmed only when `/gazebo/get_physics_properties` reads `pause` true. The package offers no unpause. Evidence is `contract_checked` on the fake backend. No Gazebo process, ROS graph, hardware run or human review is claimed. `reviewed_by` stays null.

### P5-GZ-PAUSE: wh200720041/warehouse_simulation_toolkit

[`MHS/changes/P5-GZ-PAUSE-WH200720041-WAREHOUSE_SIMULATION_TOOLKIT.md`](MHS/changes/P5-GZ-PAUSE-WH200720041-WAREHOUSE_SIMULATION_TOOLKIT.md): The warehouse Gazebo package now passes with a companion-cited world pause and a paused-flag read-back. It offers no unpause. This is a repair of the existing package: `authored_by` stays `deepseek-v4.1-flash:1017`, run `ros-wave-c-059`, date 2026-11-04. `reviewed_by` stays null.

### P5-GZ-TOPIC — justyx404/spot_gazebo_ros2

[`MHS/changes/P5-GZ-TOPIC-JUSTYX404-SPOT_GAZEBO_ROS2.md`](MHS/changes/P5-GZ-TOPIC-JUSTYX404-SPOT_GAZEBO_ROS2.md): Repair of `gh.justyx404/spot_gazebo_ros2` only (unit `ext-p5-gz-topic--justyx404__spot_gazebo_ros2-20261105`). The other packages of item p5-gz-topic are other units. `authored_by` stays `deepseek-v4.1-flash:1017`, run `ros-wave-c-071`, 2026-11-04. `reviewed_by` stays null. This is not a re-author, so the package directory was not moved aside.

### shouryash007/robothon-2026 stays blocked: the simulator major is not proved

[`MHS/changes/P5-GZ-TOPIC-SHOURYASH007-ROBOTHON-2026.md`](MHS/changes/P5-GZ-TOPIC-SHOURYASH007-ROBOTHON-2026.md): The integrator did not apply this unit's package files. Codex's package decision was not accept (`robots/shouryash007__robothon-2026` decision `block`). The package directory stays at snapshot-6. The sections below are the unit's own account.

### P5-GZ-TOPIC: will0103/ros2-mobile-manipulator world-pause read-back

[`MHS/changes/P5-GZ-TOPIC-WILL0103-ROS2-MOBILE-MANIPULATOR.md`](MHS/changes/P5-GZ-TOPIC-WILL0103-ROS2-MOBILE-MANIPULATOR.md): Repair of `MHS/drivers/robots/will0103__ros2-mobile-manipulator` only. The e-stop is the gz-sim world pause, confirmed by a fresh `WorldStatistics.paused` read-back (E2), and the two ros_gz bridges the operator must run are declared (E3). No unpause is offered.

### P5-MIXED — qdeyna/ur10e_2f140_topic_based_ros2_control: fake-hardware controller switch

[`MHS/changes/P5-MIXED-QDEYNA-UR10E_2F140_TOPIC_BASED_ROS2_CONTROL.md`](MHS/changes/P5-MIXED-QDEYNA-UR10E_2F140_TOPIC_BASED_ROS2_CONTROL.md): The blocked package `gh.qdeyna/ur10e_2f140_topic_based_ros2_control` (wave 5, rank 83) was a `MujocoDriver` of the vendored FZI `cartesian_controller_simulation` test robot. Its gate failed G5 and G8, status `blocked`, `blocked_on` `HELPER_MISSING`, digest `sha256:fe236da5862f7d209712acf535faf7c8f57e05afebbe07786af25a0ee3157a66`. That tree was moved aside. This unit re-authored it as a `RosDriver` for the repository's UR10e on the fake-hardware path only, with the E4 ...

### P5-MIXED-ROBIN-SHAUN-XTDRONE — world-pause e-stop for the XTDrone position subset

[`MHS/changes/P5-MIXED-ROBIN-SHAUN-XTDRONE.md`](MHS/changes/P5-MIXED-ROBIN-SHAUN-XTDRONE.md): Repair of `robots/robin-shaun__xtdrone` (`gh.robin-shaun/xtdrone`, pin `671f3d45b22bfe4b7f2b23ae8d4251f3172781b3`) by grok-4.7, a model and not a human, on 2026-11-05, run id `ext-p5-mixed--robin-shaun__xtdrone-20261105`. This is a repair. `authored_by` stays the existing model record (`deepseek-v4.1-flash:1017`, run `mhs-ros-continuation-20261102-b-retry1-019`, date 2026-11-04) in `driver.lock.json`. `reviewed_by` stays null. Evidence is `contract_checked` on the ROS-free ...

### P5 mixed: uthiras/scara_robot_ros2 E1 stall read-back

[`MHS/changes/P5-MIXED-UTHIRAS-SCARA_ROBOT_ROS2.md`](MHS/changes/P5-MIXED-UTHIRAS-SCARA_ROBOT_ROS2.md): Repair of `gh.uthiras/scara_robot_ros2` only. `authored_by` stays `deepseek-v4.1-flash:1017`, run `ros-wave-c-118`, date 2026-11-05. `reviewed_by` stays null. This note is by Grok (grok-4.7, a model and not a human) on 2026-11-05. No hardware, Gazebo, ROS graph or human review was run. The passing evidence is the fake gate, `contract_checked`.

### PF400 arm through ad-sdl/pf400_module_ros, re-authored (2026-11-05)

[`MHS/changes/P5-REAUTHOR-AD-SDL-PF400_MODULE_ROS.md`](MHS/changes/P5-REAUTHOR-AD-SDL-PF400_MODULE_ROS.md): Authored by Grok (grok-4.7, a model and not a human), run `ext-p5-reauthor--ad-sdl__pf400_module_ros-20261105`. Codex reviews. `reviewed_by` stays null. Nothing in this package was taken from the stopped trees `development/p5-reauthor` or `development/ext-p5-reauthor.fast-stopped`: both still held only the old `RESULT.json` and `task.json`. The old blocked package was copied to this unit's `originals/` and moved to `moved-aside/`; it was not deleted, and its notes were not ...

### P5 re-author: agilexrobotics/ugv_gazebo_sim

[`MHS/changes/P5-REAUTHOR-AGILEXROBOTICS-UGV_GAZEBO_SIM.md`](MHS/changes/P5-REAUTHOR-AGILEXROBOTICS-UGV_GAZEBO_SIM.md): Unit of item p5-reauthor. Author: grok-4.7 (a model, not a human), run `ext-p5-reauthor--agilexrobotics__ugv_gazebo_sim-20261105`, 2026-11-05. `reviewed_by` stays null. Nothing was taken from the stopped Claude tree or the stopped Grok tree; both had no file newer than their base manifests.

### P5-REAUTHOR-UNITY-TECHNOLOGIES-UNITY-ROBOTICS-HUB — plan-only RosDriver for the Niryo pick-and-place tutorial

[`MHS/changes/P5-REAUTHOR-UNITY-TECHNOLOGIES-UNITY-ROBOTICS-HUB.md`](MHS/changes/P5-REAUTHOR-UNITY-TECHNOLOGIES-UNITY-ROBOTICS-HUB.md): The blocked Unity Robotics Hub card (`gh.unity-technologies/unity-robotics-hub`, triage class D) now has a plan-only `RosDriver` package. One exclusive command asks the tutorial service `niryo_moveit` for four pick-and-place trajectories and returns them. `executed` is always false. Nothing in this package starts Unity, the gripper, or `sim_real_pnp.py`. No SDK change was made. The registry card and `task.json` were not edited, so the card stays `package_status` blocked ...

### Literal composition of a ROS endpoint, and the Webots demo sensed stop

[`MHS/changes/P5-SDK-NAMES-LITERAL.md`](MHS/changes/P5-SDK-NAMES-LITERAL.md): Written by Grok (grok-4.7, a model and not a human) on 2026-11-05, run `ext-p5-sdk-names--literal-20261105`. This is unit part (1) of item p5-sdk-names only: gate G7 accepts a ROS endpoint built from string literals joined by `+`, and `robots/jackymao1999__webots_demo` uses that for its sensed stop. Parts (2) and (3), a name composed from a deployment value and a multi-element read-back, are other units and are not in this tree. Not integrated. `reviewed_by` stays null. No ...

### P5-SDK-NAMES-MULTI — one E4 read-back for several named elements

[`MHS/changes/P5-SDK-NAMES-MULTI.md`](MHS/changes/P5-SDK-NAMES-MULTI.md): Round 1 of the ext-integrator-B review left the package directory and the companion-sources-lock entry out. The final package decision is block, and the admission rule requires accept. The E4 list predicate in the SDK remains.

### Runtime ROS names from one declared deployment value

[`MHS/changes/P5-SDK-NAMES-RUNTIME.md`](MHS/changes/P5-SDK-NAMES-RUNTIME.md): Unit `ext-p5-sdk-names--runtime` (part 2 of item p5-sdk-names only). A simulated `RosDriver` may bind an endpoint the clone builds with one `+` of a deployment value and a string literal. Gate G7 checks that concatenation. The package `robots/stdr-simulator-ros-pkg/stdr_simulator` is re-authored under user decision 3 (2026-11-05; the orchestrator remapped "Claude authors" to Grok). It publishes one `geometry_msgs/Twist` for one already-spawned robot and stops only when that ...

### Arrival freshness, ROS 1 stamp refusal, and three simulator packages

[`MHS/changes/P5-SDK-STAMPLESS-ALL.md`](MHS/changes/P5-SDK-STAMPLESS-ALL.md): Authored by grok-4.7 (a model and not a human; run ext-p5-sdk-stampless--all-20261105). `reviewed_by` stays null. Nothing here was taken from the stopped Claude attempt at `development/p5-sdk-stampless` or the stopped Grok attempt at `development/ext-p5-sdk-stampless.fast-stopped`: both trees matched their base manifests. Evidence is fake `contract_checked` only. No hardware run, no simulator run, and no human review is claimed. This record does not publish any package.

### Sensed-confirmation stop for autorally/autorally

[`MHS/changes/P5-SENSED-AUTORALLY-AUTORALLY.md`](MHS/changes/P5-SENSED-AUTORALLY-AUTORALLY.md): Repair of `MHS/drivers/robots/autorally__autorally` (`gh.autorally/autorally`), simulated card only (SAFE-049, CORE-088). `driver.lock.json` keeps `authored_by` `deepseek-v4.1-flash:1017`, run `ros-wave-c-133`, and `reviewed_by` null. The package directory was not moved aside. This file is the repair record, not a second authorship.

### P5 sensed-confirmation stop: epfl-lasa/kuka-rviz-simulation

[`MHS/changes/P5-SENSED-EPFL-LASA-KUKA-RVIZ-SIMULATION.md`](MHS/changes/P5-SENSED-EPFL-LASA-KUKA-RVIZ-SIMULATION.md): Repair of the simulated ROS 1 package `MHS/drivers/robots/epfl-lasa__kuka-rviz-simulation` (SAFE-049, CORE-088). The package stays a repair: `driver.lock.json` `authored_by` is still `deepseek-v4.1-flash:1017`, run `ros-wave-c-116`, date 2026-11-05, and `reviewed_by` stays null. One model-review paragraph was appended to `RESULT.json` notes. No human review is claimed.

### P5 sensed-confirmation stop for fdcl-gwu/uav_simulator

[`MHS/changes/P5-SENSED-FDCL-GWU-UAV_SIMULATOR.md`](MHS/changes/P5-SENSED-FDCL-GWU-UAV_SIMULATOR.md): Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 in this package unit's copy. This is a repair of the existing package. `authored_by` stays `deepseek-v4.1-flash:1017` (run `ros-wave-c-025`, date 2026-11-04). `reviewed_by` stays null. No hardware, ROS graph, Gazebo process, simulator run or human review is claimed. The gate evidence is `contract_checked` on the ROS-free fake.

### P5 sensed stop: larics/decentralized_multi_robot_exploration

[`MHS/changes/P5-SENSED-LARICS-DECENTRALIZED_MULTI_ROBOT_EXPLORATION.md`](MHS/changes/P5-SENSED-LARICS-DECENTRALIZED_MULTI_ROBOT_EXPLORATION.md): Repair of the blocked package `gh.larics/decentralized_multi_robot_exploration` to a sensed-confirmation stop (SAFE-049, CORE-088). This unit is that package only. `authored_by` stays `deepseek-v4.1-flash:1017`, run `ros-wave-c-114`, date 2026-11-05. `reviewed_by` stays null. Written by Grok (grok-4.7, a model and not a human) on 2026-11-05, run `ext-p5-sensed--larics__decentralized_multi_robot_exploration-20261105`. Evidence is fake `contract_checked` only. No ROS graph ...

### Sensed-confirmation stop for maskor/webots_ros2_spot

[`MHS/changes/P5-SENSED-MASKOR-WEBOTS_ROS2_SPOT.md`](MHS/changes/P5-SENSED-MASKOR-WEBOTS_ROS2_SPOT.md): Repair of `gh.maskor/webots_ros2_spot` only. `authored_by` stays the deepseek record in `driver.lock.json` (`deepseek-v4.1-flash:1017`, `ros-wave-c-031`, 2026-11-04). `reviewed_by` stays null. This file was written by Grok (grok-4.7, a model and not a human) on 2026-11-05. No hardware run, Webots run, ROS graph, or human review is claimed. The gate evidence is `contract_checked` on the fake backend.

### P5 sensed confirmation for okermorgant/map_simulator

[`MHS/changes/P5-SENSED-OKERMORGANT-MAP_SIMULATOR.md`](MHS/changes/P5-SENSED-OKERMORGANT-MAP_SIMULATOR.md): Repair of `MHS/drivers/robots/okermorgant__map_simulator` only. The package keeps its `authored_by` (`deepseek-v4.1-flash:1017`, run `ros-wave-c-091`). `reviewed_by` stays null. Written by Grok (grok-4.7, a model and not a human) on 2026-11-05. No hardware, ROS graph, map_simulator process, rosbridge connection or human review is claimed. The evidence is `contract_checked` on the ROS-free fake.

### Sensed-confirmation stop for robotis-git/turtlebot3_simulations

[`MHS/changes/P5-SENSED-ROBOTIS-GIT-TURTLEBOT3_SIMULATIONS.md`](MHS/changes/P5-SENSED-ROBOTIS-GIT-TURTLEBOT3_SIMULATIONS.md): Repair of `MHS/drivers/robots/robotis-git__turtlebot3_simulations` only (SAFE-049, CORE-088). The package was blocked `HELPER_MISSING`: the pinned `turtlebot3_fake_node` has no acknowledged stop. It now declares `safety_bindings["sensed_stop"]` for the fake node in simulated mode. `RESULT.json` status is `pass`. Evidence is fake `contract_checked` only. No ROS graph, simulator process, or hardware was run.

### panda_gz_moveit2 stays blocked: the Galactic bridge cannot carry the Fortress pause

[`MHS/changes/P5B-COMPANIONS-NEW-ANDREJORSULA-PANDA_GZ_MOVEIT2.md`](MHS/changes/P5B-COMPANIONS-NEW-ANDREJORSULA-PANDA_GZ_MOVEIT2.md): `andrejorsula/panda_gz_moveit2` stays `blocked` (`HELPER_MISSING`). The fetched lock companions were re-read. The Fortress world pause would hold physics while it is held, but the ROS 2 Galactic bridge this package pins cannot call that service or read `WorldStatistics.paused`. Deactivating the effort trajectory controller still writes the last effort, so it is not a stop. No unpause was added. No driver, lock, card or registry override changed. `reviewed_by` stays null.

### P5B companions, new fetches: ifra-cranfield/ros2_robotsimulation stays blocked

[`MHS/changes/P5B-COMPANIONS-NEW-IFRA-CRANFIELD-ROS2_ROBOTSIMULATION.md`](MHS/changes/P5B-COMPANIONS-NEW-IFRA-CRANFIELD-ROS2_ROBOTSIMULATION.md): The integrator did not apply this unit's package files. Codex's package decision was not accept (`gh.ifra-cranfield/ros2_robotsimulation` decision `block`). The package directory stays at snapshot-6. The sections below are the unit's own account.

### p5b-dualmode: cambel/ur3 served only as the ur_gripper_gz simulation

[`MHS/changes/P5B-DUALMODE-CAMBEL-UR3.md`](MHS/changes/P5B-DUALMODE-CAMBEL-UR3.md): Written by Grok (grok-4.7, a model and not a human) on 2026-11-05. `reviewed_by` stays null. No hardware was attached, no Gazebo or ROS graph was started, and no human review is claimed. The passing evidence is the fake backend, `contract_checked`.

### Hardware stop cited to one fetched companion

[`MHS/changes/P5B-HW-COMPANION-ALL.md`](MHS/changes/P5B-HW-COMPANION-ALL.md): Round 1 of the ext-integrator-B review left the package directory and the waiting-routing override out. The final package decision is block, and the admission rule requires accept. The opt-in hardware-stop checker in the SDK remains, tested with fixtures rather than the shipped package.

### P5B inference and companion message types

[`MHS/changes/P5B-INFERENCE-ALL.md`](MHS/changes/P5B-INFERENCE-ALL.md): Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 as the external item p5b-inference, run `ext-p5b-inference--all-20261105`, in this working copy. Nothing in the stopped Claude attempt (`development/p5b-inference`) or the stopped Grok attempt (`development/ext-p5b-inference.fast-stopped`) was copied. No hardware run, simulator run, ROS graph or human review is claimed. Evidence for the two repaired packages is `contract_checked` on the fake backend. ...

### Package composition: several typed resources in one driver package

[`MHS/changes/PACKAGE-COMPOSITION.md`](MHS/changes/PACKAGE-COMPOSITION.md): One driver package can now serve capabilities whose catalogue classes accept different resource kinds, such as a stable image (`sensor.camera`) and a stable point cloud (`sensor.depth`), as one device with several typed resources. A driver declares `extra_resources` and binds an action to one with `Action(resource=...)` or `@action(..., resource=...)`; each binding resolves against its own resource's kind on the core's existing multi-resource device, and the device keeps one ...

### PILOT-1 — the first session of the 20-repository pilot, and the fixes it led to

[`MHS/changes/PILOT-1.md`](MHS/changes/PILOT-1.md): A DeepSeek model (`deepseek-v4.1-flash:1017`) ran the typed prompt of `MASTER-PROMPT.md` in an interactive harness over the first three pilot cards. All three packages passed the gate (`gh.martinhjelmare/leicacam` in 3 runs, `gh.benpruitt/tecancavro` in 4, `gh.huggingface/gym-aloha` in 3) in about 30 minutes, with `authored_by` naming the model and `reviewed_by` null. `collect.py` printed no `RESULT_UNTRUSTED`, `RESULT_DIGEST_STALE` or `EXEMPLAR_RESIDUE`; nothing outside the ...

### PILOT-2 — the second pilot session, a model review of the first eight packages, and ten cards at a time

[`MHS/changes/PILOT-2.md`](MHS/changes/PILOT-2.md): The same DeepSeek model (`deepseek-v4.1-flash:1017`) ran five more pilot cards in an interactive harness: `gh.huggingface/gym-pusht` (1 gate run), `gh.pymeasure/pymeasure` (1), `gh.ni/nidaqmx-python` (3), `gh.ap/python-seabreeze` (3) and `gh.python-ivi/python-ivi` (1), in about an hour. All five passed the gate; nothing outside their driver directories changed.

### First public preview: specification 0.9, SDK 0.9.0.dev0 (2026-11-06)

[`MHS/changes/PUBLIC-PREVIEW-0.9.md`](MHS/changes/PUBLIC-PREVIEW-0.9.md): The owner decided on 2026-11-06 to publish a first public preview with the current version numbers (specification 0.9, SDK `0.9.0.dev0`, wire revision 1); raising the SDK to 0.9.0 is later work, because the SDK version is part of every gate's stable digest. The preview contains the specification, the JSON Schemas, the standard-library SDK, the conformance suite, the capability catalogue, the registry and the driver corpus: 842 done cards (746 passing packages, 85 blocked ...

### Finite PyLabRobot liquid-handler helper

[`MHS/changes/PYLABROBOT-FINITE-HELPER.md`](MHS/changes/PYLABROBOT-FINITE-HELPER.md): This change adds a config-only `PyLabRobotDriver` with one request profile, `plr-liquid-handler-v1`, for an upstream whose control interface is a PyLabRobot `LiquidHandler` front end, used directly or held by an upstream object. A package declares one immutable `PlrProfile`: the handler's attribute path, its setup and teardown, the channel count, the lines that switch PyLabRobot tip and volume tracking on, a finite labware allowlist (each name cited at the line that creates ...

### Finite primary-pixel camera helper candidate

[`MHS/changes/PYMMCORE-FINITE-CAMERA.md`](MHS/changes/PYMMCORE-FINITE-CAMERA.md): The SDK candidate adds an explicitly owned single-camera fixture workflow through the selected ImSwitch `acquireSingleFrame` shape. Complete mono8, mono16 and RGB8 arrays become lossless PNG artifacts through stock endpoint/MCP publication. Geometry/exposure capture inputs assert current settings, finite configuration requires operator limits and verified readback, and native hardware/simulator admission remains refused.

### Retained Python native execution

[`MHS/changes/PYTHON-NATIVE-RETENTION.md`](MHS/changes/PYTHON-NATIVE-RETENTION.md): PythonObjectBridge previously treated the caller's timeout as the end of a nested synchronous setter. A stock server reproduction returned UNKNOWN, then reported a successful e-stop and safety reset while the setter was still blocked. Releasing it changed the output after two stop calls. The runtime now retains the whole native completion chain, including Status/Future/awaitable returns and cancellation cleanup. A deadline bounds the caller; it does not prove native ...

### Retain Python safe-state actions through validated completion

[`MHS/changes/PYTHON-SAFE-ACTIONS.md`](MHS/changes/PYTHON-SAFE-ACTIONS.md): A declared argument-free Python safe-state action now uses the independent retained safety lane. Its role comes from the resolved driver model, not caller metadata. This lets a native stop dispatch while an earlier ordinary setter remains active, while correctly refusing to report achieved safety until all earlier native execution has settled.

### Explicit QCoDeS and Ophyd helper contracts

[`MHS/changes/QCODES-OPHYD-HELPERS.md`](MHS/changes/QCODES-OPHYD-HELPERS.md): QcodesDriver compiles declared Parameter get/set bindings over the retained Python bridge; OphydDriver compiles explicit classic Signal get/set bindings and deployment units. Construction performs no native discovery or connection. Reads call the declared measurement operation, and writes retain the entire native completion rather than substituting a cache or dispatch acknowledgement. Copied model/runtime configuration preserves each instance's declared fields, limits ...

### Declared re-enable after a reset, and a declared terminal e-stop

[`MHS/changes/RE-ENABLE-AND-TERMINAL-STOP.md`](MHS/changes/RE-ENABLE-AND-TERMINAL-STOP.md): A device may now declare how it recovers from an e-stop. `safety.estop.reenable` names the one command that re-enables a device whose stop leaves it disabled: the latch refuses it, the reset of such a device only releases the latch, and conformance test TSAFE-001 sends it after the reset and before its recovery command. `safety.estop.terminal` states why a device's native stop cannot be undone without a new native session: after that stop the endpoint refuses every reset ...

### Four blocked packages re-authored: SQUAD AD75019 switch, LTAMP PyBullet PR2, Galago OT-2, scanning SQUID microscope

[`MHS/changes/REAUTHOR-PHASE-3.md`](MHS/changes/REAUTHOR-PHASE-3.md): Four packages that the blocked-package triage sent to re-authoring (class D of `TRIAGE-2.json`, with scanning-squid's recon route) are rewritten by Claude and pass the gate: gh.squad-lab/qcdrivers (a decorated driver that reports each route, reads it back with the firmware's `STAT?` and drains both `*RST` lines), gh.caelan/ltamp (the PyBullet `PBController` path, whose world advances only inside driver calls), gh.sciencecorp/galago-tools (the pack's OT-2 tool, re-selected by ...

### RECON-A — the 680 recon cards of wave 4, and the override entry symbols they needed

[`MHS/changes/RECON-A.md`](MHS/changes/RECON-A.md): The 680 recon cards of wave 4 (`untriaged`: triage could not tell what the repository is) ran unattended like the driver waves: `run_wave.py --recon --jobs 10` with the DeepSeek Harness in headless mode (`deepseek-v4.1-flash:1017`, one fresh session per card, batch `rA`), 680 cards in 1 hour 45 minutes, a median of 78 seconds per card (90th percentile 162 s, longest 402 s), none timed out. Each run wrote one proposal file under `MHS/handoff/recon/` and no driver. The harness ...

### RECON-B — the 285 recon cards of wave 6, and git hooks kept out of the clones

[`MHS/changes/RECON-B.md`](MHS/changes/RECON-B.md): The recon cards of wave 6 (`untriaged` cards that need a GPU, Windows or an external engine) ran unattended as recon wave A had (`MHS/changes/RECON-A.md`): `run_wave.py --recon --wave 6 --jobs 10` with the DeepSeek Harness in headless mode (`deepseek-v4.1-flash:1017`, batch `rB`). 285 cards ran in 58 minutes, a median of 108 seconds per card (90th percentile 188 s, longest 345 s), and none timed out; the 286th card of the wave, `gh.bilalkabas/drl-nav`, already had its ...

### Source-file lab drivers and concrete Panda review

[`MHS/changes/RECON-LAB-PANDA-REVIEW.md`](MHS/changes/RECON-LAB-PANDA-REVIEW.md): The next four DeepSeek-authored packages have completed model review. Both Keithley power-supply packages pass strict fake collection with no acceptance warnings. The concrete PandaReach and Thorlabs beam-profiler packages retain blocked outcomes where source-backed native behavior conflicts with the current execution contract. An author-side fake gate pass was not accepted as native compatibility evidence. Model attribution, pinned sources and null human-review signatures ...

### Complete replay snapshots and consistent revision selection

[`MHS/changes/REPLAY-SNAPSHOTS.md`](MHS/changes/REPLAY-SNAPSHOTS.md): Replay snapshots now include the endpoint's declared recording resource alongside every recorded source resource. Unknown optional metadata is absent instead of schema-invalid null. All replay resources read from the selected frame or current recording view; stale static manifest state no longer overrides those reads. Source frames, their receipt-bound hashes and exported source evidence remain unchanged. A source resource named recording is refused explicitly because it ...

### Action-backed ROS safety and Franka gripper contract

[`MHS/changes/ROS-ACTION-SAFETY.md`](MHS/changes/ROS-ACTION-SAFETY.md): RosDriver supports an explicitly declared fixed action as an independent stop/safe-state path. ROS 1 actionlib and ROS 2 native profiles validate goal identity, terminal status, application success and the declared output schema before acknowledging safety. Action safety has its own bounded admission lane, separate from ordinary transactions. An accepted cancellation or a dispatched goal does not establish native completion or stopping.

### Synchronize the ROS cancellation regression with actual goal dispatch

[`MHS/changes/ROS-CANCELLATION-TEST-START.md`](MHS/changes/ROS-CANCELLATION-TEST-START.md): OpenMHS is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

### ROS continuation B: reviewed contracts and explicit blocks

[`MHS/changes/ROS-CONTINUATION-B.md`](MHS/changes/ROS-CONTINUATION-B.md): The 24 DeepSeek-authored packages were reviewed by a different model, gpt-6, on 2026-11-04. The original author outcomes were 14 passing fake gates and 10 blocks. After source review, repairs and combined checks, 8 packages are accepted as `contract_checked` and 16 remain blocked. Every existing human-signature field remains unchanged; all new model-written locks remain unsigned. This is a local integration record, not publication or hardware validation.

### ROS-HELPER — rosbridge topics and services, with an unsigned fake pilot

[`MHS/changes/ROS-HELPER.md`](MHS/changes/ROS-HELPER.md): On 2026-11-02 the owner approved rosbridge JSON over WebSocket, a ROS-free recording fake, and a human hardware review before any ROS hardware backend starts. This change implements that bounded first helper and pilots five pinned repositories. It adds no ROS installation or process management and makes no hardware-validation claim.

### ROS-INSTALL-RECIPES — identify root build tools from pinned source

[`MHS/changes/ROS-INSTALL-RECIPES.md`](MHS/changes/ROS-INSTALL-RECIPES.md): Task-card generation previously treated any root `package.xml` as a colcon build and any `setup.py` as pip-installable. That produced incorrect recipes for the Catkin packages in the ROS batch, including ROS Gazebo Gym and MultiROS.

### Isolated live ROS validation

[`MHS/changes/ROS-LIVE-VALIDATION.md`](MHS/changes/ROS-LIVE-VALIDATION.md): The ROS helper has now been exercised against a real ROS 2 Jazzy graph, using the upstream turtlesim tutorial simulator and rosbridge. This is additional interoperability evidence beyond controlled-peer tests. It is not validation of Panda, Gazebo, MoveIt, other corpus packages, a physical camera or hardware.

### Finite ROS image sources and per-capture headers

[`MHS/changes/ROS-MULTI-IMAGE-HEADER.md`](MHS/changes/ROS-MULTI-IMAGE-HEADER.md): A single ROS driver package previously exposed one fixed image stream and omitted the source header. The opt-in `cameras` declaration now selects among a finite set of static, source-checked image subscriptions through the existing `camera` input. Each capture retains complete pixels and the exact validated ROS1 or ROS2 header in its scoped artifact descriptor. The stable four-field image output and legacy flat subscription behavior stay unchanged; no synchronized capture ...

### Complete bounded ROS PointCloud2 artifacts

[`MHS/changes/ROS-POINTCLOUD-ARTIFACTS.md`](MHS/changes/ROS-POINTCLOUD-ARTIFACTS.md): The fixed-stream ROS bridge can now bind `cap.sensing.point_cloud.v1` and publish the complete binary message data with its field layout and exact received header as a deterministic local ZIP artifact. All point and row padding, byte order, overlapping field views and floating point bit patterns are preserved. Strict layout, whole-sample budgets and existing artifact ownership/commit barriers refuse malformed, oversized or interrupted captures without a new readable grant.

### ROS-PUBLISH-STEP-AND-MVSIM — publish-then-step ROS commands, pybind11 native selectors, Webots gym bridge and MVSim

[`MHS/changes/ROS-PUBLISH-STEP-AND-MVSIM.md`](MHS/changes/ROS-PUBLISH-STEP-AND-MVSIM.md): Two SDK gaps of the blocked-package triage (class C) closed: a `RosDriver` command can publish and then call a step service and read a fresh sample after it, and gate G7 can resolve a native class that the upstream exposes only through pybind11 binding source. With them the Webots gym bridge passes after repair, and MVSim passes as a direct driver over its own ZMQ/protobuf services. The SDK stays standard-library only; no passing package's gate digest moved.

### ROS receiver startup and bounded close

[`MHS/changes/ROS-READER-CLOSE.md`](MHS/changes/ROS-READER-CLOSE.md): A request can send its first rosbridge frame and publish the receiver Thread before Thread.start has finished. Concurrent close previously joined that unstarted thread and raised RuntimeError. The sole Thread remains retained from startup, while a new event records entry into its receive target. Close joins only after that entry proves the thread has started, keeping the existing 100 ms join budget and taking no startup lock. A receiver that starts after close sees the stop ...

### ROS simulated deployments and action completion

[`MHS/changes/ROS-RUNTIME.md`](MHS/changes/ROS-RUNTIME.md): The ROS helper now accepts an explicit simulated deployment configuration (`endpoint`, `fidelity`, `deployment_id`) for a simulated `RosDriver`. Configuration is validated before transport I/O. The helper never silently substitutes hardware for simulation, and every model-authored ROS hardware backend still requires a human `reviewed_by` signature regardless of its risk class. Per-backend fidelity is copied for each constructed driver.

### Fresh ROS stop acknowledgements

[`MHS/changes/ROS-SAFETY-FRESHNESS.md`](MHS/changes/ROS-SAFETY-FRESHNESS.md): ROS safety acknowledgements now belong to the current native activity and stop epochs. A motion command, effectful service, cancellation or reset invalidates an older stop acknowledgement; a pending native operation continues to block a positive safe-state claim and recovery until its terminal outcome is known. A fresh stop after settlement is required. The independent stop path remains available while ordinary work is pending.

### Bounded rosbridge text fragment reconstruction

[`MHS/changes/ROS-TEXT-FRAGMENT-REASSEMBLY.md`](MHS/changes/ROS-TEXT-FRAGMENT-REASSEMBLY.md): Controlled ROS2 PointCloud2 packets containing 12582912 raw bytes exceed the deployed rosbridge server's ten-million character fragment limit after base64 encoding. Small endian controls passed, but the complete sample previously failed when the first `fragment` envelope reached the bridge. The live WebSocket transport now reconstructs bounded text fragments before routing their original JSON. Default transport and artifact limits are unchanged.

### ROS control without an acknowledged stop

[`MHS/changes/ROS-UNBOUND-SAFETY.md`](MHS/changes/ROS-UNBOUND-SAFETY.md): An effectful ROS profile could report an achieved safe state after a software-only e-stop in simulated mode while the external peer retained its last target. The local latch prevented later commands but did not stop the external controller. RosBridge now reports explicit unconfirmed safety when a profile declares effectful commands, writes or a native reset without an acknowledged stop binding or safe-state Action. The stock server returns `MHS.SAFETY.SAFE_STATE_UNREACHED` ...

### ROS wave C: the 150 remaining ROS cards, reviewed by Claude (58 contracts, 86 blocks, 6 skips)

[`MHS/changes/ROS-WAVE-C.md`](MHS/changes/ROS-WAVE-C.md): After the reviewed ROS helper ([ROS-ACTION-SAFETY.md](ROS-ACTION-SAFETY.md), [ROS-CONTINUATION-B.md](ROS-CONTINUATION-B.md)), 150 ROS `family-config` cards were dispatchable: 148 robot cards of wave 3 and 2 lab cards of wave 6, with card floors R0 (129) and R1 (21); 55 need the owner's publication decision. On 2026-11-04 the user authorized sending their pinned sources, the SDK and the specifications to DeepSeek through the existing DeepSeek Harness for authoring only (no ...

### ROS continuation package review

[`MHS/changes/ROS-WAVE-REVIEW.md`](MHS/changes/ROS-WAVE-REVIEW.md): The first two and next ten DeepSeek packages were source-reviewed instead of treating their fake gate as evidence of a working ROS deployment. The review corrected native environment routing, selected a concrete Panda task where an abstract template had been chosen, and retained incomplete primary functions as blocked.

### Runtime and gate fixes: a confirmed stop once per e-stop, transport natives resolved, record modes, a linear G4 reader

[`MHS/changes/RUNTIME-AND-GATE-FIXES.md`](MHS/changes/RUNTIME-AND-GATE-FIXES.md): Four defects that the reviews of [ROS wave C](ROS-WAVE-C.md), [helper wave 1](HELPER-WAVE-1.md) and the [helper integration](HELPER-INTEGRATION.md) recorded as found, not fixed. Claude (`claude-opus-5-5`, a model and not a human) changed them in a private copy of the 2026-11-05 tree (`snapshot-2`), with tests, and compared every package's gate before and after. Nothing ran on hardware, a ROS graph or upstream code; every result is `contract_checked` on a fake.

### SAFE-031 for permit-gated capabilities without inputs (suite 1.4.1)

[`MHS/changes/SAFE031-INPUT-FREE-PERMITS.md`](MHS/changes/SAFE031-INPUT-FREE-PERMITS.md): Conformance test SAFE-031 no longer skips a permit-gated binding whose input schema admits only the empty object. Suite 1.4.0 needed a second valid input to present the permit with, so a permit-gated action without inputs, such as a declared re-enable (CORE-086), capped its endpoint at CL2 and gate G8 failed. Such a binding has no second valid input: the test now records the distinct-input presentation as not applicable and tests what still applies. Every other binding is ...

### Sensed-stop replay, companion read-back meaning and the served simulated-only binding

[`MHS/changes/SENSED-AND-COMPANION-HARDENING.md`](MHS/changes/SENSED-AND-COMPANION-HARDENING.md): Three minor safety findings of the phase-3 verification (lens safety-path) are fixed. A sensed-confirmation stop now counts only samples published after its subscription was opened: the bridge discards one sample on ROS 1 (a latched message) and the declared publisher history on ROS 2 (cited or operator_required). Gate G7 checks what a companion read-back means (the stop's world, no acknowledgement field, a field assigned from state). And only what the endpoint serves, a ...

### Sensed-confirmation stop for simulated ROS devices, and e-stop path hardening

[`MHS/changes/SENSED-CONFIRMATION-STOP.md`](MHS/changes/SENSED-CONFIRMATION-STOP.md): A simulated `RosDriver` whose only stop is a request that proves nothing by itself (a LAND, a zero velocity, a motor cut) may now declare `safety_bindings["sensed_stop"]`: the e-stop sends the request and is achieved only when every producer-stamped source delivers consecutive fresh samples that satisfy a closed predicate within a bound; otherwise it is `SAFE_STATE_UNREACHED` with the latch held and the background retry. Real hardware never may (SAFE-049, CORE-088). Five ...

### Finite SiLA2 controlled contract helper

[`MHS/changes/SILA2-CONTROLLED-HELPER.md`](MHS/changes/SILA2-CONTROLLED-HELPER.md): A private generic candidate adds `Sila2Driver` and a finite typed controlled-peer bridge, with retained construction, execution UUID, stream, transfer and cleanup ownership. The SDK fixture preserves all eight Phenix command routes and all seven properties, including acquisition progress/final result and complete DisplayIcon artifact bytes. The icon is not an acquired camera image.

### Preserve unknown Binary ownership after an empty sample batch

[`MHS/changes/SILA2-EMPTY-BINARY-BATCH.md`](MHS/changes/SILA2-EMPTY-BINARY-BATCH.md): OpenMHS is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

### Explicit controlled Phenix gate prerequisite

[`MHS/changes/SILA2-GATE-PREREQUISITES.md`](MHS/changes/SILA2-GATE-PREREQUISITES.md): The complete fake Phenix contract starts disconnected and requires an explicit Connect. The gate accepts one finite source-checked declaration to issue that command through a separate stock simulated session with the original operator overlay and input-bound permit before dependent positive and safety cases. No runtime initialization, implicit stop/reset or hardware approval is added. Negative admission cases keep their original unprepared state and zero-actuation ...

### SiLA2 Stop confirmation retains the original settlement budget

[`MHS/changes/SILA2-STOP-SETTLEMENT.md`](MHS/changes/SILA2-STOP-SETTLEMENT.md): OpenMHS is an independent project, not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview. Controlled SiLA2 Stop confirmation now waits for cooperative receipt-state reads and retries invalidated observations within the caller's original deadline.

### SIM-HOST — an isolated simulator host for environments that own a ROS and Gazebo lifecycle

[`MHS/changes/SIM-HOST.md`](MHS/changes/SIM-HOST.md): A `GymnasiumDriver` backend can now declare `isolated_process_v1`: its environment is built and driven in a child process that the endpoint starts and owns, an exit or a global ROS shutdown inside the environment ends only that process, every call is bounded, and the e-stop is the declared simulator stop confirmed by a declared state read-back, or an unreached safe state. gh.rickstaa/ros-gazebo-gym passes on it (risk raised to R2); gh.ut-amrl/socialgym2 stays blocked because ...

### SIMULATION-RISK-ERRATUM — align the safety examples with the catalogue

[`MHS/changes/SIMULATION-RISK-ERRATUM.md`](MHS/changes/SIMULATION-RISK-ERRATUM.md): The safety chapter listed simulation stepping as an R1 example, while the machine-readable `cap.world.step.v1` class, the generated capability catalogue, the driver profile and the SDK simulator families use R0. The precedence rule in `MHS/spec/README.md` places the JSON registries above the safety chapter and requires an erratum to the lower document when they disagree.

### SIMULATION-TIMING — opt-in physics accounting for fixed-decimation Gym environments

[`MHS/changes/SIMULATION-TIMING.md`](MHS/changes/SIMULATION-TIMING.md): The old Gym bridge counted one native environment call as one tick, even when that call advanced several physics timesteps. An optional backend timing declaration now publishes separate physics/control periods, requires whole control periods in the input, measures actual clock deltas and carries truthful per-command timing through the stock server's receipts and reconciliation path. The API and restrictions are documented in `MHS/sdk/docs/simulation-timing.md`.

### Preserve literal code in documentation search descriptions

[`MHS/changes/SITE-LEAD-CODE-LITERALS.md`](MHS/changes/SITE-LEAD-CODE-LITERALS.md): The site generator removed underscore and asterisk characters from inline code while extracting a document's leading description. The correctly spelled PointCloud2 capability became a different, nonexistent identifier in the generated search index, causing the release site checker to fail. Lead extraction now removes inline-code delimiters while preserving their literal content; prose emphasis still becomes plain text. No capability, SDK runtime or driver changes.

### Explicit pinned Python source surfaces

[`MHS/changes/SOURCE-SURFACES.md`](MHS/changes/SOURCE-SURFACES.md): This change adds source-only selectors for upstream modules and filenames that cannot be represented by an ordinary import path: `pyfile:path.py#Class` and `pyfile:path.py#*`. Existing dotted class selectors retain their existing resolution behavior. No source selector is a runtime factory, and upstream code is parsed rather than imported.

### SQUINT-ACTION — squint's fake serves ManiSkill's normalised action, -1 to 1 per joint

[`MHS/changes/SQUINT-ACTION.md`](MHS/changes/SQUINT-ACTION.md): GYM-SPACE-REF-2 found that the fake of `gh.aalmuzairee/squint` (`SO101LiftCube-v1`) serves its controller's per-step joint deltas as the action bounds, while ManiSkill normalises that controller's action to -1..1 (`MHS/changes/GYM-SPACE-REF-2.md`, "Found, not fixed"). A reading of the clone at the pinned commit `7086fd516eda7df585a5261c541e0670a6d916b4` and of the ManiSkill clone confirms it. The fake now serves `Box(-1, 1, (6,))` and scales each value to its joint delta in ...

### SRB-WIDTH — the Space Robotics Bench fake takes the seven action values of the default Franka and observes its hand

[`MHS/changes/SRB-WIDTH.md`](MHS/changes/SRB-WIDTH.md): GYM-SPACE-REF found that the fake of `gh.andrejorsula/space_robotics_bench` serves a six-value action while the upstream adds the Franka hand's gripper command to the arm's pose command (`MHS/changes/GYM-SPACE-REF.md`, "Found, not fixed"). A reading of the clone at the pinned commit `7528ff81f1ac0b34ba259b1ae150fdb4f6a90b5e` confirms it: in the configuration the package serves, `total_action_dim` is 7. The fake now has seven values, and because its space is then the ...

### SUBMODULES-AND-FACTORY-ENVIRONMENTS — git submodules read at their gitlink, and a G7 rule for factory-built environments

[`MHS/changes/SUBMODULES-AND-FACTORY-ENVIRONMENTS.md`](MHS/changes/SUBMODULES-AND-FACTORY-ENVIRONMENTS.md): The gate, `show_refs.py` and `collect.py` now read a citation into a git submodule of a pinned clone (`<submodule path>/...`) at the commit the pinned tree's gitlink records, from the submodule's own object store, and only while the submodule is declared, checked out and at exactly that commit; anything else fails closed. Gate G7 gains a rule for a Gymnasium environment that a factory function of the clone builds from a class outside it (`native_factory`). RoboPianist passes ...

### Tag, register and PV helper (`TagDriver`)

[`MHS/changes/TAG-BRIDGE-HELPER.md`](MHS/changes/TAG-BRIDGE-HELPER.md): This change adds `TagDriver`, the helper of the `tag-bridge` family: a configuration-only driver for devices that a server exposes as named points. One helper carries three profiles, `modbus` (holding and input registers, coils, discrete inputs), `epics-ca` (Channel Access PV suffixes; the deployment prefix stays with the native transport) and `alpaca` (ASCOM Alpaca properties and methods). Each package declares a finite point table in which every address cites the clone ...

### UNITY-PICK-PLACE-PLANNER — the Unity ROS-TCP item: no route owns Unity's execution; a plan-only package

[`MHS/changes/UNITY-PICK-PLACE-PLANNER.md`](MHS/changes/UNITY-PICK-PLACE-PLANNER.md): The blocked Unity object-pose-estimation demo (`gh.unity-technologies/robotics-object-pose-estimation`, triage class C) now passes as a plan-only `RosDriver` package: one observational command asks the demo's MoveIt service `ur3_moveit` for its five pick-and-place trajectories and returns them, executing nothing. No SDK change was needed and none was made. The simulated arm stays out of reach of any route (Unity executes plans in a coroutine that only its own request starts ...

### WAVE-A — ten side-by-side sessions, their model review, and the SDK defects they found

[`MHS/changes/WAVE-A.md`](MHS/changes/WAVE-A.md): Batch wA was the rest of the pilot and of wave 1: 28 cards in ten DeepSeek Harness sessions at once (`deepseek-v4.1-flash:1017`, two or three cards each, `dispatch.py --only` giving every session its own share). All ten ended within 20 to 30 minutes. The model reported 23 passes and 5 blocked cards; `collect.py` agreed. No file outside the 28 driver directories changed, and no clone was written to.

### WAVE-B1 — the first round of wave B, unattended, and what its review changed

[`MHS/changes/WAVE-B1.md`](MHS/changes/WAVE-B1.md): Round 1 of wave B ran unattended: `run_wave.py --jobs 10` with the DeepSeek Harness in headless mode (`deepseek-v4.1-flash:1017`, one fresh session per card), 50 cards in 55 minutes, about 10 minutes per card. The gate passed 49; one card stopped blocked. No file outside the cards' directories changed. The harness counted 637 million tokens, 98 % of them cache reads (10.8 million input and 3.5 million output tokens were not cached).

### WAVE-B2 — rounds 2 to 6 of wave B, unattended, and what their review changed

[`MHS/changes/WAVE-B2.md`](MHS/changes/WAVE-B2.md): Rounds 2 to 6 of wave B ran unattended: `run_wave.py --jobs 10` with the DeepSeek Harness in headless mode (`deepseek-v4.1-flash:1017`, one fresh session per card), 216 cards in 2 hours 1 minute, a median of 5.4 minutes per card, none timed out. The gate passed 209; four cards stopped blocked and three proposed a skip. The harness counted 1,998 million tokens, 98 % of them cache reads (44.5 million input and 13.0 million output tokens were not cached).

### WAVE-C — the 113 driver cards recon wave A opened, and four gate fixes they needed

[`MHS/changes/WAVE-C.md`](MHS/changes/WAVE-C.md): The 113 dispatchable cards after recon wave A (`MHS/changes/RECON-A.md`: 111 cards the recon review made driver tasks, and two whose existing entries gained the proposals' entry symbols, the Opentrons modules and a partner's Tecan Genesis scripts) ran unattended like the earlier waves: `run_wave.py --jobs 10` with the DeepSeek Harness in headless mode (`deepseek-v4.1-flash:1017`, one fresh session per card, batch `wC`), 113 cards in 1 hour 13 minutes, a median of 357 seconds ...

### WAVE-D — the 92 driver cards recon wave B opened, and git kept out of the clones twice more

[`MHS/changes/WAVE-D.md`](MHS/changes/WAVE-D.md): The 92 dispatchable cards after recon wave B (`MHS/changes/RECON-B.md`) ran unattended like the earlier waves: `run_wave.py --jobs 10` with the DeepSeek Harness in headless mode (`deepseek-v4.1-flash:1017`, one fresh session per card, batch `wD`). They are 81 Gymnasium, 9 MuJoCo and 2 python-object cards, 26 of wave 3 and 66 of wave 6, most of them Isaac Lab and Isaac Gym task packs and environments over CoppeliaSim, Webots, AirSim, CARLA, Unreal and other external engines. ...

### WAVE-PUB — the 80 cards that wait for a publication decision, and what their review changed

[`MHS/changes/WAVE-PUB.md`](MHS/changes/WAVE-PUB.md): After wave B, the dispatchable cards left were the 80 marked `publish_review: required` (`PUB`): their licence is unknown, network-copyleft, proprietary or source-available, so a driver may be written but the owner decides before it is published. They ran unattended like wave B: `run_wave.py --jobs 10` with the DeepSeek Harness in headless mode (`deepseek-v4.1-flash:1017`, one fresh session per card), 80 cards in 54 minutes, a median of 6.2 minutes per card, none timed out. ...

<!-- END FRAGMENTS -->
