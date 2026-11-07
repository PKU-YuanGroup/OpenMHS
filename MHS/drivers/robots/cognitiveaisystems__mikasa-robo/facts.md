# Facts and tags for gh.cognitiveaisystems/mikasa-robo

Every fact cites its source at commit `509b875f3d207c287497c0a897661062de928bb0`: `vendor_doc` (documentation text of
the clone such as `docs/source/observation_space.rst`) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are
written into `driver.py` (`facts = [...]`); `reference.json` is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| BunchOfColors3-v0 is registered by @register_env with max_episode_steps=120 | upstream_code | mikasa_robo_suite/rl/memory_envs/bunch_of_colors.py:381 |
| The abstract BunchOfColorsEnv defaults SEQUENCE_LENGTH to 5 | upstream_code | mikasa_robo_suite/rl/memory_envs/bunch_of_colors.py:25 |
| BunchOfColors3Env sets SEQUENCE_LENGTH = 3 | upstream_code | mikasa_robo_suite/rl/memory_envs/bunch_of_colors.py:383 |
| The environment supports the panda and panda_wristcam robots and defines nine colors | upstream_code | mikasa_robo_suite/rl/memory_envs/bunch_of_colors.py:19-20 |
| An episode draws SEQUENCE_LENGTH unique colors from the nine with the episode RNG | upstream_code | mikasa_robo_suite/rl/memory_envs/bunch_of_colors.py:102-105 |
| The robot qpos is a nine-element vector and its last two entries are handled as the gripper | upstream_code | mikasa_robo_suite/rl/memory_envs/bunch_of_colors.py:184-188 |
| In state mode the observation extras are tcp_pose, obj_to_goal_pos, oracle_info and, for each cube in the scene, its pose and its touch/sequence/next-target flags | upstream_code | mikasa_robo_suite/rl/memory_envs/bunch_of_colors.py:324-336 |
| The environment's step delegates to BaseEnv.step and returns its five values unchanged | upstream_code | mikasa_robo_suite/rl/memory_envs/bunch_of_colors.py:339-342 |
| The dense reward combines reaching, 0.5*static, correct-touch and wrong-touch terms, is scaled by active_phase and set to 100 on success | upstream_code | mikasa_robo_suite/rl/memory_envs/bunch_of_colors.py:346-361 |
| compute_normalized_dense_reward divides the dense reward by 100 | upstream_code | mikasa_robo_suite/rl/memory_envs/bunch_of_colors.py:376-378 |
| The default sensors are a 128x128 base_camera and a 512x512 render_camera | upstream_code | mikasa_robo_suite/rl/memory_envs/bunch_of_colors.py:61-69 |
| The environment's SimConfig sets only GPU memory capacities, not a physics or control timestep | upstream_code | mikasa_robo_suite/rl/memory_envs/bunch_of_colors.py:53-59 |
| ManiSkill's BaseEnv is imported from mani_skill.envs.sapien_env, so reset, the spaces and close are inherited outside the clone | upstream_code | mikasa_robo_suite/rl/memory_envs/bunch_of_colors.py:6 |
| The clone documents the Panda pd_ee_delta_pose action as seven values, each in [-1, 1]: xyz, rpy and the gripper command | vendor_doc | docs/source/observation_space.rst:147-172 |
| The documented proprioception is seven values: absolute TCP xyz with no finite clamp, roll/pitch/yaw and the gripper opening in [0.0, 0.08] m | vendor_doc | docs/source/observation_space.rst:107-131 |
| The clone pins gymnasium 0.29.1, mani_skill 3.0.0b15, numpy 1.23.5 and torch 2.2.1 and requires Python >=3.9,<3.12 | upstream_code | pyproject.toml:10-32 |

Limits: the driver declares no explicit `Limit`. The action bound is derived by the Gymnasium bridge from the
environment's action space: this driver serves the documented normalized `pd_ee_delta_pose` action, seven values in
`[-1, 1]` (`docs/source/observation_space.rst:147-172`), because `env_kwargs` selects that controller. The bridge also
bounds `ticks` by its `max_ticks` (1 to 10000). The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:BunchOfColors3-v0`, level F0 (kinematic/analytic:
the fake integrates the documented action mapping; it models no rigid body, robot, scene, sensor or reward),
determinism `seeded` with `seed_control` `parameter`, timestep 0 (the clone states no physics or control timestep,
`bunch_of_colors.py:53-59`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say
what is not modelled and that the fake was never compared with the upstream environment.

Safety: simulated R0 device. The upstream class is a ManiSkill environment, not a machine; there is no hardware backend.
The e-stop is the runtime's software latch: after it no step or reset is accepted until `mhs.safety.reset` clears the
latch, and the recorded world state stays readable.

Tags: mikasa-robo, memory-task, manipulation, reinforcement-learning, simulation, gymnasium
