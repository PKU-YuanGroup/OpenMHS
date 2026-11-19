# Facts and tags for gh.lightwheelai/leisaac

Every fact cites its source at commit `24d3bcd3f1e4585740fc79921782c41617237812`: `upstream_code` is code or a
comment of the clone, and the ref is `path/in/clone:LINE`. The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page. References under
`dependencies/IsaacLab` are read at gitlink `3c6e67bb5c7ada942a6d1884ab69338f57596f77`, not as parent-tree files.
That submodule's `VERSION` is 2.3.0 and its `LICENSE:1-5` states BSD-3-Clause; the parent is Apache-2.0.

| fact | source | ref |
|---|---|---|
| LeIsaac registers LeIsaac-SO101-PickOrange-Direct-v0 with entry point leisaac.tasks.pick_orange.direct.pick_orange_env:PickOrangeEnv and config PickOrangeEnvCfg | upstream_code | source/leisaac/leisaac/tasks/pick_orange/__init__.py:21-27 |
| PickOrangeEnv is a concrete direct task: it adds six subtask observations and implements _check_success with mdp.task_done | upstream_code | source/leisaac/leisaac/tasks/pick_orange/direct/pick_orange_env.py:61-90 |
| The single-arm direct task declares action_space = 6 | upstream_code | source/leisaac/leisaac/tasks/template/direct/single_arm_env.py:33 |
| IsaacLab converts an integer space specification to Box(low=-inf, high=inf, shape=(spec,)) | upstream_code | dependencies/IsaacLab/source/isaaclab/isaaclab/envs/utils/spaces.py:30-32 |
| The single-arm joint order is shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll, gripper | upstream_code | source/leisaac/leisaac/utils/constant.py:27 |
| Each action is multiplied by the configured action_scale and written as the robot joint position target | upstream_code | source/leisaac/leisaac/tasks/template/direct/single_arm_env.py:129-134 |
| The direct task sets action_scale = 1.0 | upstream_code | source/leisaac/leisaac/tasks/template/direct/single_arm_env.py:49 |
| The base observation_space dictionary declares joint_pos (6), actions (6) and joint_pos_target (6) | upstream_code | source/leisaac/leisaac/tasks/template/direct/single_arm_env.py:33-47 |
| The front and wrist cameras are 640 x 480 RGB cameras | upstream_code | source/leisaac/leisaac/tasks/template/single_arm_env_cfg.py:50-83 |
| The policy observation group carries joint_pos, joint_vel, joint_pos_rel, joint_vel_rel, actions, ee_frame_state, joint_pos_target and the RGB camera images | upstream_code | source/leisaac/leisaac/tasks/template/direct/single_arm_env.py:136-152 |
| PickOrangeEnv adds the six subtask_terms observations for picking and placing each orange | upstream_code | source/leisaac/leisaac/tasks/pick_orange/direct/pick_orange_env.py:66-83 |
| The direct env reward is 0.0 | upstream_code | source/leisaac/leisaac/tasks/template/direct/single_arm_env.py:154-155 |
| The episode times out when episode_length_buf >= max_episode_length - 1 unless never_time_out is set | upstream_code | source/leisaac/leisaac/tasks/template/direct/single_arm_env.py:162-165 |
| The direct task sets decimation = 1 and episode_length_s = 25.0 | upstream_code | source/leisaac/leisaac/tasks/template/direct/single_arm_env.py:64-65 |
| The default simulation timestep is 1/60 s | upstream_code | dependencies/IsaacLab/source/isaaclab/isaaclab/sim/simulation_cfg.py:346 |
| max_episode_length is ceil(episode_length_s / (sim.dt * decimation)) | upstream_code | dependencies/IsaacLab/source/isaaclab/isaaclab/envs/direct_rl_env.py:264-267 |
| never_time_out, manual_terminate, auto_terminate and return_success_status default to False | upstream_code | source/leisaac/leisaac/enhance/envs/direct_rl_env_cfg.py:14-20 |
| The task succeeds only when every orange is within x/y (-0.10, 0.10) and height (-0.07, 0.07) of the plate, and the arm is at its rest pose | upstream_code | source/leisaac/leisaac/tasks/pick_orange/mdp/terminations.py:14-56 |
| The reset signature is reset(seed=None, options=None) | upstream_code | source/leisaac/leisaac/enhance/envs/direct_rl_env.py:117 |
| step takes a torch tensor, moves it to self.device and returns obs_buf, reward_buf, reset_terminated, reset_time_outs and extras | upstream_code | source/leisaac/leisaac/enhance/envs/direct_rl_env.py:32-115 |
| step resets terminated or timed-out environments before collecting the returned observations | upstream_code | source/leisaac/leisaac/enhance/envs/direct_rl_env.py:82-107 |
| SO101Leader constructs a FeetechMotorsBus with port=self.port and calls connect in its constructor | upstream_code | source/leisaac/leisaac/devices/lerobot/so101_leader.py:36-51 |
| The pinned IsaacLab submodule states SPDX-License-Identifier BSD-3-Clause | vendor_doc | dependencies/IsaacLab/LICENSE:1-5 |
| The upstream package requires Python >=3.10 | upstream_code | source/leisaac/pyproject.toml:21 |
| The isaaclab extra pins isaaclab[isaacsim,all]==2.3.0 | upstream_code | source/leisaac/pyproject.toml:41 |

Limits: the isolated R0 fake preserves the upstream unbounded six-value `Box`: the task declares action_space 6,
and the pinned IsaacLab `envs/utils/spaces.py:30-32` maps an integer specification to an unbounded Box.
No finite device bound is invented. `fixtures/operator-limits.example.json` is an optional operator overlay
demonstrating finite bounds for the fake; it is neither a device limit nor a deployment default. The bridge also
bounds `ticks` from 1 to `max_ticks` (10000 by default).

Fidelity contract: the upstream simulator is described at F1 (Isaac Lab/PhysX rigid-body dynamics with contacts) in
`driver.py` `fidelity`; the deployed `fake` backend overrides this with the analytic F0 contract in
`fidelity_by_backend`: timestep 1/60 s (16.6667 ms), determinism seeded with the seed as a reset parameter,
`realtime_factor` 0, lockstep clock, full reset, no snapshot. The fake gaps list the missing dynamics, the 4 x 4 x 3
image stand-ins for the real 640 x 480 x 3 cameras, the single-environment Python RNG, the absent task-success
termination, the difference between the upstream cfg-derived observation_space and the actual 'policy' plus
'subtask_terms' observation, and the fact that neither the upstream environment nor the sim backend was run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (there is no native stop and no hardware to
stop on the fake route); after it no step or world reset is accepted until `mhs.safety.reset` clears the latch,
and the state and cached targets stay readable. Releasing the latch advances no ticks. There is no pause or stop
of an external Isaac Sim application. The repository's serial `SO101Leader` connects a motor bus from its
constructor (`devices/lerobot/so101_leader.py:20-51`); that hardware path is excluded.

At a timeout, native step resets ended environments before returning observations
(`enhance/envs/direct_rl_env.py:82-107`). The fake now resets its scene stand-in on that path while retaining the
last action; its random joint offsets remain placeholders. The bridge still requires an explicit world reset
before accepting another step after the terminal receipt.

Only the fake backend is declared. The inherited generic `gymnasium.make` fallback is not a supported live
adapter: it lacks task registration, application bootstrap, cfg and numpy-to-torch/batch conversion, and the
native declared observation space differs from the observations returned. Native construction also owns a global
SimulationContext and prints to stdout; close clears its callbacks and instance
(`dependencies/IsaacLab/source/isaaclab/isaaclab/envs/direct_rl_env.py:100-116, 483-503`), and reset can wait for
textures without a timeout (`enhance/envs/direct_rl_env.py:146-148`). Those lifecycle hazards are absent from
the analytic fake and remain deployment work.

Tags: leisaac, isaaclab, so101, pick-orange, manipulation, reinforcement-learning, simulation, gymnasium
