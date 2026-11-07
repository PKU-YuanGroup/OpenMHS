"""OpenMHS driver for gh.paddlepaddle/metagym: the ``bandits-v0`` environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives
``cap.world.step.v1`` and its limit from the environment's action space.  ``Bandits`` exposes
``spaces.Discrete(arms)`` (``metagym/bandits/bandits_env.py:21``) and ``observation_space = None``
(``:24``), so the step input is ``{"ticks", "action": {"index": 0 .. arms - 1}}``; the registered
``bandits-v0`` environment passes ``arms=50`` and ``max_steps=1000`` (``metagym/bandits/__init__.py:18-23``).
``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.

The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no
operator-required limit.  ``Bandits`` draws from numpy's global random generator rather than a
per-environment generator, so the honest determinism kind is ``statistical``; the bridge records a
supplied seed, but the class's own task and reward draws are not tied to it.

The gate environment has no gym, and package code never imports the clone or numpy, so ``backends =
{"fake": ".fake:FakeBandits"}`` is a pure Python standard-library stand-in for the upstream class.  The fake starts with a fixed
placeholder gain table because the upstream ``reset()`` raises until ``set_task`` has run; that
difference is one of the fidelity ``gaps``.  Every constant and rule cites a line of the clone at the
pinned commit ``ca724c22fd0c2ade8ec905edc688a1befdf98a3c``.  This package is model-authored and
unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

BANDITS_ENV = "metagym/bandits/bandits_env.py"
BANDITS_INIT = "metagym/bandits/__init__.py"


class Bandits(GymnasiumDriver):
    device_id = "metagym-bandits"
    env_id = "bandits-v0"
    native = "metagym.bandits:Bandits"
    backends = {"fake": ".fake:FakeBandits"}
    display_name = "MetaGym Bandits (bandits-v0)"
    vendor, model = "PaddlePaddle", "bandits-v0"
    tags = ["bandits", "meta-reinforcement-learning", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("Bandits is a gym.Env whose action space is spaces.Discrete(arms) and whose observation space is "
             "None", source="upstream_code", ref=f"{BANDITS_ENV}:12-24"),
        Fact("The constructor takes arms and max_steps and asserts that both are greater than 1",
             source="upstream_code", ref=f"{BANDITS_ENV}:13-31"),
        Fact("sample_task supports the Classical, Uniform and Gaussian distribution settings, with default "
             "mean 0.50 and dev 0.05", source="upstream_code", ref=f"{BANDITS_ENV}:33-55"),
        Fact("set_task stores task_config as exp_gains and asserts that its shape is (K,)",
             source="upstream_code", ref=f"{BANDITS_ENV}:57-60"),
        Fact("reset raises an exception unless set_task set exp_gains first; a successful reset sets steps to 0 "
             "and need_reset to False", source="upstream_code", ref=f"{BANDITS_ENV}:62-67"),
        Fact("step raises unless reset was called, indexes exp_gains by the action, draws a Bernoulli reward "
             "with that expected gain, and reports steps and expected_gain in info",
             source="upstream_code", ref=f"{BANDITS_ENV}:69-75"),
        Fact("An episode is done when steps reaches max_steps, and a done episode requires a reset before the "
             "next step", source="upstream_code", ref=f"{BANDITS_ENV}:76-78"),
        Fact("step returns the legacy Gymnasium 4-tuple (observation, reward, done, info)",
             source="upstream_code", ref=f"{BANDITS_ENV}:80"),
        Fact("expected_upperbound returns max_steps multiplied by the largest expected gain",
             source="upstream_code", ref=f"{BANDITS_ENV}:82-83"),
        Fact("The module imports numpy's global random generator", source="upstream_code",
             ref=f"{BANDITS_ENV}:7"),
        Fact("step draws its Bernoulli reward from numpy's global random generator", source="upstream_code",
             ref=f"{BANDITS_ENV}:73"),
        Fact("The class body defines __init__, reset, step, sample_task, set_task and expected_upperbound, and "
             "defines no seed method", source="upstream_code", ref=f"{BANDITS_ENV}:12-83"),
        Fact("The registered bandits-v0 environment passes arms=50 and max_steps=1000",
             source="upstream_code", ref=f"{BANDITS_INIT}:18-23"),
    ]
    safe_state = ("the simulation stops advancing: no step, reset or seed is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the gain table and step counter stay readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bandit is an
    #: analytic model: F0, no dynamics, no contact, actuator, sensor or noise model.
    fidelity_level = "F0"
    fidelity = {
        "engine": "metagym:bandits-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "statistical",
            "notes": "Bandits draws its task and Bernoulli reward from numpy's global random generator rather "
                     "than a per-environment generator; the bridge records a supplied seed, but the class's own "
                     "draws are not tied to it, so a seed does not repeat a trajectory",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "partial",
        "snapshot_restore": False,
        "gaps": [
            "analytic bandit model only: no rigid-body dynamics, contacts, actuator, sensor or noise model; "
            "a tick is one draw of a Bernoulli reward with the selected arm's expected gain",
            "no wall-clock pacing: timestep_ms 0 and realtime_factor 0, so a tick does not advance simulated "
            "time",
            "reset is partial: reset() restarts the step counter but keeps the gain table and the random "
            "stream",
            "the fake starts with a fixed placeholder gain table because the upstream reset() raises until "
            "set_task has run; the fake also uses Python's random.Random instead of numpy's global generator",
            "the fake implements only the methods Bandits itself defines; inherited gym.Env helpers (for "
            "example close, render and seed) are omitted",
            "no physical device is modelled and the model was never validated against one",
            "snapshot and restore are not offered: Bandits exposes no get_state/set_state and defines no seed "
            "method of its own",
        ],
    }
