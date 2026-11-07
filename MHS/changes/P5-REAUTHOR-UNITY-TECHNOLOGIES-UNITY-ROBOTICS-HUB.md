# P5-REAUTHOR-UNITY-TECHNOLOGIES-UNITY-ROBOTICS-HUB — plan-only RosDriver for the Niryo pick-and-place tutorial

The blocked Unity Robotics Hub card (`gh.unity-technologies/unity-robotics-hub`, triage class D) now has a plan-only `RosDriver` package. One exclusive command asks the tutorial service `niryo_moveit` for four pick-and-place trajectories and returns them. `executed` is always false. Nothing in this package starts Unity, the gripper, or `sim_real_pnp.py`. No SDK change was made. The registry card and `task.json` were not edited, so the card stays `package_status` blocked until an integrator rebuilds the registry. `CHANGELOG.md` was not edited; the integrator runs `python3 tools/build_changelog.py`.

Written by Grok (grok-4.7, a model and not a human) as run `ext-p5-reauthor--unity-technologies__unity-robotics-hub-20261105`, in this unit's copy of snapshot-6. The user's decision 3 of 2026-11-05 (Claude authors, a Claude Sonnet model reviews) is read, by the orchestrator, as Grok authors and Codex reviews. `reviewed_by` stays null. Evidence is fake `contract_checked` only. No Unity editor, ROS graph, MoveIt, rosbridge or arm was installed or run.

Nothing was taken from the stopped attempts. Both `development/p5-reauthor/project` and `development/ext-p5-reauthor.fast-stopped/project` still have only `RESULT.json` (sha256 `f11144f65d75f6831caad927eeaff82c1dc387fcae12a9db67271fdb3b6bd645`) and `task.json` (sha256 `02afaaf7d34730cf726c5b983741de01583f476c2282beba05de4a0c06f3187e`) for this package, equal to their base manifests.

## What the package binds

Pin `b8d1e1d4c76c9ce75fc145cdbf55a9072cc77364`, Apache-2.0 on the card, on `LICENSE.md:3` and on `niryo_moveit/package.xml:10`. The SRDF file header is GPL-3.0 (`niryo_one.srdf:8-11`). The lock stays Apache-2.0 and the header is disclosed.

`x-cap.unity-technologies.niryo_pick_place_plan.v1` calls `/niryo_moveit` (`niryo_moveit/MoverService`, `mover.py:128`, type import `mover.py:21`). The callback builds a local `MoveGroupCommander("arm")` (`mover.py:75-76`) and returns four plans: pre-grasp (`:81`), grasp (`:90-92`), pick-up (`:100`), place (`:108`), appended at `:113-117`. Start joints are `req.joints_input.joints` (`:78`), `float64[6]` (`NiryoMoveitJoints.msg:1`), already radians. There is no degree conversion. The grasp stage subtracts 0.05 m from a copy of the pick pose inside the callback (`mover.py:91`). This package does not apply that offset, and a mutant that subtracted it from the recorded pick z was killed. An empty `trajectories` list is how the callback returns early (`mover.py:84-85`, `:94-95`, `:102-103`, `:110-111`). The output contract requires four plans, so that success is `MHS.CAPABILITY.OUTPUT_INVALID`. A `plan()` the callback treats as false (`mover.py:48-53`) is a failed receipt with no output.

The action verb is `invoke` and the action is `exclusive`. The ROS binding `operation` is `read`. `MoverService.srv:1-5` answers trajectories only. An effectful ROS surface without an acknowledged stop would leave e-stop unreached. The software latch is the whole stop (`estop.kind` software, `native` null). There is no unpause. A request already sent is not awaited. `rospy.spin` only waits (`mover.py:130`). It does not serialise service callbacks, so another client of `/niryo_moveit` can be inside `plan_pick_and_place` at the same time, each with its own local commander (`mover.py:75-76`), both talking to the shared MoveIt `move_group` node. Plan only while Unity is not calling the service. Exclusive covers this endpoint's locally active invocations. A deadline or an e-stop does not retire a plan already sent, so remote planning can continue and overlap the next request.

## What stays uncovered

Unity starts `ExecuteTrajectories` only for the response to its own request (`TrajectoryPlanner.cs:147-152`) and writes `Rad2Deg` targets, closing the gripper at the grasp index (`:171-207`). A rosbridge answer is not that callback. The ROS-TCP endpoint (`part_3.launch:5-7`, port 10000), the `/niryo_joints` publisher (`SourceDestinationPublisher.cs:18`) and `sim_real_pnp.py` are not bound. That script subscribes to topic `sim_real_pnp` (`sim_real_pnp.py:173`), waits on action `niryo_one/commander/robot_action` (`:123-124`) and sets `PICK_PLACE_HEIGHT_OFFSET` to 0.065 (`:41`). `niryo_one_ros` is not cited. `demo.launch` passes `simulation_mode` true (`demo.launch:5-7`). `move_group.launch` still defaults `allow_trajectory_execution` to true and `fake_execution` to false (`:15-16`); the callback only calls `plan()`.

Risk stays R0, the card floor. The bound endpoint is the planning service, not a joint command topic and not `cmd_vel`.

## Limits

Joint indexes 0, 1, 3, 4 and 5 are the xacro property pairs (`niryo_one.urdf.xacro:39-42`, `:45-50`). Elbow index 2 is `operator_required`. Its lower property is `-1.397485` (`:43`) and its upper is `${PI/2}` (`:44`). The file sets `PI` to `3.14159265359` (`:37`). The gate does not evaluate `${PI/2}`, so that upper is not stored as a sourced number. Position and orientation components are `operator_required`. `site-limits.example.json` is an example overlay. Its elbow max `1.570796326795` is the operator's reading of `3.14159265359/2`, labeled as an example. `demo.launch:19-21` sets `/move_group/start_state_max_bounds_error` to 0.3. This package does not add 0.3 to the URDF travel. A non-finite number and a quaternion of norm below `1e-6` are `MHS.CAPABILITY.INPUT_INVALID` before the call.

## Checks

`python3 -m mhs.driver check` on the fake backend passed G1-G9. G1 warns `SUBMODULE_SOURCE` twice (expected notes): `moveit_msgs` at gitlink `3175099a2b7fa75f74c36850a716b0fe603c8947` and `ros_tcp_endpoint` at gitlink `993d366b8900bf9f3d2da444fde64c0379b4dc7c`. Gate digest `sha256:f127ad9fcc0dd1781f9a36d7e8fc7151736eb5411f622e6a13cd863568f2cb04`. The first gate failed G8 at 2208 bytes (limit 2048). Action and input descriptions, and the example-overlay reasons, were shortened. `reference.json` and `REFERENCE.md` were regenerated. The second gate passed. `show_refs.py` reported 54 citations and 0 bad.

`PlannerCases` (22 tests, not the nested gate) passed in 1.776 s before the mutants. G9 ran the whole `test_driver.py`, including `DriverGate.test_gate`, and passed. Package mutants were applied one at a time to `driver.py` or `fake.py`, the 22 tests were re-run, and both files were restored (hashes equal). Control exit 0. Every mutant exited 1:

- degree conversion of the recorded start: `test_the_first_plan_starts_at_the_requested_radians_unchanged` (`0.00349... != 0.2`)
- a fifth plan: `test_a_plan_has_four_trajectories_of_the_six_arm_joints` (`OUTPUT_INVALID`, `maxItems` 4)
- `executed` const true: the same test, `True is not one of [False]`
- plans that do not chain: `test_each_plan_starts_where_the_previous_ends`
- `exclusive=False`: `test_the_manifest_is_a_software_latch_and_an_exclusive_command` (`KeyError: 'exclusive'` at `test_driver.py:178`). The in-flight single-call test did not fail for this mutant, so that test does not by itself prove the flag
- `verb="read"`: the manifest test (`'read' != 'invoke'`)
- no zero-quaternion check: `test_a_zero_quaternion_never_reaches_the_service`
- no finite check: `test_a_non_finite_input_never_reaches_the_service`
- no joint index 0 limit: the manifest limit entry and `test_a_joint_outside_a_cited_urdf_limit_is_refused` (`ENVELOPE_VIOLATION` on 3.2 rad)
- `source_name` `niryo_moveit_server`: `test_the_binding_names_the_advertised_service`
- `joint_names` length relaxed, and `points` length relaxed, each alone: `test_the_published_output_contract_fixes_four_plans_of_six_joints`
- both output lengths relaxed: `test_an_empty_trajectory_list_is_a_failed_receipt` (the empty list completed)
- `mode = "hardware"`: the manifest test (`'hardware' != 'simulated'`)
- pick z reduced by 0.05 in the wrapper: `test_the_request_carries_radians_and_leaves_the_poses_unchanged`

The previous passing digest does not exist. The blocked digest `sha256:d282de5fb0b6d6185d973378c470438e050dab3c9919fcb2b3c370bd0f7e9254` is replaced by the digest above because the package was re-authored. `collect.py --strict` on this package passed with 0 warnings. Its fresh gate digest is the same `sha256:f127ad9fcc0dd1781f9a36d7e8fc7151736eb5411f622e6a13cd863568f2cb04`. The two `SUBMODULE_SOURCE` lines are notes.

## Round 1 repair

Codex and Grok each filed the same high finding. The package had said that `rospy.spin` serialises this node's service callbacks and cited `mover.py:130`. That line is only `rospy.spin()`. The sentence was replaced in the driver docstring (`driver.py:34-40`), the fidelity gap (`driver.py:323-326`), `facts.md` Scope (`facts.md:72-76`), `RESULT.json` notes, and the binding paragraph above. Exclusive covers this endpoint's locally active invocations. Another client of `/niryo_moveit` can overlap this callback on the shared MoveIt `move_group` node. Plan only while Unity is not calling the service. A deadline or an e-stop does not retire a plan already sent, so remote planning can continue and overlap the next request.

`test_a_deadline_does_not_retire_a_plan_already_sent` (`test_driver.py:315-348`) documents that on the silent fake. A 100 ms deadline returns unknown while the first `/niryo_moveit` call stays unanswered. The next invoke is sent once the local exclusive lease drops. A short `MHS.DEVICE.BUSY` rejection is retried for up to 2 s and must not add a ROS call. The following e-stop adds no ROS message.

`PlannerCases`: 23 tests, exit 0, 2.061 s. The fake gate was run again and passed G1-G9. The stable digest is still `sha256:f127ad9fcc0dd1781f9a36d7e8fc7151736eb5411f622e6a13cd863568f2cb04`. That digest is the check report without its clock, and the report's findings did not change. `reference.json` and `REFERENCE.md` were regenerated from the corrected gap before that gate. `show_refs.py` reported 54 citations and 0 bad. The mutant list above is the pre-repair run of the 22 tests. Those mutants were not re-run. `RESULT.json` notes are 7992 characters and end with one MODEL REVIEW paragraph. `collect.py --strict` was run again after these edits and passed with 0 warnings. The fresh gate digest is still `sha256:f127ad9fcc0dd1781f9a36d7e8fc7151736eb5411f622e6a13cd863568f2cb04`. `reviewed_by` stays null.

## Integration

Written by Grok (grok-4.7, a model and not a human) on 2026-11-05 while composing the phase-5 units onto snapshot-6. `reviewed_by` stays null. No simulator or hardware run is claimed.

Merged:

- `MHS/drivers/robots/unity-technologies__unity-robotics-hub/RESULT.json`
- `MHS/drivers/robots/unity-technologies__unity-robotics-hub/driver.lock.json`
- `MHS/drivers/robots/unity-technologies__unity-robotics-hub/driver.py`
- `MHS/drivers/robots/unity-technologies__unity-robotics-hub/facts.md`
- `MHS/drivers/robots/unity-technologies__unity-robotics-hub/fake.py`
- `MHS/drivers/robots/unity-technologies__unity-robotics-hub/fixtures/conformance.json`
- `MHS/drivers/robots/unity-technologies__unity-robotics-hub/site-limits.example.json`
- `MHS/drivers/robots/unity-technologies__unity-robotics-hub/test_driver.py`

Generated files (registry cards and records, task.json, reference.json, REFERENCE.md, check-report.json, CHANGELOG.md) were not copied. The integrator regenerates them.

Round-1 review INT-002: the first registry build ran before `reference.json` existed, so `MHS/registry/repos/robots/unity-technologies__unity-robotics-hub.json` omitted `reference.json` from `x-vendor.overlay.files`. The registry was rebuilt after that file was on disk. `overlay.files` now names `reference.json`. `after_apply` generates package references before `build_registry.py`, then runs `build_registry.py --check`. The package gate digest stays `sha256:f127ad9fcc0dd1781f9a36d7e8fc7151736eb5411f622e6a13cd863568f2cb04`. `reviewed_by` stays null.
