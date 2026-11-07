"""OpenMHS driver for gh.heleidsn/uav_navigation_drl_airsim: the AirSim UAV Gym environment.

The upstream repository registers the legacy Gym environment ``airsim-env-v0`` (``gym_env/gym_env/__init__.py:4-6``)
whose class is ``gym_env.envs:AirsimGymEnv`` (``gym_env/gym_env/envs/airsim_env.py:21``).  A GymnasiumDriver is
configuration only: the bridge derives ``cap.world.step.v1`` from the environment's action space and serves
``cap.world.reset.v1`` and ``cap.world.seed.v1``.  The published contract is the NH_center configuration with
``SimpleMultirotor`` dynamics (``configs/config_NH_center_SimpleMultirotor_3D.ini``): a three-element Box action
(horizontal speed, vertical speed, yaw rate) and a Box observation.

The device is simulated (R0): there is no hardware backend and no hardware stop.  The gate cannot import the clone
(it imports airsim, torch, cv2, PyQt5 and keyboard, ``gym_env/gym_env/envs/airsim_env.py:1-18``), so the ``fake``
backend is the package's own pure Python reimplementation of the selected configuration.  The ``sim`` backend, which
would call ``gym.make("airsim-env-v0")``, needs the upstream package and an AirSim v1.6.0 scene and was not run; the
upstream also requires ``set_config(cfg)`` before it has spaces, which the family bridge does not call.

Every fact and every number in the fidelity contract cites a line of the clone at the pinned commit
389e5220595361dc26a0b84c75bc4e6cde3a3112.  This package is model-authored and unreviewed; it is checked on the fake
backend only.
"""

from mhs.driver import Fact, GymnasiumDriver

ENV = "gym_env/gym_env/envs/airsim_env.py"
DYNAMICS = "gym_env/gym_env/envs/dynamics/multirotor_simple.py"
CONFIG = "configs/config_NH_center_SimpleMultirotor_3D.ini"


class AirsimNavigationEnv(GymnasiumDriver):
    device_id = "uav-navigation-drl-airsim"
    env_id = "airsim-env-v0"
    native = "gym_env.envs:AirsimGymEnv"
    backends = {"fake": ".fake:FakeAirsimGymEnv"}
    display_name = "UAV Navigation DRL AirSim (NH_center, SimpleMultirotor 3D)"
    vendor, model = "heleidsn", "UAV_Navigation_DRL_AirSim"
    seed = 0
    autoreset = False
    fidelity_level = "F1"
    tags = ["uav", "airsim", "gym", "reinforcement-learning", "navigation", "simulation", "kinematic"]
    facts = [
        Fact("The environment is registered as airsim-env-v0 with entry point gym_env.envs:AirsimGymEnv",
             source="upstream_code", ref="gym_env/gym_env/__init__.py:4-6"),
        Fact("AirsimGymEnv subclasses gym.Env and QtCore.QThread", source="upstream_code", ref=f"{ENV}:21"),
        Fact("The selected configuration sets env_name NH_center and dynamic_name SimpleMultirotor",
             source="upstream_code", ref=f"{CONFIG}:2-3"),
        Fact("The NH_center configuration sets navigation_3d True, using_velocity_state False, perception vector, "
             "dt 0.1 s, v_xy_min 0.5, v_xy_max 5, v_z_max 2.0 and yaw_rate_max_deg 30.0", source="upstream_code",
             ref=f"{CONFIG}:5-44"),
        Fact("The environment builds MultirotorDynamicsSimple when dynamic_name is SimpleMultirotor",
             source="upstream_code", ref=f"{ENV}:61-62"),
        Fact("With navigation_3d True and using_velocity_state False the multirotor state feature has 3 entries",
             source="upstream_code", ref=f"{DYNAMICS}:58-62"),
        Fact("The 3D action space is Box(low=[v_xy_min, -v_z_max, -yaw_rate_max_rad], high=[v_xy_max, v_z_max, "
             "yaw_rate_max_rad])", source="upstream_code", ref=f"{DYNAMICS}:62-65"),
        Fact("For NH_center the start position is [0, 0, 5], the goal rectangle is [-128, -128, 128, 128], the "
             "workspace is x [-140, 140], y [-140, 140], z [0.5, 20] and max_episode_steps is 1000",
             source="upstream_code", ref=f"{ENV}:69-79"),
        Fact("The configuration sets cnn_feature_num 25, crash_distance 1 and accept_radius 2",
             source="upstream_code", ref=f"{CONFIG}:18-36"),
        Fact("The declared vector observation space is Box(low=0, high=1, shape=(1, cnn_feature_num + "
             "state_feature_length))", source="upstream_code", ref=f"{ENV}:180-185"),
        Fact("The vector observation concatenates five depth-column maxima normalized to 0..1 with the normalized "
             "state feature and reshapes it to one row", source="upstream_code", ref=f"{ENV}:394-425"),
        Fact("An action step updates x, y, z and yaw by dt and wraps yaw beyond plus or minus pi",
             source="upstream_code", ref=f"{DYNAMICS}:97-116"),
        Fact("The start yaw is start_random_angle times a uniform random number",
             source="upstream_code", ref=f"{DYNAMICS}:75-83"),
        Fact("AirsimGymEnv.reset returns only the observation", source="upstream_code", ref=f"{ENV}:201-215"),
        Fact("AirsimGymEnv.step returns (observation, reward, done, info)", source="upstream_code",
             ref=f"{ENV}:300-303"),
        Fact("is_done ends the episode on a workspace exit, a goal within accept_radius, a crash, or step_num at "
             "max_episode_steps", source="upstream_code", ref=f"{ENV}:860-873"),
        Fact("compute_reward_final uses distance_reward_coef 500 for NH_center, reward_reach 10, reward_crash -20 "
             "and reward_outside -10", source="upstream_code", ref=f"{ENV}:521-530"),
        Fact("compute_reward_final subtracts 0.1 times punishment_pose, 0.2 times punishment_obs, 0.1 times "
             "punishment_action and 0.5 times yaw_error_cost", source="upstream_code", ref=f"{ENV}:577-578"),
        Fact("A collision is reported when AirSim reports has_collided or the minimum obstacle distance is below "
             "crash_distance", source="upstream_code", ref=f"{ENV}:896-902"),
        Fact("The README states Python 3.8, AirSim 1.6.0, PyTorch 1.10.1, gym 0.21.0 and PyQt5 5.15.6",
             source="vendor_doc", ref="README.md:58-66"),
    ]
    safe_state = ("the simulation stops advancing: while the e-stop is latched, step and reset calls are refused "
                  "with MHS.SAFETY.ESTOP_ENGAGED and the last state stays readable; only mhs.safety.reset clears "
                  "the latch")
    #: The fidelity contract of the kinematic model as deployed (spec 05-fidelity FID-002).  The bridge derives the
    #: engine, determinism kind and lockstep clock; they are written out so the contract reads in one place.
    fidelity = {
        "engine": "gymnasium:airsim-env-v0",
        "fidelity_level": "F1",
        "determinism": {
            "kind": "seeded",
            "seed_control": "parameter",
            "notes": "reset(seed) or cap.world.seed.v1 fixes the start yaw and the goal draw, and the kinematic "
                     "update is deterministic, so the fake repeats a trajectory for one seed and action list; the "
                     "upstream draws those two values from numpy's global generator, so a seed gives different "
                     "trajectories on the two implementations",
        },
        "timestep_ms": 100.0,
        "realtime_factor": 0,
        "clock": "lockstep",
        "reset": "full",
        "snapshot_restore": False,
        "gaps": [
            "no AirSim scene, physics engine, depth image, collision query or rendering: the fake advances the "
            "kinematic MultirotorDynamicsSimple state in pure Python and returns five placeholder depth features "
            "(marked in fake.py); the upstream observation derives those five features from a depth image",
            "the upstream declares observation_space shape (1, cnn_feature_num + state_feature_length) = (1, 28) "
            "for this configuration (airsim_env.py:180-185, config line 18), but get_obs_vector returns five depth "
            "features plus the three state features (airsim_env.py:394-425); the fake publishes the actual "
            "8-value vector",
            "the fake draws the start yaw and the goal with Python's random.Random; upstream uses numpy's global "
            "generator, so one seed gives different trajectories",
            "no collision information: is_crashed uses only the placeholder minimum distance, not AirSim's "
            "simGetCollisionInfo (airsim_env.py:896-902)",
            "no PyQt signals and no AirSim RPC; the fake was not compared with the upstream environment, which "
            "needs AirSim 1.6.0, gym 0.21.0, PyQt5 and torch (README.md:58-66)",
            "the sim backend was not run: it needs the upstream package and an AirSim scene, and the upstream "
            "environment needs set_config(cfg) before it has spaces, which the family bridge does not call",
        ],
    }
