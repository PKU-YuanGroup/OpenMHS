"""OpenMHS driver for gh.ngc92/quadgym: the QuadrotorStabilizeAttitude-MotorCommands-v0 environment.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
contract from the environment object.  ``cap.world.step.v1`` takes ``{ticks, action}`` with ``action.values`` the four
motor commands bounded by the base class's ``Box(0, 1, (4,))``, ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.  The device is simulated (R0): there is no hardware backend, no e-stop path to a
machine and no operator-required limit.

The gate cannot import the upstream package (it needs the legacy ``gym`` package and numpy, ``setup.py:5``), so the
``fake`` backend is the package's own pure Python implementation of the rotational dynamics (fake.py).  A backend
name that ``backends`` does not list (``sim``) is served by ``gymnasium.make(env_id)`` or, when only the legacy ``gym``
package is installed, by that package's ``make`` after the upstream package registered the id (``__init__.py:19-23``);
that path needs both packages installed and was not run here.

The ``fidelity`` attribute is the complete contract of the model as deployed (spec 05-fidelity FID-002).  Every
constant and rule below cites a line of the clone at the pinned commit (f7eb2fecaad5fcfbf2b8a5b9ef3062b809b64b99).
This package is model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ATTITUDE = "gym_quadrotor/envs/attitude_env.py"
BASE = "gym_quadrotor/envs/base.py"
DYNAMICS = "gym_quadrotor/dynamics/dynamics.py"
COORDINATES = "gym_quadrotor/dynamics/coordinates.py"
REWARD = "gym_quadrotor/envs/reward.py"
REGISTER = "gym_quadrotor/__init__.py"


class QuadrotorAttitude(GymnasiumDriver):
    device_id = "quadrotor-attitude"
    env_id = "QuadrotorStabilizeAttitude-MotorCommands-v0"
    native = "gym_quadrotor.envs:CopterStabilizeAttitudeEnv"
    backends = {"fake": ".fake:FakeCopterStabilizeAttitudeEnv"}
    action_space_ref = f"{BASE}:18"
    display_name = "Quadgym QuadrotorStabilizeAttitude-MotorCommands-v0"
    vendor, model = "ngc92", "QuadrotorStabilizeAttitude-MotorCommands-v0"
    tags = ["quadrotor", "attitude-control", "flight-dynamics", "reinforcement-learning", "simulation", "gymnasium"]
    fidelity_level = "F1"
    facts = [
        Fact("The action space is Box(0, 1, (4,)): four motor commands between zero and one",
             source="upstream_code", ref=f"{BASE}:18"),
        Fact("The observation is [roll, pitch, wrapped yaw, roll rate, pitch rate, yaw rate] as a float array",
             source="upstream_code", ref=f"{ATTITUDE}:42-47"),
        Fact("The observation space is Box(0, 1, (6,)), which does not bound the state; the source carries a TODO "
             "to fix it", source="upstream_code", ref=f"{ATTITUDE}:8-12"),
        Fact("A step clips the action to [0, 1], sets each desired rotor speed to sqrt(action) times "
             "max_rotor_speed, integrates one 0.02 s step and returns the state, reward, done and info",
             source="upstream_code", ref=f"{BASE}:43-52"),
        Fact("The default maximum rotor speed is 500.0", source="upstream_code",
             ref="gym_quadrotor/dynamics/copter.py:19"),
        Fact("Rotor speeds approach the desired speed with gamma = 1 - 0.5**(dt / rotor_speed_half_time) and are "
             "clamped at zero", source="upstream_code", ref=f"{DYNAMICS}:86-90"),
        Fact("The default rotor_speed_half_time is 1/16 s", source="upstream_code",
             ref="gym_quadrotor/dynamics/copter.py:20"),
        Fact("The attitude reward is -angle_factor * angle_error - angvel_factor * sum(angular_velocity^2), with "
             "angle_error = pitch^2 + roll^2 + yaw^2", source="upstream_code", ref=f"{REWARD}:24-30"),
        Fact("The environment uses AttitudeReward(1.0, attitude_error_transform=np.sqrt), so the angle term is the "
             "square root of the squared angle error", source="upstream_code", ref=f"{ATTITUDE}:19"),
        Fact("The target band is 1 degree and the in-target bonus is 0.5", source="upstream_code",
             ref=f"{ATTITUDE}:16-17"),
        Fact("The bonus is added separately for roll, pitch and yaw when each absolute error is below the target",
             source="upstream_code", ref=f"{ATTITUDE}:34-39"),
        Fact("Roll and pitch are clipped at pi/4; when clipping happens the reward is reduced by the boundary "
             "penalty 1.0", source="upstream_code", ref=f"{ATTITUDE}:18-26"),
        Fact("A reset randomises roll and pitch within 20 degrees and the angular velocity within 2.0, sets yaw "
             "uniformly in [-0.3, 0.3], places the copter at altitude 1 and halves the yaw rate",
             source="upstream_code", ref=f"{ATTITUDE}:49-55"),
        Fact("The environment step never signals done: _step_copter always returns False", source="upstream_code",
             ref=f"{ATTITUDE}:29"),
        Fact("The environment id is registered with max_episode_steps=500, so gym.make wraps it in a 500-step "
             "TimeLimit", source="upstream_code", ref=f"{REGISTER}:19-23"),
        Fact("The legacy seed() calls gym.utils.seeding.np_random and returns [seed]", source="upstream_code",
             ref=f"{BASE}:39-41"),
        Fact("Body angular velocity is mapped to Euler-angle rates through the 3x3 matrix of the roll and pitch "
             "angles", source="upstream_code", ref=f"{COORDINATES}:176-180"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    fidelity = {
        "engine": "custom:gym_quadrotor attitude dynamics",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "cap.world.reset.v1 with a seed, or a seed set by cap.world.seed.v1, makes the fake repeat a "
                     "trajectory for the same actions; the fake draws initial states with Python's random.Random "
                     "and upstream with numpy's generator, so a seed gives different trajectories on the two",
        },
        "timestep_ms": 20.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "rotational rigid-body dynamics only: positions and linear velocities are not simulated (the upstream "
            "environment fixes them each step, attitude_env.py:27); there are no contacts, no aerodynamic model and "
            "no ground or collision model",
            "the rotor speeds approach the desired speed with a first-order lag (dynamics.py:86-90); no sensor or "
            "noise model is present, and the physical parameters are the upstream CopterParams defaults "
            "(copter.py:8-20)",
            "the fake backend re-implements the equations in pure Python floats and draws initial states with "
            "Python's random.Random, not numpy's generator; it was not compared with the upstream environment "
            "(gym and numpy were not installed where the gate ran), so trajectories can differ",
            "no wall-clock pacing: realtime_factor 0 and clock lockstep, so only step calls advance simulated time "
            "by the 20 ms integration step",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "the observation space is the upstream Box(0, 1, (6,)), which does not bound the actual state (the "
            "upstream TODO at attitude_env.py:8); observations are published as numbers, not checked against it",
            "the 500-step truncation comes from the registration's TimeLimit and is applied directly by the fake; "
            "the upstream TimeLimit wrapper is not present when the fake object is served",
        ],
    }
