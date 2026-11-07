"""OpenMHS driver for gh.erwincoumans/tiny-differentiable-simulator: the CartpolePyTinyDiffSim-v0 environment.

A GymnasiumDriver for the legacy Gym environment ``tds_environments.cartpole_tds_env:CartpolePyTinyDiffSim``, a
wrapper around ``pytinydiffsim.CartpoleEnv``.  The bridge derives the whole contract from the environment's spaces:
``cap.world.step.v1`` takes ``{ticks, action}`` with ``action`` ``{values: [force]}`` bounded element by element by
the one-dimensional ``Box(-10, 10)``, ``cap.world.reset.v1`` takes ``{seed, options}`` and ``cap.world.seed.v1``
``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to a machine and no
operator-required limit.

The gate cannot import the upstream package: the wrapper imports the compiled extension ``pytinydiffsim``, the legacy
``gym`` package and ``numpy`` (python/tds_environments/cartpole_tds_env.py:2-6).  Package code never imports the clone,
so the ``fake`` backend is this package's own pure Python cart-pole (fake.py).  A backend name that ``backends`` does
not list (``sim``) is served by ``gymnasium.make(env_id)`` through GymnasiumDriver.open_native (the bridge falls back to
the legacy ``gym`` package); that path needs the compiled extension and the registration side effect of
``tds_environments`` and was not run here.

The ``fidelity`` attribute is the fidelity contract of the model as deployed (spec 05-fidelity FID-002).  Every
constant and rule cites a line of the clone at the pinned commit (8381b8c9ad7f0a959548e4982eb8a63431a842d2).  This
package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENVFILE = "python/tds_environments/cartpole_tds_env.py"
REGISTRY = "python/tds_environments/__init__.py"
CXX = "examples/environments/cartpole_environment2.h"
URDF = "examples/environments/cartpole_urdf.h"


class CartpoleTinyDiffSim(GymnasiumDriver):
    device_id = "cartpole-tds"
    env_id = "CartpolePyTinyDiffSim-v0"
    native = "tds_environments.cartpole_tds_env:CartpolePyTinyDiffSim"
    backends = {"fake": ".fake:FakeCartpolePyTinyDiffSim"}
    display_name = "Tiny Differentiable Simulator CartPole (CartpolePyTinyDiffSim-v0)"
    vendor, model = "Erwin Coumans", "Tiny Differentiable Simulator"
    tags = ["cartpole", "tds", "differentiable-simulation", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("CartpolePyTinyDiffSim is registered as CartpolePyTinyDiffSim-v0 with entry point "
             "tds_environments.cartpole_tds_env:CartpolePyTinyDiffSim and max_episode_steps 200",
             source="upstream_code", ref=f"{REGISTRY}:12-17"),
        Fact("The wrapper creates pytinydiffsim.CartpoleEnv", source="upstream_code", ref=f"{ENVFILE}:14"),
        Fact("The action space is a one-dimensional Box bounded by +-force_mag, and force_mag is 10",
             source="upstream_code", ref=f"{ENVFILE}:30-35"),
        Fact("x_threshold is 0.4 and theta_threshold_radians is 12 degrees; the observation space is a four-element "
             "Box with high [x_threshold*2, float32 max, theta_threshold*2, float32 max]",
             source="upstream_code", ref=f"{ENVFILE}:19-28"),
        Fact("step passes action[0] to the wrapped environment and returns its observation with reward 1.0 and the "
             "done flag", source="upstream_code", ref=f"{ENVFILE}:65-73"),
        Fact("reset returns the wrapped environment's reset state as the observation",
             source="upstream_code", ref=f"{ENVFILE}:75-79"),
        Fact("seed masks the seed to 32 bits, seeds the wrapped environment and returns [seed]",
             source="upstream_code", ref=f"{ENVFILE}:49-55"),
        Fact("The compiled step2 returns the observation in [q0, q1, qd0, qd1] order when COMPATIBILITY is not "
             "defined", source="upstream_code", ref=f"{CXX}:221-242"),
        Fact("A reset draws every state value uniformly from -0.05 to 0.05 with std::rand",
             source="upstream_code", ref=f"{CXX}:182-192"),
        Fact("The seed method calls std::srand(s) for the wrapped environment",
             source="upstream_code", ref=f"{CXX}:216-219"),
        Fact("The simulation timestep is 1/60 s", source="upstream_code", ref=f"{CXX}:27"),
        Fact("The world gravity is (0, 0, -10)", source="upstream_code", ref=f"{CXX}:37"),
        Fact("The constructor sets action_high_ = 10 and action_low_ = -action_high_",
             source="upstream_code", ref=f"{CXX}:172-173"),
        Fact("The C++ step clips the action to action_low_ and action_high_",
             source="upstream_code", ref=f"{CXX}:285-291"),
        Fact("The C++ step sets reward 1 and done when the cart position is beyond +-0.4 or the pole angle is "
             "beyond +-12 degrees", source="upstream_code", ref=f"{CXX}:298-307"),
        Fact("The cart has mass 1 and the pole has mass 0.1 with its inertial origin at 0.5 m",
             source="upstream_code", ref=f"{URDF}:38-65"),
        Fact("The pole is a 1.0 m box with iyy 0.00835", source="upstream_code", ref=f"{URDF}:52-65"),
    ]
    safe_state = ("the simulation stops advancing: no step, reset or seed is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "tds:pytinydiffsim.CartpoleEnv",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 seeds the wrapped CartpoleEnv (cartpole_tds_env.py:49-55) "
                     "and the dynamics are deterministic, so one implementation repeats a trajectory for the same "
                     "seed and actions; the fake draws the initial state with Python's random.Random while upstream "
                     "uses C++ std::rand, so one seed gives different trajectories on the two",
        },
        "timestep_ms": 1000.0 / 60.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "analytic cart-pole stand-in: the fake integrates the four state values with the standard cart-pole "
            "equations and the URDF masses; it does not run the TDS forward dynamics, the URDF multibody, its "
            "contact simulation or the neural-network policy, and it was never compared with the upstream engine",
            "the fake draws the initial state with Python's random.Random while upstream draws it from C++ std::rand: "
            "one seed does not repeat the same trajectory on the two implementations",
            "observations are Python lists; upstream returns numpy arrays",
            "the TimeLimit wrapper that gym.make adds for CartpolePyTinyDiffSim-v0 (max_episode_steps 200) is not "
            "reproduced: the fake reports terminated only from the environment's own x and theta thresholds",
            "no rendering and no snapshot/restore are offered: the fake has no renderer and the environment exposes "
            "no get_state/set_state",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by the 1/60 s timestep only",
            "no physical device is modelled and the model was never validated against one",
        ],
    }
