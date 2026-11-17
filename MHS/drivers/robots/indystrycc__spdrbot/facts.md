# Facts and tags for gh.indystrycc/spdrbot

Every fact cites the clone at commit `70084cd435e9871b3db69280cce49a4fb2246664`: `upstream_code` for code and
`vendor_doc` for documentation text. The generated `reference.json` reproduces the `facts = [...]` list in
`driver.py`; this page is the human-readable copy.

| fact | source | ref |
|---|---|---|
| The package registers the Gymnasium task Template-Spdrbot3-Direct-v0 with entry point spdrbot3_env:Spdrbot3Env and the configuration spdrbot3_env_cfg:Spdrbot3EnvCfg | upstream_code | spdrbot3_direct_project/source/spdrbot3/spdrbot3/tasks/direct/spdrbot3/__init__.py:16-24 |
| Spdrbot3Env is a concrete DirectRLEnv subclass: it implements the scene setup, action application, observations, rewards, dones and reset methods | upstream_code | spdrbot3_direct_project/source/spdrbot3/spdrbot3/tasks/direct/spdrbot3/spdrbot3_env.py:20-177 |
| The environment config declares action_scale = 1, action_space = 12, observation_space = 48 and state_space = 0 | upstream_code | spdrbot3_direct_project/source/spdrbot3/spdrbot3/tasks/direct/spdrbot3/spdrbot3_env_cfg.py:53-56 |
| The environment config sets episode_length_s = 20.0 and decimation = 4 | upstream_code | spdrbot3_direct_project/source/spdrbot3/spdrbot3/tasks/direct/spdrbot3/spdrbot3_env_cfg.py:51-52 |
| The simulation config uses a timestep of 1/200 s and render_interval = 1 | upstream_code | spdrbot3_direct_project/source/spdrbot3/spdrbot3/tasks/direct/spdrbot3/spdrbot3_env_cfg.py:59-61 |
| Each action is multiplied by action_scale and added to the robot's default joint positions, then written with set_joint_position_target | upstream_code | spdrbot3_direct_project/source/spdrbot3/spdrbot3/tasks/direct/spdrbot3/spdrbot3_env.py:72-77 |
| The policy observation concatenates root linear velocity, root angular velocity, projected gravity, the commands, joint positions minus defaults, joint velocities and the actions | upstream_code | spdrbot3_direct_project/source/spdrbot3/spdrbot3/tasks/direct/spdrbot3/spdrbot3_env.py:79-98 |
| The reward is the sum of eight terms: linear velocity tracking, yaw-rate tracking, z velocity, xy angular velocity, joint torques, joint acceleration, action rate and flat orientation | upstream_code | spdrbot3_direct_project/source/spdrbot3/spdrbot3/tasks/direct/spdrbot3/spdrbot3_env.py:122-135 |
| The eight reward scales are 5.0, 0.5, -2.0, -0.05, -1e-5, -1e-7, -0.01 and -5.0 | upstream_code | spdrbot3_direct_project/source/spdrbot3/spdrbot3/tasks/direct/spdrbot3/spdrbot3_env_cfg.py:101-108 |
| An episode times out when episode_length_buf >= max_episode_length - 1, and is marked died when the maximum contact-force norm over the history on a selected die body exceeds 1.0 | upstream_code | spdrbot3_direct_project/source/spdrbot3/spdrbot3/tasks/direct/spdrbot3/spdrbot3_env.py:138-145 |
| The die body ids are arm_a_1_1, arm_a_2_1, arm_a_3_1 and arm_a_4_1 | upstream_code | spdrbot3_direct_project/source/spdrbot3/spdrbot3/tasks/direct/spdrbot3/spdrbot3_env.py:37 |
| A full reset resets the robot and the environment buffer, clears the actions, samples the three commands uniformly from -1.0 to 1.0, and writes the default root pose, root velocity and joint state | upstream_code | spdrbot3_direct_project/source/spdrbot3/spdrbot3/tasks/direct/spdrbot3/spdrbot3_env.py:147-166 |
| The scene configures 200 environments with an environment spacing of 2.0 | upstream_code | spdrbot3_direct_project/source/spdrbot3/spdrbot3/tasks/direct/spdrbot3/spdrbot3_env_cfg.py:92 |
| The contact sensor uses a history length of 5 and an update period of 0.005 s | upstream_code | spdrbot3_direct_project/source/spdrbot3/spdrbot3/tasks/direct/spdrbot3/spdrbot3_env_cfg.py:84-89 |
| The environment config imports SPDRBOT_CFG from isaaclab_assets.robots.spdrbot | upstream_code | spdrbot3_direct_project/source/spdrbot3/spdrbot3/tasks/direct/spdrbot3/spdrbot3_env_cfg.py:19 |
| The root spdrbot.py defines SPDRBOT_CFG with the USD asset path C:/spdrbot3/spdrbot3/spdr.usd | upstream_code | spdrbot.py:11-13 |
| The root SPDRBOT_CFG lists twelve Revolute joints 110 to 121 with default positions 0.0 or 0.5 and one implicit actuator group with effort_limit 5.0, velocity_limit 1, stiffness 40.0 and damping 1.0 | upstream_code | spdrbot.py:34-84 |
| The README describes SPDR Bot as a four-legged robot designed for simulation in NVIDIA Isaac Sim and lists the URDF, USD assets and a sample control script | vendor_doc | README.md:5 |
| The direct-project README says to install Isaac Lab first and then install this project in editable mode from source/spdrbot3 | vendor_doc | spdrbot3_direct_project/README.md:15-26 |
| The setup script declares license MIT and python_requires >=3.10 | upstream_code | spdrbot3_direct_project/source/spdrbot3/setup.py:35-37 |
| The setup script's classifiers name Isaac Sim 4.5.0 | upstream_code | spdrbot3_direct_project/source/spdrbot3/setup.py:38-42 |
| The extension declares isaaclab, isaaclab_assets, isaaclab_mimic, isaaclab_rl and isaaclab_tasks as dependencies | upstream_code | spdrbot3_direct_project/source/spdrbot3/config/extension.toml:17-22 |
| The environment file header declares SPDX-License-Identifier BSD-3-Clause | upstream_code | spdrbot3_direct_project/source/spdrbot3/spdrbot3/tasks/direct/spdrbot3/spdrbot3_env.py:1-5 |
| The URDF description's LICENSE says MIT License and credits Toshinori Kitamura (2018) | vendor_doc | spyderbot_minimal URDF/SpdrBot_description/LICENSE:1-3 |
| The README says the project is open for personal and educational use and suggests attribution for published work | vendor_doc | README.md:46-48 |

Tags (short lowercase keywords): `spdrbot`, `quadruped`, `isaac-lab`, `isaac-sim`, `physx`,
`reinforcement-learning`, `simulation`, `gymnasium`.

Only the analytic fake backend is declared and checked. Its unbounded Box, one-environment batch, scalar reward
and termination flags, and 999-step timeout are fake choices; the external DirectRLEnv bounds, step/autoreset
lifecycle and max-episode calculation were not verified. The stop freezes fake stepping and calls nothing in
Isaac Sim. A live adapter would need the external runtime, an explicit cfg and the absent asset configuration.

Publication remains an owner decision: setup.py declares MIT, the environment header declares BSD-3-Clause,
the URDF description has an MIT LICENSE, and the README describes personal and educational use. The card records
NOASSERTION and requires publication review.
