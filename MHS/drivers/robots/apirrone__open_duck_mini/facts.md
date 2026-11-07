# Facts and tags for gh.apirrone/open_duck_mini

Every fact cites its source at commit `b23317a485b3cec7d8417f352478778b3475173c`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md) or `upstream_code` (a Python/XML file of the clone). The same facts are
written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| BDX_env is registered with entry point env_humanoid:BDXEnv, max_episode_steps=None (formerly 500) and autoreset=True | upstream_code | experiments/RL/train.py:129-134 |
| The observation space is a Box of 41 float64 values with no finite lower or upper bound | upstream_code | experiments/RL/env_humanoid.py:92 |
| The healthy base height range is 0.1 to 0.2 metres | upstream_code | experiments/RL/env_humanoid.py:97 |
| The episode terminates when the base is unhealthy or its local z-axis is not upright | upstream_code | experiments/RL/env_humanoid.py:140-145 |
| The reward weights are forward_reward_weight 1.25, ctrl_cost_weight 0.3 and healthy_reward 5.0 | upstream_code | experiments/RL/env_humanoid.py:99-101 |
| The environment runs 5 MuJoCo physics steps per environment step (frame_skip 5) | upstream_code | experiments/RL/env_humanoid.py:103-109 |
| The reward is healthy_reward minus ctrl_cost (0.3 times the sum of squared controls) minus moving_cost (twice the absolute x velocity) | upstream_code | experiments/RL/env_humanoid.py:157-165 |
| The observation concatenates the joint positions, the joint velocities and the left then right foot contact flags | upstream_code | experiments/RL/env_humanoid.py:210-216 |
| A reset adds uniform noise between -0.01 and 0.01 to the initial positions and velocities | upstream_code | experiments/RL/env_humanoid.py:181-189 |
| The BDX model defines 15 position actuators: five per leg plus neck_pitch, head_pitch, head_yaw and the two antennas | upstream_code | mini_bdx/robots/bdx/robot.xml:284-298 |
| The base body starts at height z=0.17 metres | upstream_code | mini_bdx/robots/bdx/robot.xml:69 |
| The scene's timestep option is commented out (the comment says 100 Hz), so the clone states no active physics timestep | upstream_code | mini_bdx/robots/bdx/scene.xml:2-3 |
| The environment declares render_fps 100 in its metadata | upstream_code | experiments/RL/env_humanoid.py:81-88 |
| Open Duck Mini is about 42 centimetres tall with its legs extended | vendor_doc | README.md:11 |

Limits: the driver declares none. The action space is derived by the bridge from the fake environment's Box, and
the real box is built by gymnasium's external `MujocoEnv`, which the clone does not state: the fake's boundaries
are placeholder test data, not a sourced device limit. The `ticks` bound (1 to 10000) and the `seed` minimum (0)
are class/schema bounds of `cap.world.*`, not device limits. No input needs an operator-required bound: this is a
simulated R0 world, and no hardware channel is exposed.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:BDX_env`, level F0 (kinematic stand-in: no
dynamics, contacts, actuator or sensor model), determinism `seeded` with `seed_control` `parameter`,
`timestep_ms` 0 (the clone states no active physics timestep and the fake is event-driven), `realtime_factor` 0,
clock `lockstep`, `reset` `full`, no snapshot/restore. The gaps say what is not modelled, that the declared
41-value observation corresponds to 13 joints while the pinned model has 15 (45 values) so neck_pitch and the two
antenna actuators are NOT COVERED, and that the upstream environment was not run.

Other entry symbols of the card, not implemented here (one package implements one device class): `simple_env:BDXEnv`
(`experiments/RL/new/simple_env.py:12`), `footsteps_env:BDXEnv` (`experiments/RL/new/footsteps_env.py:14`) and
`env:BDXEnv` (`experiments/RL/env.py:43`, registered from `experiments/RL/pretrain_dbrm.py:19`). Two further
`BDXEnv` classes exist in the clone but are not on the card: `experiments/RL/new/env.py:9` and
`experiments/RL/new/placo_imitate_env.py:15`.

Safety: simulated R0 device (`world.sim`). There is no hardware backend and no native stop; an e-stop is the
runtime's software latch, after which every step and reset is refused until `mhs.safety.reset` clears the latch,
and the environment state stays readable.

Tags: bdx, gymnasium, legged-robot, mujoco, open-duck-mini, reinforcement-learning, simulation
