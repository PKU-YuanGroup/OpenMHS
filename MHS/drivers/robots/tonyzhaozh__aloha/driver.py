"""OpenMHS driver for the ALOHA bimanual teleoperation environment (gh.tonyzhaozh/aloha).

The card names the ROS family and the RosDriver helper, but the pinned
upstream entry point is the Python class ``aloha_scripts.real_env:RealEnv``:
it owns two Interbotix puppet arms, subscribes through their Python SDK, and
publishes joint commands.  The clone declares no ROS stop service and no
hardware emergency-stop interface, and one rosbridge publication cannot
carry the environment's single 14-value step (two arms and two grippers).
A direct Driver over the upstream class therefore preserves the primary
``RealEnv.step`` interface; this is recorded as a DEVIATION FROM THE CARD in
RESULT.json.

Every fact and limit cites the pinned clone at
06369f03cd8e0a47e16d3a90167853fd33af7557.  The fake is package code and is
ROS-free. This package is BLOCKED: the hardware factory refuses before any
upstream import, and no effective e-stop or safe-state action is declared.
The control surface remains available on the fake for investigation only.
``driver.lock.json`` keeps ``reviewed_by`` null.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, read, write

#: The clone documents a normalized gripper position of 0 (closed) to 1 (open)
#: on the action and observation lines.
_LEFT_GRIPPER_REF = "aloha_scripts/real_env.py:22"
_RIGHT_GRIPPER_REF = "aloha_scripts/real_env.py:24"

#: The clone states no vx300s joint-travel limits.  The Interbotix model and
#: the installed arm define them, so the operator supplies the envelope.
_ARM_LIMIT_REASON = (
    "the pinned clone states no vx300s joint-travel limits; the installed arm and its Interbotix "
    "configuration define them, so the operator supplies the accepted envelope in site-limits.json"
)

#: One scalar automatic-reward value from RealEnv.get_reward.
_REWARD_FIELD = Field("number", unit="1", description="Reward returned by RealEnv.get_reward")

#: The environment observation vectors.  Arm elements are radians for qpos and
#: qvel; gripper elements are normalized; the clone states no effort unit.
_QPOS_FIELD = Field(
    "array",
    length=14,
    items=Field("number", description="One qpos element"),
    description="Concatenated left arm (6), left gripper (normalized), right arm (6), right gripper (normalized)",
)
_QVEL_FIELD = Field(
    "array",
    length=14,
    items=Field("number", description="One qvel element"),
    description="Concatenated left arm (6, rad/s), left gripper velocity (normalized), right arm (6, rad/s), "
                "right gripper velocity (normalized)",
)
_EFFORT_FIELD = Field(
    "array",
    length=14,
    items=Field("number", description="One effort element"),
    description="Concatenated first seven left and first seven right effort values; the clone states no unit",
)
_STEP_TYPE_FIELD = Field("string", description="dm_env step type of the returned TimeStep")

_STEP_OUTPUT = {
    "qpos": _QPOS_FIELD,
    "qvel": _QVEL_FIELD,
    "effort": _EFFORT_FIELD,
    "reward": _REWARD_FIELD,
    "step_type": _STEP_TYPE_FIELD,
}


def _floats(values) -> list[float]:
    return [float(value) for value in values]


def _observation(result):
    observation = getattr(result, "observation", None)
    if observation is None and isinstance(result, dict):
        observation = result.get("observation")
    if not isinstance(observation, dict):
        raise DriverFailed("MHS.DEVICE.NOT_READY", "the upstream TimeStep carries no observation mapping")
    return observation


def _step_type(result) -> str:
    value = getattr(result, "step_type", None)
    if value is None and isinstance(result, dict):
        value = result.get("step_type")
    return str(value)


def _reward(result) -> float:
    value = getattr(result, "reward", None)
    if value is None and isinstance(result, dict):
        value = result.get("reward")
    return float(value or 0)


class Aloha(Driver):
    device_id = "aloha"
    device_kind = "robot.arm"
    mode = "hardware"
    risk = "R2"
    native = "aloha_scripts.real_env:RealEnv"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeRealEnv"}
    vendor, model = "tonyzhaozh", "ALOHA bimanual vx300s"
    display_name = "ALOHA bimanual teleoperation environment (blocked)"
    tags = ["aloha", "bimanual", "teleoperation", "interbotix", "vx300s", "ros1", "manipulation"]
    facts = [
        Fact("RealEnv documents a flat action of six left-arm joint positions, one normalized left-gripper "
             "position (0 close, 1 open), six right-arm joint positions and one normalized right-gripper "
             "position (0 close, 1 open).",
             source="upstream_code", ref="aloha_scripts/real_env.py:21-24"),
        Fact("RealEnv.step splits the flat action in half, sends the first six values of each half to the left "
             "and right arm set_joint_positions, sends the last value of each half to set_gripper_pose, sleeps "
             "DT and returns a dm_env TimeStep.",
             source="upstream_code", ref="aloha_scripts/real_env.py:127-140"),
        Fact("RealEnv.get_qpos reads six arm positions from each recorder, normalizes the measured gripper "
             "position at recorder index 7, and returns left arm, left gripper, right arm and right gripper in "
             "that order.",
             source="upstream_code", ref="aloha_scripts/real_env.py:57-64"),
        Fact("RealEnv.get_qvel and get_effort read the same recorder streams; qvel takes six arm values and the "
             "normalized gripper velocity, and get_effort returns the first seven values per side.",
             source="upstream_code", ref="aloha_scripts/real_env.py:66-80"),
        Fact("RealEnv.get_images returns the ImageRecorder's camera image dictionary.",
             source="upstream_code", ref="aloha_scripts/real_env.py:82-83"),
        Fact("The README says the launch starts communication with 4 robots and 4 cameras.",
             source="vendor_doc", ref="README.md:43-44"),
        Fact("The launch file starts usb_cam nodes with image_width 640, image_height 480 and framerate 60.",
             source="upstream_code", ref="launch/4arms_teleop.launch:90-140"),
        Fact("RealEnv.set_gripper_pose converts each normalized value with PUPPET_GRIPPER_JOINT_UNNORMALIZE_FN "
             "and publishes a JointSingleCommand on each puppet.",
             source="upstream_code", ref="aloha_scripts/real_env.py:85-92"),
        Fact("PUPPET_GRIPPER_POSITION_OPEN is 0.05800 and PUPPET_GRIPPER_POSITION_CLOSE is 0.01844 in the "
             "left-finger position constants; the cited lines do not state a unit.",
             source="upstream_code", ref="aloha_scripts/constants.py:18-22"),
        Fact("PUPPET_GRIPPER_POSITION_NORMALIZE_FN maps a measured gripper position to "
             "(x - close) / (open - close).",
             source="upstream_code", ref="aloha_scripts/constants.py:33"),
        Fact("RealEnv.reset reboots both gripper motors, moves both arms to START_ARM_POSE, and opens then "
             "closes both grippers when fake is false.",
             source="upstream_code", ref="aloha_scripts/real_env.py:94-125"),
        Fact("RealEnv constructs both puppet arms as InterbotixManipulatorXS robot_model vx300s with group arm "
             "and gripper gripper.",
             source="upstream_code", ref="aloha_scripts/real_env.py:40-44"),
        Fact("The puppet mode configs enable torque and set the arm group to position control and the gripper "
             "single to linear_position control.",
             source="upstream_code", ref="config/puppet_modes_left.yaml:3-17"),
        Fact("The Recorder subscribes to /puppet_<side>/joint_states as sensor_msgs/JointState and to "
             "/puppet_<side>/commands/joint_group and /puppet_<side>/commands/joint_single as interbotix_xs_msgs "
             "JointGroupCommand and JointSingleCommand.",
             source="upstream_code", ref="aloha_scripts/robot_utils.py:96-98"),
        Fact("The launch file defaults robot_model_master to wx250s and robot_model_puppet to vx300s.",
             source="upstream_code", ref="launch/4arms_teleop.launch:3-4"),
        Fact("The launch file includes interbotix_xsarm_control for each master and puppet arm.",
             source="upstream_code", ref="launch/4arms_teleop.launch:23-62"),
        Fact("The README warns that the robot will collapse if motors are torque off because the joints have no "
             "automatically engaged brakes.",
             source="vendor_doc", ref="README.md:51"),
        Fact("The README instructs lowering the robots with sleep.py before cutting off power.",
             source="vendor_doc", ref="README.md:177-179"),
    ]
    # BLOCKED: the previous cached-position command did not interrupt native
    # step/reset publications or establish fresh stopped feedback. A software
    # latch cannot substitute for an effective device stop. Leave native=null
    # and achieved_by empty in the generated safety declaration.
    safe_state = None

    # The runtime reads every read before and after an action.  Arm qpos and
    # qvel are in radians; the gripper values are normalized by RealEnv.
    @read("left_arm_qpos", type="array", items="number", length=6, unit="rad",
          description="Left puppet arm joint positions, in RealEnv action order")
    def left_arm_qpos(self):
        return _floats(self.native.get_qpos()[:6])

    @read("right_arm_qpos", type="array", items="number", length=6, unit="rad",
          description="Right puppet arm joint positions, in RealEnv action order")
    def right_arm_qpos(self):
        return _floats(self.native.get_qpos()[7:13])

    @read("gripper_pose", type="array", items="number", length=2, unit="1",
          description="Measured normalized left and right gripper positions; 0 is closed and 1 is open")
    def gripper_pose(self):
        qpos = self.native.get_qpos()
        return [float(qpos[6]), float(qpos[13])]

    @read("left_arm_qvel", type="array", items="number", length=6, unit="rad/s",
          description="Left puppet arm joint velocities")
    def left_arm_qvel(self):
        return _floats(self.native.get_qvel()[:6])

    @read("right_arm_qvel", type="array", items="number", length=6, unit="rad/s",
          description="Right puppet arm joint velocities")
    def right_arm_qvel(self):
        return _floats(self.native.get_qvel()[7:13])

    @read("gripper_velocity", type="array", items="number", length=2, unit="1/s",
          description="Normalized left and right gripper velocities")
    def gripper_velocity(self):
        qvel = self.native.get_qvel()
        return [float(qvel[6]), float(qvel[13])]

    @read("left_effort", type="array", items="number", length=7,
          description="First seven left JointState effort values; the clone states no unit")
    def left_effort(self):
        return _floats(self.native.get_effort()[:7])

    @read("right_effort", type="array", items="number", length=7,
          description="First seven right JointState effort values; the clone states no unit")
    def right_effort(self):
        return _floats(self.native.get_effort()[7:14])

    @read("reward", type="number", unit="1",
          description="Reward returned by RealEnv.get_reward; the pinned implementation returns 0")
    def reward(self):
        return float(self.native.get_reward())

    @write("gripper_pose", type="array", items="number", length=2, unit="1",
           description="Desired normalized left and right gripper positions; 0 is closed and 1 is open",
           limit=Limit(min=[0.0, 0.0], max=[1.0, 1.0], names=["left", "right"],
                       source="upstream_code", ref=_LEFT_GRIPPER_REF))
    def set_gripper_pose(self, value):
        self.native.set_gripper_pose(float(value[0]), float(value[1]))

    @action(
        name="x-cap.tonyzhaozh.step.v1",
        description="Blocked hardware implementation, retained for fake investigation: apply one flat ALOHA "
                    "action to both puppet arms and grippers and return the joint observation (images omitted)",
        input={
            "left_arm": Field("array", items=Field("number", unit="rad"), length=6,
                              description="Six absolute left-arm joint positions, in RealEnv action order",
                              limit=Limit.operator_required(_ARM_LIMIT_REASON)),
            "left_gripper": Field("number", unit="1",
                                  description="Normalized left gripper position; 0 is closed and 1 is open",
                                  limit=Limit(min=0.0, max=1.0, source="upstream_code",
                                              ref=_LEFT_GRIPPER_REF)),
            "right_arm": Field("array", items=Field("number", unit="rad"), length=6,
                               description="Six absolute right-arm joint positions, in RealEnv action order",
                               limit=Limit.operator_required(_ARM_LIMIT_REASON)),
            "right_gripper": Field("number", unit="1",
                                   description="Normalized right gripper position; 0 is closed and 1 is open",
                                   limit=Limit(min=0.0, max=1.0, source="upstream_code",
                                               ref=_RIGHT_GRIPPER_REF)),
        },
        output=dict(_STEP_OUTPUT),
    )
    def step(self, left_arm, left_gripper, right_arm, right_gripper):
        self.check_cancelled()
        command = _floats(left_arm) + [float(left_gripper)] + _floats(right_arm) + [float(right_gripper)]
        result = self.native.step(command)
        self.check_cancelled()
        observation = _observation(result)
        return {
            "qpos": _floats(observation["qpos"]),
            "qvel": _floats(observation["qvel"]),
            "effort": _floats(observation["effort"]),
            "reward": _reward(result),
            "step_type": _step_type(result),
        }

    @action(
        name="x-cap.tonyzhaozh.reset.v1",
        description="Blocked hardware implementation, retained for fake investigation: RealEnv.reset moves both "
                    "arms and grippers without internal-trajectory envelope or cancellation enforcement",
        output={"qpos": _QPOS_FIELD, "step_type": _STEP_TYPE_FIELD},
    )
    def reset_environment(self):
        result = self.native.reset()
        observation = _observation(result)
        return {"qpos": _floats(observation["qpos"]), "step_type": _step_type(result)}

    @action(
        name="x-cap.tonyzhaozh.hold.v1",
        description="Unavailable: cached-position commands cannot establish a verified stop or safe state; "
                    "this action always fails without commanding the native layer",
        output={},
    )
    def hold(self):
        raise DriverFailed(
            "MHS.SAFETY.SAFE_STATE_UNREACHED",
            "ALOHA hold is unavailable: no interruptible native stop or fresh stopped-state confirmation",
        )
