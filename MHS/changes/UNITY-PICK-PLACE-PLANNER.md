OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# UNITY-PICK-PLACE-PLANNER — the Unity ROS-TCP item: no route owns Unity's execution; a plan-only package

The blocked Unity object-pose-estimation demo (`gh.unity-technologies/robotics-object-pose-estimation`, triage class C) now passes as a plan-only `RosDriver` package: one observational command asks the demo's MoveIt service `ur3_moveit` for its five pick-and-place trajectories and returns them, executing nothing. No SDK change was needed and none was made. The simulated arm stays out of reach of any route (Unity executes plans in a coroutine that only its own request starts, and its scripts expose no ROS interface), and the pose estimation service stays uncovered (its image exists only inside Unity); both are recorded with their evidence. No passing package's gate digest moved.

Written by Claude (claude-opus-5-5, a model and not a human) as phase-4 agent p4-unity in a private copy of
`snapshot-5` (`work/handoff-runs/claude-20261104/development/p4-unity/`); not yet applied to the tree. The package is
Claude-authored under the user's decision of 2026-11-05 (decision 3: Claude authors, a Claude Sonnet model reviews
before merge). Evidence is fake `contract_checked` only: no Unity editor, ROS graph, MoveIt, rosbridge, ROS-TCP
endpoint or pose model was installed or run, and `reviewed_by` stays null.

## The triage's three needs, against the pinned clone (45156479)

The triage row (`development/blocked-triage-2/TRIAGE-2.json`) asked for a Unity/ROS-TCP route that owns trajectory
execution, an artifact path for image service requests, and submodule reading. Paths below are in
`robots/unity-technologies/robotics-object-pose-estimation`; `TrajectoryPlanner.cs` is
`PoseEstimationDemoProject/Assets/TutorialAssets/Scripts/TrajectoryPlanner.cs`.

1. **Owning trajectory execution: no route exists.** Unity executes the plans itself: `TrajectoryResponse` starts the
   `ExecuteTrajectories` coroutine for the response to Unity's own `MoverService` request (`TrajectoryPlanner.cs:255`,
   `:258-264`), which writes each point (converted with `Rad2Deg`) to the six ArticulationBody xDrive targets with
   fixed waits and opens and closes the gripper in further coroutines (`:288-333`). The Unity assets use
   `ROSConnection` only in `TrajectoryPlanner.cs` (`:16`, `:377`) and only for two `SendServiceMessage` requests
   (`:175`, `:255`); no script subscribes to a topic or implements a Unity service (a search of the project's
   `Assets` for `Subscribe`, `ImplementService`, `RegisterSubscriber` and `RegisterPublisher` finds none). The ROS-TCP
   endpoint routes exactly a `UR3Trajectory` forwarder, `ur3_moveit` and `pose_estimation_srv`
   (`ROS/src/ur3_moveit/scripts/server_endpoint.py:15-19`), so a ROS-TCP client would reach the same two ROS services
   that rosbridge reaches, and nothing in Unity. Neither a RosDriver profile over ROS-TCP nor a helper can command,
   own or stop the simulated arm without new code in the Unity project, which is outside the pinned clone; the scene
   runs in the editor's Play mode (`Documentation/4_pick_and_place.md:215`), the only control the documentation
   gives over it. The arm and gripper are not covered. The search and the launch files' nodes are logged in
   `development/p4-unity/logs/unity-interface-grep.log`.
2. **Image service requests as artifacts: not built.** The only image is Unity's render, captured in the button
   handler and sent straight in Unity's own request (`TrajectoryPlanner.cs:105-120`, `:168-176`, `:202-216`); no ROS
   topic carries it, so the endpoint has no producer for it. The SDK's artifacts are outputs of the endpoint
   (`MHS/sdk/docs/image-artifacts.md`); a route for a client-supplied input image would be new protocol surface, and
   a faithful request would also have to reproduce Unity's layout: Unity passes the texture width and height as the
   second and third `Image` constructor arguments (in `sensor_msgs/Image`'s field order, height and width) with
   `step` 4 (`TrajectoryPlanner.cs:33-34`, `:170-173`), and the ROS callback reads `image.width` as the height,
   `image.height` as the width and flips the rows (`ROS/src/ur3_moveit/scripts/pose_estimation_script.py:32-35`).
   The pose estimation service stays not covered; the input-image route is listed below as found, not fixed.
3. **Submodules: used as built by p3-sdk-gaps-a.** Four facts cite `ROS/src/moveit_msgs` (one; gitlink `1d6168c0`)
   and `ROS/src/ros_tcp_endpoint` (three; gitlink `c56f5586`, package 0.2.0); the gate reads them from their own object stores
   at the gitlinks and reports `G1.SUBMODULE_SOURCE` for each (BSD and Apache 2.0 by their `package.xml`; not on the
   card). The `robotiq` and `universal_robot` submodules hold real-hardware driver stacks that the upstream launch does
   not start; they are not this repository's device and are not cited for any binding.

The smallest honest route is therefore the existing `RosDriver` over rosbridge (which the upstream image installs,
`docker/Dockerfile:5`) serving the one ROS-side service whose call cannot start anything in Unity: the planner. The
preflight that first blocked the package already named this shape ("return a valid plan while execution is still
blocked; the stock receipt must not certify executed motion or safety",
`work/handoff-runs/mhs-build-20261102/completion-audit/ros-next-batch-preflight-review-v1/CANDIDATE-ASSESSMENTS.md`,
section 9).

## The package (`MHS/drivers/robots/unity-technologies__robotics-object-pose-estimation`)

- `x-cap.unity-technologies.pick_place_plan.v1` (`plan_pick_and_place`) calls `/ur3_moveit`
  (`ur3_moveit/MoverService`, `ROS/src/ur3_moveit/scripts/mover.py:141`, type import `:19`) with the six start angles
  in degrees (the callback converts them, `:66-73`) and the pick and place positions and quaternions, and returns the
  five plans' joint names and points in plan order (pre grasp, grasp, pick up, place, post place, each starting at the
  previous plan's end, `:75-110`) plus `executed`, which is always `false`. The output contract fixes five plans of the
  six arm joints (an enum of the planner's names, `:21`) and six positions per point; anything else is a failed
  receipt (`MHS.CAPABILITY.OUTPUT_INVALID`).
- It is declared an observation (`operation: "read"`, verb `read`) and `exclusive`. The callback plans and returns
  (`mover.py:35-46`, `:61-110`); its state changes are the table box it re-adds to MoveIt's planning scene after a 2 s
  sleep and a new `MoveGroupCommander` in a module global (`:112-126`). A planning call through rosbridge is answered
  to this endpoint, never to Unity, so it starts no Unity coroutine.
- **Disclosed hazard.** Every call replaces the module-global `MoveGroupCommander` (`mover.py:112-116`) and rospy
  serves different clients in parallel, so a call that overlaps Unity's own planning call can mix this package's
  start state or targets into the plan that Unity then executes in its simulation. The action description, the
  fidelity gaps, `facts.md` and the RESULT notes say to plan only while the Unity scene is not planning; the package
  serialises its own calls and cannot see Unity's.
- **Stop.** The profile has only an observational command, so the SDK's software latch is the whole safety path
  (manifest `estop.kind: software`, `native: null`); `safe_state` says that Unity's own pick-and-place is not reached
  and stops only in the editor.
- **Risk.** R1, the card's floor (G3 refuses lower); by the hazard table the package is R0, because it commands no arm.
  The brief's question "a Unity simulation is R0 unless it commands a real arm": no arm, simulated or real, is
  commanded by the package, and the pipeline has no real arm: MoveIt's configured controller is the
  `follow_joint_trajectory` action (`config/ros_controllers.yaml:1-11`), and the nodes `pose_est.launch` starts
  (`launch/pose_est.launch:1-7`, `launch/demo.launch:3-18`, `launch/ros_controllers.launch:6-12`) are the joint state
  publisher, two controller-manager clients, the spawner the documentation expects to die
  (`Documentation/4_pick_and_place.md:211`),
  `move_group` and the three scripts, none of which hosts a controller; and the planning callback never executes.
- **Fake** (`fake.py`): a recording rosbridge transport with placeholder configurations, point counts and spacing;
  it models the five-plan order, the chaining, the degree-to-radian start, failed calls (MoveIt finds no plan:
  `mover.py:78` indexes an empty plan) and three malformed answers for the tests.
- Authorship: `driver.lock.json` `authored_by` claude-opus-5-5, run `p4-unity-20261105`; `reviewed_by` null; the
  source pin and Apache-2.0 licence of the card. The code-less blocked record it supersedes is kept in the agent's
  `moved-aside/snapshot-5-package/` and `originals/snapshot-5/`.

| Package | Status | Gate digest |
|---|---|---|
| gh.unity-technologies/robotics-object-pose-estimation | pass (was blocked: HELPER_MISSING, NEEDS_ARTIFACTS) | sha256:0c5a7633b76e72d8125f13af0ad102bcd9795fcc18b2fc3a4ad787bfc3ddaf98 |

Gate warnings: `G1.SUBMODULE_SOURCE` (two, above) and `G8.SAFE014_NOT_APPLICABLE` (no limit to probe: the suite
awards CL2). `collect.py --strict` passes the package with the two `SUBMODULE_SOURCE` notes.

## Registry

No override is needed: the card's family, helper, mode and risk floor fit the package. Its `package_status` and
`blocked_on` come from `RESULT.json`, so they change at the next registry rebuild; until then `validate.py --no-corpus`
reports the two overlay differences for this card (card `blocked` against overlay `pass`; record evidence
`static_scan` against `contract_checked`), as it did for the phase-3 packages before their rebuild. A trial in a
scratch copy of the private tree (`development/p4-unity/scripts/registry_trial.sh`, log
`logs/registry-trial.log`) ran `build_registry.py --jobs 4` (724 generated files rewritten), `prepare.py --sync`
(359 `task.json` refreshed, this package's among them; its card then reads `package_status: pass`, `blocked_on: []`
and equals its `task.json`), `validate.py --no-corpus` (PASS), the registry suite (345 OK), `collect.py --strict` on
this package and four other refreshed passing packages (5 of 5 pass) and `build_registry.py --check` (0 differ). The
private tree itself is left unrebuilt for the integrator.

## Found, not fixed

- The SDK has no ROS-TCP transport (Unity's binary protocol); a `RosDriver` reaches a ROS-TCP deployment only through
  an operator-run rosbridge. For this repository a ROS-TCP profile would add nothing a rosbridge call cannot do.
- There is no route for a client-supplied input image into a service request (an input artifact); it needs a package
  with a real image producer, and this repository's would also need Unity's swapped-dimension layout.
- `operation: "read"` is the SDK's only non-effectful service category. A pure computation whose callback changes
  only planner state (MoveIt's planning scene and the node's `MoveGroupCommander`) is declared with it here; whether such a callback counts as
  observational is the reviewer's reading (`MHS/sdk/docs/ros-driver.md`, "Success and stopping").
- The repository's sibling Unity demos stay as triaged: `unity-technologies/robotics-nav2-slam-example` and
  `unity-technologies/unity-robotics-hub` (class B).

## Result

In the private copy (Python 3.14.7, the validated environment, no bytecode):

- Gate on the fake backend: G1-G9 pass (warnings above); G7 checks the binding's `source_ref` and `type_ref`;
  `show_refs.py`: 42 citations (the facts), 0 bad, four of them read from the two submodules; `collect.py --strict`
  on the package: pass.
- `collect.py --strict` over all 716 passing packages of the private tree (8 chunks,
  `development/p4-unity/scripts/collect_all.py`, `logs/collect-all-1/summary.json`): 716 pass, 715 with the digest
  their snapshot-5 `RESULT.json` records, one new (this package), no problem; the only strict warning is the allowed
  `UNVERIFIABLE_CITATION` of `gh.amsikking/thorlabs_mcm3000`. Against snapshot-3, 28 digests differ, all of packages
  that did not pass there (27 passed since in phase 3 and helper wave 2; this package).
- `test_driver.py`: the gate case and 14 repository cases, all pass. A mutation check
  (`development/p4-unity/scripts/package_mutants.py`) applies ten mutations to scratch copies of the package (a
  mis-indexed start angle, rotated pose axes, a dropped five-plan length, a dropped joint enum, a non-exclusive
  action, `executed` true, unchained, unconverted and falsely successful fake answers, a dropped six-position length):
  10 of 10 killed (two survived the first round; a truncated-point case and a published-contract case were added).
- No SDK, spec, schema or registry file changed, so the full SDK suite was not run for this item; the registry suite
  ran in the registry trial above (345 OK), and `tools/build_changelog.py --check` passes (109 fragments).

## Integrator edits (integrator-v4, claude-opus-5-5, 2026-11-05)

The orchestrator accepted this change after two Claude Sonnet lenses and required these edits when it was composed
with five other inputs onto the actual tree (`snapshot-5`). Each is logged with its before and after sha256 in the
integrator's `MERGE-LOG.json`.

| Edit | Review item | What changed |
|---|---|---|
| I14 | the orchestrator's requirement from the lenses' F1 and F2 | The plan call is a command, not a read: the action's verb is `invoke` (exclusive), because the `ur3_moveit` callback re-adds the table box to MoveIt's planning scene and replaces the node's shared `MoveGroupCommander` (`mover.py:112-126`). Every numeric input has a bound: `Limit.operator_required(..., path="[*]")` on the start angles, both positions and both quaternions (the URDF states the UR3 joint limits only in radians, `ur3_with_gripper.urdf:361, 389, 417, 445, 473, 501`; no workspace or quaternion bound is stated), with an example overlay `site-limits.example.json`. A bridge wrapper refuses a zero-norm or non-finite quaternion and a non-finite angle or position with `MHS.CAPABILITY.INPUT_INVALID` before the service is called. The descriptions were shortened so the MCP tool, which now lists the five unset bounds, stays within 2 KB (`G8.TOOL_SIZE`). |
| I14 (mutants) | the lens's surviving m8 and m9 | New repository cases kill both: m8 (`mode = "hardware"`) by the manifest case, which now checks the class's mode as well as the served mode, and m9 (`source_name` `ur3_moveit2`) by a case that checks the cited name is the advertised service (`/ur3_moveit`). With four mutants of this edit (no zero check, no finiteness check, verb read, no angle limit): 6 of 6 killed, unmutated control passes. |

Deviation from the requirement's wording: the ROS binding keeps `"operation": "read"`. In `RosBridge` that word means
a call that confirms nothing and needs no stop, and the alternatives fail: an effectful service command needs an
application success predicate, which `MoverService.srv:1-5` (trajectories only) does not offer (G3 refuses the
binding), and an effectful ROS surface without an acknowledged stop leaves every e-stop unreached. The action, the
manifest and the receipts say `invoke`; `facts.md`, the docstring and `driver.py` say why the binding keeps the word.

Results: `test_driver.py` 20 cases OK; all nine gates pass. The gate's findings changed (`G8.SAFE014_NOT_APPLICABLE`
no longer applies: the command now declares limits), so the digest was re-recorded honestly, sha256:0c5a7633... to
sha256:e7df3363c9ce85c3a90a19068e532d93a5f753e3203441f4e117d38d1ff469f3, with a `MODEL REVIEW` paragraph of the
required form (labelled an integrator edit, not a review) in `RESULT.json`; the earlier record is kept in the
integrator's `reviewer-originals/`. The Claude Sonnet summary prepared for this package (decisions-sonnet-6) counts
15 tests; it predates this edit.
