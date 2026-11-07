"""OpenMHS driver for gh.pauldanielml/mujoco_rl_ur5: the Grasper-v0 UR5 pick-and-place environment.

``gym_grasper.envs:GraspEnv`` is a legacy ``gym`` MuJoCo environment (``GraspingEnv.py:13-14``, registered as
``Grasper-v0`` at ``gym_grasper/__init__.py:4-7``).  Its action is a pixel index and a rotation index
(``MultiDiscrete([IMAGE_HEIGHT * IMAGE_WIDTH, len(rotations)])``, ``GraspingEnv.py:163-165``), its observation is a
dictionary with an RGB and a depth array (``GraspingEnv.py:402-404``), and its reward is binary
(``GraspingEnv.py:130-142``).  The card's ``GymnasiumDriver`` expresses that interface: the bridge derives
``cap.world.step.v1`` from the environment's spaces and serves ``cap.world.reset.v1`` and ``cap.world.seed.v1``; no
method or command table is needed.  This is the card's helper, not a deviation.

The device is simulated (``mode = "simulated"``, R0): the clone contains no hardware path, no serial port and no
robot API.  The package therefore has one backend, the fake in ``fake.py``; there is no ``native.py`` and no
hardware backend.  The fake is a pure Python stand-in because the upstream environment needs mujoco-py, MuJoCo 2.1,
OpenCV, gym, numpy and a C compiler, which are not present where the gate runs, and package code never imports the
clone.  A backend name outside ``backends`` (``sim``) would be served by ``gymnasium.make("Grasper-v0")``
(``GymnasiumDriver.open_native``); the registration is in ``gym`` (``gym_grasper/__init__.py:1-7``), so that path
needs the upstream package installed and was not run here.

Every fact and constant cites a line of the clone at commit ``206d33edf0bc29aca6cd14778de6488e1d1ed0b3``.  The
package is model-authored and unreviewed; it is checked on the fake backend only and no hardware was involved.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "gym_grasper/envs/GraspingEnv.py"
SCENE = "UR5+gripper/UR5gripper_2_finger_many_objects.xml"


class UR5Grasper(GymnasiumDriver):
    device_id = "ur5_grasper"
    env_id = "Grasper-v0"
    native = "gym_grasper.envs:GraspEnv"
    backends = {"fake": ".fake:FakeGraspEnv"}
    display_name = "MuJoCo UR5 + gripper Grasper-v0 (simulation)"
    vendor, model = "Paul Daniel", "Grasper-v0"
    tags = ["ur5", "gripper", "pick-and-place", "mujoco", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The default scene is UR5+gripper/UR5gripper_2_finger_many_objects.xml", source="upstream_code",
             ref=f"{ENV}:30"),
        Fact("The default image width and height are 200 pixels", source="upstream_code", ref=f"{ENV}:31-32"),
        Fact("The wrist rotations are 0, 30, 60, 90, -30 and -60 degrees, indexed 0 to 5", source="upstream_code",
             ref=f"{ENV}:40"),
        Fact("The action space is MultiDiscrete([IMAGE_HEIGHT * IMAGE_WIDTH, len(rotations)])",
             source="upstream_code", ref=f"{ENV}:163-165"),
        Fact("An action is decoded as x = action[0] % IMAGE_WIDTH, y = action[0] // IMAGE_WIDTH and "
             "rotation = action[1]", source="upstream_code", ref=f"{ENV}:94-97"),
        Fact("The environment steps MuJoCo with frame_skip 1", source="upstream_code", ref=f"{ENV}:47"),
        Fact("The default scene's MuJoCo integration timestep is 2e-3 s", source="upstream_code",
             ref=f"{SCENE}:19"),
        Fact("An observation is a dictionary with an rgb array and a depth array returned by the controller's "
             "camera", source="upstream_code", ref=f"{ENV}:402-404"),
        Fact("get_observation requests an IMAGE_WIDTH by IMAGE_HEIGHT image and converts the depth image to meters",
             source="upstream_code", ref=f"{ENV}:398-401"),
        Fact("The reward is binary: 0 when the pixel is skipped or the grasp fails, and 1 when move_and_grasp "
             "reports a grasp", source="upstream_code", ref=f"{ENV}:130-142"),
        Fact("A pixel whose projected world z is below 0.8 m or whose world y is above -0.3 m is skipped with "
             "reward 0", source="upstream_code", ref=f"{ENV}:124-131"),
        Fact("step always returns done False and an empty info dictionary, and increments step_called",
             source="upstream_code", ref=f"{ENV}:76-156"),
        Fact("reset_model is called by the parent class reset method and returns an observation image",
             source="upstream_code", ref=f"{ENV}:411-412"),
        Fact("reset_model sets the seven actuated joints to [0, -1.57, 1.57, -1.57, -1.57, 0.0, 0.3]",
             source="upstream_code", ref=f"{ENV}:418"),
        Fact("reset_model randomizes 40 object joints: x in [-0.25, 0.25], y in [-0.77, -0.43], z in [1.0, 1.5] "
             "and a random unit quaternion", source="upstream_code", ref=f"{ENV}:420-430"),
        Fact("Grasper-v0 is registered with entry point gym_grasper.envs:GraspEnv", source="upstream_code",
             ref="gym_grasper/__init__.py:4-7"),
        Fact("close closes the MuJoCo environment and destroys the OpenCV windows", source="upstream_code",
             ref=f"{ENV}:479-481"),
        Fact("The README documents the default action space as 200 x 200 pixels (40000 choices) and the state as a "
             "dictionary with an RGB image and a depth image of that resolution", source="vendor_doc",
             ref="README.md:68-69"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The fake is analytic, so the
    #: level is F0; the timestep is the upstream MuJoCo timestep (2e-3 s at SCENE:19) times frame_skip 1 (ENV:47).
    fidelity = {
        "engine": "gymnasium:Grasper-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) and cap.world.seed.v1 fix the fake's occupancy grid and the fake is otherwise "
                     "deterministic, so the same seed and actions repeat a trajectory; upstream draws the 40 object "
                     "poses with numpy's global generator and Quaternion.random (GraspingEnv.py:426-430), so a seed "
                     "does not give the same scene on the two",
        },
        "timestep_ms": 2.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "analytic F0 stand-in: no MuJoCo, no rigid-body dynamics, no contacts, friction, actuators, sensors or "
            "the 40-object pile; the reward only marks a pixel of the fake's occupancy grid and ignores every "
            "controller result",
            "the fake returns 8 x 8 RGB and depth arrays where the upstream camera returns the default 200 x 200 x 3 "
            "and 200 x 200 arrays (GraspingEnv.py:31-32); the observation space advertises the real shapes",
            "no rendering, camera image, inverse kinematics, controller, move_and_grasp or wrist rotation motion; "
            "the fake's occupancy grid, density and colours are test data, marked placeholder in fake.py",
            "the upstream environment is legacy gym with mujoco_py and returns a 4-tuple from step "
            "(GraspingEnv.py:156); the fake follows that 4-tuple and returns the reset observation without an info "
            "dictionary",
            "no wall-clock pacing: realtime_factor 0, a tick is one step() call and the 2 ms timestep is the "
            "upstream MuJoCo timestep, not a measured duration",
            "the fake was never compared with the upstream environment or with a UR5 and gripper; nothing was "
            "validated on hardware",
            "reset options are accepted for the Gymnasium bridge and ignored: the upstream reset_model reads no "
            "options (GraspingEnv.py:409-477)",
            "snapshot and restore are not offered: the fake exposes no get_state or set_state",
        ],
    }
