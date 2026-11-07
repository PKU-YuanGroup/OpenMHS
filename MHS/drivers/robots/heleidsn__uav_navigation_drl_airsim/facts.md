# Facts and tags for gh.heleidsn/uav_navigation_drl_airsim

Every fact cites its source at commit `389e5220595361dc26a0b84c75bc4e6cde3a3112`: `upstream_code`
(`path/in/clone.py:LINE`) or `vendor_doc` (a text file of the clone such as `README.md`). The published contract is the
NH_center configuration with `SimpleMultirotor` dynamics; the driver is simulated (R0) and serves the fake backend.

| fact | source | ref |
|---|---|---|
| The environment is registered as `airsim-env-v0` with entry point `gym_env.envs:AirsimGymEnv` | upstream_code | `gym_env/gym_env/__init__.py:4-6` |
| `AirsimGymEnv` subclasses `gym.Env` and `QtCore.QThread` | upstream_code | `gym_env/gym_env/envs/airsim_env.py:21` |
| The selected configuration sets `env_name NH_center` and `dynamic_name SimpleMultirotor` | upstream_code | `configs/config_NH_center_SimpleMultirotor_3D.ini:2-3` |
| The NH_center configuration sets `navigation_3d True`, `using_velocity_state False`, `perception vector`, `dt 0.1 s`, `v_xy_min 0.5`, `v_xy_max 5`, `v_z_max 2.0` and `yaw_rate_max_deg 30.0` | upstream_code | `configs/config_NH_center_SimpleMultirotor_3D.ini:5-44` |
| The environment builds `MultirotorDynamicsSimple` when `dynamic_name` is `SimpleMultirotor` | upstream_code | `gym_env/gym_env/envs/airsim_env.py:61-62` |
| With `navigation_3d True` and `using_velocity_state False` the multirotor state feature has 3 entries | upstream_code | `gym_env/gym_env/envs/dynamics/multirotor_simple.py:58-62` |
| The 3D action space is `Box(low=[v_xy_min, -v_z_max, -yaw_rate_max_rad], high=[v_xy_max, v_z_max, yaw_rate_max_rad])` | upstream_code | `gym_env/gym_env/envs/dynamics/multirotor_simple.py:62-65` |
| For NH_center the start position is `[0, 0, 5]`, the goal rectangle is `[-128, -128, 128, 128]`, the workspace is x `[-140, 140]`, y `[-140, 140]`, z `[0.5, 20]` and `max_episode_steps` is 1000 | upstream_code | `gym_env/gym_env/envs/airsim_env.py:69-79` |
| The configuration sets `cnn_feature_num 25`, `crash_distance 1` and `accept_radius 2` | upstream_code | `configs/config_NH_center_SimpleMultirotor_3D.ini:18-36` |
| The declared vector observation space is `Box(low=0, high=1, shape=(1, cnn_feature_num + state_feature_length))` | upstream_code | `gym_env/gym_env/envs/airsim_env.py:180-185` |
| The vector observation concatenates five depth-column maxima normalized to 0..1 with the normalized state feature and reshapes it to one row | upstream_code | `gym_env/gym_env/envs/airsim_env.py:394-425` |
| An action step updates x, y, z and yaw by `dt` and wraps yaw beyond plus or minus pi | upstream_code | `gym_env/gym_env/envs/dynamics/multirotor_simple.py:97-116` |
| The start yaw is `start_random_angle` times a uniform random number | upstream_code | `gym_env/gym_env/envs/dynamics/multirotor_simple.py:75-83` |
| `AirsimGymEnv.reset` returns only the observation | upstream_code | `gym_env/gym_env/envs/airsim_env.py:201-215` |
| `AirsimGymEnv.step` returns `(observation, reward, done, info)` | upstream_code | `gym_env/gym_env/envs/airsim_env.py:300-303` |
| `is_done` ends the episode on a workspace exit, a goal within `accept_radius`, a crash, or `step_num` at `max_episode_steps` | upstream_code | `gym_env/gym_env/envs/airsim_env.py:860-873` |
| `compute_reward_final` uses `distance_reward_coef 500` for NH_center, `reward_reach 10`, `reward_crash -20` and `reward_outside -10` | upstream_code | `gym_env/gym_env/envs/airsim_env.py:521-530` |
| `compute_reward_final` subtracts `0.1 * punishment_pose`, `0.2 * punishment_obs`, `0.1 * punishment_action` and `0.5 * yaw_error_cost` | upstream_code | `gym_env/gym_env/envs/airsim_env.py:577-578` |
| A collision is reported when AirSim reports `has_collided` or the minimum obstacle distance is below `crash_distance` | upstream_code | `gym_env/gym_env/envs/airsim_env.py:896-902` |
| The README states Python 3.8, AirSim 1.6.0, PyTorch 1.10.1, gym 0.21.0 and PyQt5 5.15.6 | vendor_doc | `README.md:58-66` |

## Not covered by the fake

- The depth image: `get_obs_vector` takes five column maxima of an AirSim depth image (`airsim_env.py:394-415`); the
  fake returns five placeholder zeros (marked `# placeholder` in `fake.py`). The real observation is 5 + 3 = 8 values
  even though the upstream declares `(1, 28)` (`airsim_env.py:180-185`, `configs/config_NH_center_SimpleMultirotor_3D.ini:18`).
- The AirSim RPC, the UE4 scene, the collision query and the PyQt display. The fake was not compared with a real
  environment; the sim backend was not run.

Tags: `uav`, `airsim`, `gym`, `reinforcement-learning`, `navigation`, `simulation`, `kinematic`.
