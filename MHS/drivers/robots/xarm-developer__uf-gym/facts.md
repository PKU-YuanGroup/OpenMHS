# Facts and tags for gh.xarm-developer/uf-gym

Every fact cites its source at commit `5d93e0419193bfed8a7cefc7bbe9b045a650f049`: `vendor_doc` (a text file of the
clone, here README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository adds UFACTORY robot model support to panda-gym training and simulation tools for reinforcement learning | vendor_doc | README.md:3 |
| pybullet and panda-gym are prerequisites of the repository | vendor_doc | README.md:11-12 |
| The scripts add a sibling ../panda-gym checkout to sys.path, so panda-gym is external to this repository | upstream_code | test_xarm6_reach.py:3 |
| Only xArm6 and xArm7 (with gripper) are supported currently | vendor_doc | README.md:27 |
| uf_gym registers each XArm6*-v3 id on import, with entry_point uf_gym.envs:XArm6{task}Env and max_episode_steps 50, or 100 for the Stack task | upstream_code | uf_gym/__init__.py:13-20 |
| The same registration loop also creates the XArm7*-v3 ids, with entry_point uf_gym.envs:XArm7{task}Env and the same 50/100-step limit | upstream_code | uf_gym/__init__.py:24-31 |
| XArm6Reach-v3 is registered on the sparse/ee iteration: the loop visits sparse before dense and ee before joints, and those two choices add no suffix to the id | upstream_code | uf_gym/__init__.py:8-13 |
| XArm6ReachEnv is the entry class of XArm6Reach-v3 | upstream_code | uf_gym/envs/uf_tasks/xarm6_tasks.py:167 |
| XArm6ReachEnv builds a PyBullet simulation, creates an XArm6 with block_gripper=True at base position [-0.5, 0.0, 0.0], and attaches a Reach task that uses the robot's end-effector position | upstream_code | uf_gym/envs/uf_tasks/xarm6_tasks.py:201-203 |
| With control_type 'ee' the XArm6 action has three arm dimensions, and the gripper adds one unless block_gripper is true; the action space is Box(-1.0, 1.0, shape=(n_action,), dtype=np.float32) | upstream_code | uf_gym/envs/uf_robots/xarm6.py:32-34 |
| set_action clips every action to the action space before using it | upstream_code | uf_gym/envs/uf_robots/xarm6.py:56 |
| An end-effector action is scaled by 0.05 m per unit before inverse kinematics | upstream_code | uf_gym/envs/uf_robots/xarm6.py:85 |
| The target end-effector height is clipped at z=0 | upstream_code | uf_gym/envs/uf_robots/xarm6.py:90 |
| With the gripper blocked, the neutral pose is the six arm angles 0.0, -1.103210210442149, -0.5245520784266224, 0.0, 1.62760333106346, 0.0 rad and the end-effector is link 6 | upstream_code | uf_gym/envs/uf_robots/xarm6.py:46-47 |
| XArm6.reset sets the arm to its neutral joint values | upstream_code | uf_gym/envs/uf_robots/xarm6.py:125-127 |
| get_obs returns the end-effector position and velocity, plus the finger width when the gripper is not blocked | upstream_code | uf_gym/envs/uf_robots/xarm6.py:113-123 |
| get_ee_position and get_ee_velocity return the link position and velocity of ee_link | upstream_code | uf_gym/envs/uf_robots/xarm6.py:138-143 |
| The test script creates XArm6Reach-v3 with gymnasium.make and drives it through reset, step, render and close | upstream_code | test_xarm6_reach.py:24-40 |

Limits: the driver declares none. The only bound is the environment's action space, which the bridge derives from the
fake's `Box(-1, 1, shape=(3,))` (`action.values` per element, with the source `upstream_code` and the ref
`uf_gym/envs/uf_robots/xarm6.py:32-34`), and `ticks` (1 to `max_ticks`, 10000 by default). The device is simulated
(R0), so no limit is `operator_required`. The fake's `Box` is the one the clone states (`xarm6.py:34`;
`block_gripper=True` makes the three dimensions, `xarm6_tasks.py:202` and `xarm6.py:32-33`).

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:XArm6Reach-v3`, level F0 (the checked
deployment is the analytic kinematic fake, not the upstream PyBullet dynamics), determinism `seeded` with
`seed_control` `parameter`, timestep 0 ms (the clone states no PyBullet physics timestep; the fake models discrete
transitions), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not
modelled: no rigid-body dynamics, contacts or actuators; no wall-clock pacing; a flat placeholder observation; a
placeholder reward, goal range and success radius; and no validation against hardware.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the state stays readable.

Tags: ufactory, xarm6, reach, panda-gym, pybullet, reinforcement-learning, simulation, gymnasium

## Other entry symbols of the card

The task card lists four entry symbols. This package serves the first one,
`uf_gym.envs.uf_tasks.xarm6_tasks:XArm6ReachEnv` (the `XArm6Reach-v3` environment). The other three are named here
and are not bound by this package: `uf_gym.envs.uf_tasks.xarm7_tasks:XArm7PickAndPlaceEnv` (line 67),
`uf_gym.envs.uf_robots.xarm6:XArm6` (line 11) and `uf_gym.envs.uf_robots.xarm7:XArm7` (line 11). The registration
loop also creates XArm6 and XArm7 ids for the other tasks and control types (`uf_gym/__init__.py:7-31`); each would
be a separate environment with its own action space and task reward.
