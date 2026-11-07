"""OpenMHS driver for gh.henrycharlesworth/dexterous-gym: the EggHandOver-v0 environment.

A ``GymnasiumDriver`` is configuration only: ``env_id`` names the registered environment and the bridge derives the
contract from the environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action
``{"values": [...]}`` bounded by the environment's ``Box(-1, 1, shape=(40,))``, ``cap.world.reset.v1`` takes
``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware
backend, no e-stop path to a machine and no operator-required limit.

The upstream environment is old Gym 0.15.3 plus MuJoCo 2.0 (README.md:4-15); neither is installed where the gate
runs and package code never imports the clone.  The ``fake`` backend is therefore the package's own pure Python
stand-in for the registered ``EggHandOver-v0``.  A backend name that ``backends`` does not list (``sim``) is served by
``gym.make(env_id)``; that path needs the upstream stack and was not run here.

The ``fidelity`` attribute is the fidelity contract of the model as deployed (spec 05-fidelity FID-002): the fake is
an analytic kinematic stand-in, not the MuJoCo model.  Every fact cites a line of the clone at the pinned commit
dd047ad7f47ba78e2a4e2642e39bc0c0b778e594.  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

REGISTRY = "dexterous_gym/__init__.py"
ENV = "dexterous_gym/envs/egg_hand_over.py"
CORE = "dexterous_gym/core/two_hands_env.py"
ROBOT = "dexterous_gym/core/two_hand_robot_env.py"
MODEL = "dexterous_gym/envs/hand/egg_handover.xml"


class EggHandOver(GymnasiumDriver):
    device_id = "dexterous-egg-handover"
    env_id = "EggHandOver-v0"
    native = "dexterous_gym.envs.egg_hand_over:EggHandOver"
    backends = {"fake": ".fake:FakeEggHandOver"}
    display_name = "Dexterous Gym EggHandOver-v0 (two fixed Shadow hands, egg handover)"
    vendor, model = "Henry Charlesworth", "dexterous-gym 0.1.6"
    tags = ["dexterous-gym", "hand-manipulation", "mujoco", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("EggHandOver-v0 is registered with entry point dexterous_gym.envs.egg_hand_over:EggHandOver, "
             "max_episode_steps 75 and reward_type 'dense'", source="upstream_code", ref=f"{REGISTRY}:6-11"),
        Fact("The EggHandOver model file is dexterous_gym/envs/hand/egg_handover.xml", source="upstream_code",
             ref=f"{ENV}:6-7"),
        Fact("EggHandOver constructs TwoHandsEnv with moving_hands False, two_objects False and target_rotation "
             "'xyz'", source="upstream_code", ref=f"{ENV}:17-20"),
        Fact("TwoHandsEnv has 40 actions when moving_hands is False and 52 when it is True", source="upstream_code",
             ref=f"{CORE}:54-57"),
        Fact("The action space is Box(-1.0, 1.0, shape=(n_actions,), dtype float32)", source="upstream_code",
             ref=f"{ROBOT}:45"),
        Fact("Each action component is mapped to the actuator control range as centre + action*range and clipped "
             "to the range", source="upstream_code", ref=f"{CORE}:67-73"),
        Fact("step clips the action, applies it, advances the simulator and returns (observation, reward, done, "
             "info) with done hard-coded False", source="upstream_code", ref=f"{ROBOT}:76-88"),
        Fact("The observation dictionary carries observation, achieved_goal and desired_goal", source="upstream_code",
             ref=f"{CORE}:261-263"),
        Fact("The achieved goal is the object's 7-element joint position and quaternion", source="upstream_code",
             ref=f"{CORE}:75-82"),
        Fact("The observation and both goal spaces are unbounded Box spaces", source="upstream_code",
             ref=f"{ROBOT}:59-63"),
        Fact("A reset restores the initial simulator state, randomises the object's orientation and runs 10 "
             "zero-action simulation steps", source="upstream_code", ref=f"{CORE}:133-165"),
        Fact("RobotEnv.reset samples a new goal and returns the observation", source="upstream_code",
             ref=f"{ROBOT}:90-102"),
        Fact("The default goal position ranges are x 0.96-1.04, y 0.81-0.89 (hand 1) or 0.60-0.68 (hand 2) and "
             "z 0.20-0.26", source="upstream_code", ref=f"{ENV}:8-9"),
        Fact("The target rotation is a uniformly random axis-angle with angle in [-pi, pi] and axis components in "
             "[-1, 1]", source="upstream_code", ref=f"{CORE}:206-209"),
        Fact("The EggHandOver default success thresholds are 0.01 m for position and 0.1 rad for rotation",
             source="upstream_code", ref=f"{ENV}:13-14"),
        Fact("The dense reward is exp(-(dist_multiplier*d_pos + d_rot)); the sparse reward is success - 1.0",
             source="upstream_code", ref=f"{ENV}:22-29"),
        Fact("The default dist_multiplier is 20.0", source="upstream_code", ref=f"{ENV}:14"),
        Fact("The simulator timestep is 0.002 s", source="upstream_code", ref=f"{MODEL}:4"),
        Fact("n_substeps defaults to 20 simulation steps per call to step", source="upstream_code",
             ref=f"{CORE}:20"),
        Fact("dt is the model timestep times the number of substeps", source="upstream_code",
             ref=f"{ROBOT}:65-67"),
        Fact("The seed is drawn with gym.utils.seeding.np_random", source="upstream_code", ref=f"{ROBOT}:72-74"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).
    fidelity = {
        "engine": "gym:EggHandOver-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the fake's Python random generator and the kinematics "
                     "are deterministic, so one implementation repeats a trajectory for the same seed and actions; "
                     "the fake and the upstream MuJoCo model do not share a random stream",
        },
        "timestep_ms": 40.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic/analytic stand-in: no rigid-body dynamics, contacts, friction, actuator, sensor or noise "
            "model; the action moves hand joint positions directly and the object is held fixed",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "the fake was never compared with the upstream MuJoCo environment (mujoco_py and gym 0.15.3 were not "
            "installed where the gate ran); trajectories and rewards differ",
            "the upstream environment is the legacy Gym API (reset returns only the observation and step returns "
            "a 4-tuple); the fake returns the Gymnasium 5-tuple and applies the registered 75-step truncation itself",
            "the observation is a plain Python list of both hands' joint positions and velocities plus the "
            "object's qpos and qvel; upstream returns float32 numpy arrays",
            "goal sampling and the initial object rotation use Python's random.Random; upstream uses gym's numpy "
            "generator",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
