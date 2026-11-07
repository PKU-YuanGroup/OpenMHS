"""OpenMHS driver for gh.jjshoots/pyflyt: the PyFlyt/QuadX-Hover-v4 simulator.

The card names a Gymnasium family driver.  A ``GymnasiumDriver`` is configuration only: ``env_id`` selects the
registered environment and the bridge derives the contract from the environment's spaces.  For
``PyFlyt/QuadX-Hover-v4`` the default action space is a four-element ``Box`` (angular-rate setpoints and thrust)
and the default observation space is a 21-element ``Box`` (angular velocity, quaternion, linear velocity, linear
position, previous action and four motor throttles).  The device is simulated (R0): there is no hardware backend, no
physical e-stop path and no operator-required limit.

The gate does not install or import PyFlyt, pybullet or numpy, so the ``fake`` backend is this package's own pure
Python stand-in for the environment (``fake.py``).  A backend name that ``backends`` does not list (``sim``) would be
served by ``gymnasium.make(env_id)`` (``GymnasiumDriver.open_native``); that path needs the upstream package and its
system dependencies and was not run here.  This package is model-authored and unreviewed; it is checked on the fake
backend only.

The ``fidelity`` attribute is the contract of the model as deployed.  It is F0 because the fake is a kinematic
stand-in, not a rigid-body contact model, and its ``gaps`` say what it does not reproduce.  The upstream defaults
and the step arithmetic are cited in ``facts`` at the pinned commit
9095d41f6fc5f07fe711346b747b4f7fd475b424.
"""

from mhs.driver import Fact, GymnasiumDriver

HOVER = "PyFlyt/gym_envs/quadx_envs/quadx_hover_env.py"
BASE = "PyFlyt/gym_envs/quadx_envs/quadx_base_env.py"
AVIARY = "PyFlyt/core/aviary.py"


class QuadXHover(GymnasiumDriver):
    device_id = "quadx-hover"
    env_id = "PyFlyt/QuadX-Hover-v4"
    native = "PyFlyt.gym_envs.quadx_envs.quadx_hover_env:QuadXHoverEnv"
    backends = {"fake": ".fake:FakeQuadXHoverEnv"}
    display_name = "PyFlyt QuadX Hover (Gymnasium environment)"
    vendor, model = "jjshoots", "PyFlyt/QuadX-Hover-v4"
    tags = ["pyflyt", "quadx", "uav", "quadrotor", "hover", "gymnasium", "simulation"]
    facts = [
        Fact("PyFlyt/QuadX-Hover-v4 is registered with entry point "
             "PyFlyt.gym_envs.quadx_envs.quadx_hover_env:QuadXHoverEnv", source="upstream_code",
             ref="PyFlyt/gym_envs/__init__.py:8-11"),
        Fact("The hover action is [vp, vq, vr, T]: angular velocity setpoints and thrust", source="upstream_code",
             ref=f"{HOVER}:15"),
        Fact("The flight-mode-0 action space is a four-element Box with low [-pi, -pi, -pi, 0.0] and high "
             "[pi, pi, pi, 0.8]", source="upstream_code", ref=f"{BASE}:80-103"),
        Fact("The quaternion attitude space has 13 elements and the combined observation space has "
             "13 + 4 + 4 = 21 elements", source="upstream_code", ref=f"{BASE}:62-115"),
        Fact("The hover observation concatenates body angular velocity (3), quaternion orientation (4), body linear "
             "velocity (3), ground linear position (3), the previous action (4) and the auxiliary state",
             source="upstream_code", ref=f"{HOVER}:96-115"),
        Fact("The Aviary state is body angular velocity, ground angular position, body linear velocity and ground "
             "linear position", source="upstream_code", ref=f"{AVIARY}:335-351"),
        Fact("The QuadX auxiliary state is the throttle of each motor", source="upstream_code",
             ref="PyFlyt/core/drones/quadx.py:536"),
        Fact("Motors.get_states returns the throttle level of each motor", source="upstream_code",
             ref="PyFlyt/core/abstractions/motors.py:97-104"),
        Fact("The hover environment defaults to flight_mode 0, flight_dome_size 3.0, max_duration_seconds 10.0, "
             "quaternion angle_representation and agent_hz 40", source="upstream_code", ref=f"{HOVER}:30-40"),
        Fact("max_steps is int(agent_hz * max_duration_seconds) and env_step_ratio is int(120 / agent_hz)",
             source="upstream_code", ref=f"{BASE}:117-123"),
        Fact("The episode truncates when step_count exceeds max_steps", source="upstream_code", ref=f"{BASE}:255-259"),
        Fact("The episode terminates with reward -100.0 when the drone touches the floor or leaves the flight dome",
             source="upstream_code", ref=f"{BASE}:261-271"),
        Fact("Each step starts with reward -0.1; the dense hover reward adds 1.0 and subtracts the distance to "
             "[0, 0, 1], the roll-pitch angle and 0.01 times the square of the yaw rate", source="upstream_code",
             ref=f"{HOVER}:117-138"),
        Fact("The base step sets reward to -0.1 before running the controllers", source="upstream_code",
             ref=f"{BASE}:283-300"),
        Fact("reset passes the seed to gymnasium.Env.reset and stabilises the Aviary for 10 steps",
             source="upstream_code", ref=f"{BASE}:152-216"),
        Fact("Aviary physics_hz defaults to 240 and physics_period is 1/physics_hz", source="upstream_code",
             ref=f"{AVIARY}:156-164"),
        Fact("Aviary.step advances updates_per_step = physics_hz / min(control_hz) physics steps",
             source="upstream_code", ref=f"{AVIARY}:287-290"),
        Fact("The QuadX control loop defaults to control_hz 120", source="upstream_code",
             ref="PyFlyt/core/drones/quadx.py:22-28"),
        Fact("The observation space is a Box with -inf/inf bounds and dtype float64", source="upstream_code",
             ref=f"{BASE}:73-115"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity).  The fake is kinematic: it integrates
    #: positions and attitudes directly, so the claim is F0 and the gaps name the missing rigid-body model.
    fidelity = {
        "engine": "PyFlyt:PyFlyt/QuadX-Hover-v4",
        "fidelity_level": "F0",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) and cap.world.seed.v1 fix the seed the environment records; the package fake "
                     "returns a fixed start state and has deterministic kinematics, so the same seed and actions "
                     "repeat a trajectory.  The upstream environment passes gymnasium's np_random Generator to the "
                     "PyBullet Aviary, and the fake does not reproduce that random stream.",
        },
        "timestep_ms": 25.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "kinematic stand-in: positions and attitudes integrate the action without rigid-body forces, contact, "
            "collision response, drag or motor thrust curves; the upstream environment is a PyBullet quadrotor "
            "model (spec 05-fidelity F0)",
            "no actuator, sensor, camera, wind or noise model; the four auxiliary values are the commanded "
            "throttle repeated, not measured motor states",
            "the fake does not reproduce the upstream numpy random stream, the Aviary stabilisation steps or the "
            "PyBullet observation values; it was never compared with a real PyFlyt run",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by the declared timestep only",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "the observation is the 21-element quaternion form; the upstream environment can also be configured "
            "with angle_representation='euler' (20 elements)",
        ],
    }
