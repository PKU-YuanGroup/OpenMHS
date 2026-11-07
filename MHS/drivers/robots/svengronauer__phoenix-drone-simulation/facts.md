OpenMHS is not affiliated with, endorsed by, or a reimplementation of Anthropic's MHS research preview.

# Facts and tags for gh.svengronauer/phoenix-drone-simulation

Every fact cites its source at commit `c5d690732976351f5bbea4161913d98c376a4f04`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| DroneHoverSimpleEnv-v0 is the hover task with PWM control at 100 Hz, simple physics, 100 Hz observations, 10% domain randomization, no aerodynamic effects and instant motor force | vendor_doc | README.md:30 |
| DroneHoverSimpleEnv-v0 is registered with max_episode_steps=500 | upstream_code | phoenix_drone_simulation/__init__.py:9-11 |
| The CrazyFlie agent has four control channels (act_dim=4) | upstream_code | phoenix_drone_simulation/envs/agents.py:134 |
| The action space bounds each of the four control channels to [-1, 1] | upstream_code | phoenix_drone_simulation/envs/base.py:148-150 |
| The observation history keeps two (observation, action) pairs | upstream_code | phoenix_drone_simulation/envs/base.py:44 |
| The observation space is a Box bounded by +-1000 whose width is the history length times the observation plus action width | upstream_code | phoenix_drone_simulation/envs/base.py:143-149 |
| With observation noise enabled, the observation concatenates position, quaternion, linear velocity and angular rate | upstream_code | phoenix_drone_simulation/envs/hover.py:159 |
| The hover target is the position [0, 0, 1.0] | upstream_code | phoenix_drone_simulation/envs/hover.py:14 |
| The hover episode terminates when roll or pitch passes 60 degrees, altitude falls below 0.2 m or an angular rate passes 300 degrees per second | upstream_code | phoenix_drone_simulation/envs/hover.py:93-100 |
| The terminal penalty defaults to 100 | upstream_code | phoenix_drone_simulation/envs/hover.py:21 |
| The reward is minus the Euclidean distance to the target minus the action, angle, spin, velocity and terminal penalties | upstream_code | phoenix_drone_simulation/envs/hover.py:169-186 |
| A reset draws a position offset of +-0.25 m, roll and pitch of +-pi/6 rad, yaw of +-2pi rad, linear velocity of +-0.1 m/s and angular rate of +-200 deg/s (yaw +-20 deg/s) | upstream_code | phoenix_drone_simulation/envs/hover.py:200-228 |
| reset accepts a seed keyword but the body does not read it | upstream_code | phoenix_drone_simulation/envs/base.py:382-429 |
| The initial state is drawn with numpy's global random generator through np.random.uniform and np.random.normal | upstream_code | phoenix_drone_simulation/envs/hover.py:200-228 |
| Observation noise is enabled by default (observation_noise=1) | upstream_code | phoenix_drone_simulation/envs/hover.py:12 |
| Domain randomization defaults to 0.10 | upstream_code | phoenix_drone_simulation/envs/hover.py:13 |
| The simple hover environment uses SimplePhysics with the cf21x_sys_eq drone model and sim_freq=100 Hz | upstream_code | phoenix_drone_simulation/envs/hover.py:258-263 |
| The physics timestep is 1/SIM_FREQ | upstream_code | phoenix_drone_simulation/envs/base.py:98 |

Limits: The checked fake keeps four action values in -1..1. The Gymnasium bridge derives these unchanged action bounds with source `upstream_code` and ref `phoenix_drone_simulation/envs/base.py:148-150`, where the same-span ones assignment and Box construction state the bounds. The selected environment and width were source-reviewed separately; symbolic shapes alone do not prove a width. `ticks` remains the SDK bridge budget (1 to max_ticks, 10000 by default), not a device limit. This simulated R0 package declares no operator-required hardware limit.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:DroneHoverSimpleEnv-v0`, level F1 (simplified
rigid-body equations, no contacts, drag, ground effect or motor dynamics), determinism `seeded` with
`seed_control` `parameter`, timestep 10 ms (100 Hz, hover.py:263 and base.py:98), `realtime_factor` 0, clock
`lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled, that the fake uses
`random.Random(seed)` while upstream ignores seed, and that the fake was not compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: drone, quadrotor, crazyflie, reinforcement-learning, simulation, gymnasium

The card also lists DroneHoverBulletEnv, DroneTakeOffSimpleEnv, DroneTakeOffBulletEnv, DroneCircleSimpleEnv and
DroneCircleBulletEnv. This package serves only DroneHoverSimpleEnv-v0, the first confirmed entry symbol; serve another
by changing `env_id`, `native`, the facts and the fake.
