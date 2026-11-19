"""OpenMHS driver for gh.spencerfolk/rotorpy: the RotorPy ``Quadrotor-v0`` learning environment.

The card classifies the repository as the Gymnasium family, and the entry symbol is
``rotorpy.learning.quadrotor_environments:QuadrotorEnv``.  That class is a stable-baselines3 ``VecEnv`` rather than a
``gymnasium.Env``, but its ``reset``/``step`` signatures are the legacy pair the Gymnasium bridge accepts: ``reset``
returns the observation alone and ``step`` returns ``(observation, reward, dones, infos)``.  The bridge therefore
derives ``cap.world.reset.v1``, ``cap.world.seed.v1`` and ``cap.world.step.v1`` from the environment's spaces.  A
``GymnasiumDriver`` is configuration only; it has no hardware backend and no operator-required limit.

The package is checked on its own fake backend (``fake.py``), which implements one unbatched quadrotor with the
default ``cmd_vel`` action space.  ``gymnasium.make("Quadrotor-v0")`` cannot build the upstream environment:
the id is registered only when ``rotorpy.learning`` is imported (``rotorpy/learning/__init__.py:1-6``), and
``QuadrotorEnv.__init__`` requires ``num_envs`` and ``initial_states`` (``quadrotor_environments.py:73-75``), which
that registration does not supply.  The ``sim`` backend is ``_build_sim_env``.  It constructs one drone the way
``tests/test_gymenv.py:16-25`` does, with the default ``cmd_vel`` mode, and ``_OneQuadrotor`` gives that one
environment's action the leading batch axis of the test's action (``tests/test_gymenv.py:37``) and returns that
environment's observation, reward and done flag.  The values are the upstream's.  The fidelity contract is F0
because the fake is a kinematic stand-in, and its gaps state that.  This package is model-authored and unreviewed;
no hardware was attached.  This workspace checks the fake backend.  The orchestrator runs ``--backend sim``.

Every Fact below cites a line of the clone at the pinned commit 40b09697a6a1596d404a67f459941d46a39eedd3.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "rotorpy/learning/quadrotor_environments.py"
REWARDS = "rotorpy/learning/quadrotor_reward_functions.py"
GYM_TEST = "tests/test_gymenv.py"
MULTIROTOR = "rotorpy/vehicles/multirotor.py"


def _leading(value):
    """The single environment's value when the leading axis has length 1.

    ``QuadrotorEnv`` returns observation, reward and done arrays whose first axis is ``num_envs``
    (``quadrotor_environments.py:168``, ``:372``, ``:481-487``).  With one environment that axis has length 1,
    and index 0 is that environment's value.  Any other shape is returned unchanged.
    """

    shape = getattr(value, "shape", None)
    if isinstance(shape, tuple) and shape[:1] == (1,):
        return value[0]
    return value


def _as_batch(action):
    """A flat action as a one-row batch. The action's values are unchanged.

    The bridge sends the ``cmd_vel`` space, shape ``(3,)`` (``quadrotor_environments.py:141``).  The gym test
    steps with shape ``(num_drones, n_u)`` (``tests/test_gymenv.py:37``), and ``get_cmd_motor_speeds`` indexes
    ``cmd_v`` with the environment index (``rotorpy/vehicles/multirotor.py:1027``).
    """

    shape = getattr(action, "shape", None)
    if isinstance(shape, tuple) and len(shape) == 1:
        return action.reshape((1, shape[0]))
    return action


class _OneQuadrotor:
    """One drone of ``QuadrotorEnv`` on the bridge's unbatched step contract.

    The wrapper calls the upstream ``reset`` and ``step``.  It adds the leading batch axis of one environment
    on the action and returns that environment's observation, reward, done flag and info dict.  It does not
    change those values, the control mode or the dynamics.
    """

    def __init__(self, env):
        self._env = env
        self.action_space = env.action_space
        self.observation_space = env.observation_space

    def reset(self, seed=None, options=None):
        kwargs = {}
        if seed is not None:
            kwargs["seed"] = seed
        if options is not None:
            kwargs["options"] = options
        return _leading(self._env.reset(**kwargs))

    def step(self, action):
        observation, reward, dones, infos = self._env.step(_as_batch(action))
        info = infos[0] if isinstance(infos, list) and len(infos) == 1 else infos
        return _leading(observation), _leading(reward), _leading(dones), info

    def seed(self, seed=None):
        return self._env.seed(seed)

    def close(self):
        self._env.close()


def _build_sim_env(**_options):
    """Build one real ``QuadrotorEnv`` the way ``tests/test_gymenv.py:16-25`` builds ``num_drones`` of 1.

    ``control_mode`` stays the constructor default ``cmd_vel`` (``quadrotor_environments.py:76``), so the action
    space stays ``Box(-1, 1, shape=(3,))`` (``:141``).  ``render_mode`` stays ``"None"`` (``:85``).  A figure is
    created only when ``render_mode`` is ``3D`` (``:185-188``).  The returned view is the one-environment adapter above.
    """

    import torch

    from rotorpy.learning.quadrotor_environments import QuadrotorEnv
    from rotorpy.vehicles.crazyflie_params import quad_params

    num_drones = 1
    init_rotor_speed = 1788.53  # tests/test_gymenv.py:16
    initial_states = {
        "x": torch.zeros(num_drones, 3).double(),
        "v": torch.zeros(num_drones, 3).double(),
        "q": torch.tensor([0, 0, 0, 1]).repeat(num_drones, 1).double(),
        "w": torch.zeros(num_drones, 3).double(),
        "wind": torch.zeros(num_drones, 3).double(),
        "rotor_speeds": torch.tensor(
            [init_rotor_speed, init_rotor_speed, init_rotor_speed, init_rotor_speed]
        ).repeat(num_drones, 1).double(),
    }
    env = QuadrotorEnv(num_drones, initial_states=initial_states, quad_params=quad_params, control_mode="cmd_vel")
    return _OneQuadrotor(env)


class QuadrotorV0(GymnasiumDriver):
    """The RotorPy ``Quadrotor-v0`` environment, served through the Gymnasium bridge."""

    device_id = "rotorpy-quadrotor"
    env_id = "Quadrotor-v0"
    native = "rotorpy.learning.quadrotor_environments:QuadrotorEnv"
    #: ``fake`` is this package's stand-in.  ``sim`` builds the real ``QuadrotorEnv`` (one drone, ``cmd_vel``).
    #: The sim entry is a callable, so G2 compares the lock only against the string entries.
    backends = {"fake": ".fake:FakeQuadrotorEnv", "sim": _build_sim_env}
    display_name = "RotorPy Quadrotor-v0 (multirotor reinforcement-learning environment)"
    vendor, model = "spencerfolk", "RotorPy 3.0.0"
    tags = ["quadrotor", "uav", "multirotor", "reinforcement-learning", "simulation", "gymnasium", "rotorpy"]
    facts = [
        Fact("Quadrotor-v0 is registered to rotorpy.learning.quadrotor_environments:QuadrotorEnv",
             source="upstream_code", ref="rotorpy/learning/__init__.py:3-6"),
        Fact("Importing rotorpy.learning runs that registration; the register call passes no constructor arguments",
             source="upstream_code", ref="rotorpy/learning/__init__.py:1-6"),
        Fact("QuadrotorEnv.__init__ requires num_envs and initial_states, and neither parameter has a default",
             source="upstream_code", ref=f"{ENV}:73-75"),
        Fact("The gym test builds the initial state with zero position, velocity, body rate and wind, the identity "
             "quaternion and rotor speed 1788.53, and passes that state to QuadrotorEnv",
             source="upstream_code", ref=f"{GYM_TEST}:16-25"),
        Fact("The gym test includes a one-drone run", source="upstream_code", ref=f"{GYM_TEST}:55"),
        Fact("The gym test steps with an action of shape (num_drones, n_u), and n_u is 3 for cmd_vel",
             source="upstream_code", ref=f"{GYM_TEST}:33-37"),
        Fact("get_cmd_motor_speeds indexes the cmd_vel command cmd_v with the environment index",
             source="upstream_code", ref=f"{MULTIROTOR}:1024-1027"),
        Fact("QuadrotorEnv inherits stable-baselines3's VecEnv, so it is a vectorized environment rather than a "
             "gymnasium.Env", source="upstream_code", ref=f"{ENV}:37"),
        Fact("The default control abstraction is cmd_vel", source="upstream_code", ref=f"{ENV}:76"),
        Fact("The metadata lists cmd_motor_speeds, cmd_motor_thrusts, cmd_ctbr, cmd_ctbm, cmd_vel and cmd_ctatt as "
             "the control modes", source="upstream_code", ref=f"{ENV}:71"),
        Fact("The cmd_vel action space is Box(-1, 1, shape=(3,))", source="upstream_code", ref=f"{ENV}:141"),
        Fact("Every other control mode uses Box(-1, 1, shape=(4,))", source="upstream_code", ref=f"{ENV}:143"),
        Fact("The observation space is Box(-inf, inf, shape=(13,))", source="upstream_code", ref=f"{ENV}:137"),
        Fact("The observation concatenates position (3), velocity (3), quaternion (4) and body rates (3), so it has "
             "13 values", source="upstream_code", ref=f"{ENV}:481-487"),
        Fact("The default simulation rate is 100 Hz", source="upstream_code", ref=f"{ENV}:83"),
        Fact("The simulation step is 1/sim_rate", source="upstream_code", ref=f"{ENV}:123"),
        Fact("The default maximum session time is 10 s", source="upstream_code", ref=f"{ENV}:80"),
        Fact("A step is done when the elapsed time reaches max_time", source="upstream_code", ref=f"{ENV}:371"),
        Fact("A step is out of bounds when a velocity or body rate exceeds 100 or the position leaves the world "
             "extents", source="upstream_code", ref=f"{ENV}:450-479"),
        Fact("The default world is empty free space with bounds -4 to 4 on each axis (wbound = 4)",
             source="upstream_code", ref=f"{ENV}:170-174"),
        Fact("The cmd_vel action is rescaled to [-max_vel, max_vel]", source="upstream_code", ref=f"{ENV}:440"),
        Fact("max_vel is 4/sqrt(4)", source="upstream_code", ref=f"{ENV}:163"),
        Fact("The default reset bounds are pos_bound 2 and vel_bound 0", source="upstream_code",
             ref=f"{ENV}:23-25"),
        Fact("A reset draws position and velocity uniformly from the bounds",
             source="upstream_code", ref=f"{ENV}:216-218"),
        Fact("A reset reseeds numpy and torch when a seed is supplied", source="upstream_code",
             ref=f"{ENV}:298-300"),
        Fact("reset returns only the observation", source="upstream_code", ref=f"{ENV}:317"),
        Fact("step returns the 4-tuple (observation, reward, dones, infos)", source="upstream_code",
             ref=f"{ENV}:398"),
        Fact("The reward array has one entry per environment", source="upstream_code", ref=f"{ENV}:168"),
        Fact("dones is the logical or of the out-of-bounds flag and the time limit",
             source="upstream_code", ref=f"{ENV}:371-372"),
        Fact("The observation concatenates the batched position, velocity, quaternion and body-rate tensors",
             source="upstream_code", ref=f"{ENV}:481-487"),
        Fact("The default render_mode is None", source="upstream_code", ref=f"{ENV}:85"),
        Fact("A matplotlib figure is created when render_mode is 3D", source="upstream_code", ref=f"{ENV}:185-188"),
        Fact("reset replaces its options argument with self.reset_options", source="upstream_code",
             ref=f"{ENV}:285"),
        Fact("The default reward function is vec_hover_reward", source="upstream_code", ref=f"{ENV}:77"),
        Fact("vec_hover_reward adds a survival reward of 2, weights velocity at 0.1, body rate at 0 and action at "
             "1e-5", source="upstream_code", ref=f"{REWARDS}:56-74"),
        Fact("_minmax_scale clips a scaled command to its bounds", source="upstream_code", ref=f"{ENV}:34"),
        Fact("The multirotor dynamics are integrated with rk4", source="upstream_code", ref=f"{ENV}:133"),
    ]
    safe_state = ("the simulation stops advancing: after an e-stop no step or reset is accepted until "
                  "mhs.safety.reset clears the latch, while the last observation and tick stay readable")
    #: The model actually deployed with this package is the fake: a kinematic stand-in.  ``timestep_ms`` is the
    #: upstream default step 1/sim_rate at sim_rate = 100 Hz (quadrotor_environments.py:83 and :123); the bridge
    #: advances only by commands (lockstep) and does not pace wall-clock time.
    fidelity = {
        "engine": "rotorpy:Quadrotor-v0",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the fake's initial draw from Python's random.Random "
                     "and the kinematic update is deterministic, so one implementation repeats a trajectory for "
                     "the same seed and actions; upstream seeds numpy and torch and uses its own dynamics "
                     "(quadrotor_environments.py:298-300), so a seed does not give the same trajectory on both",
        },
        "timestep_ms": 10.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic stand-in (F0): the fake integrates the commanded velocity of the default cmd_vel mode; it "
            "does not model the upstream rigid-body dynamics, rotor thrust, motor dynamics, wind or aerodynamics, "
            "and no forces or contacts are computed",
            "the fake serves one quadrotor and collapses the upstream batch axis (num_envs); the real observation "
            "and action arrays carry that extra leading dimension",
            "the fake models only the default cmd_vel action shape (3 values); the 4-value control modes of the "
            "upstream are not modelled",
            "the fake honors the reset options argument; the upstream reset overwrites it with self.reset_options "
            "(quadrotor_environments.py:285)",
            "the fake does not auto-reset on a terminal step; upstream calls reset_idx for every done environment "
            "inside step (quadrotor_environments.py:382-390)",
            "the fake starts from Python's random.Random stream, upstream from numpy and torch, so the same seed "
            "does not produce the same trajectory on the two",
            "no wall-clock pacing: realtime_factor 0, commands alone advance simulated time by timestep_ms",
            "the bridge maps the legacy dones flag to terminated and does not surface TimeLimit.truncated from the "
            "upstream info dict",
            "no snapshot or restore: the environment exposes no get_state/set_state pair",
            "no rendering, visualization or sensor model in the fake",
        ],
    }
