OpenMHS is an independent open-source project, not affiliated with or endorsed by Anthropic, and not a reimplementation or compatible dialect of Anthropic's MHS research preview.

# Facts and tags for gh.ros-naoqi/nao_robot

Every fact cites the pinned clone at commit `67476469a1371b00b17538eb6ea336367ece7d44`.
`upstream_code` refs name `path/in/clone:LINE`; a bounded range is used where the
statement spans adjacent lines. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

## Facts

| fact | source | ref |
|---|---|---|
| nao_walker subscribes to the relative cmd_vel, cmd_pose and cmd_step topics and registers the relative cmd_pose_srv, cmd_vel_srv, cmd_step_srv and stop_walk_srv services. | upstream_code | nao_apps/nodes/nao_walker.py:92-103 |
| handleCmdVel forwards the Twist linear.x, linear.y and angular.z components to ALMotion setWalkTargetVelocity with the node's step frequency; a near-zero Twist sends setWalkTargetVelocity(0,0,0,0.5). | upstream_code | nao_apps/nodes/nao_walker.py:138-147 |
| handleCmdVelService calls handleCmdVel(req.twist) and returns an empty CmdVelServiceResponse. | upstream_code | nao_apps/nodes/nao_walker.py:155-157 |
| stopWalk sends setWalkTargetVelocity(0,0,0,stepFrequency) and then blocks in waitUntilWalkIsFinished; a RuntimeError is caught and stopWalk returns False. | upstream_code | nao_apps/nodes/nao_walker.py:120-132 |
| handleStopWalkSrv returns EmptyResponse when stopWalk returns True and None otherwise. | upstream_code | nao_apps/nodes/nao_walker.py:208-212 |
| handleTargetPose calls walkTo in the blocking branch and post.walkTo in the asynchronous branch; the cmd_pose topic callback uses the default post=True. | upstream_code | nao_apps/nodes/nao_walker.py:159-175 |
| handleTargetPoseService calls handleTargetPose(req.pose, False) and returns CmdPoseServiceResponse on True and None otherwise. | upstream_code | nao_apps/nodes/nao_walker.py:201-206 |
| The node reads the private step_frequency parameter with a default of 0.5. | upstream_code | nao_apps/nodes/nao_walker.py:58 |
| stopWalk passes stepFrequency to setWalkTargetVelocity(0,0,0,...). | upstream_code | nao_apps/nodes/nao_walker.py:123 |
| handleCmdVel passes stepFrequency to setWalkTargetVelocity for a nonzero Twist. | upstream_code | nao_apps/nodes/nao_walker.py:147 |
| A nonzero cmd_vel calls gotoStartWalkPose before setting the target velocity. | upstream_code | nao_apps/nodes/nao_walker.py:140-141 |
| gotoStartWalkPose runs startWalkPose once when use_walk_pose is true and clears needsStartWalkPose. | upstream_code | nao_apps/nodes/nao_walker.py:214-217 |
| startWalkPose calls angleInterpolation on the fixed Body pose with a 1.5 second duration. | upstream_code | nao_apps/src/nao_apps/start_walk_pose.py:43 |
| stopWalk only calls setWalkTargetVelocity(0,0,0,stepFrequency) and waitUntilWalkIsFinished; it has no joint-interpolation or pose-cancel call. | upstream_code | nao_apps/nodes/nao_walker.py:120-132 |
| nao_footstep_clipping.Params defines the footstep clipping constants min_step_x=-0.04, min_step_y=0.088, max_step_x=0.08, max_step_y=0.16 and max_step_theta=0.5; these bound the clipping helpers, not nao_walker's velocity or pose services. | upstream_code | nao_apps/src/nao_apps/nao_footstep_clipping.py:7-14 |
| nao_footsteps subscribes to the relative footstep topic, registers the relative footstep_srv and clip_footstep_srv services, and starts the footsteps_execution action server. | upstream_code | nao_apps/nodes/nao_footsteps.py:102-116 |
| handleClipSrv reads req.step and returns a ClipFootstepResponse whose step is the result of handleClipping(req.step). | upstream_code | nao_apps/nodes/nao_footsteps.py:184-187 |
| handleClipping sets is_left_support from step.leg != StepTarget.left and rewrites step.pose.x, step.pose.y and step.pose.theta through clip_footstep_tuple. | upstream_code | nao_apps/nodes/nao_footsteps.py:177-182 |
| clip_footstep_on_gait_config clips x to min_step_x..max_step_x, y to min_step_y..max_step_y or -max_step_y..-min_step_y depending on support, and theta to -max_step_theta..max_step_theta. | upstream_code | nao_apps/src/nao_apps/nao_footstep_clipping.py:52-65 |
| clip_footstep applies the gait-config clip, then clip_footstep_with_ellipse and clip_footstep_to_avoid_collision; clip_footstep_tuple wraps it and constructs an almath.Pose2D. | upstream_code | nao_apps/src/nao_apps/nao_footstep_clipping.py:105-130 |

## Scope and the card's entry symbol

The card's `entry_symbols` names `nao_apps.nao_footstep_clipping:Params`. That class is
present at `nao_apps/src/nao_apps/nao_footstep_clipping.py:7-14`, but it is a helper
that clips footstep poses; it registers no ROS endpoint and controls no hardware by
itself. The pinned preflight for this card names `nao_apps/nodes/nao_walker.py` as the
primary walking surface, so this package is a `RosDriver` over the walker's ROS 1
topics and stop service. The entry symbol is provenance, not a Python native class,
and no upstream Python code is imported or run.

The package binds the primary teleoperation topics `cmd_vel` and `cmd_pose` as
publications, and `stop_walk_srv` as an ordinary stop request, without safety certification. It does not
bind `cmd_vel_srv` or `cmd_pose_srv`: the velocity handler returns its response after an internally caught error,
whereas the pose handler returns None on failure; neither provides whole-device
safety evidence (`nao_apps/nodes/nao_walker.py:155-157,201-206`). A publication is transmission
evidence only; the resource snapshot is empty. The `cmd_step` service and topic are
not exposed because `StepTarget.leg` is compared with `StepTarget.left`/`StepTarget.right`
at `nao_apps/nodes/nao_walker.py:182-188`, and the numeric enum values and pose units
live in the external `humanoid_nav_msgs` package, which the clone does not contain.
Guessing those values would be inventing a wire contract.

The package also binds the `nao_footsteps` node's `clip_footstep_srv` as a subordinate
computation, not as motion control. It is the one service in this stack whose reply
carries an applied value that depends on its input, and the card's entry symbol is the
clipping `Params` class. Its request carries the `StepTarget` message default leg `0`;
the external left/right enum constants are not in the clone, so the fixed leg is a
message default, not a device fact. The full helper also runs external `almath` ellipse
and collision routines; the fake models only the axis clipping, so the fake's clipped
values are a stand-in for the real helper output. The `nao_footsteps` footstep action and
`footstep_srv` are not exposed.

The node registers relative topic and service names. `nao_apps/launch/walker.launch:11`
starts it as `nao_walker` with no namespace, so the package declares the resolved root
names `/cmd_vel`, `/cmd_pose` and `/stop_walk_srv`. A deployment that namespaces the
node must expose those absolute names through the operator's rosbridge remapping.
This is a deployment assumption, not an upstream fact.

## Stop path, pending work and units

`handleStopWalkSrv` (`nao_apps/nodes/nao_walker.py:208-212`) calls `stopWalk`, which
sets zero walk target velocity and blocks in `waitUntilWalkIsFinished`
(`nao_apps/nodes/nao_walker.py:120-132`). A caught `RuntimeError` makes `stopWalk`
return False, and the handler then returns `None`. The external rospy service
converter rejects None as a failed handler response; it does not manufacture
a successful Empty response. A successful wire reply proves callback
settlement at best. It does not prove the walking engine cleared, does not disable
stiffness, does not stop every other NaOqi actuator, and does not cancel the fixed
`startWalkPose` `angleInterpolation` that a first nonzero `cmd_vel` or any `cmd_pose`
can start (`nao_apps/nodes/nao_walker.py:140-141,214-217`;
`nao_apps/src/nao_apps/start_walk_pose.py:43`). The ordinary stop action reports `callback_returned`, never `stopped`,
and is not included in safe_state.achieved_by. A preceding callback can issue
a new walking target after this stop returns, so the complete control remains blocked.

The clone states no SI units or safe ranges for the Twist components passed to
`setWalkTargetVelocity` or for the robot-frame `walkTo` pose. Each numeric input is
therefore `Limit.operator_required`: without an operator overlay every set is refused
`MHS.SAFETY.LIMITS_UNSET`. `site-limits.example.json` is an illustrative overlay, not
a device fact; replace its values with the installed robot's measured envelope. The
clipping constants in `nao_footstep_clipping.Params` are footstep clipping constants,
not velocity, pose or whole-device limits, so they are not copied into this driver.

## Fidelity

The fake is a ROS-free recording transport (`fake.py`, F0 contract evidence). It models
the `advertise`/`publish` command topics, the `clip_footstep_srv` request/response and
the empty stop-service response, and runs no ROS graph, NaOqi, walking engine, physics,
balance controller or clock. Its walk state, counters, poses and negative-path switches
are placeholders. The clip stand-in applies the upstream axis clipping constants but
does not reproduce the external `almath` ellipse or collision-avoidance steps, and its
support-side y branch is a placeholder because the external `StepTarget.left` value is
unknown. The subscription-free empty resource snapshot reports no device state. The
fake does not establish that a real graph delivered a publication, that the node acted
on it, or that a real service call stopped the robot. Actual ROS compatibility, NaOqi
behavior and stop latency require a separate deployment test.

## Safety and review

This is a hardware-mode package at R2 because NAO is a biped mobile robot. The upstream
stop request is an ordinary action only. It is not an estop binding or an
input-free safe-state action: its callback does not retire pending start-pose
work. The R2 strict gate intentionally remains blocked. The clone documents
no independent hardware emergency stop. Official rospy rejects a handler
returning None as a service failure; the fake models that error rather than
a successful empty response. `driver.lock.json` keeps `reviewed_by: null`: a human must review the package (and the
hardware scope) before any hardware backend or rosbridge connection can run. No
hardware run, ROS graph or NaOqi connection has been claimed here.

## Tags

`ros`, `ros1`, `nao`, `humanoid`, `walking`, `motion`
