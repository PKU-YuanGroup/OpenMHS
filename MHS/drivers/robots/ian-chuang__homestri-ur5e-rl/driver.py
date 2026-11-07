"""OpenMHS driver for gh.ian-chuang/homestri-ur5e-rl: the BaseRobot-v0 MuJoCo Gymnasium environment.

The upstream repository is a MuJoCo Gymnasium environment for manipulating flexible objects with a UR5e robot arm
and a Robotiq 2F-85 gripper (README.md:3, :11-13).  ``BaseRobot`` (base_robot_env.py:24) extends the repository's
``MujocoEnv``; its observation space is a 28-element unbounded float64 ``Box`` (base_robot_env.py:46) and its action
space is a 7-element ``Box`` whose elements are between -1.0 and 1.0 (base_robot_env.py:65).  It is registered as
``BaseRobot-v0`` (``homestri_ur5e_rl/__init__.py:3-6``).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the whole contract
from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action
``{values: [7 numbers]}`` bounded by the action space, ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` takes ``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path
to a machine and no operator-required limit.

The gate cannot import gymnasium, gymnasium-robotics or mujoco (setup.py:7-12), so ``backends["fake"]`` is this
package's own kinematic stand-in for ``BaseRobot`` (fake.py).  A backend name that ``backends`` does not list
(``sim``) is served by ``gymnasium.make("BaseRobot-v0")`` (GymnasiumDriver.open_native); that path needs the upstream
package and its dependencies and was not run here.

The ``fidelity`` attribute describes the model as deployed on the checked fake backend (spec 05-fidelity FID-002):
F0, because the fake is kinematic and has no MuJoCo dynamics.  The upstream environment itself uses MuJoCo with a
0.002 s timestep and a frame skip of 40, i.e. 80 ms per environment step (scene.xml:6, base_robot_env.py:37); the
fake uses the same step interval but not the engine.  Every constant and rule below cites a line of the clone at the
pinned commit 89b7e23cc5acbd9a164222fa548cb0113684523e.  This package is model-authored and unreviewed: it is
checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "homestri_ur5e_rl/envs/base_robot/base_robot_env.py"
SCENE = "homestri_ur5e_rl/envs/assets/base_robot/scene.xml"


class HomestriUR5e(GymnasiumDriver):
    device_id = "homestri-ur5e"
    env_id = "BaseRobot-v0"
    native = "homestri_ur5e_rl.envs.base_robot:BaseRobot"
    backends = {"fake": ".fake:FakeBaseRobot"}
    display_name = "homestri-ur5e-rl BaseRobot-v0 (MuJoCo simulation)"
    vendor, model = "ian-chuang", "homestri-ur5e-rl"
    tags = ["homestri", "ur5e", "robotiq-2f85", "mujoco", "gymnasium", "simulation", "reinforcement-learning"]
    facts = [
        Fact("The repository is a MuJoCo Gymnasium environment for manipulating flexible objects with a UR5e "
             "robot arm and a Robotiq 2F-85 gripper", source="vendor_doc", ref="README.md:3"),
        Fact("The repository combines a MuJoCo simulation of the arm, gripper and flexible cable with Gymnasium "
             "integration and a graphical environment view", source="vendor_doc", ref="README.md:11-13"),
        Fact("The repository declares the dependencies gymnasium-robotics, mujoco, gymnasium and pynput",
             source="upstream_code", ref="setup.py:7-12"),
        Fact("The package registers the environment id BaseRobot-v0 with entry point "
             "homestri_ur5e_rl.envs.base_robot:BaseRobot", source="upstream_code",
             ref="homestri_ur5e_rl/__init__.py:3-6"),
        Fact("BaseRobot is a subclass of the repository's MujocoEnv", source="upstream_code", ref=f"{ENV}:24"),
        Fact("The BaseRobot constructor defaults are model_path ../assets/base_robot/scene.xml and frame_skip=40",
             source="upstream_code", ref=f"{ENV}:34-40"),
        Fact("The observation space is a Box with low=-inf, high=inf, shape=(28,) and dtype float64",
             source="upstream_code", ref=f"{ENV}:46"),
        Fact("The action space is a Box with low=-1.0, high=1.0, shape=(7,) and dtype float64",
             source="upstream_code", ref=f"{ENV}:65"),
        Fact("The MuJoCo model uses the implicitfast integrator, angles in radians and a timestep of 0.002 s",
             source="upstream_code", ref=f"{SCENE}:2-6"),
        Fact("The initial joint configuration sets shoulder_lift, elbow and wrist_1 to -pi/2 and wrist_2 to pi/2",
             source="upstream_code", ref=f"{ENV}:216-223"),
        Fact("Each step runs the operational-space controller with action[:6], writes action[6] to the seventh "
             "control channel and calls do_simulation(ctrl, n_frames=1) once per frame_skip iteration",
             source="upstream_code", ref=f"{ENV}:275-296"),
        Fact("step returns the observation with reward 0.0, terminated=False, truncated=False and an empty info "
             "dictionary", source="upstream_code", ref=f"{ENV}:301-303"),
        Fact("The observation concatenates the robot qpos and qvel returned by robot_get_obs",
             source="upstream_code", ref=f"{ENV}:305-311"),
        Fact("reset_model restores init_qpos and init_qvel with set_state and returns the observation",
             source="upstream_code", ref=f"{ENV}:313-319"),
        Fact("The README states that the repository is not actively maintained and is experimental",
             source="vendor_doc", ref="README.md:27"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed on the fake backend (spec 05-fidelity section 2.1, FID-002).
    #: The step interval 80.0 ms is frame_skip 40 (base_robot_env.py:37) times the 0.002 s MuJoCo timestep
    #: (scene.xml:6); the fake reproduces that interval but not the engine.
    fidelity = {
        "engine": "gymnasium:BaseRobot-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake reset draws its start state from Python's random.Random(seed); the upstream MuJoCo "
                     "environment uses its own random generator, so one seed does not reproduce the same trajectory "
                     "on the fake and upstream",
        },
        "timestep_ms": 80.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is kinematic, not MuJoCo: it has no rigid-body dynamics, contacts, friction, "
            "actuator or sensor model, and it only integrates the seven action values into a stand-in state",
            "the upstream operational-space controller, the Robotiq 2F-85 gripper and the flexible cable are not "
            "modelled by the fake",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "the fake was not compared with the upstream environment: gymnasium, gymnasium-robotics and mujoco "
            "were not importable where the gate ran",
            "snapshot and restore are not offered: BaseRobot inherits set_state but exposes no get_state",
            "no physical UR5e is modelled and nothing was validated against hardware",
        ],
    }
