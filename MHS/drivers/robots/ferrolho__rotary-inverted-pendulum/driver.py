"""OpenMHS driver for gh.ferrolho/rotary-inverted-pendulum: the MuJoCo Gymnasium environment.

The card's entry symbol is ``pendulum_env:RotaryInvertedPendulumEnv`` (``policy/pendulum_env.py:387``), a
``gymnasium.Env`` whose action space is a one-element ``Box`` bounded to ``[-1, 1]``.  This package is a
``GymnasiumDriver``: the bridge derives ``cap.world.step.v1`` (``{ticks, action}`` with ``action.values``), the
``cap.world.reset.v1`` and ``cap.world.seed.v1`` contracts from that space, and the fake backend supplies the
environment object.  The device is simulated (R0): there is no hardware backend and no operator-required bound.

The upstream environment integrates one control period as 20 physics steps of 1 ms (``policy/pendulum_env.py:343``
and ``:668-670``), so ``timing_by_backend`` declares ``physics_ticks_v1`` with a decimation of 20 and reads the clock
from the fake's ``data.time``.  A step request is therefore counted in physics ticks in multiples of 20 and the
receipt reports the verified count.

The gate cannot import gymnasium or mujoco here, so the ``fake`` backend is this package's own pure Python reduced
model (``fake.py``); it is not the upstream environment.  That path, the upstream MuJoCo model and the physical rig
were not run.  This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

PENDULUM_ENV = "policy/pendulum_env.py"
REWARD = "policy/reward.py"
MODEL_URDF = "model/model.urdf"


class RotaryInvertedPendulum(GymnasiumDriver):
    device_id = "rotary-inverted-pendulum"
    native = "pendulum_env:RotaryInvertedPendulumEnv"
    backends = {"fake": ".fake:FakeRotaryInvertedPendulumEnv"}
    #: The action space the fake copies is defined at this line of the clone (gate G4).
    action_space_ref = f"{PENDULUM_ENV}:731-733"
    display_name = "Rotary inverted pendulum (MuJoCo Gymnasium environment)"
    vendor, model = "ferrolho", "rotary-inverted-pendulum"
    tags = [
        "rotary-inverted-pendulum",
        "furuta-pendulum",
        "reinforcement-learning",
        "simulation",
        "gymnasium",
        "mujoco",
    ]
    facts = [
        Fact("The simulation class RotaryInvertedPendulumEnv subclasses gym.Env",
             source="upstream_code", ref=f"{PENDULUM_ENV}:387"),
        Fact("The action space is a Box with low -1.0 and high 1.0 and one element", source="upstream_code",
             ref=f"{PENDULUM_ENV}:731-733"),
        Fact("The constructor defaults action_mode to accel, max_accel_rad_s2 to MAX_ACCEL_RAD_S2 and "
             "max_velocity_rad_s to MAX_VELOCITY_RAD_S", source="upstream_code", ref=f"{PENDULUM_ENV}:397-406"),
        Fact("MAX_ACTION_DELTA_RAD is 0.10, CONTROL_FREQ_HZ is 50.0, MAX_VELOCITY_RAD_S is 3.5 and "
             "MAX_ACCEL_RAD_S2 is 150.0", source="upstream_code", ref=f"{PENDULUM_ENV}:146-155"),
        Fact("MOTOR_LIMIT_RAD is math.radians(135.0) and MOTOR_SAFE_LIMIT_RAD is math.radians(125.0)",
             source="upstream_code", ref=f"{PENDULUM_ENV}:66-67"),
        Fact("The MJCF option sets a 0.001 s timestep and the implicitfast integrator", source="upstream_code",
             ref=f"{PENDULUM_ENV}:343"),
        Fact("GRAVITY is 9.81", source="upstream_code", ref=f"{PENDULUM_ENV}:79"),
        Fact("The pendulum URDF inertial origin is xyz 0 0 -0.051 and its mass value is 0.014",
             source="upstream_code", ref=f"{MODEL_URDF}:119-121"),
        Fact("In accel mode the action is scaled by max_accel_rad_s2, the integrated command is clipped to "
             "max_velocity_rad_s and the position target is clipped to MOTOR_SAFE_LIMIT_RAD",
             source="upstream_code", ref=f"{PENDULUM_ENV}:1050-1077"),
        Fact("With obs_include_velocities enabled, the non-firmware observation frame is [motor_pos, sin(theta), "
             "cos(theta), motor_vel, pen_vel, prev_action]", source="upstream_code",
             ref=f"{PENDULUM_ENV}:1248-1254"),
        Fact("The default observation stacks obs_history_len = 4 frames", source="upstream_code",
             ref=f"{PENDULUM_ENV}:426"),
        Fact("theta = phi - pi, so theta = 0 is upright and the joint angle phi = 0 is hanging down",
             source="upstream_code", ref=f"{PENDULUM_ENV}:1180-1185"),
        Fact("A reset draws the motor position uniformly from plus or minus 0.7 times MOTOR_SAFE_LIMIT_RAD and, "
             "for a hanging start, the pendulum angle uniformly from -0.05 to 0.05 rad",
             source="upstream_code", ref=f"{PENDULUM_ENV}:808-817"),
        Fact("episode_length_s defaults to 8.0 s", source="upstream_code", ref=f"{PENDULUM_ENV}:406"),
        Fact("_max_steps is int(episode_length_s * control_freq_hz)",
             source="upstream_code", ref=f"{PENDULUM_ENV}:681"),
        Fact("An episode is truncated when _step_count >= _max_steps", source="upstream_code",
             ref=f"{PENDULUM_ENV}:1148"),
        Fact("The step terminates when terminate_on_hard_stop is true and abs(motor_pos) is at least "
             "MOTOR_LIMIT_RAD, subtracting hard_stop_penalty from the reward", source="upstream_code",
             ref=f"{PENDULUM_ENV}:1144-1146"),
        Fact("The reward weights are k_pen_vel 0.001, k_motor_pos 0.5, k_motor_vel 0.005 and k_action 0.20",
             source="upstream_code", ref=f"{REWARD}:27-30"),
        Fact("The quadratic cost sums theta, pendulum velocity, motor position, motor velocity, action, "
             "action_delta and motor_vel_delta squared terms, with weights on all except theta",
             source="upstream_code", ref=f"{REWARD}:94-102"),
        Fact("compute_reward returns float(alive + bonus - cost)", source="upstream_code", ref=f"{REWARD}:116"),
        Fact("The environment declares render_fps 50 in its metadata", source="upstream_code",
             ref=f"{PENDULUM_ENV}:395"),
    ]
    safe_state = ("on the fake backend the software latch refuses step, reset and seed until mhs.safety.reset; "
                  "the cached world state stays readable and releasing the latch does not advance it; "
                  "no stop of the physical rotary-pendulum rig is offered")
    #: One native step integrates control_decimation physics ticks of the declared timestep
    #: (policy/pendulum_env.py:668-670 and :1008); a reset restores the clock to zero and integrates nothing.
    timing_by_backend = {
        "fake": {
            "mode": "physics_ticks_v1",
            "control_decimation": 20,
            "physics_timestep_attr": "model.opt.timestep",
            "physics_clock_attr": "data.time",
            "native_autoreset": False,
            "reset_advances_physics": False,
            "source_refs": [f"{PENDULUM_ENV}:343", f"{PENDULUM_ENV}:668-670", f"{PENDULUM_ENV}:1008"],
        },
    }
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The engine is the package's
    #: reduced analytic model, not the upstream MuJoCo engine, and the gaps say exactly what it omits.
    fidelity = {
        "engine": "analytic:rotary-inverted-pendulum",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) fixes the fake's initial motor position and pendulum angle and the reduced model "
                     "is deterministic; the fake uses Python's random.Random while upstream uses numpy's generator, "
                     "so one seed gives different trajectories on the two.  The episode number is part of the "
                     "state hash, so a repeated trajectory must start from a fresh endpoint or a reset.",
        },
        "timestep_ms": 1.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the deployed fake is an analytic test model, without rigid-body dynamics or contacts: its toy "
            "gravity/acceleration transition is not a sourced Furuta equation and does not reproduce the MuJoCo "
            "arm/pendulum inertia coupling or the stiff PD position actuator; it therefore declares F0",
            "no contact model: the fake clamps the motor target at the 125 degree safe limit and never reaches the "
            "135 degree hard-stop termination, so the termination branch is present but not exercised",
            "no actuator, sensor or noise model: friction, the encoder quantisation, the firmware finite-difference "
            "velocity window and the observation staleness of the upstream environment are not reproduced",
            "the fake does not model the firmware boxcar action smoothing delay, transport lag or domain "
            "randomisation; their constructor defaults are accepted but the reduced model has no equivalent state",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by timestep_ms only",
            "the fake was not compared with the upstream environment (gymnasium and mujoco were not importable where "
            "the gate ran), so trajectories can differ from upstream's numpy random stream and MuJoCo state",
            "the physical rig path RealRotaryInvertedPendulumEnv in policy/real_env.py:76 uses LowLevelClient and "
            "the binary serial firmware; it is outside this fake-only package and was neither imported nor run",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
        ],
    }
