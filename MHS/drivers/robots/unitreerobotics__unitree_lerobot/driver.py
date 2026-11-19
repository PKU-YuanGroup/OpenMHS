"""OpenMHS driver for gh.unitreerobotics/unitree_lerobot: the G1 29-DoF dual-arm controller.

A direct Driver over ``unitree_lerobot.eval_robot.robot_control.robot_arm:G1_29_ArmController``.  The controller is a
DDS bridge: it subscribes to ``rt/lowstate``, publishes a ``LowCmd`` on ``rt/lowcmd`` or, in motion mode, on
``rt/arm_sdk`` from a daemon thread, and exposes ``ctrl_dual_arm(q_target, tauff_target)``, which only stores the
target.  The driver therefore reports ``reached: false``: the upstream call returns immediately and says nothing about
where the arms are.  The fourteen arm joints are the left arm (indices 15 to 21) followed by the right arm (22 to 28),
the order of ``G1_29_JointArmIndex``.

* reads: the current arm joint positions and velocities, the stored target, the controller's arm velocity limit and
  its motion-mode flag;
* ``cap.motion.joint_position.v1``: the fourteen joint targets.  No text of the clone states a joint travel range for
  the G1 arms, so the input is ``Limit.operator_required``: every call is refused ``MHS.SAFETY.LIMITS_UNSET`` until
  the site supplies the range in ``site-limits.json`` (``site-limits.example.json`` shows the overlay);
* the stop: the class has no stop, disable, brake or emergency method.  ``ctrl_dual_arm_go_home`` is a move to the
  zero pose, not a stop.  The e-stop makes a best-effort request using the last joint positions from the
  subscribed LowState buffer and send them back as the target with zero feedforward torque; the daemon publisher keeps
  publishing that hold.  The buffer has no freshness check, so if the DDS stream stopped the target is the last
  received q and may be stale.  The request is not an acknowledged stop: the e-stop always fails with the latch held.
  The ordinary hold action is not a safe-state action. A physical e-stop is not documented
  in the clone and the deployment must provide one; the driver makes no claim that the hold is a substitute for it.

This package is model-authored and unreviewed: the acceptance gate runs the fake backend only, and the loader refuses
the R2 hardware backend until a human signs ``reviewed_by`` in ``driver.lock.json``.  The hardware backend also needs
``unitree_sdk2py``, which the upstream ``pyproject.toml`` leaves commented out, and a live DDS domain with an
``rt/lowstate`` publisher.  Nothing here ran on a robot.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read

ARM = "unitree_lerobot/eval_robot/robot_control/robot_arm.py"
MAKE_ROBOT = "unitree_lerobot/eval_robot/make_robot.py"
UTILS = "unitree_lerobot/eval_robot/utils/utils.py"
PYPROJECT = "pyproject.toml"
README = "README.md"

NUM_ARM_JOINTS = 14

#: The order of G1_29_JointArmIndex (robot_arm.py:290-307): left arm first, then the right arm.
JOINT_NAMES = [
    "left_shoulder_pitch",
    "left_shoulder_roll",
    "left_shoulder_yaw",
    "left_elbow",
    "left_wrist_roll",
    "left_wrist_pitch",
    "left_wrist_yaw",
    "right_shoulder_pitch",
    "right_shoulder_roll",
    "right_shoulder_yaw",
    "right_elbow",
    "right_wrist_roll",
    "right_wrist_pitch",
    "right_wrist_yaw",
]

JOINT_LIMIT_REASON = (
    "the clone states no joint travel range for the G1 arms: G1_29_ArmController starts q_target at zeros and leaves "
    "the range to the robot and the deployment (robot_arm.py:72-73), so the site supplies it"
)


class G1DualArm(Driver):
    device_id = "g1-dual-arm"
    device_kind = "robot.arm"
    mode = "hardware"
    risk = "R2"
    native = "unitree_lerobot.eval_robot.robot_control.robot_arm:G1_29_ArmController"
    backends = {"hardware": ".native:connect", "fake": ".fake:FakeG1_29_ArmController"}
    vendor = "Unitree Robotics"
    model = "G1 29-DoF dual arm (G1_29_ArmController)"
    display_name = "Unitree G1 dual arm (G1_29_ArmController)"
    tags = ["robot arm", "humanoid", "dual arm", "joint control", "dds", "unitree", "g1"]

    facts = [
        Fact("The module defines the topic names rt/lowcmd, rt/arm_sdk and rt/lowstate", source="upstream_code",
             ref=f"{ARM}:19-21"),
        Fact("The controller publishes LowCmd on rt/arm_sdk when motion_mode is true and on rt/lowcmd otherwise",
             source="upstream_code", ref=f"{ARM}:97-100"),
        Fact("The controller subscribes to LowState on rt/lowstate", source="upstream_code", ref=f"{ARM}:102"),
        Fact("The constructor joins DDS domain 1 in simulation mode and domain 0 on the real robot",
             source="upstream_code", ref=f"{ARM}:92-95"),
        Fact("After initializing the DDS endpoints and starting the subscriber thread, the constructor blocks until the first LowState "
             "message arrives; the loop has no timeout", source="upstream_code", ref=f"{ARM}:101-113"),
        Fact("The control period is control_dt = 1/250 s", source="upstream_code", ref=f"{ARM}:85"),
        Fact("The clip is current_q + delta / max(motion_scale, 1.0) with motion_scale = max(abs(delta)) / "
             "(velocity_limit * control_dt)", source="upstream_code", ref=f"{ARM}:166-171"),
        Fact("The constructor starts the publisher thread as a daemon", source="upstream_code", ref=f"{ARM}:147-151"),
        Fact("The publisher loops indefinitely, reads the stored arm targets and writes LowCmd at the control period; "
             "it does not check for a stop acknowledgement", source="upstream_code", ref=f"{ARM}:173-204"),
        Fact("The constructor enables motor modes and position gains for all G1 joints, including the non-arm joints",
             source="upstream_code", ref=f"{ARM}:127-145"),
        Fact("ctrl_dual_arm stores q_target and tauff_target under ctrl_lock and returns nothing; it sends no command "
             "of its own", source="upstream_code", ref=f"{ARM}:208-212"),
        Fact("G1_29_JointArmIndex lists the left arm joints 15 to 21 and the right arm joints 22 to 28, in that "
             "order", source="upstream_code", ref=f"{ARM}:290-307"),
        Fact("get_current_dual_arm_q returns the fourteen arm joint positions and get_current_dual_arm_dq their "
             "velocities from the subscribed LowState buffer", source="upstream_code", ref=f"{ARM}:222-228"),
        Fact("ctrl_dual_arm_go_home sets q_target to zeros and waits up to 100 attempts of 0.05 s for the joints to "
             "come within 0.05 rad of zero; it is a move to the home pose, not a stop", source="upstream_code",
             ref=f"{ARM}:230-249"),
        Fact("The class defines no stop, disable, brake or emergency method", source="upstream_code", ref=f"{ARM}:69-287"),
        Fact("The controller's arm_velocity_limit starts at 20.0; this is a controller setting, not the joint travel "
             "range", source="upstream_code", ref=f"{ARM}:84"),
        Fact("speed_instant_max sets arm_velocity_limit to 30.0", source="upstream_code", ref=f"{ARM}:257-259"),
        Fact("The publisher's gradual-speed branch uses a hard-coded 5 s ramp from 20.0 to 30.0",
             source="upstream_code", ref=f"{ARM}:197-199"),
        Fact("The package imports unitree_sdk2py for the DDS channel, the IDL messages and the CRC",
             source="upstream_code", ref=f"{ARM}:6-13"),
        Fact("pyproject.toml leaves the unitree_sdk2py dependency commented out, so the clone does not install the "
             "DDS transport", source="upstream_code", ref=f"{PYPROJECT}:21"),
        Fact("EvalRealConfig defaults arm to G1_29", source="upstream_code", ref=f"{UTILS}:125"),
        Fact("setup_robot_interface constructs the selected arm controller with motion_mode and simulation_mode",
             source="upstream_code", ref=f"{MAKE_ROBOT}:94"),
        Fact("The README describes eval_robot as the real-machine inference verification of the model",
             source="vendor_doc", ref=f"{README}:49"),
    ]

    safe_state = (
        "no safe state is confirmed: the e-stop requests the last buffered arm positions with zero feedforward torque, "
        "then fails SAFE_STATE_UNREACHED with the latch held; the undated buffer may be stale, the daemon continues "
        "publishing and may still have a previous target in flight, and non-arm motor commands remain enabled"
    )

    # -- reads ------------------------------------------------------------------------------------------------
    @read("joint_positions", type="array", items="number", length=NUM_ARM_JOINTS, unit="rad",
          description="Current angle of the fourteen arm joints, left arm first then the right arm")
    def get_joint_positions(self):
        return self._current_joint_positions()

    @read("joint_velocities", type="array", items="number", length=NUM_ARM_JOINTS, unit="rad/s",
          description="Current velocity of the fourteen arm joints from the LowState buffer")
    def get_joint_velocities(self):
        return [float(value) for value in self.native.get_current_dual_arm_dq()]

    @read("target_joint_positions", type="array", items="number", length=NUM_ARM_JOINTS, unit="rad",
          description="Target angle stored by the last ctrl_dual_arm call (not a measured position)")
    def get_target_joint_positions(self):
        return [float(value) for value in self.native.q_target]

    @read("arm_velocity_limit", unit="rad/s",
          description="Velocity limit the publish thread uses to clip a new target toward the current q")
    def get_arm_velocity_limit(self):
        return float(self.native.arm_velocity_limit)

    @read("motion_mode", type="boolean",
          description="True when the controller publishes on rt/arm_sdk (motion mode), false when it publishes on "
                      "rt/lowcmd")
    def get_motion_mode(self):
        return bool(self.native.motion_mode)

    # -- motion -------------------------------------------------------------------------------------------------
    @action(cap="cap.motion.joint_position.v1", long_running=True, cancellable=True,
            description="Store a target for the fourteen arm joints; the daemon publish thread applies it over time. "
                        "The upstream call only stores the target, so the receipt reports reached=false.",
            input={"joint_positions": Field(
                length=NUM_ARM_JOINTS, unit="rad",
                description="Target angle of the fourteen arm joints, left arm first then the right arm",
                limit=Limit.operator_required(JOINT_LIMIT_REASON))})
    def move_joints(self, joint_positions):
        targets = [float(value) for value in joint_positions]
        self.native.ctrl_dual_arm(targets, [0.0] * NUM_ARM_JOINTS)
        return {"reached": False, "joint_positions": self._current_joint_positions()}

    # -- safety --------------------------------------------------------------------------------------------------
    @action(name="x-cap.unitreerobotics.hold_position.v1",
            description="Set the arm targets to the last joint positions from the subscribed LowState buffer with zero "
                        "feedforward torque; this is an ordinary unconfirmed target request. The daemon publisher "
                        "keeps running, and the buffer has no freshness check.",
            output={
                "hold_requested": Field("boolean", description="True when the hold target was sent"),
                "joint_positions": Field("array", items="number", length=NUM_ARM_JOINTS, unit="rad",
                                         description="Last joint positions from the LowState buffer, used as the hold "
                                                     "target"),
            })
    def hold_position(self):
        current = self._hold()
        return {"hold_requested": True, "joint_positions": current}

    @estop(native="ctrl_dual_arm")
    def stop(self):
        """Request a buffered-position hold without reporting an unconfirmed physical stop as achieved."""
        self._hold()
        raise DriverFailed("MHS.DEVICE.NOT_READY", "ctrl_dual_arm only stores a target; no stop is confirmed")

    # -- helpers ---------------------------------------------------------------------------------------------------
    def _current_joint_positions(self):
        return [float(value) for value in self.native.get_current_dual_arm_q()]

    def _hold(self):
        current = self._current_joint_positions()
        self.native.ctrl_dual_arm(current, [0.0] * NUM_ARM_JOINTS)
        return current
