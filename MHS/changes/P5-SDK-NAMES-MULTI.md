OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# P5-SDK-NAMES-MULTI — one E4 read-back for several named elements

Round 1 of the ext-integrator-B review left the package directory and the companion-sources-lock entry out. The final package decision is block, and the admission rule requires accept. The E4 list predicate in the SDK remains.

This unit is part (3) of item p5-sdk-names: an E4 read-back that confirms several named elements in one safe state, then the repair of `gh.sahilrajpurkar03/nlp-pnp-robotic-arm`. Parts (1) and (2) (literal-composed endpoints, and a RosDriver endpoint composed from a deployment value) are other units. This tree does not contain them.

The package stays a repair. `driver.lock.json` keeps `authored_by` `deepseek-v4.1-flash:1017`, run `ros-wave-c-105`, date `2026-11-05`. `reviewed_by` stays null. One MODEL REVIEW paragraph is appended to `RESULT.json`.

## SDK

`success.where` may be a list of 2 to 4 selector objects. Each selector has the same shape as today's single `where` object: 1 to 4 plain field names, JSON scalar values. The selectors share one `field` and one `equals`. Each selector must match exactly one list element, the matched indexes must be distinct, and each selected element's `field` must equal `equals`. A one-element list is refused, so the object form and the list form stay disjoint. Five or more selectors, an empty selector, a repeated selector and two selectors that match the same element fail. List order does not matter.

The object form is unchanged (`MHS/sdk/src/mhs/bridge/ros.py`, `_passes` still uses the mapping comprehension when `where` is a mapping). `_passes_several` and `RosBridge._where_list` implement the list. G7 (`MHS/sdk/src/mhs/driver/ros_check.py`, `_e4_where`) requires the read-back `state_ref` to show `field` and every key of every selector, and still requires `_assigned_from_state` only for the compared field. A list that is not 2 to 4 well-formed selectors is a problem, so the path is not treated as the compared field.

`MHS/sdk/docs/ros-driver.md` (Success and stopping, and the E4 paragraph) and one sentence of `MHS/handoff/REVIEW.md` item 13 say the same thing. `COMPANION-LOCKS.md` is unchanged: its E4 section still describes the single-element form, and this record is the extension.

Tests: `MHS/sdk/tests/bridges/test_ros_list_predicate.py` (`SeveralElementsTests`, `SeveralBridgeTests`, `SeveralValidationTests`; the eight existing tests stayed) and `MHS/sdk/tests/driver/test_companion_stall_gate.py` (`MultiListGateTests`; `INIT_CPP` line 20 adds `controller_state.kind` after the existing `response->ok = true` line so the older citations stay on the same lines). Nine mutants of `_passes_several`, `_where_list` and `_e4_where` were killed: `only_first_selector`, `distinctness_ignored`, `later_field_not_compared`, `where_list_as_single_object`, `empty_where_returns_true`, `one_element_list_accepted`, `five_selectors_accepted`, `duplicate_selectors_accepted`, `g7_later_selector_key_ignored`.

## Package

`sahilrajpurkar03/nlp-pnp-robotic-arm` was blocked, `HELPER_MISSING`, digest `sha256:364d6f76c486d767fd7f542ad4dc760481c02d34b0ba7bea3dc86cdeaef75623`, on G6 (`ESTOP_FAILED`, `SAFE_STATE_UNREACHED`) and G8 (`SAFE-028`). The C++ node `ur5_pick_place_cpp_r` still has no stop of its own (`src/ur5_moveit_config/src/ur5_pick_place_cpp_r.cpp:495-497` is `executor.cancel()` after the main loop). The e-stop is one `/controller_manager/switch_controller` that deactivates `arm_controller` and `gripper_controller` with `strictness` 1 (`BEST_EFFORT`, `SwitchController.srv:27`) and a 0.4 s timeout (`driver.py` `safety_bindings.estop`). The reply field `ok` is the acknowledgement (`SwitchController.srv:33`). The safe state is one `/controller_manager/list_controllers` answer: two selectors, `{"name": "arm_controller"}` and `{"name": "gripper_controller"}`, `field` `state`, `equals` `inactive` (`controller_manager.cpp:1752-1755` assigns both). `joint_state_broadcaster` is not named.

The triage text asked for a declared re-enable that discloses the open-loop sequence. SAFE-042 forbids a re-enable that resumes a stored command the package cannot clear first. `executePickAndPlace` (`ur5_pick_place_cpp_r.cpp:297-346`) keeps its remaining steps, and deactivating the controllers does not clear them. This package therefore declares no re-enable. `safe_state` says the operator stops `ur5_pick_place_cpp_r` outside MHS, then activates the controllers outside MHS. That conflict is an open question for the orchestrator; the package fails closed.

What the citations support: under STRICT a missing name aborts and switches nothing (`controller_manager.cpp:1021-1024`, `1043-1046`); `deactivate_controllers` deactivates an active controller and releases its interfaces (`:1487-1518`) and can continue past a name that is absent from the realtime list (`:1497-1503`). A controller that stays active makes `ok` false (`:1372-1383`; the service sets `ok` from that result at `:2025-2027`). `ok` can stay true when deactivation lands outside inactive, because `:1510-1515` only logs. `ok` is still only the switch result (`SwitchController.srv:17-19` and `:33`), so the read-back requires the state string `inactive`. `update` runs only while the controller is active, and `write()` still calls `resource_manager_->write` (`:2192-2235`); the trajectory controller aborts its goal, holds a position command, zeroes velocity, acceleration and effort commands when those interfaces exist, releases interfaces and drops the trajectory (`joint_trajectory_controller.cpp:1055-1106`); this deployment's arm `command_interfaces` is position only (`ros2_controllers.yaml:26-27`); the gripper controller's `on_deactivate` releases interfaces and does not abort the action goal (`gripper_action_controller_impl.hpp:310-317`). TopicBasedSystem and `/isaac_joint_commands` (`ur5.ros2_control.xacro:10-12`) are not in the fetched ros2_control clone, so the package does not claim that Isaac joints hold still.

The served manager is the default node name `controller_manager` (`ros2_control_node.cpp:43`). `demo.launch.py:6-7` does not name or remap it. A remapped manager is not served.

The fake answers the two services. `strictness` 2 (STRICT) answers `ok` false and changes nothing when a requested name is missing or a deactivate target is not active (`controller_manager.cpp:1021-1024`, `:1126-1159`). `strictness` 1 (BEST_EFFORT) skips those names and deactivates the controllers that are active (`:1147-1152`). A missing or zero strictness becomes BEST_EFFORT (`:976-986`). `refuse_switch` and a duplicate name answer `ok` false and change nothing. `drop_gripper` omits the gripper from `list_controllers`. `leave_gripper_active` and `reactivate_arm` answer `ok` true and then leave one motion controller active, so the read-back fails. The package tests cover mixed initial states, a repeated stop, and assert that no action has `reenable=True`.

## Lock and registry

`DEV/companions-root/` symlinks every clone directory of the read-only `work/companions` and holds a copy of `LOCK.json` and `README.txt`. The copy appends `gh.sahilrajpurkar03/nlp-pnp-robotic-arm` to `needed_by` of `ros-controls__ros2_control@2.54.4` (commit `7f26da889aa0898442d1c0a135ae001add1a9878`) and `ros-controls__ros2_controllers@2.54.1` (commit `65db73628ebac1948833f0fbdc60973c74d6cd0e`). The real `LOCK.json` is not edited. No clone was fetched. The symlink mode is `a-w` because G1 `lstat`s the path it is given (`upstream.py` `writable_entries`).

Both pins use profile `ros2-humble-gzsim6`. The package README names Isaac Sim (`README.md:14`). G1 checks that the profile's distro token `humble` appears on both sides of `version_evidence`. The cited controller-manager and controller lines do not depend on gz-sim. A strict reading of REVIEW item 13 could still reject this profile for an Isaac package; that is an open question. The package passes G1 on the distro token.

The user text named the ros2_control `needed_by`. ros2_controllers is widened as well because the trajectory drop and the gripper release are facts in that clone. Both are listed under `lock_changes` for the orchestrator.

`build_registry.py` was not run. `triage.py` `lock_problems` requires the package id in the real `LOCK.json` `needed_by`, which does not have it yet, and a failed build must not half-write the registry. The override `MHS/registry/overrides/companion-sources-lock.json`, the registry card, the package `task.json` (identical to the card) and `driver.lock.json` companions are hand-written in the shape `attach_companions` emits: `lock`, `ref`, `local_path`, `repo_url`, `license_spdx` Apache-2.0. `python3 MHS/registry/validate.py --no-corpus` passed (0 errors), including `lock_shape_problems`, which does not read `needed_by`. A full registry rebuild waits until the orchestrator applies the `needed_by` lines.

The card and the record say `package_status` `blocked`, `blocked_on` `ENTRY_UNVERIFIED`, evidence `static_scan`. The fake gate still passes. That pass is not acceptance: controller inactivity is not an Isaac motion stop. `publish_review` stays `required` (licence `NOASSERTION`). The package may not be merged into a published tree before that review.

## Gate

`python3 -m mhs.driver check MHS/drivers/robots/sahilrajpurkar03__nlp-pnp-robotic-arm --backend fake --companions-root <DEV>/companions-root` passed G1 through G9 twice, before and after the card status change, with the same digest `sha256:68883d85a3c1ee993d3a938185bf0194180d6035b9a8bced963e4e95521e84f8`. Evidence is fake `contract_checked` only. No hardware, Isaac Sim, MoveIt or ROS graph was run.

## Taken from stopped attempts

The stopped Claude tree at `development/p5-sdk-names/project` had changed only `MHS/sdk/src/mhs/driver/ros_check.py`. This unit took the idea that a `where` list's keys must all appear in `state_ref`. It did not copy that file: the stopped edit also imports `ros_names` and composes endpoint names, which belong to the other units and would fail to import here.

The stopped Grok tree at `development/ext-p5-sdk-names.fast-stopped/project` had no file whose hash differed from its `base-manifest.json`. Nothing was taken from it.

## Verification

`python3 tools/build_changelog.py` inserted only this fragment into the generated block of `CHANGELOG.md` (four added lines). `tests.handoff.test_tools.ChangelogTests.test_the_shipped_changelog_lists_every_fragment` then passed. The hand-written summary above the fragment block was not edited.

One SDK suite run (`python3 -m unittest discover -s MHS/sdk/tests -t MHS/sdk`) ran 3801 tests in 688.695s and failed: 12 failures, 7 errors, 16 skipped. The changelog failure above was the one this record caused. Re-run alone, the other 14 failing tests failed again in 40.158s. Five PyMMCore modules raise `No module named 'PIL'` (`MHS/sdk/tests/bridges/test_pymmcore_camera.py` line 8 and the same import in the other four); those files match `base-manifest.json`, and Pillow is not installed. `test_reset_through_a_pseudo_terminal` raises `OSError: out of pty devices` (`pty.py` line 58). The MCP screenshot tests fail with `MHS.CAPABILITY.OUTPUT_INVALID: MCP result is invalid` from `mhs/bridge/mcp_client.py` line 316, which this unit did not edit. A second full suite was not run.

After that, on this tree: `tests.bridges.test_ros_list_predicate` 17 ok, `tests.driver.test_companion_stall_gate` 8 ok, `test_driver.SparcPickPlaceCases` 15 ok, and the nine mutants named in the SDK section were killed again. `python3 MHS/handoff/tools/prepare.py --sync` refreshed 0 task.json files. `python3 MHS/registry/validate.py --no-corpus` had already passed with 0 errors after `build_index.py`. `build_registry.py` was not run.

`python3 MHS/handoff/tools/collect.py --strict --companions-root <DEV>/companions-root` was run over every package whose `RESULT.json` says pass (730 directories), in batches of 15 after one full invocation was killed before it wrote a summary. 726 gates passed. This package passed again with digest `sha256:68883d85a3c1ee993d3a938185bf0194180d6035b9a8bced963e4e95521e84f8`. `blackcoffeerobotics/bcr_arm` passed with digest `sha256:73851954e93d31032f21b4702470d7c02bf3be3ce619a083db82cbfcfb9c0d10`, the same value as its unchanged `RESULT.json`. No passing package's re-run digest differed from the digest recorded in its `RESULT.json`. The only `RESULT.json` whose bytes differ from the base manifest is this package. `--strict` exited 1 because four other packages fail the gate in this environment and one passing package has a pre-existing PDF citation warning. Those five are recorded in `REPORT.json`. None of their driver files differ from the base manifest.

## Round 1 review

Codex blocked the package. Two controller findings are fixed in this tree. The Isaac finding is fixed by keeping the package blocked.

STRICT aborts the whole switch when any deactivate target is not active (`controller_manager.cpp:1126-1159`, `clear_requests()` and `return ERROR` at `:1154-1159`). BEST_EFFORT erases that name and continues (`:1147-1152`). A missing name does the same: STRICT returns at `:1021-1024`, and BEST_EFFORT leaves the name off the request list. The e-stop request is therefore `strictness` 1. The two-selector `list_controllers` read-back is unchanged. The fake implements both strictness values. Package tests start with one controller already inactive, in either order, show that an identical STRICT retry leaves the active controller running, and show that the BEST_EFFORT e-stop then makes both inactive and that a further BEST_EFFORT call leaves them inactive. A missing gripper still fails the read-back, and BEST_EFFORT still deactivates the arm.

`SwitchController.srv:11-12` says BEST_EFFORT still tries to stop the remaining controllers. `:27` is `BEST_EFFORT=1` and `:28` is `STRICT=2`. A controller that stays active makes `ok` false (`controller_manager.cpp:1378-1383`, copied to the service reply at `:2025-2027`). `ok` can stay true when `deactivate()` lands outside inactive, because `:1510-1515` only logs. The read-back requires the state string `inactive`. The change record no longer says that the realtime-list continue is what makes `ok` true.

Controller inactivity does not show that Isaac motion stops. SAFE-028 says motion stops and outputs go to the declared safe state (`MHS/spec/04-safety.md:301-304`). The conformance check requires the receipt flag `safe_state_achieved` (`tests_core.py` `safe_028`). This deployment's hardware interface is `topic_based_ros2_control/TopicBasedSystem` with `/isaac_joint_commands` (`ur5.ros2_control.xacro:10-12`). That plugin is not in the ros2_control 2.54.4 clone. The trajectory controller holds the last position command (`joint_trajectory_controller.cpp:1071-1074`). `write()` still runs (`controller_manager.cpp:2233-2235`). The gripper release only clears interfaces (`gripper_action_controller_impl.hpp:310-317`). No pause or stop service was found in the package clone. No new companion was fetched, and the shared `ros2-humble-gzsim6` profile was not retargeted. The package therefore stays `blocked` on `ENTRY_UNVERIFIED`, in the same shape as a passing fake gate with a blocked deployment (`ut-amrl/socialgym2`). The fake gate was re-run on 2026-11-06 with `DEV/companions-root` and passed G1 through G9 with the same digest `sha256:68883d85a3c1ee993d3a938185bf0194180d6035b9a8bced963e4e95521e84f8`. `RESULT.json` records that digest, `failed` `[]`, `status` `blocked`, and `blocked_on` `["ENTRY_UNVERIFIED"]`. `collect.py` warns `RESULT_UNTRUSTED` when a blocked package's gate passes, so this package is not in the passing set that `--strict` re-runs. `authored_by` stays `deepseek-v4.1-flash:1017`. The existing grok MODEL REVIEW paragraph was updated in place. The Claude paragraph was not edited. `reviewed_by` stays null.

The list-predicate tests now include two response elements for one selector, including conflicting states, at `_passes` and at `bridge.estop`. Changing `len(chosen) != 1` to `not chosen` in `_passes_several` fails those two tests. The other nine mutants were already killed; production `_passes_several` was not weakened. `ros.py` was not edited in this round.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-06 while composing the phase-5 units onto snapshot-7. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged the list-predicate SDK and this record:

- `MHS/sdk/src/mhs/bridge/ros.py`
- `MHS/sdk/src/mhs/driver/ros_check.py`
- `MHS/sdk/docs/ros-driver.md`
- `MHS/sdk/tests/bridges/test_ros_list_predicate.py`
- `MHS/sdk/tests/driver/test_companion_stall_gate.py`

Snapshot-6 and snapshot-7 were the same bytes on those paths. The literal and runtime units also edited `ros.py`, `ros_check.py`, and `ros-driver.md`. Those edits were left out with their open high findings, so these files are this unit's copies.

`MHS/handoff/REVIEW.md` is a clean three-way product of this unit's item-13 sentence and the hardware-stop unit's item-13 text against snapshot-6 (`DEV/merge/review-both.md`). The literal and inference edits of `REVIEW.md` were left out.

Package `gh.sahilrajpurkar03/nlp-pnp-robotic-arm`: round 1 (INT-B-001) removed the package directory. The final Codex package decision is `block`, and admission requires `accept`. The tree holds the snapshot-7 bytes again, including `RESULT.json` digest `sha256:364d6f76c486d767fd7f542ad4dc760481c02d34b0ba7bea3dc86cdeaef75623` (`HELPER_MISSING`). The round-0 re-record `sha256:68883d85a3c1ee993d3a938185bf0194180d6035b9a8bced963e4e95521e84f8` is not in the tree. `DEV/originals/r1-before/` keeps that round-0 text.

`MHS/registry/overrides/companion-sources-lock.json` is the snapshot-7 file again: 20 entries, sorted by `package_id`, with no nlp object. `DEV/originals/MHS/registry/overrides/companion-sources-lock.json` is that same file. The round-0 splice is in `DEV/originals/r1-before/`.

`DEV/companions-root/LOCK.json` no longer lists `gh.sahilrajpurkar03/nlp-pnp-robotic-arm` on `needed_by` of `ros-controls__ros2_control@2.54.4` (commit `7f26da889aa0898442d1c0a135ae001add1a9878`) or `ros-controls__ros2_controllers@2.54.1` (commit `65db73628ebac1948833f0fbdc60973c74d6cd0e`). `gh.blackcoffeerobotics/bcr_arm` stays on both lists. The real `work/companions/LOCK.json` was not written. There is no lock change for the orchestrator to apply.

Generated package files and `CHANGELOG.md` were not copied.
