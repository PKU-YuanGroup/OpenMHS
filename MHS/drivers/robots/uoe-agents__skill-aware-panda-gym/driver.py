"""OpenMHS driver for gh.uoe-agents/skill-aware-panda-gym: the PandaSkillAware-v3 environment.

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the whole contract
from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action derived from the
robot's action space, ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The
device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required limit.

PandaSkillAware-v3 is a PyBullet simulation of a Franka Panda that pushes, rolls or picks a cube, and
``info["state"]`` labels which skill the last step used (``README.md:27``).  The gate cannot import the upstream
stack (panda-gym, gymnasium, pybullet, numpy and scipy, ``setup.py:23``), so the ``fake`` backend is the package's
own pure Python stand-in (``fake.py``).  A backend name that ``backends`` does not list (``sim``) is served by
``gymnasium.make("PandaSkillAware-v3")`` (``GymnasiumDriver.open_native``); that path needs the upstream package and
was not run here.

The action space and the observation layout are built by panda-gym's ``Panda`` and ``RobotTaskEnv`` classes in the
external dependency; the clone imports them and does not state their dimensions or bounds, so the driver declares
no Limit and the fake's arrays are test data (see the fidelity ``gaps``).  The ``fidelity`` attribute is the
fidelity contract of the only served backend, the analytic fake (spec 05-fidelity section 2): level F0, no claim
about forces or contacts.  Every fact cites a line of the clone at the pinned commit
(4910d3733da4df60991d5cd82e839e5eb16e6b74).  This package is model-authored and unreviewed: it is checked on the
fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENVS = "skill_aware_panda_gym/envs/__init__.py"
INIT = "skill_aware_panda_gym/__init__.py"


class PandaSkillAware(GymnasiumDriver):
    device_id = "panda-skill-aware"
    env_id = "PandaSkillAware-v3"
    native = "skill_aware_panda_gym.envs:PandaPushEnv"
    backends = {"fake": ".fake:FakePandaPushEnv"}
    device_kind = "world.sim"
    mode = "simulated"
    risk = "R0"
    display_name = "Skill-aware Panda-gym PandaSkillAware-v3 (PyBullet)"
    vendor, model = "uoe-agents", "PandaSkillAware-v3"
    tags = ["panda", "franka", "push", "pybullet", "reinforcement-learning", "simulation", "gymnasium",
            "skill-aware"]
    facts = [
        Fact("The project is the modified Panda-gym benchmark for evaluating skill-aware reinforcement-learning "
             "algorithms", source="vendor_doc", ref="README.md:2"),
        Fact("The documented use is gym.make('PandaSkillAware-v3', render_mode='rgb_array', friction=1.0, mass=1.0) "
             "followed by reset() and step(action), which returns observation, reward, terminated, truncated and "
             "info", source="vendor_doc", ref="README.md:20-26"),
        Fact("info['state'] is one of push, roll, pick and down", source="vendor_doc", ref="README.md:27"),
        Fact("PandaSkillAware-v3 is registered with entry point skill_aware_panda_gym.envs:PandaPushEnv and "
             "max_episode_steps=50", source="upstream_code", ref=f"{INIT}:7-11"),
        Fact("PandaPushEnv is a RobotTaskEnv task environment", source="upstream_code", ref=f"{ENVS}:70"),
        Fact("PandaPushEnv builds PyBullet with the requested render mode and renderer and a Panda robot in that "
             "simulation, with block_gripper=False and base_position [-0.6, 0.0, 0.0]",
             source="upstream_code", ref=f"{ENVS}:107-108"),
        Fact("control_type selects end-effector control ('ee', the default) or joint control ('joints')",
             source="upstream_code", ref=f"{ENVS}:76-77"),
        Fact("friction and mass are constructor arguments that default to 1.0", source="upstream_code",
             ref=f"{ENVS}:104-105"),
        Fact("set_obs_friction_mass writes the mass to the object body with changeDynamics and the lateral friction "
             "to the table body", source="upstream_code", ref=f"{ENVS}:125-130"),
        Fact("The task wrapper's defaults are distance_threshold 0.05, goal_xy_range 0.3, goal_z_range 0.11, "
             "obj_xy_range 0.3 and object_height 1.0", source="upstream_code", ref=f"{ENVS}:24-28"),
        Fact("The environment constructs the task with the requested object_height and goal_z_range=0.0",
             source="upstream_code", ref=f"{ENVS}:109"),
        Fact("get_state labels the object 'pick' when it is above 0.021 with no table contact and both finger "
             "contacts, 'roll' when it is above 0.021 otherwise, 'push' when it is between 0.019 and 0.21, and "
             "'down' otherwise", source="upstream_code", ref=f"{ENVS}:141-153"),
        Fact("PandaPushEnv.step applies the action, advances the simulation once, sets truncated=False, and returns "
             "the five-value Gymnasium result with info['state']", source="upstream_code", ref=f"{ENVS}:155-166"),
        Fact("The installation requirements are gymnasium>=0.26, pybullet, numpy, scipy and panda-gym, with no "
             "serial, VISA or vendor-SDK dependency", source="upstream_code", ref="setup.py:23"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the only served backend, the analytic fake (spec 05-fidelity section 2).
    fidelity = {
        "engine": "python:skill_aware_panda_gym.fake:FakePandaPushEnv",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake's reset(seed=...) fixes the object and goal draws with Python's random.Random and "
                     "its step is deterministic, so one seed repeats a trajectory on this package; the upstream "
                     "reset is inherited from panda-gym's RobotTaskEnv, which is not in this clone and seeds "
                     "numpy's generator, so one seed does not give the same trajectory on the fake and upstream",
        },
        "timestep_ms": 0.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "analytic kinematics only: no rigid-body dynamics, contacts, friction, mass, actuator or sensor noise; "
            "the skill label comes from the stand-in's own geometric flags, not from PyBullet contact points",
            "the clone exposes no simulation timestep, so timestep_ms is 0: the fake advances one transition per "
            "step and makes no claim about simulated time",
            "the fake reproduces the registration's 50-step TimeLimit although the clone's own step always "
            "returns truncated=False",
            "the action space is built by panda-gym's Panda class, an external dependency that is not in this "
            "clone: the fake's Box bounds and width are test data and were not compared with an installed upstream",
            "the observation structure follows panda-gym's external RobotTaskEnv (a robot block, the task's object "
            "pose and velocity block, and the achieved and desired goals); its sizes are stand-in test data, not "
            "stated by this clone",
            "the clone defines no reset of its own and seeds nothing: the fake seeds Python's random.Random while "
            "panda-gym's RobotTaskEnv uses numpy's generator",
            "no rendering is modelled (render_mode is accepted and ignored), and snapshot/restore is not offered",
        ],
    }
