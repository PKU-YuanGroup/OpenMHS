"""OpenMHS driver for gh.farama-foundation/gymnasium-robotics: the FetchSlide-v4 environment (Gymnasium family).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the contract from
the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` where ``action`` is ``{values: [dx, dy, dz,
gripper]}`` bounded element by element by ``Box(-1.0, 1.0, (4,), float32)``; ``cap.world.reset.v1`` takes ``{seed,
options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend, no
e-stop path to a machine and no operator-required limit.

The gate cannot import the upstream package (it needs Python 3.11 or newer, MuJoCo, numpy and the MuJoCo model
assets; pyproject.toml:11 and :31-38), so the ``fake`` backend is this package's own pure Python FetchSlide stand-in
(fake.py).  A backend name that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)``
(GymnasiumDriver.open_native); that path needs the upstream package and was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
every member of ``device.schema.json`` that applies to a simulator without a physical counterpart.  Every constant
and rule cites a line of the clone at the pinned commit (b8da02a89191daf8f004e7f7510ff655f7a90100).  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

SLIDE = "gymnasium_robotics/envs/fetch/slide.py"
FETCH = "gymnasium_robotics/envs/fetch/fetch_env.py"
ROBOT = "gymnasium_robotics/envs/robot_env.py"
REGISTRY = "gymnasium_robotics/__init__.py"


class FetchSlide(GymnasiumDriver):
    device_id = "fetch-slide"
    env_id = "FetchSlide-v4"
    native = "gymnasium_robotics.envs.fetch.slide:MujocoFetchSlideEnv"
    backends = {"fake": ".fake:FakeFetchSlideEnv"}
    action_space_ref = f"{ROBOT}:87"
    display_name = "Gymnasium-Robotics FetchSlide-v4 (Fetch mobile manipulator)"
    vendor, model = "Farama Foundation", "FetchSlide-v4"
    tags = ["fetch", "fetch-slide", "mujoco", "robotics", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("FetchSlide-v4 is registered with entry point "
             "gymnasium_robotics.envs.fetch.slide:MujocoFetchSlideEnv and max_episode_steps=50",
             source="upstream_code", ref=f"{REGISTRY}:33-38"),
        Fact("The action space is Box(-1.0, 1.0, (4,), float32): the Cartesian displacement dx, dy, dz of the end "
             "effector and a gripper command", source="upstream_code", ref=f"{SLIDE}:53"),
        Fact("The action vector has four entries, created with n_actions=4",
             source="upstream_code", ref=f"{FETCH}:69"),
        Fact("The position control is scaled by 0.05 before it is applied to the simulation",
             source="upstream_code", ref=f"{FETCH}:92"),
        Fact("A control step applies the same action for 20 simulator substeps of 0.002 s, a control frequency of "
             "25 Hz (a 40 ms control step)", source="upstream_code", ref=f"{SLIDE}:49"),
        Fact("On reset the gripper starts at global (x,y,z) = [1, 0.75, 0.41] m and the robot base is fixed at "
             "[0.405, 0.48, 0]", source="upstream_code", ref=f"{SLIDE}:132"),
        Fact("The puck has a fixed height z = 0.42 m; its initial x,y offset from the gripper is drawn uniformly "
             "from [-0.1, 0.1] m until the 2D Euclidean distance is greater than 0.1 m",
             source="upstream_code", ref=f"{SLIDE}:134"),
        Fact("The target is drawn by adding an offset uniformly in [-0.3, 0.3] m to the initial gripper x,y and "
             "its height is 0.42 m", source="upstream_code", ref=f"{SLIDE}:137"),
        Fact("The constructor sets target_offset [0.4, 0, 0], target_range 0.3, obj_range 0.1 and "
             "distance_threshold 0.05", source="upstream_code", ref=f"{SLIDE}:181-184"),
        Fact("The sparse reward is -1 until the puck is within 0.05 m of the target and 0 then; the dense reward "
             "is the negative Euclidean distance", source="upstream_code", ref=f"{SLIDE}:115-117"),
        Fact("The episode is truncated at max_episode_steps (50 by default) and never terminated: the task is "
             "continuing", source="upstream_code", ref=f"{SLIDE}:142-143"),
        Fact("The observation array is 25 values of the gripper and puck state",
             source="upstream_code", ref=f"{SLIDE}:67"),
        Fact("The desired goal and the achieved goal are each a 3-dimensional array (3,) of the puck position",
             source="upstream_code", ref=f"{SLIDE}:97-105"),
        Fact("The gripper is locked in a closed configuration because the puck does not need to be grasped",
             source="upstream_code", ref=f"{SLIDE}:47"),
        Fact("The observation space is a Dict of desired_goal, achieved_goal and observation Boxes whose shapes "
             "are copied from the reset observation", source="upstream_code", ref=f"{ROBOT}:88-98"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium-robotics:FetchSlide-v4",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the initial puck and target and the fake's motion is "
                     "deterministic, so one implementation repeats a trajectory for the same seed and actions; "
                     "the fake draws with Python's random.Random while upstream uses numpy's generator, so a seed "
                     "gives different trajectories on the two",
        },
        "timestep_ms": 40.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic stand-in: no MuJoCo contact solver, friction, actuator, sensor or noise model; the puck "
            "push is a placeholder rule, so contact and sliding behaviour are not modelled",
            "the fake draws the initial puck and the target with Python's random.Random while upstream uses "
            "numpy's generator: one seed does not repeat the same trajectory on the two implementations",
            "observations are Python lists of floats; the upstream environment returns numpy arrays (float64)",
            "rendering, PassiveEnvChecker and the TimeLimit wrapper that gymnasium.make adds are not reproduced; "
            "the fake truncates at max_episode_steps=50 itself",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "no physical device is modelled and the model was never validated against one",
        ],
    }
