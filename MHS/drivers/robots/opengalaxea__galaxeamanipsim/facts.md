# Facts and tags for gh.opengalaxea/galaxeamanipsim

Every fact cites its source at commit `abe7f5161eeaa150e6eaffdf443af5df7f23f356`; all are `upstream_code`. The same
facts are written into `driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this
page.

| fact | source | ref |
|---|---|---|
| R1Base-v0 is registered to galaxea_sim.envs.base.bimanual_manipulation:BimanualManipulationEnv with robot_class=R1Robot | upstream_code | galaxea_sim/envs/base/__init__.py:7-15 |
| BimanualManipulationEnv defaults to control_freq 15, timestep 0.01 s and obs_mode 'image', with obs_mode Literal['state', 'image'] | upstream_code | galaxea_sim/envs/base/bimanual_manipulation.py:14-24 |
| SapienEnv stores the timestep and sets it on the Sapien scene | upstream_code | galaxea_sim/envs/base/base.py:17-22 |
| The action space is the joint-position controller's Box(low=-inf, high=inf, shape=(action_dim,)), and action_dim is the number of left and right arm joints plus two gripper commands | upstream_code | galaxea_sim/controllers/bimanual_joint_position.py:37-42 |
| The joint-position controller takes the action as left arm targets, one left gripper target, right arm targets and one right gripper target, in that order | upstream_code | galaxea_sim/controllers/bimanual_joint_position.py:25-35 |
| step() sets the joint drive targets, runs decimation scene steps and returns observation, reward, terminated, truncated and info | upstream_code | galaxea_sim/envs/base/bimanual_manipulation.py:113-145 |
| The state observation contains upper-body joint positions and velocities, gripper positions, end-effector poses, the last joint-position commands, chassis and torso positions, the language instruction and the object dict | upstream_code | galaxea_sim/envs/base/bimanual_manipulation.py:169-223 |
| In image mode the observation adds an rgb_<camera> and a depth_<camera> array for every camera | upstream_code | galaxea_sim/envs/base/bimanual_manipulation.py:210-213 |
| The base environment returns empty info and reset info and never terminates or truncates | upstream_code | galaxea_sim/envs/base/bimanual_manipulation.py:147-157 |
| The base environment's reward is 0 | upstream_code | galaxea_sim/envs/base/bimanual_manipulation.py:232-233 |
| reset(seed, options) sets the robot qpos to init_qpos, resets the controller and the world, and returns the observation and reset info; seed and options are accepted but unused | upstream_code | galaxea_sim/envs/base/bimanual_manipulation.py:159-164 |
| R1Robot's default init_qpos is 20 zeros | upstream_code | galaxea_sim/robots/r1.py:18-26 |
| The R1 URDF defines a four-joint torso, six joints per arm and two gripper finger joints per hand as non-fixed joints | upstream_code | galaxea_sim/assets/r1/robot.urdf:420-1782 |
| The environment's dt is 1/control_freq and decimation is int(dt/timestep) | upstream_code | galaxea_sim/envs/base/base.py:119-125 |
| R1's cameras are a 1280x720 head camera and two 320x240 wrist cameras | upstream_code | galaxea_sim/robots/r1.py:55-90 |
| SapienEnv.close releases only the viewer when one exists | upstream_code | galaxea_sim/envs/base/base.py:60-62 |

Limits: the driver declares none. The action space is the controller's unbounded Box (no finite joint or gripper
bound is stated by the clone), so the bridge derives no action limits and every step input is limited only by the
schema's action length. The environment is simulated (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `sapien:BimanualManipulationEnv`, level F0 (the fake is
kinematic; no rigid-body dynamics), determinism `seeded` (the seed is accepted and recorded, but the upstream reset
does not use it and the fake starts from a fixed placeholder state), `timestep_ms` 10 ms (the constructor's timestep;
`control_freq` 15 makes one control step six 10 ms scene steps), `realtime_factor` 0, clock `lockstep`, reset `full`,
snapshot and restore not offered. The gaps state that the camera rgb_*/depth_* arrays are NOT COVERED (the driver
configures `obs_mode="state"`; the upstream default would add a 1280x720 head image and two 320x240 wrist images),
that no Sapien dynamics or contacts are modelled, that one tick is 60 ms of scene time while `timestep_ms` names the
10 ms physics step, and that the fake was never compared with an upstream run.

Safety: simulated R0 device, `device_kind` `world.sim`. There is no hardware backend and no native stop. The e-stop
is the runtime's software latch: after it no step or reset is accepted until `mhs.safety.reset` clears the latch, and
the state stays readable. Nothing is sent to a machine.

Tags: bimanual-manipulation, galaxea, r1, reinforcement-learning, simulation, gymnasium
