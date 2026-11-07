"""OpenMHS Gymnasium driver for the MARA environment of gh.acutronicrobotics/gym-gazebo2.

The card names ``gym_gazebo2.envs.MARA:MARAEnv`` beside ``MARARealEnv``.  The
confirmed MARA-v0 entry is a legacy OpenAI Gym environment
(``class MARAEnv(gym.Env)``, gym_gazebo2/envs/MARA/mara.py:40) registered at
gym_gazebo2/__init__.py:6-9.  Its primary interface is ``reset()`` and
``step(action)``, not a ROS topic contract: the ROS 2 publisher and
subscriber inside ``MARAEnv`` are its transport to Gazebo.  A
``GymnasiumDriver`` therefore matches the runtime, and the ROS helper named
by the card does not (DEVIATION FROM THE CARD, recorded in RESULT.json).

``cap.world.step.v1`` takes ``{ticks, action}`` with the action derived from
the environment's ``Box`` action space.  ``cap.world.reset.v1`` and
``cap.world.seed.v1`` are the bridge's world classes.  ``MARAEnv`` publishes
``JointTrajectory`` commands on ``/mara_controller/command``, the topic
``MARARealEnv`` also publishes (mara.py:99, 149; mara_real.py:72-74, 222-228),
so the device risk is R2 (an arm) however simulated the deployment.  The
package declares no hardware or ``sim`` backend.
``gym.make("MARA-v0")``, ROS 2 Dashing and Gazebo 9.9.0 are required by a
live deployment; none of them is installed or contacted here.  The ``fake``
backend is this package's analytic stand-in and claims F0 only.

Every fact cites a text file of the pinned clone at commit
545e203e07895927fd7aae66596d83d97ee89fe5.  The action-space bounds are not
repeated as a ``Limit``: the bridge derives them from the fake's space and
``action_space_ref`` cites the upstream code that defines the same bounds.
"""

from mhs.driver import Fact, GymnasiumDriver

#: The registered MARA-v0 entry point, named by the card.
NATIVE = "gym_gazebo2.envs.MARA:MARAEnv"

#: The action space of MARAEnv: Box(-pi, pi) over ``numJoints`` joints.
ACTION_SPACE_REF = "gym_gazebo2/envs/MARA/mara.py:169-172"


class GymGazebo2MARA(GymnasiumDriver):
    # R2, not the inherited R0 (grok-4.7, 2026-11-05; REVIEW.md item 12):
    # MARAEnv publishes JointTrajectory on /mara_controller/command (mara.py:99, 149).
    # MARARealEnv uses the same publisher topic and its step publishes the same
    # message (mara_real.py:72-74, 222-228). launchReal starts the real cognition
    # node (ut_launch.py:158-168). No fact cites that only Gazebo consumes the
    # topic. An arm is R2 however simulated the deployment. The latch does not
    # publish a zero trajectory.
    risk = "R2"
    device_id = "gym-gazebo2-mara"
    env_id = "MARA-v0"
    native = NATIVE
    backends = {"fake": ".fake:FakeGymGazebo2"}
    action_space_ref = ACTION_SPACE_REF
    display_name = "gym-gazebo2 MARA simulated arm"
    vendor = "Acutronic Robotics"
    model = "MARA-v0"
    tags = ["gym-gazebo2", "mara", "robot-arm", "ros2", "gazebo", "simulation", "gymnasium"]
    facts = [
        Fact("gym-gazebo2 describes itself as a toolkit for developing and comparing reinforcement learning "
             "algorithms using ROS 2 and Gazebo, built as an extension of gym-gazebo.",
             source="vendor_doc", ref="README.md:5"),
        Fact("The installation instructions require ROS 2 Dashing and Gazebo 9.9.0, and state that lower "
             "versions such as 9.0.0 will not work.",
             source="vendor_doc", ref="INSTALL.md:17-22"),
        Fact("The package registers MARA-v0 with entry point gym_gazebo2.envs.MARA:MARAEnv.",
             source="upstream_code", ref="gym_gazebo2/__init__.py:6-9"),
        Fact("MARAEnv is a subclass of gym.Env.",
             source="upstream_code", ref="gym_gazebo2/envs/MARA/mara.py:40"),
        Fact("MARAEnv launches the Gazebo launch description returned by generateLaunchDescriptionMara in a new "
             "service process.", source="upstream_code", ref="gym_gazebo2/envs/MARA/mara.py:67-69"),
        Fact("The MARA launch description starts gzserver or gazebo with libgazebo_ros_factory.so and "
             "libgazebo_ros_init.so, then the MARA spawn and cognition nodes.",
             source="upstream_code", ref="gym_gazebo2/utils/ut_launch.py:142-155"),
        Fact("MARAEnv publishes JointTrajectory commands on /mara_controller/command, subscribes to "
             "JointTrajectoryControllerState on /mara_controller/state and /gazebo_contacts, and creates an "
             "Empty client for /reset_simulation.", source="upstream_code",
             ref="gym_gazebo2/envs/MARA/mara.py:148-152"),
        Fact("The number of joints comes from the KDL chain and the observation dimension is numJoints + 6 + 12.",
             source="upstream_code", ref="gym_gazebo2/envs/MARA/mara.py:160-164"),
        Fact("The action space is Box(-pi, pi) over numJoints and the observation space is Box(-inf, inf) of "
             "obs_dim.", source="upstream_code", ref="gym_gazebo2/envs/MARA/mara.py:169-176"),
        Fact("take_observation concatenates joint positions, end-effector position error, end-effector "
             "velocities, current end-effector position and a 9-element rotation matrix.",
             source="upstream_code", ref="gym_gazebo2/envs/MARA/mara.py:272-276"),
        Fact("getTrajectoryMessage writes the action values into JointTrajectoryPoint.positions and the "
             "configured velocity into velocities.", source="upstream_code",
             ref="gym_gazebo2/utils/ut_mara.py:84-102"),
        Fact("seed() seeds numpy's generator through seeding.np_random and returns [seed].",
             source="upstream_code", ref="gym_gazebo2/envs/MARA/mara.py:294-296"),
        Fact("step() publishes the trajectory, takes an observation, calls collision(), computes the reward, "
             "sets done when iterator equals max_episode_steps, and returns the legacy four-tuple "
             "(obs, reward, done, info).",
             source="upstream_code", ref="gym_gazebo2/envs/MARA/mara.py:298-354"),
        Fact("MARAEnv sets max_episode_steps to a default of 1024 that baselines can update.",
             source="upstream_code", ref="gym_gazebo2/envs/MARA/mara.py:77-77"),
        Fact("collision() calls the /reset_simulation service when a contact message was received since the "
             "last check.", source="upstream_code", ref="gym_gazebo2/envs/MARA/mara.py:280-292"),
        Fact("take_observation() calls rclpy.spin_once in a loop until a controller state message passes its "
             "stamp check; the loop has no timeout.", source="upstream_code",
             ref="gym_gazebo2/envs/MARA/mara.py:235-243"),
        Fact("reset() calls the /reset_simulation service, resets iterator and returns only the observation.",
             source="upstream_code", ref="gym_gazebo2/envs/MARA/mara.py:356-376"),
        Fact("close() destroys the ROS node, kills the launch process and its children, and shuts rclpy down.",
             source="upstream_code", ref="gym_gazebo2/envs/MARA/mara.py:378-385"),
        Fact("MARAEnv.__init__ parses the process command line with getArgsParserMARA().parse_args().",
             source="upstream_code", ref="gym_gazebo2/envs/MARA/mara.py:49-50"),
        Fact("MARARealEnv starts the launchReal description in a new launch service process.",
             source="upstream_code", ref="gym_gazebo2/envs/MARA/mara_real.py:44-45"),
        Fact("launchReal runs the hros_cognition_mara_components node with the motors.yaml configuration and "
             "the real argument.", source="upstream_code", ref="gym_gazebo2/utils/ut_launch.py:158-168"),
        Fact("MARARealEnv uses /mara_controller/command for its robot publisher and /mara_controller/state for "
             "its subscriber.", source="upstream_code", ref="gym_gazebo2/envs/MARA/mara_real.py:72-74"),
        Fact("MARARealEnv.step() publishes ut_mara.getTrajectoryMessage(action[:numJoints], ...) on self._pub.",
             source="upstream_code", ref="gym_gazebo2/envs/MARA/mara_real.py:222-228"),
    ]
    safe_state = ("Software latch only: the runtime refuses every step, reset and seed until mhs.safety.reset, "
                  "and the last observation and tick stay readable. In a live MARA-v0 deployment Gazebo keeps "
                  "running in its own process and the controller keeps executing the last published trajectory. "
                  "The latch does not publish a zero JointTrajectory and does not stop a MARA controller on "
                  "/mara_controller/command, including the real controller MARARealEnv uses.")
    fidelity = {
        "engine": "gym-gazebo2:MARA-v0 analytic fake (no Gazebo, no ROS 2)",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake resets a placeholder joint offset from a Python random generator seeded by "
                     "reset(seed) or the preceding seed capability; the upstream environment seeds numpy through "
                     "seeding.np_random (mara.py:294-296), and no trajectory was compared with it",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is an analytic kinematic stand-in, not a recording: it replays no captured Gazebo, ROS 2 "
            "or MARA traffic and was never compared with the upstream environment",
            "no Gazebo server, ROS 2 graph, MARA URDF, KDL chain, controller, physics engine, contact sensor or "
            "camera is loaded; the fake moves each joint a placeholder fraction toward the commanded position "
            "and fabricates a 24-value observation in the upstream concatenation order (mara.py:272-276)",
            "upstream actions are absolute joint-position targets written to JointTrajectoryPoint.positions with "
            "a 1 ms time_from_start (ut_mara.py:84-102); the controller's tracking and joint limits are not "
            "modelled",
            "upstream step() resets the Gazebo simulation through /reset_simulation when a contact was received "
            "(mara.py:280-292, 320) without ending the episode; the fake has no contacts",
            "upstream step() and reset() wait without a timeout for a fresh controller state and reset() also "
            "waits for /reset_simulation (mara.py:235-243, 364-368); the e-stop latch cannot interrupt such a "
            "native call",
            "one step is one environment step with no simulated or wall-clock duration; timestep_ms is 0 because "
            "the fake has no physics clock, while a live Gazebo world advances on its own engine clock",
            "the 24-value observation size is the upstream size; every value is placeholder test data and no "
            "end-effector position, Jacobian or rotation matrix is computed",
            "the legacy four-tuple done flag is adapted by the SDK bridge to terminated=True with truncated=False; "
            "upstream done marks the 1024-step iterator limit (mara.py:77-77, 298-354), which a Gymnasium "
            "environment would normally report as truncation",
            "reset jitter, the tracking fraction, the reward and the 1024-step limit are fake test data marked "
            "as placeholders; the upstream reset restores the Gazebo simulation and the upstream reward is "
            "ut_math.computeReward",
            "the live environment needs ROS 2 Dashing and Gazebo 9.9.0 (INSTALL.md:17-22) plus the MARA workspace "
            "from INSTALL.md; none of it is installed where the gate runs",
            "no hardware backend exists: MARAReal-v0 (MARARealEnv) commands a real MARA arm by publishing "
            "JointTrajectory messages on /mara_controller/command to the hros_cognition_mara_components node "
            "that launchReal starts in real mode; that robot-arm path is out of scope",
            "constructing MARAEnv parses the host process's command line, launches Gazebo, calls rclpy.init and "
            "waits without a timeout for /spawn_entity (mara.py:50, 67-73, 181-182); no sim backend is declared",
            "snapshot and restore are not offered because MARAEnv defines no get_state or set_state method",
        ],
    }
