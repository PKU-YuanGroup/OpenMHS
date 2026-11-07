# Facts and tags for gh.tau-intelligence/mujoco-drones-gym

Every fact cites its source at commit `ca170dc6760d422e47ef46fb3af46f8cd20410eb` as `upstream_code`
(`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the reference files are
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| HoverAviary is the single-drone hover task: hover at height 1.0 and remain stable | upstream_code | multi_drone_mujoco/envs/hover_aviary.py:3 |
| The action is a 4-element normalized RPM command in [-1, 1] | upstream_code | multi_drone_mujoco/envs/hover_aviary.py:5 |
| The action space is a Box with low -1 and high 1 for each of the 4 motors | upstream_code | multi_drone_mujoco/envs/hover_aviary.py:51-53 |
| The observation is 12 values: position (3), roll-pitch-yaw (3), linear velocity (3) and angular velocity (3) | upstream_code | multi_drone_mujoco/envs/hover_aviary.py:68-73 |
| The default simulation frequency is 240 Hz and the default control frequency is 48 Hz | upstream_code | multi_drone_mujoco/envs/hover_aviary.py:22-23 |
| The control period is 1/ctrl_freq and the physics step is 1/sim_freq; the environment runs sim_freq/ctrl_freq physics sub-steps per control step | upstream_code | multi_drone_mujoco/envs/base_aviary.py:350-354 |
| The default initial position is [0.0, 0.0, 0.1] | upstream_code | multi_drone_mujoco/envs/hover_aviary.py:33-34 |
| EPISODE_LEN_SEC is 10 s | upstream_code | multi_drone_mujoco/envs/hover_aviary.py:32 |
| The episode truncates when step_counter / SIM_FREQ reaches the episode length | upstream_code | multi_drone_mujoco/envs/hover_aviary.py:113-115 |
| The episode terminates when the altitude is below 0 or above 3 m, or when the absolute roll or pitch exceeds pi/2 | upstream_code | multi_drone_mujoco/envs/hover_aviary.py:105-110 |
| The reward is -(height error) - 0.1*(xy error) - 0.05*abs(velocity) - 0.05*(abs(roll) + abs(pitch)), plus 1 when both errors are below 0.05 and -100 when terminated | upstream_code | multi_drone_mujoco/envs/hover_aviary.py:83-95 |
| The info dict reports the position and the absolute height error | upstream_code | multi_drone_mujoco/envs/hover_aviary.py:117-121 |
| reset(seed, options) delegates the seed to the Gymnasium base class, restores the initial position and orientation, zeroes step_counter and last_clipped_action, and returns the observation and info | upstream_code | multi_drone_mujoco/envs/base_aviary.py:490-524 |
| step preprocesses the action, runs the physics sub-steps, increments step_counter by SIM_STEPS_PER_CTRL and returns observation, reward, terminated, truncated and info | upstream_code | multi_drone_mujoco/envs/base_aviary.py:528-598 |
| With the MuJoCo physics mode each simulation sub-step advances the model with mujoco.mj_step | upstream_code | multi_drone_mujoco/envs/base_aviary.py:577-579 |
| The package's runtime dependencies are gymnasium>=0.29.0, mujoco>=3.0.0 and numpy>=1.21.0; no hardware transport is declared | upstream_code | setup.py:13-15 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Box` of four elements from -1 to 1); the source in the reference is the fake stand-in's `action_space`, and the
bridge's `ticks` input is bounded by `max_ticks` (10000 by default). The device is simulated (R0), so no limit is
`operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:HoverAviary`, level F1 (rigid-body MuJoCo dynamics
with contacts and an RPM-to-thrust/torque actuator), determinism `seeded` with `seed_control` `parameter` (the hover
start pose is fixed, so an action sequence repeats from a reset), `timestep_ms` 4.1667 ms (the physics step, 1/240 s,
`base_aviary.py:354`; one `cap.world.step.v1` tick is one control step of 5 physics sub-steps, 1/48 s,
`base_aviary.py:352-353` and `:585`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The
gaps say what is not modelled and that the fake was not compared with the upstream environment.

The envs package re-exports the environment classes (`multi_drone_mujoco/envs/__init__.py:1-7`) and the upstream
README constructs `HoverAviary` directly (`README.md:67`); the driver therefore leaves `env_id` None instead of naming
an unregistered id.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: mujoco, quadcopter, hover, reinforcement-learning, simulation, gymnasium
