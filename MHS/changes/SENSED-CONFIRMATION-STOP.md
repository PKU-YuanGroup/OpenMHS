OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Sensed-confirmation stop for simulated ROS devices, and e-stop path hardening

A simulated `RosDriver` whose only stop is a request that proves nothing by itself (a LAND, a zero velocity, a motor cut) may now declare `safety_bindings["sensed_stop"]`: the e-stop sends the request and is achieved only when every producer-stamped source delivers consecutive fresh samples that satisfy a closed predicate within a bound; otherwise it is `SAFE_STATE_UNREACHED` with the latch held and the background retry. Real hardware never may (SAFE-049, CORE-088). Five simulator packages pass with it, and the composed e-stop path got the hardening items of review s10 and the phase-2 verification.

Written by Claude (claude-opus-5-5, a model and not a human) on 2026-11-05 in a private project copy
(`work/handoff-runs/claude-20261104/development/p3-sensed-stop/`), built on `snapshot-3`, from the design of the
read-only preflight `development/p3-sensed-preflight/` (DESIGN.json, PREFLIGHT.json). Not integrated. A Claude Sonnet
model reviews it before integration (the user's decision of 2026-11-04). No hardware, ROS graph, simulator, network,
install or human review is involved anywhere below; every package result is `contract_checked` on a ROS-free fake.

## Why

User decision 2 of 2026-11-05 (`work/handoff-runs/claude-20261104/user-decisions-20261105.json`): seven blocked
simulator packages (PX4/ArduPilot SITL, a quadruped, an AMR, a Crazyflie swarm) have only a stop request, which the
rule of 2026-11-04 does not count as a stop. The user allowed "a request plus sensed confirmation (e-stop achieved
only when a confirming state is read within a bound; otherwise latched and retried in the background), simulators
only". Everything else of the 2026-11-04 rule stands: a request, mode, flag, torque-off, motor-cut, zero-velocity or
callback acknowledgement alone is never a stop, and real hardware, real MAVLink vehicles included, stays blocked.

## Design (SAFE-049, CORE-088)

- Declaration (`mhs/driver/sensed_stop.py`): 1 to 3 fixed request steps (a service with its success predicate, or a
  fixed topic publication; no action goals, no mapped arguments); 1 to 3 sources (topic, message type with a producer
  stamp at `stamp_path`, default `header.stamp`; `std_msgs` types other than `Header` and the plain geometry types are
  refused as header-less; `fill_refs` citing, for every field a term reads, where the producer assigns it, where the
  clone's own code reads it from that topic, or a vendor document line); a closed predicate (`equals`, `range`,
  `abs_max`, `norm_max`, `span_max` over the window); `consecutive` (at least 2), `min_span_ms`, `max_gap_ms`,
  `confirm_within_ms`; one `description`. A source may not be a topic the request publishes. Exclusive with the
  `estop` and `safe_state` bindings and with safe-state actions.
- Thresholds are `Limit`s: cited (`vendor_doc`/`upstream_code`; gate G4 checks that the line shows the number) or
  `Limit.operator_required(reason)`; a plain number or an `operator` source is a definition error. A live
  simulation fills them, narrow-only against a cited value, in `simulation_deployment["estop_confirmation"]`
  (`thresholds`, optional `consecutive` that may only rise, `min_span_ms`, `max_gap_ms`, `confirm_within_ms`); a live
  driver with an unfilled one does not construct, and the live model's `estop_latency_ms` is recomputed from the
  deployment. The fake backend reads placeholders from the package's `fixtures/estop-confirmation.json`; nothing else
  reads that file. The client bounds need no source: a wrong value can only withhold the confirmation.
  `estop_latency_ms` must cover the step timeouts plus `confirm_within_ms` (definition check).
- Simulated only, enforced four times: the model (`mode` must be `simulated`); gate G3 (`SENSED_STOP_CARD` when the
  card's `expected_mode` is not `simulated`; `SENSED_FIXTURE` when the fake's placeholders are missing or widen a
  cited value); the bridge (`RosBridge(..., device_mode="simulated")`, which only `RosDriver` passes; a raw adapter
  file is `MANIFEST_INVALID`); `MHSServer` start-up in every mode (`MHS.ADAPTER.MANIFEST_INVALID`, `details.reason`
  `sensed_stop_not_simulated`) and late devices on first use (the e-stop still reaches them).
- Runtime (`mhs/bridge/ros.py`, pure logic in `mhs/bridge/ros_sensed.py`): the core latches first (unchanged). The
  bridge's `estop` takes its safety stamp, sends every step on the safety lane (not fenced by the latch or the
  epoch, not refused by unresolved ordinary goals, no native activity; each outcome `succeeded`, `refused`,
  `unknown`, `published` or `not_sent` is recorded and decides nothing), then opens new subscriptions (queue length
  1, optional `throttle_rate`) whose samples go to a bounded ring per subscription (an overflow restarts the count).
  The first sample of each subscription is discarded; stamps (ROS 1 `secs`/`nsecs`, ROS 2 `sec`/`nanosec`) must
  strictly increase; a repeated stamp, an arrival gap above `max_gap_ms` or a failing per-sample term restarts the
  count; a missing, zero or decreasing stamp, or a missing, non-numeric or mistyped field ends the attempt. The safe
  state is committed only when every source holds `consecutive` samples spanning `min_span_ms` whose newest arrived
  within `max_gap_ms`, before `confirm_within_ms` after the first transmission and the caller's deadline, with no
  native activity, new epoch, disconnect or close in between. Otherwise `estop` returns unachieved with
  `confirmation.reason` (`request_not_sent`, `sensed_missing`, `sensed_stale`, `sensed_invalid`, `not_confirmed`,
  `superseded`; a closed bridge or a lost connection included); it never raises for an unconfirmed outcome (a
  malformed declaration is refused when the bridge is built).
- Outcomes (CORE-077 unchanged, no new reason): confirmed gives a `completed` e-stop with
  `x-vendor.sensed_confirmation` (request outcomes; per source the counted samples, first and last stamp; elapsed
  time); unconfirmed gives `failed` `SAFE_STATE_UNREACHED` (`bridge_reports_unsafe`, or `timeout` when the budget ended
  first, or `native_failed`) with `details.sensed`; the background retry sends the request again on new
  subscriptions and its `cap.internal.safety_estop.v1` confirmation carries `x-vendor.sensed_confirmation`. Both are
  copied only from the SDK's own ROS route (`_sdk_ros_route`), so a package cannot put a confirmation it did not make
  into a receipt. `safety_status` reports the committed confirmation of the current attempt only.
- Reset re-confirms read-only (new subscriptions, no request, no re-enable) and is refused (`bridge_refused`, latch
  kept) when the sensed state no longer holds; it never resumes anything. A stop that only a restart undoes declares
  `estop_terminal` as well (the Crazyflie motor cut).
- Gate: G7 checks every request step and source like any binding (endpoint and type citations, recorded wire
  operations) and every `fill_refs` line (exists at the pin and shows the field's name, `ROS_FILL_REF_NOT_SHOWN`);
  G4 checks cited thresholds; G6 adds three gate-side filters on the fake transport (every sensed sample withheld,
  one producer stamp repeated, a predicate field nulled), each of which must leave the e-stop `failed`
  `SAFE_STATE_UNREACHED` with the latch held (`G6.SENSED_FAIL_OPEN` otherwise); the stock e-stop checks and G8
  (SAFE-028, TSAFE-001) run on the converging fake. The manifest and the reference file publish
  `safety.estop.confirmation` (request steps, sources, predicate lines, thresholds with their source or
  `operator_required` reason, client bounds marked "no source").
- Honest limit: the SDK cannot prove that a ROS graph is simulated. MAVROS and cflib stacks drive real vehicles with
  another endpoint; every such package says so, and the real path is out of scope and never served.

Considered and left out (as the preflight decided): a simulation witness topic, a site-limits overlay section for the
thresholds, continuous monitoring after the confirmation, action-goal steps, direct-Driver variants and service reads
as sources.

## Hardening of the composed e-stop path (review s10, verification safety lens)

- S10-1: `_sdk_ros_route` now also requires the driver class's `inner`, `estop`, `safety_status` and
  `_run_safe_state` to be the SDK's, an inner bridge of exactly `RosBridge`, and no instance `safety_status`
  (CORE-074 text updated). No passing package overrides these members.
- S10-2: each run of the stop path takes its settle budget from its own start.
- S10-3: a test pins that the latch is set and persisted while the settle hook runs.
- S10-4: `_sdk_settle_hook` looks the SDK classes up in `sys.modules`; it imports nothing on the e-stop path.
- S10-5 and F2: the e-stop label and `details.awaiting_operations` come from the operations still in flight: once
  they all settled, a second run that has not answered is reported as `timeout` (SAFE-040 and CORE-086 updated).
- F1: a restore admission seen at the first sample keeps the e-stop unachieved even if it is gone at the second.
- F3: a test with a bridge without `restore_admission` shows a restore after the latch refused before any bridge call
  (it fails when the guard before the rollback read is removed).
- F4: the wait for a command in flight ends when its worker thread is gone without settling (it can no longer reach
  the device); the stop path then runs again.

## Packages

Repaired from `blocked` to `pass` (authorship kept; a MODEL REVIEW paragraph of claude-opus-5-5 in each RESULT.json;
facts, fakes, tests, fixtures and references updated; source pins unchanged):

| Package | Request | Sources and predicate | Notes |
|---|---|---|---|
| tfly6/opendrone (ROS 1) | `/land` SetBool(true); `/mavros/cmd/arming` disarm | `/mavros/state` connected, not armed; `/mavros/local_position/pose` z below the landed band, x, y, z still | `/flight_state` never a source; landing lock stops the node's own OFFBOARD and arming; `fcu_url` serial default disclosed |
| darienmt/px4-sitl-ros-example (ROS 1) | `/mavros/cmd/land` CommandTOL; `/mavros/cmd/arming` disarm | `mavros/state` connected, not armed; `/mavros/altitude` AMSL still | `offb_node` re-arms every 5 s (disclosed; a reset is refused then) |
| larics/mrs_crazyflies (ROS 2) | `/all/emergency` Empty | `/cf_1/pose` z below the on-ground band, x, y, z still | `estop_terminal`; swarm-wide motor cut disclosed; the per-drone service is not citable by G7 (found, not fixed) |
| karthik0497/ros2-amr-simulation (ROS 2) | zero Twist on `/cmd_vel` | `/odom` pose x, y and orientation z, w still | pose only (the orchestrator's decision: the local gz-sim clone is not the Harmonic version); other `/cmd_vel` publishers disclosed |
| derek-th-wang/quadruped_ctrl (ROS 1) | zero Twist on `cmd_vel`; `gait_type` 4 | `/robot_odom` x, y still, z in the standing band; `/imu0` angular-rate norm | odometry twist never read (never filled); sources throttled to 20 ms |

Every threshold of the five is `operator_required` (none of the clones states an at-rest or landed bound); the fake
placeholders are in each package's `fixtures/estop-confirmation.json`. Unchanged and still blocked:
ifra-cranfield/ros2_robotsimulation (re-triaged by the orchestrator to the companion-source route, CTRL-SWITCH) and
markusbuchholz/gazebosim_blueboat_ardupilot_sitl (no stamped state on its MAVLink route; its Gazebo route needs a
card change and its wave world has no standstill).

## Normative text

- `04-safety.md`: SAFE-040 (`command_in_flight` while a command has not settled; `timeout` once they all have);
  §5.4 SAFE-049; §11 hooks row.
- `core.md`: CORE-074 (the SDK route's definition), CORE-077 (`details.sensed`, `x-vendor.sensed_confirmation`, no new
  reason), CORE-086 (the label from the commands still in flight; the wait ends when a worker is gone), new CORE-088,
  CORE-160 (CORE-088 in both modes).
- Schemas: `device.schema.json` and `reference.schema.json` `safety.estop.confirmation` (optional), mirrored to
  `mhs/_data/schema`.
- Docs: `MHS/sdk/docs/ros-driver.md` (new section), `MHS/spec/driver-profile.md` DRV-012, `MHS/handoff/REVIEW.md`
  item 5. Generated: `mhs/conformance/applicability.json`, `CHANGELOG.md` block.

## Tests

New: `MHS/sdk/tests/bridges/test_ros_sensed_stop.py` (40 cases: stamps, windows and reasons; the endpoint outcomes
for a confirmed stop, ROS 1 stamps, an ignored or refused request, a single latched sample, silent, frozen,
decreasing, null, missing, mistyped and unset samples, arrival gaps, an untransmitted request, the background
confirmation, the read-only reset and its refusal, a terminal sensed stop; the bridge's mode, exclusivity and
supersession rules, an early end on native activity; the definition checks; the fixture and deployment thresholds and the live latency; the manifest
and the reference file; start-up and late-device refusals in both modes; a forged report on an overriding package;
the gate filter) and `MHS/sdk/tests/safety/test_phase3_estop_hardening.py` (13 cases, one or more per hardening
item). A mutation check (`development/p3-sensed-stop/scripts/mutate.py`, logs `logs/mutation-1.json` and
`logs/mutation-2.json`) applied 27 mutants of the new rules and the hardening fixes to a copy of the SDK: 26 make the
new tests fail. The survivor drops the `now <= bound` guard of the confirmation; it is equivalent while the second
guard holds (a sample that arrived after the bound is never counted), so the two guards are kept as defence in depth.
Each package carries its own cases for every fail-closed path of its fake.

Validation in the private copy (2026-11-05): SDK suite 3,479 tests OK (5 skipped) on the second run; the first run,
under a machine load of about 15, also failed one ROS action timing case (it passes alone, 16 of 16 in its module)
and four inventory cases whose fixed count of 582 normative ids is now 583 (SAFE-049; updated). `collect.py --strict`
passes the 688 previously passing packages with their recorded digests (the only warning is the earlier MCM3000
binary citation) and the five repaired ones. `sync_data`, `build_applicability` and `build_changelog` are in step;
`INTERFACE.md` is unchanged. `MHS/registry/validate.py --no-corpus` reports only the five repaired overlays, whose
registry cards still say blocked until the registry is rebuilt at integration.

## Found, not fixed

- The per-drone Crazyflie emergency service is built as `name + "/emergency"`; gate G7 matches only a quoted literal
  name, so the package uses the swarm-wide service. A G7 rule for concatenated relative names would allow the
  narrower stop.
- The PX4 auto-disarm (`COM_DISARM_LAND`) and land-detector settings of darienmt live in the `px4-firmware` git
  submodule, which the SDK cannot cite yet (phase-3 item "submodule reading at the pin"); the fakes model a
  disarm at touchdown as a placeholder, and without it the retry's disarm request confirms.
- The confirmation proves the state over its window only; nothing watches the device after it (a node that re-arms
  the vehicle is disclosed per package; a reset re-confirms).
