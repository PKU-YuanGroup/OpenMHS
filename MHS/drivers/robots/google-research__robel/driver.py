"""OpenMHS driver for gh.google-research/robel: the DClaw pose task as a Gymnasium family driver.

The card's ``family-config`` decision and ``GymnasiumDriver`` helper express this environment: ROBEL registers
``DClawPoseFixed-v0`` with entry point ``robel.dclaw.pose:DClawPoseFixed`` (``robel/dclaw/__init__.py:26-29``),
and the environment is a legacy gym ``RobotEnv`` with a ``Box(-1.0, 1.0, shape=(9,))`` action space
(``robel/dclaw/base_env.py:118-121``) and a flat ``Box`` observation of qpos, last_action and qpos_error
(``robel/dclaw/pose.py:33-38``).  The Gymnasium bridge derives the contract from those spaces: ``cap.world.step.v1``
takes ``{ticks, action}`` with ``action.values`` bounded per element by the normalized action space,
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` takes ``{seed}``.

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required
limit.  The gate cannot import the upstream package (it needs MuJoCo 2.1, mujoco-py, gym and numpy, and package
code never imports the clone), so the ``fake`` backend is this package's pure Python kinematic stand-in (fake.py).
A backend name that ``backends`` does not list (``sim``) is served by ``gym.make(env_id)`` after ROBEL registers its
environments (``GymnasiumDriver.open_native``); that path was not run here.

The ``fidelity`` attribute is the contract of the model as deployed: MuJoCo rigid-body dynamics with contacts,
seeded at reset, a 50 ms control interval (the 0.0025 s model timestep times the default frame_skip of 20) and
lockstep time.  The ``gaps`` say what the fake does not model.  Every fact cites a line of the clone at commit
5b0fd3704629931712c6e0f7268ace1c2154dc83.  This package is model-authored and unreviewed: it is checked on the fake
backend only, and its evidence is ``contract_checked``, never an MHS-Device level.
"""

from mhs.driver import Fact, GymnasiumDriver

POSE = "robel/dclaw/pose.py"
BASE = "robel/dclaw/base_env.py"
INIT = "robel/dclaw/__init__.py"
ROBOT_ENV = "robel/robot_env.py"
ROBOT = "robel/components/robot/robot.py"
GROUP = "robel/components/robot/group_config.py"


class DClawPoseFixed(GymnasiumDriver):
    device_id = "dclaw-pose-fixed"
    env_id = "DClawPoseFixed-v0"
    native = "robel.dclaw.pose:DClawPoseFixed"
    backends = {"fake": ".fake:FakeDClawPoseFixed"}
    action_space_ref = f"{BASE}:121"
    display_name = "ROBEL DClaw pose (DClawPoseFixed-v0)"
    vendor, model = "Google Research", "DClawPoseFixed-v0"
    risk = "R0"
    tags = ["dclaw", "pose", "manipulation", "mujoco", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("DClawPoseFixed-v0 is registered with the entry point robel.dclaw.pose:DClawPoseFixed and "
             "max_episode_steps 80", source="upstream_code", ref=f"{INIT}:23-29"),
        Fact("The DCLAW3_ASSET_PATH constant of a pose task is robel-scenes/dclaw/dclaw3xh.xml",
             source="upstream_code", ref=f"{POSE}:46"),
        Fact("The pose episode counts 80 steps of 20 simulation steps at 2.5 ms each (4 s)", source="upstream_code",
             ref=f"{INIT}:24"),
        Fact("An environment step skips 20 simulation steps by default", source="upstream_code",
             ref=f"{POSE}:52-56"),
        Fact("The DClaw group covers nine joints with position ranges -0.48 to 0.48 rad, -PI/3 to PI/3 rad and "
             "-PI/2 to PI/2 rad repeated three times, and a velocity range -2*PI/3 to 2*PI/3 rad/s",
             source="upstream_code", ref=f"{BASE}:98-106"),
        Fact("The normalized action space is a Box from -1.0 to 1.0 with one element per joint position",
             source="upstream_code", ref=f"{BASE}:118-121"),
        Fact("An action is clipped to -1.0 to 1.0 before it is applied", source="upstream_code",
             ref=f"{ROBOT_ENV}:476-486"),
        Fact("The denormalization center is the mean of the actuator range and its range is half the span of "
             "that range", source="upstream_code", ref=f"{GROUP}:160-166"),
        Fact("A normalized action is clipped to -1.0 to 1.0 and denormalized with the actuator center and range",
             source="upstream_code", ref=f"{ROBOT}:218-228"),
        Fact("A joint-position command is clipped to the qpos range and then its velocity is clipped to the "
             "qvel range", source="upstream_code", ref=f"{ROBOT}:242-261"),
        Fact("The default observation keys are qpos, last_action and qpos_error", source="upstream_code",
             ref=f"{POSE}:33-38"),
        Fact("get_obs_dict returns qpos, qvel, last_action and qpos_error, where qpos_error is the desired pose "
             "minus the current qpos", source="upstream_code", ref=f"{POSE}:98-105"),
        Fact("The flat observation is the concatenation of the selected observation arrays", source="upstream_code",
             ref=f"{ROBOT_ENV}:511-517"),
        Fact("The observation space is a Box from -inf to +inf with the observation shape", source="upstream_code",
             ref=f"{ROBOT_ENV}:425-438"),
        Fact("A reset sets last_action to None", source="upstream_code", ref=f"{ROBOT_ENV}:216"),
        Fact("When no action has been taken, the last-action observation is a zero array", source="upstream_code",
             ref=f"{ROBOT_ENV}:470-474"),
        Fact("DClawPoseFixed resets to a random initial pose and a random desired pose", source="upstream_code",
             ref=f"{POSE}:168-172"),
        Fact("A random pose clamps the upper bound of the middle joints at indices 1, 4 and 7 to 0",
             source="upstream_code", ref=f"{POSE}:148-156"),
        Fact("The pose reward is the negative norm of qpos_error minus 0.1 times the norm of the qvel entries "
             "whose absolute value is at least pi", source="upstream_code", ref=f"{POSE}:112-126"),
        Fact("The default get_done returns an all-false array, so the pose environment does not terminate by "
             "itself", source="upstream_code", ref=f"{ROBOT_ENV}:395-412"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed.  The bridge derives the engine, the determinism kind and
    #: the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "mujoco:dclaw3xh",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) seeds the environment and draws both poses from the seeded generator, so one "
                     "seed and one action sequence repeat a trajectory; upstream draws with numpy's generator "
                     "and this package's fake with Python's random.Random, so a seed gives different poses and a "
                     "different trajectory on the two",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a kinematic stand-in for MuJoCo: it moves each joint toward the normalized "
            "position target through the clipped desired velocity, resolves no contacts, actuator forces, gear "
            "friction, damping or sensor model, and the MuJoCo engine was never run here",
            "the fake draws the initial and desired poses with Python's random.Random, while upstream uses numpy's "
            "generator, so one seed gives different poses and trajectories on the two",
            "the fake does not apply the registered 80-step TimeLimit that gym.make wraps around "
            "DClawPoseFixed-v0: an episode in the fake ends only on reset",
            "the fake does not model rendering or the safety scores, and it serves the fixed-pose task only "
            "(not the random or random-dynamics variants)",
            "snapshot and restore are not offered: the fake exposes no get_state/set_state, and upstream's "
            "get_state covers only qpos/qvel, not the desired pose or the random generator",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "no physical DClaw is modelled and the model was never validated against one",
        ],
    }
