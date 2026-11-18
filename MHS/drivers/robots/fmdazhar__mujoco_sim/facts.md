# Facts and tags for gh.fmdazhar/mujoco_sim

Every fact cites its source at commit `9c204da4f307c7a711ca4e5cddb1d46a86cab0b1`: `vendor_doc` (a text file
of the clone, here README.md) or `upstream_code` (`path/in/clone:LINE`). The same facts are written into
`driver.py` (`facts = [...]`); the reference file is generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| The clone is a UR5e arm and Robotiq Hand-e gripper simulator with a state-based peg-in-hole Gymnasium environment and custom Gymnasium wrappers | vendor_doc | README.md:3-4 |
| Importing mujoco_sim registers ur5ePegInHoleGymEnv_easy-v0 with entry point mujoco_sim.envs:ur5ePegInHoleGymEnv | upstream_code | mujoco_sim/__init__.py:10-12 |
| setup() names the package and find_packages() and declares no install_requires and no package_data | upstream_code | setup.py:3-8 |
| The environment loads the MuJoCo model from xmls/ur5e_demos.xml beside the env module | upstream_code | mujoco_sim/envs/ur5e_pick_gym_connector.py:17-18 |
| The constructor calls glfw.init and reads the primary monitor size for every render mode | upstream_code | mujoco_sim/envs/ur5e_pick_gym_connector.py:240-242 |
| The env module imports SliderController and ForceFeedback while the class module loads | upstream_code | mujoco_sim/envs/ur5e_pick_gym_connector.py:11-12 |
| ForceFeedback's module imports tkinter and matplotlib at import time | upstream_code | mujoco_sim/utils/force_feedback.py:1-5 |
| SliderController's module imports tkinter at import time | upstream_code | mujoco_sim/utils/slider_controller.py:1 |
| The renderer module imports imageio at module scope | upstream_code | mujoco_sim/mujoco_rendering.py:6 |
| The wrapper module imports Keyboard and SpaceMouse at load time | upstream_code | mujoco_sim/envs/wrappers.py:6-8 |
| SpacemouseIntervention tries SpaceMouse and on OSError constructs Keyboard | upstream_code | mujoco_sim/envs/wrappers.py:209-215 |
| Keyboard opens a pygame display window in its constructor | upstream_code | mujoco_sim/devices/keyboard.py:21-22 |
| SpaceMouse opens the HID device with hid.device().open | upstream_code | mujoco_sim/devices/spacemouse.py:183-184 |
| The env module imports scipy.spatial.transform.Rotation, glfw and OpenGL at load time | upstream_code | mujoco_sim/envs/ur5e_pick_gym_connector.py:13-15 |
| The easy variant applies XYZGripperCloseEnv, SpacemouseIntervention, CustomObsWrapper and FlattenObservation | upstream_code | mujoco_sim/__init__.py:13-42 |
| The easy registration passes config ENV_CONFIG version 0 and UR5E_CONFIG tcp_xyz_randomize True and mocap_orient True | upstream_code | mujoco_sim/__init__.py:44-54 |
| The easy variant ends with gymnasium's FlattenObservation wrapper | upstream_code | mujoco_sim/__init__.py:38-41 |
| The base action space is a seven-element Box from -1.0 to 1.0 | upstream_code | mujoco_sim/envs/ur5e_pick_gym_connector.py:234-236 |
| XYZGripperCloseEnv narrows the action space to the first three elements (x, y, z) of the base Box | upstream_code | mujoco_sim/envs/wrappers.py:134-138 |
| The observation space is a Dict of nine Box members, each bounded by +-1e6 | upstream_code | mujoco_sim/envs/ur5e_pick_gym_connector.py:172-206 |
| The easy variant keeps connector_pose, controller_pose, ur5e/tcp_pose, ur5e/tcp_vel, ur5e/wrist_force and ur5e/wrist_torque | upstream_code | mujoco_sim/__init__.py:27-36 |
| CustomObsWrapper rebuilds the state Dict with only the kept keys | upstream_code | mujoco_sim/envs/wrappers.py:54-62 |
| controller_pose is a six-element array: the controller position and its orientation | upstream_code | mujoco_sim/envs/ur5e_pick_gym_connector.py:540-542 |
| control_dt is 0.02 s and physics_dt is 0.002 s | upstream_code | mujoco_sim/config/config.py:13-14 |
| n_substeps is int(control_dt // physics_dt), so one control step runs ten physics steps | upstream_code | mujoco_sim/mujoco_gym_env.py:34-36 |
| _max_episode_steps is 1000.0 | upstream_code | mujoco_sim/config/config.py:15 |
| step sets truncated once _elapsed_steps reaches _max_episode_steps | upstream_code | mujoco_sim/envs/ur5e_pick_gym_connector.py:471-475 |
| step returns observation, reward, terminated, truncated and info | upstream_code | mujoco_sim/envs/ur5e_pick_gym_connector.py:476 |
| reset returns the observation and an empty info dict | upstream_code | mujoco_sim/envs/ur5e_pick_gym_connector.py:391-393 |
| reset accepts an optional seed argument | upstream_code | mujoco_sim/envs/ur5e_pick_gym_connector.py:257 |
| Port randomization draws with np.random.uniform from numpy's global generator, so the reset seed argument does not seed it | upstream_code | mujoco_sim/envs/ur5e_pick_gym_connector.py:276-279 |
| reward_shaping is False and sparse_reward_weights is 0 by default | upstream_code | mujoco_sim/config/config.py:88-92 |
| The step returns the sparse reward while reward_shaping is False | upstream_code | mujoco_sim/envs/ur5e_pick_gym_connector.py:721-723 |
| task_complete_tolerance is 0.0025 | upstream_code | mujoco_sim/config/config.py:93 |
| The task is complete when the connector-to-port distance is below the tolerance | upstream_code | mujoco_sim/envs/ur5e_pick_gym_connector.py:710 |
| The UR5e home joint position is [-1.907, -1.565, 2.350, -2.355, -1.571, 1.234] | upstream_code | mujoco_sim/config/config.py:40 |
| The default Cartesian workspace bounds are [0.2, -0.3, 0.0] to [0.6, 0.3, 0.05] | upstream_code | mujoco_sim/config/config.py:41 |
| The environment declares the render modes human and rgb_array | upstream_code | mujoco_sim/envs/ur5e_pick_gym_connector.py:30-35 |
| The clone pins mujoco 3.2.5 and gymnasium 1.0.0 | upstream_code | requirements.txt:2-3 |

Limits: the driver declares none of its own. The only bound is the action space, which the Gymnasium bridge
derives from the environment: the easy variant's ``XYZGripperCloseEnv`` keeps the first three elements of the
base ``Box(-1.0, 1.0)``, so ``action.values`` is three numbers each in [-1, 1] with no source and the ref
``action_space of the fake backend .fake:FakeUR5ePegInHoleEnv`` (``mujoco_sim/envs/wrappers.py:134-138``),
plus the bridge's ``ticks`` bound (1 to 10000). The device is simulated (R0), so no limit is
``operator_required``.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `mujoco:ur5ePegInHoleGymEnv_easy-v0`, level F1
(MuJoCo rigid-body dynamics with contacts, no validation), determinism `seeded` with `seed_control`
`parameter`, timestep 20 ms (one control step of `control_dt` 0.02 s,
`mujoco_sim/config/config.py:13`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot and
restore. The observation is the 27-value flattened easy-variant array (six kept members of 6, 6, 3, 3, 3 and
6 values). The gaps say what the fake does not model and that it was never compared with the upstream
environment.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no
step or reset is accepted until `mhs.safety.reset` clears the latch (a simulator needs no operator for that),
and the last world state stays readable.

Sim path (`driver.py`): `backends["sim"]` is `_build_sim_env`. `setup.py:3-8` installs the `find_packages()`
modules and no `package_data`, so the wheel omits `mujoco_sim/envs/xmls`. `source-path.txt` is not used: the
clone has `setup.py`. `_build_sim_env` loads `mujoco_sim/envs/ur5e_pick_gym_connector.py` from the pinned
checkout by path, without inserting it into the import table, so `_XML_PATH` at
`ur5e_pick_gym_connector.py:17-18` is the checkout's `xmls/ur5e_demos.xml` (the meshes are the includes at
`ur5e1.xml:68-93`). It then calls that class with the easy registration's `config` (`mujoco_sim/__init__.py:44-54`)
and applies `XYZGripperCloseEnv`, `SpacemouseIntervention`, `CustomObsWrapper` and `FlattenObservation` in that
order (`mujoco_sim/__init__.py:13-42`). The fake backend is still `.fake:FakeUR5ePegInHoleEnv` and does not
import the clone. `ur5e_pick_gym_connector.py:241-242` calls `glfw.init()` and `glfw.get_video_mode` for every
`render_mode`, `keyboard.py:21-22` opens a pygame window when the SpaceMouse is absent (`wrappers.py:209-215`),
and `force_feedback.py:1` plus `slider_controller.py:1` import tkinter while the env module loads
(`ur5e_pick_gym_connector.py:11-12`). There is no constructor flag that skips those calls. `display.txt` asks
for Xvfb, which is also what `docker/Dockerfile:36-41`, `docker/entrypoint.sh:63` and
`docker/docker-compose.yml:26` use. `constraints.txt` pins `gymnasium==1.0.0` and `mujoco==3.2.5` from
`requirements.txt:2-3`, and `requirements.txt` installs the modules the env import loads because `setup.py:3-8`
declares no `install_requires`.

Tags: ur5e, peg-in-hole, mujoco, manipulation, reinforcement-learning, simulation, gymnasium
