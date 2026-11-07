# Facts and tags for gh.bilalkabas/drl-nav

Every fact cites its source at commit `a996f5461c90adfe765ca3274d4da7c8499891c3`: `vendor_doc` (a text file of the
clone) or `upstream_code` (a file of the clone with the line). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| AirSimDroneEnv is a gym.Env subclass; its constructor takes ip_address, image_shape, env_config and input_mode and connects an airsim.MultirotorClient to ip_address | upstream_code | scripts/airsim_env.py:11-17 |
| The action space is a two-element Box with low -0.6, high 0.6 and dtype float32 | upstream_code | scripts/airsim_env.py:28-29 |
| The observation space is Box(0, 255) with dtype uint8; for multi_rgb its shape is (image_shape[0], image_shape[1]*3, 1), otherwise image_shape | upstream_code | scripts/airsim_env.py:19-26 |
| The environment is registered as airsim-env-v0 with entry point scripts:AirSimDroneEnv | upstream_code | scripts/__init__.py:5-8 |
| step calls do_action, get_obs and compute_reward and returns the legacy four values obs, reward, done, info | upstream_code | scripts/airsim_env.py:36-40 |
| do_action sends moveByVelocityBodyFrameAsync(0.4, action[0], action[1], duration=1) and then moveByVelocityAsync(0, 0, 0, duration=1) | upstream_code | scripts/airsim_env.py:87-91 |
| The AirSim duration argument is in seconds | upstream_code | scripts/airsim/client.py:1027 |
| setup_flight resets the drone, enables API control, arms it, commands moveToZAsync(-1, 1), stores the collision timestamp, chooses a random section, and sets the pose with y_pos and z_pos from ((np.random.rand(1,2)-0.5)*2) | upstream_code | scripts/airsim_env.py:50-76 |
| The alignment reward is exp(-target_dist_curr_3d)*30; a collision or a lost hole gives -100 and done, and travelling more than 3.7 gives done | upstream_code | scripts/airsim_env.py:122-148 |
| is_collision compares the current simGetCollisionInfo().time_stamp with the timestamp stored at setup | upstream_code | scripts/airsim_env.py:152-154 |
| get_obs for depth requests a DepthPerspective image, clips values above 3.4 and scales the clipped value by 255/3.4 | upstream_code | scripts/airsim_env.py:111-113 |
| The README gives the input sizes as 50 x 50 x 1 for depth, 50 x 50 x 3 for single RGB and 50 x 150 x 1 for stacked gray | vendor_doc | README.md:30-32 |
| The README says the project currently runs only on Windows because the Unreal environments are packaged for Windows | vendor_doc | README.md:8 |
| The README says the training scene is a separately downloaded TrainEnv.zip and its executable must be opened before training | vendor_doc | README.md:165-171 |
| The pinned requirements use gym==0.21.0 | upstream_code | requirements.txt:11 |
| config.yml sets train_mode and test_mode to multi_rgb | upstream_code | config.yml:1-3 |
| train.py builds image_shape (50,50,1) for depth and (50,50,3) otherwise and calls gym.make('scripts:airsim-env-v0', ip_address='127.0.0.1', image_shape=..., env_config=..., input_mode=...) | upstream_code | train.py:21-33 |
| The README's settings.json configures a 50 x 50 camera with FOV_Degrees 120 and ClockSpeed 40 | vendor_doc | README.md:119-158 |

Limits: the driver declares no `Limit` of its own. The only bound is the action space, which the bridge derives
from the environment: each element of `action.values` has minimum -0.6 and maximum 0.6, with source
`upstream_code` and the reference `scripts/airsim_env.py:28-29`, where the class states the space. `ticks` is
bounded by the bridge's `max_ticks` default (1 to 10000), which is an SDK configuration value, not a device limit.
The device is simulated (R0), so no limit is `operator_required` and there is no `site-limits.example.json`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic:drl-nav-corridor`, level F0 (a kinematic
corridor: the agent moves by the commanded body-frame velocity for the 1 s command period, with no Unreal
renderer, no AirSim physics and no contact, actuator, sensor or noise model), determinism `seeded` with
`seed_control` `parameter`, timestep 1000 ms (one 1 s velocity command, `scripts/airsim_env.py:87-88` and
`scripts/airsim/client.py:1027`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore.
The gaps say the external Windows Unreal/AirSim scene was not run, the fake was never compared with it, the
depth image is synthetic, the AirSim physics timestep is not in the clone, snapshots are absent, and the fake's
`reset` options (`start`, `target`, `sections`) are test conveniences that `AirSimDroneEnv.reset` does not have.
The driver sets `autoreset = True`: a step that follows a terminal state starts a new episode through the bridge,
where the upstream class expects the caller to call `reset()` itself (`scripts/airsim_env.py:42-45`).
The fake returns the full configured 50 x 50 x 1 depth array (`train.py:22-24`), not a reduced array, so no
array is NOT COVERED.

Safety: simulated R0 device with no hardware backend. The e-stop is the runtime's software latch (the
environment has no native stop): after it no step or reset is accepted until `mhs.safety.reset` clears the
latch, and the world state stays readable. There is no `estop_physical_ref` because there is no machine.

Tags: drone, uav, navigation, reinforcement-learning, simulation, airsim, legacy-gym, corridor
