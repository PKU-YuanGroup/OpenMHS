# Facts and tags for gh.etaoxing/kitchen-shift

Every fact cites its source at commit `6d0928000d4843df43791d3efd9e58af72c3acac`. The same facts are written into
`driver.py` (`facts = [...]`); `reference.json` and `REFERENCE.md` are generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Kitchen_v0 is a gym.Env subclass described as a kitchen manipulation environment in MuJoCo | upstream_code | kitchen_shift/kitchen_v0.py:37-38 |
| The environment imports dm_control, mujoco, gym and numpy | upstream_code | kitchen_shift/kitchen_v0.py:15-24 |
| The robot has 9 degrees of freedom and the object state has 21 | upstream_code | kitchen_shift/kitchen_v0.py:63-64 |
| The default control mode is 'absvel' | upstream_code | kitchen_shift/kitchen_v0.py:42 |
| In the absvel control mode the action dimension is 9 | upstream_code | kitchen_shift/kitchen_v0.py:107-108 |
| The action space is gym.spaces.Box(-1.0, 1.0, shape=(action_dim,)) | upstream_code | kitchen_shift/kitchen_v0.py:129 |
| act_mid is zeros(action_dim) and act_amp is 2.0 * ones(action_dim) | upstream_code | kitchen_shift/kitchen_v0.py:130-131 |
| The action is clipped to [-1, 1] and then mapped to act_mid + a * act_amp | upstream_code | kitchen_shift/kitchen_v0.py:222-225 |
| The observation dict has the keys robot_qp, robot_qv, obj_qp and obj_qv | upstream_code | kitchen_shift/kitchen_v0.py:178-183 |
| The observation arrays are cast to float32 | upstream_code | kitchen_shift/kitchen_v0.py:189-191 |
| The observation space is a Dict of Box spaces bounded by -inf and inf, shaped by the observation dict | upstream_code | kitchen_shift/kitchen_v0.py:133-137 |
| step returns the observation dict, reward 0.0, done False and an empty info dict | upstream_code | kitchen_shift/kitchen_v0.py:215-220 |
| reset restores the simulator and returns the observation; objects_done_set selects elements whose goal pose is restored | upstream_code | kitchen_shift/kitchen_v0.py:293-305 |
| seed(seed) creates the environment's numpy random generator and returns [seed] | upstream_code | kitchen_shift/kitchen_v0.py:361-363 |
| The MuJoCo model timestep is 0.002 s | upstream_code | kitchen_shift/assets/kitchen.xml:16 |
| The default frame_skip is 40 | upstream_code | kitchen_shift/kitchen_v0.py:44 |
| kitchen-v0 is registered as a gym environment with max_episode_steps=280 | upstream_code | kitchen_shift/__init__.py:6-10 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(`Box(-1, 1, shape=(9,))`: `action.values` from -1 to 1 for all nine elements, source `upstream_code`, ref
`kitchen_shift/kitchen_v0.py:129`), and `ticks` (1 to `max_ticks`, 10000 by default). The device is simulated (R0),
so no limit is `operator_required` and there is no site overlay.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:kitchen-v0`, level F0 (the fake is not MuJoCo),
determinism `seeded` with `seed_control` `parameter`, timestep 80 ms (the default `frame_skip` of 40 at the model's
0.002 s timestep, `kitchen_v0.py:44` and `assets/kitchen.xml:16`), `realtime_factor` 0, clock `lockstep`, reset
`full`, no snapshot and restore. The gaps say what is not modelled: the MuJoCo physics, the robot controller and
observation noise, the object goal poses, rendering, worldgen, and any comparison with the upstream simulator.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: kitchen, manipulation, mujoco, franka, reinforcement-learning, simulation, gym
