# Facts and tags for gh.simpler-env/maniskill2_real2sim

Every fact cites its source at commit `ef7a4d4fdf4b69f2c2154db5b15b9ac8dfe10682`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The default robot is google_robot_static | upstream_code | mani_skill2_real2sim/envs/custom_scenes/base_env.py:49-51 |
| The static Google robot's default control mode is arm_pd_ee_delta_pose_align_interpolate_by_planner_gripper_pd_joint_target_delta_pos_interpolate_by_planner | upstream_code | mani_skill2_real2sim/agents/robots/googlerobot.py:207-211 |
| The arm pose controller builds a six-element Box: three position deltas and three rotation deltas | upstream_code | mani_skill2_real2sim/agents/controllers/pd_ee_pose.py:161-178 |
| The arm controller config passes pos_lower -1.0, pos_upper 1.0 and rot_bound np.pi / 2 | upstream_code | mani_skill2_real2sim/agents/configs/google_robot/defaults.py:168-176 |
| The selected arm explicitly disables normalization and keeps its rotation Box bounds | upstream_code | mani_skill2_real2sim/agents/configs/google_robot/defaults.py:177-201 |
| The controller normalizes its action space when normalize_action is true | upstream_code | mani_skill2_real2sim/agents/base_controller.py:51-54 |
| The action normalizer is Box(-1, 1) with the original shape and dtype | upstream_code | mani_skill2_real2sim/utils/common.py:121-123 |
| The gripper uses PDJointPosMimicControllerConfig with normalize_action=True | upstream_code | mani_skill2_real2sim/agents/configs/google_robot/defaults.py:291-307 |
| CombinedController flattens the arm and gripper spaces into one Box | upstream_code | mani_skill2_real2sim/agents/base_controller.py:253-260 |
| GraspSingleCokeCanInScene-v0 is registered with max_episode_steps=80 and the model_ids list ['coke_can'] | upstream_code | mani_skill2_real2sim/envs/custom_scenes/grasp_single_in_scene.py:613-617 |
| register_env notes that gym.make wraps the environment with a TimeLimit to limit the maximum number of steps | upstream_code | mani_skill2_real2sim/utils/registration.py:127-130 |
| The supported observation modes are state, state_dict, none and image | upstream_code | mani_skill2_real2sim/envs/sapien_env.py:65 |
| The default obs_mode is the first supported mode | upstream_code | mani_skill2_real2sim/envs/sapien_env.py:146-147 |
| For obs_mode state, get_obs flattens the observation dict into one array | upstream_code | mani_skill2_real2sim/envs/sapien_env.py:255-261 |
| The agent proprioception is qpos, qvel and the controller state | upstream_code | mani_skill2_real2sim/agents/base_agent.py:173-178 |
| The static Google robot qpos is 11-dimensional | upstream_code | mani_skill2_real2sim/agents/robots/googlerobot.py:21 |
| The observation adds the robot base pose to the agent proprioception | upstream_code | mani_skill2_real2sim/envs/custom_scenes/base_env.py:344-346 |
| The task adds tcp_pose, obj_pose and tcp_to_obj_pos to the state observation | upstream_code | mani_skill2_real2sim/envs/custom_scenes/grasp_single_in_scene.py:390-398 |
| A serialized pose is its position followed by its quaternion, seven numbers | upstream_code | mani_skill2_real2sim/utils/sapien_utils.py:21-22 |
| The reward is 0.0, or 1.0 when the episode info has success | upstream_code | mani_skill2_real2sim/envs/custom_scenes/base_env.py:401-406 |
| The episode terminates when info['success'] is true | upstream_code | mani_skill2_real2sim/envs/sapien_env.py:579-580 |
| reset(seed, options) reseeds the main and episode RNGs and initializes the episode | upstream_code | mani_skill2_real2sim/envs/sapien_env.py:465-486 |
| The scene timestep is 1 / sim_freq | upstream_code | mani_skill2_real2sim/envs/sapien_env.py:620 |
| sim_freq defaults to 500 Hz and control_freq to 20 Hz | upstream_code | mani_skill2_real2sim/envs/sapien_env.py:86-87 |
| BaseEnv provides get_state and set_state for the simulation state | upstream_code | mani_skill2_real2sim/envs/sapien_env.py:674-680 |
| BaseEnv seeds its main RNG with 2022 before it constructs the environment | upstream_code | mani_skill2_real2sim/envs/sapien_env.py:185-188 |
| step_action calls scene.step and then _after_simulation_step once per simulation substep | upstream_code | mani_skill2_real2sim/envs/sapien_env.py:569-573 |
| The sim_timestep property is 1.0 / _sim_freq | upstream_code | mani_skill2_real2sim/envs/sapien_env.py:233-234 |
| _settle steps the scene int(sim_freq * t) times | upstream_code | mani_skill2_real2sim/envs/custom_scenes/base_env.py:220-224 |
| The object settles with _settle(0.5) twice and _settle(1.5) once more when it is still moving | upstream_code | mani_skill2_real2sim/envs/custom_scenes/grasp_single_in_scene.py:302-316 |
| EnvSpec.make passes the registered default keyword arguments to the environment class | upstream_code | mani_skill2_real2sim/utils/registration.py:31-34 |

Limits: the driver declares none. The only bound is the action Box, which the bridge derives from the environment
(`cap.world.step.v1` `action.values`: three position deltas in [-1.0, 1.0], three rotation deltas in [-pi/2, pi/2]
and one gripper action in [-1, 1]; no source, ref
`action_space of the fake backend .fake:FakeGraspSingleCokeCanEnv`), plus the bridge's `ticks`
bound (1 to `max_ticks`). The device is simulated (R0), so no limit is `operator_required`.

Deployment fidelity is selected per backend. The only runnable backend is the package-owned fake: engine
`python:openmhs-simplerenv-grasp-fake`, F0, seeded determinism, a 50 ms logical control tick, no wall-clock pacing,
and full fake reset. The selected arm is not normalized (`normalize_action=False` at defaults.py:180); its
rotation Box uses the float32 representation of plus/minus pi/2, and only the gripper is normalized.

`checkpoint_by_backend["fake"]` explicitly opts into `json_state_v1`, with a 65536-byte whole-world bound.
Its checkpoint includes the fake observation, episode count/flags, fixed model identity, and Python Random state.
A deliberate version 3 codec preserves the RNG word vector, index and Gaussian cache. It validates the complete
payload before committing and supports later unseeded-reset continuation. This is the fake's own data, not a
SAPIEN checkpoint or proof of native exact determinism. The stock endpoint additionally preserves public world
state, pending seed and identity/hash integrity; its lifetime step budget cannot be restored from a checkpoint.
Python's primary documentation describes the getstate/setstate contract:
https://docs.python.org/3/library/random.html#random.getstate; the explicit version 3 shape is in
https://github.com/python/cpython/blob/v3.14.0/Lib/random.py#L163-L171. The 624-word vector and final index are
defined in https://github.com/python/cpython/blob/v3.14.0/Modules/_randommodule.c#L383-L455 (N=624 at line82).

The full seven-axis grasp task is declared for live use through `.sim:connect` (not run). It imports nothing until
the sim backend opens, then builds the registered task class with its registered default keyword arguments and the
registered 80-step TimeLimit (`utils/registration.py:31-34,64-116,154-160`; gymnasium's OrderEnforcing wrapper is not
added). SAPIEN exposes no physics clock to this code, so `sim.py` subclasses the task and counts every completed
`scene.step()` at the only two integration sites: the control substeps (`envs/sapien_env.py:569-573`, through the
`_after_simulation_step` hook) and the reset's settling loop (`envs/custom_scenes/base_env.py:220-224`, re-stated with
a counter). `mhs_physics_clock_s` is that count times `sim_timestep` (2 ms at the 500 Hz default). The sim backend
declares `physics_ticks_v1` with 25 physics ticks per control call (`envs/sapien_env.py:137-143`) and a reset that
integrates physics: `reset_clock` "continue" and at most 1,250 settling ticks (250 + 250 + 750 at 500 Hz,
`envs/custom_scenes/grasp_single_in_scene.py:302-316`). The SDK measures each reset's ticks and reports them in the
reset receipt (`reset_integrated_ticks`), never as episode ticks; a reset that settles beyond the bound, or off the
2 ms grid, is a timing fault that refuses further steps until a verified reset. A 50 ms native control call is never
presented as one physics tick. The optional prepackaged configuration uses other frequencies and is not this default.

Native `get_state` returns an ndarray of actor/articulation state only (`envs/sapien_env.py:653-680`). It omits
main/episode RNG, elapsed-step counters, grasp/lift success statistics, controller state and the TimeLimit wrapper.
See `envs/sapien_env.py:469-505`, `envs/custom_scenes/grasp_single_in_scene.py:401-452`,
`agents/base_agent.py:180-208` and `utils/registration.py:108-114`. The sim backend therefore opts out of protocol snapshots
explicitly (`checkpoint_by_backend["sim"] = {"profile": "none", ...}`); a future live checkpoint adapter must
preserve those semantics and an explicit reversible native representation; method presence alone is not evidence.

Not established: SAPIEN, the asset tree and the upstream package were not installed, so the counter, the settling
bound, the TimeLimit construction and native trajectories were not run; the counter is tested only against a stand-in
with the same integration structure. Fake contract tests and fake snapshot continuation do not validate the native
environment or hardware. No scope was reduced to observation-only control;
step, reset, seed and the full action dimensions remain present. Only the fixed fake configuration is supported;
nonempty fake constructor/reset options are refused instead of silently pretending to apply native options.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists). After it no new
step or reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that). A native
step or reset that is already running cannot be interrupted: it completes (a multi-step command stops at the next
control call; a live reset may settle for up to 1,250 physics ticks), and while it runs the bridge never reports the
safe state; the endpoint's e-stop waits for it at most its budget and otherwise answers `SAFE_STATE_UNREACHED` and
keeps retrying in the background. The world state stays readable.

Tags: maniskill2, real2sim, simplerenv, grasping, simulation, gymnasium
