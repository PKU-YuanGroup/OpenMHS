"""OpenMHS driver for gh.spencerfolk/rotorpy: the RotorPy ``Quadrotor-v0`` learning environment.

The card classifies the repository as the Gymnasium family, and the entry symbol is
``rotorpy.learning.quadrotor_environments:QuadrotorEnv``.  That class is a stable-baselines3 ``VecEnv`` rather than a
``gymnasium.Env``, but its ``reset``/``step`` signatures are the legacy pair the Gymnasium bridge accepts: ``reset``
returns the observation alone and ``step`` returns ``(observation, reward, dones, infos)``.  The bridge therefore
derives ``cap.world.reset.v1``, ``cap.world.seed.v1`` and ``cap.world.step.v1`` from the environment's spaces.  A
``GymnasiumDriver`` is configuration only; it has no hardware backend and no operator-required limit.

The package is checked on its own fake backend (``fake.py``), which implements one unbatched quadrotor with the
default ``cmd_vel`` action space.  The upstream environment is vectorized (``num_envs``) and its registered
constructor needs arguments that ``gymnasium.make("Quadrotor-v0")`` does not supply, so the upstream simulator was
not run here.  The fidelity contract is F0 because the fake is a kinematic stand-in, and its gaps state that.  This
package is model-authored and unreviewed; no hardware was attached.

Every Fact below cites a line of the clone at the pinned commit 40b09697a6a1596d404a67f459941d46a39eedd3.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "rotorpy/learning/quadrotor_environments.py"
REWARDS = "rotorpy/learning/quadrotor_reward_functions.py"


class QuadrotorV0(GymnasiumDriver):
    """The RotorPy ``Quadrotor-v0`` environment, served through the Gymnasium bridge on its fake backend."""

    device_id = "rotorpy-quadrotor"
    env_id = "Quadrotor-v0"
    native = "rotorpy.learning.quadrotor_environments:QuadrotorEnv"
    backends = {"fake": ".fake:FakeQuadrotorEnv"}
    display_name = "RotorPy Quadrotor-v0 (multirotor reinforcement-learning environment)"
    vendor, model = "spencerfolk", "RotorPy 3.0.0"
    tags = ["quadrotor", "uav", "multirotor", "reinforcement-learning", "simulation", "gymnasium", "rotorpy"]
    facts = [
        Fact("Quadrotor-v0 is registered to rotorpy.learning.quadrotor_environments:QuadrotorEnv",
             source="upstream_code", ref="rotorpy/learning/__init__.py:3-6"),
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
