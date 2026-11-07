"""OpenMHS driver for gh.adipandas/gym_multirotor: the QuadrotorPlusHoverEnv-v0 simulator.

A GymnasiumDriver is configuration only: ``env_id`` names the registered environment and the bridge derives the
``cap.world.*`` contract from the environment's action and observation spaces.  ``cap.world.step.v1`` takes
``{ticks, action}`` with ``action.values`` bounded by the four-motor ``Box`` action space (each element 0 to 1, taken
from the model's ``actuator_ctrlrange``), ``cap.world.reset.v1`` takes ``{seed, options}`` and
``cap.world.seed.v1`` ``{seed}``.  The device is a simulation (R0): there is no hardware backend, no e-stop path to a
machine and no operator-required limit.

The upstream environment is a gym 0.21 + mujoco_py environment (requirements.txt:4-5) with three registered variants
(gym_multirotor/__init__.py:8-25); this package serves the QuadrotorPlus variant named by the first entry symbol of
the task card.  The gate cannot import gym, mujoco_py or the clone, so the ``fake`` backend is this package's pure
Python stand-in (fake.py).  A backend name that ``backends`` does not list (``sim``) is served by
``gym.make(env_id)`` (GymnasiumDriver.open_native); that path needs the upstream stack and was not run here.

The ``fidelity`` attribute is the complete fidelity contract of the model as deployed (spec 05-fidelity FID-002):
every member of ``device.schema.json`` that applies to a simulator without a physical counterpart.  Every constant
and rule cites a line of the clone at the pinned commit (c13535254b6f6ecc84a32e49320cd989b54304d5).  This package is
model-authored and unreviewed: it is checked on the fake backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

QUADROTOR_PLUS = "gym_multirotor/envs/mujoco/quadrotor_plus_hover.py"
BASE_ENV = "gym_multirotor/envs/mujoco/base_env.py"
REGISTRATION = "gym_multirotor/__init__.py"
MODEL_XML = "gym_multirotor/envs/mujoco/assets/quadrotor_plus.xml"


class GymMultirotorQuadrotorPlus(GymnasiumDriver):
    device_id = "quadrotor-plus-hover"
    env_id = "QuadrotorPlusHoverEnv-v0"
    native = "gym_multirotor.envs.mujoco.quadrotor_plus_hover:QuadrotorPlusHoverEnv"
    backends = {"fake": ".fake:FakeQuadrotorPlusEnv"}
    action_space_ref = f"{MODEL_XML}:73-76"
    display_name = "gym_multirotor QuadrotorPlusHoverEnv-v0 (MuJoCo quadrotor)"
    vendor, model = "adipandas", "QuadrotorPlusHoverEnv-v0"
    tags = ["quadrotor", "uav", "mujoco", "hover", "reinforcement-learning", "simulation", "gym"]
    facts = [
        Fact("QuadrotorPlusHoverEnv-v0 is registered with frame_skip=5, env_bounding_box=1.2 and randomize_reset=True",
             source="upstream_code", ref=f"{REGISTRATION}:8-12"),
        Fact("The QuadrotorPlusHoverEnv constructor defaults are xml_name quadrotor_plus.xml, frame_skip 5, "
             "env_bounding_box 1.2 and randomize_reset False", source="upstream_code",
             ref=f"{QUADROTOR_PLUS}:17-18"),
        Fact("The policy action range is -1.0 to 1.0 and the safe policy range is -0.8 to 0.8",
             source="upstream_code", ref=f"{BASE_ENV}:197-203"),
        Fact("step clips the action to the policy range and maps it to motor inputs hover_force + action * 2.0 / "
             "(policy_range[1] - policy_range[0])", source="upstream_code", ref=f"{QUADROTOR_PLUS}:40-41"),
        Fact("step updates the time counter and clips the action to the policy range before the motor input is "
             "computed", source="upstream_code", ref=f"{QUADROTOR_PLUS}:59-61"),
        Fact("hover_force is mass * gravity_mag * 0.25", source="upstream_code", ref=f"{QUADROTOR_PLUS}:28"),
        Fact("The observation is an 18-value vector: the position error (3), the flattened 3x3 rotation matrix, "
             "linear velocity (3) and angular velocity (3), concatenated in that order", source="upstream_code",
             ref=f"{QUADROTOR_PLUS}:87-116"),
        Fact("The reward sums a position term (position error norm times -position_reward_constant), an orientation "
             "term, linear and angular velocity terms, an action term, the alive bonus, the goal bonus, the bound "
             "penalty and a velocity-towards-goal term, all times reward_scaling_coefficient", source="upstream_code",
             ref=f"{QUADROTOR_PLUS}:132-153"),
        Fact("The reward constants default to bonus_to_reach_goal 15.0, max_reward_for_velocity_towards_goal 2.0, "
             "position 5.0, orientation 0.02, linear velocity 0.01, angular velocity 0.001, action 0.0025, "
             "reward_for_staying_alive 5.0 and reward_scaling_coefficient 1.0", source="upstream_code",
             ref=f"{BASE_ENV}:103-111"),
        Fact("defaults are error_tolerance 0.05 and max_time_steps 1000", source="upstream_code",
             ref=f"{BASE_ENV}:92-93"),
        Fact("done is True when the observation is not finite, the position error norm is not below "
             "env_bounding_box_norm, or _time is not below max_time_steps", source="upstream_code",
             ref=f"{BASE_ENV}:493-505"),
        Fact("env_bounding_box defaults to 1.2 and is the per-axis initial position error bound", source="upstream_code",
             ref=f"{BASE_ENV}:99"),
        Fact("The desired hover position is [0, 0, 3.0]", source="upstream_code", ref=f"{BASE_ENV}:234"),
        Fact("With randomize=False the reset starts at the desired position with zero velocity; with "
             "randomize=True it draws a position offset within env_bounding_box - 0.2 of the desired position and "
             "velocities within init_max_vel and init_max_angular_vel", source="upstream_code",
             ref=f"{QUADROTOR_PLUS}:183-210"),
        Fact("The model timestep is 0.01 s and gravity is -9.81 in z", source="upstream_code", ref=f"{MODEL_XML}:8"),
        Fact("The four motors are ctrl-limited to the range 0 to 1", source="upstream_code",
             ref=f"{MODEL_XML}:73-76"),
        Fact("The README names QuadrotorPlusHoverEnv-v0, TiltrotorPlus8DofHoverEnv-v0 and QuadrotorXHoverEnv-v0 as "
             "the available environments", source="vendor_doc", ref="README.md:35-37"),
    ]
    safe_state = ("the simulation stops advancing: no step or reset is accepted after an e-stop until "
                  "mhs.safety.reset clears the latch; the environment state is kept and stays readable")
    #: The fidelity contract of the model as deployed (spec 05-fidelity section 2).  The bridge derives the engine,
    #: the determinism kind and the lockstep clock; they are written out so the whole contract reads in one place.
    fidelity = {
        "engine": "gym_multirotor:QuadrotorPlusHoverEnv-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) fixes the initial state and the fake's dynamics are deterministic, so one "
                     "implementation repeats a trajectory for the same seed and actions; the fake draws initial "
                     "states with Python's random.Random and upstream with numpy's generator, so a seed gives "
                     "different trajectories on the two",
        },
        "timestep_ms": 50.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "the fake is a damped toy model, not a MuJoCo integration of the quadrotor: it does not model contacts, "
            "thrust vectoring, rotor dynamics or the rigid-body equations, and it keeps the rotation matrix at the "
            "identity",
            "the fake's action space is a four-element Box 0 to 1 taken from the model's actuator ctrlrange; the "
            "action space inherited from gym's MuJoCo base class is outside the clone, was not available where the "
            "gate ran and was not compared with the fake's",
            "initial states use Python's random.Random while the upstream environment uses numpy's generator, so a "
            "seed does not give the same trajectory on the two",
            "no wall-clock pacing: realtime_factor 0, ticks advance simulated time by 50 ms (0.01 s model timestep "
            "times the registered frame_skip 5) only",
            "no rendering, no viewer and no mujoco_py: the fake returns plain Python floats where upstream returns "
            "numpy arrays",
            "snapshot and restore are not offered: the environment exposes no get_state or set_state",
            "no physical device is modelled and the model was never validated against one",
        ],
    }
