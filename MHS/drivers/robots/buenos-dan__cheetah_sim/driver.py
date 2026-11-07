"""OpenMHS driver for the cheetah_sim ROS 1/Gazebo quadruped (gh.buenos-dan/cheetah_sim).

The pinned repository is a ROS 1 Gazebo simulation, not a packaged ROS
node with a fixed, statically named control endpoint.  Its control surface is
the ``ros_package/cheetah_core/src/leg_control/legController.py`` Python class:
``LegController`` publishes one ``std_msgs/Float64`` message to each of the
twelve position-controller topics, and ``Cheetah.stand`` commands the four
legs to a fixed end-effector pose.  The topic names are assembled at runtime
from the controller name and the 1-based joint index
(``legController.py:23``), so a configuration-only ``RosDriver`` cannot cite
the exact endpoint literals the gate requires.  There is also no stop, pause
or reset service/action in the clone: the only stop-shaped path is the active
``Cheetah.stand`` posture command, twelve unacknowledged topic publications.
This package therefore uses a direct ``Driver`` over the pinned ``Cheetah``
class and a package-local analytic fake.  It is simulated-only: the loader
refuses a hardware backend on a simulated driver, and the fake/sim backends
may not use ``.native``.  No live ROS backend is claimed; the pinned modules
are Python 2 code (``legController.py:48``), and a deployment would need a
separately reviewed live driver.  The fake is not the upstream Gazebo
simulator and no ROS graph or hardware was run.

Model review (2026-11-05): the e-stop still sends the stand posture command,
but it reports ``MHS.SAFETY.SAFE_STATE_UNREACHED`` with the latch held, and
the stand action is no longer a safe-state action: an unacknowledged
publication that any running demo node overrides cannot certify a stop.  The
package is blocked (HELPER_MISSING).

Every Fact cites the pinned clone at
8c8948fbf041e2f5bc8e0225de0a665a262572ab.
"""

from mhs.driver import Driver, DriverFailed, Fact, Field, Limit, action, estop

#: The pinned class is the reusable high-level pose command: it owns the four
#: LegController objects (a dict keyed by leg name) and the fixed stand pose.
_NATIVE = "ros_package.cheetah_core.src.stand_demo:Cheetah"

#: No upstream text states a joint-angle envelope: the URDF declares the leg
#: joints continuous, the controller YAML states only PID gains and the
#: publisher writes the value unchanged.  The operator supplies the envelope.
_ANGLE_LIMIT = Limit.operator_required(
    "the pinned URDF declares the leg joints continuous and the controller config states no "
    "joint-position limit; the deployment operator supplies the joint-angle envelope in site-limits.json"
)


class CheetahSim(Driver):
    device_id = "cheetah-sim"
    device_kind = "robot.mobile_base"
    mode = "simulated"
    #: A quadruped is a mobile base; the catalogue's mobile-base class is R2
    #: even though this package's published commands reach only Gazebo.
    risk = "R2"
    native = _NATIVE
    backends = {"fake": ".fake:FakeCheetahSim"}
    tags = ["ros", "ros1", "gazebo", "simulation", "quadruped", "joint-position"]
    display_name = "Cheetah quadruped Gazebo simulation"
    vendor = "buenos-dan"
    model = "cheetah quadruped (ROS 1/Gazebo)"
    facts = [
        Fact("The README describes the repository as a quadrupedal robot simulation by ROS and Gazebo.",
             source="vendor_doc", ref="README.md:7"),
        Fact("The README quick start launches cheetah_gazebo, cheetah_control and the cheetah_core "
             "stand_demo script.", source="vendor_doc", ref="README.md:23-28"),
        Fact("LegController stores the leg name, the joint_name list of hip/thigh/calf, the leg's fixed "
             "JOINT_OFFSET and three publisher objects.", source="upstream_code",
             ref="ros_package/cheetah_core/src/leg_control/legController.py:14-25"),
        Fact("LegController builds each command topic by concatenating /cheetah/, the leg name, _joint, the "
             "1-based joint index and _position_controller/command, and creates a rospy Publisher of Float64 "
             "with queue_size 5 on it.",
             source="upstream_code",
             ref="ros_package/cheetah_core/src/leg_control/legController.py:22-25"),
        Fact("_writeJointPosInRad adds the leg's fixed joint offset to the requested angle and publishes the "
             "sum as a Float64 message.", source="upstream_code",
             ref="ros_package/cheetah_core/src/leg_control/legController.py:32-35"),
        Fact("writeEndPos runs inverseKinematics on the end-effector position and writes the three resulting "
             "joint angles.", source="upstream_code",
             ref="ros_package/cheetah_core/src/leg_control/legController.py:37-40"),
        Fact("The __main__ block of legController.py ends with the Python 2 print statement "
             "print \"hello world\".", source="upstream_code",
             ref="ros_package/cheetah_core/src/leg_control/legController.py:43-48"),
        Fact("Cheetah.__init__ stores the leg_names list and a controllers dict that maps each leg name to a "
             "LegController.", source="upstream_code",
             ref="ros_package/cheetah_core/src/stand_demo.py:15-18"),
        Fact("Cheetah.stand commands each of the four legs to a fixed end-effector pose through writeEndPos.",
             source="upstream_code", ref="ros_package/cheetah_core/src/stand_demo.py:20-26"),
        Fact("Cheetah.run calls stand every 0.1 s until rospy shuts down, and the script's main initialises "
             "the anonymous node control_node and runs it.", source="upstream_code",
             ref="ros_package/cheetah_core/src/stand_demo.py:28-37"),
        Fact("trot_demo.py's trot writes each leg's computed end position through "
             "self.controllers[leg].writeEndPos, and its run calls trot with the elapsed ROS time every "
             "0.01 s until rospy shuts down.", source="upstream_code",
             ref="ros_package/cheetah_core/src/trot_demo.py:82-97"),
        Fact("The control launch spawns twelve position controllers and the joint_state_controller under "
             "the /cheetah namespace.", source="upstream_code",
             ref="ros_package/cheetah_control/launch/cheetah_control.launch:7-20"),
        Fact("The controller configuration loads joint_state_controller with publish_rate 50 and twelve "
             "effort_controllers/JointPositionController entries.", source="upstream_code",
             ref="ros_package/cheetah_control/config/cheetah_control.yaml:3-56"),
        Fact("The URDF's gazebo_ros_control plugin declares robotNamespace /cheetah and robotSimType "
             "gazebo_ros_control/DefaultRobotHWSim.", source="upstream_code",
             ref="ros_package/cheetah_description/urdf/cheetah.urdf:3-6"),
        Fact("The URDF declares the leg joint LF_JOINT1 as a continuous joint without a limit element.",
             source="upstream_code",
             ref="ros_package/cheetah_description/urdf/cheetah.urdf:311-325"),
        Fact("settings.py defines BODY_LENGTH, BODY_WIDTH, the hip, thigh and calf lengths in LEG_LENGTH, "
             "LEG_NAME and the per-leg JOINT_OFFSET values.", source="upstream_code",
             ref="ros_package/cheetah_core/src/lib/settings.py:7-19"),
        Fact("The Gazebo launch includes empty_world.launch with paused=true and spawns the cheetah model "
             "from the URDF.", source="upstream_code",
             ref="ros_package/cheetah_gazebo/launch/cheetah.launch:2-16"),
    ]
    safe_state = (
        "No safe state is certified: the e-stop sends the Cheetah.stand posture (twelve unacknowledged "
        "Float64 setpoints) and reports SAFE_STATE_UNREACHED with the latch held; Gazebo keeps simulating, "
        "nothing senses quiescence, a running stand_demo (0.1 s) or trot_demo (0.01 s) node overrides the "
        "setpoints, and the legs track whatever setpoint the position controllers received last."
    )
    #: The package fake is a Python stand-in for the pinned Python 2/rospy
    #: publisher; it is not the Gazebo simulator and not a recording.
    fidelity = {
        "engine": "analytic:Python package fake (no physics)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "none",
            "notes": "Event-driven Python fake with no physics step, ROS graph, controller dynamics or "
                     "wall-clock pacing; placeholder joint and stand state does not establish a trajectory "
                     "or state-hash replay",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "reset": "none",
        "snapshot_restore": False,
        "gaps": [
            "the fake is an analytic Python stand-in for the upstream Python 2/rospy publisher, not a "
            "recording of captured ROS traffic and not the Gazebo simulator; it runs no physics, contacts, "
            "controller dynamics or IK",
            "the twelve /cheetah/<leg>_joint<N>_position_controller/command topics are assembled at "
            "legController.py:23; the fake publishes no ROS messages and no live ROS backend is declared "
            "or run by this simulated package",
            "the upstream stand command is an active posture command, not a stop: the e-stop sends it and "
            "then reports SAFE_STATE_UNREACHED with the latch held, and no joint-state, TF, IMU or contact "
            "observation confirms that the robot stopped",
            "the README's stand_demo node republishes the stand pose every 0.1 s and trot_demo publishes a "
            "trot gait every 0.01 s on the same twelve topics (stand_demo.py:28-31, trot_demo.py:93-97); "
            "while either runs it overrides this package's joint and stand commands",
            "the native modules are Python 2 code (print statements at legController.py:48 and "
            "InverseKinematics.py:57; InverseKinematics.py:4 imports settings as an implicit relative "
            "import): the native class cannot be imported by the SDK's Python 3, so no live backend can "
            "construct it",
            "the gate's call recorder does not trace calls on objects inside the upstream controllers dict, "
            "so it cannot see the per-joint publication of the leg command (only the fake's own record does)",
            "the /cheetah/joint_states topic from the joint_state_controller and the IMU plugin are not "
            "exposed; there is no read-back of the commanded joint positions",
            "the Gazebo launch starts the world paused=true (cheetah.launch:4); the operator must unpause it "
            "and the fake does not model pause/unpause",
            "the upstream controllers, Gazebo physics and rosbridge are ROS 1 components; no ROS graph, "
            "Gazebo process, rosbridge connection or hardware was started or tested here",
            "the fake's joint and stand values are placeholders; the real stand pose and IK are in "
            "stand_demo.py:20-26 and InverseKinematics.py:6-51 and are not used as facts",
        ],
    }

    @action(
        name="x-cap.buenos-dan.leg_position.v1",
        description=(
            "Publish one joint-angle command to a leg's position controller. The angle is the value before "
            "the per-leg JOINT_OFFSET; the upstream method adds that fixed offset and publishes a "
            "std_msgs/Float64. The receipt confirms that the message was handed to the publisher, not that "
            "the joint moved or reached the target."
        ),
        risk="R2",
        cancellable=True,
        input={
            "leg": Field(
                "string",
                description="Leg whose position controller receives the command",
                enum=["LF", "LB", "RF", "RB"],
            ),
            "joint": Field(
                "string",
                description="Joint within the leg, mapped through LegController.joint_name",
                enum=["hip", "thigh", "calf"],
            ),
            "angle_rad": Field(
                "number",
                unit="rad",
                description="Joint angle before the fixed per-leg JOINT_OFFSET",
                limit=_ANGLE_LIMIT,
            ),
        },
        output={
            "leg": Field("string", description="Leg that received the command"),
            "joint": Field("string", description="Joint that received the command"),
            "joint_index": Field("integer", unit="1", description="Zero-based index in LegController.joint_name"),
            "angle_rad": Field("number", unit="rad", description="Joint angle before the fixed offset"),
            "published": Field("boolean", description="True when the publisher call was made"),
            "confirmed": Field(
                "boolean",
                description="Always false: the upstream publisher has no execution or arrival acknowledgement",
            ),
        },
        examples=[{"leg": "LF", "joint": "hip", "angle_rad": 0.2}],
    )
    def move_joint(self, leg, joint, angle_rad):
        # Cheetah.controllers is a dict keyed by leg name (stand_demo.py:18).
        controller = self.native.controllers[leg]
        index = controller.joint_name.index(joint)
        controller._writeJointPosInRad(index, angle_rad)
        self.check_cancelled()
        return {
            "leg": leg,
            "joint": joint,
            "joint_index": index,
            "angle_rad": angle_rad,
            "published": True,
            "confirmed": False,
        }

    @action(
        name="x-cap.buenos-dan.stand.v1",
        description=(
            "Command the four legs to the upstream fixed stand end-effector pose. This is an active posture "
            "command, not a stop or a measured stand: the position controllers provide no quiescence "
            "acknowledgement, so it is not a safe-state action and is refused while the e-stop is latched."
        ),
        risk="R2",
        output={
            "legs": Field("array", items="string", length=4, description="Legs commanded to the stand pose"),
            "commanded": Field("boolean", description="True when the stand publication calls were made"),
            "confirmed": Field(
                "boolean",
                description="Always false: the upstream publisher has no posture or quiescence acknowledgement",
            ),
        },
    )
    def stand(self):
        self.native.stand()
        return {"legs": list(self.native.leg_names), "commanded": True, "confirmed": False}

    @estop(native="stand")
    def stop(self):
        """Send the upstream stand posture command, then refuse to certify it.

        The clone has no stop, pause or reset service/action; ``Cheetah.stand``
        publishes twelve position setpoints without any acknowledgement, and a
        running demo node overrides them.  The e-stop therefore reports
        SAFE_STATE_UNREACHED and the latch stays held (model review,
        2026-11-05).
        """
        self.native.stand()
        raise DriverFailed(
            "MHS.SAFETY.SAFE_STATE_UNREACHED",
            "the stand posture command was published without acknowledgement; the clone has no stop, pause "
            "or reset service and nothing confirms that the simulated robot stopped",
        )
