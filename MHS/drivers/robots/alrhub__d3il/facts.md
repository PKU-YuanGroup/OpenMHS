# Facts and tags for gh.alrhub/d3il

Every fact cites its source at commit `1d9c71850d4fc1477cee17b557c8b97d70b13071`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| sorting-v0 is registered with entry point gym_sorting.envs:Sorting_Env, max_episode_steps=2000 and the kwargs max_steps_per_episode=100, render=True, num_boxes=2 and if_vision=False | upstream_code | environments/d3il/envs/gym_sorting_env/gym_sorting/__init__.py:3-8 |
| The action space is a 2-D Box with low [-0.01, -0.01] and high [0.01, 0.01] | upstream_code | environments/d3il/envs/gym_sorting_env/gym_sorting/envs/sorting.py:237-239 |
| The observation space is a Box with shape (8,) and unbounded low -inf and high +inf | upstream_code | environments/d3il/envs/gym_sorting_env/gym_sorting/envs/sorting.py:240-242 |
| With num_boxes=2 the observation concatenates the robot xy, the red box xy and yaw tangent and the blue box xy and yaw tangent | upstream_code | environments/d3il/envs/gym_sorting_env/gym_sorting/envs/sorting.py:340-350 |
| get_reward returns 0 | upstream_code | environments/d3il/envs/gym_sorting_env/gym_sorting/envs/sorting.py:509-511 |
| The episode terminates when every red box is in x (0.3, 0.5) and y (0.22, 0.41) and every blue box is in x (0.525, 0.725) and y (0.22, 0.41); with num_boxes=2 those are the red and blue box | upstream_code | environments/d3il/envs/gym_sorting_env/gym_sorting/envs/sorting.py:523-541 |
| The wrapper ends an episode when terminated, the task's early termination or env_step_counter >= max_steps_per_episode - 1 is true | upstream_code | environments/d3il/d3il_sim/gyms/gym_env_wrapper.py:124-137 |
| The MuJoCo scene is created with the physics timestep dt=0.001 s | upstream_code | environments/d3il/envs/gym_sorting_env/gym_sorting/envs/sorting.py:218-220 |
| n_substeps defaults to 35 controller steps per environment step | upstream_code | environments/d3il/envs/gym_sorting_env/gym_sorting/envs/sorting.py:196 |
| A step passes the action to the Cartesian controller's setSetPoint and executes n_substeps controller steps | upstream_code | environments/d3il/d3il_sim/gyms/gym_env_wrapper.py:83-86 |
| The initial end-effector position is [0.525, -0.3, 0.25] | upstream_code | environments/d3il/envs/gym_sorting_env/gym_sorting/envs/objects/sorting_objects.py:11 |
| The context manager samples six box positions from 3-D Box spaces with x in [0.4, 0.5] or [0.55, 0.65], y in [-0.15, 0.1] and yaw in [-90, 90] degrees | upstream_code | environments/d3il/envs/gym_sorting_env/gym_sorting/envs/sorting.py:52-74 |
| The wrapper's seed method delegates to gym.utils.seeding.np_random and returns the accepted seed | upstream_code | environments/d3il/d3il_sim/gyms/gym_env_wrapper.py:41-43 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Box` low [-0.01, -0.01] and high [0.01, 0.01], with source `upstream_code` and ref
`environments/d3il/envs/gym_sorting_env/gym_sorting/envs/sorting.py:237-239`), and `ticks` (1 to `max_ticks`, 10000 by
default). The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gym:sorting-v0`, level F0 (kinematic state transitions
of the fake), determinism `seeded` with `seed_control` `parameter`, timestep 35 ms (one control step; the upstream
scene integrates MuJoCo at 1 ms for 35 substeps), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and
restore. The gaps say what is not modelled: the MuJoCo arm, contacts, actuator and sensor dynamics, the upstream start
sampling, the 2-D action versus the Cartesian controller, and the difference between the fake's float lists and the
upstream float32 arrays.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step,
reset or seed is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the
state stays readable.

Tags: sorting, manipulation, mujoco, reinforcement-learning, simulation, gymnasium, d3il
