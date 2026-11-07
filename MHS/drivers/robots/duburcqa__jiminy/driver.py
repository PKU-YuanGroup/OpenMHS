"""OpenMHS driver for gh.duburcqa/jiminy: the ``cartpole`` environment of ``gym_jiminy.envs``.

``CartPoleJiminyEnv`` is a Gymnasium environment whose physics is computed by the Jiminy engine on the toy cart-pole
URDF.  This is a ``GymnasiumDriver``: ``env_id`` names the registration and the bridge derives ``cap.world.step.v1``
(``{ticks, action}`` with a ``Discrete(3)`` action), ``cap.world.reset.v1`` (``{seed, options}``) and
``cap.world.seed.v1`` (``{seed}``) from the environment's spaces.  The device is simulated (R0): there is no hardware
backend, no e-stop path to a machine and no operator-required limit.

The gate cannot import the upstream package (the compiled Jiminy engine, NumPy and Gymnasium are not installed where
it runs), so ``backends`` names the package's own pure Python stand-in, ``fake.FakeCartPoleJiminyEnv``.  A backend name
that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)`` (``GymnasiumDriver.open_native``);
that path also needs ``gym_jiminy.envs`` to be imported so its ``register`` calls run, and it was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002).
Every constant and rule cites a line of the clone at the pinned commit
(accdf3629d9d8c08bb97f2905f010f1616d2168a).  This package is model-authored and unreviewed: it is checked on the fake
backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

CARTPOLE = "python/gym_jiminy/envs/gym_jiminy/envs/cartpole.py"
ENV_INIT = "python/gym_jiminy/envs/gym_jiminy/envs/__init__.py"
URDF = "data/toys_models/cartpole/cartpole.urdf"
GENERIC = "python/gym_jiminy/common/gym_jiminy/common/envs/generic.py"
SENSORS = "core/src/hardware/basic_sensors.cc"


class JiminyCartPole(GymnasiumDriver):
    device_id = "jiminy-cartpole"
    env_id = "cartpole"
    native = "gym_jiminy.envs:CartPoleJiminyEnv"
    backends = {"fake": ".fake:FakeCartPoleJiminyEnv"}
    display_name = "Jiminy CartPole (gym_jiminy)"
    vendor, model = "duburcqa", "CartPoleJiminyEnv"
    tags = ["cartpole", "classic-control", "reinforcement-learning", "simulation", "gymnasium", "jiminy"]
    facts = [
        Fact("The environment is registered as 'cartpole' with max_episode_steps=500, order_enforce=False and "
             "disable_env_checker=True", source="upstream_code", ref=f"{ENV_INIT}:31-38"),
        Fact("The environment step period STEP_DT and the controller update period CONTROL_DT are both 0.02 s",
             source="upstream_code", ref=f"{CARTPOLE}:20-23"),
        Fact("The failure thresholds are 2.4 for the cart position and 12 degrees for the pole angle",
             source="upstream_code", ref=f"{CARTPOLE}:24-27"),
        Fact("The sampling ranges of cart position, pole angle, cart velocity and pole velocity are all 0.05",
             source="upstream_code", ref=f"{CARTPOLE}:28-35"),
        Fact("The constructor's continuous flag defaults to False, so the discrete action space is selected",
             source="upstream_code", ref=f"{CARTPOLE}:82-84"),
        Fact("The two encoder sensors are 'slider' on slider_to_cart and 'pole' on cart_to_pole, attached in that "
             "order", source="upstream_code", ref=f"{CARTPOLE}:117-121"),
        Fact("The EncoderSensor fieldnames are Q and V, so its measurement matrix has a position row then a "
             "velocity row", source="upstream_code", ref=f"{SENSORS}:394"),
        Fact("The observation flattens the EncoderSensor measurement matrix with reshape((-1,))",
             source="upstream_code", ref=f"{CARTPOLE}:197-199"),
        Fact("The observation space is a Box with the symmetric position bounds [X_THRESHOLD, THETA_THRESHOLD] and "
             "the robot's velocity limit", source="upstream_code", ref=f"{CARTPOLE}:158-169"),
        Fact("The three discrete commands are -command_limit, zero and +command_limit, where command_limit is the "
             "motor effort limit", source="upstream_code", ref=f"{CARTPOLE}:131-134"),
        Fact("The action space is Discrete(len(AVAIL_CTRL)) when continuous is False", source="upstream_code",
             ref=f"{CARTPOLE}:171-180"),
        Fact("The cart motor effort limit is 10 N", source="upstream_code", ref=f"{URDF}:25"),
        Fact("The cart is 1.0 kg", source="upstream_code", ref=f"{URDF}:37-40"),
        Fact("The pole is a 0.1 kg point mass at 1.0 m from its joint", source="upstream_code", ref=f"{URDF}:59-64"),
        Fact("The simulation uses the euler_explicit integrator with dtMax = CONTROL_DT", source="upstream_code",
             ref=f"{CARTPOLE}:139-147"),
        Fact("A reset samples cart position and pole angle, then cart velocity and pole velocity, from the "
             "environment's np_random generator", source="upstream_code", ref=f"{CARTPOLE}:184-195"),
        Fact("A discrete action selects its force from AVAIL_CTRL", source="upstream_code", ref=f"{CARTPOLE}:201-208"),
        Fact("The reward is 1.0 if the episode is not terminated and 0.0 otherwise", source="upstream_code",
             ref=f"{CARTPOLE}:210-216"),
        Fact("By default has_terminated returns terminated=False and truncates when the observation is out of "
             "bounds", source="upstream_code", ref=f"{GENERIC}:1434-1464"),
        Fact("A step truncates when the observation is out of bounds or the simulation exceeds "
             "simulation_duration_max", source="upstream_code", ref=f"{GENERIC}:843-849"),
        Fact("The default simulation_duration_max is 86400 s", source="upstream_code", ref=f"{GENERIC}:125"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop neither step nor reset is accepted until "
                  "mhs.safety.reset clears the latch, and the last state stays readable")
    #: The fidelity contract of the model as deployed.  The bridge derives the engine, the determinism kind and the
    #: lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gymnasium:cartpole",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the initial state and the dynamics are deterministic, so "
                     "one implementation repeats a trajectory for the same seed and actions; this package's fake "
                     "draws initial states with Python's random.Random while upstream derives its generator from "
                     "numpy SeedSequence/SFC64, so a seed gives different trajectories on the two",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a point-mass cart-pole in pure Python, not the Jiminy engine: no contact, friction, actuator "
            "dynamics, sensor noise or rendering; it was never compared with a real gym_jiminy run",
            "the fake seeds Python random.Random; upstream's BaseJiminyEnv._initialize_seed derives a numpy "
            "SeedSequence/SFC64 state (generic.py:383-388), so one seed gives different trajectories on the two",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms (STEP_DT 0.02 s) "
            "only",
            "the registration id 'cartpole' resolves through gymnasium.make only after gym_jiminy.envs has been "
            "imported to run its register() calls; that sim path was not run here",
            "no physical device is modelled and the model was never validated against one",
            "snapshot and restore are not offered: CartPoleJiminyEnv defines no get_state/set_state",
        ],
    }
