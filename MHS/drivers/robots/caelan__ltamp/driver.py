"""OpenMHS driver for gh.caelan/ltamp: the simulated PR2 of LTAMP's PyBullet controller (``PBController``).

Re-authored by Claude (claude-opus-5-5, a model and not a human) on 2026-11-05 (the user's decision of 2026-11-05:
Claude authors, Claude Sonnet reviews).  The earlier DeepSeek package served the retired real-PR2 ``ROSController``,
whose only stop is unacknowledged (blocked, NO_HARDWARE_FREE_PATH).  The card's override names the hardware-free
path instead: ``ROSWorld(sim_only=True)`` builds a PyBullet world and drives it with ``PBController``
(plan_tools/ros_world.py:15-38).

Why the software latch is an honest stop for this device.  ``ROSWorld`` switches PyBullet's real-time simulation off
(ros_world.py:27), so the simulated world advances only when code calls into it.  ``PBController`` keeps
``execute_motor_control`` false unless a caller sets it (pb_controller.py:23); then ``command_arm`` reaches
``follow_trajectory``, which sets the joint positions kinematically for each waypoint without stepping the physics
(pb_controller.py:103-148, 161-162).  Every command of this driver is one such call, refused once the e-stop latch is
engaged, so after the latch nothing this driver calls moves the simulated PR2.  The upstream has no stop of its own
(ROSWorld.stop resets the simulation and disconnects, ros_world.py:92-95, which ends the endpoint rather than stopping
it).  The one switch that makes PBController use motor control and step the physics is ``execute_motor_control``: with
it set, ``command_torso`` also calls ``control_joint`` with the target (pb_controller.py:77-78), and
``rest_for_duration`` and ``follow_trajectory`` loop over ``step_simulation`` (83-101, 124-143); follow_trajectory reads
the flag again for every waypoint (124).  The e-stop therefore sets that flag to false and reads it back, after the
runtime has latched; every command of this driver also refuses to run while the flag is set, because the motor-control
loops step the physics inside the call for up to ``max_sim_duration`` per waypoint and nothing in them checks for a
stop.  A command checks for cancellation and makes its kinematic set under a lock the e-stop also takes, so no set
happens after the e-stop returns.

The stop covers this driver's calls only.  Any other holder of the same ``ROSWorld`` or ``PBController`` in the process
can still set the flag or step the world (the upstream's plan runner sets ``execute_motor_control`` and executes a
plan, plan_tools/run_simulation.py:77-81), so a backend that builds the world must keep it private to the endpoint.

Scope: the two seven-joint arms (``Controller.LEFT_ARM``/``RIGHT_ARM``, control_tools/controller.py:8-11) and the
torso lift joint (``Controller.TORSO``, controller.py:16).  Arm bounds are the clone's PR2 safety-controller soft
limits (control_tools/common.py:11-30, copied from the PR2 URDF the world loads); the forearm-roll and wrist-roll
joints are continuous in that URDF and carry no bound.  The package is fake-only: ``fake.py`` is an in-memory
stand-in, not PyBullet (pybullet, the ss-pybullet submodule's ``pybullet_tools`` and the PR2 meshes are needed to
build the real world; see RESULT.json).
"""

from __future__ import annotations

import math
import threading

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop, read, write

COMMON = "control_tools/common.py"
CONTROLLER = "control_tools/controller.py"
PB = "control_tools/pb_controller.py"
WORLD = "plan_tools/ros_world.py"
URDF = "models/pr2_description/pr2.urdf"

LEFT_ARM = ["l_shoulder_pan_joint", "l_shoulder_lift_joint", "l_upper_arm_roll_joint", "l_elbow_flex_joint",
            "l_forearm_roll_joint", "l_wrist_flex_joint", "l_wrist_roll_joint"]           # controller.py:10-11
RIGHT_ARM = ["r_shoulder_pan_joint", "r_shoulder_lift_joint", "r_upper_arm_roll_joint", "r_elbow_flex_joint",
             "r_forearm_roll_joint", "r_wrist_flex_joint", "r_wrist_roll_joint"]          # controller.py:8-9
TORSO = "torso_lift_joint"                                                                   # controller.py:16

#: The timeout the upstream's own executor passes to command_arm (control_tools/execution.py:94); with
#: execute_motor_control false it only enters the unused velocity estimate of follow_trajectory (pb_controller.py:108-115).
COMMAND_TIMEOUT_S = 1.0
#: follow_trajectory's goal tolerance (pb_controller.py:104): 5e-3 * pi rad.
GOAL_TOLERANCE_RAD = 5e-3 * math.pi

_LOCK_GUARD = threading.Lock()


#: Per-element bounds of the 14-element arm command (left arm 0-6, right arm 7-13): the PR2 safety-controller soft
#: limits of control_tools/common.py.  Elements 4, 6, 11 and 13 (forearm roll, wrist roll) are continuous joints in the
#: PR2 URDF the world loads (pr2.urdf:2148, 2304, 3143, 3299) and carry no bound.
ARM_LIMITS = [
    Limit(min=-0.564601836603, max=2.1353981634, path="[0]", source="upstream_code", ref="control_tools/common.py:26"),
    Limit(min=-0.3536, max=1.2963, path="[1]", source="upstream_code", ref="control_tools/common.py:27"),
    Limit(min=-0.65, max=3.75, path="[2]", source="upstream_code", ref="control_tools/common.py:28"),
    Limit(min=-2.1213, max=-0.15, path="[3]", source="upstream_code", ref="control_tools/common.py:29"),
    Limit(min=-2.0, max=-0.1, path="[5]", source="upstream_code", ref="control_tools/common.py:30"),
    Limit(min=-2.1353981634, max=0.564601836603, path="[7]", source="upstream_code", ref="control_tools/common.py:19"),
    Limit(min=-0.3536, max=1.2963, path="[8]", source="upstream_code", ref="control_tools/common.py:20"),
    Limit(min=-3.75, max=0.65, path="[9]", source="upstream_code", ref="control_tools/common.py:21"),
    Limit(min=-2.1213, max=-0.15, path="[10]", source="upstream_code", ref="control_tools/common.py:22"),
    Limit(min=-2.0, max=-0.1, path="[12]", source="upstream_code", ref="control_tools/common.py:23"),
]


class LtampPR2PyBullet(Driver):
    device_id = "ltamp-pr2-pybullet"
    device_kind = "robot.arm"
    mode = "simulated"
    risk = "R1"
    native = "control_tools.pb_controller:PBController"
    backends = {"fake": ".fake:FakePBController"}
    vendor = "caelan"
    model = "PR2 in LTAMP's PyBullet world (PBController)"
    display_name = "LTAMP simulated PR2 (PyBullet PBController)"
    tags = ["pybullet", "pr2", "robot arm", "simulation", "task and motion planning"]
    safe_state = ("no command after the latch and PBController.execute_motor_control false (set and read back by "
                  "the e-stop): with real-time simulation off (ros_world.py:27) and commands that set joint positions "
                  "kinematically (pb_controller.py:103-148), nothing this endpoint calls advances the simulated PR2 "
                  "after the latch (another holder of the same world could)")
    facts = [
        Fact("ROSWorld(sim_only=True) skips rospy.init_node, connects a PyBullet client, switches real-time "
             "simulation off and builds PBPerception and PBController", source="upstream_code",
             ref=f"{WORLD}:16-38"),
        Fact("ROSWorld sets PyBullet's real-time simulation to 0 for its client", source="upstream_code",
             ref=f"{WORLD}:27"),
        Fact("ROSWorld loads the PR2 from the models directory with a fixed base and places its base link at the "
             "origin", source="upstream_code", ref=f"{WORLD}:51-60"),
        Fact("ROSWorld.stop resets the simulation, removing bodies and constraints, and disconnects the client",
             source="upstream_code", ref=f"{WORLD}:77-95"),
        Fact("PBController starts with execute_motor_control false", source="upstream_code", ref=f"{PB}:20-26"),
        Fact("execute_motor_control selects motor control in command_torso and rest_for_duration, and is read again "
             "for every waypoint of follow_trajectory", source="upstream_code", ref=f"{PB}:72-148"),
        Fact("get_joint_positions and set_joint_positions read and set the named joints of the robot through "
             "pybullet_tools", source="upstream_code", ref=f"{PB}:47-56"),
        Fact("command_torso always sets the torso lift joint position kinematically, and also calls control_joint "
             "with the same position when execute_motor_control is true", source="upstream_code", ref=f"{PB}:72-80"),
        Fact("follow_trajectory steps the simulation through joint_controller_hold2 for each waypoint when "
             "execute_motor_control is true, up to max_sim_duration simulated seconds per waypoint, and otherwise "
             "sets the joint positions of each waypoint", source="upstream_code", ref=f"{PB}:103-148"),
        Fact("command_arm calls command_arm_trajectory with one waypoint and its timeout as the time from start",
             source="upstream_code", ref=f"{PB}:150-162"),
        Fact("The upstream executor calls command_arm with timeout=1.0", source="upstream_code",
             ref="control_tools/execution.py:94"),
        Fact("Controller defines the seven arm joints of each arm, the four finger joints of each gripper, the "
             "torso lift joint and the two head joints", source="upstream_code", ref=f"{CONTROLLER}:8-17"),
        Fact("get_arm_positions returns get_joint_positions of the arm's joint names", source="upstream_code",
             ref=f"{CONTROLLER}:39-40"),
        Fact("PR2_JOINT_SAFETY_LIMITS lists the PR2 safety_controller soft limits taken from the PR2 URDF",
             source="upstream_code", ref=f"{COMMON}:11-36"),
        Fact("The PR2 URDF declares r_forearm_roll_joint and r_wrist_roll_joint continuous", source="upstream_code",
             ref=f"{URDF}:2148-2304"),
        Fact("The PR2 URDF declares l_forearm_roll_joint and l_wrist_roll_joint continuous", source="upstream_code",
             ref=f"{URDF}:3143-3299"),
        Fact("The upstream's simulation runner sets execute_motor_control true and enables gravity before it "
             "executes a plan", source="upstream_code", ref="plan_tools/run_simulation.py:77-81"),
    ]
    fidelity = {
        "engine": "analytic: in-memory PBController stand-in (no PyBullet, no physics)",
        "fidelity_level": "F0",
        "determinism": {"kind": "exact", "seed_control": "none",
                        "notes": "the fake has no randomness; its start pose is placeholder data"},
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is an in-memory stand-in for PBController, not PyBullet: no collisions, joint limits of the "
            "URDF, gravity, attachments or perception",
            "the package has no sim backend: building ROSWorld(sim_only=True) needs pybullet, the ss-pybullet "
            "submodule (pybullet_tools) and the PR2 model files, none of which the gate loads",
            "the start pose of the fake is placeholder data, not the URDF's zero configuration",
            "only the arms and the torso are served; grippers, head, attachments, perception and plan execution "
            "are not",
            "commands are refused when execute_motor_control is true (motor control steps the physics inside the "
            "call and cannot be stopped)",
        ],
    }

    # -- guard -----------------------------------------------------------------------------------------------------
    def _world_lock(self) -> threading.Lock:
        """Held by every command around its cancellation check and its kinematic set, and by the e-stop."""
        lock = getattr(self, "_pb_world_lock", None)
        if lock is None:
            with _LOCK_GUARD:
                lock = getattr(self, "_pb_world_lock", None)
                if lock is None:
                    lock = threading.Lock()
                    self._pb_world_lock = lock
        return lock

    def _kinematic_only(self) -> None:
        if self.native.execute_motor_control is not False:
            raise DriverFailed("MHS.DEVICE.PRECONDITION_UNMET",
                               "PBController.execute_motor_control is set: a command would step the physics inside "
                               "the call (pb_controller.py:124-143), which the e-stop latch cannot interrupt")

    # -- reads -----------------------------------------------------------------------------------------------------
    @read("joint_positions", type="array", items="number", unit="rad",
          description="Left then right arm joint angles in Controller.LEFT_ARM, RIGHT_ARM order")
    def joint_positions(self):
        return [float(value) for value in list(self.native.get_arm_positions("l"))
                + list(self.native.get_arm_positions("r"))]

    @read("torso_position", unit="m", description="Torso lift joint position")
    def torso_position(self):
        (value,) = self.native.get_joint_positions([TORSO])
        return float(value)

    # -- commands --------------------------------------------------------------------------------------------------
    @write("torso_position", unit="m", description="Torso lift joint position, set kinematically",
           limit=Limit(min=0.0115, max=0.325, source="upstream_code", ref="control_tools/common.py:14"))
    def set_torso_position(self, value):
        with self._world_lock():
            self._kinematic_only()
            self.check_cancelled()
            self.native.command_torso(float(value))
        (applied,) = self.native.get_joint_positions([TORSO])
        return float(applied)

    @action(cap="cap.motion.joint_position.v1",
            description="Set both PR2 arms kinematically with PBController.command_arm (left arm, then right arm)",
            input={"joint_positions": Field("array", length=len(LEFT_ARM) + len(RIGHT_ARM),
                                            items=Field("number", unit="rad", description="Joint angle"),
                                            description="Left then right arm joint angles in controller order",
                                            limit=ARM_LIMITS)})
    def move_arms(self, joint_positions):
        values = [float(value) for value in joint_positions]
        with self._world_lock():
            self._kinematic_only()
            self.check_cancelled()
            self.native.command_arm("l", values[:len(LEFT_ARM)], COMMAND_TIMEOUT_S)
            self.native.command_arm("r", values[len(LEFT_ARM):], COMMAND_TIMEOUT_S)
        actual = [float(value) for value in list(self.native.get_arm_positions("l"))
                  + list(self.native.get_arm_positions("r"))]
        reached = len(actual) == len(values) and all(abs(a - b) <= GOAL_TOLERANCE_RAD for a, b in zip(actual, values))
        return {"reached": reached, "joint_positions": actual, "tolerance_rad": GOAL_TOLERANCE_RAD}

    # -- safety ----------------------------------------------------------------------------------------------------
    @estop(native="execute_motor_control = False")
    def stop(self):
        """The runtime latches and cancels first; then motor control is switched off and read back.

        It takes the world lock: a command that holds it checked for cancellation before its kinematic set, so it
        either was cancelled (the server cancels before it stops) or finishes its instantaneous set before this runs.
        """
        with self._world_lock():
            self.native.execute_motor_control = False
            if self.native.execute_motor_control is not False:
                raise DriverFailed("MHS.DEVICE.FAULTED", "PBController.execute_motor_control did not read back false")
