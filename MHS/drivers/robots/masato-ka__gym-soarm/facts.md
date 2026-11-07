# Facts and tags for gh.masato-ka/gym-soarm

Every fact cites its source at commit `d1e47309120a372cf95169a555bda64704c9cf40`: `vendor_doc` (a text file of the
clone such as README.md or docs/*.md, or a PDF page as `docs/manual.pdf:PAGE`) or `upstream_code`
(`path/in/clone.py:LINE`). The same facts are written into `driver.py` (`facts = [...]`); the reference file is
generated from the driver, not from this page.

| fact | source | ref |
|---|---|---|
| SoArm-v0 is registered with entry point gym_soarm.env:SoArmAlohaEnv, max_episode_steps 200, and defaults task pick_place, obs_type pixels_agent_pos, render_mode rgb_array and camera_config front_wrist | upstream_code | gym_soarm/__init__.py:25-34 |
| The environment declares render modes rgb_array and human and render_fps 50 | upstream_code | gym_soarm/env.py:20 |
| The action space is a Box of six absolute joint positions for shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll and gripper | upstream_code | gym_soarm/env.py:103-110 |
| The joint limits are shoulder_pan -1.91986 to 1.91986, shoulder_lift -1.74533 to 1.74533, elbow_flex -1.69 to 1.69, wrist_flex -1.65806 to 1.65806, wrist_roll -2.74385 to 2.84121 and gripper -0.17453 to 1.74533 | upstream_code | gym_soarm/constants.py:21-28 |
| The joint angles are in radians: the start-pose comment says in radians and the README displays joint angles in radians | vendor_doc | README.md:84-87 |
| The simulation timestep is DT = 0.02 s (50 Hz) | upstream_code | gym_soarm/constants.py:4-5 |
| The dm_control Environment is created with control_timestep=DT and an infinite time limit | upstream_code | gym_soarm/env.py:224-240 |
| The starting arm pose is [0.0, 0.0, -1.57, 0.0, 0.0, 0.0] radians | upstream_code | gym_soarm/constants.py:30-38 |
| The gripper observation is normalized to [0, 1] with 0 closed and 1 open: (x - (-0.17453)) / (1.74533 - (-0.17453)) | upstream_code | gym_soarm/constants.py:42-57 |
| The agent_pos observation is the five arm joint positions followed by the normalized gripper position | upstream_code | gym_soarm/tasks/sim.py:144-151 |
| The observation types are state (6 joint positions, 6 velocities, end-effector position and quaternion), pixels (a Dict of camera images) and pixels_agent_pos (pixels plus 6 joint positions) | upstream_code | gym_soarm/env.py:60-101 |
| camera_config front_wrist includes front_camera and wrist_camera; the four accepted values are front_only, front_wrist, diagonal_wrist and all | upstream_code | gym_soarm/env.py:112-123 |
| The task renders four camera images at height 480 and width 640: front_camera, wrist_camera, diagonal_camera and overview_camera | upstream_code | gym_soarm/tasks/sim.py:188-192 |
| A reset seeds the task random generators with the given seed | upstream_code | gym_soarm/env.py:293-296 |
| PickPlaceTask.initialize_episode draws the cube placement from a time-based seed, so the reset seed does not make the pick_place placement repeatable | upstream_code | gym_soarm/tasks/sim.py:246-249 |
| The reset options accept cube_grid_position 0 to 8, -1 with cube_x and cube_y for custom coordinates, or None for random placement, and values outside the grid range raise ValueError | upstream_code | gym_soarm/env.py:276-291 |
| The blue cube grid is 3x3 around table centre (0.0, 0.4) with +-0.10 m in x and +-0.075 m in y, at z = 0.05 m | upstream_code | gym_soarm/tasks/sim.py:251-276 |
| The goal plate starts at (-0.2, 0.4, 0.05) in the scene model | upstream_code | gym_soarm/assets/scene.xml:33 |
| step clips the action to the joint limits before it advances the dm_control physics | upstream_code | gym_soarm/env.py:311-317 |
| SoArmAlohaEnv.step always returns truncated=False | upstream_code | gym_soarm/env.py:329-330 |
| An episode terminates when the blue cube is within 10 mm of the goal plate | upstream_code | gym_soarm/tasks/sim.py:401-419 |
| The pick_place reward is 1 - d / 1.0, clipped to 0, where d is the Euclidean distance between the forward-kinematics end-effector position and the blue cube, and the reward is 0 beyond 1.0 m | upstream_code | gym_soarm/tasks/sim.py:321-361 |
| The forward kinematics maps the first five joint angles to the end-effector position with the SO-ARM101 link offsets | upstream_code | gym_soarm/tasks/sim.py:18-107 |
| The environment depends on mujoco, gymnasium, dm-control and imageio | upstream_code | pyproject.toml:21-26 |
| The task module imports torch, lerobot and a .reward_wrapper module | upstream_code | gym_soarm/tasks/sim.py:1-16 |

Limits: the driver declares none. The action bounds come from the environment's action Box, which the bridge derives
(`action.values` per element, source `upstream_code`, ref `gym_soarm/constants.py:21-28`), and `ticks` (1 to
`max_ticks`, 10000 by default). The device is a simulated world (R0), so no limit is `operator_required`.

Fidelity contract (`driver.py`, `fidelity = {...}`): engine `gymnasium:SoArm-v0`, level F0 (a kinematic stand-in: no
dynamics, contacts, actuator, sensor or noise model), determinism `seeded` with `seed_control` `parameter`, timestep
20 ms (`DT = 0.02` s, `gym_soarm/constants.py:4`), `realtime_factor` 0, clock `lockstep`, reset `full`, no snapshot
and restore. The gaps say what is not modelled: MuJoCo physics, real 480x640x3 camera frames, object contact and
grasping, wall-clock pacing, the stacking task, validation against hardware, snapshots, and that the upstream sim
backend was not run.

Safety: simulated R0 device. The e-stop is the runtime's software latch (no native stop exists); after it no step or
reset is accepted until `mhs.safety.reset` clears the latch, and the last observation stays readable.

Tags: robot-arm, so-arm100, manipulation, reinforcement-learning, simulation, gymnasium
