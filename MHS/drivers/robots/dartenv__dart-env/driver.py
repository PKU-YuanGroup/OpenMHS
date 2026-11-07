"""OpenMHS driver for gh.dartenv/dart-env: the Copy-v0 algorithmic tape environment (a Gymnasium family driver).

The upstream clone is an old gym package; ``gym.envs.algorithmic.copy_:CopyEnv`` is the class the card names, and
``Copy-v0`` is its registration (``gym/envs/__init__.py:6-11``).  A GymnasiumDriver is configuration only: ``env_id``
names the environment and the bridge derives the contract from the environment's spaces.  ``cap.world.step.v1``
takes ``{ticks, action}`` with the action ``{items: [movement, write_flag, character]}``, ``cap.world.reset.v1``
takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware
backend, no e-stop path to a machine and no operator-required limit.

The gate cannot import the clone (it is a legacy gym package and package code never imports upstream code), so the
``fake`` backend is the package's own pure Python tape environment (see fake.py).  A backend name that ``backends``
does not list (``sim``) is served by ``gym.make(env_id)`` (GymnasiumDriver.open_native); that path needs the
upstream package and its numpy/six dependencies and was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
the model is an event-driven analytic tape and write head, not a physical system, so it is F0.  Every constant and
rule cites a line of the clone at the pinned commit 43e5f8c17b534e180e2340ec2ef405950ad7f542.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ALGORITHMIC = "gym/envs/algorithmic/algorithmic_env.py"
COPY_ENV = "gym/envs/algorithmic/copy_.py"
REGISTRATION = "gym/envs/__init__.py"


class DartEnvCopy(GymnasiumDriver):
    device_id = "dart-env"
    env_id = "Copy-v0"
    native = "gym.envs.algorithmic:CopyEnv"
    backends = {"fake": ".fake:FakeCopyEnv"}
    display_name = "dart-env Copy-v0 (algorithmic tape world)"
    vendor, model = "dartenv", "Copy-v0"
    tags = ["algorithmic", "copy", "gym", "reinforcement-learning", "simulation", "world-model"]
    #: The environment is episodic and its own time limit can be shorter than one long command sequence; the first
    #: step after a terminal flag starts the next episode instead of being refused with a precondition error.
    autoreset = True
    facts = [
        Fact("Copy-v0 is registered with entry point gym.envs.algorithmic:CopyEnv and max_episode_steps=200",
             source="upstream_code", ref=f"{REGISTRATION}:6-11"),
        Fact("The action space is a three-tuple of Discrete spaces: left or right movement, a write flag with 2 "
             "values, and a character in 0 .. base - 1", source="upstream_code", ref=f"{ALGORITHMIC}:74-80"),
        Fact("The observation space is Discrete(base + 1): the character under the read head, and the blank index "
             "base when the head is out of bounds", source="upstream_code", ref=f"{ALGORITHMIC}:81-83"),
        Fact("The movements are left and right and the read head starts at index 0", source="upstream_code",
             ref=f"{ALGORITHMIC}:244-245"),
        Fact("The observation is the input character at the read head; a position below 0 or past the tape returns "
             "the blank index base", source="upstream_code", ref=f"{ALGORITHMIC}:251-261"),
        Fact("A correct write earns +1, a wrong character earns -0.5 and ends the episode, and a step without a "
             "write earns 0", source="upstream_code", ref=f"{ALGORITHMIC}:162-188"),
        Fact("The episode also ends when the write head reaches the target length, and a step that passes the "
             "time limit earns -1 and ends the episode", source="upstream_code", ref=f"{ALGORITHMIC}:186-192"),
        Fact("The time limit is input_width + len(target) + 4 steps", source="upstream_code",
             ref=f"{ALGORITHMIC}:198-203"),
        Fact("A reset draws a tape length of randint(3) + min_length and derives the target from that tape",
             source="upstream_code", ref=f"{ALGORITHMIC}:219-230"),
        Fact("The Copy task's target is the input tape itself", source="upstream_code", ref=f"{COPY_ENV}:12-13"),
        Fact("The minimum tape length starts at 2 (AlgorithmicEnv's starting_min_length default)",
             source="upstream_code", ref=f"{ALGORITHMIC}:49"),
        Fact("The environment raises min_length by one after its promotion window and caps it at 30",
             source="upstream_code", ref=f"{ALGORITHMIC}:205-217"),
        Fact("AlgorithmicEnv.seed seeds the environment from gym.utils.seeding", source="upstream_code",
             ref=f"{ALGORITHMIC}:91-93"),
        Fact("CopyEnv's constructor defaults are base=5 and chars=True", source="upstream_code",
             ref=f"{COPY_ENV}:9"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gym:Copy-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the fake's tape; the dynamics of the tape and write "
                     "head are deterministic, so one implementation repeats a trajectory for the same seed and "
                     "actions.  This package's fake draws tapes with Python's random.Random and upstream with "
                     "numpy's RandomState (algorithmic_env.py:91-93), so one seed gives different tapes on the two",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the model is an algorithmic input tape and write head, not a physical device: no rigid-body "
            "dynamics, contacts, actuators, sensors or noise are modelled",
            "event-driven analytic model: timestep_ms 0 means no wall-clock or simulated duration advances; one "
            "step is one discrete transition, and only commands advance the world",
            "the fake draws tapes with Python's random.Random while upstream draws them with numpy's RandomState "
            "from gym.utils.seeding, so a seed does not give the same tape on the two implementations",
            "the registered TimeLimit wrapper with max_episode_steps=200 is not modelled; the environment's own "
            "time limit (input_width + len(target) + 4, at most 68 with the 30-character cap) ends an episode first",
            "the fake is a re-implementation of CopyEnv and AlgorithmicEnv and was not compared with the upstream "
            "environment, which was never imported or installed where the gate ran",
            "no rendering, PassiveEnvChecker or OrderEnforcing wrapper is modelled; the bridge serves the raw "
            "environment API",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "the bridge derives the action schema from a Tuple space without per-element limits, so the three "
            "action elements are checked by the environment's own assertion, not by the runtime envelope",
            "autoreset is enabled: after terminated or truncated, the next step starts a new episode, while the "
            "output still reports the terminal flags of the last tick",
        ],
    }
