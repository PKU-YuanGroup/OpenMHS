"""OpenMHS rosbridge driver for the src_dog quadruped simulation.

The pinned repository is a ROS 1 catkin workspace with a Gazebo model of a
twelve-joint quadruped, a custom effort controller and a ``dog_ros`` node that
is meant to consume ``/dog/joint_states`` and ``/dog/imu`` and publish a flat
``std_msgs/Float64MultiArray`` motor command.  This package is a
configuration-only :class:`RosDriver` over rosbridge; it declares no Python
native class and does not start ROS, Gazebo or rosbridge.

The primary wire surface is the command topic.  ``PublishCommand`` writes five
twelve-element blocks into the Float64MultiArray (desired position, kp, desired
velocity, kd and feed-forward torque), and ``GazeboPVEController::commandCB``
rejects any message whose length is not ``joint_cnt_ * 5``.  The exact same
flat frame is exposed here, so the driver does not invent a second command
grammar.

The pinned node has no stop service or action.  The shipped ``dog_ros_node``
entry point runs only the ``test_DynamicsDiff`` dynamics check and constructs
no ``SimulatedHardware`` object, so it publishes no command either.  A
zero-valued frame drops the PD hold and is not a safe state, and a rosbridge
publication is transmission evidence only.  The package therefore declares no
e-stop or safe-state binding and stays blocked on the missing acknowledged
stop; the runtime still latches in software.

Every endpoint, type and fact cites the pinned clone at
1399108d258e964ef04850ddbfb6865dbd117000.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

#: The dog_ros launch remaps the node's private endpoints to these topics.
_LAUNCH_REF = "dog_ros/launch/control.launch:10-12"

#: SimulatedHardware's private node handle and its relative endpoints.
_HARDWARE_SETUP_REF = "dog_ros/src/hardware/SimulatedHardware.cpp:14-20"

#: The type includes used by SimulatedHardware and the controller.
_IMU_TYPE_REF = "dog_ros/include/dog_ros/hardware/SimulatedHardware.h:8"
_JOINT_STATE_TYPE_REF = "dog_ros/include/dog_ros/hardware/SimulatedHardware.h:10"
_COMMAND_TYPE_REF = "gazebo_pve_controller/include/gazebo_pve_controller/gazebo_pve_controller.h:5"

#: PublishCommand's flat five-block frame.
_PUBLISH_REF = "dog_ros/src/hardware/SimulatedHardware.cpp:59-75"

#: commandCB's size check and block copies.
_COMMAND_CB_REF = "gazebo_pve_controller/src/gazebo_pve_controller.cpp:288-310"

#: The torque clamp in the controller update loop and the URDF effort limit it uses.
_TORQUE_CLAMP_REF = "gazebo_pve_controller/src/gazebo_pve_controller.cpp:241-254"
_TORQUE_LIMIT_REF = "gazebo_pve_controller/src/gazebo_pve_controller.cpp:108-122"

#: The default controller configuration: twelve actuated leg joints.
_CONTROLLERS_REF = "dog_model/config/controllers.yaml:7-19"

#: The configured joint-name to motor-index map.
_MOTOR_NAME_REF = "dog_control/config/motor.lua:8-21"

#: Joint-state size checks and the derived velocity.
_JOINT_STATE_CB_REF = "dog_ros/src/hardware/SimulatedHardware.cpp:94-120"
_JOINT_NAME_MAP_REF = "dog_ros/src/hardware/SimulatedHardware.cpp:103-121"

#: The p3d odometry plugin.
_ODOM_REF = "dog_model/urdf/dog.gazebo:41-49"
_ODOM_LAUNCH_REF = "dog_model/launch/dog_world.launch:52-53"
_ODOM_TYPE_REF = "dog_model/scripts/Odom2TF.py:9"
_ODOM_SUB_REF = "dog_model/scripts/Odom2TF.py:9-15"

#: The Gazebo IMU sensor plugin.
_IMU_REF = "dog_model/urdf/dog.gazebo:59-62"

#: The joint limits declared by the leg macro and the shared motor bounds.
_HIP_X_LIMITS_REF = "dog_model/urdf/leg.xacro:58-60"
_HIP_Y_LIMITS_REF = "dog_model/urdf/leg.xacro:106-108"
_KNEE_LIMITS_REF = "dog_model/urdf/leg.xacro:155-157"
_MOTOR_LIMITS_REF = "dog_model/urdf/defines.xacro:22-23"
_LIMIT_MACRO_REF = "dog_model/urdf/defines.xacro:76-80"

#: The shipped entry point and the single executable built from all sources.
_ENTRY_REF = "dog_ros/src/main.cpp:1-8"
_GLOB_REF = "dog_ros/CMakeLists.txt:27-29"
_BUILD_REF = "dog_ros/CMakeLists.txt:158"

#: The joint command is one flat Float64MultiArray on the controller topic.
_JOINT_COMMAND = {
    "topic": "/dog/gazebo_pve_controller/command",
    "type": "std_msgs/Float64MultiArray",
    "operation": "publish",
    "source_ref": _LAUNCH_REF,
    "type_ref": _COMMAND_TYPE_REF,
    "args": {"data": {"from": "input.data"}},
}

#: Joint positions are published by the joint_state_controller.
_JOINT_STATES = {
    "topic": "/dog/joint_states",
    "type": "sensor_msgs/JointState",
    "source_ref": "dog_ros/launch/control.launch:11",
    "type_ref": _JOINT_STATE_TYPE_REF,
    "path": "position",
    "timeout_ms": 2000,
}

#: Ground-truth pose from the Gazebo p3d plugin.
_BASE_POSITION = {
    "topic": "/ground_truth/state",
    "type": "nav_msgs/Odometry",
    "source_ref": _ODOM_LAUNCH_REF,
    "type_ref": _ODOM_TYPE_REF,
    "path": "pose.pose.position",
    "timeout_ms": 2000,
}

#: The Gazebo IMU sensor fields.
_IMU_ORIENTATION = {
    "topic": "/dog/imu",
    "type": "sensor_msgs/Imu",
    "source_ref": _IMU_REF,
    "type_ref": _IMU_TYPE_REF,
    "path": "orientation",
    "timeout_ms": 2000,
}
_IMU_ANGULAR_VELOCITY = dict(_IMU_ORIENTATION, path="angular_velocity")
_IMU_LINEAR_ACCELERATION = dict(_IMU_ORIENTATION, path="linear_acceleration")

#: The twelve-joint order used by the default controller configuration.
_JOINT_NAMES = (
    "fl_hip_x", "fl_hip_y", "fl_knee",
    "fr_hip_x", "fr_hip_y", "fr_knee",
    "bl_hip_x", "bl_hip_y", "bl_knee",
    "br_hip_x", "br_hip_y", "br_knee",
)

_JOINT_POSITIONS = Field(
    "array",
    unit="rad",
    length=12,
    items=Field("number", unit="rad", description="Joint position in rad"),
    description=("Twelve joint positions in the order of the message's name array, which this read "
                 "does not return; dog_ros maps them to motors by name"),
)

_POSITION = Field(
    "object",
    properties={
        "x": Field("number", unit="m", description="Position x in the world frame"),
        "y": Field("number", unit="m", description="Position y in the world frame"),
        "z": Field("number", unit="m", description="Position z in the world frame"),
    },
    description="Torso position in the Gazebo world frame",
)

_ORIENTATION = Field(
    "object",
    properties={
        "x": Field("number", unit="1", description="Quaternion x"),
        "y": Field("number", unit="1", description="Quaternion y"),
        "z": Field("number", unit="1", description="Quaternion z"),
        "w": Field("number", unit="1", description="Quaternion w"),
    },
    description="Torso orientation as a unit quaternion",
)

_RATE = Field(
    "object",
    properties={
        "x": Field("number", unit="rad/s", description="Angular velocity x"),
        "y": Field("number", unit="rad/s", description="Angular velocity y"),
        "z": Field("number", unit="rad/s", description="Angular velocity z"),
    },
    description="Torso angular velocity in the sensor frame",
)

_ACCEL = Field(
    "object",
    properties={
        "x": Field("number", unit="m/s2", description="Linear acceleration x"),
        "y": Field("number", unit="m/s2", description="Linear acceleration y"),
        "z": Field("number", unit="m/s2", description="Linear acceleration z"),
    },
    description="Torso linear acceleration in the sensor frame",
)

#: The flat frame has five blocks of twelve values.  The pinned controller
#: accepts only ``joint_cnt_ * 5`` values and reads five blocks at offsets
#: 0, 12, 24, 36 and 48.
_COMMAND_FRAME = Field(
    "array",
    unit="1",
    length=60,
    items=Field("number", unit="1", description="One raw field of the flat command frame"),
    description=(
        "Flat Float64MultiArray data frame: indices 0-11 desired positions in rad, "
        "12-23 kp in N.m/rad, 24-35 desired velocities in rad/s, 36-47 kd in N.m.s/rad "
        "and 48-59 feed-forward torques in N.m; the order is the twelve joints of "
        "controllers.yaml"
    ),
    limit=Limit.operator_required(
        "the flat frame mixes rad, rad/s, N.m and two PD gains; the pinned controller "
        "clamps only the resulting torque to the URDF effort limit and states no kp or "
        "kd bound, so the deployment operator must supply the per-element envelope"
    ),
)

_PUBLISHED = {
    "published": Field("boolean", description="True when the driver handed the publication to rosbridge"),
    "confirmed": Field(
        "boolean",
        description="Always false: a rosbridge publication carries no execution or stopping confirmation",
    ),
}


class SrcDog(RosDriver):
    device_id = "src-dog"
    device_kind = "robot.mobile_base"
    mode = "simulated"
    #: A commanded twelve-joint frame drives a mobile quadruped; the catalogue's
    #: mobile-base class is R2, so the same class applies to this extension.
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeSrcDog"}
    tags = ["ros", "ros1", "gazebo", "simulation", "quadruped", "mobile-base",
            "joint-command", "motor-command"]
    display_name = "src_dog Gazebo quadruped"
    vendor = "sqrt81"
    model = "twelve-joint quadruped from dog_model/urdf/robot.xacro"
    facts = [
        Fact("The dog_ros launch remaps the node's private imu, joint_state and joint_cmd "
             "endpoints to /dog/imu, /dog/joint_states and "
             "/dog/gazebo_pve_controller/command.",
             source="upstream_code", ref=_LAUNCH_REF),
        Fact("SimulatedHardware uses a private node handle, subscribes to the relative imu and "
             "joint_state topics and advertises joint_cmd as std_msgs/Float64MultiArray.",
             source="upstream_code", ref=_HARDWARE_SETUP_REF),
        Fact("SimulatedHardware::PublishCommand resizes the Float64MultiArray data to 60 and "
             "writes five twelve-element blocks: desired positions, kp, desired velocities, kd "
             "and feed-forward torque.",
             source="upstream_code", ref=_PUBLISH_REF),
        Fact("GazeboPVEController::commandCB rejects a message whose data size is not "
             "joint_cnt_ * 5 and otherwise copies the five blocks into its joint commands.",
             source="upstream_code", ref=_COMMAND_CB_REF),
        Fact("GazeboPVEController::update clamps pos_err * kp + vel_err * kd + torque for each joint to "
             "plus or minus that joint's joint_torque_limit_ entry.",
             source="upstream_code", ref=_TORQUE_CLAMP_REF),
        Fact("GazeboPVEController::init accepts only revolute joints and fills joint_torque_limit_ from "
             "each joint's URDF effort limit.",
             source="upstream_code", ref=_TORQUE_LIMIT_REF),
        Fact("The default controllers.yaml lists twelve actuated leg joints in the order "
             "fl_hip_x, fl_hip_y, fl_knee, fr_hip_x, fr_hip_y, fr_knee, bl_hip_x, bl_hip_y, "
             "bl_knee, br_hip_x, br_hip_y and br_knee.",
             source="upstream_code", ref=_CONTROLLERS_REF),
        Fact("motor.lua maps the same twelve joint names to motor indices zero through eleven.",
             source="upstream_code", ref=_MOTOR_NAME_REF),
        Fact("SimulatedHardware::JointStateCb rejects a JointState unless its name, position, "
             "velocity and effort arrays each have twelve entries, and derives joint velocity "
             "from the position difference.",
             source="upstream_code", ref=_JOINT_STATE_CB_REF),
        Fact("SimulatedHardware::JointStateCb finds each entry's motor index by its joint name and "
             "logs an error for an unknown name.",
             source="upstream_code", ref=_JOINT_NAME_MAP_REF),
        Fact("The libgazebo_ros_p3d.so plugin is configured with updateRate 1000.0, bodyName torso, "
             "topicName ground_truth/state and frameName world.",
             source="upstream_code", ref=_ODOM_REF),
        Fact("The dog_world launch remaps the odom_to_tf subscriber's odom name to "
             "/ground_truth/state.",
             source="upstream_code", ref=_ODOM_LAUNCH_REF),
        Fact("The Odom2TF.py script imports nav_msgs.msg.Odometry and subscribes to its odom topic "
             "with that type.",
             source="upstream_code", ref=_ODOM_SUB_REF),
        Fact("The Gazebo IMU sensor plugin publishes on /dog/imu for the torso body at an "
             "update rate of 500 Hz.",
             source="upstream_code", ref=_IMU_REF),
        Fact("The leg macro declares hip_x limits of -3.00 to 3.00.",
             source="upstream_code", ref=_HIP_X_LIMITS_REF),
        Fact("The leg macro declares hip_y limits of -3.89 to 1.50.",
             source="upstream_code", ref=_HIP_Y_LIMITS_REF),
        Fact("The leg macro declares knee limits of -2.70 to 2.70.",
             source="upstream_code", ref=_KNEE_LIMITS_REF),
        Fact("defines.xacro sets MOTOR_TORQUE_MAX to 17 and MOTOR_VELOCITY_MAX to 40.",
             source="upstream_code", ref=_MOTOR_LIMITS_REF),
        Fact("The motor joint macro writes MOTOR_TORQUE_MAX and MOTOR_VELOCITY_MAX as the URDF limit "
             "effort and velocity.",
             source="upstream_code", ref=_LIMIT_MACRO_REF),
        Fact("The dog_ros main function casts argc and argv to void and calls only "
             "test_DynamicsDiff(argc, argv).",
             source="upstream_code", ref=_ENTRY_REF),
        Fact("CMakeLists.txt globs every src/*.cpp file, including the test sources, into "
             "ALL_SRCS and leaves the removal of TEST_SRCS commented out.",
             source="upstream_code", ref=_GLOB_REF),
        Fact("The package adds one dog_ros_node executable from ALL_SRCS.",
             source="upstream_code", ref=_BUILD_REF),
    ]
    safe_state = (
        "No acknowledged stop is declared: the pinned node exposes no stop service or action, "
        "the shipped dog_ros_node runs only the test_DynamicsDiff dynamics check and publishes "
        "no command, a zero-valued joint frame only removes the PD hold, and the runtime latch "
        "therefore blocks commands without any evidence that the simulated robot stopped."
    )
    fidelity = {
        "engine": "analytic:ROS contract fake (no Gazebo physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven rosbridge stand-in with placeholder topic samples and no "
                     "physics step, controller, contact solver or wall-clock pacing",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a ROS-free rosbridge contract stand-in, not a capture of Gazebo "
            "traffic: it runs no Gazebo world, ODE solver, contact model, controller update or "
            "rosbridge connection",
            "the flat command frame is recorded only and the first desired-position field is "
            "echoed into the placeholder base x to make the arrival observable; the fake does "
            "not integrate the quadruped and cannot show that a publication was received, held "
            "or stopped",
            "joint positions, torso pose and IMU samples are fixed placeholder values and do "
            "not advance with simulation time",
            "the default twelve-joint configuration is served; the optional tail configuration "
            "loads fourteen joints (controllers_tail.yaml) and is NOT COVERED",
            "the pinned repository registers no ROS stop, pause or reset service or action; a "
            "zero-valued command frame removes the PD hold and is not a safe state, so no "
            "e-stop binding is declared",
            "the shipped dog_ros_node main calls only test_DynamicsDiff and constructs no "
            "SimulatedHardware, so the command publisher and the control loop are not part of "
            "the shipped node; a live run needs a controller process that this package does "
            "not start",
            "no ROS graph, rosbridge connection, Gazebo simulator or hardware run has "
            "occurred",
        ],
    }

    parameters = {
        "joint_positions": _JOINT_POSITIONS,
        "base_position": _POSITION,
        "imu_orientation": _ORIENTATION,
        "imu_angular_velocity": _RATE,
        "imu_linear_acceleration": _ACCEL,
    }
    reads = {
        "joint_positions": _JOINT_STATES,
        "base_position": _BASE_POSITION,
        "imu_orientation": _IMU_ORIENTATION,
        "imu_angular_velocity": _IMU_ANGULAR_VELOCITY,
        "imu_linear_acceleration": _IMU_LINEAR_ACCELERATION,
    }
    commands = {
        "x-cap.sqrt81.joint_pd.v1": _JOINT_COMMAND,
    }
    actions = {
        "x-cap.sqrt81.joint_pd.v1": Action(
            name="publish_joint_pd_frame",
            verb="invoke",
            risk="R2",
            description=(
                "Publish one flat five-block std_msgs/Float64MultiArray motor frame on the "
                "Gazebo effort-controller command topic. The receipt confirms only that "
                "rosbridge accepted the publication, never that the controller received it, "
                "that a joint moved or that the robot stopped."
            ),
            input={"data": _COMMAND_FRAME},
            output=_PUBLISHED,
        ),
    }
    # The clone has no stop service or action.  A zero command frame removes the
    # PD hold and a publication has no acknowledgement, so neither is declared as
    # an e-stop or safe-state binding.  The e-stop reports SAFE_STATE_UNREACHED.
    safety_bindings = {}
