"""OpenMHS driver for gh.learnsyslab/safe-control-gym: the CartPole environment (a Gymnasium family driver).

The upstream repository is a PyBullet/Gymnasium benchmark, not a hardware device.  ``GymnasiumDriver`` is configuration
only: ``env_id`` names the registered environment and the bridge derives the contract from the environment's spaces.
``cap.world.step.v1`` takes ``{ticks, action}`` with the action ``{values: [force]}`` bounded by the one-dimensional
``Box(-10, 10)``, ``cap.world.reset.v1`` takes ``{seed}`` and ``cap.world.seed.v1`` ``{seed}``.  The device is simulated
(R0): there is no hardware backend, no e-stop path to a machine and no operator-required limit.

The gate cannot import or run the upstream package (PyBullet, CasADi, gymnasium, numpy and matplotlib are in
``setup.py:5-31``, and package code never imports the clone), so the ``fake`` backend is the package's own pure Python
CartPole in ``fake.py``.  A backend name that ``backends`` does not list (``sim``) goes through
``gymnasium.make(env_id)`` in ``GymnasiumDriver.open_native``; that path needs the upstream package and was not run.

The ``fidelity`` attribute is the complete contract of the model as deployed (spec 05-fidelity FID-002): every member
of ``device.schema.json`` that applies to a simulator without a physical counterpart.  Every fact cites a line of the
clone at the pinned commit 6b5391d014f36fdfa0f9d22d92c77387e5274308.  This package is model-authored and unreviewed: it
is checked on the fake backend only (evidence contract_checked, never an MHS-Device level).
"""

from mhs.driver import Fact, GymnasiumDriver

CARTPOLE = "safe_control_gym/envs/gym_control/cartpole.py"
BENCHMARK = "safe_control_gym/envs/benchmark_env.py"
REGISTRATION = "safe_control_gym/envs/__init__.py"


class CartPole(GymnasiumDriver):
    device_id = "cartpole"
    env_id = "cartpole"
    native = "safe_control_gym.envs.gym_control.cartpole:CartPole"
    backends = {"fake": ".fake:FakeCartPole"}
    display_name = "Safe-Control-Gym CartPole (PyBullet)"
    vendor, model = "LearnSysLab", "safe-control-gym cartpole"
    tags = ["cartpole", "safe-control-gym", "pybullet", "reinforcement-learning", "simulation", "gymnasium"]
    facts = [
        Fact("The environment is registered under the id 'cartpole' with entry point "
             "'safe_control_gym.envs.gym_control.cartpole:CartPole'", source="upstream_code",
             ref=f"{REGISTRATION}:5-7"),
        Fact("CartPole extends BenchmarkEnv, the benchmark's base gymnasium environment", source="upstream_code",
             ref=f"{CARTPOLE}:29"),
        Fact("CartPole is a physics-based environment that uses PyBullet", source="upstream_code", ref=f"{CARTPOLE}:1-8"),
        Fact("The action space is a one-element Box with low -10 and high 10; the physical action bounds are also "
             "-10 and 10 and the action unit is N unless normalized_rl_action_space is set", source="upstream_code",
             ref=f"{CARTPOLE}:439-447"),
        Fact("A control action is denormalized when needed, disturbed, and clipped to the physical action bounds "
             "before it is applied", source="upstream_code", ref=f"{CARTPOLE}:479-500"),
        Fact("The state and observation labels are x, x_dot, theta and theta_dot with units m, m/s, rad and rad/s",
             source="upstream_code", ref=f"{CARTPOLE}:475-477"),
        Fact("The state and observation spaces are Box spaces bounded by +-4.8 for x, +-20 for x_dot, "
             "+-pi for theta and +-20 for theta_dot; the state bound is twice the failure threshold",
             source="upstream_code", ref=f"{CARTPOLE}:449-473"),
        Fact("The failure thresholds are +-2.4 for the cart position and +-90 degrees (pi/2 rad) for the pole angle",
             source="upstream_code", ref=f"{CARTPOLE}:452-454"),
        Fact("The stabilization goal tolerance is 0.05 in the state norm", source="upstream_code",
             ref=f"{CARTPOLE}:115-123"),
        Fact("The episode terminates when the cart position or the pole angle passes its threshold, or when the "
             "stabilization goal is reached", source="upstream_code", ref=f"{CARTPOLE}:654-672"),
        Fact("The default reward is the exponential of the negative quadratic state error plus an action penalty, "
             "so it lies in (0, 1]", source="upstream_code", ref=f"{CARTPOLE}:611-635"),
        Fact("The default physics and control frequencies are both 50 Hz", source="upstream_code",
             ref=f"{BENCHMARK}:64-65"),
        Fact("The control timestep is 1/ctrl_freq = 0.02 s and the physics timestep is 1/pyb_freq; the default "
             "frequencies give one physics step per control step", source="upstream_code", ref=f"{BENCHMARK}:143-145"),
        Fact("The default episode length is 5 s", source="upstream_code", ref=f"{BENCHMARK}:66"),
        Fact("after_step marks the episode done at the control-step limit and records info['TimeLimit.truncated'] "
             "when it was not already done", source="upstream_code", ref=f"{BENCHMARK}:497-501"),
        Fact("The initial state is randomized by default (randomized_init=True)", source="upstream_code",
             ref=f"{BENCHMARK}:69"),
        Fact("The initial-state randomization draws x, x_dot, theta and theta_dot uniformly from (-0.05, 0.05)",
             source="upstream_code", ref=f"{CARTPOLE}:88-112"),
        Fact("BenchmarkEnv.seed seeds numpy's generator and the action space and returns the seed",
             source="upstream_code", ref=f"{BENCHMARK}:193-214"),
        Fact("reset accepts an optional seed and passes it to before_reset, which reseeds when it is not None",
             source="upstream_code", ref=f"{CARTPOLE}:266-279"),
        Fact("step returns the legacy (observation, reward, done, info) tuple; done covers failure, goal and the "
             "time limit", source="upstream_code", ref=f"{CARTPOLE}:238-264"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop the runtime refuses step, reset and seed calls "
                  "until mhs.safety.reset clears the latch, and the last state stays readable")
    # The upstream reset takes only a seed (CartPole.reset(seed=None), cartpole.py:266); it has no options argument,
    # so the family's default {seed, options} input is narrowed to the one input the environment accepts.
    _RESET_INPUTS = {
        "seed": {"type": "integer", "minimum": 0, "description": "Seed of the environment's random generator"},
    }
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: determinism kind and lockstep clock; the whole contract is written out here so it reads in one place.
    fidelity = {
        "engine": "safe-control-gym:cartpole",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "cap.world.seed.v1 sets the seed of the next reset and cap.world.reset.v1 accepts a seed; the "
                     "dynamics are deterministic for a fixed seed and action sequence.  This package's fake draws "
                     "initial states with Python's random.Random and upstream draws them from numpy's generator, so "
                     "one seed gives different trajectories on the two",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake backend is a two-link rigid-body approximation with a force input, not PyBullet: the upstream "
            "URDF contact, damping, inertia and PyBullet solver behaviour are not modelled, and the fake was never "
            "compared with the upstream environment",
            "no actuator, sensor, noise or disturbance model: the force is an ideal clipped input and no observation "
            "or action disturbance is applied",
            "no wall-clock pacing: realtime_factor 0, so ticks advance simulated time by timestep_ms (20 ms) only",
            "no rendering, GUI, video recording, symbolic model, constraint evaluation or adversarial control",
            "snapshot and restore are not offered: the upstream environment exposes no get_state/set_state pair",
            "the fake draws initial states with Python's random.Random while upstream uses numpy's generator, and "
            "the fake returns the modern five-tuple while upstream returns the legacy four-tuple, so one seed gives "
            "different trajectories on the two",
        ],
    }
