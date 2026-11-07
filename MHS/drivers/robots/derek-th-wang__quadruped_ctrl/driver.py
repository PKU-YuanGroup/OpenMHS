"""OpenMHS rosbridge driver for the quadruped_ctrl pybullet simulator.

The pinned upstream is a ROS 1 Melodic catkin package.  Its node is
``scripts/walking_simulation.py``: a pybullet mini-cheetah simulation that
registers the relative ``gait_type`` and ``robot_mode`` services, subscribes
to the relative ``cmd_vel`` topic, and publishes odometry and IMU observations.
This package is a configuration-only :class:`RosDriver` over rosbridge; it
declares no Python native class and does not start ROS, rosbridge or pybullet.

The selected interface is the simulator's motion-control surface plus its two
principal observations.  A rosbridge publication is transmission evidence
only.  The node registers no stop service or action: the upstream callbacks
set a gait, set a mode value or store a velocity command, and the pybullet
loop keeps running until ``rospy.is_shutdown()``.  The fixed ``stand`` command
requests gait 4, but the controller honours the gait type only in robot mode 0;
in robot mode 1, which the node selects before entering its endless run loop,
the gait is chosen from the commanded speed and the request is ignored.  No
acknowledged request is therefore a stop by itself (model review 2026-11-04).
This simulated package declares a sensed-confirmation stop (SAFE-049, the
user's decision of 2026-11-05, simulated devices only): the e-stop publishes a
zero Twist (standing in robot mode 1 once the filtered speed decays) and
requests gait 4 (standing in robot mode 0), and it is achieved only when the
``/robot_odom`` pose stays still within a standing height band and the
``/imu0`` angular rate stays small in three consecutive fresh samples within
the bound; otherwise it fails ``MHS.SAFETY.SAFE_STATE_UNREACHED`` with the
latch held and is retried in the background.

Every endpoint, type and fact cites the pinned clone at
6e1093c1d67ff835c02d66d0ad611d2c67d912ad.  The fake transport is ROS-free;
no ROS graph, simulator process or hardware is contacted.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The launch file starts the Python simulation node under this name.
_LAUNCH_REF = "launch/quadruped_ctrl.launch:8-9"

#: The node registers its services and the command subscriber on the relative
#: names "gait_type", "robot_mode" and "cmd_vel".
_ROS_SETUP_REF = "scripts/walking_simulation.py:64-66"

#: The service/type imports at the top of the node.
_SRV_TYPE_REF = "scripts/walking_simulation.py:20"
_TWIST_TYPE_REF = "scripts/walking_simulation.py:19"
_ODOM_TYPE_REF = "scripts/walking_simulation.py:18"
_IMU_TYPE_REF = "scripts/walking_simulation.py:17"

#: The service callbacks and the Twist callback.
_GAIT_CALLBACK_REF = "scripts/walking_simulation.py:386-388"
_MODE_CALLBACK_REF = "scripts/walking_simulation.py:390-392"
_CMD_VEL_CALLBACK_REF = "scripts/walking_simulation.py:394-396"

#: The odometry and IMU publishers.
_ODOM_PUBLISHER_REF = "scripts/walking_simulation.py:413"
_IMU_PUBLISHER_REF = "scripts/walking_simulation.py:433"
#: The producer lines of the sensed fields: the base position into the odometry pose, the base angular velocity
#: into the IMU message (both stamped with rospy.Time.now(), :415 and :445).
_ODOM_POSITION_FILL_REF = "scripts/walking_simulation.py:418-420"
_IMU_RATE_FILL_REF = "scripts/walking_simulation.py:438-440"

#: The C++ controller stores the gait and mode; the mode is not a stop.
_GAIT_SETTER_REF = "src/GaitCtrller.cpp:65-68"
_MODE_SETTER_REF = "src/GaitCtrller.cpp:70-73"
_MODE_COMMENT_REF = "src/GaitCtrller.h:84-85"

#: SetRobotVel zeroes a component whose magnitude is below 0.03.
_VEL_DEADBAND_REF = "src/GaitCtrller.cpp:75-93"

#: The desired-state setup clamps x to [-1.0, 2.0] and y to [-0.6, 0.6].
_VEL_CLAMP_REF = "src/MPC_Ctrl/ConvexMPCLocomotion.cpp:89-101"

#: The node's continuous simulation loop and the publishers used each step.
_LOOP_REF = "scripts/walking_simulation.py:205-222"
_STEP_PUBLISH_REF = "scripts/walking_simulation.py:229-232"

#: The README lists gait types 0 through 11.
_GAIT_README_REF = "README.md:69-80"

#: The simulator connects pybullet in GUI mode and sets its timestep from freq.
_PYBULLET_REF = "scripts/walking_simulation.py:83-86"

#: The optional camera thread starts only when /simulation/camera is true.
_CAMERA_THREAD_REF = "scripts/walking_simulation.py:45-47"
_CAMERA_TOPICS_REF = "scripts/walking_simulation.py:246-257"

#: The pinned controller clamps only the x and y desired velocities.  It
#: filters the yaw-rate channel without bounding it, so the deployment
#: operator supplies the yaw-rate envelope.
_YAW_LIMIT = Limit.operator_required(
    "the pinned controller filters but does not clamp the yaw-rate channel; "
    "the deployment operator supplies the bound in site-limits.json"
)

_LINEAR_X_LIMIT = Limit(
    min=-1.0,
    max=2.0,
    unit="m/s",
    source="upstream_code",
    ref=_VEL_CLAMP_REF,
)

_LINEAR_Y_LIMIT = Limit(
    min=-0.6,
    max=0.6,
    unit="m/s",
    source="upstream_code",
    ref=_VEL_CLAMP_REF,
)

_GAIT_LIMIT = Limit(
    min=0,
    max=11,
    source="vendor_doc",
    ref=_GAIT_README_REF,
)

_MODE_LIMIT = Limit(
    min=0,
    max=1,
    source="upstream_code",
    ref=_MODE_COMMENT_REF,
)

#: One Twist publication on the relative cmd_vel topic.  The callback reads
#: linear.x, linear.y and angular.x; angular.z is not consumed by this node.
_CMD_VEL = {
    "topic": "/cmd_vel",
    "type": "geometry_msgs/Twist",
    "operation": "publish",
    "source_name": "cmd_vel",
    "source_ref": _ROS_SETUP_REF,
    "type_ref": _TWIST_TYPE_REF,
    "message": {
        "linear": {"x": 0.0, "y": 0.0, "z": 0.0},
        "angular": {"x": 0.0, "y": 0.0, "z": 0.0},
    },
    "args": {
        "linear.x": {"from": "input.linear_x"},
        "linear.y": {"from": "input.linear_y"},
        "angular.x": {"from": "input.yaw_rate"},
    },
}

#: The relative gait_type service.  The callback acknowledges unconditionally
#: with result 0 and the fixed text "get the gait".
_GAIT_TYPE = {
    "service": "/gait_type",
    "type": "quadruped_ctrl/QuadrupedCmd",
    "source_name": "gait_type",
    "source_ref": _ROS_SETUP_REF,
    "type_ref": _SRV_TYPE_REF,
    "args": {"cmd": {"from": "input.gait_type"}},
    "success": {"path": "result", "equals": 0},
    "result": {"map": {"result": "output.result", "description": "output.description"}},
}

#: The relative robot_mode service.  The callback acknowledges unconditionally
#: with result 0 and the fixed text "get the mode"; it is not a stop path.
_ROBOT_MODE = {
    "service": "/robot_mode",
    "type": "quadruped_ctrl/QuadrupedCmd",
    "source_name": "robot_mode",
    "source_ref": _ROS_SETUP_REF,
    "type_ref": _SRV_TYPE_REF,
    "args": {"cmd": {"from": "input.robot_mode"}},
    "success": {"path": "result", "equals": 0},
    "result": {"map": {"result": "output.result", "description": "output.description"}},
}

#: Fixed standing-gait request.  In robot mode 0 gait 4 selects the standing
#: gait, whose schedule is all stance and whose branch skips desired-position
#: integration; in robot mode 1 the controller ignores the gait type.  The
#: callback only stores the selector; it does not await the posture.
_GAIT_STAND = {
    "service": "/gait_type",
    "type": "quadruped_ctrl/QuadrupedCmd",
    "source_name": "gait_type",
    "source_ref": _ROS_SETUP_REF,
    "type_ref": _SRV_TYPE_REF,
    "request": {"cmd": 4},
    "success": {"path": "result", "equals": 0},
    "result": {"map": {"result": "output.result", "description": "output.description"}},
}

#: One odometry observation.  The node fills pose.pose.position and
#: pose.pose.orientation from the pybullet base state and IMU quaternion.
_ODOMETRY = {
    "topic": "/robot_odom",
    "type": "nav_msgs/Odometry",
    "operation": "subscribe",
    "source_ref": _ODOM_PUBLISHER_REF,
    "type_ref": _ODOM_TYPE_REF,
    "path": "$",
    "result": {"map": {
        "position": "pose.pose.position",
        "orientation": "pose.pose.orientation",
    }},
}

#: One IMU observation.  The node fills the acceleration, angular velocity and
#: orientation fields in the body frame.
_IMU = {
    "topic": "/imu0",
    "type": "sensor_msgs/Imu",
    "operation": "subscribe",
    "source_ref": _IMU_PUBLISHER_REF,
    "type_ref": _IMU_TYPE_REF,
    "path": "$",
    "result": {"map": {
        "linear_acceleration": "linear_acceleration",
        "angular_velocity": "angular_velocity",
        "orientation": "orientation",
    }},
}

_POSITION = Field(
    "object",
    description="Position in the odometry frame",
    properties={
        "x": Field("number", unit="m", description="Position x"),
        "y": Field("number", unit="m", description="Position y"),
        "z": Field("number", unit="m", description="Position z"),
    },
)

_ORIENTATION = Field(
    "object",
    description="Orientation as a unit quaternion in the body frame",
    properties={
        "x": Field("number", unit="1", description="Quaternion x"),
        "y": Field("number", unit="1", description="Quaternion y"),
        "z": Field("number", unit="1", description="Quaternion z"),
        "w": Field("number", unit="1", description="Quaternion w"),
    },
)

_VECTOR3_ACCEL = Field(
    "object",
    description="Linear acceleration in the body frame",
    properties={
        "x": Field("number", unit="m/s2", description="Acceleration x"),
        "y": Field("number", unit="m/s2", description="Acceleration y"),
        "z": Field("number", unit="m/s2", description="Acceleration z"),
    },
)

_VECTOR3_RATE = Field(
    "object",
    description="Angular velocity in the body frame",
    properties={
        "x": Field("number", unit="rad/s", description="Angular velocity x"),
        "y": Field("number", unit="rad/s", description="Angular velocity y"),
        "z": Field("number", unit="rad/s", description="Angular velocity z"),
    },
)

_PUBLISHED_OUTPUT = {
    "published": Field("boolean", description="True when the driver handed the Twist to rosbridge"),
    "confirmed": Field(
        "boolean",
        description="Always false: a rosbridge publication carries no execution or arrival confirmation",
    ),
}

_SERVICE_OUTPUT = {
    "result": Field("integer", description="QuadrupedCmd response result; the pinned callback returns 0"),
    "description": Field("string", description="QuadrupedCmd response description text"),
}


#: Sensed-confirmation stop (SAFE-049): neither request is a stop by itself.  The zero Twist leads to the standing
#: branch of the adaptive gait in robot mode 1 once the filtered speed decays (ConvexMPCLocomotion.cpp:173-185);
#: gait 4 selects standing in robot mode 0 (:150-158).  The confirmation reads the node's own stamped /robot_odom
#: pose (the twist is never filled) and /imu0 angular velocity.  Every threshold is operator_required: the clone
#: states no at-rest bound, and the stand trajectory z 0.21 (:140) and _body_height 0.25 (:79) are references, not a
#: band.  The node publishes every simulation step (500 Hz in the shipped config), so the sources are throttled; the
#: client bounds are fake-scale and a live deployment sets them in its estop_confirmation.
_NO_REST_BOUND = ("the clone states no at-rest bound; the operator supplies the largest change over the "
                  "confirmation window that counts as standing still")
_NO_STAND_BAND = ("the clone states no standing height band (the stand trajectory z 0.21 and _body_height 0.25 are "
                  "references, not bounds); the operator supplies it")

_SENSED_STOP = {
    "request": [
        {"topic": "/cmd_vel", "type": "geometry_msgs/Twist", "source_name": "cmd_vel", "source_ref": _ROS_SETUP_REF,
         "type_ref": _TWIST_TYPE_REF,
         "message": {"linear": {"x": 0.0, "y": 0.0, "z": 0.0}, "angular": {"x": 0.0, "y": 0.0, "z": 0.0}},
         "description": "a zero Twist (the cmd_vel callback reads linear.x, linear.y and angular.x)"},
        {"service": "/gait_type", "type": "quadruped_ctrl/QuadrupedCmd", "source_name": "gait_type",
         "source_ref": _ROS_SETUP_REF, "type_ref": _SRV_TYPE_REF, "request": {"cmd": 4},
         "success": {"path": "result", "equals": 0}, "timeout_ms": 1000,
         "description": "the standing gait request (honoured in robot mode 0 only)"},
    ],
    "sources": {
        "odom": {"topic": "/robot_odom", "type": "nav_msgs/Odometry", "source_ref": _ODOM_PUBLISHER_REF,
                 "type_ref": _ODOM_TYPE_REF, "throttle_ms": 20,
                 "fill_refs": {"pose.pose.position": _ODOM_POSITION_FILL_REF}},
        "imu": {"topic": "/imu0", "type": "sensor_msgs/Imu", "source_ref": _IMU_PUBLISHER_REF,
                "type_ref": _IMU_TYPE_REF, "throttle_ms": 20,
                "fill_refs": {"angular_velocity": _IMU_RATE_FILL_REF}},
    },
    "predicate": [
        {"source": "odom", "path": "pose.pose.position.x", "name": "rest_x", "unit": "m",
         "span_max": Limit.operator_required(_NO_REST_BOUND)},
        {"source": "odom", "path": "pose.pose.position.y", "name": "rest_y", "unit": "m",
         "span_max": Limit.operator_required(_NO_REST_BOUND)},
        {"source": "odom", "path": "pose.pose.position.z", "name": "standing_z", "unit": "m",
         "range": {"min": Limit.operator_required(_NO_STAND_BAND), "max": Limit.operator_required(_NO_STAND_BAND)}},
        {"source": "imu", "paths": ["angular_velocity.x", "angular_velocity.y", "angular_velocity.z"],
         "name": "rest_rate", "unit": "rad/s", "norm_max": Limit.operator_required(_NO_REST_BOUND)},
    ],
    "consecutive": 3,
    "min_span_ms": 200,
    "max_gap_ms": 500,
    "confirm_within_ms": 1500,
    "description": "zero velocity commanded and the standing gait requested; the base sensed still within the "
                   "standing height band with a small angular rate in three consecutive fresh samples within the bound",
}


class QuadrupedCtrl(RosDriver):
    """The ROS 1 pybullet quadruped simulator's motion and observation surface."""

    device_id = "quadruped-ctrl"
    device_kind = "world.sim"
    mode = "simulated"
    #: The driver is a simulated ROS endpoint with no hardware factory, but REVIEW.md
    #: item 12 sets its risk (integrator v4, 2026-11-05, at the orchestrator's
    #: requirement after an item-12 audit): it publishes a velocity setpoint on the
    #: root /cmd_vel that a physical mobile base behind the same bridge would act on,
    #: and /gait_type and /robot_mode select the locomotion controller's gait
    #: (scripts/walking_simulation.py:64-66).  Mobile-base transit is R2
    #: (04-safety.md), however simulated the deployment; the card's floor is R0.
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeQuadrupedCtrl"}
    tags = ["ros", "ros1", "simulation", "quadruped", "pybullet", "cmd-vel", "odometry", "imu"]
    display_name = "quadruped_ctrl pybullet simulator"
    vendor = "derek-th-wang"
    model = "MIT mini cheetah (pybullet simulation)"
    facts = [
        Fact("The launch file starts the Python node walking_simulation.py as quadruped_simulator.",
             source="upstream_code", ref=_LAUNCH_REF),
        Fact("The node registers the relative gait_type and robot_mode services with the quadruped_ctrl/QuadrupedCmd "
             "type and subscribes to the relative cmd_vel topic with geometry_msgs/Twist.",
             source="upstream_code", ref=_ROS_SETUP_REF),
        Fact("The gait_type callback calls set_gait_type(req.cmd) and returns QuadrupedCmdResponse(0, "
             "\"get the gait\").",
             source="upstream_code", ref=_GAIT_CALLBACK_REF),
        Fact("The robot_mode callback calls set_robot_mode(req.cmd) and returns QuadrupedCmdResponse(0, "
             "\"get the mode\").",
             source="upstream_code", ref=_MODE_CALLBACK_REF),
        Fact("The cmd_vel callback builds [msg.linear.x, msg.linear.y, msg.angular.x] and passes it to "
             "set_robot_vel; it does not read linear.z, angular.y or angular.z.",
             source="upstream_code", ref=_CMD_VEL_CALLBACK_REF),
        Fact("GaitCtrller::SetGaitType stores the integer gait type in _gaitType and prints it.",
             source="upstream_code", ref=_GAIT_SETTER_REF),
        Fact("GaitCtrller::SetRobotMode stores the integer mode in _robotMode and prints it; it performs no "
             "actuation or stop.",
             source="upstream_code", ref=_MODE_SETTER_REF),
        Fact("The C wrapper comment defines robot mode 0 as high performance and 1 as low power.",
             source="upstream_code", ref=_MODE_COMMENT_REF),
        Fact("GaitCtrller::SetRobotVel zeroes a velocity component whose magnitude is below 0.03 and otherwise "
             "stores the component unchanged.",
             source="upstream_code", ref=_VEL_DEADBAND_REF),
        Fact("The desired-state setup clamps the filtered x velocity to [-1.0, 2.0] m/s and the filtered y "
             "velocity to [-0.6, 0.6] m/s; the yaw-rate channel is filtered but not clamped.",
             source="upstream_code", ref=_VEL_CLAMP_REF),
        Fact("The README lists gait type values 0 through 11.",
             source="vendor_doc", ref=_GAIT_README_REF),
        Fact("The standing gait is constructed with a zero swing schedule for all four legs and a 14-step "
             "stance schedule.",
             source="upstream_code", ref="src/MPC_Ctrl/ConvexMPCLocomotion.cpp:35"),
        Fact("The desired world-position integration is skipped while the selected gait is standing.",
             source="upstream_code", ref="src/MPC_Ctrl/ConvexMPCLocomotion.cpp:276-280"),
        Fact("ConvexMPCLocomotion::run maps the gait number to a gait only when robotMode is 0; when robotMode is "
             "1 it uses the adaptive aio gait and sets the gait from the commanded body speed and yaw rate.",
             source="upstream_code", ref="src/MPC_Ctrl/ConvexMPCLocomotion.cpp:148-185"),
        Fact("__reset_robot sets robot mode 1 and then calls run(), which the upstream comment marks as blocking, "
             "before the line that sets robot mode 0.",
             source="upstream_code", ref="scripts/walking_simulation.py:194-198"),
        Fact("The node's run loop continues until rospy.is_shutdown() and executes one simulation step per "
             "rospy.Rate(freq) period.",
             source="upstream_code", ref=_LOOP_REF),
        Fact("Each simulation step calls the odometry, IMU, joint-state and whole-body-state publishers.",
             source="upstream_code", ref=_STEP_PUBLISH_REF),
        Fact("The /robot_odom publisher uses nav_msgs/Odometry and fills pose.pose.position from the pybullet base "
             "position and pose.pose.orientation from the base quaternion.",
             source="upstream_code", ref=_ODOM_PUBLISHER_REF),
        Fact("The /imu0 publisher uses sensor_msgs/Imu and fills linear_acceleration, angular_velocity and "
             "orientation in the body frame.",
             source="upstream_code", ref=_IMU_PUBLISHER_REF),
        Fact("The simulator connects pybullet in GUI mode and sets the physics timestep to 1.0/freq.",
             source="upstream_code", ref=_PYBULLET_REF),
        Fact("A separate camera thread starts only when the /simulation/camera parameter is true.",
             source="upstream_code", ref=_CAMERA_THREAD_REF),
        Fact("The camera thread publishes /generated_pc as sensor_msgs/PointCloud2 and /cam0/image_raw as "
             "sensor_msgs/Image at 20 Hz.",
             source="upstream_code", ref=_CAMERA_TOPICS_REF),
        Fact("The odometry publisher stamps the header with rospy.Time.now() and sets pose.pose.position x, y and z "
             "from the base position.", source="upstream_code", ref="scripts/walking_simulation.py:414-420"),
        Fact("The IMU publisher sets angular_velocity x, y and z from imu_data[7], imu_data[8] and imu_data[9] and "
             "stamps the header with rospy.Time.now().", source="upstream_code",
             ref="scripts/walking_simulation.py:438-445"),
        Fact("The desired x, y and yaw-rate commands pass through first-order filters with coefficients 0.01, 0.006 "
             "and 0.03 per controller step.", source="upstream_code",
             ref="src/MPC_Ctrl/ConvexMPCLocomotion.cpp:82-91"),
        Fact("The shipped configuration sets the simulation frequency to 500.0.", source="upstream_code",
             ref="config/quadruped_ctrl_config.yaml:1-6"),
    ]
    #: The node registers no stop service or action.  gait_type=4 selects the standing gait only in robot mode 0;
    #: in robot mode 1 (the mode the node sets before its endless run loop) the controller picks the gait from the
    #: commanded speed.  Neither request is a stop by itself: the e-stop is the sensed-confirmation stop above.
    safe_state = (
        "Simulated only: zero velocity commanded and the standing gait requested, and the base sensed standing "
        "still: the /robot_odom position within the operator's at-rest and standing-height bounds and the /imu0 "
        "angular rate below the operator's bound, in three consecutive fresh stamped samples within the "
        "confirmation bound. Another /cmd_vel publisher or the pybullet GUI mode buttons can move it again; nothing "
        "is claimed beyond the confirmation window."
    )
    #: The request steps' timeouts (2000 + 1000 ms) plus confirm_within_ms (1500 ms): the e-stop's budget.
    estop_latency_ms = 4500
    #: The deployed fake is a ROS-free recording transport with canned replies,
    #: not a replay of captured traffic and not the upstream pybullet simulator.
    fidelity = {
        "engine": "analytic:ROS contract fake (canned replies; no pybullet or physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned replies with no physics step, controller, wall-clock pacing or "
                     "state-hash replay; the fake is not a recording of captured traffic",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free RecordingRosTransport: it answers the declared endpoints with placeholder "
            "messages and runs no pybullet engine, MPC controller, contacts, sensors, ROS node or wall-clock loop",
            "the cmd_vel publication is recorded only; the fake does not integrate robot motion or prove that a "
            "Twist was received, executed or stopped",
            "odometry and IMU values are placeholders and do not advance; the fake's /robot_odom position echoes "
            "the last /cmd_vel linear x/y as a placeholder, while the live node publishes the pybullet base pose; "
            "a live run must receive the node's actual /robot_odom and /imu0 samples",
            "the upstream node publishes at /simulation/freq (500 Hz in the shipped config) and its simulator "
            "uses pybullet GUI; these are source facts, not fake timing",
            "the node registers no stop service or action; /gait_type cmd=4 is honoured only in robot mode 0 and "
            "the node runs in robot mode 1 after start-up: the e-stop is a sensed-confirmation stop (SAFE-049, "
            "simulated only) that publishes a zero Twist and requests gait 4 and is achieved only on three "
            "consecutive fresh /robot_odom and /imu0 samples within the bound; the thresholds are operator_required "
            "(fake placeholders in fixtures/estop-confirmation.json) and the client bounds are fake-scale, so a live "
            "deployment sets both in simulation_deployment['estop_confirmation']",
            "the fake starts walking (robot mode 1, a placeholder 0.3 m/s) and models the stop as a placeholder "
            "decay of the filtered speed to the standing branch and a stand in robot mode 0 after gait 4, with "
            "simulated stamps; while walking its bursts are projections that are not stored, so two reads agree; "
            "it is not the MPC controller or pybullet",
            "the pybullet GUI buttons switch the robot mode and another /cmd_vel publisher can move the robot after a "
            "confirmed stop; a failed controller safety check zeroes all torques and the robot collapses, which "
            "leaves the standing band and keeps the stop unconfirmed (fail closed)",
            "the optional camera path (/generated_pc, /cam0/image_raw), joint_states, wb_state, TF, reset, "
            "seed, step and snapshot/restore are not covered by this profile",
            "the yaw-rate envelope is operator-required because the pinned controller does not state one; the "
            "example overlay is illustrative fake-only data, not an upstream bound",
            "no ROS graph, rosbridge connection, simulator execution, hardware run or human review has occurred",
        ],
    }

    #: The resource state is the simulator's published odometry position.  A
    #: live node fills it from the pybullet base pose; the fake uses a
    #: placeholder echo of the last command, not a physics integration.
    parameters = {
        "odom_x": Field("number", unit="m", description="Odometry position x published on /robot_odom"),
        "odom_y": Field("number", unit="m", description="Odometry position y published on /robot_odom"),
    }
    safety_bindings = {"sensed_stop": _SENSED_STOP}
    reads = {
        "odom_x": {
            "topic": "/robot_odom",
            "type": "nav_msgs/Odometry",
            "source_ref": _ODOM_PUBLISHER_REF,
            "type_ref": _ODOM_TYPE_REF,
            "path": "pose.pose.position.x",
            "timeout_ms": 2000,
        },
        "odom_y": {
            "topic": "/robot_odom",
            "type": "nav_msgs/Odometry",
            "source_ref": _ODOM_PUBLISHER_REF,
            "type_ref": _ODOM_TYPE_REF,
            "path": "pose.pose.position.y",
            "timeout_ms": 2000,
        },
    }
    commands = {
        "x-cap.derek-th-wang.cmd_vel.v1": _CMD_VEL,
        "x-cap.derek-th-wang.gait_type.v1": _GAIT_TYPE,
        "x-cap.derek-th-wang.robot_mode.v1": _ROBOT_MODE,
        "x-cap.derek-th-wang.stand.v1": _GAIT_STAND,
        "x-cap.derek-th-wang.odometry.v1": _ODOMETRY,
        "x-cap.derek-th-wang.imu.v1": _IMU,
    }
    actions = {
        "x-cap.derek-th-wang.cmd_vel.v1": Action(
            name="publish_velocity",
            verb="invoke",
            description=(
                "Publish one geometry_msgs/Twist velocity setpoint on the upstream cmd_vel topic; the callback "
                "stores linear.x, linear.y and angular.x, and the receipt confirms only that rosbridge accepted "
                "the publication"
            ),
            input={
                "linear_x": Field(
                    "number",
                    unit="m/s",
                    description="Body-frame forward velocity; the callback reads twist.linear.x",
                    limit=_LINEAR_X_LIMIT,
                ),
                "linear_y": Field(
                    "number",
                    unit="m/s",
                    description="Body-frame lateral velocity; the callback reads twist.linear.y",
                    limit=_LINEAR_Y_LIMIT,
                ),
                "yaw_rate": Field(
                    "number",
                    unit="rad/s",
                    description="Yaw-rate command; the callback reads it from twist.angular.x",
                    limit=_YAW_LIMIT,
                ),
            },
            output=_PUBLISHED_OUTPUT,
        ),
        "x-cap.derek-th-wang.gait_type.v1": Action(
            name="set_gait_type",
            verb="invoke",
            description="Call the upstream gait_type service with one gait-type command",
            input={
                "gait_type": Field(
                    "integer",
                    unit="1",
                    description="Gait selector; the README lists 0 through 11",
                    limit=_GAIT_LIMIT,
                ),
            },
            output=_SERVICE_OUTPUT,
        ),
        "x-cap.derek-th-wang.robot_mode.v1": Action(
            name="set_robot_mode",
            verb="invoke",
            description=(
                "Call the upstream robot_mode service; mode 0 is high performance and mode 1 is low power, and "
                "the service is not a stop path"
            ),
            input={
                "robot_mode": Field(
                    "integer",
                    unit="1",
                    description="Robot mode selector; 0 is high performance and 1 is low power",
                    limit=_MODE_LIMIT,
                ),
            },
            output=_SERVICE_OUTPUT,
        ),
        "x-cap.derek-th-wang.stand.v1": Action(
            name="stand",
            verb="invoke",
            description=(
                "Fixed /gait_type request with cmd=4 (standing gait); honoured only in robot mode 0, ignored in "
                "the node's default robot mode 1; not a stop"
            ),
            output=_SERVICE_OUTPUT,
        ),
        "x-cap.derek-th-wang.odometry.v1": Action(
            name="read_odometry",
            verb="read",
            description="Read one nav_msgs/Odometry sample published on /robot_odom",
            output={"position": _POSITION, "orientation": _ORIENTATION},
        ),
        "x-cap.derek-th-wang.imu.v1": Action(
            name="read_imu",
            verb="read",
            description="Read one sensor_msgs/Imu sample published on /imu0",
            output={
                "linear_acceleration": _VECTOR3_ACCEL,
                "angular_velocity": _VECTOR3_RATE,
                "orientation": _ORIENTATION,
            },
        ),
    }
    #: No safety binding (model review 2026-11-04): the standing-gait request
    #: is ignored in robot mode 1, so it cannot certify a stop.  The stock
    #: e-stop latches and reports MHS.SAFETY.SAFE_STATE_UNREACHED.
