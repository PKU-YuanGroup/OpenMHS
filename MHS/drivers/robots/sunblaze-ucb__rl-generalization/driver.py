"""OpenMHS driver for gh.sunblaze-ucb/rl-generalization: the SunblazeCartPole-v0 simulation.

A GymnasiumDriver is configuration only: ``env_id`` names the environment, the ``native`` symbol is the card's entry
class, and the bridge derives the ``cap.world.*`` contract from the environment's spaces.  The environment is an old
Gym 0.10.8 environment (``classic_control.py:3`` imports Gym's CartPoleEnv; ``setup.py:42-43`` pins gym==0.10.8r1), so
the bridge's legacy paths are the ones that apply: a 4-tuple ``step`` and a bare ``reset`` return are accepted, and a
``seed`` keyword that the environment does not take falls back to ``env.seed(seed)`` before ``reset()``.

The device is a simulation: mode ``simulated``, risk R0, no hardware backend and no native stop.  The gate cannot
install or import the upstream package (gym 0.10.8r1 is pinned to Python-era dependencies that are not installed), so
the ``fake`` backend is the package's own pure Python stand-in (fake.py) and was not compared with a real run.

This package is model-authored and unreviewed.  It is checked on the fake backend only; every Fact cites a line of
the clone at commit 5e05aa108aeadd4cf21f45d56128e9da3bddc14c.
"""

from mhs.driver import Fact, GymnasiumDriver

CLASSIC = "sunblaze_envs/classic_control.py"
REGISTRATION = "sunblaze_envs/__init__.py"
PACKAGE_README = "sunblaze_envs/README.md"


class SunblazeCartPole(GymnasiumDriver):
    device_id = "sunblaze-cartpole"
    env_id = "SunblazeCartPole-v0"
    native = "sunblaze_envs.classic_control:ModifiableCartPoleEnv"
    backends = {"fake": ".fake:FakeModifiableCartPoleEnv"}
    display_name = "Sunblaze CartPole-v0 (deterministic classic control)"
    vendor, model = "UC Berkeley, Intel Labs and contributors", "SunblazeCartPole-v0"
    tags = ["cartpole", "classic-control", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("The registered entry point of SunblazeCartPole-v0 is "
             "sunblaze_envs.classic_control:ModifiableCartPoleEnv", source="upstream_code",
             ref=f"{REGISTRATION}:7-12"),
        Fact("ModifiableCartPoleEnv subclasses gym's CartPoleEnv and the package's EnvBinarySuccessMixin",
             source="upstream_code", ref=f"{CLASSIC}:30"),
        Fact("SunblazeCartPole-v0 is registered with max_episode_steps=200 and reward_threshold=195.0",
             source="upstream_code", ref=f"{REGISTRATION}:7-12"),
        Fact("EnvRegistry.make wraps an environment that has a timestep limit in "
             "sunblaze_envs.time_limit.TimeLimit", source="upstream_code",
             ref="sunblaze_envs/registration.py:126-131"),
        Fact("sunblaze_envs.make delegates to the package's own EnvRegistry", source="upstream_code",
             ref="sunblaze_envs/registration.py:166-167"),
        Fact("The package's TimeLimit resets its elapsed-step counter to 0 on reset", source="upstream_code",
             ref="sunblaze_envs/time_limit.py:7-10"),
        Fact("ModifiableCartPoleEnv.reset sets nsteps=0 and returns the parent Gym reset()", source="upstream_code",
             ref=f"{CLASSIC}:52-56"),
        Fact("ModifiableCartPoleEnv.step increments nsteps and returns the parent Gym step()", source="upstream_code",
             ref=f"{CLASSIC}:62-65"),
        Fact("is_success returns True once nsteps reaches 195, the package's definition of a balanced episode",
             source="upstream_code", ref=f"{CLASSIC}:67-76"),
        Fact("The documented deterministic CartPole parameters are force 10, length 0.5 and mass 0.1",
             source="vendor_doc", ref=f"{PACKAGE_README}:22-24"),
        Fact("The commented parent defaults recorded in the clone are gravity 9.8, masscart 1.0, masspole 0.1, "
             "length 0.5 (half the pole's length), force_mag 10.0 and tau 0.02 s between state updates",
             source="upstream_code", ref=f"{CLASSIC}:340-347"),
        Fact("CartPoleEnv is imported from gym.envs.classic_control.cartpole, so the action space, the observation "
             "bounds and the failure thresholds are Gym's and are not stated by this repository",
             source="upstream_code", ref=f"{CLASSIC}:3"),
        Fact("setup.py pins gym==0.10.8r1, the legacy Gym API the environment is built on", source="upstream_code",
             ref="setup.py:42-43"),
        Fact("The README documents sunblaze_envs.make('SunblazeCartPole-v0') as the construction path for the "
             "deterministic CartPole", source="vendor_doc", ref="README.md:55-59"),
    ]
    safe_state = ("the simulation stops advancing: no step, reset or seed is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out here so the whole contract reads in one place.
    fidelity = {
        "engine": "sunblaze:SunblazeCartPole-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "a reset seed fixes the fake's initial state and the dynamics are deterministic, so the fake "
                     "repeats a trajectory for the same seed and actions; the upstream reset takes new, not seed "
                     "(classic_control.py:52-56), and the bridge falls back to Gym's legacy seed() before reset(); "
                     "the fake uses Python's random.Random while Gym uses numpy's generator, so one seed gives "
                     "different trajectories on the two",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "rigid-body equations of motion of a cart and a pole on a frictionless track inherited from Gym; no "
            "contacts, no friction and no actuator, sensor or noise model, and the push is an ideal step force",
            "the clone states no failure thresholds, and the base class calls Gym's reset (classic_control.py:52-56); "
            "the randomized variants draw the initial state from -0.05 to 0.05 (classic_control.py:296-299), and "
            "the fake uses that spread as a placeholder together with placeholder thresholds, so its trajectories "
            "are not compared with the upstream environment",
            "the fake integrates with Python floats and random.Random, while Gym 0.10.8 uses numpy arrays and its "
            "own random generator; one seed gives different trajectories on the two",
            "the 200-step TimeLimit is re-implemented in the fake and reported through the legacy 4-tuple done flag, "
            "so the bridge marks the limit as terminated; upstream's limit is the wrapper in "
            "sunblaze_envs/time_limit.py:4-10 added by the package registry",
            "no rendering and no PassiveEnvChecker; the fake has no close() because the upstream class inherits one "
            "from Gym, which is outside the clone and was not run",
            "no wall-clock pacing: realtime_factor 0, ticks only advance simulated time by timestep_ms (tau 0.02 s)",
            "no physical device is modelled and the model was never validated against one",
            "snapshot and restore are not offered: the environment exposes no get_state/set_state",
        ],
    }
