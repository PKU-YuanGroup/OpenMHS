# Facts and tags for gh.yzqin/dexpoint-release

Every fact cites its source at commit `17f1e238bb120d92baabe8207494d48476fea289`: `vendor_doc` (a text file of the
clone such as README.md) or `upstream_code` (`path/in/clone.py:LINE`). The same facts are written into `driver.py`
(`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The repository contains the simulated environment and training code for DexPoint | vendor_doc | README.md:11-12 |
| The environment is constructed in-process from its Python class with keyword arguments, with no transport setup | upstream_code | example/example_use_state_only_env.py:14-22 |
| AllegroRelocateRLEnv is the concrete environment; LabRelocateEnv and BaseRLEnv are its parents | upstream_code | dexpoint/env/rl_env/relocate_env.py:16 |
| The constructor defaults the robot to allegro_hand_xarm6_wrist_mounted_face_front, the object category to YCB and the object to tomato_soup_can | upstream_code | dexpoint/env/rl_env/relocate_env.py:17-19 |
| The default robot's configuration declares hand_dof 16 and arm_dof 6 | upstream_code | dexpoint/utils/common_robot_utils.py:53-56 |
| The action space is Box(low=-1, high=1) with shape (action_dim,) | upstream_code | dexpoint/env/rl_env/base.py:400-402 |
| action_dim returns the robot's degree-of-freedom count | upstream_code | dexpoint/env/rl_env/base.py:78-80 |
| The oracle state concatenates robot qpos (dof), palm position (3), object pose (7), object-to-tip offsets (12), contact flags (5), target offset (3), target quaternion (4) and target angle (1) | upstream_code | dexpoint/env/rl_env/relocate_env.py:87-91 |
| For a state-only environment obs_dim is the length of the oracle state | upstream_code | dexpoint/env/rl_env/base.py:314-319 |
| The observation space is a Box from -infinity to +infinity with obs_dim elements | upstream_code | dexpoint/env/rl_env/base.py:404-408 |
| The SAPIEN scene timestep is 0.005 s | upstream_code | dexpoint/env/sim_env/relocate_env.py:28-29 |
| One control step advances frame_skip simulation steps: control_time_step is the scene timestep times frame_skip | upstream_code | dexpoint/env/rl_env/base.py:111-113 |
| The horizon is 200 control steps | upstream_code | dexpoint/env/rl_env/relocate_env.py:155-157 |
| OBJECT_LIFT_LOWER_LIMIT is -0.03 | upstream_code | dexpoint/env/rl_env/relocate_env.py:13 |
| An episode is done when object_lift is below OBJECT_LIFT_LOWER_LIMIT | upstream_code | dexpoint/env/rl_env/relocate_env.py:152-153 |
| step applies the action, updates the cached state and returns (observation, reward, done, info); at the horizon it sets done and info['TimeLimit.truncated'] | upstream_code | dexpoint/env/rl_env/base.py:204-217 |
| reset re-seeds when a seed is given, resets the internal state and returns the new observation | upstream_code | dexpoint/env/rl_env/relocate_env.py:124-150 |
| The object start pose is drawn uniformly in x and y from (-0.1, 0.1) times randomness_scale at the object height | upstream_code | dexpoint/env/sim_env/relocate_env.py:81-88 |
| The target pose is drawn uniformly in x and y from (-0.2, 0.2) times randomness_scale at height 0.25 | upstream_code | dexpoint/env/sim_env/relocate_env.py:91-100 |
| seed installs the random generator and returns [seed] | upstream_code | dexpoint/env/sim_env/base.py:58-60 |
| The reward gives 0.5 on contact, 10 times the lift clipped to 0..0.2, a 1.0 bonus above 0.02 lift plus 1/(0.04 + target distance), and divides the total by 10 | upstream_code | dexpoint/env/rl_env/relocate_env.py:100-122 |
| The thumb's finger reward scale is 0.04 and the other three tips use 0.01 | upstream_code | dexpoint/env/rl_env/relocate_env.py:52-53 |
| The package requires numpy, transforms3d, gym 0.25.2, sapien 2.1.0, open3d, imageio and torch, and declares Python 3.8 or newer | upstream_code | setup.py:18-27 |
| The installation instructions download day.ktx and place it at assets/misc/ktx/day.ktx | vendor_doc | README.md:37-39 |

Limits: the driver declares none. `cap.world.step.v1` takes `ticks` (1 to `max_ticks`, 10000 by default) and an
`action` derived from the environment's action space: `Box(-1, 1)` with one element per degree of freedom of the
default robot (6 arm + 16 hand = 22, from `common_robot_utils.py:53-56`; `action_dim` is `robot.dof`). The gymnasium
bridge derives those per-element bounds from the live environment and gives them the source `upstream_code` and the
ref `dexpoint/env/rl_env/base.py:401-402`; they are not a hand-written Limit. The device is simulated (R0), so no
limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `analytic:dexpoint-allegro-relocate-stand-in`, level F0
(a kinematic stand-in: no dynamics, contacts, friction, actuator or sensor model), determinism `seeded` with
`seed_control` `parameter`, timestep 50 ms (the upstream control step: 0.005 s scene timestep x the constructor
default `frame_skip` 10, `dexpoint/env/rl_env/relocate_env.py:17` and `dexpoint/env/rl_env/base.py:111-113`),
`realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and restore. The gaps say what is not modelled,
including that the stand-in was never compared with a SAPIEN run and that its geometry is placeholder data.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that), and the last
observation and state stay readable. No hardware backend is declared, so the model-written package cannot start one.

Tags: dexpoint, dexterous-manipulation, allegro, sapien, simulation, reinforcement-learning, point-cloud
