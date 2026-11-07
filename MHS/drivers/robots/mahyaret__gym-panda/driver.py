"""OpenMHS driver for gh.mahyaret/gym-panda: the PandaEnv grasping environment (a Gymnasium family driver).

The upstream registers ``panda-v0`` (``gym_panda/__init__.py:3-6``): a Franka Emika Panda in PyBullet with a
four-number action Box (hand displacement and finger target, ``panda_env.py:22``) and a five-number observation
(hand position plus two finger joints, ``panda_env.py:45-47`` and ``:65-66``).  A GymnasiumDriver is configuration
only: ``env_id`` names the environment and the bridge derives ``cap.world.step.v1`` (``action.values`` bounded by the
action space), ``cap.world.reset.v1`` and ``cap.world.seed.v1`` from it.  The device is simulated (R0): there is no
hardware backend, no e-stop path to a machine and no operator-required limit.

The gate cannot import gym, pybullet or numpy, so the ``fake`` backend is this package's pure Python kinematic
stand-in (``fake.py``).  A backend name that ``backends`` does not list (``sim``) is served by
``gym.make("panda-v0")`` (GymnasiumDriver.open_native); that path needs the upstream package (gym, pybullet, numpy)
and ``gym_panda`` imported so ``panda-v0`` is registered (``gym_panda/__init__.py:3-6``), and it was not run here.
The upstream ``reset()`` takes no seed and draws the object start from the global random module
(``panda_env.py:87``); only the fake honours a seed (see the fidelity gaps).

The ``fidelity`` attribute is the contract of the model as deployed (spec 05-fidelity FID-002): the PyBullet Panda
simulation (engine pybullet, level F1) plus the gaps that say what the checked fake does not model.  Every constant
and rule cites a line of the clone at the pinned commit 92c769fcd4d910b5913f99f96aa7cb1231a9d069.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

PANDA = "gym_panda/envs/panda_env.py"


class Panda(GymnasiumDriver):
    device_id = "gym-panda"
    env_id = "panda-v0"
    native = "gym_panda.envs:PandaEnv"
    backends = {"fake": ".fake:FakePandaEnv"}
    action_space_ref = f"{PANDA}:22"
    display_name = "gym-panda PandaEnv (PyBullet grasping)"
    vendor, model = "mahyaret", "gym-panda 0.0.6"
    tags = ["franka-panda", "pybullet", "grasping", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("PandaEnv is registered as panda-v0 with entry point gym_panda.envs:PandaEnv", source="upstream_code",
             ref="gym_panda/__init__.py:3-6"),
        Fact("The action space is a four-element Box with every element between -1 and 1", source="upstream_code",
             ref=f"{PANDA}:22"),
        Fact("The observation space is declared as a five-element Box with every element between -1 and 1",
             source="upstream_code", ref=f"{PANDA}:23"),
        Fact("A step moves the hand target by action[0], action[1] and action[2] times 0.005", source="upstream_code",
             ref=f"{PANDA}:28-31"),
        Fact("The fourth action element is the position target of finger joints 9 and 10", source="upstream_code",
             ref=f"{PANDA}:32-41"),
        Fact("The hand state is link 11 and the finger state is joints 9 and 10", source="upstream_code",
             ref=f"{PANDA}:34-47"),
        Fact("The observation is the hand position followed by the two finger positions as a float32 array",
             source="upstream_code", ref=f"{PANDA}:65-66"),
        Fact("The episode ends with reward 1 when the object is above z = 0.45, otherwise the reward is 0 and done "
             "is false", source="upstream_code", ref=f"{PANDA}:51-56"),
        Fact("MAX_EPISODE_LEN is 20*100", source="upstream_code", ref=f"{PANDA}:13"),
        Fact("A step after MAX_EPISODE_LEN ends the episode with reward 0", source="upstream_code",
             ref=f"{PANDA}:58-62"),
        Fact("A reset draws the object start uniformly in x 0.5 to 0.8 and y -0.2 to 0.2 at z = 0.05",
             source="upstream_code", ref=f"{PANDA}:87-88"),
        Fact("A reset sets gravity to -10 and loads the plane, Panda, table and tray in PyBullet", source="upstream_code",
             ref=f"{PANDA}:73-85"),
        Fact("A reset puts the seven arm joints at fixed rest poses and both fingers at 0.08", source="upstream_code",
             ref=f"{PANDA}:77-82"),
        Fact("A step calls PyBullet's stepSimulation once", source="upstream_code", ref=f"{PANDA}:43"),
        Fact("The constructor opens a PyBullet GUI", source="upstream_code", ref=f"{PANDA}:20"),
        Fact("render() returns an image with 960 columns and 720 rows", source="upstream_code",
             ref=f"{PANDA}:106-115"),
        Fact("close() disconnects the PyBullet client", source="upstream_code", ref=f"{PANDA}:121-122"),
        Fact("The README's PD example states that PyBullet's default timestep is 240 Hz", source="vendor_doc",
             ref="README.md:65"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The upstream reset() takes no options (panda_env.py:68); only the seed the fake honours is served.
    _RESET_INPUTS = {
        "seed": {"type": "integer", "minimum": 0,
                 "description": "Seed of the object-start draw; the upstream reset() takes no seed and uses the "
                                "global random module (panda_env.py:87), so only the fake repeats for a seed"},
    }
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "pybullet:panda-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake repeats a trajectory for the same seed because it draws the object start from "
                     "random.Random(seed); the upstream PandaEnv.reset() takes no seed and uses the global random "
                     "module (panda_env.py:87), so the sim backend, which was not run, does not apply the seed",
        },
        "timestep_ms": 1000.0 / 240.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "PyBullet rigid-body dynamics with contacts: a step calls stepSimulation once (panda_env.py:43) at "
            "PyBullet's default 240 Hz (README.md:65) with gravity -10 (panda_env.py:73); the URDF and PyBullet "
            "defaults are the actuator, sensor and noise model, and there is no other",
            "the checked fake backend is a kinematic stand-in: it integrates the hand target by action * 0.005, "
            "sets the finger joints directly and applies a placeholder grasp rule; it runs no PyBullet, URDF, "
            "inverse kinematics, contacts, joint limits or gravity",
            "the fake's hand start pose and grasp radius are placeholders; PyBullet computes the hand pose from the "
            "URDF and the rest joint poses (panda_env.py:77-80)",
            "the upstream reset() accepts no seed or options and draws the object start from the global random "
            "module (panda_env.py:87); the fake accepts a seed and repeats a seeded trajectory, while the sim "
            "backend was not run",
            "the upstream render() returns a 720x960 RGB image (panda_env.py:106-115); the fake has no renderer and "
            "cap.world.render.v1 stays unbound",
            "snapshot and restore are not offered: PandaEnv exposes only a private _get_state (panda_env.py:118-119) "
            "and no set_state",
            "no physical device is modelled and nothing was validated against hardware; the upstream opens a "
            "PyBullet GUI when constructed (panda_env.py:20)",
        ],
    }
