"""OpenMHS rosbridge driver for one Interbotix X-Series arm profile (wx250s).

The upstream repository is a collection of ROS 1 launch, configuration and
example packages for Interbotix arms.  The motor server itself is the external
``interbotix_xs_sdk`` node from ``interbotix_ros_core``; the pinned clone
contains only clients of that server.  This package therefore declares the
wire interface proven by the clone but does not invent a Python native class.

Scope: the six-joint ``arm`` group's position command, published on the
relative ``commands/joint_group`` topic with ``interbotix_xs_msgs/JointGroupCommand``,
and one ``sensor_msgs/JointState`` sample from the relative ``joint_states``
topic.  A topic publish is transmitted only.  The receipt says ``confirmed:
false``; it never claims that the arm reached a position.

The clone contains no stop service, stop action or torque-enable service.
The only command surfaces are topic publications processed by the external
server, and the joystick example's torque-off command can drop a gravity-loaded
arm.  No safe state is claimed and the package is blocked on that source gap.
"""

from mhs.driver import Action, Fact, Field, Limit, RosDriver

# The diagnostic example is the in-clone proof of the client-side wire names.
_DIAG = (
    "interbotix_ros_xsarms/examples/interbotix_xsarm_diagnostic_tool/"
    "src/xsarm_diagnostic_tool.cpp"
)

#: Relative JointGroupCommand publisher and the message include.
_GROUP_REF = f"{_DIAG}:26"
_GROUP_TYPE_REF = f"{_DIAG}:6"

#: Relative JointState subscriber and the message include.
_STATE_REF = f"{_DIAG}:31"
_STATE_TYPE_REF = f"{_DIAG}:5"

#: The wx250s motor config names the seven-joint order and the six-joint arm group.
_CONFIG = "interbotix_ros_xsarms/interbotix_xsarm_control/config/wx250s.yaml"

#: The launch starts the external xs_sdk node under the robot namespace.
_LAUNCH = "interbotix_ros_xsarms/interbotix_xsarm_control/launch/xsarm_control.launch"


class Wx250s(RosDriver):
    device_id = "wx250s"
    device_kind = "robot.arm"
    mode = "hardware"
    risk = "R2"
    ros_version = 1
    backends = {"fake": ".fake:FakeWx250s"}
    vendor = "Trossen Robotics"
    model = "wx250s"
    display_name = "Interbotix WX250s X-Series arm"
    tags = ["ros", "ros1", "interbotix", "wx250s", "x-series", "arm", "joint-control"]
    facts = [
        Fact(
            "The diagnostic example advertises interbotix_xs_msgs/JointGroupCommand on the "
            "relative commands/joint_group topic and interbotix_xs_msgs/JointSingleCommand on "
            "the relative commands/joint_single topic.",
            source="upstream_code",
            ref=f"{_DIAG}:26-27",
        ),
        Fact(
            "The same example subscribes to the relative joint_states topic and hands each "
            "sample to a sensor_msgs/JointState callback.",
            source="upstream_code",
            ref=f"{_DIAG}:16-31",
        ),
        Fact(
            "The diagnostic path reads the joint lower and upper limits from the RobotInfo "
            "service and builds a sinusoidal joint command around 0 radians, so the group "
            "command positions are in radians.",
            source="upstream_code",
            ref=f"{_DIAG}:63-75",
        ),
        Fact(
            "The wx250s motor config declares the joint order [waist, shoulder, elbow, "
            "forearm_roll, wrist_angle, wrist_rotate, gripper] and groups the six arm joints as arm.",
            source="upstream_code",
            ref=f"{_CONFIG}:3-12",
        ),
        Fact(
            "The X-Series control launch starts the external interbotix_xs_sdk node (or its "
            "xs_sdk_sim variant) under the robot_name namespace; the server implementation "
            "is not in this clone.",
            source="upstream_code",
            ref=f"{_LAUNCH}:32-41",
        ),
        Fact(
            "The X-Series README says the packages build on the interbotix_xs_sdk wrapper in "
            "the separate interbotix_ros_core repository and directs readers there for "
            "implementation details.",
            source="vendor_doc",
            ref="interbotix_ros_xsarms/README.md:28",
        ),
        Fact(
            "The joystick example's torque-off path sets ArmJoy::TORQUE_OFF; this is a "
            "message field, not an acknowledged stop service or action.",
            source="upstream_code",
            ref="interbotix_ros_xsarms/examples/interbotix_xsarm_joy/src/xsarm_joy.cpp:92-109",
        ),
        Fact(
            "The joystick example advertises ArmJoy on the relative commands/joy_processed "
            "topic.",
            source="upstream_code",
            ref="interbotix_ros_xsarms/examples/interbotix_xsarm_joy/src/xsarm_joy.cpp:260",
        ),
        Fact(
            "The diagnostic example's final motion writes Profile_Velocity with "
            "set_motor_registers and then publishes a JointGroupCommand carrying the sleep "
            "positions; that is another planned motion, not a stop.",
            source="upstream_code",
            ref=f"{_DIAG}:130-140",
        ),
    ]
    safe_state = (
        "No safe state is claimed: the pinned clone exposes no acknowledged stop service or "
        "action, and the external interbotix_xs_sdk owns the motor stop and torque semantics."
    )

    commands = {
        "x-cap.interbotix.joint_group.v1": {
            "topic": "/wx250s/commands/joint_group",
            "type": "interbotix_xs_msgs/JointGroupCommand",
            "source_name": "commands/joint_group",
            "source_ref": _GROUP_REF,
            "type_ref": _GROUP_TYPE_REF,
            "operation": "publish",
            "message": {"name": "arm"},
            "args": {"cmd": {"from": "input.joint_positions"}},
            "result": {"map": {"published": "published", "confirmed": "confirmed"}},
            "timeout_ms": 2000,
        },
        "x-cap.interbotix.joint_states.v1": {
            "topic": "/wx250s/joint_states",
            "type": "sensor_msgs/JointState",
            "source_name": "joint_states",
            "source_ref": _STATE_REF,
            "type_ref": _STATE_TYPE_REF,
            "operation": "subscribe",
            "path": "$",
            "result": {"map": {"names": "name", "positions": "position"}},
            "timeout_ms": 2000,
        },
    }
    actions = {
        "x-cap.interbotix.joint_group.v1": Action(
            name="command_joint_group",
            risk="R2",
            description=(
                "Publish one six-joint arm position command to the external xs_sdk; the "
                "topic has no execution acknowledgement"
            ),
            input={
                "joint_positions": Field(
                    "array",
                    items=Field("number", unit="rad", description="One arm joint position"),
                    length=6,
                    description=(
                        "Six arm joint positions in the wx250s group order: waist, shoulder, "
                        "elbow, forearm_roll, wrist_angle, wrist_rotate"
                    ),
                    limit=Limit.operator_required(
                        "the wx250s joint travel envelope depends on the selected robot model, "
                        "its URDF and the deployed site; the operator supplies the per-joint bounds"
                    ),
                ),
            },
            output={
                "published": Field(
                    "boolean",
                    description="True when rosbridge transmitted the publish frame",
                ),
                "confirmed": Field(
                    "boolean",
                    description=(
                        "Always false: the external xs_sdk topic publication has no execution "
                        "acknowledgement in the pinned clone"
                    ),
                ),
            },
        ),
        "x-cap.interbotix.joint_states.v1": Action(
            name="read_joint_states",
            verb="read",
            risk="R0",
            description="Read one sensor_msgs/JointState sample from the external xs_sdk",
            output={
                "names": Field(
                    "array",
                    items=Field("string", description="One joint name"),
                    description="Joint names in the sample's order",
                ),
                "positions": Field(
                    "array",
                    items=Field("number", description="One raw native joint position; units depend on joint identity"),
                    description="Raw positions in sample order; arm angles are radians, gripper scale is unverified",
                ),
            },
        ),
    }
