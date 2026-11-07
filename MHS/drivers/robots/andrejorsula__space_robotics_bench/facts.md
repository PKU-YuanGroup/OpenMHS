# Facts and tags for gh.andrejorsula/space_robotics_bench

Every fact cites its source at commit `7528ff81f1ac0b34ba259b1ae150fdb4f6a90b5e`: `vendor_doc` (a text file of the
clone) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`);
the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| Space Robotics Bench is a collection of environments and tasks for robotics research in space, providing a unified framework | vendor_doc | README.md:16 |
| The simulation runs on NVIDIA Isaac Sim | vendor_doc | docs/src/README.md:7 |
| The CLI refuses to run without the omni module, requiring an environment with NVIDIA Omniverse and Isaac Sim installed | upstream_code | srb/__main__.py:37-40 |
| The CLI creates an environment with gymnasium.make(id=env_id, cfg=env_cfg, render_mode=...) | upstream_code | srb/__main__.py:208-210 |
| register_srb_tasks registers each task with gymnasium.register under the default namespace srb as f'{namespace}/{id}' | upstream_code | srb/utils/registry.py:21-27 |
| The manipulation template registers its package name and a _visual variant with Task as default_entry_point and TaskCfg as default_task_cfg | upstream_code | srb/tasks/manipulation/_manipulation/__init__.py:6-17 |
| The docs list _manipulation as a barebones template whose entry point is Task(ManipulationEnv) and whose config is TaskCfg(ManipulationEnvCfg) | vendor_doc | docs/src/getting_started/basic_usage.md:108 |
| The docs invoke the template with 'srb agent rand -e _manipulation ...' | vendor_doc | docs/src/config/robot.md:80 |
| The template environment class is Task(ManipulationEnv), constructed from a TaskCfg | upstream_code | srb/tasks/manipulation/_manipulation/task.py:53-57 |
| TaskCfg sets episode_length_s to 10.0 and is_finite_horizon to False | upstream_code | srb/tasks/manipulation/_manipulation/task.py:41-42 |
| truncate_episodes defaults to True | upstream_code | srb/core/env/common/base/env_cfg.py:132 |
| The manipulation env runs physics at env_rate 1/150 s and the agent at agent_rate 1/50 s | upstream_code | srb/core/env/manipulation/env.py:79-80 |
| The cfg sets decimation to floor(agent_rate / env_rate) and sim.dt to env_rate | upstream_code | srb/core/env/common/base/env_cfg.py:172-173 |
| The default robot of ManipulationEnvCfg is Franka | upstream_code | srb/core/env/manipulation/env.py:68 |
| The default Franka action group is a differential inverse-kinematics relative pose command with command_type pose, use_relative_mode True and scale 0.1 | upstream_code | srb/assets/robot/manipulation/franka.py:91-106 |
| The default Franka action addresses joints panda_joint1 through panda_joint7 | upstream_code | srb/assets/robot/manipulation/franka.py:95 |
| The action space is a Box with low -1.0 and high 1.0 per element, shaped by action_manager.total_action_dim | upstream_code | srb/core/env/common/base/direct/impl.py:353-357 |
| The observation is a Dict with the groups state, state_dyn, proprio and proprio_dyn | upstream_code | srb/tasks/manipulation/_manipulation/task.py:235-253 |
| The proprio group carries the end-effector position and its 6D rotation, and proprio_dyn carries the normalized robot and end-effector joint positions | upstream_code | srb/tasks/manipulation/_manipulation/task.py:245-252 |
| The end-effector rotation is converted to a 6D representation with rotmat_to_rot6d | upstream_code | srb/tasks/manipulation/_manipulation/task.py:173-174 |
| The reward sums four penalty terms: action rate, joint torque, joint acceleration and undesired robot contacts | upstream_code | srb/tasks/manipulation/_manipulation/task.py:189-221 |
| The action-rate penalty is -0.5 times the mean squared difference between the current and previous action | upstream_code | srb/tasks/manipulation/_manipulation/task.py:192-196 |
| There is no termination condition; the episode is truncated when the episode length reaches max_episode_length if truncate_episodes is true | upstream_code | srb/tasks/manipulation/_manipulation/task.py:226-233 |
| The reset randomizes the robot joints with a uniform position offset of +-5 degrees and a zero velocity range | upstream_code | srb/core/env/manipulation/env.py:54-61 |
| DirectEnv imports DirectRLEnv from isaaclab.envs, so the Gymnasium reset and step implementations come from outside the clone | upstream_code | srb/core/env/common/base/direct/impl.py:7 |
| DirectEnv.close deletes the action manager and closes the Isaac Lab environment | upstream_code | srb/core/env/common/base/direct/impl.py:136-141 |

Limits: the driver declares none of its own. The bridge derives the action bound from the fake's action Box, which
copies the upstream `low=-1.0` and `high=1.0` per element (`srb/core/env/common/base/direct/impl.py:354-355`); the
number of elements is the upstream `action_manager.total_action_dim` (`:356`), seven in the default configuration: six
for the Franka's relative pose command (`srb/assets/robot/manipulation/franka.py:91-106`) and one for the binary
gripper command of its FrankaHand (`srb/assets/object/tool/franka_hand.py:53-61`), which
`srb/core/env/common/base/env_cfg.py:761-778` adds to the action group. `action_space_ref` cites
`srb/core/env/common/base/direct/impl.py:353-357`, so the derived bound is `upstream_code`. `ticks` is bounded by the
bridge's `max_ticks` (10 000 by default). The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `isaac:srb/_manipulation (kinematic fake stand-in)`, level
F0 (the fake has no dynamics; it advances joint positions directly), determinism `seeded` with `seed_control`
`parameter`, timestep 20 ms (the agent period `1/50` s, `srb/core/env/manipulation/env.py:80`, with decimation and
`sim.dt` set at `srb/core/env/common/base/env_cfg.py:172-173`), `realtime_factor` 0, clock `lockstep`, reset `full`,
no snapshot and restore. The gaps name the missing Isaac Sim physics, the reduced observation (two of the four groups,
each one vector as the upstream flattens them), the action the fake applies without inverse kinematics or the hand's
actuator, the approximate truncation and the fact that the fake was never compared with an upstream run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (the fake has no native stop); after it no step
or reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: space-robotics, isaac-sim, isaac-lab, gymnasium, manipulation, simulation, reinforcement-learning
