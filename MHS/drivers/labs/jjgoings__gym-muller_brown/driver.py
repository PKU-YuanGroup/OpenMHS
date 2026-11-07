"""OpenMHS driver for gh.jjgoings/gym-muller_brown: the MullerBrownDiscrete-v0 environment (a Gymnasium family driver).

A GymnasiumDriver is configuration only: ``env_id`` names the environment and the bridge derives the contract from the
environment's spaces.  ``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{index}`` bounded by
``Discrete(5)`` (0 to 4), ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1`` ``{seed}``.  The
device is simulated (R0): no hardware backend, no e-stop path to a machine and no operator-required limit.

The upstream clone is a legacy ``gym`` environment; package code never imports it and the gate may run without
``gym``/``gymnasium``.  The ``fake`` backend is therefore the package's own pure Python re-implementation (fake.py) of
``MullerBrownDiscreteEnv``.  The card's second entry symbol, ``MullerBrownContinuousEnv``, is a separate environment
and is not served by this package.  A backend name that ``backends`` does not list (``sim``) is served by
``gymnasium.make(env_id)`` (GymnasiumDriver.open_native); that path needs the pinned upstream installed and was not
run here.

The ``fidelity`` attribute is the complete contract of the model as deployed (spec 05-fidelity FID-002).  Every fact
cites a line of the clone at the pinned commit 41467f4137008045c759a499cdcbb3aadf04f70c.  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

DISCRETE = "gym_muller_brown/envs/muller_brown_discrete.py"


class MullerBrownDiscrete(GymnasiumDriver):
    device_id = "muller-brown"
    env_id = "MullerBrownDiscrete-v0"
    native = "gym_muller_brown.envs:MullerBrownDiscreteEnv"
    backends = {"fake": ".fake:FakeMullerBrownDiscreteEnv"}
    action_space_ref = f"{DISCRETE}:18"
    display_name = "gym-muller_brown discrete Muller-Brown potential"
    vendor, model = "jjgoings", "gym-muller_brown"
    tags = ["muller-brown", "potential-energy-surface", "gridworld", "reinforcement-learning", "simulation",
            "gymnasium"]
    #: The kwargs of the registered MullerBrownDiscrete-v0 (gym_muller_brown/__init__.py:3-7); the fake also
    #: defaults to this 5 by 5 grid.
    env_kwargs = {"m": 5, "n": 5}
    facts = [
        Fact("MullerBrownDiscrete-v0 is registered with env_kwargs m=5 and n=5, so the environment opens on a 5 by 5 "
             "grid by default", source="upstream_code", ref="gym_muller_brown/__init__.py:3-7"),
        Fact("m and n are the number of grid points along the x and y axes", source="vendor_doc", ref="README.md:42"),
        Fact("The grid extent is x from -1.5 to 1 and y from -0.5 to 2", source="upstream_code",
             ref=f"{DISCRETE}:14"),
        Fact("The x and y grid coordinates are linspace over that extent with m and n points", source="upstream_code",
             ref=f"{DISCRETE}:15-16"),
        Fact("The observation space is MultiDiscrete([m, n]) and the action space is Discrete(5)", source="upstream_code",
             ref=f"{DISCRETE}:17-18"),
        Fact("Actions 0, 1, 2, 3 and 4 are up one grid point (+y), down (-y), left (-x), right (+x) and do nothing",
             source="vendor_doc", ref="README.md:71-76"),
        Fact("The action table is {0: [0, 1], 1: [0, -1], 2: [-1, 0], 3: [1, 0], 4: [0, 0]}", source="upstream_code",
             ref=f"{DISCRETE}:19"),
        Fact("The potential sums four exponential terms with A [-200, -100, -170, 15], a [-1, -1, -6.5, 0.7], "
             "b [0, 0, 11, 0.6], c [-10, -10, -6.5, 0.7], x0 [1, 0, -0.5, -1] and y0 [0, 0.5, 1.5, 1]",
             source="upstream_code", ref=f"{DISCRETE}:75-80"),
        Fact("Each term is A[k] * exp(a[k]*(x-x0[k])**2 + b[k]*(x-x0[k])*(y-y0[k]) + c[k]*(y-y0[k])**2), summed over "
             "the four terms", source="upstream_code", ref=f"{DISCRETE}:82-87"),
        Fact("An on-grid step rewards old_energy - new_energy, the decrease in potential energy", source="upstream_code",
             ref=f"{DISCRETE}:103-110"),
        Fact("An off-grid move is penalized by a reward of -100 and leaves the agent at its current position",
             source="upstream_code", ref=f"{DISCRETE}:113-115"),
        Fact("step always returns done=False: the environment has no pre-set endpoint", source="upstream_code",
             ref=f"{DISCRETE}:105"),
        Fact("reset() draws the starting state from observation_space.sample()", source="upstream_code",
             ref=f"{DISCRETE}:117-120"),
        Fact("The README describes a discretized 2-D Muller-Brown potential in a gym-compatible format, a GridWorld "
             "variant with no pre-set endpoint", source="vendor_doc", ref="README.md:7-10"),
        Fact("The README defines the potential over X = [-1.5, 1.0] and Y = [-0.5, 2.0]", source="vendor_doc",
             ref="README.md:88"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the grid state is kept and stays readable")
    fidelity_level = "F0"
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:MullerBrownDiscrete-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "the fake's reset(seed=...) seeds the observation space's Python RNG and the step rule is "
                     "deterministic, so a fresh world repeats a trajectory for the same seed and actions; the "
                     "upstream reset() takes no seed and samples an unseeded observation_space (the imported "
                     "gym.utils.seeding is unused), so seeded repeatability is a property of the fake, not of the "
                     "upstream class, and a seed does not give the same trajectory on the two",
        },
        "timestep_ms": 0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic/analytic grid world: the agent moves between the m by n grid points of an analytic "
            "Muller-Brown potential; there are no continuous dynamics, no forces, no contacts and no actuator, "
            "sensor or noise model, and timestep_ms is 0 because one tick is one grid move with no physical duration",
            "no wall-clock pacing: realtime_factor 0; only commands advance the world and ticks do not model "
            "elapsed time",
            "the fake draws the start state with a seeded Python random.Random and evaluates the energy with "
            "math.exp, while the upstream class samples numpy's observation space (unseeded) and uses numpy float "
            "arithmetic, so a seed does not repeat the same trajectory on the two and numbers can differ in the "
            "last bits",
            "render/plotPES and matplotlib are not modelled and cap.world.render.v1 is unbound; snapshot/restore "
            "are not offered because the upstream class has no get_state()/set_state() pair (its set_state() only "
            "sets the agent position)",
            "no physical device is modelled and the model was never validated against one",
        ],
    }
