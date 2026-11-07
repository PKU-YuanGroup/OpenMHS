"""OpenMHS driver for gh.stanfordvl/gibsonenv: the Gibson ``AntNavigateEnv`` gym environment.

Gibson is a simulated world, not a hardware device (README.md:3 and :11): an ant-shaped agent moves
through a PyBullet scene and returns a proprioceptive ``nonviz_sensor`` observation. The card's
helper is ``GymnasiumDriver`` and the class below supplies the family's two pieces of configuration:
``env_id`` names the environment and ``native`` is the ``AntNavigateEnv`` class of the clone. The
bridge derives ``cap.world.step.v1`` (``{ticks, action}``, the discrete index 0..16), the reset
(``{seed, options}``) and the seed (``{seed}``) from the backend's spaces.

The upstream's registered gym ids (``gibson/__init__.py:14-34``) point at the absent ``realenv``
package, so this driver names the direct environment class the README documents (README.md:404),
not a ``gym.make`` id. On a backend that ``backends`` does not list (``sim``) the bridge would call
``gym.make(env_id)``, which the clone does not register; that path was not run and is not offered.
The ``fake`` backend is the package's own pure-Python stand-in for this interface (see fake.py).

The device is simulated and R0. There is no hardware backend, no e-stop path to a machine and no
operator-required bound. The fidelity block describes the upstream model as deployed (PyBullet,
F1) and its ``gaps`` name what the fake does not reproduce. This package is model-authored and
unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ANT_ENV = "gibson/envs/ant_env.py"
LOCOMOTORS = "gibson/core/physics/robot_locomotors.py"
MODALITIES = "gibson/envs/env_modalities.py"
BASES = "gibson/envs/env_bases.py"
ROBOT_BASES = "gibson/core/physics/robot_bases.py"
SCENES = "gibson/core/physics/scene_abstract.py"
CONFIG = "examples/configs/play/play_ant_nonviz.yaml"


class GibsonAntNavigate(GymnasiumDriver):
    device_id = "gibson-ant"
    env_id = "AntNavigateEnv"
    native = "gibson.envs.ant_env:AntNavigateEnv"
    backends = {"fake": ".fake:FakeAntNavigateEnv"}
    action_space_ref = f"{LOCOMOTORS}:267"
    display_name = "Gibson AntNavigateEnv (PyBullet ant navigation)"
    vendor, model = "Stanford University", "AntNavigateEnv"
    tags = ["gibson", "ant", "navigation", "pybullet", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("Gibson is a virtual environment simulator for embodied agents, not a hardware device",
             source="vendor_doc", ref="README.md:3"),
        Fact("Gibson simulates the agent with the Bullet physics engine", source="vendor_doc",
             ref="README.md:11"),
        Fact("AntNavigateEnv is a CameraRobotEnv subclass whose constructor takes a configuration path "
             "and a GPU index", source="upstream_code", ref=f"{ANT_ENV}:26-34"),
        Fact("The documented interface is env.step(action) returning (obs, rew, env_done, info) and "
             "env.reset(); obs is a dictionary keyed by the configured output components", source="vendor_doc",
             ref="README.md:407-414"),
        Fact("The play_ant_nonviz configuration sets is_discrete: true and output: [nonviz_sensor]",
             source="upstream_code", ref=f"{CONFIG}:8-24"),
        Fact("The play_ant_nonviz configuration sets the simulation timestep to 0.01 s with frameskip 1",
             source="upstream_code", ref=f"{CONFIG}:27-29"),
        Fact("With is_discrete true the Ant action space is gym.spaces.Discrete(17)",
             source="upstream_code", ref=f"{LOCOMOTORS}:266-267"),
        Fact("The 17 discrete Ant actions are 8 positive joint torques, 8 negative joint torques and one "
             "all-zero action", source="upstream_code", ref=f"{LOCOMOTORS}:270-286"),
        Fact("The Ant proprioceptive sensor has 28 values", source="upstream_code", ref=f"{LOCOMOTORS}:259-260"),
        Fact("calc_state concatenates eight body features, the joint state and the feet contacts and "
             "clips every element to [-5, 5]", source="upstream_code", ref=f"{LOCOMOTORS}:191-204"),
        Fact("AntNavigateEnv terminates the episode when nframe > 300", source="upstream_code",
             ref=f"{ANT_ENV}:89"),
        Fact("BaseRobotEnv._step increments nframe before applying the action and checking termination",
             source="upstream_code", ref=f"{MODALITIES}:182-189"),
        Fact("The AntNavigateEnv reward is the change in the robot potential between steps",
             source="upstream_code", ref=f"{ANT_ENV}:42-82"),
        Fact("The potential is -walk_target_dist / scene.dt", source="upstream_code",
             ref=f"{LOCOMOTORS}:206-213"),
        Fact("walk_target_dist is the planar distance from the body to the target", source="upstream_code",
             ref=f"{LOCOMOTORS}:157-160"),
        Fact("A reset restores the configured initial position and orientation and then calls "
             "robot_specific_reset", source="upstream_code", ref=f"{ROBOT_BASES}:122-131"),
        Fact("On reset the ant joint angles are drawn uniformly from (-0.1, 0.1) through np_random",
             source="upstream_code", ref=f"{LOCOMOTORS}:64-66"),
        Fact("BaseEnv seeds np_random through gym.utils.seeding.np_random", source="upstream_code",
             ref=f"{BASES}:90-92"),
        Fact("The environment uses an in-process PyBullet connection: p.connect(p.DIRECT) headless or "
             "p.GUI with a display", source="upstream_code", ref=f"{BASES}:44-51"),
        Fact("The gym ids registered in gibson/__init__.py point at realenv.envs.* entry points",
             source="upstream_code", ref="gibson/__init__.py:14-34"),
        Fact("The scene advances one physics step with frame_skip per environment step", source="upstream_code",
             ref=f"{SCENES}:47-52"),
    ]
    safe_state = ("the simulation is frozen: after a software e-stop the bridge accepts no step or reset "
                  "until mhs.safety.reset clears the latch, and the last observation stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge would derive
    #: pybullet-free defaults; they are written out so engine, level, timestep, determinism and gaps read together.
    fidelity = {
        "engine": "pybullet",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "A reset accepts a seed and the clone draws the reset joint angles from np_random "
                     "(robot_locomotors.py:64-66, seeded by env_bases.py:90-92), so one seed and one action "
                     "sequence repeat a trajectory. The package's fake uses Python's random.Random instead of "
                     "numpy's generator, so a seed repeats the fake's trajectory but not an upstream one.",
        },
        "timestep_ms": 10.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "PyBullet rigid-body dynamics and contacts are replaced in the fake by a toy integrator: joint "
            "torques, contact forces, friction and the ant's 28-value proprioceptive state are not reproduced; "
            "only the array shape, the [-5, 5] clip and the 300-frame termination are kept",
            "the camera modalities (rgb_filled, depth, normal, semantics), the CUDA point-cloud renderer and "
            "the downloaded scene database are not modelled; the package serves the nonviz_sensor configuration",
            "no wall-clock pacing: realtime_factor 0 and lockstep ticks advance simulated time by 10 ms, and "
            "the GUI display path of the upstream is not run",
            "the fake has no actuator, sensor or noise model and was never compared with the upstream "
            "environment; the sim backend needs the pinned gym 0.9.4 / pybullet 1.9.4 stack and a GPU, and was "
            "not run",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
