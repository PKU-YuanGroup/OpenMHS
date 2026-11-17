# Facts and tags for gh.ice-mao/rl_auv_tracking

Every fact cites its source at commit `8ff39512f796801aa461fa074f7972e3a4e3a81f`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| TargetTrackingBase is the Gymnasium environment class and derives from gym.Env | upstream_code | auv_env/envs/base.py:27 |
| TargetTrackingBase constructs the world from the world class, map and viewport flag, stores the config, and takes its action and observation spaces from the world | upstream_code | auv_env/envs/base.py:32-44 |
| auv_env.make builds TargetTrackingBase(world_class, map_name, show_viewport, config, **kwargs) | upstream_code | auv_env/__init__.py:51 |
| The make factory's t_steps parameter defaults to 100 | upstream_code | auv_env/__init__.py:11 |
| auv_env.make wraps the environment in gym.wrappers.TimeLimit(max_episode_steps=t_steps) | upstream_code | auv_env/__init__.py:53 |
| AUVTracking_v0 selects WorldAuvV0, the SimpleUnderwater-Bluerov2 map and ../configs/envs/v0_config.yml | upstream_code | auv_env/__init__.py:31 |
| The v1-state gym.register block is commented out | upstream_code | auv_env/__init__.py:125-129 |
| When no config is passed, make loads the cwd-relative default by config_loader.load_config | upstream_code | auv_env/__init__.py:44-46 |
| WorldAuvV0 is the state-only world | upstream_code | auv_env/envs/world_auv_v0.py:20-23 |
| WorldBase creates the scene with holoocean.make(self.map, show_viewport=show) | upstream_code | auv_env/envs/base.py:73 |
| WorldBase derives the sampling period as 1/scenario['ticks_per_sec'] from the HoloOcean scenario | upstream_code | auv_env/envs/base.py:78 |
| WorldBase computes ticks_per_rl_step from the controller frequency and the sampling period | upstream_code | auv_env/envs/base.py:110-118 |
| TargetTrackingBase.reset calls np.random.seed() with no argument before delegating to world.reset | upstream_code | auv_env/envs/base.py:46-51 |
| WorldAuvV0.reset clears its reward and action queues before calling WorldBase.reset | upstream_code | auv_env/envs/world_auv_v0.py:30-33 |
| get_init_pose_random calls np.random.seed() with no argument inside its outer initial-pose sampling loop | upstream_code | auv_env/envs/base.py:461-466 |
| TargetTrackingBase.step delegates to world.step(action=action) | upstream_code | auv_env/envs/base.py:53-60 |
| WorldBase.step loops over ticks_per_rl_step iterations | upstream_code | auv_env/envs/base.py:181 |
| WorldBase.step calls self.ocean.tick() | upstream_code | auv_env/envs/base.py:237 |
| WorldBase.step returns (state, reward, done, 0, info) | upstream_code | auv_env/envs/base.py:271 |
| WorldBase.reset teleports auv0 and each target to the sampled poses and ticks the ocean once | upstream_code | auv_env/envs/base.py:386-408 |
| WorldBase.reset returns (state, info) with info {'reset_info': 'yes'} | upstream_code | auv_env/envs/base.py:432-444 |
| WorldBase.reset prints the sampled agent and target poses | upstream_code | auv_env/envs/base.py:383-384 |
| TargetTrackingBase.seed calls np.random.seed(seed) | upstream_code | auv_env/envs/base.py:62-63 |
| The shipped v0 config selects the PID controller | upstream_code | configs/envs/v0_config.yml:24 |
| The PID controller config has action_dim 2 and control_frequency 5 | upstream_code | configs/envs/v0_config.yml:35-37 |
| WorldAuvV0.set_limits builds the PID action space from config action_range_low[1] and action_range_high[1] | upstream_code | auv_env/envs/world_auv_v0.py:43-48 |
| The shipped v0 PID action range is low [-1, -1] and high [1, 1] with scale [1.5, 0.5] | upstream_code | configs/envs/v0_config.yml:79-81 |
| The PID step sets CmdVel.linear.x to action[0] times action_range_scale[0] and CmdVel.angular.z to action[1] times action_range_scale[1] | upstream_code | auv_env/envs/base.py:174-179 |
| The v0 state is [target-belief distance, target-belief bearing, log determinant of the covariance, observed flag] per target, then [nearest obstacle distance, nearest obstacle angle] | upstream_code | auv_env/envs/world_auv_v0.py:109-133 |
| The v0 observation space is Box(6) with lower [0, -pi, -50, 0, 0, -pi] and upper [600, pi, 50, 2, sensor_r, pi] for one target | upstream_code | auv_env/envs/world_auv_v0.py:61-67 |
| The v0 reward is c_mean * r_detcov_mean + c_std * r_detcov_std + c_smooth * r_action_smooth and, on a collision, min(0, reward) - c_penalty | upstream_code | auv_env/envs/world_auv_v0.py:78-95 |
| The v0 reward defaults are c_mean 0.2, c_std 0.0, c_smooth 1.0 and c_penalty 5.0 | upstream_code | configs/envs/v0_config.yml:83-87 |
| WorldAuvV0 keeps the last 100 rewards in a deque(maxlen=100) | upstream_code | auv_env/envs/world_auv_v0.py:26 |
| The episode is done when the 100-entry reward deque is full and its mean is below -3.5 | upstream_code | auv_env/envs/world_auv_v0.py:97-103 |
| The v0 config sets num_targets 1, margin 1.0 and margin2wall 1.0 | upstream_code | configs/envs/v0_config.yml:14-16 |
| The v0 config sets sensor_r 4.0 and fov 100 | upstream_code | configs/envs/v0_config.yml:46-47 |
| The README requires HoloOcean 2.0.0 and copying the configs/holoocean scenarios into the HoloOcean worlds directory | vendor_doc | README.md:48-53 |
| The README documents gym.make('AUVTracking_v0') as the registration path | vendor_doc | README.md:134 |

Limits: the driver declares none. The only bound is the action Box, which the bridge derives from the fake
environment (`[-1, -1]` to `[1, 1]` per element, `source` `upstream_code`, ref `configs/envs/v0_config.yml:79-81`
through `action_space_ref`). The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine analytic AUVTracking_v0 stand-in, level F0, determinism
`seeded` with `seed_control` `parameter` (the fake honors `reset(seed)`; the upstream reset reseeds numpy from
entropy at `auv_env/envs/base.py:47` and `:463`, so an upstream seed fixes nothing), `timestep_ms` 0 (the upstream
sampling period is `1/scenario['ticks_per_sec']` of the HoloOcean scenario, `base.py:78`, and is not fixed in the
clone), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot. The gaps say what is not modelled and that
the live environment was never run or compared.

Scope: `AUVTracking_v0` with the shipped `configs/envs/v0_config.yml` defaults (the state-only `WorldAuvV0`, PID, two
actions, one target). Other worlds, the 3D variants and the LQR/KEYBOARD controller configurations are not covered.

Safety: simulated R0 device with only a fake backend. The e-stop is the runtime's software latch; after it
no step, reset or seed is accepted until `mhs.safety.reset` clears the latch, and the fake state stays readable.
No stop is sent to HoloOcean. The package provides no live HoloOcean construction or stop evidence.

Tags: auv, underwater, target-tracking, reinforcement-learning, holoocean, simulation, gymnasium

Native construction caveats (unserved): the outer initial-pose sampling loop has no total attempt or time bound
(`auv_env/envs/base.py:454-533`), and reset prints poses to stdout (`:383-384`). A live adapter would need bounded
sampling, simulator lifecycle handling and separation from the MHS stdio channel.
