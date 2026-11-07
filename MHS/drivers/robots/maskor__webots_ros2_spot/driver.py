"""OpenMHS rosbridge driver for the Webots ROS 2 Spot simulation (gh.maskor/webots_ros2_spot).

The pinned upstream is a Webots controller plug-in, ``webots_spot.spot_driver.SpotDriver``,
loaded by ``webots_ros2_driver`` through ``resource/spot_control.urdf`` and the
``spot_launch.py`` launch file.  The plug-in is not a standalone Python class that can be
imported without Webots, so this package is a configuration-only :class:`RosDriver` over
rosbridge and declares no Python native class.  The operator runs Webots, the upstream
nodes and rosbridge separately.

Scope is the plug-in's ROS 2 surface:

* ``/cmd_vel`` (``geometry_msgs/msg/Twist``) is the base velocity input.  The callback
  stores the message as ``previous_cmd_vel`` and converts only ``linear.x``, ``linear.y``
  and ``angular.z`` into persistent gait state.  A rosbridge publication is transmission
  evidence only; the callback has no acknowledgement and no stale-command timer.
* ``/joint_states`` (``sensor_msgs/msg/JointState``) and ``/Spot/odometry``
  (``nav_msgs/msg/Odometry``) are explicit read-only observations.
* ``/Spot/stand_up``, ``/Spot/sit_down``, ``/Spot/lie_down`` (``SpotMotion``) and
  ``/Spot/set_height`` (``SpotHeight``) are the posture services.  The callbacks return
  immediately after starting a one-second joint-target transition; they acknowledge the
  start, not the completion or a measured stopped state.
* ``/Spot/lie_down`` with ``override=true`` remains an ordinary posture command.  Its
  callback stores ``fixed_motion`` and the lie targets and acknowledges at once.  The
  e-stop is a sensed-confirmation stop (SAFE-049, simulated only): it clears
  ``/Spot/float_mode`` and requests that lie, and the stop is achieved only when fresh
  ``/Spot/odometry`` samples show the base still in position and orientation and inside
  the lying height band.  While ``fixed_motion`` is set, ``defined_motions`` and
  ``step`` each call ``handle_transforms_and_odometry``.  Once ``previous_rotation``
  exists, both calls publish ``/Spot/odometry``.  The clone does not say ``getTime()``
  stays fixed between them.  ``throttle_ms`` asks rosbridge for a queue of length 1.
  A second copy still queued is overwritten; a copy that arrives after the first was
  forwarded is delivered, and the equal stamp fails closed.  The second copy can also
  carry a zero finite-difference twist, so stillness is read from the pose, not the
  twist.  The first call only stores the pose and does not publish odometry; it still
  publishes ``/joint_states``.  Service answers alone are not the stop.  There is no
  re-enable and no Webots pause.

Every endpoint, type and fact cites the pinned clone at
1245900385c5f0a8f7d153a047886b06010c0524.  The fake is an event-driven ROS-free
recording stand-in; no ROS graph, Webots engine or hardware is contacted by this package.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The controller class is instantiated by the Webots ROS 2 driver plug-in, not by this
#: package: the URDF selects ``webots_spot.spot_driver.SpotDriver``.
_PLUGIN_REF = "resource/spot_control.urdf:4"

#: The launch file runs the Webots controller for the Spot robot and starts Webots.
_LAUNCH_REF = "launch/spot_launch.py:91-109"

#: Type imports for the declared ROS 2 endpoints.
_TYPES_REF = "webots_spot/spot_driver.py:4-12"

#: The Twist subscription: create_subscription(Twist, "/cmd_vel", ...).
_CMD_VEL_REF = "webots_spot/spot_driver.py:197"

#: The two published observations.  The odometry publisher is created with integer depth 1.
_JOINT_STATES_REF = "webots_spot/spot_driver.py:198-200"
_ODOM_REF = "webots_spot/spot_driver.py:201"

#: Webots basic step used by the plug-in, in milliseconds.
_TIMESTEP_REF = "webots_spot/spot_driver.py:161"

#: header.stamp is a builtin_interfaces Time built from Webots getTime().
_ODOM_STAMP_REF = "webots_spot/spot_driver.py:478-481"

#: The first call stores previous_rotation and skips the odometry publish.  Later
#: calls assign header.stamp, pose.pose.position and pose.pose.orientation.  The
#: sensed predicate reads the position and the orientation.  That first call still
#: publishes /joint_states.  The second publish can zero twist: previous_rotation
#: was just stored, and there is no new pose between the two calls.
_ODOM_FIRST_REF = "webots_spot/spot_driver.py:558-560"
_ODOM_POSE_FILL_REF = "webots_spot/spot_driver.py:579-581"
_ODOM_ORIENT_FILL_REF = "webots_spot/spot_driver.py:582-586"

#: While fixed_motion is set and previous_rotation exists, defined_motions and step
#: each publish /Spot/odometry.  The clone does not say getTime() is frozen, so this
#: package does not claim the two publishes must share a stamp.
_DEFINED_ODOM_REF = "webots_spot/spot_driver.py:701-702"
_STEP_ODOM_REF = "webots_spot/spot_driver.py:943-950"

#: nav_launch includes nav2_bringup.  The params file in this clone has no cmd_vel literal.
_NAV_LAUNCH_REF = "launch/nav_launch.py:37-50"

#: The posture services and their callback sites.
_STAND_REF = "webots_spot/spot_driver.py:204"
_SIT_REF = "webots_spot/spot_driver.py:205"
_LIE_REF = "webots_spot/spot_driver.py:206"
_HEIGHT_REF = "webots_spot/spot_driver.py:210-212"

#: The callback converts only these three Twist components into gait state.
_CMD_VEL_CALLBACK_REF = "webots_spot/spot_driver.py:361-388"

#: The stand callback is representative of the three posture callbacks: it sets
#: fixed_motion, checks previous_cmd/override, starts a one-second transition and
#: returns the answer string immediately.
_STAND_CALLBACK_REF = "webots_spot/spot_driver.py:638-648"

#: The lie callback with override=true starts the fixed lie transition and returns
#: "lying down"; with override=false it still sets fixed_motion first and returns the
#: "performing previous command" answer.
_LIE_CALLBACK_REF = "webots_spot/spot_driver.py:662-672"

#: The set_height callback refuses heights outside [-0.2, 0.2] and stores zd = -height.
_HEIGHT_CALLBACK_REF = "webots_spot/spot_driver.py:756-761"

#: The step loop chooses float motion, the fixed-motion target path or the gait path.
_STEP_REF = "webots_spot/spot_driver.py:935-948"

#: The fixed target path decrements n_steps_to_achieve_target once per Webots step.
_DEFINED_MOTIONS_REF = "webots_spot/spot_driver.py:701-727"

#: The odometry publisher fills pose.pose and twist.twist from the Webots pose difference.
_ODOM_FIELDS_REF = "webots_spot/spot_driver.py:562-593"

#: The joint-state publisher writes 12 motor positions and 4 piston positions.
_JOINT_FIELDS_REF = "webots_spot/spot_driver.py:595-613"

#: The upstream declares 12 actuated leg joints.
_NUMBER_OF_JOINTS_REF = "webots_spot/spot_driver.py:22"

#: The float-mode callback only stores a flag that selects float_motion; that path ignores
#: fixed_motion and still translates the base with the last previous_cmd_vel, so neither
#: float mode nor a lie-down request made while it is set is a stop.
_FLOAT_MODE_INIT_REF = "webots_spot/spot_driver.py:218-220"
_FLOAT_MODE_REF = "webots_spot/spot_driver.py:763-767"
_FLOAT_MOTION_REF = "webots_spot/spot_driver.py:769-933"

#: The blocksworld_pose service teleports the robot to one hardcoded pose and lies down;
#: it is a scenario-specific scenario reset, not a general world reset.
_BLOCKSWORLD_REF = "webots_spot/spot_driver.py:625-636"

#: The service type import is on the same line for SpotMotion and SpotHeight.
_SPOT_MOTION_TYPE = "webots_spot_msgs/srv/SpotMotion"
_SPOT_HEIGHT_TYPE = "webots_spot_msgs/srv/SpotHeight"

#: The clone states no numeric range for the three Twist components; only the gait
#: conversion constants exist and they depend on the deployment.  The operator supplies
#: the site's signed velocity envelope.
_LINEAR_LIMIT = Limit.operator_required(
    "the pinned spot_driver callback consumes twist.linear.x without a numeric bound, and the "
    "shipped nav2 velocity_smoother parameters describe the navigation pipeline, not the "
    "plug-in's direct /cmd_vel subscription; the operator supplies the site forward/reverse bound"
)
_LATERAL_LIMIT = Limit.operator_required(
    "the pinned spot_driver callback consumes twist.linear.y without a numeric bound; the "
    "operator supplies the site lateral bound"
)
_ANGULAR_LIMIT = Limit.operator_required(
    "the pinned spot_driver callback consumes twist.angular.z without a numeric bound; the "
    "operator supplies the site yaw-rate bound"
)

#: One geometry_msgs/msg/Twist publication.  The other components stay at the fixed zero
#: template; the three mapped components are the ones the callback reads.
_CMD_VEL = {
    "topic": "/cmd_vel",
    "type": "geometry_msgs/msg/Twist",
    "source_name": "/cmd_vel",
    "source_ref": _CMD_VEL_REF,
    "type_ref": _TYPES_REF,
    "operation": "publish",
    "message": {
        "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
        "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
    },
    "args": {
        "linear.x": {"from": "input.linear_velocity"},
        "linear.y": {"from": "input.lateral_velocity"},
        "angular.z": {"from": "input.angular_velocity"},
    },
    "result": {"map": {"published": "published", "confirmed": "confirmed"}},
}

#: The fixed lie-down posture request.  An ordinary command: the acknowledgement starts
#: the transition and is not a measured stop.  The sensed-confirmation stop below sends
#: the same fixed request as its second step.
_LIE_DOWN = {
    "service": "/Spot/lie_down",
    "type": _SPOT_MOTION_TYPE,
    "source_name": "/Spot/lie_down",
    "source_ref": _LIE_REF,
    "type_ref": _TYPES_REF,
    "request": {"override": True},
    "success": {"path": "answer", "equals": "lying down"},
    "result": {"map": {"answer": "answer"}},
}

#: The stand service maps the caller's override flag and requires the success answer.
_STAND_UP = {
    "service": "/Spot/stand_up",
    "type": _SPOT_MOTION_TYPE,
    "source_name": "/Spot/stand_up",
    "source_ref": _STAND_REF,
    "type_ref": _TYPES_REF,
    "request": {"override": False},
    "args": {"override": {"from": "input.override"}},
    "success": {"path": "answer", "equals": "standing up"},
    "result": {"map": {"answer": "answer"}},
}

#: The sit service is the same shape with its own success answer.
_SIT_DOWN = {
    "service": "/Spot/sit_down",
    "type": _SPOT_MOTION_TYPE,
    "source_name": "/Spot/sit_down",
    "source_ref": _SIT_REF,
    "type_ref": _TYPES_REF,
    "request": {"override": False},
    "args": {"override": {"from": "input.override"}},
    "success": {"path": "answer", "equals": "sitting down"},
    "result": {"map": {"answer": "answer"}},
}

#: The set-height service succeeds with an empty answer; the callback rejects values
#: outside the source range with a nonempty message.
_SET_HEIGHT = {
    "service": "/Spot/set_height",
    "type": _SPOT_HEIGHT_TYPE,
    "source_name": "/Spot/set_height",
    "source_ref": _HEIGHT_REF,
    "type_ref": _TYPES_REF,
    "request": {"height": 0.0},
    "args": {"height": {"from": "input.height"}},
    "success": {"path": "answer", "equals": ""},
    "result": {"map": {"answer": "answer"}},
}

#: Sensed-confirmation stop (SAFE-049, simulated only).  Step 1 clears float mode, which
#: otherwise runs before fixed_motion and keeps applying previous_cmd_vel.  Step 2 starts
#: the lie.  Neither answer is the stop.  While fixed_motion is set, defined_motions
#: (spot_driver.py:702) and step (spot_driver.py:950) can each publish /Spot/odometry.
#: The clone does not say getTime() stays fixed.  throttle_ms 100 is rosbridge
#: throttle_rate with queue_length 1: a waiting copy is overwritten, and a copy that
#: arrives after the first was published is forwarded.  An equal stamp fails closed.
#: Stillness is position and orientation span, not twist.  Thresholds are
#: operator_required.  min_span_ms 200 matches the fake's 100 ms ticks; a 32 ms producer
#: needs a lower min_span_ms in simulation_deployment.  There is no re-enable: a later
#: /cmd_vel or gait input clears fixed_motion, and previous_cmd_vel is not cleared here.
_NO_LYING_BAND = (
    "the clone states no lying height band for pose.pose.position.z; the operator supplies "
    "the band a lying base must stay inside"
)
_NO_REST_BOUND = (
    "the clone states no at-rest bound on pose.pose.position; the operator supplies the largest "
    "change over the confirmation window that still counts as still"
)
_NO_STILL_QUAT = (
    "the clone states no at-rest bound on pose.pose.orientation; the operator supplies the largest "
    "change of this quaternion component over the confirmation window that still counts as still. "
    "Twist is not the check: the second publish in one step can carry a zero finite difference "
    "after previous_rotation is stored"
)
_FLOAT_OFF = {
    "service": "/Spot/float_mode",
    "type": "std_srvs/srv/SetBool",
    "source_name": "/Spot/float_mode",
    "source_ref": _FLOAT_MODE_INIT_REF,
    "type_ref": _TYPES_REF,
    "request": {"data": False},
    "success": {"path": "success", "equals": True},
    "timeout_ms": 2000,
    "description": "clear float mode so the step loop can run the lie; success is only the callback flag",
}
_LIE_REQUEST = {
    "service": "/Spot/lie_down",
    "type": _SPOT_MOTION_TYPE,
    "source_name": "/Spot/lie_down",
    "source_ref": _LIE_REF,
    "type_ref": _TYPES_REF,
    "request": {"override": True},
    "success": {"path": "answer", "equals": "lying down"},
    "timeout_ms": 2000,
    "description": "start the fixed lie transition; the answer string is not a measured stop",
}
_SENSED_STOP = {
    "request": [_FLOAT_OFF, _LIE_REQUEST],
    "sources": {
        "odom": {
            "topic": "/Spot/odometry",
            "type": "nav_msgs/msg/Odometry",
            "source_name": "/Spot/odometry",
            "source_ref": _ODOM_REF,
            "type_ref": _TYPES_REF,
            "throttle_ms": 100,
            "fill_refs": {
                "pose.pose.position": _ODOM_POSE_FILL_REF,
                "pose.pose.orientation": _ODOM_ORIENT_FILL_REF,
            },
            "history": {"durability": "volatile", "ref": _ODOM_REF},
        },
    },
    "predicate": [
        {"source": "odom", "path": "pose.pose.position.x", "name": "rest_x", "unit": "m",
         "span_max": Limit.operator_required(_NO_REST_BOUND)},
        {"source": "odom", "path": "pose.pose.position.y", "name": "rest_y", "unit": "m",
         "span_max": Limit.operator_required(_NO_REST_BOUND)},
        {"source": "odom", "path": "pose.pose.position.z", "name": "lying_z", "unit": "m",
         "range": {"min": Limit.operator_required(_NO_LYING_BAND),
                   "max": Limit.operator_required(_NO_LYING_BAND)}},
        {"source": "odom", "path": "pose.pose.orientation.x", "name": "still_qx", "unit": "1",
         "span_max": Limit.operator_required(_NO_STILL_QUAT)},
        {"source": "odom", "path": "pose.pose.orientation.y", "name": "still_qy", "unit": "1",
         "span_max": Limit.operator_required(_NO_STILL_QUAT)},
        {"source": "odom", "path": "pose.pose.orientation.z", "name": "still_qz", "unit": "1",
         "span_max": Limit.operator_required(_NO_STILL_QUAT)},
        {"source": "odom", "path": "pose.pose.orientation.w", "name": "still_qw", "unit": "1",
         "span_max": Limit.operator_required(_NO_STILL_QUAT)},
    ],
    "consecutive": 3,
    "min_span_ms": 200,
    "max_gap_ms": 500,
    "confirm_within_ms": 3000,
    "description": (
        "After /Spot/float_mode is set false and /Spot/lie_down is requested, three consecutive "
        "fresh /Spot/odometry samples show the base still in x, y and orientation and inside the "
        "lying height band; the service answers are not the stop."
    ),
}

_VECTOR3 = Field(
    "object",
    description="Three-component vector from the upstream message",
    properties={
        "x": Field("number", unit="1", description="x component"),
        "y": Field("number", unit="1", description="y component"),
        "z": Field("number", unit="1", description="z component"),
    },
)

_ODOM_POSITION = Field(
    "object",
    description="nav_msgs/Odometry pose.pose.position in the odom frame",
    properties={
        "x": Field("number", unit="m", description="Position x"),
        "y": Field("number", unit="m", description="Position y"),
        "z": Field("number", unit="m", description="Position z"),
    },
)

_ODOM_ORIENTATION = Field(
    "object",
    description="nav_msgs/Odometry pose.pose.orientation as a quaternion",
    properties={
        "x": Field("number", unit="1", description="Quaternion x"),
        "y": Field("number", unit="1", description="Quaternion y"),
        "z": Field("number", unit="1", description="Quaternion z"),
        "w": Field("number", unit="1", description="Quaternion w"),
    },
)

_ODOM_TWIST = Field(
    "object",
    description="nav_msgs/Odometry twist.twist filled by finite differences of the Webots pose",
    properties={
        "linear": Field(
            "object",
            description="Linear velocity components",
            properties={
                "x": Field("number", unit="m/s", description="Linear x"),
                "y": Field("number", unit="m/s", description="Linear y"),
                "z": Field("number", unit="m/s", description="Linear z"),
            },
        ),
        "angular": Field(
            "object",
            description="Angular velocity components",
            properties={
                "x": Field("number", unit="rad/s", description="Angular x"),
                "y": Field("number", unit="rad/s", description="Angular y"),
                "z": Field("number", unit="rad/s", description="Angular z"),
            },
        ),
    },
)

_JOINT_POSITIONS = Field(
    "array",
    unit="rad",
    description="JointState.position: 12 leg motor sensors followed by 4 unactuated piston entries",
    items=Field("number", unit="rad", description="One joint position in radians"),
    length=16,
)

_PUBLISHED = {
    "published": Field("boolean", description="True when the driver handed the Twist to rosbridge"),
    "confirmed": Field("boolean",
                       description="Always false: a rosbridge publication carries no execution confirmation"),
}

_ANSWER = {
    "answer": Field("string", description="The upstream service's answer text; a started transition is not completion"),
}

_HEIGHT = Field(
    "number",
    unit="m",
    description="Requested body height offset; the callback stores zd = -height",
    limit=Limit(min=-0.2, max=0.2, source="upstream_code", ref="webots_spot/spot_driver.py:757"),
)


class WebotsSpot(RosDriver):
    device_id = "webots-spot"
    device_kind = "robot.mobile_base"
    mode = "simulated"
    risk = "R2"
    ros_version = 2
    backends = {"fake": ".fake:FakeWebotsRos2Spot"}
    display_name = "Webots ROS 2 Spot simulation"
    vendor = "MASKOR"
    model = "Spot in Webots"
    tags = ["ros", "ros2", "webots", "simulation", "spot", "quadruped", "mobile-base", "cmd-vel"]
    facts = [
        Fact("The URDF selects the webots_spot.spot_driver.SpotDriver plug-in for the Spot robot.",
             source="upstream_code", ref=_PLUGIN_REF),
        Fact("The launch file creates a WebotsController for robot_name Spot and starts the Webots world.",
             source="upstream_code", ref=_LAUNCH_REF),
        Fact("The plug-in imports geometry_msgs Twist, sensor_msgs JointState, nav_msgs Odometry, "
             "std_srvs SetBool and the webots_spot_msgs SpotMotion and SpotHeight service types.",
             source="upstream_code", ref=_TYPES_REF),
        Fact("The plug-in creates a geometry_msgs/Twist subscription on the absolute /cmd_vel topic.",
             source="upstream_code", ref=_CMD_VEL_REF),
        Fact("The plug-in publishes sensor_msgs/JointState on /joint_states.",
             source="upstream_code", ref=_JOINT_STATES_REF),
        Fact("The plug-in creates a nav_msgs/Odometry publisher on /Spot/odometry with integer history depth 1.",
             source="upstream_code", ref=_ODOM_REF),
        Fact("The plug-in registers SpotMotion services /Spot/stand_up, /Spot/sit_down and /Spot/lie_down.",
             source="upstream_code", ref="webots_spot/spot_driver.py:204-206"),
        Fact("The plug-in registers the SpotHeight service /Spot/set_height.",
             source="upstream_code", ref=_HEIGHT_REF),
        Fact("The /cmd_vel callback stores the message as previous_cmd_vel, clears fixed_motion and, when no "
             "/Spot/inverse_gait_input publisher exists, converts linear.x, linear.y and angular.z into "
             "persistent gait state; it returns no acknowledgement and starts no stale-command timer.",
             source="upstream_code", ref=_CMD_VEL_CALLBACK_REF),
        Fact("The stand callback sets fixed_motion=True, checks previous_cmd against request.override, starts a "
             "one-second movement_decomposition to the stand targets and returns the answer string immediately.",
             source="upstream_code", ref=_STAND_CALLBACK_REF),
        Fact("The lie callback sets fixed_motion=True before checking previous_cmd/override; with override=true it "
             "starts the one-second lie transition and returns 'lying down'.",
             source="upstream_code", ref=_LIE_CALLBACK_REF),
        Fact("The set_height callback refuses request heights outside [-0.2, 0.2] and otherwise stores zd as "
             "the negated height.",
             source="upstream_code", ref=_HEIGHT_CALLBACK_REF),
        Fact("The step loop runs float_motion whenever float_mode is set, before it checks fixed_motion; "
             "otherwise it runs defined_motions while fixed_motion is set and spot_inverse_control when it is not.",
             source="upstream_code", ref=_STEP_REF),
        Fact("defined_motions moves each leg motor by step_difference toward the target and decrements "
             "n_steps_to_achieve_target once per call; when the count is spent it clears previous_cmd unless a "
             "paw motion is pending.",
             source="upstream_code", ref=_DEFINED_MOTIONS_REF),
        Fact("The odometry publisher fills pose.pose.position, pose.pose.orientation and twist.twist from the "
             "Webots pose and finite differences.",
             source="upstream_code", ref=_ODOM_FIELDS_REF),
        Fact("The plug-in sets the Webots robot timestep to 32.",
             source="upstream_code", ref=_TIMESTEP_REF),
        Fact("handle_transforms_and_odometry builds a builtin_interfaces Time from Webots getTime(), with sec "
             "and nanosec.",
             source="upstream_code", ref=_ODOM_STAMP_REF),
        Fact("handle_transforms_and_odometry stores previous_rotation and previous_translation when they are "
             "not yet set.",
             source="upstream_code", ref=_ODOM_FIRST_REF),
        Fact("The odometry message sets header.stamp and pose.pose.position.x, pose.pose.position.y and "
             "pose.pose.position.z.",
             source="upstream_code", ref="webots_spot/spot_driver.py:575-581"),
        Fact("defined_motions calls handle_transforms_and_odometry.",
             source="upstream_code", ref=_DEFINED_ODOM_REF),
        Fact("step calls handle_transforms_and_odometry after the float_mode, fixed_motion or inverse branch.",
             source="upstream_code", ref=_STEP_ODOM_REF),
        Fact("nav_launch.py includes nav2_bringup bringup_launch.py and passes params/nav2_params.yaml.",
             source="upstream_code", ref=_NAV_LAUNCH_REF),
        Fact("The joint-state publisher writes the motor sensor positions (motors_pos) followed by zero positions "
             "for four unactuated piston joints.",
             source="upstream_code", ref=_JOINT_FIELDS_REF),
        Fact("The plug-in declares NUMBER_OF_JOINTS = 12 for the actuated leg joints.",
             source="upstream_code", ref=_NUMBER_OF_JOINTS_REF),
        Fact("SpotDriver.init sets float_mode to False, stores an empty Twist as previous_cmd_vel and registers "
             "the std_srvs SetBool service /Spot/float_mode.",
             source="upstream_code", ref=_FLOAT_MODE_INIT_REF),
        Fact("float_mode_cb assigns request.data to float_mode and returns success=True for every "
             "request.",
             source="upstream_code", ref=_FLOAT_MODE_REF),
        Fact("The float_motion path sets every leg motor position to zero, moves and yaws the base by "
             "previous_cmd_vel and resets the physics of the base and its children; it reads neither fixed_motion "
             "nor n_steps_to_achieve_target and does not zero previous_cmd_vel.",
             source="upstream_code", ref=_FLOAT_MOTION_REF),
        Fact("The GaitInput callback __gait_cb sets fixed_motion to False and copies the message fields "
             "into the gait state.",
             source="upstream_code", ref="webots_spot/spot_driver.py:403-420"),
        Fact("The blocksworld_pose callback moves the Spot node to a hardcoded translation and rotation, "
             "sets fixed_motion and starts the lie transition.",
             source="upstream_code", ref=_BLOCKSWORLD_REF),
        Fact("get_ros2_nodes creates the SpotArm WebotsController, controller_manager spawners for the arm "
             "trajectory, joint-state broadcaster and gripper controllers, and the retract_manipulator node.",
             source="upstream_code", ref="launch/spot_launch.py:20-88"),
    ]
    safe_state = (
        "Simulated only: /Spot/odometry shows the base still in x, y and orientation and inside the lying height "
        "band for three consecutive fresh samples after /Spot/float_mode false and /Spot/lie_down. Service answers "
        "are not the stop. Nothing is claimed past that window. Float mode, /cmd_vel, gait input and the stored "
        "previous_cmd_vel can move the base again. SpotArm is not stopped and Webots is not paused. Reset only "
        "re-checks that sensed state."
    )
    #: Two request timeouts of 2000 ms plus confirm_within_ms of 3000 ms.
    estop_latency_ms = 7000
    fidelity = {
        "engine": "analytic:ROS-free recording fake (no Webots physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned service replies and topic samples; no Webots engine, gait, contacts, "
                     "sensors, clock or pacing, and no trajectory or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free recording transport: it answers the declared endpoints and runs no Webots "
            "engine, gait, contact, sensor or wall-clock loop",
            "a /cmd_vel publication is recorded and echoed into the placeholder odometry twist; it does not "
            "step the simulated robot or establish the commanded motion",
            "the stand/sit/lie replies are canned; the one-second joint transition performed by "
            "defined_motions is not simulated",
            "joint and odometry resource samples are placeholders, not captured traffic or Webots state; the "
            "sensed subscription is a separate placeholder burst and is not a cache of the resource read",
            "the e-stop is a sensed-confirmation stop (SAFE-049, simulated only): /Spot/float_mode data false, then "
            "/Spot/lie_down override true, then three consecutive fresh /Spot/odometry samples still in x, y and "
            "orientation and inside the lying height band; the SetBool flag and the answer string are not the stop; "
            "thresholds are operator_required and fixtures/estop-confirmation.json holds fake placeholders only",
            "while fixed_motion is set, defined_motions calls handle_transforms_and_odometry "
            "(webots_spot/spot_driver.py:702) and step calls it again (webots_spot/spot_driver.py:950); after "
            "previous_rotation exists both calls publish and assign header.stamp from getTime() (478-481, assigned "
            "at 577); the first call only stores the pose (558-560) and still publishes joint states; this package "
            "reads the two publishes as one stamp, and the clone does not say getTime() stays fixed; the second "
            "publish can carry a zero finite-difference twist after previous_rotation is stored (571-573), so the "
            "predicate uses orientation span and not twist; throttle_ms 100 is sent as rosbridge throttle_rate with "
            "queue_length 1; that queue overwrites a copy still waiting and forwards a copy that arrives after the "
            "first was published, and the equal stamp then fails closed; the fake models that timing and does not "
            "run rosbridge or Webots",
            "min_span_ms 200 matches the fake's 100 ms producer ticks, so three counted samples span 200 ms; a 32 ms "
            "producer (webots_spot/spot_driver.py:161) puts three one-step samples 64 ms apart and needs a lower "
            "min_span_ms in simulation_deployment['estop_confirmation'] (the floor is 0); a live Webots step slower "
            "than max_gap_ms, or the one-second lie (movement_decomposition duration 1) that outlasts "
            "confirm_within_ms, fails closed until the operator raises those two bounds there; throttle_ms stays on "
            "the declaration and the deployment cannot replace it; confirm_within_ms 3000 and max_gap_ms 500 are "
            "fake-scale client bounds, not device facts",
            "the stop does not clear previous_cmd_vel, does not pause Webots, and declares no re-enable; "
            "/Spot/float_mode true applies the stored velocity and ignores fixed_motion, and any /cmd_vel or gait "
            "input clears fixed_motion; reset re-confirms the sensed state read-only and is refused when that "
            "state no longer holds; physics can move the base out of the band, which fails closed",
            "a stand, sit or lie request refused with 'performing previous command' still sets fixed_motion "
            "upstream and so stops the gait although the receipt reports failure, and a /cmd_vel clears "
            "fixed_motion; the fake models neither side effect",
            "spot_launch.py also starts a SpotArm WebotsController with ros2_control arm and gripper "
            "trajectory controllers; the arm is outside this package and nothing here stops it",
            "/joint_states and /Spot/odometry are published only from the plug-in's step, which also runs "
            "rclpy.spin_once: while Webots is paused or before its first step the resource topics are silent, every "
            "command waits for the 2 s resource read (a probe with silent subscriptions took 2.0 s per command) and "
            "resource reads fail MHS.DEVICE.NOT_READY, and the posture services are not answered; the fake always "
            "answers",
            "nav_launch.py includes nav2_bringup (launch/nav_launch.py:37-50); any publisher of /cmd_vel clears "
            "fixed_motion at the callback (webots_spot/spot_driver.py:361-363), so a navigation stack started by "
            "that launch competes if it writes /cmd_vel; this clone's params/nav2_params.yaml contains no cmd_vel "
            "string, and this package does not state that nav2 publishes /cmd_vel",
            "the posture and set-height services return the answer string before their one-second motion "
            "sequence completes; a live deployment must not treat the acknowledgement as completion",
            "the Webots process, the ROS graph, namespace remapping, QoS and the upstream webots_spot_msgs "
            "package are operator deployment concerns outside this package",
        ],
    }

    parameters = {
        "joint_positions": _JOINT_POSITIONS,
        "odom_position": _ODOM_POSITION,
        "odom_orientation": _ODOM_ORIENTATION,
        "odom_twist": _ODOM_TWIST,
    }
    reads = {
        "joint_positions": {
            "topic": "/joint_states",
            "type": "sensor_msgs/msg/JointState",
            "source_name": "/joint_states",
            "source_ref": _JOINT_STATES_REF,
            "type_ref": _TYPES_REF,
            "path": "position",
            "timeout_ms": 2000,
        },
        "odom_position": {
            "topic": "/Spot/odometry",
            "type": "nav_msgs/msg/Odometry",
            "source_name": "/Spot/odometry",
            "source_ref": _ODOM_REF,
            "type_ref": _TYPES_REF,
            "path": "pose.pose.position",
            "timeout_ms": 2000,
        },
        "odom_orientation": {
            "topic": "/Spot/odometry",
            "type": "nav_msgs/msg/Odometry",
            "source_name": "/Spot/odometry",
            "source_ref": _ODOM_REF,
            "type_ref": _TYPES_REF,
            "path": "pose.pose.orientation",
            "timeout_ms": 2000,
        },
        "odom_twist": {
            "topic": "/Spot/odometry",
            "type": "nav_msgs/msg/Odometry",
            "source_name": "/Spot/odometry",
            "source_ref": _ODOM_REF,
            "type_ref": _TYPES_REF,
            "path": "twist.twist",
            "timeout_ms": 2000,
        },
    }
    commands = {
        "x-cap.maskor.cmd_vel.v1": _CMD_VEL,
        "x-cap.maskor.stand_up.v1": _STAND_UP,
        "x-cap.maskor.sit_down.v1": _SIT_DOWN,
        "x-cap.maskor.lie_down.v1": _LIE_DOWN,
        "x-cap.maskor.set_height.v1": _SET_HEIGHT,
    }
    actions = {
        "x-cap.maskor.cmd_vel.v1": Action(
            name="publish_velocity",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one geometry_msgs/Twist to the upstream /cmd_vel subscription; the receipt confirms "
                "only that rosbridge accepted the publication, not motion, arrival or stopping"
            ),
            input={
                "linear_velocity": Field(
                    "number",
                    unit="m/s",
                    description="Body-frame forward velocity; the callback uses twist.linear.x",
                    limit=_LINEAR_LIMIT,
                ),
                "lateral_velocity": Field(
                    "number",
                    unit="m/s",
                    description="Body-frame lateral velocity; the callback uses twist.linear.y",
                    limit=_LATERAL_LIMIT,
                ),
                "angular_velocity": Field(
                    "number",
                    unit="rad/s",
                    description="Body-frame yaw rate; the callback uses twist.angular.z",
                    limit=_ANGULAR_LIMIT,
                ),
            },
            output=_PUBLISHED,
        ),
        "x-cap.maskor.stand_up.v1": Action(
            name="stand_up",
            verb="invoke",
            risk="R2",
            description=(
                "Call /Spot/stand_up and require the 'standing up' answer; the callback returns after starting "
                "a one-second joint-target transition, so the answer is not completion"
            ),
            input={
                "override": Field(
                    "boolean",
                    description="Passed to the upstream SpotMotion.override field; true bypasses a previous fixed motion",
                ),
            },
            output=_ANSWER,
        ),
        "x-cap.maskor.sit_down.v1": Action(
            name="sit_down",
            verb="invoke",
            risk="R2",
            description=(
                "Call /Spot/sit_down and require the 'sitting down' answer; the callback returns after starting "
                "a one-second joint-target transition, so the answer is not completion"
            ),
            input={
                "override": Field(
                    "boolean",
                    description="Passed to the upstream SpotMotion.override field; true bypasses a previous fixed motion",
                ),
            },
            output=_ANSWER,
        ),
        "x-cap.maskor.lie_down.v1": Action(
            name="lie_down",
            verb="invoke",
            risk="R2",
            description=(
                "Fixed /Spot/lie_down call with override=true; it sets fixed_motion and starts the fixed lie "
                "targets. It acknowledges the start only. The sensed stop sends this request and confirms on "
                "odometry; this command alone is not that stop"
            ),
            output=_ANSWER,
        ),
        "x-cap.maskor.set_height.v1": Action(
            name="set_height",
            verb="invoke",
            risk="R2",
            description=(
                "Call /Spot/set_height with a body height offset in the source range; the callback stores "
                "zd = -height and returns an empty answer on success"
            ),
            input={"height": _HEIGHT},
            output=_ANSWER,
        ),
    }
    # The lie-down acknowledgement is not a stop.  SAFE-049 confirms on /Spot/odometry after
    # float mode is cleared and the lie is requested.  No safe_state action and no re-enable.
    safety_bindings = {"sensed_stop": _SENSED_STOP}
