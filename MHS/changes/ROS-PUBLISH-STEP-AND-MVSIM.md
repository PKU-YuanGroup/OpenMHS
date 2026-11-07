# ROS-PUBLISH-STEP-AND-MVSIM — publish-then-step ROS commands, pybind11 native selectors, Webots gym bridge and MVSim

Two SDK gaps of the blocked-package triage (class C) closed: a `RosDriver` command can publish and then call a step service and read a fresh sample after it, and gate G7 can resolve a native class that the upstream exposes only through pybind11 binding source. With them the Webots gym bridge passes after repair, and MVSim passes as a direct driver over its own ZMQ/protobuf services. The SDK stays standard-library only; no passing package's gate digest moved.

Draft written by Claude (claude-opus-5-5, a model and not a human) as phase-3 agent p3-sdk-gaps-b in a private copy of
`snapshot-3` (`work/handoff-runs/claude-20261104/development/p3-sdk-gaps-b/`); not yet applied to the tree. The SDK code
and both packages are Claude-written; by the user's decisions of 2026-11-04 and 2026-11-05 a Claude Sonnet model
reviews them before they are merged. Evidence is fake `contract_checked` only: no Webots world, MVSim server, ROS graph,
rosbridge deployment or hardware was run, and `reviewed_by` stays null everywhere.

## SDK changes

- `mhs/bridge/ros.py`: a topic publication command may add `then: {"step": <service call>, "observe": <read>}`
  (`observe` optional). The bridge publishes, calls the step service once under the command's wire epoch, then takes the
  observation (a new subscription opened after the step was acknowledged, or an observational service). The raw output
  is `{published, confirmed: false, step, stepped, observation}` for `result` to map. `step` must be an effectful
  service call with a literal request and an application `success` predicate and no `args`; neither stage may carry
  `resource`, `safe_state`, `then`, `image`, `point_cloud`, `args` or its own `result`; `then` is refused on services,
  subscriptions, reads, writes and safety bindings. Once the publication was sent, the bridge reports every failure,
  refusal, cancellation or interruption of a stage, and a failure to map the command's `result`, as
  `MHS.OUTCOME.UNKNOWN` with `details.stage` (`step`, `observe` or `result`), `details.stepped` and the cause; nothing
  is retried. A `result` path whose first field the raw output never carries (`output.observation` without `observe`, a
  misspelled stage) is refused when the bridge is configured. The server's strict output-contract check, which runs
  after the bridge returns, is unchanged: a mismatch is a failed receipt, as for every effectful command whose native
  call ran. An e-stop, a cancellation or an expired budget after the publication keeps the step from being sent. A step
  that was sent and not settled is retained like any effectful service call. The command's `timeout_ms` bounds the whole
  sequence.
- `mhs/driver/ros_check.py` (G7): each `then` stage is a declaration of its own, checked against its own
  `source_ref`/`type_ref`, and the only wire operations allowed at its endpoint besides the publication's.
- `mhs/driver/pybind_surface.py` (new), `mhs/driver/source_selector.py`, `mhs/driver/model.py`, `mhs/driver/check.py`:
  `native = "pybind:<binding.cpp>#<scope>.<Class>"` names a class bound with pybind11. The binding file is read as a
  regular blob at the pinned commit; the class must be declared exactly once (binder's `class_<...> var(M("scope"),
  "Name")` or `class_<...> var(module, "Name")`), and its members are the `var.def*("name")` calls at the declaration's
  own brace depth (nested classes and comments excluded; a declaration without a variable is reported). G7 then checks
  the fake's public members and every attribute the driver used against them (`NOT_UPSTREAM`); only a direct `Driver` or
  a `PythonObjectDriver` may name one (G7 dispatches the selector before its shortcut for a Gymnasium or MuJoCo fake
  that is the upstream simulator, so such a driver is refused too), and the card's entry symbols constrain it as they
  constrain `package.module:Class`. Nothing is imported or compiled; argument shapes, the binding's GIL handling and the
  bound code's behaviour are not checked. The module is a gate internal (`_GATE_INTERNALS`, `_GATE_MODULES`,
  `_CORE_MODULES`).
- Documentation: `sdk/docs/ros-driver.md` ("Publish, then step", including that the publication and the step reach
  the node on different ROS connections, so a completed receipt does not prove the publication was applied before
  the step, and that a driver whose only stop is a safe-state Action cannot finish the reset after an unsettled step),
  `sdk/docs/source-selectors.md` ("Classes bound with pybind11"), `sdk/docs/driver-authoring.md` (shape table, G7
  troubleshooting).

## Packages

- `gh.alexanderkeijzer/ros-gym-env-webots`: pass after repair (was blocked, HELPER_MISSING; only G8 `TCAP-003` failed).
  `x-cap.alexanderkeijzer.action_step.v1` replaces the publish-only joint action: it publishes `/joint_actuators/value`
  (whose callback increments the node's setpoints and calls `set_position`), calls `/webots/step` once and reads a fresh
  `/joint_sensors/value` sample, so the observation depends on the action. rosbridge forwards the publication and the
  step call over different ROS connections and the node serves both from one `ros::spin()`
  (`src/gym_env_webots_node.cpp:253`, `:258`, `:265`), so the step may run before the action callback and the first
  action after the topic is advertised may be lost: a fidelity gap, the action description, the `confirmed` field and
  `facts.md` say that a completed receipt's observation need not reflect the action, and the fake's `action_after_step`
  switch reproduces it in a test. The reset safe state accepted on 2026-11-05 is unchanged. The joint-position array no
  longer claims radians for the two LinearMotor finger joints (three facts added: the two finger motors, and the
  subscription queue and `ros::spin()` of `main`). The fake applies the node's setpoint arithmetic and moves each joint
  to its target on a step (placeholder dynamics). DeepSeek attribution, source pin, null `reviewed_by` and
  `publish_review: required` are kept; the repair is the last `MODEL REVIEW` paragraph of `RESULT.json`
  (claude-opus-5-5).
- `gh.mrpt/mvsim`: re-authored by Claude (claude-opus-5-5) as a direct `Driver`; the blocked DeepSeek RosDriver package
  (no stop on the ROS route) is kept in the agent's `moved-aside/`. DEVIATION FROM THE CARD (family-config /
  RosDriver; `collect.py` notes it): the package drives one vehicle through MVSim's own services,
  `set_controller_twist` (a setpoint the controller accepted under the simulation-step lock) and `get_pose`; the e-stop
  sets a zero twist and checks the answer. Its native is the pybind11 binding of `mvsim::Client`. The `sim` backend is
  the package's own bounded ZMQ client (`mvsim_wire.MvsimServiceClient` built by `sim.py`, pyzmq declared in
  `driver.lock.json`, never an SDK dependency): the upstream Python client waits on ZMQ without a timeout inside a
  binding that does not release the GIL, so a silent simulator could stall the whole process, e-stop included. The
  package encodes MVSim's protobuf messages itself (standard library; byte vectors in `test_driver.py` pin the field
  numbers). The client calls only `set_controller_twist` and `get_pose`, passes on only their own answer types or a
  `GenericAnswer` whose success is false (so no other message reads as an accepted zero twist), and connects to the
  configured host at the port the server reports for a service, never to a host the server names (MVSim reports its
  wildcard bind, `Client.cpp:166-167`, `462`; the upstream client connects to it verbatim, `:775`, `:783`). The client
  has not been run against an MVSim server. The device and its twist action are R2 (mobile-base transit in the hazard
  table of `spec/04-safety.md`, as in the comparable simulated mobile-base packages; the first draft said R0). The pose
  read has a documented side effect: `get_pose` makes the next simulation step reset the vehicle's own `hadCollision`
  flag (`World_services.cpp:115-120`, `World_simul.cpp:260-269`), which the ROS node's collision topic also reads,
  while the `in_collision` it reports comes from a record that the step only adds to (`World_simul.cpp:254-256`);
  review round 1 added three facts for it. Twist inputs are `operator_required`.

| Package | Status | Gate digest |
|---|---|---|
| gh.alexanderkeijzer/ros-gym-env-webots | pass (was blocked) | sha256:6d021a290add79448cc33d8efcfc4011f5f10d44713692603c5b1dd002793d6b |
| gh.mrpt/mvsim | pass (was blocked; re-authored) | sha256:2939c811067ec6c57841b2cdbf2cdeb1d80908b29d367feb119ec5a0db80fefe |

Both digests are unchanged by review round 1: a gate digest covers the gate results, the backend, the upstream pin and
the SDK version (`stable_digest`, `sdk/src/mhs/driver/check.py`), not the package text, and both packages still pass
every gate without a finding. Both cards change at the next registry rebuild (`package_status`, `blocked_on`);
`prepare.py --sync` then refreshes their `task.json`.

## Found, not fixed

- A driver whose stop is a declared safe-state Action (the Webots package), after a step that was sent and not
  answered in time: while that step stays unanswered, every safe-state call sends its request (`/webots/reset`) but
  reports `SAFE_STATE_UNREACHED`, because the commit needs every effectful call the bridge sent to be settled
  (`_effects_settled_locked`); if no reply ever comes, every later e-stop on that connection reports it unreached. Once
  the late reply arrives, the safe-state call commits, but `RosBridge.reset()` stays refused on that connection:
  it re-confirms the retained call through `safe_state()`, which runs only `safety_bindings`. Both fail safe (the latch
  holds). Reproduced with a two-command bridge (`scratch/f4_probe.py` in the agent's directory). Letting a settled
  safe-state Action re-confirm retained calls is left to a later item: a settled reset does not in general prove that
  a retained step cannot still land.
- Whether webots_ros publishes a sensor sample after the reply of a `time_step` call is outside the clone; a live
  act-and-step gives an unknown receipt when none arrives within its 2 s observation bound.
- MVSim's upstream Python client (`pymvsim_comms`) has no timeouts and holds the GIL while it waits (upstream code,
  `common.cpp:63-73`, generated `Client.cpp:74-87`); `mvsim launch` may serve on one of the nine ports after 23700.
- The pybind11 reader does not follow chained `.def` calls, macros or preprocessor branches.
- The isolated-process simulator host, dodal file artifacts and the Unity ROS-TCP helper (the other class-C items)
  are left as found.

## Review round 1

Two Claude Sonnet reviewers (safety and evidence lenses, 2026-11-05) found no blocker and one major item. Handling:

| Finding | Severity | Handling |
|---|---|---|
| F1: a result that cannot be mapped after the step was a failed receipt | minor | Fixed: `RosBridge.call` reports it as unknown (`stage: result`), and a `result` path the raw output never carries is refused at configuration; `ros-driver.md` says the server's output-contract check after the bridge is unchanged. Tests; mutants M11-M13. |
| F2: the MVSim client ignored the type of a service's answer | minor | Fixed: only the service's own answer type, or a `GenericAnswer` whose success is false, is passed on; another service name is refused before anything is sent. Tests; mutants M16, M17, M20. |
| F3: a `pybind:` selector was not refused for a Gymnasium or MuJoCo driver whose fake is the upstream simulator | minor | Fixed: G7 dispatches the selector before that shortcut (and reports a missing clone itself). Tests with `records_native` false; mutant M14. |
| F4: the Webots safe-state Action cannot commit while a sent step is unsettled | minor | Not fixed (the reviewer asked for no change in this item): the disclosure under "Found, not fixed" and in the Webots `facts.md` now states both phases, reproduced by `scratch/f4_probe.py`. |
| F5: no pybind test had a line comment inside the class block | nit | Fixed: the fixture has one; mutant M15 (line comments kept) is killed. |
| F6: the MVSim client connected to the endpoint the server reported, host included | nit | Fixed: it connects to the configured host at the reported port; an endpoint without a host and a valid port is not used (nothing is sent to the service). Tests; mutants M18, M19. |
| MVSIM-RISK: R0 for a vehicle that takes velocity setpoints | major | Fixed: the device and the twist action are R2; `facts.md` (Safety) and `RESULT.json` give the reason. |
| WEBOTS-ORDER: the publication and the step reach the node on different connections | minor | Fixed: a fidelity gap, `facts.md` (Scope), the action and `confirmed` descriptions, a fact (`src/gym_env_webots_node.cpp:258-265`), a fake switch with a test, and a general paragraph in `ros-driver.md`; mutant M21. |
| MVSIM-POSE-SIDEEFFECT: the pose read clears the collision flag | minor | Fixed, more narrowly than reported: `get_pose` queues a reset of the vehicle's own `hadCollision` flag, applied at the next step (`World_services.cpp:115-120`, `World_simul.cpp:260-269`); the flag it reports comes from a separate record that the step only adds to (`World_simul.cpp:254-256`, read at `World_services.cpp:108`), so a read does not clear what it reported, but it can clear a collision before the ROS node publishes it (`mvsim_node.cpp:1120-1130`). Three facts, the action and output descriptions, a gap and `facts.md`. |
| MVSIM-LIVE-UNRUN: the live client never ran against a server | nit | No change requested; the disclosure stays. |
| TOOL-SHOWREFS: `MHS/handoff/tools/show_refs.py` resolves its root from its own location | nit | Not changed: the tool is outside this item and no package depends on it; left for the integrator. |

## Result

In the private copy (Python 3.14.7, the validated environment, no bytecode; logs in
`work/handoff-runs/claude-20261104/development/p3-sdk-gaps-b/logs/`). After review round 1:

- New SDK tests: `tests/bridges/test_ros_publish_then_step.py` 20, `tests/driver/test_ros_publish_then_step_gate.py` 7,
  `tests/driver/test_pybind_native.py` 14 (41; 37 before the review). Twenty-one mutants of the new code are all
  killed (`mutants-r1.log`): the first draft's ten (step sent without the epoch, failures passed through, observation
  without the step, step without a predicate, G7 ignoring `then`, nested or trailing pybind members counted,
  `NOT_UPSTREAM` skipped, other families allowed, card entries ignored) and eleven for the review (a result-mapping
  failure reported failed, result paths unchecked, an observation allowed without `observe`, pybind dispatched after
  the upstream-simulator shortcut, pybind line comments kept, an MVSim answer of another type or a `GenericAnswer`
  claiming success passed on, the reported endpoint host followed, an endpoint without a host accepted, any service
  called, the Webots fake's `action_after_step` switch ignored).
- SDK suite: 3,467 tests OK, 5 skipped, in 650 s on the shared machine (`sdk-suite-3.log`; the 3,426 tests of
  `snapshot-3` plus the 41 new). OpenAI4S integration suite 129 OK (`integration-suite-r1.log`). Generated data
  (`sync_data.py`, `gen_errors.py`, `gen_appendices.py`, `build_applicability.py` checks), the interface contract
  (`INTERFACE.md` unchanged), the spec doctests and the changelog index pass (`generators-r1.log`);
  `tools/oss_export_check.py --skip-suites`, the tutorial gate (digest unchanged) and the pilot (20 of 20) pass
  (`light-checks-r1.log`). The site tests pass again (15, `site-tests-r1.log`) after the last edit, a paragraph of
  `ros-driver.md` written once the suite had finished.
- Package tests: Webots 17 cases, MVSim 28 cases; both gates pass G1-G9 with the digests above, and
  `collect.py --strict` on the two packages passes with no warning (`collect-two-r1.log`).
- `collect.py --strict` over every package whose `RESULT.json` says pass (`collect-all-2/summary.json`): 690 of 690
  pass the gate; the only strict warning is the historical MCM3000 binary citation; 688 gate digests equal the digests
  `snapshot-3` records and the two new passes record their own digests (above). No passing package's digest moved.
  Two MVSim fact edits (a wording and a line range) landed while that run was in progress; the package's tests, gate
  and `collect.py --strict` were re-run on the final text with the same digest.
- Registry: until the rebuild, `validate.py --no-corpus` and the registry suite report only the stale overlays of the
  two packages (card `blocked` against overlay `pass`; `validate-no-corpus-r1.log`, `registry-suite-r1.log`); the R2
  change adds no finding. A rebuild in a fresh scratch copy of the private tree after review round 1
  (`scripts/registry_trial_2.sh`, `registry-trial-2.log`: `build_registry.py --jobs 4`) wrote 731 generated files, and
  `prepare.py --sync` refreshed 357 `task.json`; then `validate.py --no-corpus` passes, the registry suite passes (329
  tests), both cards say `pass` with no blocker, and `collect.py --strict` passes both packages and four other refreshed
  passing packages with their recorded digests. The rebuild is left to the integrator, as in phase 2.
