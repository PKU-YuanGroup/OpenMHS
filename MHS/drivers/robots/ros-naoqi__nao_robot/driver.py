"""OpenMHS rosbridge driver for the NAO walker ROS 1 node (gh.ros-naoqi/nao_robot).

Scope: the walking interface of ``nao_apps/nodes/nao_walker.py`` at the pinned
commit.  The primary teleoperation interface is the relative ``cmd_vel``
(geometry_msgs/Twist) and ``cmd_pose`` (geometry_msgs/Pose2D) topics; the
stop request uses the relative ``stop_walk_srv`` (std_srvs/Empty)
service.  The node also registers ``cmd_vel_srv`` and ``cmd_pose_srv``; they
are not bound in this selected topic-control profile. The velocity handler
discards a caught RuntimeError; the pose handler returns None on failure.
Neither reply proves a complete device safety transition.
A rosbridge publication is transmission evidence only and never proves motion,
arrival or stopping.

The ``nao_footsteps`` node exposes the footstep clipping helper as
``clip_footstep_srv``.  It is bound as a subordinate computation, not as motion
control: it is the only service in this stack whose reply carries an applied
value that depends on its input, and the card's entry symbol is the clipping
``Params`` class.  The full upstream helper also runs external ``almath``
ellipse and collision routines that the fake does not model.

The card's ``entry_symbols`` name ``nao_apps.nao_footstep_clipping:Params``.
That class exists, but it is a clipping helper, not a ROS endpoint; the pinned
preflight for this card names the walker node as the primary robot surface.
The footstep clipping constants therefore remain facts (they are used by the
separate ``nao_footsteps`` clipping helpers), not limits of this interface.

Every endpoint, type and fact cites the pinned clone at
67476469a1371b00b17538eb6ea336367ece7d44.  This is a configuration-only
RosDriver: it declares no Python native class, never imports the Python 2
upstream node, and the fake transport is ROS-free.  No ROS graph or hardware
was contacted.  Hardware requires an explicit operator endpoint (there is no
default destination) and a human hardware review in ``driver.lock.json``;
``reviewed_by`` stays null in this model-authored package.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The node subscribes to these relative topics under ``nao_walker``; the
#: launch file starts it without a namespace, so the resolved root names are
#: the declared endpoints.  A deployment that namespaces the node must expose
#: the same absolute names through rosbridge remapping.
_CMD_VEL = {
    "topic": "/cmd_vel",
    "type": "geometry_msgs/Twist",
    "operation": "publish",
    "source_name": "cmd_vel",
    "source_ref": "nao_apps/nodes/nao_walker.py:92",
    "type_ref": "nao_apps/nodes/nao_walker.py:41",
    "message": {
        "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
        "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
    },
    "args": {
        "linear.x": {"from": "input.linear_x"},
        "linear.y": {"from": "input.linear_y"},
        "angular.z": {"from": "input.angular_z"},
    },
}

_CMD_POSE = {
    "topic": "/cmd_pose",
    "type": "geometry_msgs/Pose2D",
    "operation": "publish",
    "source_name": "cmd_pose",
    "source_ref": "nao_apps/nodes/nao_walker.py:93",
    "type_ref": "nao_apps/nodes/nao_walker.py:42",
    "message": {"x": 0.0, "y": 0.0, "theta": 0.0},
    "args": {
        "x": {"from": "input.x"},
        "y": {"from": "input.y"},
        "theta": {"from": "input.theta"},
    },
}

#: Ordinary stop request only. The callback waits for the walking engine,
#: but does not retire an earlier start-pose callback or prevent its later
#: velocity effect. It cannot certify the whole selected control scope.
_STOP_CALL = {
    "service": "/stop_walk_srv",
    "type": "std_srvs/Empty",
    "source_name": "stop_walk_srv",
    "source_ref": "nao_apps/nodes/nao_walker.py:103",
    "type_ref": "nao_apps/nodes/nao_walker.py:44",
    "success": {"path": "$", "equals": {}},
}

_STOP_COMMAND = dict(_STOP_CALL, result={"callback_returned": {"value": True}})

#: ``nao_footsteps`` exposes the footstep clipping helper as a service.  It is
#: a computation, not a walking command, and it is the only upstream service in
#: this stack whose reply carries an applied value that depends on its input.
#: The fixed leg is the StepTarget message default; the external left/right
#: constants are not in the clone.
_CLIP = {
    "service": "/clip_footstep_srv",
    "type": "humanoid_nav_msgs/ClipFootstep",
    "source_name": "clip_footstep_srv",
    "source_ref": "nao_apps/nodes/nao_footsteps.py:107",
    "type_ref": "nao_apps/nodes/nao_footsteps.py:45",
    "request": {"step": {"leg": 0}},
    "args": {
        "step.pose.x": {"from": "input.x"},
        "step.pose.y": {"from": "input.y"},
        "step.pose.theta": {"from": "input.theta"},
    },
    "success": {"path": "step.leg", "equals": 0},
    "result": {"map": {"x": "step.pose.x", "y": "step.pose.y", "theta": "step.pose.theta"}},
}

_MOTION_LIMIT = (
    "the pinned node does not state the unit or a safe range for this native motion value; "
    "the deployment operator supplies the bound in site-limits.json"
)

_CLIP_LIMIT = (
    "the pinned clipping helper states footstep clipping constants, not a universal safe workspace; "
    "the deployment operator supplies the bound in site-limits.json"
)

_PUBLISHED_OUTPUT = {
    "published": Field("boolean", description="True when the driver handed the message to rosbridge"),
    "confirmed": Field("boolean",
                       description="Always false: a rosbridge publication carries no execution confirmation"),
}


class NaoWalker(RosDriver):
    """The ROS 1 walking topics and stop service of the pinned NAO stack."""

    device_id = "nao-walker"
    device_kind = "robot.mobile_base"
    mode = "hardware"
    #: A biped walking robot is a mobile base with fall and contact hazards.
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeNaoWalker"}
    vendor = "ros-naoqi"
    model = "NAO"
    display_name = "NAO walker (nao_walker ROS 1 topics and stop)"
    tags = ["ros", "ros1", "nao", "humanoid", "walking", "motion"]
    #: The operator supplies options={"endpoint": "ws://..."}; this package
    #: assumes no rosbridge destination.
    facts = [
        Fact("nao_walker subscribes to the relative cmd_vel, cmd_pose and cmd_step topics and registers the "
             "relative cmd_pose_srv, cmd_vel_srv, cmd_step_srv and stop_walk_srv services.",
             source="upstream_code", ref="nao_apps/nodes/nao_walker.py:92-103"),
        Fact("handleCmdVel forwards the Twist linear.x, linear.y and angular.z components to ALMotion "
             "setWalkTargetVelocity with the node's step frequency; a near-zero Twist sends "
             "setWalkTargetVelocity(0,0,0,0.5).",
             source="upstream_code", ref="nao_apps/nodes/nao_walker.py:138-147"),
        Fact("handleTargetPose calls walkTo in the blocking branch and post.walkTo in the asynchronous branch; "
             "the cmd_pose topic callback uses the default post=True.",
             source="upstream_code", ref="nao_apps/nodes/nao_walker.py:159-175"),
        Fact("handleCmdVelService calls handleCmdVel(req.twist) and returns an empty CmdVelServiceResponse.",
             source="upstream_code", ref="nao_apps/nodes/nao_walker.py:155-157"),
        Fact("stopWalk sends setWalkTargetVelocity(0,0,0,stepFrequency) and then blocks in "
             "waitUntilWalkIsFinished; a RuntimeError is caught and stopWalk returns False.",
             source="upstream_code", ref="nao_apps/nodes/nao_walker.py:120-132"),
        Fact("handleStopWalkSrv returns EmptyResponse when stopWalk returns True and None otherwise.",
             source="upstream_code", ref="nao_apps/nodes/nao_walker.py:208-212"),
        Fact("handleTargetPoseService calls handleTargetPose(req.pose, False) and returns "
             "CmdPoseServiceResponse on True and None otherwise.",
             source="upstream_code", ref="nao_apps/nodes/nao_walker.py:201-206"),
        Fact("The node reads the private step_frequency parameter with a default of 0.5.",
             source="upstream_code", ref="nao_apps/nodes/nao_walker.py:58"),
        Fact("stopWalk passes stepFrequency to setWalkTargetVelocity(0,0,0,...).",
             source="upstream_code", ref="nao_apps/nodes/nao_walker.py:123"),
        Fact("handleCmdVel passes stepFrequency to setWalkTargetVelocity for a nonzero Twist.",
             source="upstream_code", ref="nao_apps/nodes/nao_walker.py:147"),
        Fact("A nonzero cmd_vel calls gotoStartWalkPose before setting the target velocity.",
             source="upstream_code", ref="nao_apps/nodes/nao_walker.py:140-141"),
        Fact("gotoStartWalkPose runs startWalkPose once when use_walk_pose is true and clears "
             "needsStartWalkPose.",
             source="upstream_code", ref="nao_apps/nodes/nao_walker.py:214-217"),
        Fact("nao_footsteps subscribes to the relative footstep topic, registers the relative footstep_srv and "
             "clip_footstep_srv services, and starts the footsteps_execution action server.",
             source="upstream_code", ref="nao_apps/nodes/nao_footsteps.py:102-116"),
        Fact("handleClipSrv reads req.step and returns a ClipFootstepResponse whose step is the result of "
             "handleClipping(req.step).",
             source="upstream_code", ref="nao_apps/nodes/nao_footsteps.py:184-187"),
        Fact("handleClipping sets is_left_support from step.leg != StepTarget.left and rewrites step.pose.x, "
             "step.pose.y and step.pose.theta through clip_footstep_tuple.",
             source="upstream_code", ref="nao_apps/nodes/nao_footsteps.py:177-182"),
        Fact("clip_footstep_on_gait_config clips x to min_step_x..max_step_x, y to min_step_y..max_step_y or "
             "-max_step_y..-min_step_y depending on support, and theta to -max_step_theta..max_step_theta.",
             source="upstream_code", ref="nao_apps/src/nao_apps/nao_footstep_clipping.py:52-65"),
        Fact("clip_footstep applies the gait-config clip, then clip_footstep_with_ellipse and "
             "clip_footstep_to_avoid_collision; clip_footstep_tuple wraps it and constructs an almath.Pose2D.",
             source="upstream_code", ref="nao_apps/src/nao_apps/nao_footstep_clipping.py:105-130"),
        Fact("startWalkPose calls angleInterpolation on the fixed Body pose with a 1.5 second duration.",
             source="upstream_code", ref="nao_apps/src/nao_apps/start_walk_pose.py:43"),
        Fact("stopWalk only calls setWalkTargetVelocity(0,0,0,stepFrequency) and waitUntilWalkIsFinished; it "
             "has no joint-interpolation or pose-cancel call.",
             source="upstream_code", ref="nao_apps/nodes/nao_walker.py:120-132"),
        Fact("nao_footstep_clipping.Params defines the footstep clipping constants min_step_x=-0.04, "
             "min_step_y=0.088, max_step_x=0.08, max_step_y=0.16 and max_step_theta=0.5; these bound the "
             "clipping helpers, not nao_walker's velocity or pose services.",
             source="upstream_code", ref="nao_apps/src/nao_apps/nao_footstep_clipping.py:7-14"),
    ]
    #: One sentence; it deliberately does not claim that the Empty reply proves
    #: the walking engine or a queued footstep action stopped.
    safe_state = (
        "No verified safe state is available: an earlier start-pose callback may set a walking target "
        "after stop_walk_srv returns. The full control package remains blocked."
    )

    parameters = {}
    reads = {}
    commands = {
        "x-cap.ros-naoqi.walk_velocity.v1": _CMD_VEL,
        "x-cap.ros-naoqi.walk_pose.v1": _CMD_POSE,
        "x-cap.ros-naoqi.stop_walk.v1": _STOP_COMMAND,
        "x-cap.ros-naoqi.clip_footstep.v1": _CLIP,
    }
    actions = {
        "x-cap.ros-naoqi.walk_velocity.v1": Action(
            name="walk_velocity",
            description=(
                "Publish a Twist on the cmd_vel teleoperation topic. The receipt is transmission evidence only; "
                "it does not confirm that the base moved or reached a velocity."
            ),
            input={
                "linear_x": Field(
                    "number", unit="1",
                    description="Twist linear.x component passed to setWalkTargetVelocity; the clone states no SI unit",
                    limit=Limit.operator_required(_MOTION_LIMIT),
                ),
                "linear_y": Field(
                    "number", unit="1",
                    description="Twist linear.y component passed to setWalkTargetVelocity; the clone states no SI unit",
                    limit=Limit.operator_required(_MOTION_LIMIT),
                ),
                "angular_z": Field(
                    "number", unit="1",
                    description="Twist angular.z component passed to setWalkTargetVelocity; the clone states no SI unit",
                    limit=Limit.operator_required(_MOTION_LIMIT),
                ),
            },
            output=_PUBLISHED_OUTPUT,
            risk="R2",
        ),
        "x-cap.ros-naoqi.walk_pose.v1": Action(
            name="walk_pose",
            description=(
                "Publish a Pose2D on the cmd_pose teleoperation topic; the callback calls post.walkTo and returns "
                "immediately. The publication receipt cannot show that the target was reached."
            ),
            input={
                "x": Field(
                    "number", unit="1",
                    description="Pose2D x passed to walkTo in the robot coordinate frame; the clone states no SI unit",
                    limit=Limit.operator_required(_MOTION_LIMIT),
                ),
                "y": Field(
                    "number", unit="1",
                    description="Pose2D y passed to walkTo in the robot coordinate frame; the clone states no SI unit",
                    limit=Limit.operator_required(_MOTION_LIMIT),
                ),
                "theta": Field(
                    "number", unit="1",
                    description="Pose2D theta passed to walkTo in the robot coordinate frame; the clone states no SI unit",
                    limit=Limit.operator_required(_MOTION_LIMIT),
                ),
            },
            output=_PUBLISHED_OUTPUT,
            risk="R2",
        ),
        "x-cap.ros-naoqi.stop_walk.v1": Action(
            name="stop_walk",
            description=(
                "Call the upstream stop_walk_srv service, which sets zero walk target velocity and waits for "
                "waitUntilWalkIsFinished. The empty reply reports callback settlement, not proven quiescence."
            ),
            output={
                "callback_returned": Field(
                    "boolean",
                    description="True when the stop_walk_srv callback returned; physical quiescence is not observed",
                ),
            },
        ),
        "x-cap.ros-naoqi.clip_footstep.v1": Action(
            name="clip_footstep",
            description=(
                "Call the nao_footsteps clipping helper with a requested footstep pose. This is a computation, "
                "not a motion command; the reply is the clipped step the helper returns. The full upstream "
                "clipping also uses external almath ellipse and collision routines that the fake does not model."
            ),
            input={
                "x": Field(
                    "number", unit="1",
                    description="Requested footstep x; the clone states no unit for the footprint coordinates",
                    limit=Limit.operator_required(_CLIP_LIMIT),
                ),
                "y": Field(
                    "number", unit="1",
                    description="Requested footstep y; the clone states no unit for the footprint coordinates",
                    limit=Limit.operator_required(_CLIP_LIMIT),
                ),
                "theta": Field(
                    "number", unit="1",
                    description="Requested footstep theta; the clone states no unit for the footprint coordinates",
                    limit=Limit.operator_required(_CLIP_LIMIT),
                ),
            },
            output={
                "x": Field("number", unit="1",
                           description="Clipped footstep x returned by the upstream helper"),
                "y": Field("number", unit="1",
                           description="Clipped footstep y returned by the upstream helper"),
                "theta": Field("number", unit="1",
                               description="Clipped footstep theta returned by the upstream helper"),
            },
        ),
    }
    #: Keep the ordinary stop request, but do not label callback settlement
    #: as an independent whole-device safety proof. G3 retains the R2 blocker.
    safety_bindings = {}
