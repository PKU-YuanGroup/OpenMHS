# Facts and tags for gh.physical-superintelligence-lab/simple

Every fact cites its source at commit `6d10628794d9c7de4596b4f2afb2c054a637c2bc`. The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page. The paths keep
the clone's `src/` layout. The model is the registered `simple/FrankaTabletopGraspMP-v0` environment, the Franka
tabletop grasp task and its MuJoCo simulator.

| fact | source | ref |
|---|---|---|
| simple/FrankaTabletopGraspMP-v0 is registered with entry point simple.envs.tabletop_grasp:TabletopGraspEnv and task franka_tabletop_grasp_mp | upstream_code | src/simple/envs/__init__.py:12-16 |
| BaseDualSim defaults sim_mode to mujoco_isaac and always builds MuJoCo; a mode without 'isaac' sets the Isaac Sim simulator to None | upstream_code | src/simple/envs/base_dual_env.py:41-68 |
| The environment takes action_space and observation_space from the task | upstream_code | src/simple/envs/base_dual_env.py:71-72 |
| The task's action_space is the robot controller's action space | upstream_code | src/simple/tasks/franka_tabletop_grasp_mp.py:241-244 |
| The controller action space is a Dict with one 'arm' entry | upstream_code | src/simple/robots/controllers/combo.py:24-28 |
| The arm PD joint-position controller is configured with joint1 to joint7 | upstream_code | src/simple/robots/franka_fr3.py:63-65 |
| Each arm joint action is bounded by -1.0 and 1.0 | upstream_code | src/simple/robots/controllers/qpos.py:74 |
| The Franka Research 3 robot has 9 degrees of freedom | upstream_code | src/simple/robots/franka_fr3.py:27 |
| The parallel gripper is configured with the two finger joints finger_joint1 and finger_joint2 | upstream_code | src/simple/robots/franka_fr3.py:67-70 |
| _get_obs returns agent, joint_qpos and eef_pose and merges the rendered camera frames into the observation | upstream_code | src/simple/envs/tabletop_grasp.py:83-88 |
| The observation space bounds agent and joint_qpos to -pi..pi with robot.dof entries and eef_pose to -inf..inf with 7 entries, and adds the camera spaces of the task sensor configs | upstream_code | src/simple/tasks/franka_tabletop_grasp_mp.py:247-262 |
| The task configures a 640x360 front stereo camera, a 480x270 wrist camera, a 480x270 second wrist camera and a 640x360 side camera | upstream_code | src/simple/tasks/franka_tabletop_grasp_mp.py:53-105 |
| The task metadata defaults physics_dt to 0.002 s and render_hz to 30 | upstream_code | src/simple/tasks/franka_tabletop_grasp_mp.py:41-46 |
| MujocoSimulator reads physics_dt from the task metadata | upstream_code | src/simple/engines/mujoco.py:40 |
| MujocoSimulator reads need_gravity from the task metadata and defaults it to False | upstream_code | src/simple/engines/mujoco.py:55 |
| MujocoSimulator sets the MuJoCo model timestep to physics_dt | upstream_code | src/simple/engines/mujoco.py:129-132 |
| Without need_gravity, MujocoSimulator.step advances MuJoCo from the current physics time to the end of the next render frame (render_step + 1) / render_hz using the model timestep | upstream_code | src/simple/engines/mujoco.py:64-75 |
| reset calls task.reset(seed, options), updates the MuJoCo layout, steps it once, clears step_count and _success, and returns the observation and info | upstream_code | src/simple/envs/tabletop_grasp.py:101-122 |
| step applies the action, steps MuJoCo, increments step_count, computes the reward and success, never truncates, and returns obs, reward, terminated, truncated and info | upstream_code | src/simple/envs/tabletop_grasp.py:124-140 |
| The task reward is clip((target height - initial target height) / _LIFT_HEIGHT, 0, 1) | upstream_code | src/simple/tasks/franka_tabletop_grasp_mp.py:291-297 |
| _LIFT_HEIGHT is 0.02 m | upstream_code | src/simple/tasks/franka_tabletop_grasp_mp.py:32 |
| check_success returns reward >= 1.0 | upstream_code | src/simple/tasks/franka_tabletop_grasp_mp.py:287-289 |
| Task.reset seeds the domain randomizer with dr.reset(seed=seed) unless an option carries a state_dict | upstream_code | src/simple/core/task.py:144-149 |
| close closes the MuJoCo simulator and the Isaac Sim application if it was loaded, then calls gym.Env.close | upstream_code | src/simple/envs/base_dual_env.py:126-139 |

Limits: the driver declares no `Limit` of its own. The only input bound is the action space derived by the bridge:
`action.arm` is a 7-element array in [-1.0, 1.0] per element, with the source `upstream_code` and the ref
`src/simple/robots/controllers/qpos.py:74`, and `ticks` is 1 to `max_ticks` (10000 by default) from the bridge. The
device is simulated (R0), so no limit is `operator_required`. The -1.0/1.0 values are the controller's action-space
implementation (`qpos.py:62-74`, whose comments say the joint limits still have to be read from the robot), not a
manufacturer limit, and the driver does not widen them.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:simple/FrankaTabletopGraspMP-v0`, level F1
(rigid-body dynamics with contacts; the model is the task's MuJoCo model, no actuator, sensor or noise model claimed),
determinism `seeded` with `seed_control` `parameter`, timestep 2 ms (`physics_dt = 0.002` s,
`franka_tabletop_grasp_mp.py:42`, applied at `mujoco.py:132`), `realtime_factor` 0, clock `lockstep`, reset `full`,
no snapshot and restore. The physics timestep is 2 ms, but one `env.step` advances MuJoCo to the end of the next
render frame at `render_hz` 30 (`mujoco.py:64-75`): the control period is about 33.3 ms and `ticks` count env steps.
`timestep_ms` names the physics timestep per FID-015; the package has no `operating_notes` field, so the control
period is disclosed in the fidelity `gaps`. The gaps also say what is not modelled, that the fake is not MuJoCo, the
real camera sizes it omits, and that the fake was not compared with the upstream environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the last observation and fake state stay readable.
No hardware backend is declared, so a model-authored package never runs a hardware endpoint.

Tags: simple, franka, tabletop-grasp, mujoco, reinforcement-learning, simulation, gymnasium
