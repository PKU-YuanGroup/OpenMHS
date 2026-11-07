# Companion topic read-back: a fresh-sample world-state read-back, operator-run bridges and three gz-sim packages

A companion-cited e-stop may now be confirmed by a boolean world-state flag read from fresh topic samples (E2: gz-sim's `WorldStatistics.paused`, since the reply of its world control confirms nothing), and a ROS driver may declare the ros_gz bridges its operator must run (E3: `operator_bridges`, checked by gate G7 and listed in the reference file). Three gz-sim simulator packages pass with the WorldControl pause as their stop: linorobot2, VRX and TortoiseBot. vision-agh/crazyflie-sim was evaluated and stays blocked.

Written by Claude (claude-opus-5-5, a model and not a human) on 2026-11-05 as the phase-3 agent p3-companion-3.

- **Where:** a private project copy (`work/handoff-runs/claude-20261104/development/p3-companion-3/`). The copy is of the p3-companion-2 project as its accepted review left it, which is `snapshot-3` plus the companion-source change (`COMPANION-SOURCES.md`) and the companion-lock change (`COMPANION-LOCKS.md`); `logs/project-copy.json` shows it equals p3-companion-2's base manifest changed by its delta index, file by file.
- **From:** the design in `development/p3-companion-preflight-2/` (`DESIGN-2.json` items E2, E3 and E5, `DESIGN-2.txt`, `PREFLIGHT-2.json`).
- **Status:** not integrated. A Claude Sonnet review follows, as the user decided.
- **What was run:** no hardware, Gazebo, ROS graph, network fetch or human review anywhere below. Every result is `contract_checked` on fakes.

## Why

**The user's decisions of 2026-11-05.** A stop may cite a locally cloned companion repository at a pinned commit (`user-decisions-20261105.json`, decision 1), and the companion versions the version-mismatch packages need were fetched under `work/companions` (`user-authorization-companion-clones.json`, `work/companions/LOCK.json`).

**What preflight 2 found for three of those packages.** linorobot2 and VRX run gz-sim 8 (Harmonic) through ros_gz 1.0.25 (Jazzy); TortoiseBot runs ignition-gazebo 6 (Fortress) through ros_gz 0.244.27 (Humble). Their only stop is the world pause, a WorldControl request on the gz-transport service `/world/<world>/control`. Two things stood in the way:

1. The reply confirms nothing. `OnWorldControlState` queues the request and answers true (`SimulationRunner.cc:1375-1377` in gz-sim 8), and `ProcessWorldControl` applies it later in the step loop (`:1440-1443`). The paused flag is reported only on the topic `/world/<world>/stats`, in `WorldStatistics.paused` (`PublishStats`, `:534`). The SDK refused a topic as a safety binding (`bridge/ros.py` `_binding`).
2. Neither endpoint is on the ROS graph unless someone runs ros_gz's `parameter_bridge` with them: the three clones bridge topics only.

These are E2 and E3 of `DESIGN-2.json`. E5 (a run-time world name) is optional there and is not built (below).

**Conditions that hold.** The orchestrator's SAFE-042 condition (`review/ORCHESTRATOR-DECISIONS.md`): no unpause may resume a stored motion command; where it cannot be cleared first, offer no unpause and say how the operator recovers; for VRX disclose the stored thrust and the waves. The rule the p3-companion-2 integration follows: a read-back confirms only a state value, never an acknowledgement. The phase-3 verification's finding F1 (`sonnet-review/verify-p3/result.json`, lens safety-path): a stream whose freshness is its arrival time alone can confirm from a history replayed on subscribe.

## Design

### E2: a fresh-sample topic read-back

**The binding.** `safety_bindings.safe_state` (that binding only) may be a topic subscription:

```
{"topic": "/world/<world>/stats", "type": "ros_gz_interfaces/msg/WorldStatistics", "operation": "subscribe",
 "success": {"path": "paused", "equals": true},
 "fresh": {"after_request": true, "discard_first": true, "consecutive": 2..5, "within_ms": 200..5000,
           "min_interval_ms": 10..1000}}
```

plus the provenance keys (`source_name`, `source_ref`, `type_ref`, `state_ref`, `description`). It takes no request, mapping, result or `timeout_ms`: the bound is `within_ms`, which must hold the discarded sample and `consecutive` samples `min_interval_ms` apart (`within_ms >= (consecutive + 1) x min_interval_ms`). `success.equals` must be a boolean and `success.path` a field. `RosBridge._fresh_read_back` and `_fresh` validate it; anything else is `MHS.ADAPTER.MANIFEST_INVALID`, a definition problem (G3).

**The runtime** (`RosBridge._topic_read_back`, run by `_perform_safety` after the stop request returned, and by `safe_state()` alone without a request):

1. A new subscription (queue length 1, no throttle) is opened. Its samples go to a bounded stream (`_Stream`, 64 samples) that the receive thread fills in arrival order (`_receive`); a dropped sample is remembered.
2. The first sample is discarded: it may be a latched sample or one already in flight.
3. Every later sample must arrive at least `min_interval_ms` after the sample before it, discarded or not. A sample that arrives sooner restarts the count instead of counting: a history replayed on subscribe arrives as one burst, while gz-sim throttles the statistics to 10 per second (`SimulationRunner.cc:806-808`).
4. A sample whose flag is not `equals` restarts the count. `consecutive` samples in a row that hold the flag confirm the stop.
5. Silence, a sample without a boolean at the path, a lost sample, a closed bridge, a cancellation or the bound (inside the caller's budget) raise, and the e-stop stays unconfirmed: `MHS.SAFETY.SAFE_STATE_UNREACHED`, the latch held, the existing background retry. The subscription is always closed.

Freshness is the arrival time only, because the bridged header is the simulator's header, which `PublishStats` never stamps (ros_gz copies it, `convert/ros_gz_interfaces.cpp:840`), and every `WorldStatistics` field that could serve as a producer stamp (`sim_time`, `real_time`, `iterations`) stops advancing in a paused world (`SimulationRunner.cc:423-429`; `SetPaused` stops the real-time stopwatch, `:1274-1291`). The confirmation therefore says that the producer reported the flag in samples that arrived after the request, not that it still holds afterwards. The read-back never enters the stop-once ledger (`_stop_request_identity` is `None` for a topic).

**The gate.**
- **G7** (`ros_check.py`): a fresh read-back only on the read-back of a companion-cited e-stop (`ROS_FRESH_SCOPE`); the read-back rule (`ROS_COMPANION_READBACK`) now accepts a topic with `fresh` and adds three conditions for it: a boolean `equals`; a compared field that is not an acknowledgement (`success`, `status_message`, `message`, `result`, `accepted`, `ok`); and a topic in the stop's namespace (two global names that differ only in their last segment: the same world). The existing rule still wants the `state_ref` line to show the field (`paused` at `SimulationRunner.cc:534`). The recorded subscription is allowed even when the binding leaves `operation` implicit.
- **G3** (`families.py` `_fresh_budget`, SAFE-028): stop timeout + `within_ms` must fit in `estop_latency_ms` (1000 ms when undeclared).
- **G6** (`behaviour.py`, `FreshFilter`): the gate puts a filter between the fake transport and the bridge three times and requires the e-stop to end `failed` `MHS.SAFETY.SAFE_STATE_UNREACHED` with the latch held each time (`FRESH_FAIL_OPEN`): every sample with the opposite flag (a world still running), every sample withheld (no bridge), and each subscription answered only by a burst of five stale confirming samples (a history replayed on subscribe).

### E3: bridges the operator runs

**The declaration.** `RosDriver.operator_bridges` lists 1 to 8 entries `{"args": <one parameter_bridge argument>, "ref": <a citation that shows its ROS type>, "description"?: <one sentence>}`. The package never starts them. `ros_check.parse_operator_bridge` parses an argument as the bridge's own usage text states it (`parameter_bridge.cpp:30-61` in ros_gz 1.0.25): `<name>@<pkg/srv/Name>` (optionally `@<gz request>@<gz reply>`) for a service, `<name>@<pkg/msg/Name>` then `@`, `[` or `]` and a `gz.msgs`/`ignition.msgs` type for a topic; absolute names only, no whitespace or options. A malformed entry is a definition problem (G3, `families._operator_bridges`), and `DriverModel.operator_bridges` carries the valid ones.

**The gate.** G7 (`_check_operator_bridges`): each bridge's citation (a companion citation is allowed here, a scope extension that DRV-021 now names) must show its ROS type (`ROS_OPERATOR_BRIDGE_REF`), and each bridge must serve a declared binding with the same name, type and direction: a service bridge for a service, a bridge towards ROS for a subscription, towards Gazebo for a publication (`ROS_OPERATOR_BRIDGE_UNUSED`). With an E2 read-back, every endpoint of the stop, the read-back and the re-enable whose `source_ref` cites a companion must be one of them (`ROS_OPERATOR_BRIDGE_MISSING`): a simulator's own transport names are on the ROS graph only through a bridge.

**The reference file.** `reference.json` `safety.operator_bridges` (`reference.schema.json`, mirrored by `sync_data.py`) and a `REFERENCE.md` section "Operator must run" list them (`build.py` `_add_driver_details`, `reference_file.render_markdown`). A package without them renders exactly as before. `show_refs.py` lists each operator bridge's citation with its lines.

**At run time** nothing new is needed: without the bridges the control call is not answered and the read-back sees no sample, so the e-stop fails closed. The optional start-up probe of DESIGN-2 (rosapi lists) is not built.

### Not built: E5

A run-time world name is not built. The three packages name their default worlds, which their clones cite (`turtlebot3_world`, `sydney_regatta`, `default`); with another world their endpoints do not exist and the e-stop fails closed, which each package discloses. The one package whose endpoint is composed at run time, crazyflie-sim, stays blocked for other reasons (below), so E5 would unblock nothing.

### Deviations from DESIGN-2

- **The burst rule.** DESIGN-2's `fresh` had `after_request`, `discard_first`, `consecutive` and `within_ms`. `min_interval_ms` is added, because a discarded first sample covers a history of one sample only (verify-p3 F1 found the same gap for the sensed stop, which p3-hardening-3 is fixing there).
- **Where E2 lives.** DESIGN-2 suggested reusing the sensed-stop counting code (`bridge/ros_sensed.py`). That module is not in this base (it came with p3-sensed-stop into snapshot-4), and its rules need producer stamps, so E2 is a self-contained method of `RosBridge` and a `_Stream` beside the one-sample `_topics`.
- **The E3 coverage rule.** DESIGN-2 asked G7 to match "every safety binding endpoint that the clone's launch does not produce". G7 cannot see what a launch produces, so the rule is tied to what it can see: with an E2 read-back, a companion-cited endpoint must be bridged by the operator. REVIEW.md item 13 asks the reviewer to check that the clone does not already bridge the same names.
- **The acknowledgement and same-world checks** are E2's own. verify-p3 F2 asks for the same for service read-backs; p3-hardening-3 does that in its copy, and the integrator composes the two.

## The three packages

All three keep their `authored_by` (`deepseek-v4.1-flash:1017`, runs `ros-wave-c-*`) and their source pins. Each gets a MODEL REVIEW paragraph in RESULT.json and moves from `blocked` (`HELPER_MISSING`) to `pass`; the author text before the earlier paragraphs is shortened with ` [...]` where the notes would exceed 8000 characters (the originals are in `development/p3-companion-3/originals/packages/`). Each card's companions come from three new entries of the reviewed `companion-sources-lock.json` override (`scripts/write_lock_overrides.py`; every evidence range read back by `triage.companion_problems`, 0 problems), and `driver.lock.json` repeats them.

**Common to the three.**
- The e-stop is a WorldControl request with `pause` true on `/world/<world>/control` (`ros_gz_interfaces/srv/ControlWorld`, `success == true`, 400 ms). The read-back is E2 on `/world/<world>/stats`: two samples, at least 40 ms apart, after a discarded first one, within 600 ms. `estop_latency_ms = 1500`.
- `operator_bridges` names the two `parameter_bridge` arguments; REFERENCE.md lists them under "Operator must run".
- Each fake keeps a paused flag that a control request sets after the next statistics sample (as gz-sim publishes a step's statistics before it processes the world controls), publishes statistics every 100 ms (placeholder) while subscribed, and has four negative switches: no answer, a `success` false reply, a world that keeps running, no statistics.
- The topics a paused world does not publish left the device resource, which now reads no topic, so a reset device stays readable; each command's receipt reports what it sent (TCAP-003).
- Disclosed in `safe_state`, the facts, the fidelity gaps and facts.md: the paused flag in the confirmation window, not a measured standstill; the GUI, a WorldControl `multi_step` or any client can unpause or step the world; arrival-only freshness and what a QoS override of the stats publisher would change; only the default world; the pinned releases.

| Package | Was | Stop and read-back | SAFE-042: the unpause | Other changes | Stable digest |
|---|---|---|---|---|---|
| `robots/linorobot__linorobot2` (R2) | blocked (G6, G8) | `/world/turtlebot3_world/control` and `/stats`; gz-sim 8.15.0, ros_gz 1.0.25, gz-transport 13.6.0 (Jazzy, Harmonic) | Declared re-enable `x-cap.linorobot.resume.v1`: a zero Twist on `/cmd_vel`, then `pause` false. DiffDrive stores the last Twist (`DiffDrive.cc:637-644`; MecanumDrive `:672-676`) and the bridge forwards `/cmd_vel` while paused, so the zero replaces it, unacknowledged; the clone's `command_timeout` also publishes a zero Twist 0.2 s after the last nonzero command on the wall clock (`command_timeout.py:37-48`, launched without `use_sim_time`). | `/odom/unfiltered` left the resource for the read `x-cap.linorobot.odometry.v1`; IMU and scan are silent while paused; the cmd_vel receipt reports the two values sent. | `sha256:227ab2afaa73ee8261ddc8cd428e224506e90cedc8530d0904755af60126a02d` |
| `robots/osrf__vrx` (R2) | blocked (G6, G8) | `/world/sydney_regatta/control` and `/stats`; the same releases | None. The Thruster system stores the last thrust (`Thruster.cc:517-526`) and each joint position controller the last angle target (`JointPositionController.cc:489-492`); a zero thrust would replace the thrust only unacknowledged, an angle target cannot be cleared without a joint reading, and buoyancy, waves and wind act as soon as the world steps. Recovery outside MHS: zero thrust on both sides, stop the teleop, then the GUI's play button or `pause` false. | The previous review's open defects: the clock is the ROS 2 `sec`/`nanosec`; the fake's ParamVec has a header and the rcl_interfaces parameter types; the four command-echo resource reads are gone (each thruster receipt reports the value sent); two facts narrowed to their lines. | `sha256:4f2c65f6dc3388c03def9485be7cc5b9cf3dc6bdf64fd9ec853c11001c75f3a2` |
| `robots/rigbetellabs__tortoisebot` (R2) | blocked (G6, G8) | `/world/default/control` and `/stats`; ignition-gazebo 6.18.0, ros_gz 0.244.27 (Humble, Fortress); the stats bridge type is `ignition.msgs.WorldStatistics` | Declared re-enable `x-cap.rigbetellabs.resume.v1`: a zero Twist, then `pause` false (DiffDrive stores the last Twist, `DiffDrive.cc:654-661`); unacknowledged, and the simulation launch has no command timeout. | `/odom` left the resource (it stays the read `x-cap.rigbetellabs.odom.v1`); the velocity receipt reports the two values sent. publish_review stays required. | `sha256:15e175eeca361df522d9874ca8b09781c3f40de253683e3c384d04bf518f40b5` |

**Risk** (REVIEW.md item 12). All three stay R2: `/cmd_vel` is also linorobot2's and TortoiseBot's real base's command topic (on a hardware graph no world exists and the e-stop fails closed), and VRX's thrusters drive a vessel.

## vision-agh/crazyflie-sim stays blocked

Evaluated against its clone at `95002dc7`, its RESULT.json and `TRIAGE-2.json`; its files are not changed here (the actual tree's copy also carries the p3-sdk-gaps-a and Sonnet paragraphs, which this base does not have). The remaining reasons:

1. **No companion lock at its profile.** The clone pairs ROS 2 Humble with Gazebo Harmonic (`README.md:5-6`), a pairing ros_gz's humble branch builds only from the Gazebo packages "use with caution" (ros_gz 0.244.27 `README.md:7`). The fetched gz-sim 8 clone is pinned for `ros2-jazzy-gzsim8` (needed by linorobot2 and VRX) and the ros_gz 0.244.27 clone for `ros2-humble-gzsim6` (needed by TortoiseBot); a card's companion must carry its LOCK.json entry's profile and be in its `needed_by`. A `ros2-humble-gzsim8` profile is a reviewed LOCK.json entry (and the matching gz-transport), a decision for the orchestrator or the user, not made here.
2. **The endpoint is composed at run time.** The clone itself bridges the control service, as `/world/{world_name_str}/control` from a launch argument whose default is `default` (`evs_gz_utils/launch/gz_step.launch.py:9, 16-37`); the literal never appears, so a RosDriver binding needs E5 or a companion citation, and a second, operator-run bridge of the same service would be a second path.
3. **The package is a direct Driver** over `GzStepExample`, whose `step_simulation` spins without a timeout and discards the response (`gz_step_example.py:36-49`); re-authoring it as a RosDriver is re-authoring work (the user's decision 3 route, with a Sonnet review).
4. **Its citations are in a git submodule** (`evs_gz_utils` at `b8893f58`), which this base cannot read; p3-sdk-gaps-a's submodule reading is in snapshot-5.
5. **A Gazebo pause does not stop cflib clients** (`README.md:76`), so the stop's scope would be the world only.

## Validation

Logs and scripts are in `development/p3-companion-3/` (`logs/`, `scripts/`).

**New tests.** All of them pass.

| Test file | Tests | What it covers |
|---|---|---|
| `MHS/sdk/tests/bridges/test_ros_topic_readback.py` | 18 | a paused world confirms after the discarded first sample (the wire is the control call, one subscribe, one unsubscribe); a first sample that holds the flag still does not count; a world that keeps running, silence, a replayed history alone, and a burst followed by live samples (only the live ones count); a failing sample restarts the count; a sample without a boolean flag ends the attempt early; the reader's bound and its lost-sample flag, and a lost sample ending the attempt; `safe_state()` alone without a request; every e-stop opens its own subscription; no read-back after a failed request; a short caller budget; cancellation and a closed bridge; 20 malformed declarations; `fresh` refused on other bindings; the compiled read-back never enters the stop ledger |
| `MHS/sdk/tests/driver/test_companion_topic_gate.py` | 10 | the parameter_bridge parser (every accepted form; 14 refused forms); a scratch package whose stop, read-back, re-enable and bridges cite a gz-sim-like companion fixture passes G1 to G8 and lists its bridges in both reference files; G3 refuses a worst case beyond the budget and a malformed bridge; G7 refuses a fresh read-back without a companion-cited stop, an acknowledgement field, another world, a `state_ref` without the flag and a non-boolean flag, and accepts an implicit subscription; G7's three operator-bridge findings, a bridge in the wrong direction included; G6 `FRESH_FAIL_OPEN` catches a bridge that confirms without fresh samples (all three modes) and one that counts a replayed burst (the replay mode); `show_refs.py` lists an operator bridge's citation |

The existing companion tests (`test_companion_sources.py`, `test_companion_stall_gate.py`, `test_companion_lock.py`, `test_ros_stall_readback.py`, `test_ros_list_predicate.py`) and the ROS bridge tests (`test_ros.py`, `test_safety_bindings.py`, `test_ros_safety_freshness.py`) pass unchanged (123 tests).

**Mutation check.** `scripts/mutants.py` killed 32 of 32 mutants (`logs/mutants-1.log`: 31 killed and one survivor, a service argument with a direction symbol that the parser still refused for another reason; a parser case for it was added and `logs/mutants-2.log` shows it killed):

| Area | Count | Mutants |
|---|---|---|
| E2 bridge | 13 | the first sample counts; no burst rule; a burst sample counts without a restart; a failing sample does not restart the count; one sample suffices; a lost sample ignored; a non-boolean flag does not end the attempt; the reader treats a stream as a one-sample read; the reader keeps no bound; a non-boolean flag declarable; a bound that cannot hold the samples declarable; `discard_first` may be false; the read-back is a one-sample read |
| G7 | 11 | no `ROS_FRESH_SCOPE`; a non-boolean flag passes; an acknowledgement field passes; another world passes; no `ROS_OPERATOR_BRIDGE_MISSING`, `_REF` or `_UNUSED`; a bridge's direction ignored; an implicit subscription treated as a publication on the wire; relative bridge names parse; a service argument with a direction parses |
| G3, G6, G5, tools | 8 | no fresh budget; malformed bridges pass G3; no `FRESH_FAIL_OPEN` check; the replay filter sends one stale sample; no fresh source for G6; the reference file or REFERENCE.md omits the bridges; `show_refs.py` omits operator-bridge citations |

**The three packages.** Each passes all nine gates with the digest in the table above (`logs/write-results-1.log`); a second gate run after the final registry rebuild and `prepare.py --sync` gave the same three digests (`logs/write-results-digests-1.log`). Their own suites pass: linorobot2 12, VRX 13 and TortoiseBot 12 tests, each including its gate (`logs/package-tests-1.log`). `show_refs.py` reports 0 bad citations for each (`logs/show-refs-<package>.txt`).

**Digests against `snapshot-3`** (`logs/digests-vs-snapshot3-1.json`): 704 packages pass, against 688 in `snapshot-3`; every one of the 688 keeps its `snapshot-3` digest; 16 newly pass: the five of p3-companion and the eight of p3-companion-2 with their recorded digests, and the three here; none was lost.

**Collect.** `collect.py --strict` ran over all 704 passing packages of the private copy, in six chunks (`logs/collect-1/`, `scripts/collect_chunks.py`, 17:14 to 17:27 at a load average of 8 to 14). All 704 pass the gate with their recorded digests: there is no `RESULT_DIGEST_STALE`, `RESULT_UNTRUSTED` or `EXEMPLAR_RESIDUE`. The only warning is the known MCM3000 PDF citation (`UNVERIFIABLE_CITATION`, user-owned), which sets chunk 0's exit code to 1, as in phase 2 and the two earlier companion items. Each of the three packages gets one `COMPANION_SOURCE` note per companion, with the lock alias and the count of fact citations.

**Show refs.** `show_refs.py` ran over the 704 passing packages, with this tool and with the base's tool on the base tree (`logs/show-refs-all-1.json`): no crash, no bad citation, and for the 701 packages both trees pass the two tools print the same text.

**SDK suite.** It ran once (the brief allows two): 3,543 tests OK, 5 skipped, in 629 s at a load average of about 6 to 10 (`logs/sdk-suite-1.log`, `logs/sdk-suite-1.timing`); 3,515 before this change plus the 28 new tests. No timing test failed, so none was re-run. The OpenAI4S integration suite ran 129 tests: OK (`logs/openai4s-suite-1.log`).

**Registry and generators.**
- The registry suite ran 358 tests: OK (`logs/registry-suite-1.log`).
- `validate.py` passed with and without the corpus (`logs/validate-corpus-1.log`, `logs/validate-no-corpus-1.log`).
- `build_registry.py --check`: 0 files differ (`logs/build-registry-check-1.log`).
- The `sync_data.py`, `build_applicability.py`, `gen_appendices.py`, `gen_errors.py` and `build_changelog.py` checks pass, and `MHS/sdk/INTERFACE.md` equals `--print-interface` (unchanged; `logs/generator-checks-1.log`).
- `dispatch.py --stats` is unchanged (done 827, dispatch 15), and `--check-pilot` gives 20 of 20.
- No `__pycache__` is left in the tree.

**Generated changes from the rebuild.**
- The registry rebuild moved the three cards from rule 9 to the override (deciding rule 9: 299 to 296; override: 1260 to 1263; `contract_checked`: 701 to 704). It re-ranks 289 other cards: only `rank`, plus the rank quoted in some `next_action` texts, a global effect of three more passing packages.
- Four family pages change: the gazebo page's wave counts (the three cards moved from wave 5 to wave 3) and quoted ranks on the pylabrobot, qcodes and tag-bridge pages.
- `prepare.py --sync` refreshed the three cards' `task.json` (companions, status, rank) and 284 re-ranked ones.
- These files are generated and were never edited by hand.

## Residual risk

- **What the read-back proves.** The paused flag in samples that arrived after the request, not a measured standstill and not that the world stays paused. Another client, the GUI or a WorldControl `multi_step` can unpause or step the world at any time; MHS does not watch.
- **Freshness.** Arrival time only. A live stream that bunches (a starved receive thread) restarts the count and can leave a correct pause unconfirmed (fails closed). A replayed history arriving spaced out, which the bridge's default publisher does not produce, is not covered beyond the discarded first sample and the burst rule; an operator QoS override of the stats publisher is disclosed in each package.
- **Bridges.** The e-stop works only while the operator runs the two bridges, with the declared arguments and no remapping. The packages cannot check what the operator runs; without them the e-stop fails closed.
- **Stored commands.** linorobot2 and TortoiseBot clear the stored Twist before an unpause with an unacknowledged publication; other publishers may command again. VRX offers no unpause.
- **Versions and worlds.** The deployment's simulator and ros_gz must be the pinned releases (rosbridge cannot read them), and the world must be the default one.

## Composition notes for the integrator

- `bridge/ros.py`, `driver/ros_check.py`, `driver/families.py`, `driver/check.py` and `driver/behaviour.py` change here and in p3-hardening-3 (F1 sensed-stop history, F2 companion read-back meaning, F3 simulated-only). The E2/E3 code is in new functions (`_fresh_read_back`, `_fresh`, `_topic_read_back`, `_Stream`, `parse_operator_bridge`, `_bridge_serves`, `_namespace`, `_check_operator_bridges`, `_fresh_budget`, `_operator_bridges`, `_fresh_source`, `_fresh_fail_open`, `FreshFilter`); the edits inside existing functions are small (`_binding`'s first branch, `_receive`'s publish branch, `_perform_safety`'s dispatch, `_check_readback`'s service condition and three E2 checks, the wire operations, `RosDriver._fill_model`'s two calls).
- p3-hardening-3's F2 (a read-back field named in the `state_ref` line, never an acknowledgement; the same world as the stop) and this item's E2 checks overlap; keep both or fold E2's into F2's rule.
- The integrator-v4 edits for p3-companion-2 (finite stall values, the hung-simulator clock check, a LOCK `needed_by` test, the hardened `fetch_companions.py`) touch the stall code and tools, not E2 or E3.

## Rule deviations

None. Every Python process that imported project code ran with `PYTHONDONTWRITEBYTECODE=1` (no `__pycache__` is left in the tree), no git command was run by hand in any clone or companion (the gate's own read-only `git --no-optional-locks` reads ran with the batch's empty hooks path, `env.sh`), nothing was fetched, installed or deleted, and nothing was written outside the private copy and its scratch directory except the temporary directories the SDK's own tests create under the user's default `TMPDIR`.

## Integrator edits (integrator-v4, claude-opus-5-5, 2026-11-05)

The orchestrator accepted this change after two Claude Sonnet lenses and required the surviving mutants to be killed
where cheap when it was composed with five other inputs onto the actual tree (`snapshot-5`); logged as I17 in the
integrator's `MERGE-LOG.json`. Tests only; no SDK code changed.

| Edit | Review item | What changed |
|---|---|---|
| I17 | safety lens F1 | `test_g7_binds_a_bridge_only_of_the_binding_ros_type`: a world-control bridge with the right name but the ROS type `std_srvs/srv/Empty` serves no binding: one `ROS_OPERATOR_BRIDGE_UNUSED` and two `ROS_OPERATOR_BRIDGE_MISSING` (the stop and the resume). Kills the mutant that drops the type comparison from `_bridge_serves`. |
| I17 | safety lens F2 | `test_samples_that_arrived_after_the_bound_never_count`: paused samples at the producer's period, stamped by the bridge's reader 5 s after the bound (a delayed batch) while the caller keeps the real clock, never confirm: `SAFE_STATE_UNREACHED`, caused by "sample arrived after its bound". Kills the mutant that replaces the `received_at > deadline` guard with `False`. |

Both mutants were re-run in a scratch copy of the composed tree (`merge/mutants/mutants4.json`): killed; the unmutated
control passes.
