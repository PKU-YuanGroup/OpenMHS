"""OpenMHS driver for gh.lachlanhurst/so100-mujoco-rl: the Env01-v1 SO-100 reaching environment.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
contract from the environment's spaces.  Env01-v1 has a six-element ``Box(-1, 1)`` action space (one increment per
joint) and a fifteen-element observation (six joint angles, the block-to-end-effector offset, the block position and
the end-effector position).  The device is simulated (R0): it has no hardware backend, no e-stop path to a machine
and no operator-required limit.

The gate cannot import the upstream package (it needs mujoco and gymnasium and Python 3.11 or newer, pyproject.toml:4,
:9 and :13), so the ``fake`` backend is the package's own pure-Python kinematic stand-in (fake.py).  On a machine with
gymnasium and mujoco installed, a backend name that ``backends`` does not list (``sim``) is served by
``gymnasium.make("Env01-v1")`` and the registered ``Env01`` class; that path was not run here.

The ``fidelity`` attribute is the contract of the model as deployed.  The upstream reset draws from numpy's global
generator (env01_v1.py:45-55), not from the environment's seeded ``np_random``, so the package declares statistical
determinism: the fake repeats a trajectory for a seed, but the upstream model does not.  Every fact cites a line of
the clone at the pinned commit (057ccecbb5c2bb06aa526714f300e801c19d3cf7).  This package is model-authored and
unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV01 = "src/so100_mujoco_rl/envs/env01_v1.py"
BASE = "src/so100_mujoco_rl/envs/env_base_01.py"
UTILS = "src/so100_mujoco_rl/envs/utils.py"
MODEL = "src/so100_mujoco_rl/envs/model/so_arm100_camera.xml"
SCENE = "src/so100_mujoco_rl/envs/model/env01.xml"


class So100Env01(GymnasiumDriver):
    device_id = "so100-env01"
    env_id = "Env01-v1"
    native = "so100_mujoco_rl.envs.env01_v1:Env01"
    backends = {"fake": ".fake:FakeEnv01"}
    display_name = "SO-100 MuJoCo Env01-v1 (reach the block)"
    vendor, model = "Lachlan Hurst", "so100-mujoco-rl Env01-v1"
    tags = ["so100", "so-arm100", "mujoco", "gymnasium", "reinforcement-learning", "robot-arm", "simulation"]
    facts = [
        Fact("Env01 is registered as Env01-v1 with max_episode_steps=4000 and reward_threshold=6000",
             source="upstream_code", ref="src/so100_mujoco_rl/__init__.py:5-10"),
        Fact("Env01 extends So100BaseEnv", source="upstream_code", ref=f"{ENV01}:10"),
        Fact("So100BaseEnv extends MujocoEnv and gymnasium.utils.EzPickle", source="upstream_code",
             ref=f"{BASE}:25"),
        Fact("The action space is a Box of six floats, each from -1.0 to 1.0", source="upstream_code",
             ref=f"{BASE}:77-83"),
        Fact("One action component scales the joint motion by JOINT_STEP_SCALE = 0.075", source="upstream_code",
             ref=f"{UTILS}:9"),
        Fact("A step adds the scaled action to each joint angle, writes the result to the position actuator ctrl and "
             "integrates the MuJoCo model frame_skip times", source="upstream_code", ref=f"{ENV01}:15-27"),
        Fact("MujocoEnv is constructed with frame_skip=16", source="upstream_code", ref=f"{BASE}:42-51"),
        Fact("The observation is fifteen numbers: six joint angles, the block-to-end-effector deltas dx, dy and dz, "
             "the block position and the end-effector position", source="upstream_code", ref=f"{BASE}:241-270"),
        Fact("The observation space bounds the six joints by the model ranges and the remaining nine values by -1 "
             "to 1 and -0.5 to 0.5", source="upstream_code", ref=f"{BASE}:63-75"),
        Fact("The joint ranges are Rotation -2.2 to 2.2, Pitch -3.14158 to 0.2, Elbow 0 to 3.14158, Wrist_Pitch "
             "-2.0 to 1.8, Wrist_Roll -3.14158 to 3.14158 and Jaw -0.2 to 2.0 radians", source="upstream_code",
             ref=f"{MODEL}:33-50"),
        Fact("The position actuators use kp=50, dampratio=1 and a force range of -35 to 35", source="upstream_code",
             ref=f"{MODEL}:31-33"),
        Fact("Reset draws the block at a distance of 0.18 to 0.42 m from the base and within 0.25*pi of -0.5*pi in "
             "angle", source="upstream_code", ref=f"{ENV01}:45-47"),
        Fact("Reset chooses one of 36 start poses from VALID_START_POSITIONS (six joint angles each)",
             source="upstream_code", ref=f"{UTILS}:13-50"),
        Fact("Reset draws from numpy's global generator (np.random.uniform and np.random.randint), not from the "
             "environment's seeded np_random", source="upstream_code", ref=f"{ENV01}:45-55"),
        Fact("Env01.step always reports terminated=False; the 4000-step TimeLimit wrapper is the only truncation",
             source="upstream_code", ref=f"{ENV01}:29-37"),
        Fact("The reward combines a block-to-end-effector distance term, joint-range penalties and previous-step "
             "positions", source="upstream_code", ref=f"{BASE}:180-239"),
        Fact("The scene attaches the so_arm100 model and adds a free-joint block_a and a floor", source="upstream_code",
             ref=f"{SCENE}:24-40"),
        Fact("Contacts between block_a and every arm body are excluded, so the arm never pushes the block",
             source="upstream_code", ref=f"{SCENE}:42-49"),
        Fact("The scene does not set a MuJoCo timestep: its option timestep line is commented out",
             source="upstream_code", ref=f"{SCENE}:3"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    fidelity_level = "F1"
    #: The contract of the model as deployed (spec 05-fidelity section 2).  ``timestep_ms`` is 16 integration steps
    #: (BASE:45) of the MuJoCo default 0.002 s because the scene does not set a timestep (SCENE:3); the derived
    #: value is written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:Env01-v1",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "statistical",
            "notes": "the upstream reset_model draws the block position and the start pose from numpy's global "
                     "generator (env01_v1.py:45-55), which gymnasium's reset(seed=...) does not seed, so the "
                     "upstream model varies run to run; the package's fake backend seeds its own stand-in with "
                     "random.Random(seed) and repeats a trajectory, but that is a property of the test data, not "
                     "of the upstream model",
        },
        "timestep_ms": 32.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a pure-Python kinematic stand-in: it models joint increments, a simple forward "
            "kinematics end effector and a distance reward, not MuJoCo rigid-body dynamics, contacts, gravity or "
            "the position actuators; it was never compared with the upstream environment (mujoco and gymnasium "
            "were not importable where the gate ran)",
            "the upstream reset uses numpy's global generator, so the same seed does not repeat a trajectory on the "
            "sim backend; seed control is a property of the fake only, and the contract is statistical",
            "contacts between block_a and every arm body are excluded (env01.xml:42-49): the block is a position "
            "indicator that the arm never pushes or grasps",
            "the fake uses six representative rows of the clone's 36 VALID_START_POSITIONS (utils.py:13-50), so its "
            "reset start poses are a subset, and its forward kinematics and reward are stand-ins",
            "no actuator, sensor or noise model is represented by the fake; the model's position actuators "
            "(kp=50, dampratio=1, forcerange -35..35) are not simulated",
            "the timestep is 32 ms from frame_skip 16 (env_base_01.py:45) times MuJoCo's default 0.002 s; the scene "
            "leaves option timestep commented out (env01.xml:3) and the upstream path was not run to measure it",
            "no rendering: Env01 renders only for a human viewer; the observation is the fifteen-number vector of "
            "_get_obs, and the Env03-Env05 offscreen camera paths are not served",
            "snapshot and restore are not offered: Env01 exposes no get_state/set_state",
        ],
    }
