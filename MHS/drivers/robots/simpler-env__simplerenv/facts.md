# Facts and tags for gh.simpler-env/simplerenv

Every fact cites its source at commit `eddb5690749a1e34267807c0f7b5eede323918d7`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| GraspSingleCokeCanInScene-v0 is registered with max_episode_steps=80 and its constructor fixes model_ids to ['coke_can'] | upstream_code | ManiSkill2_real2sim/mani_skill2_real2sim/envs/custom_scenes/grasp_single_in_scene.py:613-618 |
| The default robot is google_robot_static | upstream_code | ManiSkill2_real2sim/mani_skill2_real2sim/envs/custom_scenes/base_env.py:51 |
| The static Google robot's default control mode is arm_pd_ee_delta_pose_align_interpolate_by_planner_gripper_pd_joint_target_delta_pos_interpolate_by_planner | upstream_code | ManiSkill2_real2sim/mani_skill2_real2sim/agents/robots/googlerobot.py:210-211 |
| The arm controller takes a position lower bound of -1.0, a position upper bound of 1.0 and a rotation bound of pi/2 | upstream_code | ManiSkill2_real2sim/mani_skill2_real2sim/agents/configs/google_robot/defaults.py:168-176 |
| The arm action is a Box of three position and three rotation elements built from those bounds | upstream_code | ManiSkill2_real2sim/mani_skill2_real2sim/agents/controllers/pd_ee_pose.py:161-178 |
| A controller configured with normalize_action=True receives a Box with bounds -1 and 1 | upstream_code | ManiSkill2_real2sim/mani_skill2_real2sim/utils/common.py:121-123 |
| The selected gripper controller has use_target=True and clip_target=True | upstream_code | ManiSkill2_real2sim/mani_skill2_real2sim/agents/configs/google_robot/defaults.py:291-307 |
| The combined controller flattens the controllers' Box spaces into one Box action space | upstream_code | ManiSkill2_real2sim/mani_skill2_real2sim/agents/base_controller.py:253-260 |
| A controller with use_target reports its target_qpos as its controller state | upstream_code | ManiSkill2_real2sim/mani_skill2_real2sim/agents/controllers/pd_joint_pos.py:163-166 |
| The default simulation frequency is 500 Hz and the default control frequency is 20 Hz | upstream_code | ManiSkill2_real2sim/mani_skill2_real2sim/envs/sapien_env.py:86-87 |
| The control timestep is the reciprocal of the control frequency, so 50 ms at the default 20 Hz | upstream_code | ManiSkill2_real2sim/mani_skill2_real2sim/envs/sapien_env.py:236-238 |
| step returns the observation, the reward, the terminated flag, a False truncation flag and info | upstream_code | ManiSkill2_real2sim/mani_skill2_real2sim/envs/sapien_env.py:547-555 |
| The default observation mode is state and get_obs flattens the state dict into one array | upstream_code | ManiSkill2_real2sim/mani_skill2_real2sim/envs/sapien_env.py:255-261 |
| The state observation puts the agent proprioception and the task extras under agent and extra | upstream_code | ManiSkill2_real2sim/mani_skill2_real2sim/envs/sapien_env.py:269-271 |
| The agent proprioception is qpos, qvel and the controller state | upstream_code | ManiSkill2_real2sim/mani_skill2_real2sim/agents/base_agent.py:173-178 |
| A static Google robot has 11 qpos values | upstream_code | ManiSkill2_real2sim/mani_skill2_real2sim/agents/robots/googlerobot.py:21-27 |
| The agent observation adds the robot base pose | upstream_code | ManiSkill2_real2sim/mani_skill2_real2sim/envs/custom_scenes/base_env.py:344-347 |
| The task extras add the tcp pose, the object pose and the object-minus-tcp position | upstream_code | ManiSkill2_real2sim/mani_skill2_real2sim/envs/custom_scenes/grasp_single_in_scene.py:390-399 |
| The reward is 1.0 when info['success'] is true and 0.0 otherwise | upstream_code | ManiSkill2_real2sim/mani_skill2_real2sim/envs/custom_scenes/base_env.py:401-406 |
| Success requires a grasp and lifting the object more than 0.01 above its settled height | upstream_code | ManiSkill2_real2sim/mani_skill2_real2sim/envs/custom_scenes/grasp_single_in_scene.py:434-440 |
| get_done returns info['success'], so the episode terminates when the object is lifted | upstream_code | ManiSkill2_real2sim/mani_skill2_real2sim/envs/sapien_env.py:579-580 |
| gym.make wraps the environment in a TimeLimit when max_episode_steps is set | upstream_code | ManiSkill2_real2sim/mani_skill2_real2sim/utils/registration.py:108-114 |
| A reset draws the object xy uniformly from [-0.35, -0.02] to [-0.12, 0.42] and drops it from 0.5 above the table height | upstream_code | ManiSkill2_real2sim/mani_skill2_real2sim/envs/custom_scenes/grasp_single_in_scene.py:268-277 |
| A reset draws the static Google base x from 0.30 to 0.40 and y from 0.0 to 0.2 unless the reset options give an initial xy | upstream_code | ManiSkill2_real2sim/mani_skill2_real2sim/envs/custom_scenes/base_env.py:306-311 |

Limits: the driver declares none. The only bound is the action space, which the bridge derives from the environment
(one Box of 7 elements: three position elements -1..1, three rotation elements -pi/2..pi/2 and one normalized
gripper element -1..1, with no source and the ref
`action_space of the fake backend .fake:FakeGraspSingleCokeCanEnv`), plus `ticks` (1 to `max_ticks`,
10000 by default). The device is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `simplerenv:GraspSingleCokeCanInScene-v0`, level F1,
determinism `seeded` with `seed_control` `parameter`, timestep 50 ms (control_freq 20 Hz, `sapien_env.py:86-87` and
`:236-238`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say that the
fake is a toy kinematic stand-in with the 47-number state layout and placeholder values, not SAPIEN physics, and
that it was not compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the state
stays readable.

Tags: grasp, coke-can, manipulation, reinforcement-learning, simulation, simplerenv, gymnasium
