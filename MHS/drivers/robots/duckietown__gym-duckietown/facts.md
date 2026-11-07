OpenMHS is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

# Facts and tags for gh.duckietown/gym-duckietown

Every fact cites its source at commit `c76a7fec7f739db4f624f40ca83ce99383665558`: `upstream_code`
(`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| MultiMapEnv builds one DuckietownEnv for each of the two maps loop_only_duckies and small_loop_only_duckies | upstream_code | src/gym_duckietown/envs/multimap_env.py:17-20 |
| MultiMapEnv copies the action space, observation space and reward range of the DuckietownEnv it built | upstream_code | src/gym_duckietown/envs/multimap_env.py:22-24 |
| Every reset advances cur_env_idx to the next environment and resets that environment | upstream_code | src/gym_duckietown/envs/multimap_env.py:44-49 |
| step delegates to the current environment, adds the reward and the step count to the totals, and clears the totals when the episode is done | upstream_code | src/gym_duckietown/envs/multimap_env.py:51-65 |
| seed seeds every environment and the environment's np_random, and returns [seed] | upstream_code | src/gym_duckietown/envs/multimap_env.py:34-42 |
| The step_count property returns the step count of the current environment | upstream_code | src/gym_duckietown/envs/multimap_env.py:88-90 |
| DuckietownEnv is a wrapper that controls the simulator with a velocity and a steering angle instead of differential drive motor velocities | upstream_code | src/gym_duckietown/envs/duckietown_env.py:9-13 |
| DuckietownEnv sets the action space to Box(low=[-1, -1], high=[1, 1], dtype=float32) | upstream_code | src/gym_duckietown/envs/duckietown_env.py:19 |
| DuckietownEnv.step reads the action as vel and angle, computes the two motor rotation rates from them and the wheel distance, converts those to duty cycles limited to [-limit, limit] and passes [left, right] to Simulator.step | upstream_code | src/gym_duckietown/envs/duckietown_env.py:36-63 |
| The observation space is Box(low=0, high=255, shape=(camera_height, camera_width, 3), dtype=uint8): an RGB camera image | upstream_code | src/gym_duckietown/simulator.py:315-320 |
| The default camera size is 640 by 480 pixels | upstream_code | src/gym_duckietown/simulator.py:103-105 |
| The observation is the image rendered from the agent's camera | upstream_code | src/gym_duckietown/simulator.py:1953-1960 |
| The simulator's default frame rate is 30 | upstream_code | src/gym_duckietown/simulator.py:165 |
| delta_time is 1.0 / frame_rate | upstream_code | src/gym_duckietown/simulator.py:299-300 |
| The reward range is -1000 to 1000 | upstream_code | src/gym_duckietown/simulator.py:322 |
| The default max_steps is 1500 | upstream_code | src/gym_duckietown/simulator.py:167 |
| Simulator.step clips its action to [-1, 1] before applying it | upstream_code | src/gym_duckietown/simulator.py:1670 |
| update_physics increments step_count and advances timestamp by delta_time | upstream_code | src/gym_duckietown/simulator.py:1561-1562 |
| An in-progress reward is speed * dot_dir - 10 * abs(lane distance) + 40 * collision penalty | upstream_code | src/gym_duckietown/simulator.py:1666 |
| An invalid pose terminates the episode and returns REWARD_INVALID_POSE | upstream_code | src/gym_duckietown/simulator.py:1687-1692 |
| REWARD_INVALID_POSE is -1000 | upstream_code | src/gym_duckietown/simulator.py:175 |
| Reaching max_steps terminates the episode with reward 0 | upstream_code | src/gym_duckietown/simulator.py:1694-1699 |
| MultiMap-v0 is registered with entry point gym_duckietown.envs:MultiMapEnv and reward_threshold 400 | upstream_code | src/gym_duckietown/__init__.py:48 |
| Duckiebot-v0 is registered with entry point gym_duckietown.envs:DuckiebotEnv | upstream_code | src/gym_duckietown/__init__.py:50 |
| DuckiebotEnv is the environment that is the actual real robot | upstream_code | src/gym_duckietown/envs/duckiebot_env.py:46-47 |
| DuckiebotEnv connects a ZMQ PAIR socket to the bridge node at serverAddr:serverPort | upstream_code | src/gym_duckietown/envs/duckiebot_env.py:73-78 |
| DuckiebotEnv sends each action over that socket as a JSON command | upstream_code | src/gym_duckietown/envs/duckiebot_env.py:132-133 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Box(low=[-1, -1], high=[1, 1])`: `action.values`, a velocity and a steering angle, each from -1 to 1, with the
source `upstream_code` and the ref `src/gym_duckietown/envs/duckietown_env.py:19`, the space the fake copies), and
`ticks` (1 to `max_ticks`, 10000 by default). The simulator is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gym-duckietown:MultiMap-v0`, level F0 (kinematic
differential-drive pose integration with geometric collision checks, no force, contact, actuator, sensor or noise
dynamics), determinism `seeded` with `seed_control` `parameter`, timestep 33.3 ms (default frame rate 30 and
`delta_time = 1.0 / frame_rate`, `simulator.py:165` and `:299-300`), `realtime_factor` 0, clock `lockstep`, reset
`full`, no snapshot and restore. The gaps say what is not modelled, that the fake's observation is one 3-value RGB
sample rather than the rendered 480 x 640 x 3 camera frame, and that the fake converts the velocity and the steering
angle to wheel commands as `DuckietownEnv.step` does but moves its pose from them with placeholder dynamics.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: duckietown, multimap, camera, differential-drive, simulation, gym

## Simulator status messages

The fake now returns the sentence or empty string placed in `info["Simulator"]["msg"]` by the pinned `src/gym_duckietown/simulator.py:1681,1687-1705`. The internal done codes are not messages. This repairs observable result semantics only; the disclosed F0 lane, image and steering dynamics remain placeholders.
