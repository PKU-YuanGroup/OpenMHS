OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Sensed-stop replay, companion read-back meaning and the served simulated-only binding

Three minor safety findings of the phase-3 verification (lens safety-path) are fixed. A sensed-confirmation stop now counts only samples published after its subscription was opened: the bridge discards one sample on ROS 1 (a latched message) and the declared publisher history on ROS 2 (cited or operator_required). Gate G7 checks what a companion read-back means (the stop's world, no acknowledgement field, a field assigned from state). And only what the endpoint serves, a simulated manifest on the SDK's own route, lets a sensed confirmation stand for a stop. Every passing digest is unchanged.

Written by Claude (claude-opus-5-5, a model and not a human) on 2026-11-05 as the phase-3 agent p3-hardening-3, in a
private project copy (`work/handoff-runs/claude-20261104/development/p3-hardening-3/`) of `snapshot-5`, the actual tree
after the phase-3 apply. Not integrated; a Claude Sonnet review follows (the user's decision). No hardware, ROS graph,
rosbridge server, simulator or human review is involved anywhere below: every result is `contract_checked` on fakes.

## Why

The phase-3 verification (`work/handoff-runs/claude-20261104/sonnet-review/verify-p3/result.json`, lens safety-path)
went with three minor findings, which the orchestrator gave to this item:

- F1: the probe `p1.py` (a fake whose subscription replays five pre-request samples that show the vehicle landed and
  disarmed while it is at 5 m and armed) completed the e-stop with `safe_state_achieved` true. Only the first sample of
  a confirmation subscription was discarded, and freshness was arrival time only, so a ROS 2 transient-local history
  deeper than one sample could confirm the stop on subscribe.
- F2: gate G7's companion read-back rule checked form, not meaning: the probe `p3.py` passed a read-back comparing the
  acknowledgement field (`success == True`, its `state_ref` line `res.success = true;`) and a read-back under another
  namespace (`/other_world/get_physics_properties` against `/gazebo/pause_physics`).
- F3: the simulated-only restriction rested on `RosBridge(..., device_mode=...)`, a constructor argument: a package's
  own hardware Driver that builds `RosBridge(..., device_mode="simulated")` with a `sensed_stop` would get one, and its
  manifest would declare no confirmation for the server's start-up check to see.

## F1: only samples published after the subscription count

What can be shown. A new subscription receives samples published before it existed only from a history its
publisher keeps for late subscribers. ROS 1 keeps none except a latched publisher's last message, so at most one
sample per latched publisher. In ROS 2 a `transient_local` publisher replays up to its history depth and a `volatile`
one replays nothing. Through rosbridge (the corpus clone `robots/robotwebtools/rosbridge_suite`, ros2 branch at
`ae4d7f8c`, rosbridge_library 4.2.1), a fresh subscription's reader is transient-local only when every publisher is
(`rosbridge_library/src/rosbridge_library/internal/subscribers.py:170-186`, `ROSBRIDGE_PROTOCOL.md:288-294`), and a
subscription on a topic rosbridge already reads gets one hand-over message (`subscribers.py:224-248`, `293-317`). So
the bound is the publisher's QoS. A rule on stamps or arrival times alone cannot show it: a replayed history and a
fast live stream look the same (simulation time may run faster than real time), and a rule that discarded each
subscription's initial burst would also discard every package fake's samples, since each fake answers a subscription
with one burst. The bound is therefore stated per source, as `history`, and the bridge trusts the stated bound.

The rule (`MHS/sdk/src/mhs/bridge/ros_sensed.py`):

- `replay_bound` (`:213`) reads a resolved history: `{"durability": "volatile"}` gives 0,
  `{"durability": "transient_local", "depth": N}` gives N (1 to 10,000); anything else is refused.
- `compile_profile` (`:365-376`): a ROS 1 source may not declare `history` (bound 1, the latched message); a ROS 2
  source must, or the bridge refuses the configuration. `Source.skip` (`:251`) is `max(1, replay)`: the first sample
  is still discarded on every source, so the five shipped fakes, whose first sample is the pre-request state, behave
  as before.
- `Ring.append` (`:435`) numbers every sample of a subscription before it drops any, and the bridge passes the ordinal
  (`MHS/sdk/src/mhs/bridge/ros.py:1732`). `SourceWindow.add` (`:479`) discards ordinals up to `skip` whatever they
  show; the newest stamp among them is the baseline a counted sample must exceed. A window that counted only the samples
  it saw would discard more after an overflow, never fewer (mutation M02 below); the ordinal keeps live samples after
  a lossy replay counted.

The declaration (`MHS/sdk/src/mhs/driver/sensed_stop.py`): every ROS 2 source of a `RosDriver` declares
`"history": {"durability": "volatile", "ref": "path:LINE"}` or `{"durability": "transient_local", "depth": N,
"ref": "path:LINE"}`, citing the line that creates its publisher with its QoS, or `{"operator_required": reason}` when
the clone does not show it (`_history`, `:401`). An operator_required history is stated by the live deployment in
`simulation_deployment["estop_confirmation"]["history"]` or the driver does not construct (`deployment_member`, `:565`),
and by the fake backend's fixture `history` member (`fixture_history`, `:544`); either may only raise a cited replay
(`resolve_history`, `:433`). The manifest and the reference publish each ROS 2 source's history (cited with its `ref`,
`operator_required`, or the deployment's operator value; `:209`, `MHS/sdk/src/mhs/reference_file.py:963`); a ROS 1
source publishes none, so the three ROS 1 packages' references are unchanged. Gate G7
(`MHS/sdk/src/mhs/driver/ros_check.py`, `_check_history_refs`, `:338`) refuses (`ROS_HISTORY_NOT_SHOWN`) a cited
`transient_local` history whose lines do not show a transient-local durability and the depth, and a cited `volatile`
one whose lines do not create a publisher without a transient-local durability or say volatile. Gate G3
`SENSED_FIXTURE` covers the fixture's histories (`check.py:1781-1786`).

The five sensed-stop packages:

| package | ROS | history | change |
|---|---|---|---|
| tfly6/opendrone | 1 | none (latched message, discarded) | none |
| darienmt/px4-sitl-ros-example | 1 | none | none |
| derek-th-wang/quadruped_ctrl | 1 | none | none |
| larics/mrs_crazyflies | 2 | `/cf_1/pose` volatile, cited `to_copy/crazyflie_server.py:404-405` (`create_publisher(topic_type, ..., 10)`: an integer depth, so rclpy's default volatile durability) | driver.py, facts.md, references, RESULT.json paragraph |
| karthik0497/ros2-amr-simulation | 2 | `/odom` operator_required: its publisher is ros_gz_bridge's parameter_bridge, outside the clone; the clone's bridge entry (`src/robot_description/config/ros_gz_bridge.yaml:23-27`) and launch parameters (`src/robot_description/launch/gazebo.launch.py:144-153`) set no QoS; fake placeholder volatile | driver.py, fixtures/estop-confirmation.json, facts.md, references, RESULT.json paragraph |

Both repaired packages pass G1-G9 with their recorded digests (the gate report has the same findings), keep their
`authored_by` and get a second MODEL REVIEW paragraph (claude-opus-5-5, labelled "second repair, verification F1 of
phase 3"; the earlier author text was shortened at a word boundary to stay within 8,000 characters, as
`review/apply_review.py` does; the full originals are in `development/p3-hardening-3/originals/packages/`).

The trust boundary. The bridge trusts the declared history: a declaration that understates the replay lets the replay
count (`test_the_declared_history_is_the_trusted_bound` pins it). The verifier's `p1.py`, run unchanged against this
tree, still completes, because it builds its device from the test module's default declaration, which now states the
test stand-in's history as volatile (an understatement for p1's five-sample replay). With the history stated as
transient-local depth 5 the same graph is refused (`test_the_verifier_probe_no_longer_confirms`: `sensed_missing`,
latched). This is why a ROS 2 history is cited and checked by G7, or operator_required and then stated by the operator,
and why REVIEW.md item 5 now asks the reviewer to check that the cited line is that source's publisher.

## F2: what a companion read-back means

`_check_readback` (`ros_check.py:189-244`) adds three rules, all under the existing `ROS_COMPANION_READBACK`:

- the read-back is in the stop's namespace, the same simulator world (`_same_world`, `:179`): both names global, both
  relative or both private, with equal segments before the last. `/gazebo/get_physics_properties` passes for
  `/gazebo/pause_physics`; `/other_world/...`, `/gazebo/sim/...`, `/get_physics_properties` and any relative or
  private spelling are refused (a pair of different kinds resolves against namespaces the gate cannot see);
- its `success` path names no acknowledgement field (`_ACK_FIELDS`, `:160`: `success`, `succeeded`, `status_message`,
  `message`, `result`, `ok`, `error`, `error_code`, `error_message`, `error_string`, `errmsg`, `ack`, `acknowledged`,
  `accepted`; `gazebo_msgs/srv/GetPhysicsProperties.srv:8-9` declares `success` and `status_message`);
- its `state_ref` line assigns the compared field from something other than a constant (`_assigned_from_state`,
  `:167`): `res.pause = world_->IsPaused();` (the five packages' line, `gazebo_ros/src/gazebo_ros_api_plugin.cpp:1489`
  at the gazebo_ros_pkgs pin), a keyword argument or a dict entry pass; `res.pause = true;`, a number, a string, a null
  or a bare field declaration do not.

The verifier's `p3.py`, run unchanged against this tree, now reports the acknowledgement message and
`['G7.ROS_COMPANION_READBACK']` for the other world. The five companion packages pass G7 unchanged. Whether the
assigned value is the state the step loop reads, and which value means stopped, stays the reviewer's trace (REVIEW.md
item 13 now says what the gate checks).

## F3: only what the endpoint serves grants a sensed stop

- The bridge (`ros.py`): `device_mode` still refuses anything but `"simulated"` at construction, but no longer grants.
  A sensed confirmation commits a safe state only on a bridge bound to `"simulated"` (`_bind_served_mode`, `:529`); an
  unbound bridge still sends the request steps (they may stop the device) and opens no confirmation
  (`confirmation.reason` `not_simulated`, `:1686`), and the loop checks the binding again before a commit (`:1739`). A
  reset of an unbound bridge is refused (`sensed_reason` `not_simulated`).
- The server (`MHS/sdk/src/mhs/server.py`): at start-up (`:1185`) and on first use of a late device (`:2248`)
  `_bind_sensed_route` (`:9792`) binds a device whose served manifest declares mode `simulated` and the sensed
  confirmation, and only when its bridge builds the SDK's RosBridge through SDK code: the SDK's `RosBridge` itself, or a
  `RosDriver` whose class route members are the SDK's (`_sdk_ros_route_class`, `:9678`) and whose instance carries no
  `make_bridge`, `inner` or `_grant_served_mode` of its own. `RosDriver._grant_served_mode` binds the inner bridge now
  or when `make_bridge` builds it (`MHS/sdk/src/mhs/driver/families.py:1414-1431`). Instance wrappers of the contract
  methods do not prevent the binding: the gate's phase windows (`check.py` `_open_windows`) wrap `estop`,
  `safety_status` and the others on the instance, which makes `_sdk_ros_route` (the receipt rule of CORE-074) false
  inside the gate; whether a receipt may carry the confirmation report stays that rule's separate question.
- Gate G3 (`check.py`, `_g3_sensed_served`, `:1789`): the served manifest is checked as the server checks it at
  start-up (`SENSED_SERVED`: mode `simulated`, the confirmation published), and a RosDriver that overrides its route is
  refused (`SENSED_ROUTE`), since the endpoint would never bind it.

A package's own Driver that builds `RosBridge(..., device_mode="simulated")` is never bound: its e-stop sends the
request, is `failed` `SAFE_STATE_UNREACHED` and stays latched
(`test_a_package_s_own_hardware_bridge_with_device_mode_simulated_gets_no_sensed_stop`). A package can still forge a
binding by calling the SDK's private methods; that is deliberate code that review reads (REVIEW.md item 10), not a
constructor argument.

## Review tool

`MHS/handoff/tools/show_refs.py` now lists, next to the clone's lines, every `fill_refs` line of a sensed source and
each ROS 2 source's cited `history` line (`citations`, the dict-literal branch). REVIEW.md item 5 asks the reviewer to
read both, and before this change the tool listed neither. Its output for the five sensed-stop packages gains those
lines; nothing else changes.

## Normative text, docs and schemas

- `MHS/spec/04-safety.md`: SAFE-049 (samples published after the subscriptions; only what the endpoint serves grants
  the stop; the history cited or operator-supplied) and its traceability row (the G3, G6 and G7 codes).
- `MHS/spec/core.md`: CORE-088 (the binding, the replay discard, `not_simulated`, the history narrow-only).
- `MHS/spec/driver-profile.md`: DRV-012, and the G3 and G7 rows of the gate table.
- `MHS/sdk/docs/ros-driver.md` (the replay, the binding, the read-back meaning), `MHS/handoff/REVIEW.md` items 5 and
  13.
- `MHS/schema/device.schema.json` and `reference.schema.json`: optional `history` on a confirmation source (cited,
  operator value or operator_required), mirrored to `mhs/_data/schema` by `sync_data.py`. Generated:
  `mhs/conformance/applicability.json` (39 ids moved to new spec lines; no count changed), `CHANGELOG.md` block.

## Tests

New: `MHS/sdk/tests/bridges/test_sensed_stop_hardening.py` (24 cases: the replay bound of each generation; refused
undeclared and ROS 1 histories; a deep replay discarded whatever it shows; the ring's ordinals; the verifier's probe
with the stated depth; a deep replay then live airborne samples (`not_confirmed`) and then live landed samples
(confirmed); a replay deeper than the ring; a lossy replay injected straight into the ring; the trusted bound; a ROS 1
latched replay; the declaration's shapes, the fixture and the live deployment (narrow-only, unknown sources); the
manifest and the reference; G7 history citations; the constructor argument that never grants; an unbound reset; the
server's binding, a driver without a server, a late device; a package's own hardware bridge; a RosDriver off the route
and G3; an instance that builds its own bridge; G3's served-manifest check).
`MHS/sdk/tests/driver/test_companion_sources.py` gains `CompanionReadBackMeaningTests` (6 cases, the verifier's probe
among them) and its spelling test now also expects the world rule. `MHS/sdk/tests/handoff/test_tools.py` gains
`test_a_sensed_stop_s_fill_refs_and_history_are_listed`. `MHS/sdk/tests/bridges/test_ros_sensed_stop.py`: its ROS 2
fixtures declare a history, its bridge-level helper binds as the server does, and its forging test now expects the
unbound stop.

Mutation check (`development/p3-hardening-3/scripts/mutate.py`, `logs/mutation-final.json`): 27 mutants of the three
fixes and one of the review tool, each on a fresh copy of the SDK: 26 make the tests fail. The two survivors each
remove one of the attempt's two served-mode guards (M18 before the subscriptions, M26 before a commit), and either
guard alone holds; with both removed (M27) seven tests fail. Both are kept: the second re-checks under the lock right
before a commit. An earlier run (`logs/mutation-1.json`) had a third survivor, M02 (the window counting only the
samples it saw), which errs towards discarding; `test_live_samples_after_a_replay_the_ring_lost_still_confirm` now kills
it.

## Validation

Logs in `development/p3-hardening-3/logs/`.

- SDK suite, full run 1 (`sdk-suite-r1.log`): 3,653 tests OK (5 skipped) in 650 s, load 2.6 at the start and 9.8 at
  the end; registry suite 345 OK; OpenAI4S integration suite 129 OK. Full run 2, on the final tree after the
  review-tool change (`sdk-suite-r2.log`): 3,654 tests OK (5 skipped) in 652 s, load 4.2 at the start and 15.5 at
  the end; registry 345 OK; OpenAI4S 129 OK. No test failed in either run.
- The ten packages this change concerns, the five sensed-stop and the five companion-source packages, pass G1-G9 with
  their recorded digests (`gates-r1/`).
- `collect.py --strict` over every passing package (`collect-final/summary.json`): 715, the same set as snapshot-5,
  all pass the gate with snapshot-5's digests, and every RESULT.json records that digest. The only warning is the
  known MCM3000 PDF citation (`UNVERIFIABLE_CITATION`, user-owned); its chunk exits 1, as in every earlier phase.
- `MHS/registry/build_registry.py --check`: 0 generated files differ. `MHS/registry/validate.py --no-corpus`: PASS.
  The `sync_data`, `build_applicability`, `gen_appendices`, `gen_errors` and `build_changelog` checks pass;
  `INTERFACE.md` is unchanged; no `__pycache__` in the project.
- `show_refs.py` on the two repaired packages: 0 bad citations; the Crazyflie history prints next to
  `to_copy/crazyflie_server.py:404-405`.
- The verifier's probes against this tree: `p3.py` reports the acknowledgement refusal and
  `['G7.ROS_COMPANION_READBACK']` for the other world; `p1.py` as written completes (the trust boundary above), and
  with the depth stated the same graph is refused.

## Digests

No digest moved. Against snapshot-5 all 715 passing digests are unchanged and no package changed status: the two
repaired packages changed files but not their gate findings. Against snapshot-3 (688 passing) no digest of a package
that passed there changed and none stopped passing; the 27 packages passing since then come from helper wave 2 and the
phase-3 apply, not from this change (`digests-vs-snapshot-3.json`).

## Considered and left out

- A rule on stamps or arrival times alone ("discard every sample not newer than the newest one of the subscription's
  initial burst", or a wall-time span): it cannot tell a replay from a fast live stream, and it would also discard every
  package fake's burst.
- Asking rosbridge for a volatile reader (the subscribe `qos` field of rosbridge protocol 2.1.0,
  `ROSBRIDGE_PROTOCOL.md:21`, `rosbridge_library/src/rosbridge_library/capabilities/subscribe.py:254`, `309-311`):
  a fresh reader would then replay nothing and a shared one hands over one message, but an older rosbridge ignores the
  field, and the SDK cannot read the server's version; a later item could add it as a deployment statement.
- A static gate rule against package code that calls the bridge's private binding methods: forging a binding is
  deliberate code that the reviewer reads (REVIEW.md item 10); not added.

## Found, not fixed

- A ROS 1 topic latched by several publishers replays one message per publisher; the bridge discards one. Competing
  publishers on source topics stay a review item (REVIEW.md item 5).
- The cited history is trusted: G7 checks that the cited lines show a publisher and the QoS, not that they create
  the source's publisher; an `operator_required` history is the operator's statement.
- The companion read-back's meaning beyond the three rules (that the assigned value is the state the step loop reads,
  and which value means stopped) stays the reviewer's trace.
- The read-back forms that p3-companion-2 and p3-companion-3 add (a stall read-back, a list-element predicate, a topic
  read-back) were built in parallel from other bases; at integration they meet the F2 rules of `_check_readback`, which
  hold for every companion read-back.

## Rule deviations

None: no git command ran in a clone, nothing was installed, no network was used, and nothing was written outside the
private copy and the session scratchpad except the temporary files that the suites and gates create under the user's
default temporary directory; nothing was deleted (the mutation copies stay in the scratchpad).

## Integrator edits (integrator-v4, claude-opus-5-5, 2026-11-05)

The orchestrator accepted this change after two Claude Sonnet lenses and required these edits when it was composed
with p3-companion-2 onto the actual tree (`snapshot-5`). Each is logged with its before and after sha256 in the
integrator's `MERGE-LOG.json`; the tests are in `MHS/sdk/tests/driver/test_phase3b_hardening_edits.py` and the
mutants in the integrator's `merge/mutants/v4b.json` (17 of 17 killed, unmutated controls pass).

| Edit | Review item | What changed |
|---|---|---|
| R-V4-06 (merge) | the F2 rules meet p3-companion-2's read-back forms | `_check_readback` applies the acknowledgement rule to the state each form compares: the stall path of a stall read-back (whose own `success` only accepts each answer, as `GetModelList`'s `success` does; the plain rule would have refused unitree_ros2_sim, quadruped_sim2sim and sjtu_drone), the selected element's `field` of a list-element predicate, the path otherwise; the assignment rule applies to that compared field only, never to the `where` keys that select the element. |
| I9 | S1 | Gate G3's static scan refuses package code that names a private member of the endpoint's served-mode binding or the bridge's safe-state commit (`_bind_served_mode`, `_grant_served_mode`, `_bind_sensed_route`, `_served_mode`, `_mhs_served_mode`, `_commit_safe_state_locked`, `_safe_state_achieved`, `_safe_stamp`), as an attribute, a name, an imported name, a string or a constant expression. A name computed at run time stays beyond a static scan (REVIEW.md item 10). No package of the tree names one. |
| I10 | S4 | A `state_ref` value that reads the request (`res.x = req.x`, `request->x`, `goal->x`, also inside a larger value or through a dereference or cast) is no state; the acknowledgement fields add `status`, `status_code`, `code`, `return_code`, `result_code`, `done`, `is_done`, `sent`, `completed`, `complete`, `finished`, `executed`, `handled`, `received`. |
| I11 | S5 | A cited history counts no word in a comment, and a `volatile` claim whose `create_publisher` QoS is a variable the cited lines do not define (a predefined rclpy or rmw profile excepted), or whose call they do not close, shows nothing (`ROS_HISTORY_NOT_SHOWN`). larics__mrs_crazyflies's cited publisher passes its QoS as the literal `10` and is unchanged. |
| I12 | S2, E3 | Tests only: `mhs.server._bind_sensed_route` refuses a device not served as `simulated` (directly and for a late hardware device); an unbound bridge opens no subscription (kills this change's mutant M18), and a bridge rebound away from `simulated` during an attempt never commits (kills M26). |
| listed | E1 | Not implemented: larics__mrs_crazyflies's cited publisher builds its topic at run time (`self.cf_dict[link_uri] + "/" + prefix`), so requiring the source's topic on the cited line would refuse a passing package whose citation is right; that the cited line publishes the source's topic stays the reviewer's reading (REVIEW.md item 5). |

The docs say the same: `driver-authoring.md` (the scan), `ros-driver.md` (the read-back fields and the history rule)
and `REVIEW.md` items 5, 10 and 13.

