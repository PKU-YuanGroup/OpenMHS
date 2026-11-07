"""OpenMHS rosbridge driver for the FDCL-GWU UAV Gazebo simulator.

The pinned repository is a ROS 2 Gazebo simulation with Python estimator,
trajectory and control nodes.  This package is a configuration-only
:class:`RosDriver` over rosbridge; it declares no Python native class and
neither imports nor starts the upstream code.  The operator runs the clone's
launch files and rosbridge separately.

The selected interfaces are the clone's own ROS 2 topics:

* ``/uav/states`` (``uav_gazebo/msg/StateData``) is the estimated UAV state;
* ``/uav/imu`` (``sensor_msgs/msg/Imu``) is the raw simulated IMU;
* ``/uav/mode`` (``uav_gazebo/msg/ModeData``) is the trajectory mode input,
  with modes 0..5 matching the GUI's Idle, Warmup, Take-off, Stay, Circle and
  Land radio buttons;
* ``/uav/motors_on`` (``std_msgs/msg/Bool``) carries a motor-off publication.
  The same Bool false is the sensed-confirmation stop request.  This package
  publishes no Bool true.  ControlNode and TrajectoryNode keep their last
  mode, and stopping GuiNode does not clear it, so Bool true before mode 0
  resumes stored motion.

The stop is simulated only (SAFE-049).  The Bool false proves nothing.  The
e-stop is achieved only when fresh ``/uav/gps`` samples show a landed, still
Gazebo-frame pose.  ``/uav/states`` is not a source: its publisher assigns no
header stamp.

Every endpoint, type and fact cites the pinned clone at
7270fe4e274f2a5d84432336311da478d87d8d3d.  The fake transport is ROS-free and
all of its numbers are placeholders.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: TrajectoryNode's state and mode subscriptions.
_STATE_SUB_REF = "src/fdcl_uav/fdcl_uav/trajectory.py:80-84"
_MODE_SUB_REF = "src/fdcl_uav/fdcl_uav/trajectory.py:86-90"

#: TrajectoryNode's message import names StateData and ModeData.
_TRAJECTORY_TYPE_REF = "src/fdcl_uav/fdcl_uav/trajectory.py:7"

#: EstimatorNode's IMU and GPS subscriptions, and the message imports.
_IMU_SUB_REF = "src/fdcl_uav/fdcl_uav/estimator.py:283-287"
_IMU_TYPE_REF = "src/fdcl_uav/fdcl_uav/estimator.py:13"
_GPS_SUB_REF = "src/fdcl_uav/fdcl_uav/estimator.py:289-293"
_GPS_TYPE_REF = "src/fdcl_uav/fdcl_uav/estimator.py:12"
_GPS_POSITION_REF = "src/fdcl_uav/fdcl_uav/estimator.py:333"
_GPS_LINEAR_REF = "src/fdcl_uav/fdcl_uav/estimator.py:334"

#: ControlNode's motor-enable subscription and std_msgs/Bool import.
_MOTORS_SUB_REF = "src/fdcl_uav/fdcl_uav/control.py:537-541"
_BOOL_TYPE_REF = "src/fdcl_uav/fdcl_uav/control.py:11"

#: The trajectory dispatcher accepts these six mode values.
_MODE_LIMIT_REF = "src/fdcl_uav/fdcl_uav/trajectory.py:153-162"

#: The control loop publishes zero force and torque while motors are off or
#: the mode is below take-off.
_CONTROL_ZERO_REF = "src/fdcl_uav/fdcl_uav/control.py:245-251"

_NO_LANDED_BAND = (
    "The clone states no Gazebo-frame landed height. landing_motor_cutoff_height -0.25 is an NED desired "
    "height, not a /uav/gps z bound, and the spawn z 0.2 is a start pose, so the operator supplies the band."
)
_NO_REST_BOUND = (
    "The clone states no at-rest bound. The p3d gaussian_noise 0.01 is sensor noise, not the largest position "
    "change that counts as still, so the operator supplies the span."
)
_GPS_HISTORY_UNSTATED = (
    "The /uav/gps publisher is libgazebo_ros_p3d outside this clone. The URDF remaps odom to uav/gps and sets "
    "frame_name world, gaussian_noise 0.01 and update_rate 10, and it states no QoS. The README names Ubuntu "
    "22.04 with ROS 2 Iron, and no Iron gazebo_ros companion is fetched."
)

#: Sensed-confirmation stop (SAFE-049).  The Bool false is the same publication ControlNode reads
#: (control.py:585-586) before it publishes a zero wrench (control.py:245-251).  That publication proves
#: nothing.  The confirmation reads pose.pose.position from /uav/gps, which EstimatorNode reads at
#: estimator.py:333.  The p3d publisher and its QoS are outside the clone, so the history is operator_required.
#: Every threshold is operator_required.  The client bounds are fake-scale: three samples at the URDF's 10 Hz
#: p3d rate span min_span_ms 200, and confirm_within_ms 4000 leaves room for a fall from above the clone's
#: about-1 m world-up takeoff target.  The clone states no maximum altitude (README.md:184, the P key), so a
#: higher flight must raise confirm_within_ms in simulation_deployment['estop_confirmation'] or the latch stays.
#: There is no motors-on command and no estop_terminal.  ControlNode retains its mode
#: (control.py:544-549) and TrajectoryNode retains its mode (trajectory.py:116-124).
#: motors_on_callback only sets motor_on (control.py:585-586).  With mode >= 2, Bool true
#: permits a nonzero wrench (control.py:245-251).  Stopping GuiNode does not clear those
#: modes.  Recovery stays outside MHS and must leave both nodes at mode 0 before any
#: Bool true (SAFE-042).
_SENSED_STOP = {
    "request": [
        {"topic": "/uav/motors_on", "type": "std_msgs/msg/Bool", "source_ref": _MOTORS_SUB_REF,
         "type_ref": _BOOL_TYPE_REF, "source_name": "/uav/motors_on", "timeout_ms": 2000,
         "message": {"data": False},
         "description": "Bool false on /uav/motors_on (transmission only; the same publication as motors_off)"},
    ],
    "sources": {
        "gps": {"topic": "/uav/gps", "type": "nav_msgs/msg/Odometry", "source_name": "/uav/gps",
                "source_ref": _GPS_SUB_REF, "type_ref": _GPS_TYPE_REF,
                "fill_refs": {"pose.pose.position": _GPS_POSITION_REF,
                              "twist.twist.linear": _GPS_LINEAR_REF},
                "history": {"operator_required": _GPS_HISTORY_UNSTATED}},
    },
    "predicate": [
        {"source": "gps", "path": "pose.pose.position.z", "name": "landed_z", "unit": "m",
         "range": {"max": Limit.operator_required(_NO_LANDED_BAND)}},
        {"source": "gps", "path": "pose.pose.position.x", "name": "rest_x", "unit": "m",
         "span_max": Limit.operator_required(_NO_REST_BOUND)},
        {"source": "gps", "path": "pose.pose.position.y", "name": "rest_y", "unit": "m",
         "span_max": Limit.operator_required(_NO_REST_BOUND)},
        {"source": "gps", "path": "pose.pose.position.z", "name": "rest_z", "unit": "m",
         "span_max": Limit.operator_required(_NO_REST_BOUND)},
    ],
    "consecutive": 3,
    "min_span_ms": 200,
    "max_gap_ms": 500,
    "confirm_within_ms": 4000,
    "description": "Bool false on /uav/motors_on, then three fresh /uav/gps samples with Gazebo-frame z at or "
                   "below the operator's landed band and x, y and z still, inside the confirmation window; the "
                   "publication proves nothing and the pose may already hold.",
}

_VECTOR3_IMU = Field(
    "object",
    description="Three-component vector from the simulated IMU message",
    properties={
        "x": Field("number", unit="1", description="x component"),
        "y": Field("number", unit="1", description="y component"),
        "z": Field("number", unit="1", description="z component"),
    },
)

_ATTITUDE = Field(
    "array",
    unit="1",
    length=9,
    items=Field("number", unit="1", description="Row-major rotation-matrix entry"),
    description="Row-major 3x3 attitude matrix entries from StateData.attitude",
)

_POSITION = Field(
    "array",
    unit="m",
    length=3,
    items=Field("number", unit="m", description="Position component"),
    description="Estimated position from StateData.position",
)

_VELOCITY = Field(
    "array",
    unit="m/s",
    length=3,
    items=Field("number", unit="m/s", description="Velocity component"),
    description="Estimated velocity from StateData.velocity",
)

_ACCELERATION = Field(
    "array",
    unit="m/s2",
    length=3,
    items=Field("number", unit="m/s2", description="Acceleration component"),
    description="Estimated acceleration from StateData.acceleration",
)

_ANGULAR_VELOCITY = Field(
    "array",
    unit="rad/s",
    length=3,
    items=Field("number", unit="rad/s", description="Angular-velocity component"),
    description="Estimated body angular velocity from StateData.angular_velocity",
)

_QUATERNION = Field(
    "object",
    description="Unit quaternion from the simulated IMU message",
    properties={
        "x": Field("number", unit="1", description="Quaternion x"),
        "y": Field("number", unit="1", description="Quaternion y"),
        "z": Field("number", unit="1", description="Quaternion z"),
        "w": Field("number", unit="1", description="Quaternion w"),
    },
)

_PUBLISHED = {
    "published": Field("boolean", description="True when rosbridge accepted the publication"),
    "confirmed": Field("boolean",
                       description="Always false: a ROS topic publication has no execution acknowledgement"),
}

_STATE = {
    "topic": "/uav/states",
    "type": "uav_gazebo/msg/StateData",
    "source_name": "/uav/states",
    "source_ref": _STATE_SUB_REF,
    "type_ref": _TRAJECTORY_TYPE_REF,
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {
        "position": "output.position",
        "velocity": "output.velocity",
        "acceleration": "output.acceleration",
        "attitude": "output.attitude",
        "angular_velocity": "output.angular_velocity",
    }},
}

_IMU = {
    "topic": "/uav/imu",
    "type": "sensor_msgs/msg/Imu",
    "source_name": "/uav/imu",
    "source_ref": _IMU_SUB_REF,
    "type_ref": _IMU_TYPE_REF,
    "operation": "subscribe",
    "path": "$",
    "result": {"map": {
        "orientation": "output.orientation",
        "angular_velocity": "output.angular_velocity",
        "linear_acceleration": "output.linear_acceleration",
    }},
}

#: ModeData is published by the GUI and consumed by TrajectoryNode and
#: ControlNode.  The zero offsets are the values the GUI stores at
#: gui.py:405-406; this driver does not invent a different offset envelope.
#: Publishing a mode does not turn the motors on.
_MODE = {
    "topic": "/uav/mode",
    "type": "uav_gazebo/msg/ModeData",
    "source_name": "/uav/mode",
    "source_ref": _MODE_SUB_REF,
    "type_ref": _TRAJECTORY_TYPE_REF,
    "operation": "publish",
    "message": {
        "header": {"frame_id": "", "stamp": {"sec": 0, "nanosec": 0}},
        "x_offset": [0.0, 0.0, 0.0],
        "yaw_offset": 0.0,
    },
    "args": {"mode": {"from": "input.mode"}},
    "result": {"map": {"published": "output.published", "confirmed": "output.confirmed"}},
}

#: Input-free.  The message is the same Bool false the e-stop sends.  Repeating
#: it does not turn the motors on and does not resume a stored mode.
_MOTORS_OFF = {
    "topic": "/uav/motors_on",
    "type": "std_msgs/msg/Bool",
    "source_name": "/uav/motors_on",
    "source_ref": _MOTORS_SUB_REF,
    "type_ref": _BOOL_TYPE_REF,
    "operation": "publish",
    "message": {"data": False},
    "result": {"map": {"published": "output.published", "confirmed": "output.confirmed"}},
}

#: The resource snapshot reads the same topics the GUI publishes.  The value
#: is the last ModeData or Bool observed on the wire, not proof that the
#: trajectory or the rotors executed anything.
_MODE_OBSERVE = {
    "topic": "/uav/mode",
    "type": "uav_gazebo/msg/ModeData",
    "source_name": "/uav/mode",
    "source_ref": _MODE_SUB_REF,
    "type_ref": _TRAJECTORY_TYPE_REF,
}

_MOTORS_OBSERVE = {
    "topic": "/uav/motors_on",
    "type": "std_msgs/msg/Bool",
    "source_name": "/uav/motors_on",
    "source_ref": _MOTORS_SUB_REF,
    "type_ref": _BOOL_TYPE_REF,
}


class UavSimulator(RosDriver):
    device_id = "fdcl-uav-sim"
    device_kind = "world.sim"
    mode = "simulated"
    #: A multirotor command is R2 (REVIEW.md item 12).  The card floor is R1.
    risk = "R2"
    ros_version = 2
    timeout_s = 2.0
    backends = {"fake": ".fake:FakeUavSimulator"}
    tags = ["ros", "ros2", "simulation", "gazebo", "uav", "quadrotor", "trajectory", "mode"]
    display_name = "FDCL-GWU UAV Gazebo simulator"
    vendor = "FDCL-GWU"
    model = "Geometric-control quadrotor in Gazebo"
    facts = [
        Fact("TrajectoryNode subscribes to /uav/states as StateData and /uav/mode as ModeData, each with "
             "queue depth 1.",
             source="upstream_code", ref="src/fdcl_uav/fdcl_uav/trajectory.py:80-90"),
        Fact("TrajectoryNode creates a DesiredData publisher on /uav/trajectory with queue depth 1.",
             source="upstream_code", ref="src/fdcl_uav/fdcl_uav/trajectory.py:93-98"),
        Fact("calculate_trajectory calls set_desired_states_to_zero for mode 0 or 1, takeoff for mode 2, "
             "stay for mode 3, circle for mode 4 and land for mode 5, and otherwise logs Undefined mode.",
             source="upstream_code", ref="src/fdcl_uav/fdcl_uav/trajectory.py:153-165"),
        Fact("The mode callback stores x_offset and yaw_offset from the message and, when the mode differs, "
             "stores the new mode and calls mark_traj_start.",
             source="upstream_code", ref="src/fdcl_uav/fdcl_uav/trajectory.py:116-125"),
        Fact("mark_traj_start sets is_landed to False, clears x_offset and yaw_offset, resets the trajectory "
             "timers and calls update_initial_state.",
             source="upstream_code", ref="src/fdcl_uav/fdcl_uav/trajectory.py:168-183"),
        Fact("update_initial_state copies self.x, self.v, self.a, self.R and self.W into the initial-state fields.",
             source="upstream_code", ref="src/fdcl_uav/fdcl_uav/trajectory.py:217-222"),
        Fact("set_desired_states_to_zero sets desired position, velocity, acceleration, jerk and snap and the "
             "b1 derivatives to zero, and sets b1d to [1.0, 0.0, 0.0].",
             source="upstream_code", ref="src/fdcl_uav/fdcl_uav/trajectory.py:193-202"),
        Fact("takeoff copies self.x into xd and sets xd_dot[2] from takeoff_velocity; land sets is_landed True "
             "when self.x[2] is greater than landing_motor_cutoff_height.",
             source="upstream_code", ref="src/fdcl_uav/fdcl_uav/trajectory.py:266-344"),
        Fact("EstimatorNode subscribes to /uav/imu as Imu with queue depth 1.",
             source="upstream_code", ref="src/fdcl_uav/fdcl_uav/estimator.py:283-287"),
        Fact("EstimatorNode subscribes to /uav/gps as Odometry with queue depth 1.",
             source="upstream_code", ref="src/fdcl_uav/fdcl_uav/estimator.py:289-293"),
        Fact("gps_callback reads pose.pose.position and twist.twist.linear and builds the NED vectors "
             "x_gps as [x, -y, -z] and v_gps as [x, -y, -z].",
             source="upstream_code", ref="src/fdcl_uav/fdcl_uav/estimator.py:333-338"),
        Fact("EstimatorNode creates a StateData publisher on /uav/states with queue depth 1.",
             source="upstream_code", ref="src/fdcl_uav/fdcl_uav/estimator.py:347"),
        Fact("publish_states assigns position, velocity, acceleration, angular_velocity and attitude from the "
             "estimator state and publishes the StateData.",
             source="upstream_code", ref="src/fdcl_uav/fdcl_uav/estimator.py:350-361"),
        Fact("ControlNode subscribes to /uav/states as StateData, /uav/trajectory as DesiredData, /uav/mode as "
             "ModeData and /uav/motors_on as Bool, each with queue depth 1.",
             source="upstream_code", ref="src/fdcl_uav/fdcl_uav/control.py:517-541"),
        Fact("ControlNode creates publishers for DesiredData on /uav/desired, ErrorData on /uav/errors and "
             "WrenchStamped on /uav/fm, each with queue depth 1, and a timer of 0.005 s.",
             source="upstream_code", ref="src/fdcl_uav/fdcl_uav/control.py:508-514"),
        Fact("ControlNode assigns a zero force and a zero torque when motor_on is false or mode is below 2.",
             source="upstream_code", ref=_CONTROL_ZERO_REF),
        Fact("motors_on_callback sets motor_on from msg.data.",
             source="upstream_code", ref="src/fdcl_uav/fdcl_uav/control.py:585-586"),
        Fact("GuiNode's radio buttons are labelled Idle, Warmup, Take-off, Stay, Circle and Land.",
             source="upstream_code", ref="src/fdcl_uav/fdcl_uav/gui.py:128-136"),
        Fact("GuiNode creates a ModeData publisher on /uav/mode and a Bool publisher on /uav/motors_on, each "
             "with queue depth 1.",
             source="upstream_code", ref="src/fdcl_uav/fdcl_uav/gui.py:261-263"),
        Fact("GuiNode creates a QTimer, connects it to update and starts it at 100.",
             source="upstream_code", ref="src/fdcl_uav/fdcl_uav/gui.py:86-88"),
        Fact("update assigns mode, x_offset and yaw_offset on a ModeData and publishes it on /uav/mode.",
             source="upstream_code", ref="src/fdcl_uav/fdcl_uav/gui.py:302-306"),
        Fact("The shutdown handler logs, sets motor_on to False and publishes that Bool.",
             source="upstream_code", ref="src/fdcl_uav/fdcl_uav/gui.py:363-371"),
        Fact("The motor-toggle handler logs, stores the toggled self.motor_on, updates the button text and "
             "publishes that Bool.",
             source="upstream_code", ref="src/fdcl_uav/fdcl_uav/gui.py:378-391"),
        Fact("The flight-mode callback logs the selected index, publishes ModeData.mode and then sets x_offset "
             "and yaw_offset to zero.",
             source="upstream_code", ref="src/fdcl_uav/fdcl_uav/gui.py:394-407"),
        Fact("The M key calls the motor-toggle handler.",
             source="upstream_code", ref="src/fdcl_uav/fdcl_uav/gui.py:410-413"),
        Fact("fdcl_uav_launch.py starts four fdcl_uav nodes named sim, with executables estimator, control, "
             "trajectory and gui in namespaces estimator, control, trajectory and gui.",
             source="upstream_code", ref="src/fdcl_uav/launch/fdcl_uav_launch.py:6-29"),
        Fact("The Gazebo plugin creates a subscription of geometry_msgs::msg::WrenchStamped on topic_name_ "
             "with depth 1.",
             source="upstream_code", ref="src/uav_plugins/src/uav_control_plugin.cpp:59-64"),
        Fact("update_fm copies wrench.force and wrench.torque into f and M and sets no_msg_counter to 0.",
             source="upstream_code", ref="src/uav_plugins/src/uav_control_plugin.cpp:122-133"),
        Fact("The world-update callback increments no_msg_counter, calls reset_uav and returns when the counter "
             "exceeds 100, and otherwise calls SetForce and SetTorque.",
             source="upstream_code", ref="src/uav_plugins/src/uav_control_plugin.cpp:68-88"),
        Fact("reset_uav calls SetForce and SetTorque with zero_fM.",
             source="upstream_code", ref="src/uav_plugins/src/uav_control_plugin.cpp:137-141"),
        Fact("The URDF gazebo block for link sets gravity to true.",
             source="upstream_code", ref="src/uav_gazebo/urdf/uav.urdf.xacro:30"),
        Fact("The URDF remaps the IMU plugin ~/out to uav/imu.",
             source="upstream_code", ref="src/uav_gazebo/urdf/uav.urdf.xacro:38-40"),
        Fact("The URDF loads libgazebo_ros_p3d, remaps odom to uav/gps, and sets frame_name world, "
             "gaussian_noise 0.01 and update_rate 10.",
             source="upstream_code", ref="src/uav_gazebo/urdf/uav.urdf.xacro:53-61"),
        Fact("The URDF sets the uav_control_plugin topic_name to /uav/fm.",
             source="upstream_code", ref="src/uav_gazebo/urdf/uav.urdf.xacro:65-69"),
        Fact("The Gazebo launch joins the package path with worlds/simple.world.",
             source="upstream_code", ref="src/uav_gazebo/launch/uav_gazebo.launch.py:29"),
        Fact("simple.world includes the model URI model://ground_plane.",
             source="upstream_code", ref="src/uav_gazebo/worlds/simple.world:13-15"),
        Fact("The Gazebo launch spawns the entity named uav at x=0, y=0, z=0.2.",
             source="upstream_code", ref="src/uav_gazebo/launch/uav_gazebo.launch.py:47-52"),
        Fact("The README says the current main branch has been tested on Ubuntu 22.04 running ROS2-Iron.",
             source="vendor_doc", ref="README.md:61"),
        Fact("The README says that while the UAV is in manual the P key increases altitude and the L key "
             "decreases altitude.",
             source="vendor_doc", ref="README.md:182-185"),
        Fact("The README documents the M key as kill motors and the 0-5 keys as flight mode selection.",
             source="vendor_doc", ref="README.md:188-190"),
    ]
    safe_state = (
        "Simulated only: Bool false on /uav/motors_on is confirmed only by three fresh /uav/gps samples with "
        "Gazebo z at or below the operator's landed band and x, y and z still within the operator's span; the "
        "Bool proves nothing, an already-landed pose can pass, and there is no motors-on command because "
        "ControlNode and TrajectoryNode keep their last mode, so recovery outside MHS must leave both at mode 0 "
        "before any Bool true, and stopping GuiNode alone does not clear that mode."
    )
    #: Request timeout_ms 2000 plus confirm_within_ms 4000.  A live deployment that raises confirm_within_ms
    #: also raises the model's latency (families.py); this attribute covers the declared bound.
    estop_latency_ms = 6000
    fidelity = {
        "engine": "analytic:ROS contract fake (canned replies; no Gazebo physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven canned replies with no physics step, controller, wall-clock pacing "
                     "or state-hash replay; the fake is not a recording of captured traffic",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free RecordingRosTransport: it answers /uav/states, /uav/imu, /uav/mode and "
            "/uav/motors_on and records the mode and motors-off publications, but it runs no Gazebo, quadrotor "
            "dynamics, estimator, trajectory generator, controller or wall-clock loop",
            "the /uav/states and /uav/imu arrays are placeholder constants and do not follow the /uav/gps pose; "
            "a live run must receive the clone's own samples",
            "the /uav/mode publication is recorded only; the fake does not execute takeoff, stay, circle or land",
            "a Bool false is answered with a placeholder fall of 0.4 m per 0.1 s stamp step from z 2.0 down to "
            "z 0.15, then held still; that is not Gazebo physics, not the p3d noise, and not the controller "
            "zeroing the wrench when the mode is below 2",
            "the e-stop is a sensed-confirmation stop (SAFE-049, simulated only): Bool false on /uav/motors_on, "
            "then three fresh /uav/gps samples with z at or below the operator's landed band and x, y and z "
            "still; the thresholds and the /uav/gps history are operator_required (fake placeholders in "
            "fixtures/estop-confirmation.json) and the client bounds are fake-scale (consecutive 3, min_span_ms "
            "200, max_gap_ms 500, confirm_within_ms 4000), so a live deployment sets them in "
            "simulation_deployment['estop_confirmation']",
            "the clone states no maximum altitude (README manual P key); a flight above the 4000 ms window "
            "must raise confirm_within_ms or the latch stays and the request is retried",
            "the check reports the pose at the end of the window; an already-landed still UAV satisfies it "
            "without the Bool having caused the landing, and samples from before the request are discarded",
            "this package publishes no Bool true and declares no re-enable: ControlNode retains its mode "
            "(control.py:544-549) and TrajectoryNode retains its mode (trajectory.py:116-124), motors_on_callback "
            "only sets motor_on (control.py:585-586), and mode at least 2 plus Bool true permits a nonzero wrench "
            "(control.py:245-251); stopping GuiNode does not clear those modes; estop_terminal is not claimed "
            "because a Bool true publication can undo the cut; recovery is outside MHS and must leave both nodes "
            "at mode 0 before any Bool true",
            "GuiNode publishes /uav/motors_on only on the shutdown button, the motor button and the M key, so a "
            "live resource read of motors_on waits for one of those events while the fake answers at once; the "
            "same events can publish Bool true after a confirmed stop, which a reset's re-confirmation refuses "
            "and which nothing in this package prevents",
            "the /uav/gps publisher is libgazebo_ros_p3d outside the clone; the URDF states frame_name world, "
            "gaussian_noise 0.01 and update_rate 10 and no QoS, and it does not say which p3d fields the noise "
            "applies to; the Python topics are absolute, so a remap makes an endpoint absent and the e-stop "
            "fails closed",
            "/uav/states is not a confirmation source: publish_states assigns position, velocity, acceleration, "
            "angular_velocity and attitude and does not assign header.stamp",
            "the plugin calls reset_uav after more than 100 updates without /uav/fm, which also zeros force and "
            "torque; that watchdog is not the stop this package uses",
            "no hardware, live ROS graph, rosbridge connection, Gazebo process or upstream simulator run is "
            "claimed; the fake's evidence is contract_checked on the fake backend only",
        ],
    }
    parameters = {
        "mode": Field("integer", unit="1",
                      description="Last ModeData.mode observed on /uav/mode; not execution feedback"),
        "motors_on": Field("boolean",
                           description="Last Bool.data observed on /uav/motors_on; not proof that rotors stopped"),
    }
    reads = {
        "mode": dict(_MODE_OBSERVE, path="mode"),
        "motors_on": dict(_MOTORS_OBSERVE, path="data"),
    }
    commands = {
        "x-cap.fdcl-gwu.state.v1": _STATE,
        "x-cap.fdcl-gwu.imu.v1": _IMU,
        "x-cap.fdcl-gwu.mode.v1": _MODE,
        "x-cap.fdcl-gwu.motors_off.v1": _MOTORS_OFF,
    }
    actions = {
        "x-cap.fdcl-gwu.state.v1": Action(
            name="read_state",
            verb="read",
            description="Read one fused /uav/states sample: position, velocity, acceleration, attitude "
                        "and body angular velocity",
            output={
                "position": _POSITION,
                "velocity": _VELOCITY,
                "acceleration": _ACCELERATION,
                "attitude": _ATTITUDE,
                "angular_velocity": _ANGULAR_VELOCITY,
            },
        ),
        "x-cap.fdcl-gwu.imu.v1": Action(
            name="read_imu",
            verb="read",
            description="Read one simulated /uav/imu sample: orientation, angular velocity and linear "
                        "acceleration",
            output={
                "orientation": _QUATERNION,
                "angular_velocity": _VECTOR3_IMU,
                "linear_acceleration": _VECTOR3_IMU,
            },
        ),
        "x-cap.fdcl-gwu.mode.v1": Action(
            name="set_flight_mode",
            verb="invoke",
            risk="R2",
            description="Publish one ModeData flight-mode request on /uav/mode; the receipt confirms "
                        "transmission only, not mode execution, and the publication does not turn the motors on",
            input={"mode": Field("integer", unit="1",
                                 description="Flight mode index: 0 Idle, 1 Warmup, 2 Take-off, 3 Stay, "
                                             "4 Circle, 5 Land",
                                 limit=Limit(min=0, max=5, source="upstream_code", ref=_MODE_LIMIT_REF))},
            output=_PUBLISHED,
        ),
        "x-cap.fdcl-gwu.motors_off.v1": Action(
            name="motors_off",
            verb="invoke",
            risk="R2",
            description="Publish one std_msgs/Bool false on /uav/motors_on, the same publication the e-stop "
                        "sends; the receipt confirms transmission only, not the sensed confirmation, and "
                        "repeating it does not turn the motors on",
            output=_PUBLISHED,
        ),
    }
    # No estop or safe_state binding and no safe_state action: the only stop is the sensed confirmation above.
    # No reenable action: Bool true with a retained mode of at least 2 resumes the wrench
    # (control.py:245-251).  Stopping GuiNode does not clear ControlNode or TrajectoryNode.
    safety_bindings = {"sensed_stop": _SENSED_STOP}
