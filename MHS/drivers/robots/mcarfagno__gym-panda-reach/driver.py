"""OpenMHS driver for gh.mcarfagno/gym-panda-reach: the panda-reach-v0 environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
contract from the environment's spaces.  ``panda-reach-v0`` is a legacy Gym environment: its action space is a
``Box`` of four values in [-1, 1], so ``cap.world.step.v1`` takes ``{ticks, action: {values: [...]}}`` with one
limit per element; ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The
device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no operator-required limit.

The gate cannot run the upstream environment: ``PandaEnv.__init__`` opens a PyBullet GUI window and the package
needs pybullet, gym and a display (panda_env.py:26-29).  Package code never imports the clone, so the ``fake``
backend is the package's own pure Python kinematic stand-in (fake.py).  A backend name that ``backends`` does not
list (``sim``) is served by ``gym.make(env_id)`` through the Gymnasium bridge; that path needs the upstream package
and was not run here.

Every fact cites a line of the clone at commit 928d1e6b779b52d25bbef2a9f717bcf64991f6fb.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

PANDA = "gym_panda_reach/envs/panda_env.py"


class PandaReach(GymnasiumDriver):
    device_id = "panda-reach"
    env_id = "panda-reach-v0"
    native = "gym_panda_reach.envs:PandaEnv"
    backends = {"fake": ".fake:FakePandaEnv"}
    action_space_ref = f"{PANDA}:36"
    display_name = "gym-panda-reach panda-reach-v0 (PyBullet)"
    vendor, model = "Marcello Carfagno", "gym-panda-reach"
    tags = ["panda", "robot-arm", "reach", "reinforcement-learning", "simulation", "gymnasium", "pybullet"]
    facts = [
        Fact("panda-reach-v0 is registered with the entry point gym_panda_reach.envs:PandaEnv",
             source="upstream_code", ref="gym_panda_reach/__init__.py:3-6"),
        Fact("gym_panda_reach.envs re-exports PandaEnv from panda_env", source="upstream_code",
             ref="gym_panda_reach/envs/__init__.py:1"),
        Fact("PandaEnv is a gym.Env", source="upstream_code", ref=f"{PANDA}:20"),
        Fact("The constructor connects to PyBullet in GUI mode, so creating the environment needs pybullet and a "
             "display", source="upstream_code", ref=f"{PANDA}:26-29"),
        Fact("The action space is Box([-1, -1, -1, -1], [1, 1, 1, 1]): four continuous values from -1 to 1",
             source="upstream_code", ref=f"{PANDA}:36"),
        Fact("The observation space is declared as Box([-1] * 24, [1] * 24)", source="upstream_code",
             ref=f"{PANDA}:37"),
        Fact("Each step moves the end effector by action[0], action[1] and action[2] times dv = 0.05 in x, y and z "
             "and takes action[3] as the finger command", source="upstream_code", ref=f"{PANDA}:51-55"),
        Fact("The end effector is link 11 and its target pose is solved with calculateInverseKinematics for the "
             "incremented position with a fixed orientation", source="upstream_code", ref=f"{PANDA}:57-66"),
        Fact("Joints 0 to 6 are position-controlled at the inverse-kinematics solution and joints 9 and 10 at "
             "action[3]", source="upstream_code", ref=f"{PANDA}:68-73"),
        Fact("One step advances the simulation once with p.stepSimulation()", source="upstream_code",
             ref=f"{PANDA}:75"),
        Fact("The reach threshold is distance 0.05 between the end effector and the object; the episode is done "
             "when the distance is below it", source="upstream_code", ref=f"{PANDA}:88-95"),
        Fact("The dense reward is minus the distance; the sparse reward is -1 when the distance is above 0.05 and "
             "0 otherwise", source="upstream_code", ref=f"{PANDA}:39-45"),
        Fact("MAX_EPISODE_LEN is 20 * 100 = 2000 steps", source="upstream_code", ref=f"{PANDA}:13"),
        Fact("The episode is also done when step_counter is greater than MAX_EPISODE_LEN, so a run stops on the "
             "2001st step", source="upstream_code", ref=f"{PANDA}:97-101"),
        Fact("The observation has 24 values: grip position, object position, their difference, mean finger "
             "position, object orientation, object linear and angular velocity, commanded xyz velocity and finger "
             "velocity", source="upstream_code", ref=f"{PANDA}:120-132"),
        Fact("reset loads the Panda at base z 0.65 with the rest pose [0, -0.215, 0, -2.57, 0, 2.356, pi/4, 0, 0, "
             "0]", source="upstream_code", ref=f"{PANDA}:153-159"),
        Fact("The object starts uniformly at x in [0.5, 0.8], y in [-0.2, 0.2] and z in [0.65, 0.85]",
             source="upstream_code", ref=f"{PANDA}:201-205"),
        Fact("The goal object is loaded with useFixedBase=True, so it does not move during an episode",
             source="upstream_code", ref=f"{PANDA}:207-211"),
        Fact("The step result is the legacy 4-tuple (observation, reward, done, info)", source="upstream_code",
             ref=f"{PANDA}:134"),
        Fact("reset takes no seed or options argument", source="upstream_code", ref=f"{PANDA}:136"),
        Fact("reset returns the observation alone, not an (observation, info) pair", source="upstream_code",
             ref=f"{PANDA}:247"),
        Fact("The object position is reported in info as object_position", source="upstream_code",
             ref=f"{PANDA}:103"),
        Fact("render returns a 720 by 960 RGB array from getCameraImage", source="upstream_code",
             ref=f"{PANDA}:249-273"),
        Fact("close disconnects the PyBullet client", source="upstream_code", ref=f"{PANDA}:278-279"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed on the fake backend (spec 05-fidelity section 2): the fake
    #: is kinematic (F0), while the upstream PyBullet environment is the model it stands in for.
    fidelity = {
        "engine": "analytic:gym-panda-reach-fake",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake draws the object start from Python's random.Random(seed); the upstream reset takes "
                     "no seed and draws from the module-level random generator (panda_env.py:136,202-204), so the "
                     "seed is applied by this package's fake only, not by the PyBullet environment",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic fake: the end effector moves exactly by action * 0.05 and the object is fixed; PyBullet "
            "rigid-body dynamics, contacts, inverse kinematics and joint limits are not modelled",
            "one step() call is one control event and no simulated time is modelled, so timestep_ms is 0",
            "the upstream environment opens a PyBullet GUI in its constructor (panda_env.py:26-29) and needs "
            "pybullet, gym and a display; it was never opened or compared with this fake",
            "the upstream reset takes no seed and places the object with the module-level random generator; the "
            "seeded reset is the fake's extension",
            "the fake does not render: it has no render() and returns no image, while the upstream render() returns "
            "a 720x960 RGB array (panda_env.py:249-273)",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
