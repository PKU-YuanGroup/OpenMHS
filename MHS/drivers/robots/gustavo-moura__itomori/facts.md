# Facts and tags for gh.gustavo-moura/itomori

Every fact cites its source at commit `0c2da173bf989736f919772d3c6cbc2fea098b72`. All facts are `upstream_code`:
the clone is the simulator and a code line is the evidence. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| itomori/Navigation2DEnv-v0 is registered with entry point itomori.envs:Navigation2DEnv and max_episode_steps=300 | upstream_code | itomori/__init__.py:3-7 |
| The constructor defaults render_mode to 'human' and accepts only 'human' or 'rgb_array' | upstream_code | itomori/envs/navigation2d.py:21-39 |
| The constructor's default map_filepath is the relative path itomori/navigation2d_config/maps/10x10/10x10_NoObstacle.json | upstream_code | itomori/envs/navigation2d.py:22 |
| default_uav_args sets velocity_initial 0, velocity_min 0, velocity_max 50, velocity_change_min -10, velocity_change_max 100, angle_initial 0, angle_change_min -10, angle_change_max 10, delta_T 0.1, gps_uncertainty_initial 0.5 and gps_uncertainty_increment 0.02 | upstream_code | itomori/envs/configs.py:2-13 |
| load_uav_args documents velocity in m/s, angle change in degrees/s, velocity change in m/s**2, delta_T in s and GPS uncertainty in m | upstream_code | itomori/envs/navigation2d.py:133-140 |
| The observation space is a Dict of origin (x, y in 0..50), destination (x, y in 0..size) and agent_location (x, y in 0..size; velocity in velocity_min..velocity_max; angle unbounded and risk/GPS uncertainty in 0..inf) | upstream_code | itomori/envs/navigation2d.py:79-98 |
| The action space is a Box(2) of [angle change, velocity change] with low [angle_change_min, velocity_change_min] and high [angle_change_max, velocity_change_max], dtype float | upstream_code | itomori/envs/navigation2d.py:100-111 |
| The starting agent location is [origin x, origin y, velocity_initial, angle_initial] | upstream_code | itomori/envs/navigation2d.py:55-62 |
| _move unpacks the action as ac, vc = action, so the first action value is the angle change and the second the velocity change | upstream_code | itomori/envs/navigation2d.py:325 |
| A step sets velocity to v + velocity_change*delta_T clipped to [velocity_min, velocity_max] and the angle to a + angle_change*delta_T clipped to [angle_change_min, angle_change_max] | upstream_code | itomori/envs/navigation2d.py:329-335 |
| A step then advances x by v_next*cos(angle_next)*delta_T + velocity_change*cos(angle_next)*delta_T**2/2 (sin for y) and clips each coordinate to [0, size] | upstream_code | itomori/envs/navigation2d.py:337-343 |
| reset sets timestep 0, previous_agent_location None, the agent at the starting location with risk from chance_constraint and the current gps_uncertainty, and the history to that one location | upstream_code | itomori/envs/navigation2d.py:217-235 |
| step increments timestep, adds gps_uncertainty_increment to gps_uncertainty, appends the new location to the history, and returns observation, reward, terminated, truncated=False and info | upstream_code | itomori/envs/navigation2d.py:237-261 |
| destination_tolerance is 1.5 m | upstream_code | itomori/envs/navigation2d.py:46 |
| is_done is true when the distance to the destination is below destination_tolerance or the agent failed | upstream_code | itomori/envs/navigation2d.py:202-212 |
| is_outofbounds is true when any coordinate is <= 0 or >= size | upstream_code | itomori/envs/navigation2d.py:214-215 |
| is_failed is true when the agent is out of bounds or its segment hits an obstacle | upstream_code | itomori/envs/navigation2d.py:194-200 |
| The reward is distance_weight*distance + steps_weight*len(agent_location_history) + risk_weight*risk, and math.inf when the agent failed | upstream_code | itomori/envs/navigation2d.py:349-369 |
| reward_weights defaults to distance 0.9, steps 0.1 and risk 0, and the constructor asserts that the weights sum to 1 | upstream_code | itomori/envs/navigation2d.py:24-42 |
| A map JSON declares size in m, origin [x, y], destination [x, y] and a list of polygon obstacles | upstream_code | itomori/envs/navigation2d.py:162-166 |
| The 10x10_NoObstacle.json map has size 10, origin [1, 1], destination [9, 9] and no obstacles | upstream_code | itomori/envs/navigation2d_configs/maps/10x10/10x10_NoObstacle.json:1-6 |
| step always returns truncated=False | upstream_code | itomori/envs/navigation2d.py:255 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Box(2)`: `action.values` from `[-10, -10]` to `[10, 100]` for the default `uav_args`, with no source and the ref
`action_space of the fake backend .fake:FakeNavigation2DEnv`), and `ticks` (1 to `max_ticks`, 10000 by default). The
device is simulated (R0), so no limit is `operator_required`. The numbers in `default_uav_args` are constructor
defaults, not device bounds: a deployment may pass a different `uav_args` and the action space follows it.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `itomori:Navigation2DEnv-v0`, level F0 (a kinematic
point model with no mass, force, actuator, contact or noise model; the gaps say so), determinism `seeded` with
`seed_control` `parameter` (the environment draws no random numbers, so a reset always starts at the map origin),
timestep 100 ms (`delta_T = 0.1` s, `configs.py:11`), `realtime_factor` 0, clock `lockstep`, reset `full`, no
snapshot and restore. The gaps also name the fake's coverage (default no-obstacle map only) and the upstream default
`map_filepath` mismatch.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: uav, navigation, risk-aware, reinforcement-learning, simulation, gymnasium
