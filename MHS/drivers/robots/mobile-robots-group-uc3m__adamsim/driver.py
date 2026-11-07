"""OpenMHS driver for the ADAMSim PyBullet mobile-manipulator simulation (gh.mobile-robots-group-uc3m/adamsim).

The card names the ROS family and the ``RosDriver`` helper.  The pinned runtime that actually owns the
simulation and the base control is the Python class ``scripts.adam:ADAM``: ``ADAM.step`` calls
``p.stepSimulation()`` and ``Navigation.send_velocity`` converts a linear/angular velocity into the two
wheel targets.  ``scripts.ros_connection:ROSConnection`` is the simulator's bridge to a real ADAM robot
(ROS publishers for ``/robot/...`` and hand services); it has no pause, stop or reset service, and a
configuration-only ``RosDriver`` cannot start the PyBullet process.  This package therefore uses a direct
``Driver`` over ``ADAM`` (DEVIATION FROM THE CARD, recorded in RESULT.json).  With ``use_ros`` (an ADAM
default) that bridge mirrors the real robot's arm states into the simulation and holds publishers to the real
arm controllers and base; no method of this driver calls it.

Only the fake backend is declared.  A live backend would have to construct ``ADAM(use_fixed_base=False,
use_ros=False)``: ``Navigation`` exists only without a fixed base, and with ``use_ros`` at the pin ``ADAM.step``
reads an attribute ``ADAM`` never assigns.  In PyBullet real-time mode (``use_realtime``, the ADAM default) the
simulation advances by itself, so the stop is the zero wheel-velocity target, not the absence of step calls.

Scope: the differential-drive base.  ``cap.motion.mobile_base.v1`` applies a bounded velocity for a
bounded period, advancing ``ADAM.step`` once per control period, and the input-free
``x-cap.mobile-robots-group-uc3m.zero_wheels.v1`` safe-state action commands both wheel targets to zero
through ``Navigation.move_wheels``.
The camera angle and the two six-joint arm arrays are read-only state.  The arms are not commanded: the
upstream has no arm stop or arm quiescence feedback, and the arm and hand kinematics are outside this
package's scope (NOT COVERED in RESULT.json notes).

Every number that is a device claim cites the pinned clone at
85a9b1fce83a36c45bb29412546f67bc8a03c29b.  The fake backend is a pure-Python kinematic stand-in; it does
not import or run the clone, PyBullet, ROS or any hardware.  This package is model-authored and
unreviewed, and ``driver.lock.json`` keeps ``reviewed_by`` null.
"""

import math

from mhs.driver import Driver, Fact, Field, Limit, action, estop, read

#: The ADAM class owns the PyBullet client, the robot id and the control period.
_ADAM = "scripts.adam:ADAM"

#: ``Navigation.send_velocity`` clamps to two configurable constructor
#: defaults.  They are not device bounds, so the operator supplies the
#: deployment envelope.
_LINEAR_LIMIT = Limit.operator_required(
    "Navigation.send_velocity clamps the command to self.linear_speed, a configurable constructor "
    "default (scripts/navigation.py:14 and :208-209), not a device limit; the operator supplies the "
    "deployment linear-velocity bound."
)
_ANGULAR_LIMIT = Limit.operator_required(
    "Navigation.send_velocity clamps the command to self.angular_speed, a configurable constructor "
    "default (scripts/navigation.py:15 and :208-209), not a device limit; the operator supplies the "
    "deployment angular-velocity bound."
)
_DURATION_LIMIT = Limit.operator_required(
    "ADAM.step advances one control period per call (scripts/adam.py:173-193) and states no maximum "
    "command duration; the operator supplies the deployment duration bound."
)


class Adamsim(Driver):
    """Differential-drive base of the ADAMSim PyBullet simulation."""

    device_id = "adamsim"
    device_kind = "robot.mobile_base"
    mode = "simulated"
    #: A mobile base is at least R2 (MHS/spec/04-safety.md); the card floor is R0.
    risk = "R2"
    native = _ADAM
    backends = {"fake": ".fake:FakeAdam"}
    tags = ["pybullet", "simulation", "mobile-base", "differential-drive", "adamsim"]
    display_name = "ADAMSim ADAM mobile base"
    vendor = "Mobile Robots Group UC3M"
    model = "ADAM (ADAMSim)"

    facts = [
        Fact("ADAM is the ADAMSim robot class; its constructor connects a PyBullet GUI client and loads "
             "the robot URDF with the requested fixed-base flag.", source="upstream_code",
             ref="scripts/adam.py:20-70"),
        Fact("The ADAM constructor defaults use_realtime, use_fixed_base and use_ros to True.",
             source="upstream_code", ref="scripts/adam.py:21-31"),
        Fact("The ADAM constructor sets the control period self.t to 0.01.", source="upstream_code",
             ref="scripts/adam.py:77"),
        Fact("The ADAM constructor creates the Sensors and ArmsKinematics modules and creates Navigation "
             "only when use_fixed_base is false.", source="upstream_code", ref="scripts/adam.py:88-98"),
        Fact("The ADAM constructor imports and constructs ROSConnection only when use_ros is true.",
             source="upstream_code", ref="scripts/adam.py:107-109"),
        Fact("ADAM.step calls p.stepSimulation() only when use_realtime is false, measures the execution "
             "speed, and then sleeps for self.t or delegates to the ROS rate.", source="upstream_code",
             ref="scripts/adam.py:173-193"),
        Fact("Navigation.send_velocity clamps the linear and angular velocity to self.linear_speed and "
             "self.angular_speed, converts them to left/right wheel velocities with the wheel radius and "
             "wheel distance, and applies PyBullet VELOCITY_CONTROL to both wheel joints.",
             source="upstream_code", ref="scripts/navigation.py:200-217"),
        Fact("Navigation.move_wheels applies PyBullet VELOCITY_CONTROL to both wheel joints with the given "
             "left and right wheel speeds and force.", source="upstream_code",
             ref="scripts/navigation.py:23-34"),
        Fact("Navigation.move_base_continuous commands both wheel targets to zero with force 10 when its "
             "target is reached.", source="upstream_code", ref="scripts/navigation.py:160-169"),
        Fact("The Navigation constructor sets wheel_radius 0.0762, wheel_distance 0.436, linear_speed "
             "6.55 and angular_speed 1.0.",
             source="upstream_code", ref="scripts/navigation.py:7-18"),
        Fact("Sensors.get_camera_angle returns the camera joint position converted to degrees minus 45.",
             source="upstream_code", ref="scripts/sensors.py:117-124"),
        Fact("ArmsKinematics.get_arm_joint_angles reads the arm joint angles in radians from PyBullet.",
             source="upstream_code", ref="scripts/arms_kinematics.py:365-380"),
        Fact("semantic_groups_inspire_hands.json lists six joints for the right arm and six for the left "
             "arm.", source="upstream_code",
             ref="models/robot/rb1_base_description/config/semantic_groups_inspire_hands.json:2-19"),
        Fact("The README describes ADAMSim as a PyBullet-based simulation environment for the ADAM "
             "domestic mobile manipulator, with navigation, arm and hand kinematics, perception and ROS "
             "communication.", source="vendor_doc", ref="Readme.md:4-12"),
        Fact("The README requires ROS 1 Noetic and Python 3.8 and says ADAMSim is developed for "
             "Ubuntu/Linux.", source="vendor_doc", ref="Readme.md:39-42"),
        Fact("The navigation example constructs ADAM with use_fixed_base=False and use_ros=False.",
             source="upstream_code", ref="examples/example_navigation.py:9"),
        Fact("The navigation loop calls move_base_continuous and then advances the simulation with "
             "adam.step() in the same iteration.", source="upstream_code",
             ref="examples/example_navigation.py:48-71"),
        Fact("The ADAM constructor calls p.setRealTimeSimulation(1) when use_realtime is true and "
             "p.setRealTimeSimulation(0) otherwise.", source="upstream_code", ref="scripts/adam.py:54-55"),
        Fact("The ADAM constructor stores the real-time flag as self.use_realtime and the ROS flag as "
             "self.use_ros.", source="upstream_code", ref="scripts/adam.py:74-75"),
        Fact("When the robot_info JSON file is missing, the ADAM constructor generates it with "
             "print_robot_info(save=True).", source="upstream_code", ref="scripts/adam.py:81-83"),
        Fact("ROSConnection.sleep reads self.adam.useRealTimeSimulation to choose between "
             "rospy.sleep(self.adam.t) and self.rate.sleep().", source="upstream_code",
             ref="scripts/ros_connection.py:59-65"),
        Fact("The ROSConnection constructor initialises the ROS node adam_ros_node, subscribes "
             "/robot/left_arm/joint_states and /robot/right_arm/joint_states, creates JointTrajectory "
             "publishers on /robot/left_arm/scaled_pos_traj_controller/command and "
             "/robot/right_arm/scaled_pos_traj_controller/command and a Twist publisher on "
             "/robot/move_base/cmd_vel, and starts a 0.02 s hand-service timer and a 1/120 s real_to_sim timer.",
             source="upstream_code", ref="scripts/ros_connection.py:12-37"),
        Fact("ROSConnection.real_to_sim moves the simulated arms and hands to the latest arm joint states and "
             "hand states received from the robot.", source="upstream_code",
             ref="scripts/ros_connection.py:159-180"),
        Fact("ROSConnection.call_get_angle_act calls rospy.wait_for_service on "
             "/robot/<arm>/inspire_hand/get_angle_act with no timeout before calling the service.",
             source="upstream_code", ref="scripts/ros_connection.py:183-196"),
        Fact("The README says the architecture allows synchronized operation between the real robot and its "
             "digital twin, including experiments running both simulated and real robots simultaneously.",
             source="vendor_doc", ref="Readme.md:12"),
    ]

    safe_state = (
        "Both wheel targets are commanded to zero through Navigation.move_wheels (PyBullet VELOCITY_CONTROL, "
        "force 100) and the driver stops calling ADAM.step: in real-time mode (use_realtime, the ADAM default) "
        "the world keeps advancing and the wheel motors brake toward zero, in stepped mode it stays frozen until "
        "the next ADAM.step applies the zero targets, and with no wheel-velocity getter this is a commanded "
        "stop, not measured quiescence; the arms are not commanded."
    )

    #: The deployed fake is a kinematic stand-in, not the PyBullet simulator.
    fidelity = {
        "engine": "analytic:ADAMSim kinematic base stand-in (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "The fake integrates the commanded velocity with a fixed 0.01 s period and no physics "
                     "solver, contacts, actuator model or wall-clock pacing; placeholder state does not "
                     "establish a trajectory or state-hash replay.",
        },
        "timestep_ms": 10.0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a pure-Python kinematic stand-in for the ADAM base: it runs no PyBullet, no "
            "rigid-body dynamics, no contacts, no wheel friction and no GUI, and it is not a recording of "
            "captured simulator traffic",
            "one fake tick is 10 ms, the ADAM control period self.t (scripts/adam.py:77); the PyBullet "
            "physics timestep is not set by ADAM and is not modelled or claimed by the fake",
            "the native backend is not declared: constructing the real simulator needs pybullet, a PyBullet "
            "GUI client (scripts/adam.py:51), ROS 1 Noetic and Python 3.8 (Readme.md:39), and it was neither "
            "installed nor run by this package",
            "the arms are read-only state: no arm or hand command is exposed because the upstream has no arm "
            "stop, arm quiescence feedback or gripper stop, and the camera, lidar and RGB-D outputs are not "
            "exposed (NOT COVERED in RESULT.json)",
            "the fake's wheel radius, wheel distance, linear/angular clamp and 10 ms period are the upstream "
            "constructor values copied to mirror Navigation.send_velocity and ADAM.step, not device limits",
            "the zero-velocity stop is a motor-target command: the clone has no wheel-velocity readback, so "
            "the safe-state action cannot prove that the simulated base reached zero speed",
            "the ADAM constructor defaults are use_fixed_base=True and use_ros=True (scripts/adam.py:21-31): "
            "with a fixed base it creates no Navigation (:97-98), so drive, stop and e-stop need "
            "use_fixed_base=False; with use_ros, ADAM.step calls ROSConnection.sleep, which reads "
            "self.adam.useRealTimeSimulation (scripts/ros_connection.py:64), an attribute ADAM never assigns "
            "(it stores use_realtime, scripts/adam.py:74), so every step fails at the pin",
            "in PyBullet real-time mode (use_realtime, the ADAM default; scripts/adam.py:54) the world advances "
            "by itself and ADAM.step only sleeps, so ending the step calls does not stop it; in stepped mode "
            "each ADAM.step is one stepSimulation at a PyBullet timestep ADAM does not set, so the dead-reckoned "
            "distance (applied velocity times duration_s) is not the simulated travel",
            "constructing ADAM opens a PyBullet GUI client, prints to stdout, writes the robot_info JSON into "
            "the clone's config directory when it is missing (scripts/adam.py:51, :81-83), and with use_ros "
            "initialises a ROS node whose timers mirror the real robot's arms into the simulation and block in "
            "rospy.wait_for_service on the real hands' services (scripts/ros_connection.py:14-37, :159-196)",
        ],
    }

    @read("camera_angle", unit="deg",
          description="Camera angle reported by Sensors.get_camera_angle: the camera joint position in degrees minus 45")
    def camera_angle(self):
        return float(self.native.sensors.get_camera_angle())

    @read("left_arm_joint_positions", type="array", items="number", unit="rad", length=6,
          description="Six left-arm joint angles in the semantic_groups_inspire_hands.json order")
    def left_arm_joint_positions(self):
        return [float(value) for value in self.native.arm_kinematics.get_arm_joint_angles("left")]

    @read("right_arm_joint_positions", type="array", items="number", unit="rad", length=6,
          description="Six right-arm joint angles in the semantic_groups_inspire_hands.json order")
    def right_arm_joint_positions(self):
        return [float(value) for value in self.native.arm_kinematics.get_arm_joint_angles("right")]

    @action(
        cap="cap.motion.mobile_base.v1",
        long_running=True,
        cancellable=True,
        max_duration_ms=300000,
        description=(
            "Drive the simulated differential-drive base at a linear and angular velocity for a bounded "
            "period. The driver commands Navigation.send_velocity and advances ADAM.step once per control "
            "period, then commands both wheel targets to zero on every exit. Distance and heading change are "
            "dead-reckoned from the applied velocities, not measured by an upstream odometry getter."
        ),
        input={
            "linear_velocity": Field(
                "number", unit="m/s",
                description="Commanded forward velocity before the upstream Navigation clamp",
                limit=_LINEAR_LIMIT,
            ),
            "angular_velocity": Field(
                "number", unit="rad/s",
                description="Commanded yaw rate before the upstream Navigation clamp",
                limit=_ANGULAR_LIMIT,
            ),
            "duration_s": Field(
                "number", unit="s",
                description="Period to hold the velocity; converted to ADAM.step ticks with self.t",
                limit=_DURATION_LIMIT,
            ),
        },
        examples=[{"linear_velocity": 0.2, "angular_velocity": 0.0, "duration_s": 5.0}],
    )
    def drive(self, linear_velocity, angular_velocity, duration_s):
        self.check_cancelled()
        period = float(self.native.t)
        if period <= 0.0:
            raise ValueError("ADAM.t must be positive to convert duration_s into simulation ticks")
        linear = float(linear_velocity)
        angular = float(angular_velocity)
        duration = float(duration_s)
        linear_limit = float(self.native.navigation.linear_speed)
        angular_limit = float(self.native.navigation.angular_speed)
        applied_linear = max(-linear_limit, min(linear_limit, linear))
        applied_angular = max(-angular_limit, min(angular_limit, angular))
        ticks = max(1, int(round(duration / period)))
        try:
            # send_velocity sets the two wheel targets in two PyBullet calls (navigation.py:214-217); a failure
            # between them is also covered by the zeroing below.
            self.native.navigation.send_velocity(applied_linear, applied_angular)
            for _ in range(ticks):
                self.check_cancelled()
                self.native.step()
        finally:
            # Reviewer change: zero the wheel targets on every exit, not only on cancellation.  A failing
            # ADAM.step (with use_ros it reads self.adam.useRealTimeSimulation, ros_connection.py:64, which ADAM
            # never assigns) would otherwise leave the targets at the commanded velocity, and in PyBullet
            # real-time mode (adam.py:54) the base would keep driving.
            self.native.navigation.move_wheels(0.0, 0.0)
        self.check_cancelled()
        heading = math.atan2(math.sin(applied_angular * duration), math.cos(applied_angular * duration))
        return {
            "distance_m": abs(applied_linear) * duration,
            "heading_rad": heading,
            "stopped": True,
        }

    @action(
        name="x-cap.mobile-robots-group-uc3m.zero_wheels.v1",
        safe_state=True,
        description=(
            "Command both wheel targets to zero through Navigation.move_wheels. The upstream exposes no "
            "wheel-velocity readback and no deceleration profile, so the receipt reports that the zero "
            "command was applied, not that the simulated base was measured at rest."
        ),
        output={
            "stopped": Field(
                "boolean",
                description="True when the upstream zero wheel-velocity command was applied",
            ),
        },
    )
    def stop_motion(self):
        self.native.navigation.move_wheels(0.0, 0.0)
        return {"stopped": True}

    @estop(native="navigation.move_wheels")
    def emergency_stop(self):
        self.native.navigation.move_wheels(0.0, 0.0)
